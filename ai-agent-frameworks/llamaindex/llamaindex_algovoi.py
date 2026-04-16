"""
AlgoVoi LlamaIndex Adapter
===========================

Payment-gate any LlamaIndex LLM, query engine, chat engine, or agent tool
using x402, MPP, or AP2 — paid in USDC on Algorand, VOI, Hedera, or Stellar.

Three integration modes:

  1. Server-side gate (Flask / FastAPI)
     -----------------------------------------
     from llamaindex_algovoi import AlgoVoiLlamaIndex

     gate = AlgoVoiLlamaIndex(
         openai_key        = "sk-...",
         algovoi_key       = "algv_...",
         tenant_id         = "your-tenant-uuid",
         payout_address    = "YOUR_ALGORAND_ADDRESS",
         protocol          = "mpp",               # "mpp" | "ap2" | "x402"
         network           = "algorand-mainnet",  # see NETWORKS below
         amount_microunits = 10000,               # 0.01 USDC per call
     )

     # Flask
     @app.route("/ai/query", methods=["POST"])
     def query():
         result = gate.check(dict(request.headers), request.get_json())
         if result.requires_payment:
             return result.as_flask_response()
         return jsonify({"content": gate.complete(request.json["messages"])})

     # FastAPI
     @app.post("/ai/query")
     async def query(req: Request):
         body = await req.json()
         result = gate.check(dict(req.headers), body)
         if result.requires_payment:
             status, headers, body_bytes = result.as_wsgi_response()
             return Response(body_bytes, status_code=402, headers=dict(headers))
         return {"content": gate.complete(body["messages"])}

  2. LlamaIndex query / chat engine
     -----------------------------------------
     # Gate any LlamaIndex QueryEngine
     result = gate.check(headers, body)
     if not result.requires_payment:
         output = gate.query_engine_query(query_engine, body["query"])

     # Gate any LlamaIndex ChatEngine
     if not result.requires_payment:
         output = gate.chat_engine_chat(chat_engine, body["message"])

  3. LlamaIndex agent tool
     -----------------------------------------
     tool = gate.as_tool(resource_fn=lambda q: my_handler(q), tool_name="premium_kb")
     # Drop into any LlamaIndex ReAct agent:
     from llama_index.core.agent import ReActAgent
     agent = ReActAgent.from_tools([tool, ...], llm=llm, verbose=True)
     # Agent sends JSON: {"query": "...", "payment_proof": "<base64>"}
     # Tool returns challenge JSON if proof missing, or resource_fn(query) if verified.

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
from typing import Any

__version__ = "1.0.0"
__all__ = ["AlgoVoiLlamaIndex", "AlgoVoiPaymentTool", "LlamaIndexResult"]

# ── Path helpers ──────────────────────────────────────────────────────────────

# Three levels up from ai-agent-frameworks/llamaindex/llamaindex_algovoi.py
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

# ── Stub base classes (used when llama_index.core is not installed) ───────────

_LI_CORE_AVAILABLE = False
try:
    from llama_index.core.tools import BaseTool, ToolMetadata, ToolOutput  # type: ignore
    _LI_CORE_AVAILABLE = True
except ImportError:
    class ToolMetadata:  # type: ignore[no-redef]
        def __init__(self, name: str, description: str, **kwargs: Any) -> None:
            self.name = name
            self.description = description

    class ToolOutput:  # type: ignore[no-redef]
        def __init__(
            self,
            content: str,
            tool_name: str,
            raw_input: dict,
            raw_output: Any,
            is_error: bool = False,
        ) -> None:
            self.content = content
            self.tool_name = tool_name
            self.raw_input = raw_input
            self.raw_output = raw_output
            self.is_error = is_error

    class BaseTool:  # type: ignore[no-redef]
        @property
        def metadata(self) -> "ToolMetadata":
            raise NotImplementedError

        def __call__(self, input: Any) -> "ToolOutput":
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
        from mpp_algovoi import AlgoVoiMppGate  # type: ignore
        return AlgoVoiMppGate(
            algovoi_key=algovoi_key,
            tenant_id=tenant_id,
            payout_address=payout_address,
            networks=[network],
            amount_microunits=amount_microunits,
            resource_id=resource_id,
        )
    elif protocol == "ap2":
        _add_path("ap2-adapter")
        from ap2_algovoi import AlgoVoiAp2Gate  # type: ignore
        return AlgoVoiAp2Gate(
            algovoi_key=algovoi_key,
            tenant_id=tenant_id,
            payout_address=payout_address,
            networks=[network],
            amount_microunits=amount_microunits,
        )
    else:  # x402
        _add_path("ai-adapters/openai")
        from openai_algovoi import AlgoVoiX402Gate  # type: ignore
        return AlgoVoiX402Gate(
            algovoi_key=algovoi_key,
            tenant_id=tenant_id,
            payout_address=payout_address,
            networks=[network],
            amount_microunits=amount_microunits,
        )


# ── Result wrapper ────────────────────────────────────────────────────────────

class LlamaIndexResult:
    """Thin wrapper around the underlying gate result."""

    def __init__(self, gate_result: Any) -> None:
        self._r = gate_result

    @property
    def requires_payment(self) -> bool:
        return self._r.requires_payment

    @property
    def error(self) -> str | None:
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


# ── Message converter ─────────────────────────────────────────────────────────

def _to_li_messages(messages: list[dict]) -> list:
    """Convert OpenAI-format message dicts → LlamaIndex ChatMessage objects."""
    from llama_index.core.llms import ChatMessage, MessageRole  # type: ignore

    role_map = {
        "system":    MessageRole.SYSTEM,
        "user":      MessageRole.USER,
        "assistant": MessageRole.ASSISTANT,
    }
    result = []
    for m in messages:
        role = (m.get("role") or "user").lower()
        if role not in role_map:
            continue  # silently skip tool / function / unknown roles
        content = m.get("content", "")
        result.append(ChatMessage(role=role_map[role], content=content))
    return result


# ── Main adapter ──────────────────────────────────────────────────────────────

class AlgoVoiLlamaIndex:
    """
    Payment-gate wrapper for LlamaIndex.

    Args:
        algovoi_key (str): AlgoVoi API key (``algv_...``).
        tenant_id (str): AlgoVoi tenant UUID.
        payout_address (str): On-chain address to receive payments.
        openai_key (str | None): OpenAI API key — used to build a default
            ``llama_index.llms.openai.OpenAI`` LLM when ``llm`` is not supplied.
        llm: Pre-built LlamaIndex ``LLM`` instance (takes precedence over
            ``openai_key`` / ``model``).
        protocol (str): ``"mpp"`` | ``"ap2"`` | ``"x402"`` (default: ``"mpp"``).
        network (str): Chain network key (default: ``"algorand-mainnet"``).
        amount_microunits (int): Price per call in USDC microunits (default: ``10000``).
        model (str): LlamaIndex OpenAI model ID (default: ``"gpt-4o"``).
        base_url (str | None): Override OpenAI API base URL (``api_base`` in
            LlamaIndex terminology — for compatible providers).
        resource_id (str): Resource identifier used in MPP challenges
            (default: ``"ai-query"``).
    """

    def __init__(
        self,
        algovoi_key: str,
        tenant_id: str,
        payout_address: str,
        openai_key: str | None = None,
        llm: Any = None,
        protocol: str = "mpp",
        network: str = "algorand-mainnet",
        amount_microunits: int = 10_000,
        model: str = "gpt-4o",
        base_url: str | None = None,
        resource_id: str = "ai-query",
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

    def check(self, headers: dict, body: dict | None = None) -> LlamaIndexResult:
        """
        Verify a payment proof from request headers.

        Returns a :class:`LlamaIndexResult` whose ``requires_payment`` flag
        indicates whether a 402 challenge should be returned to the client.
        """
        try:
            raw = self._gate.check(headers, body or {})
        except TypeError:
            raw = self._gate.check(headers)
        return LlamaIndexResult(raw)

    # ── LLM helpers ───────────────────────────────────────────────────────────

    def _ensure_llm(self) -> Any:
        if self._llm is not None:
            return self._llm
        from llama_index.llms.openai import OpenAI  # type: ignore

        kwargs: dict[str, Any] = {"model": self._model, "api_key": self._openai_key}
        if self._base_url:
            kwargs["api_base"] = self._base_url
        self._llm = OpenAI(**kwargs)
        return self._llm

    def complete(self, messages: list[dict]) -> str:
        """
        Call the LlamaIndex LLM with OpenAI-format messages.

        Converts message dicts → ``ChatMessage`` objects, calls ``llm.chat()``,
        and returns the reply content as a plain string.

        Recognised roles: ``system``, ``user``, ``assistant``.
        Unknown roles (``tool``, ``function``, etc.) are silently skipped.
        """
        llm = self._ensure_llm()
        li_messages = _to_li_messages(messages)
        response = llm.chat(li_messages)
        return response.message.content

    # ── Engine helpers ────────────────────────────────────────────────────────

    def query_engine_query(self, query_engine: Any, query_str: str) -> str:
        """
        Run a LlamaIndex ``QueryEngine.query()`` call and return the text response.

        Call only after ``gate.check()`` returns ``requires_payment = False``.

        Example::

            index = VectorStoreIndex.from_documents(docs)
            engine = index.as_query_engine()

            result = gate.check(headers, body)
            if not result.requires_payment:
                answer = gate.query_engine_query(engine, body["query"])
        """
        response = query_engine.query(query_str)
        return str(response)

    def chat_engine_chat(self, chat_engine: Any, message: str) -> str:
        """
        Run a LlamaIndex ``ChatEngine.chat()`` call and return the text response.

        Call only after ``gate.check()`` returns ``requires_payment = False``.

        Example::

            engine = index.as_chat_engine(chat_mode="best")

            result = gate.check(headers, body)
            if not result.requires_payment:
                reply = gate.chat_engine_chat(engine, body["message"])
        """
        response = chat_engine.chat(message)
        return str(response)

    # ── Agent tool ────────────────────────────────────────────────────────────

    def as_tool(
        self,
        resource_fn: Any,
        tool_name: str = "algovoi_payment_gate",
        tool_description: str = (
            "Payment-gated resource. "
            'Input JSON: {"query": "<question>", "payment_proof": "<base64>"}. '
            "Returns challenge JSON if proof is absent or invalid, "
            "or the resource response when payment is verified."
        ),
    ) -> "AlgoVoiPaymentTool":
        """
        Return an :class:`AlgoVoiPaymentTool` wrapping this gate and ``resource_fn``.

        Drop the returned tool into any LlamaIndex agent via ``from_tools([tool, ...])``:

        .. code-block:: python

            tool  = gate.as_tool(resource_fn=my_handler, tool_name="premium_kb")
            agent = ReActAgent.from_tools([tool], llm=llm, verbose=True)
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

class AlgoVoiPaymentTool(BaseTool):
    """
    LlamaIndex ``BaseTool`` that wraps an AlgoVoi payment gate.

    Register with any LlamaIndex ReAct or function-calling agent::

        tool  = gate.as_tool(resource_fn=my_handler, tool_name="premium_kb")
        agent = ReActAgent.from_tools([tool], llm=llm)

    Input (as a JSON string passed by the agent):

        {"query": "Your question", "payment_proof": "<base64 MPP/AP2/x402 proof>"}

    Returns challenge JSON (``{"error": "payment_required", ...}``) when proof
    is absent or invalid, or ``str(resource_fn(query))`` when verified.
    """

    def __init__(
        self,
        adapter: AlgoVoiLlamaIndex,
        resource_fn: Any,
        tool_name: str,
        tool_description: str,
    ) -> None:
        self._adapter = adapter
        self._resource_fn = resource_fn
        self._tool_name = tool_name
        self._tool_description = tool_description

    # ── BaseTool interface ────────────────────────────────────────────────────

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name=self._tool_name,
            description=self._tool_description,
        )

    def __call__(self, input: Any) -> ToolOutput:
        result = self._run(str(input))
        return ToolOutput(
            content=result,
            tool_name=self._tool_name,
            raw_input={"input": input},
            raw_output=result,
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _parse_input(self, tool_input: str) -> tuple[str, dict]:
        """Parse JSON tool input → (query, headers_with_proof)."""
        try:
            data = json.loads(tool_input)
            if not isinstance(data, dict):
                return tool_input, {}
            query = data.get("query") or tool_input
            proof = data.get("payment_proof", "")
            headers: dict[str, str] = (
                {"Authorization": f"Payment {proof}"} if proof else {}
            )
        except (json.JSONDecodeError, AttributeError):
            query = tool_input
            headers = {}
        return query, headers

    def _run(self, tool_input: str) -> str:
        """Verify payment and return challenge or resource response."""
        query, headers = self._parse_input(tool_input)
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
