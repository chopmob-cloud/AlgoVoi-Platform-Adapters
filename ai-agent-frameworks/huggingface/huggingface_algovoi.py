"""
AlgoVoi Hugging Face Adapter
==============================

Payment-gate any Hugging Face InferenceClient call, transformers pipeline,
or smolagents agent tool using x402, MPP, or AP2 — paid in USDC on Algorand,
VOI, Hedera, or Stellar.

Three integration modes:

  1. Server-side gate — InferenceClient.chat_completion() (Flask / FastAPI)
     -----------------------------------------
     from huggingface_algovoi import AlgoVoiHuggingFace

     gate = AlgoVoiHuggingFace(
         hf_token          = "hf_...",
         algovoi_key       = "algv_...",
         tenant_id         = "your-tenant-uuid",
         payout_address    = "YOUR_ALGORAND_ADDRESS",
         protocol          = "mpp",               # "mpp" | "ap2" | "x402"
         network           = "algorand-mainnet",  # see NETWORKS below
         amount_microunits = 10000,               # 0.01 USDC per call
         model             = "meta-llama/Meta-Llama-3-8B-Instruct",
     )

     # Flask
     @app.route("/ai/chat", methods=["POST"])
     def chat():
         body   = request.get_json(silent=True) or {}
         result = gate.check(dict(request.headers), body)
         if result.requires_payment:
             return result.as_flask_response()
         return jsonify({"content": gate.complete(body["messages"])})

  2. transformers pipeline gate
     -----------------------------------------
     from transformers import pipeline

     pipe = pipeline("text-generation", model="...", token="hf_...")

     result = gate.check(headers, body)
     if not result.requires_payment:
         output = gate.inference_pipeline(pipe, body["messages"])

  3. smolagents agent tool
     -----------------------------------------
     tool = gate.as_tool(resource_fn=lambda q: my_handler(q), tool_name="premium_kb")

     # Drop into any smolagents CodeAgent or ToolCallingAgent:
     from smolagents import ToolCallingAgent, InferenceClientModel
     agent = ToolCallingAgent(tools=[tool], model=InferenceClientModel(...))
     agent.run("Access the premium knowledge base to answer: What is AlgoVoi?")

     # Agent passes: query="..." and payment_proof="<base64>" or ""
     # Tool returns challenge JSON if proof absent/invalid, or resource_fn(query) if verified.

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
from typing import Any, Optional

__version__ = "1.0.0"
__all__ = ["AlgoVoiHuggingFace", "AlgoVoiPaymentTool", "HuggingFaceResult"]

# ── Path helpers ──────────────────────────────────────────────────────────────

# Three levels up from ai-agent-frameworks/huggingface/huggingface_algovoi.py
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

# ── smolagents Tool stub (used when smolagents not installed) ─────────────────

_SMOLAGENTS_AVAILABLE = False
try:
    from smolagents import Tool  # type: ignore
    _SMOLAGENTS_AVAILABLE = True
except ImportError:
    class Tool:  # type: ignore[no-redef]
        """Stub when smolagents is not installed."""
        name: str = ""
        description: str = ""
        inputs: dict = {}
        output_type: str = "string"

        def __init__(self) -> None:
            pass

        def forward(self, **kwargs: Any) -> str:
            raise NotImplementedError


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

class HuggingFaceResult:
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

class AlgoVoiHuggingFace:
    """
    Payment-gate wrapper for Hugging Face.

    Supports three integration surfaces:

    * ``complete(messages)`` — ``InferenceClient.chat_completion()``
    * ``inference_pipeline(pipe, inputs)`` — any ``transformers.pipeline()``
    * ``as_tool(resource_fn)`` — ``smolagents.Tool`` for agent integration

    Args:
        algovoi_key (str): AlgoVoi API key (``algv_...``).
        tenant_id (str): AlgoVoi tenant UUID.
        payout_address (str): On-chain address to receive payments.
        hf_token (str | None): Hugging Face access token (``hf_...``).
            Used by ``complete()`` via ``InferenceClient``.
        protocol (str): ``"mpp"`` | ``"ap2"`` | ``"x402"`` (default: ``"mpp"``).
        network (str): Chain network key (default: ``"algorand-mainnet"``).
        amount_microunits (int): Price per call in USDC microunits (default: ``10000``).
        model (str): HF model ID for ``InferenceClient``
            (default: ``"meta-llama/Meta-Llama-3-8B-Instruct"``).
        base_url (str | None): Custom HF Inference endpoint URL.
        resource_id (str): Resource identifier used in MPP challenges
            (default: ``"ai-inference"``).
    """

    def __init__(
        self,
        algovoi_key: str,
        tenant_id: str,
        payout_address: str,
        hf_token: Optional[str] = None,
        protocol: str = "mpp",
        network: str = "algorand-mainnet",
        amount_microunits: int = 10_000,
        model: str = "meta-llama/Meta-Llama-3-8B-Instruct",
        base_url: Optional[str] = None,
        resource_id: str = "ai-inference",
    ) -> None:
        if protocol not in PROTOCOLS:
            raise ValueError(f"protocol must be one of {sorted(PROTOCOLS)}")
        if network not in NETWORKS:
            raise ValueError(f"network must be one of {sorted(NETWORKS)}")

        self._hf_token = hf_token
        self._model = model
        self._base_url = base_url
        self._client: Any = None  # lazy InferenceClient

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

    def check(self, headers: dict, body: Optional[dict] = None) -> HuggingFaceResult:
        """
        Verify a payment proof from request headers.

        Returns a :class:`HuggingFaceResult` whose ``requires_payment`` flag
        indicates whether a 402 challenge should be returned to the client.
        """
        try:
            raw = self._gate.check(headers, body or {})
        except TypeError:
            raw = self._gate.check(headers)
        return HuggingFaceResult(raw)

    # ── InferenceClient helper ────────────────────────────────────────────────

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        from huggingface_hub import InferenceClient  # type: ignore

        kwargs: dict[str, Any] = {}
        if self._hf_token:
            kwargs["token"] = self._hf_token
        if self._model:
            kwargs["model"] = self._model
        if self._base_url:
            kwargs["base_url"] = self._base_url
        self._client = InferenceClient(**kwargs)
        return self._client

    def complete(self, messages: list[dict]) -> str:
        """
        Call ``InferenceClient.chat_completion()`` with OpenAI-format messages.

        Returns the assistant reply as a plain string.

        Recognised roles: ``system``, ``user``, ``assistant`` — passed through
        directly to the HF Inference API (OpenAI-compatible format).
        """
        client = self._ensure_client()
        response = client.chat_completion(messages=messages)
        return response.choices[0].message.content

    # ── transformers pipeline helper ──────────────────────────────────────────

    def inference_pipeline(self, pipe: Any, inputs: Any) -> str:
        """
        Run a ``transformers.pipeline()`` call and return the text response.

        Handles both chat-format output (list of message dicts, where the last
        entry is the assistant's reply) and plain string output.

        Call only after ``gate.check()`` returns ``requires_payment = False``.

        Example::

            from transformers import pipeline
            pipe = pipeline("text-generation", model="...", token="hf_...")

            result = gate.check(headers, body)
            if not result.requires_payment:
                answer = gate.inference_pipeline(pipe, body["messages"])
        """
        result = pipe(inputs)
        if isinstance(result, list) and result:
            first = result[0]
            if isinstance(first, dict):
                generated = first.get("generated_text", "")
                if isinstance(generated, list) and generated:
                    # Chat template mode: last entry is the assistant's message dict
                    return str(generated[-1].get("content", ""))
                return str(generated)
        return str(result)

    # ── Agent tool ────────────────────────────────────────────────────────────

    def as_tool(
        self,
        resource_fn: Any,
        tool_name: str = "algovoi_payment_gate",
        tool_description: str = (
            "Payment-gated resource. "
            "Provide 'query' with your question and 'payment_proof' (base64-encoded). "
            "Returns a payment challenge JSON if proof is absent or invalid, "
            "or the resource response when payment is verified."
        ),
    ) -> "AlgoVoiPaymentTool":
        """
        Return an :class:`AlgoVoiPaymentTool` wrapping this gate and ``resource_fn``.

        Drop the returned tool into any smolagents agent::

            tool  = gate.as_tool(resource_fn=my_handler, tool_name="premium_kb")
            agent = ToolCallingAgent(tools=[tool], model=InferenceClientModel(...))
            agent.run("Use premium_kb to answer my question.")
        """
        return AlgoVoiPaymentTool(
            adapter=self,
            resource_fn=resource_fn,
            tool_name=tool_name,
            tool_description=tool_description,
        )

    # ── Flask convenience ─────────────────────────────────────────────────────

    def flask_guard(self) -> Any:
        """
        Convenience Flask handler — check + complete in one call.

        Reads ``request.headers`` and ``request.json`` automatically.
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
        messages = body.get("messages", [])
        return jsonify({"content": self.complete(messages)})


# ── Agent tool class ──────────────────────────────────────────────────────────

class AlgoVoiPaymentTool(Tool):
    """
    smolagents ``Tool`` that wraps an AlgoVoi payment gate.

    Register with any smolagents agent::

        tool  = gate.as_tool(resource_fn=my_handler, tool_name="premium_kb")
        agent = ToolCallingAgent(tools=[tool], model=InferenceClientModel(...))

    The agent generates input which smolagents routes to ``forward()``:

        query         — the question or task to process
        payment_proof — base64-encoded payment proof (empty → returns challenge)

    Returns challenge JSON (``{"error": "payment_required", ...}``) when proof
    is absent or invalid, or ``str(resource_fn(query))`` when verified.
    """

    name: str = "algovoi_payment_gate"
    description: str = (
        "Payment-gated resource. "
        "Provide 'query' with your question and 'payment_proof' (base64-encoded). "
        "Returns a payment challenge JSON if proof is absent or invalid, "
        "or the resource response when payment is verified."
    )
    inputs: dict = {
        "query": {
            "type": "string",
            "description": "The question or task to process once payment is verified.",
        },
        "payment_proof": {
            "type": "string",
            "description": (
                "Base64-encoded payment proof (MPP / AP2 / x402 format). "
                "Pass an empty string to receive the payment challenge."
            ),
        },
    }
    output_type: str = "string"

    def __init__(
        self,
        adapter: Any,
        resource_fn: Any,
        tool_name: Optional[str] = None,
        tool_description: Optional[str] = None,
    ) -> None:
        # Set instance attrs BEFORE super().__init__() so smolagents sees them
        if tool_name is not None:
            self.name = tool_name
        if tool_description is not None:
            self.description = tool_description
        self._adapter = adapter
        self._resource_fn = resource_fn
        super().__init__()

    def forward(self, query: str = "", payment_proof: str = "") -> str:
        """
        Verify payment and return challenge JSON or resource response.

        Called by smolagents after routing agent input to this tool.
        """
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
            return str(self._resource_fn(query))
        except Exception as exc:
            return json.dumps({"error": "resource_error", "detail": str(exc)})
