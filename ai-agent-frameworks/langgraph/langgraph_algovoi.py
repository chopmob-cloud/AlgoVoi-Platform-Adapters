"""
AlgoVoi LangGraph Adapter
==========================

Payment-gate any LangGraph StateGraph or compiled graph using x402, MPP, or AP2 —
paid in USDC on Algorand, VOI, Hedera, or Stellar.

LangGraph is a graph-based stateful agent framework built on top of LangChain.
Agents are defined as directed graphs where nodes are Python functions or
Runnables, state flows between nodes, and the graph is compiled before
invocation. This adapter gates compiled LangGraph graphs behind on-chain payment
verification.

Two integration surfaces:

  1. Server-side gate (Flask / FastAPI)
     gate = AlgoVoiLangGraph(algovoi_key="algv_...", ...)

     @app.route("/agent", methods=["POST"])
     def agent():
         result = gate.check(dict(request.headers), request.get_json())
         if result.requires_payment:
             return result.as_flask_response()
         output = gate.invoke_graph(compiled_graph, {"messages": [...]})
         return jsonify(output)

  2. LangGraph agent tool (via ToolNode)
     tool = gate.as_tool(resource_fn=lambda q: my_handler(q))
     # Use directly in create_react_agent:
     from langgraph.prebuilt import create_react_agent
     agent = create_react_agent(llm, tools=[tool])
     # Or wrap in a ToolNode:
     node = gate.tool_node(resource_fn=lambda q: my_handler(q))

Networks:
    "algorand-mainnet"  USDC  (ASA 31566704)
    "voi-mainnet"       aUSDC (ARC200 302190)
    "hedera-mainnet"    USDC  (HTS 0.0.456858)
    "stellar-mainnet"   USDC  (Circle)

AlgoVoi repo: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
Licensed under the Business Source License 1.1 — see LICENSE for details.

Version: 1.0.0
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Callable, Iterator, Optional, Type

__version__ = "1.0.0"

_API_BASE = "https://api1.ilovechicken.co.uk"
_MAX_FLASK_BODY = 1_048_576  # 1 MiB

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

_ADAPTERS_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)


def _add_path(subdir: str) -> None:
    p = os.path.join(_ADAPTERS_ROOT, subdir)
    if p not in sys.path:
        sys.path.insert(0, p)


# ── Optional langchain-core import (lazy) ─────────────────────────────────────

try:
    from langchain_core.tools import BaseTool as _BaseTool  # type: ignore
    from pydantic import BaseModel as _BaseModel            # type: ignore
    from pydantic import Field as _Field                    # type: ignore
    from pydantic import PrivateAttr as _PrivateAttr        # type: ignore
    _LC_CORE_AVAILABLE = True
except ImportError:
    class _BaseTool:  # type: ignore[no-redef]
        """Stub used when langchain-core is not installed."""
        def __init__(self, **kw: Any) -> None:
            for k, v in kw.items():
                object.__setattr__(self, k, v)

    class _BaseModel:  # type: ignore[no-redef]
        pass

    def _Field(default: Any = None, **kw: Any) -> Any:  # type: ignore[no-redef]
        return default

    def _PrivateAttr(default: Any = None, **kw: Any) -> Any:  # type: ignore[no-redef]
        return default

    _LC_CORE_AVAILABLE = False


# ── Result ─────────────────────────────────────────────────────────────────────

class LangGraphResult:
    """
    Unified payment check result for all three protocols.

    Attributes:
        requires_payment: True if the caller must pay before proceeding.
        receipt:          MppReceipt on MPP success.
        mandate:          Ap2Mandate on AP2 success.
        error:            Error string if verification failed.
    """

    def __init__(self, inner: Any) -> None:
        self._inner          = inner
        self.requires_payment: bool         = inner.requires_payment
        self.receipt:          Any          = getattr(inner, "receipt",  None)
        self.mandate:          Any          = getattr(inner, "mandate",  None)
        self.error:            Optional[str] = getattr(inner, "error",   None)

    def as_flask_response(self):
        if hasattr(self._inner, "as_wsgi_response"):
            _, wsgi_headers, body_bytes = self._inner.as_wsgi_response()
            return body_bytes.decode(), 402, dict(wsgi_headers)
        body = json.dumps({"error": "Payment Required", "detail": self.error or ""})
        return body, 402, {"Content-Type": "application/json"}

    def as_wsgi_response(self):
        if hasattr(self._inner, "as_wsgi_response"):
            return self._inner.as_wsgi_response()
        body = json.dumps({"error": "Payment Required", "detail": self.error or ""}).encode()
        return "402 Payment Required", [("Content-Type", "application/json")], body


# ── Gate factory ───────────────────────────────────────────────────────────────

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
        raise ValueError(f"network must be one of {NETWORKS!r} — got {network!r}")
    if protocol not in PROTOCOLS:
        raise ValueError(f"protocol must be one of {PROTOCOLS!r} — got {protocol!r}")

    if protocol == "x402":
        _add_path("ai-adapters/openai")
        from openai_algovoi import _X402Gate  # type: ignore
        return _X402Gate(
            api_base=_API_BASE,
            api_key=algovoi_key,
            tenant_id=tenant_id,
            payout_address=payout_address,
            network=network,
            amount_microunits=amount_microunits,
        )

    if protocol == "mpp":
        _add_path("mpp-adapter")
        from mpp import MppGate  # type: ignore
        return MppGate(
            api_base=_API_BASE,
            api_key=algovoi_key,
            tenant_id=tenant_id,
            resource_id=resource_id,
            payout_address=payout_address,
            networks=[_SNAKE[network]],
            amount_microunits=amount_microunits,
        )

    if protocol == "ap2":
        _add_path("ap2-adapter")
        from ap2 import Ap2Gate  # type: ignore
        return Ap2Gate(
            merchant_id=tenant_id,
            api_base=_API_BASE,
            api_key=algovoi_key,
            tenant_id=tenant_id,
            payout_address=payout_address,
            networks=[network],
            amount_microunits=amount_microunits,
        )


# ── Payment tool ───────────────────────────────────────────────────────────────

class _PaymentInput(_BaseModel):
    """Input schema for AlgoVoiPaymentTool."""
    query:         str = _Field(description="The question or task to gate.")
    payment_proof: str = _Field(
        default="",
        description="Base64-encoded payment proof. Pass empty string to receive a challenge.",
    )


class AlgoVoiPaymentTool(_BaseTool):
    """
    LangGraph-compatible payment-gate tool.

    Subclasses LangChain's ``BaseTool`` so it works with:
      - ``create_react_agent(llm, tools=[tool])``
      - ``ToolNode([tool])`` in a custom StateGraph
      - Any LangGraph agent that uses LangChain tools

    Returns:
      - Challenge JSON ``{"error": "payment_required", ...}`` if proof absent/invalid.
      - ``resource_fn(query)`` result as str if payment proof is verified.
    """

    name: str        = "algovoi_payment_gate"
    description: str = (
        "Payment-gated resource access. "
        "Provide query (the question or task) and payment_proof "
        "(base64-encoded payment proof — empty string to receive a payment challenge)."
    )
    args_schema: Type[_BaseModel] = _PaymentInput  # type: ignore[assignment]

    _adapter:     Any = _PrivateAttr()
    _resource_fn: Any = _PrivateAttr()

    def __init__(
        self,
        adapter: "AlgoVoiLangGraph",
        resource_fn: Callable,
        tool_name: str = "algovoi_payment_gate",
        tool_description: str = (
            "Payment-gated resource access. "
            "Provide query (the question or task) and payment_proof "
            "(base64-encoded payment proof — empty string to receive a payment challenge)."
        ),
    ) -> None:
        super().__init__(name=tool_name, description=tool_description)
        self._adapter     = adapter
        self._resource_fn = resource_fn

    def _run(self, query: str = "", payment_proof: str = "") -> str:
        headers: dict[str, str] = {}
        if payment_proof:
            headers["Authorization"] = f"Payment {payment_proof}"
        try:
            result = self._adapter.check(headers, {})
        except TypeError:
            result = self._adapter.check(headers)
        if result.requires_payment:
            return json.dumps(
                {
                    "error":  "payment_required",
                    "detail": result.error or "Payment proof required",
                }
            )
        try:
            return str(self._resource_fn(query))
        except Exception as exc:
            return json.dumps({"error": "resource_error", "detail": str(exc)})

    async def _arun(self, query: str = "", payment_proof: str = "") -> str:  # type: ignore[override]
        return self._run(query=query, payment_proof=payment_proof)


# ── Main adapter ───────────────────────────────────────────────────────────────

class AlgoVoiLangGraph:
    """
    Payment gate for LangGraph compiled StateGraphs.

    Gates any compiled LangGraph graph (``graph.invoke`` / ``graph.stream``)
    behind on-chain payment verification using x402, MPP, or AP2.

    Surfaces:
      check(headers[, body])              Verify payment proof
      invoke_graph(graph, inputs[, cfg])  Run compiled graph after gate passes
      stream_graph(graph, inputs[, cfg])  Stream compiled graph after gate passes
      as_tool(resource_fn, ...)           LangChain BaseTool for ToolNode / ReAct
      tool_node(resource_fn, ...)         Ready-to-use LangGraph ToolNode
      flask_guard()                       Flask payment-check-only handler
      flask_agent(graph[, input_key])     Full Flask endpoint — check + invoke
    """

    def __init__(
        self,
        algovoi_key:       str,
        tenant_id:         str,
        payout_address:    str,
        protocol:          str = "mpp",
        network:           str = "algorand-mainnet",
        amount_microunits: int = 10_000,
        resource_id:       str = "ai-function",
    ) -> None:
        self._algovoi_key       = algovoi_key
        self._tenant_id         = tenant_id
        self._payout_address    = payout_address
        self._protocol          = protocol
        self._network           = network
        self._amount_microunits = amount_microunits
        self._resource_id       = resource_id
        self._gate              = _build_gate(
            protocol=protocol,
            algovoi_key=algovoi_key,
            tenant_id=tenant_id,
            payout_address=payout_address,
            network=network,
            amount_microunits=amount_microunits,
            resource_id=resource_id,
        )

    # ── Payment check ─────────────────────────────────────────────────────────

    def check(self, headers: dict, body: Optional[dict] = None) -> LangGraphResult:
        """
        Verify payment proof from request headers.

        Args:
            headers: Request headers dict.
            body:    Optional parsed request body dict.

        Returns:
            LangGraphResult — ``requires_payment=True`` triggers a 402 response;
            ``requires_payment=False`` means the proof is verified.
        """
        try:
            inner = self._gate.check(headers, body or {})
        except TypeError:
            inner = self._gate.check(headers)
        return LangGraphResult(inner)

    # ── Graph invocation ──────────────────────────────────────────────────────

    def invoke_graph(
        self,
        graph: Any,
        inputs: dict,
        config: Optional[dict] = None,
    ) -> dict:
        """
        Run a compiled LangGraph and return the final state dict.

        The compiled graph is any object returned by
        ``StateGraph(...).compile(checkpointer=...)`` — this adapter calls
        ``graph.invoke(inputs, config)`` directly, preserving checkpointing,
        recursion limits, and any other ``RunnableConfig`` options.

        Args:
            graph:   A compiled LangGraph (``CompiledStateGraph``).
            inputs:  Input dict — typically ``{"messages": [...]}`` for agents.
            config:  Optional ``RunnableConfig`` dict (e.g. ``{"configurable":
                     {"thread_id": "session-1"}}`` for checkpointed graphs).

        Returns:
            Final state dict from the graph execution.
        """
        return graph.invoke(inputs, config=config)

    def stream_graph(
        self,
        graph: Any,
        inputs: dict,
        config: Optional[dict] = None,
        stream_mode: str = "values",
    ) -> Iterator[Any]:
        """
        Stream a compiled LangGraph and yield state snapshots.

        Args:
            graph:       A compiled LangGraph.
            inputs:      Input dict.
            config:      Optional ``RunnableConfig`` dict.
            stream_mode: LangGraph stream mode — ``"values"`` (full state each
                         step), ``"updates"`` (delta per node), or
                         ``"messages"`` (token-level LLM output).

        Yields:
            State snapshots or update dicts depending on ``stream_mode``.
        """
        yield from graph.stream(inputs, config=config, stream_mode=stream_mode)

    # ── Tool factory ──────────────────────────────────────────────────────────

    def as_tool(
        self,
        resource_fn: Callable,
        tool_name: str = "algovoi_payment_gate",
        tool_description: str = (
            "Payment-gated resource access. "
            "Provide query (the question or task) and payment_proof "
            "(base64-encoded payment proof — empty string to receive a payment challenge)."
        ),
    ) -> AlgoVoiPaymentTool:
        """
        Return an AlgoVoiPaymentTool wrapping ``resource_fn``.

        The tool is a LangChain ``BaseTool`` subclass and is compatible with:

          - ``create_react_agent(llm, tools=[tool])``
          - ``ToolNode([tool])`` in a custom StateGraph
          - Any LangChain/LangGraph agent tool interface

        Args:
            resource_fn:      ``Callable[[str], str]`` — receives query, returns answer.
            tool_name:        Tool name shown to the LLM.
            tool_description: Tool description shown to the LLM.

        Returns:
            AlgoVoiPaymentTool (``BaseTool`` subclass).
        """
        return AlgoVoiPaymentTool(self, resource_fn, tool_name, tool_description)

    def tool_node(
        self,
        resource_fn: Callable,
        tool_name: str = "algovoi_payment_gate",
        tool_description: str = (
            "Payment-gated resource access. "
            "Provide query (the question or task) and payment_proof "
            "(base64-encoded payment proof — empty string to receive a payment challenge)."
        ),
    ) -> Any:
        """
        Return a ready-to-use LangGraph ``ToolNode`` containing the payment tool.

        Requires ``langgraph`` to be installed (``pip install langgraph``).

        Usage::

            node = gate.tool_node(resource_fn=lambda q: fetch_kb(q))
            graph = StateGraph(State)
            graph.add_node("tools", node)

        Args:
            resource_fn:      ``Callable[[str], str]``
            tool_name:        Tool name shown to the LLM.
            tool_description: Tool description shown to the LLM.

        Returns:
            ``langgraph.prebuilt.ToolNode`` wrapping the payment tool.

        Raises:
            ImportError: If ``langgraph`` is not installed.
        """
        try:
            from langgraph.prebuilt import ToolNode  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "langgraph is required for tool_node(): pip install langgraph"
            ) from exc
        tool = self.as_tool(resource_fn, tool_name, tool_description)
        return ToolNode([tool])

    # ── Flask helpers ─────────────────────────────────────────────────────────

    def flask_guard(self) -> Any:
        """
        Payment-check-only Flask handler.

        Returns a Flask tuple ``(body, 402, headers)`` if payment is required,
        otherwise returns ``None`` so the caller can run the graph.

        Usage::

            @app.route("/agent", methods=["POST"])
            def agent():
                guard = gate.flask_guard()
                if guard is not None:
                    return guard          # 402

                body   = request.get_json()
                output = gate.invoke_graph(compiled_graph, body["inputs"])
                return jsonify(output)
        """
        import flask

        raw = flask.request.get_data()
        if len(raw) > _MAX_FLASK_BODY:
            raw = raw[:_MAX_FLASK_BODY]
        try:
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            body = {}

        result = self.check(dict(flask.request.headers), body)
        if result.requires_payment:
            return result.as_flask_response()
        return None

    def flask_agent(
        self,
        graph: Any,
        input_key: str = "messages",
        config: Optional[dict] = None,
    ) -> Any:
        """
        Full Flask endpoint handler — payment check + graph invocation.

        Reads the request body, checks payment, extracts ``body[input_key]``
        (default ``"messages"``), runs the compiled graph, and returns the
        final state as JSON.

        Usage::

            @app.route("/agent", methods=["POST"])
            def agent():
                return gate.flask_agent(compiled_graph)

        Args:
            graph:     Compiled LangGraph to run on verified requests.
            input_key: Key in the JSON body that holds the graph input value
                       (default ``"messages"``). The extracted value is passed
                       as ``graph.invoke({input_key: value})``.
            config:    Optional ``RunnableConfig`` forwarded to ``graph.invoke``.

        Returns:
            Flask JSON response with the final graph state, or 402 response.
        """
        import flask
        from flask import jsonify

        raw = flask.request.get_data()
        if len(raw) > _MAX_FLASK_BODY:
            raw = raw[:_MAX_FLASK_BODY]
        try:
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            body = {}

        result = self.check(dict(flask.request.headers), body)
        if result.requires_payment:
            return result.as_flask_response()

        inputs = {input_key: body.get(input_key, [])}
        output = self.invoke_graph(graph, inputs, config=config)
        return jsonify(output)
