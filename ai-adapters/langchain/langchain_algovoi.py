"""
AlgoVoi LangChain Adapter

Payment-gate any LangChain LLM, chain, or agent endpoint using x402, MPP, or AP2
— paid in USDC on Algorand, VOI, Hedera, or Stellar.

Two integration modes:

  1. Server-side gate (Flask / FastAPI)
     -----------------------------------------
     from langchain_algovoi import AlgoVoiLangChain

     gate = AlgoVoiLangChain(
         openai_key        = "sk-...",
         algovoi_key       = "algv_...",
         tenant_id         = "your-tenant-uuid",
         payout_address    = "YOUR_ALGORAND_ADDRESS",
         protocol          = "mpp",               # "mpp" | "ap2" | "x402"
         network           = "algorand-mainnet",  # see NETWORKS below
         amount_microunits = 10000,               # 0.01 USDC per call
     )

     # Flask
     @app.route("/ai/chat", methods=["POST"])
     def chat():
         result = gate.check(dict(request.headers), request.get_json())
         if result.requires_payment:
             return result.as_flask_response()
         return jsonify({"content": gate.complete(request.json["messages"])})

     # FastAPI
     @app.post("/ai/chat")
     async def chat(req: Request):
         body = await req.json()
         result = gate.check(dict(req.headers), body)
         if result.requires_payment:
             status, headers, body_bytes = result.as_wsgi_response()
             return Response(body_bytes, status_code=402, headers=dict(headers))
         return {"content": gate.complete(body["messages"])}

  2. LangChain agent tool
     -----------------------------------------
     tool = gate.as_tool(resource_fn=lambda q: my_handler(q))
     # Drop into any LangChain agent:
     from langchain.agents import create_react_agent
     agent = create_react_agent(llm, tools=[tool, ...], prompt=prompt)

     # Agent sends JSON with optional proof:
     #   {"query": "What is the weather?", "payment_proof": "<base64>"}
     # Tool returns challenge JSON if proof missing/invalid,
     # or resource_fn(query) result if proof verified.

  3. Custom chain / runnable
     -----------------------------------------
     chain = prompt | llm | output_parser
     result = gate.check(headers, body)
     if not result.requires_payment:
         output = gate.invoke_chain(chain, {"question": "Hello"})

Networks:
    "algorand-mainnet"  USDC  (ASA 31566704)
    "voi-mainnet"       aUSDC (ARC200 302190)
    "hedera-mainnet"    USDC  (HTS 0.0.456858)
    "stellar-mainnet"   USDC  (Circle)

AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
Licensed under the Business Source License 1.1 — see LICENSE for details.

Version: 1.0.0
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Callable, Optional

__version__ = "1.0.0"

_API_BASE = "https://api1.ilovechicken.co.uk"

NETWORKS = [
    "algorand-mainnet",
    "voi-mainnet",
    "hedera-mainnet",
    "stellar-mainnet",
]

PROTOCOLS = ["x402", "mpp", "ap2"]

_SNAKE = {
    "algorand-mainnet": "algorand_mainnet",
    "voi-mainnet":      "voi_mainnet",
    "hedera-mainnet":   "hedera_mainnet",
    "stellar-mainnet":  "stellar_mainnet",
}

_ADAPTERS_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _add_path(subdir: str) -> None:
    p = os.path.join(_ADAPTERS_ROOT, subdir)
    if p not in sys.path:
        sys.path.insert(0, p)


# ── Optional langchain-core import (lazy — only fails at instantiation time) ──

try:
    from langchain_core.tools import BaseTool as _BaseTool      # type: ignore
    from pydantic import PrivateAttr as _PrivateAttr            # type: ignore
    _LC_CORE_AVAILABLE = True
except ImportError:
    class _BaseTool:                                             # type: ignore[no-redef]
        """Stub base used when langchain-core is not installed."""
        def __init__(self, **kw: Any) -> None:
            for k, v in kw.items():
                object.__setattr__(self, k, v)

    def _PrivateAttr(default: Any = None, **kw: Any) -> Any:   # type: ignore[no-redef]
        return default

    _LC_CORE_AVAILABLE = False


# ── Result ────────────────────────────────────────────────────────────────────

class LangChainResult:
    """
    Unified payment check result for all three protocols.

    Attributes:
        requires_payment: True if caller must pay before proceeding
        receipt:          MppReceipt on MPP success (.payer, .tx_id, .amount)
        mandate:          Ap2Mandate on AP2 success (.payer_address, .network, .tx_id)
        error:            Error string if verification failed
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.requires_payment: bool    = inner.requires_payment
        self.receipt:          Any     = getattr(inner, "receipt",  None)
        self.mandate:          Any     = getattr(inner, "mandate",  None)
        self.error:            Optional[str] = getattr(inner, "error", None)

    def as_flask_response(self) -> tuple:
        if hasattr(self._inner, "as_flask_response"):
            return self._inner.as_flask_response()
        if hasattr(self._inner, "as_wsgi_response"):
            _, wsgi_headers, body_bytes = self._inner.as_wsgi_response()
            return body_bytes.decode(), 402, dict(wsgi_headers)
        body = json.dumps({"error": "Payment Required", "detail": self.error or ""})
        return body, 402, {"Content-Type": "application/json"}

    def as_wsgi_response(self) -> tuple[str, list, bytes]:
        if hasattr(self._inner, "as_wsgi_response"):
            return self._inner.as_wsgi_response()
        body = json.dumps({"error": "Payment Required", "detail": self.error or ""}).encode()
        return "402 Payment Required", [("Content-Type", "application/json")], body


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
    if network not in NETWORKS:
        raise ValueError(f"network must be one of {NETWORKS} — got {network!r}")
    if protocol not in PROTOCOLS:
        raise ValueError(f"protocol must be one of {PROTOCOLS} — got {protocol!r}")

    if protocol == "x402":
        _add_path("ai-adapters/openai")
        from openai_algovoi import _X402Gate  # type: ignore
        return _X402Gate(
            api_base=_API_BASE, api_key=algovoi_key, tenant_id=tenant_id,
            payout_address=payout_address, network=network,
            amount_microunits=amount_microunits,
        )

    if protocol == "mpp":
        _add_path("mpp-adapter")
        from mpp import MppGate  # type: ignore
        return MppGate(
            api_base=_API_BASE, api_key=algovoi_key, tenant_id=tenant_id,
            resource_id=resource_id, payout_address=payout_address,
            networks=[_SNAKE[network]], amount_microunits=amount_microunits,
        )

    if protocol == "ap2":
        _add_path("ap2-adapter")
        from ap2 import Ap2Gate  # type: ignore
        return Ap2Gate(
            merchant_id=tenant_id, api_base=_API_BASE, api_key=algovoi_key,
            tenant_id=tenant_id, payout_address=payout_address,
            networks=[network], amount_microunits=amount_microunits,
        )


# ── LangChain message helpers ─────────────────────────────────────────────────

def _to_lc_messages(messages: list[dict]) -> list:
    """
    Convert OpenAI-format message dicts to LangChain message objects.

    Recognised roles: system, user, assistant.
    Unknown roles (tool, function, etc.) are skipped silently — consistent
    with the xAI / Mistral pattern.

    Requires: pip install langchain-core
    """
    try:
        from langchain_core.messages import (  # type: ignore
            HumanMessage, SystemMessage, AIMessage,
        )
    except ImportError:
        raise ImportError(
            "langchain-core is required: pip install langchain-core"
        )

    lc_msgs = []
    for msg in messages:
        role    = (msg.get("role") or "user").lower()
        content = msg.get("content", "")
        if role == "user":
            lc_msgs.append(HumanMessage(content=content))
        elif role == "system":
            lc_msgs.append(SystemMessage(content=content))
        elif role == "assistant":
            lc_msgs.append(AIMessage(content=content))
        # else: unknown role — skip silently

    return lc_msgs


# ── Main adapter ──────────────────────────────────────────────────────────────

class AlgoVoiLangChain:
    """
    Payment-gated wrapper for LangChain LLMs, chains, and agents.

    Supports x402, MPP, and AP2 payment protocols across
    Algorand, VOI, Hedera, and Stellar.

    Server-side gate:
        gate = AlgoVoiLangChain(openai_key="sk-...", ...)
        result = gate.check(headers, body)
        if result.requires_payment:
            return result.as_flask_response()
        content = gate.complete(messages)

    Custom chain:
        gate.invoke_chain(prompt | llm | parser, {"question": "Hello"})

    Agent tool:
        tool = gate.as_tool(resource_fn=lambda q: my_handler(q))
        agent = create_react_agent(llm, tools=[tool])
    """

    def __init__(
        self,
        algovoi_key:       str,
        tenant_id:         str,
        payout_address:    str,
        openai_key:        Optional[str] = None,
        llm:               Optional[Any] = None,
        protocol:          str = "mpp",
        network:           str = "algorand-mainnet",
        amount_microunits: int = 10000,
        model:             str = "gpt-4o",
        base_url:          Optional[str] = None,
        resource_id:       str = "ai-chat",
    ):
        """
        Args:
            algovoi_key:       AlgoVoi API key (algv_...)
            tenant_id:         AlgoVoi tenant UUID
            payout_address:    On-chain address to receive payments
            openai_key:        OpenAI API key — used by complete() to build
                               a ChatOpenAI instance. Pass llm= instead to
                               bring your own LangChain chat model.
            llm:               Pre-built LangChain ChatModel (takes precedence
                               over openai_key / model / base_url when passed)
            protocol:          Payment protocol — "mpp", "ap2", or "x402"
            network:           Chain — "algorand-mainnet", "voi-mainnet",
                               "hedera-mainnet", or "stellar-mainnet"
            amount_microunits: Price per call in USDC microunits (10000 = 0.01 USDC)
            model:             ChatOpenAI model ID (default: gpt-4o)
            base_url:          Override OpenAI API base URL (for compatible providers)
            resource_id:       Resource identifier used in MPP challenges
        """
        self._openai_key = openai_key
        self._llm        = llm
        self._model      = model
        self._base_url   = base_url
        self._gate       = _build_gate(
            protocol, algovoi_key, tenant_id, payout_address,
            network, amount_microunits, resource_id,
        )

    # ── Payment check ─────────────────────────────────────────────────────────

    def check(self, headers: dict, body: Optional[dict] = None) -> LangChainResult:
        """
        Check a request for valid payment credentials.

        Returns LangChainResult. If result.requires_payment is True, return
        result.as_flask_response() or result.as_wsgi_response() immediately.
        """
        try:
            inner = self._gate.check(headers, body)
        except TypeError:
            inner = self._gate.check(headers)
        return LangChainResult(inner)

    # ── LLM completion ────────────────────────────────────────────────────────

    def complete(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Run messages through a LangChain chat model and return the reply text.

        Uses the pre-built llm= if provided at construction, otherwise builds
        a ChatOpenAI instance using openai_key / model / base_url.

        Args:
            messages:  OpenAI-format message list
                       [{"role": "user", "content": "Hello"}]
                       Roles: system / user / assistant. Unknown roles skipped.
            model:     Override the default model (ignored when llm= was passed)
            **kwargs:  Extra kwargs forwarded to ChatOpenAI(...)
                       (e.g. temperature, max_tokens)

        Returns:
            The assistant's reply as a plain string.

        Requires: pip install langchain-core
        Requires for default ChatOpenAI: pip install langchain-openai
        """
        lc_msgs = _to_lc_messages(messages)

        if self._llm is not None:
            resp = self._llm.invoke(lc_msgs)
            return str(resp.content)

        if not self._openai_key:
            raise ValueError(
                "openai_key is required to call complete() without a pre-built llm. "
                "Pass openai_key='sk-...' to AlgoVoiLangChain(), or pass llm=<ChatModel>."
            )
        try:
            from langchain_openai import ChatOpenAI  # type: ignore
        except ImportError:
            raise ImportError(
                "langchain-openai is required: pip install langchain-openai"
            )

        chat_kwargs: dict[str, Any] = {
            "model":   model or self._model,
            "api_key": self._openai_key,
        }
        if self._base_url:
            chat_kwargs["base_url"] = self._base_url
        chat_kwargs.update(kwargs)

        chat = ChatOpenAI(**chat_kwargs)
        resp = chat.invoke(lc_msgs)
        return str(resp.content)

    # ── Arbitrary chain / runnable ────────────────────────────────────────────

    def invoke_chain(self, chain: Any, inputs: Any) -> Any:
        """
        Invoke any LangChain Runnable after payment has been verified.

        Args:
            chain:  Any object with a .invoke() method (LLMChain, LCEL pipe,
                    AgentExecutor, etc.)
            inputs: Dict or string forwarded to chain.invoke()

        Returns:
            Whatever chain.invoke(inputs) returns.
        """
        if not hasattr(chain, "invoke"):
            raise TypeError(
                f"chain must be a LangChain Runnable with .invoke() — "
                f"got {type(chain).__name__!r}"
            )
        return chain.invoke(inputs)

    # ── Agent tool ────────────────────────────────────────────────────────────

    def as_tool(
        self,
        resource_fn:      Callable[[str], str],
        tool_name:        str = "algovoi_payment_gate",
        tool_description: Optional[str] = None,
    ) -> "AlgoVoiPaymentTool":
        """
        Return an AlgoVoiPaymentTool for use inside LangChain agents.

        The tool accepts JSON with 'query' and optional 'payment_proof'.
        On missing/invalid proof it returns a challenge JSON.
        On valid proof it calls resource_fn(query) and returns the result.

        Args:
            resource_fn:      Callable(query: str) -> str — the protected resource
            tool_name:        Name shown to the agent
            tool_description: Description shown to the agent

        Returns:
            AlgoVoiPaymentTool — a LangChain BaseTool subclass

        Requires: pip install langchain-core pydantic
        """
        desc = tool_description or (
            "Access a payment-gated resource using an AlgoVoi payment proof. "
            "Input is a JSON string with 'query' (your question) and optional "
            "'payment_proof' (base64 AlgoVoi proof). "
            "Returns a payment challenge if the proof is missing or invalid. "
            "Returns the resource response when the proof is verified."
        )
        return AlgoVoiPaymentTool(
            adapter=self,
            resource_fn=resource_fn,
            tool_name=tool_name,
            tool_description=desc,
        )

    # ── Flask convenience ─────────────────────────────────────────────────────

    def flask_guard(
        self,
        messages_key: str = "messages",
        model: Optional[str] = None,
        **kwargs: Any,
    ):
        """
        Flask route handler — checks payment then calls the LangChain LLM.

        Usage:
            @app.route("/ai/chat", methods=["POST"])
            def chat():
                return gate.flask_guard()
        """
        from flask import request, jsonify, Response  # type: ignore

        body   = request.get_json(silent=True) or {}
        result = self.check(dict(request.headers), body)
        if result.requires_payment:
            flask_body, status, headers = result.as_flask_response()
            return Response(
                flask_body, status=status, headers=headers,
                mimetype="application/json",
            )
        messages = body.get(messages_key, [])
        content  = self.complete(messages, model=model, **kwargs)
        return jsonify({"content": content})


# ── Agent payment tool ────────────────────────────────────────────────────────

class AlgoVoiPaymentTool(_BaseTool):
    """
    LangChain BaseTool that payment-gates access to a resource.

    LangChain agents call this tool with a JSON string:
        {"query": "your question", "payment_proof": "<base64 AlgoVoi proof>"}

    Without a valid proof the tool returns challenge JSON so the orchestrator
    can prompt the user/payer. With a valid proof it calls resource_fn(query)
    and returns the result as a string.

    Obtain via AlgoVoiLangChain.as_tool() — do not instantiate directly.
    Requires: pip install langchain-core pydantic
    """

    name:        str = "algovoi_payment_gate"
    description: str = (
        "Access a payment-gated resource. Input must be a JSON string with "
        "'query' (your question) and 'payment_proof' (base64 AlgoVoi proof). "
        "Returns payment challenge JSON if proof is missing or invalid."
    )

    # Private attributes — set via object.__setattr__ to work with both
    # Pydantic v1 and v2 (PrivateAttr descriptor vs. plain __dict__).
    _adapter:     Any = _PrivateAttr()
    _resource_fn: Any = _PrivateAttr()

    def __init__(
        self,
        *,
        adapter:          Any,
        resource_fn:      Callable[[str], str],
        tool_name:        str,
        tool_description: str,
        **data: Any,
    ) -> None:
        if not _LC_CORE_AVAILABLE:
            raise ImportError(
                "langchain-core and pydantic are required to use AlgoVoiPaymentTool: "
                "pip install langchain-core pydantic"
            )
        super().__init__(name=tool_name, description=tool_description, **data)
        object.__setattr__(self, "_adapter",     adapter)
        object.__setattr__(self, "_resource_fn", resource_fn)

    # ── Input parsing ─────────────────────────────────────────────────────────

    def _parse_input(self, tool_input: str) -> tuple[str, dict]:
        """
        Parse tool_input string — returns (query, headers_dict).

        Accepts:
          - JSON: {"query": "...", "payment_proof": "<base64>"}
          - JSON: {"query": "..."} — proof omitted
          - Plain string — treated as query, no proof
        """
        try:
            data  = json.loads(tool_input)
        except (json.JSONDecodeError, TypeError):
            return str(tool_input), {}

        query = str(data.get("query", ""))
        proof = str(data.get("payment_proof", "")).strip()
        headers = {"Authorization": f"Payment {proof}"} if proof else {}
        return query, headers

    # ── Tool execution ────────────────────────────────────────────────────────

    def _run(self, tool_input: str, **kwargs: Any) -> str:
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

    async def _arun(self, tool_input: str, **kwargs: Any) -> str:
        """Async variant — delegates to synchronous _run."""
        return self._run(tool_input, **kwargs)
