"""
AlgoVoi CrewAI Adapter
=======================

Payment-gate any CrewAI crew, task, or agent tool using x402, MPP, or AP2
— paid in USDC on Algorand, VOI, Hedera, or Stellar.

Three integration modes:

  1. Server-side gate — wrap crew.kickoff() (Flask / FastAPI)
     -----------------------------------------
     from crewai_algovoi import AlgoVoiCrewAI

     gate = AlgoVoiCrewAI(
         openai_key        = "sk-...",
         algovoi_key       = "algv_...",
         tenant_id         = "your-tenant-uuid",
         payout_address    = "YOUR_ALGORAND_ADDRESS",
         protocol          = "mpp",               # "mpp" | "ap2" | "x402"
         network           = "algorand-mainnet",  # see NETWORKS below
         amount_microunits = 10000,               # 0.01 USDC per call
     )

     # Flask
     @app.route("/ai/run", methods=["POST"])
     def run():
         body   = request.get_json(silent=True) or {}
         result = gate.check(dict(request.headers), body)
         if result.requires_payment:
             return result.as_flask_response()
         output = gate.crew_kickoff(my_crew, inputs=body)
         return jsonify({"content": output})

     # Or use the convenience wrapper:
     @app.route("/ai/run", methods=["POST"])
     def run():
         return gate.flask_guard(my_crew)

  2. CrewAI agent tool
     -----------------------------------------
     tool = gate.as_tool(resource_fn=lambda q: my_handler(q), tool_name="premium_kb")
     # Drop into any CrewAI agent:
     agent = Agent(role="Researcher", ..., tools=[tool])
     # Agent generates: {"query": "...", "payment_proof": "<base64>"}
     # Tool returns challenge JSON if proof missing, or resource_fn(query) if verified.

  3. Custom kickoff helper
     -----------------------------------------
     result = gate.check(headers, body)
     if not result.requires_payment:
         output = gate.crew_kickoff(crew, inputs={"topic": body["topic"]})
         # output = crew_result.raw (str)

Networks:
    algorand-mainnet, voi-mainnet, hedera-mainnet, stellar-mainnet

Protocols:
    mpp  — IETF draft-ryan-httpauth-payment (WWW-Authenticate: Payment)
    ap2  — AP2 v0.1 CartMandate/PaymentMandate + AlgoVoi crypto-algo extension
    x402 — x402 spec v1 (X-PAYMENT-REQUIRED / X-PAYMENT)
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Optional, Type

__version__ = "1.0.0"
__all__ = ["AlgoVoiCrewAI", "AlgoVoiPaymentTool", "CrewAIResult"]

# ── Path helpers ──────────────────────────────────────────────────────────────

# Three levels up from ai-agent-frameworks/crewai/crewai_algovoi.py
# → platform-adapters/
_ADAPTERS_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _add_path(subdir: str) -> None:
    p = os.path.join(_ADAPTERS_ROOT, subdir)
    if p not in sys.path:
        sys.path.insert(0, p)


# ── Supported networks / protocols ────────────────────────────────────────────

NETWORKS = frozenset({
    "algorand-mainnet",
    "voi-mainnet",
    "hedera-mainnet",
    "stellar-mainnet",
})

PROTOCOLS = frozenset({"mpp", "ap2", "x402"})

# ── Body-size cap for flask_guard ─────────────────────────────────────────────

_MAX_FLASK_BODY = 1_048_576  # 1 MiB

# ── Pydantic PrivateAttr (always available — pydantic is a universal dep) ─────

try:
    from pydantic import PrivateAttr as _PrivateAttr, BaseModel, Field
except ImportError:  # pragma: no cover
    def _PrivateAttr(**_: Any) -> Any:  # type: ignore[misc]
        return None

    class BaseModel:  # type: ignore[no-redef]
        pass

    def Field(*args: Any, **kwargs: Any) -> Any:  # type: ignore[misc]
        return None

# ── CrewAI BaseTool stub (used when crewai not installed) ─────────────────────

_CREWAI_AVAILABLE = False
try:
    from crewai.tools import BaseTool  # type: ignore
    _CREWAI_AVAILABLE = True
except ImportError:
    class BaseTool:  # type: ignore[no-redef]
        """Stub when crewai is not installed."""

        def __init__(self, **kwargs: Any) -> None:
            for k, v in kwargs.items():
                object.__setattr__(self, k, v)

        def _run(self, **kwargs: Any) -> str:
            raise NotImplementedError


# ── Input schema for AlgoVoiPaymentTool ──────────────────────────────────────

class PaymentToolInput(BaseModel):
    """Input schema for AlgoVoiPaymentTool — validated by CrewAI before _run()."""
    query: Any = Field(
        description="The question or task to process once payment is verified.",
    )
    payment_proof: str = Field(
        default="",
        description="Base64-encoded payment proof (MPP / AP2 / x402). "
                    "Leave empty to receive the payment challenge.",
    )


# ── Gate factory ──────────────────────────────────────────────────────────────

def _build_gate(
    protocol: str,
    algovoi_key: str,
    tenant_id: str,
    payout_address: str,
    network: str,
    amount_microunits: int,
    resource_id: str,
) -> Any:
    """Construct the appropriate AlgoVoi gate for the given protocol."""
    if protocol == "mpp":
        _add_path("mpp-adapter")
        from mpp import MppGate  # type: ignore
        return MppGate(
            api_base="https://api1.ilovechicken.co.uk", api_key=algovoi_key,
            tenant_id=tenant_id,
            payout_address=payout_address,
            networks=[network],
            amount_microunits=amount_microunits,
            resource_id=resource_id,
        )
    elif protocol == "ap2":
        _add_path("ap2-adapter")
        from ap2 import Ap2Gate  # type: ignore
        return Ap2Gate(
            merchant_id=tenant_id, api_base="https://api1.ilovechicken.co.uk", api_key=algovoi_key,
            tenant_id=tenant_id,
            payout_address=payout_address,
            networks=[network],
            amount_microunits=amount_microunits,
        )
    else:  # x402
        _add_path("ai-adapters/openai")
        from openai_algovoi import _X402Gate  # type: ignore
        return _X402Gate(
            api_base="https://api1.ilovechicken.co.uk", api_key=algovoi_key,
            tenant_id=tenant_id,
            payout_address=payout_address,
            network=network,
            amount_microunits=amount_microunits,
        )


# ── Result wrapper ────────────────────────────────────────────────────────────

class CrewAIResult:
    """Thin wrapper around the underlying gate result."""

    def __init__(self, gate_result: Any) -> None:
        self._r = gate_result

    @property
    def requires_payment(self) -> bool:
        return self._r.requires_payment

    @property
    def error(self) -> Optional[str]:
        return getattr(self._r, "error", None)

    @property
    def receipt(self) -> Any:
        return getattr(self._r, "receipt", None)

    @property
    def mandate(self) -> Any:
        return getattr(self._r, "mandate", None)

    def as_flask_response(self) -> Any:
        return self._r.as_flask_response()

    def as_wsgi_response(self) -> Any:
        return self._r.as_wsgi_response()


# ── Main adapter ──────────────────────────────────────────────────────────────

class AlgoVoiCrewAI:
    """
    Payment-gate wrapper for CrewAI.

    Args:
        algovoi_key (str): AlgoVoi API key (``algv_...``).
        tenant_id (str): AlgoVoi tenant UUID.
        payout_address (str): On-chain address to receive payments.
        openai_key (str | None): OpenAI API key — used to build a default
            ``crewai.LLM`` when ``llm`` is not supplied.
        llm: Pre-built CrewAI ``LLM`` instance (takes precedence over
            ``openai_key`` / ``model``).
        protocol (str): ``"mpp"`` | ``"ap2"`` | ``"x402"`` (default: ``"mpp"``).
        network (str): Chain network key (default: ``"algorand-mainnet"``).
        amount_microunits (int): Price per call in USDC microunits (default: ``10000``).
        model (str): LiteLLM model identifier passed to ``crewai.LLM`` — use
            ``"openai/gpt-4o"`` format (default: ``"openai/gpt-4o"``).
        base_url (str | None): Override OpenAI API base URL (for compatible providers).
        resource_id (str): Resource identifier used in MPP challenges
            (default: ``"ai-crew"``).
    """

    def __init__(
        self,
        algovoi_key: str,
        tenant_id: str,
        payout_address: str,
        openai_key: Optional[str] = None,
        llm: Any = None,
        protocol: str = "mpp",
        network: str = "algorand-mainnet",
        amount_microunits: int = 10_000,
        model: str = "openai/gpt-4o",
        base_url: Optional[str] = None,
        resource_id: str = "ai-crew",
    ) -> None:
        if protocol not in PROTOCOLS:
            raise ValueError(f"protocol must be one of {sorted(PROTOCOLS)}")
        if network not in NETWORKS:
            raise ValueError(f"network must be one of {sorted(NETWORKS)}")

        self._openai_key = openai_key
        self._llm = llm
        self._model = model
        self._base_url = base_url

        self._gate = _build_gate(
            protocol=protocol,
            algovoi_key=algovoi_key,
            tenant_id=tenant_id,
            payout_address=payout_address,
            network=network,
            amount_microunits=amount_microunits,
            resource_id=resource_id,
        )

    # ── Gate ──────────────────────────────────────────────────────────────────

    def check(self, headers: dict, body: Optional[dict] = None) -> CrewAIResult:
        """
        Verify a payment proof from request headers.

        Returns a :class:`CrewAIResult` whose ``requires_payment`` flag
        indicates whether a 402 challenge should be returned to the client.
        """
        try:
            raw = self._gate.check(headers, body or {})
        except TypeError:
            raw = self._gate.check(headers)
        return CrewAIResult(raw)

    # ── LLM helper ────────────────────────────────────────────────────────────

    def _ensure_llm(self) -> Any:
        if self._llm is not None:
            return self._llm
        from crewai import LLM  # type: ignore

        kwargs: dict[str, Any] = {"model": self._model}
        if self._openai_key:
            kwargs["api_key"] = self._openai_key
        if self._base_url:
            kwargs["base_url"] = self._base_url
        self._llm = LLM(**kwargs)
        return self._llm

    # ── Crew kickoff ──────────────────────────────────────────────────────────

    def crew_kickoff(self, crew: Any, inputs: Optional[dict] = None) -> str:
        """
        Run ``crew.kickoff(inputs=inputs)`` and return the raw string output.

        Call only after ``gate.check()`` returns ``requires_payment = False``.

        ``CrewOutput.raw`` is returned; falls back to ``str(result)`` for
        forward-compatibility if the attribute is absent.

        Example::

            result = gate.check(headers, body)
            if not result.requires_payment:
                output = gate.crew_kickoff(my_crew, inputs={"topic": body["topic"]})
                return jsonify({"content": output})
        """
        crew_output = crew.kickoff(inputs=inputs or {})
        return getattr(crew_output, "raw", str(crew_output))

    # ── Agent tool ────────────────────────────────────────────────────────────

    def as_tool(
        self,
        resource_fn: Any,
        tool_name: str = "algovoi_payment_gate",
        tool_description: str = (
            "Payment-gated resource. "
            "Provide 'query' with your question and 'payment_proof' (base64-encoded). "
            "Returns a payment challenge if proof is absent or invalid, "
            "or the resource response when payment is verified."
        ),
    ) -> "AlgoVoiPaymentTool":
        """
        Return an :class:`AlgoVoiPaymentTool` wrapping this gate and ``resource_fn``.

        Drop the returned tool into any CrewAI ``Agent``::

            tool  = gate.as_tool(resource_fn=my_handler, tool_name="premium_kb")
            agent = Agent(role="Researcher", goal="...", backstory="...", tools=[tool])
        """
        return AlgoVoiPaymentTool(
            adapter=self,
            resource_fn=resource_fn,
            name=tool_name,
            description=tool_description,
        )

    # ── Flask convenience ─────────────────────────────────────────────────────

    def flask_guard(
        self,
        crew: Any,
        inputs_fn: Optional[Any] = None,
    ) -> Any:
        """
        Convenience Flask handler — check + crew.kickoff() in one call.

        Reads ``request.headers`` and ``request.json`` automatically.

        Args:
            crew: A pre-built ``crewai.Crew`` instance.
            inputs_fn: Optional callable ``(body: dict) -> dict`` that extracts
                the crew ``inputs`` dict from the request body. If ``None``,
                the entire request body is passed as ``inputs``.

        Returns a Flask ``Response`` (402 + challenge) or a JSON dict
        with ``{"content": "..."}`` that the view can return directly.

        Rejects bodies over 1 MiB with HTTP 413 before parsing.
        """
        from flask import request, Response, jsonify  # type: ignore

        if request.content_length and request.content_length > _MAX_FLASK_BODY:
            return Response(
                '{"error":"Request Too Large"}',
                status=413,
                mimetype="application/json",
            )

        body = request.get_json(silent=True) or {}
        result = self.check(dict(request.headers), body)
        if result.requires_payment:
            return result.as_flask_response()

        inputs = inputs_fn(body) if callable(inputs_fn) else body
        return jsonify({"content": self.crew_kickoff(crew, inputs=inputs)})


# ── Agent tool class ──────────────────────────────────────────────────────────

class AlgoVoiPaymentTool(BaseTool):
    """
    CrewAI ``BaseTool`` that wraps an AlgoVoi payment gate.

    Register with any CrewAI agent::

        tool  = gate.as_tool(resource_fn=my_handler, tool_name="premium_kb")
        agent = Agent(role="Researcher", goal="...", backstory="...", tools=[tool])

    The agent generates structured input which CrewAI validates against
    ``PaymentToolInput`` before calling ``_run()``:

        query         — the question or task to process
        payment_proof — base64-encoded payment proof (empty → returns challenge)

    Returns challenge JSON (``{"error": "payment_required", ...}``) when proof
    is absent or invalid, or ``str(resource_fn(query))`` when verified.
    """

    name: str = "algovoi_payment_gate"
    description: str = (
        "Payment-gated resource. "
        "Provide 'query' with your question and 'payment_proof' (base64-encoded). "
        "Returns a payment challenge if proof is absent or invalid, "
        "or the resource response when payment is verified."
    )
    args_schema: Type[BaseModel] = PaymentToolInput  # type: ignore[assignment]

    _adapter: Any = _PrivateAttr(default=None)
    _resource_fn: Any = _PrivateAttr(default=None)

    def __init__(
        self,
        adapter: Any,
        resource_fn: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        object.__setattr__(self, "_adapter", adapter)
        object.__setattr__(self, "_resource_fn", resource_fn)

    def _run(self, query: Any = "", payment_proof: str = "", **kwargs: Any) -> str:
        """
        Verify payment and return challenge JSON or resource response.

        Called by CrewAI after validating ``PaymentToolInput`` — receives
        ``query`` and ``payment_proof`` as keyword arguments.
        """
        query_str = str(query) if query is not None else ""
        headers: dict[str, str] = (
            {"Authorization": f"Payment {payment_proof}"} if payment_proof else {}
        )

        try:
            result = self._adapter.check(headers, {})
        except TypeError:
            result = self._adapter.check(headers)

        if result.requires_payment:
            challenge: dict[str, Any] = {
                "error":  "payment_required",
                "detail": result.error or "Payment proof required",
            }
            return json.dumps(challenge)

        try:
            return str(self._resource_fn(query_str))
        except Exception as exc:
            return json.dumps({"error": "resource_error", "detail": str(exc)})
