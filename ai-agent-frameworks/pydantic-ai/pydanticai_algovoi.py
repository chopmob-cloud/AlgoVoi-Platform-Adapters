"""
AlgoVoi Pydantic AI Adapter
============================

Payment-gate any Pydantic AI agent or model using x402, MPP, or AP2 —
paid in USDC on Algorand, VOI, Hedera, or Stellar.

Wraps Pydantic AI's Agent, model invocation, and tool system behind on-chain
payment verification. Compatible with all Pydantic AI model providers
(OpenAI, Anthropic, Google, Groq, Ollama, and more via the provider:model
string format or explicit Model objects).

x402 gate reused from ai-adapters/openai/openai_algovoi.py.
MPP and AP2 gates require the sibling mpp-adapter/ and ap2-adapter/ directories.

Version: 1.0.0
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any, Callable, Optional

__version__ = "1.0.0"

_MAX_FLASK_BODY = 1_048_576  # 1 MiB


def _add_path(target: str) -> None:
    """Prepend *target* to sys.path (no-op if already present)."""
    if target not in sys.path:
        sys.path.insert(0, target)


def _adapters_root() -> str:
    """Return the repository root (three directories above this file)."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(here))


# ── Result wrapper ────────────────────────────────────────────────────────────

class PydanticAIResult:
    """
    Thin wrapper around the underlying gate result.

    Mirrors the surface of the other AlgoVoi AI adapter result objects:
      result.requires_payment  — True → client must pay; False → request allowed
      result.error             — human-readable reason for rejection
      result.as_wsgi_response() → (status_code, headers, body_bytes)
      result.as_flask_response() → Flask Response object (402)
    """

    def __init__(
        self,
        requires_payment: bool,
        error: str = "",
        gate: Any = None,
    ) -> None:
        self.requires_payment = requires_payment
        self.error = error
        self._gate_result = gate

    def as_wsgi_response(self):
        if self._gate_result and hasattr(self._gate_result, "as_wsgi_response"):
            return self._gate_result.as_wsgi_response()
        body = json.dumps({"error": self.error or "Payment required"}).encode()
        return (402, [], body)

    def as_flask_response(self):
        from flask import Response

        status, headers, body = self.as_wsgi_response()
        resp = Response(body, status=status, mimetype="application/json")
        for k, v in headers:
            resp.headers[k] = v
        return resp


# ── Payment tool ──────────────────────────────────────────────────────────────

class AlgoVoiPaymentTool:
    """
    Payment-gate tool compatible with Pydantic AI agents.

    Usage — register with any Pydantic AI Agent:

        tool = gate.as_tool(resource_fn=my_handler, tool_name="premium_kb")

        # Option A — wrap with pydantic_ai.tools.Tool
        from pydantic_ai.tools import Tool
        agent = Agent(
            "openai:gpt-4o",
            tools=[Tool(tool, name=tool.name, description=tool.description)],
        )

        # Option B — direct callable (no agent needed)
        result = tool(query="...", payment_proof="<base64>")

    The tool returns:
      - Challenge JSON {"error": "payment_required", ...} if proof absent/invalid
      - resource_fn(query) result as str if payment verified
    """

    def __init__(
        self,
        adapter: "AlgoVoiPydanticAI",
        resource_fn: Callable,
        tool_name: str = "algovoi_payment_gate",
        tool_description: str = (
            "Payment-gated resource access. "
            "Provide query (the question or task) and payment_proof "
            "(base64-encoded payment proof — empty string to receive a payment challenge)."
        ),
    ) -> None:
        self.name = tool_name
        self.description = tool_description
        self._adapter = adapter
        self._resource_fn = resource_fn

    def __call__(self, query: str = "", payment_proof: str = "") -> str:
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
                    "error": "payment_required",
                    "detail": result.error or "Payment proof required",
                }
            )
        try:
            return str(self._resource_fn(query))
        except Exception as exc:
            return json.dumps({"error": "resource_error", "detail": str(exc)})


# ── Main adapter ──────────────────────────────────────────────────────────────

class AlgoVoiPydanticAI:
    """
    Payment gate for Pydantic AI agents.

    Gates any Pydantic AI Agent or direct model call behind on-chain payment
    verification using x402, MPP, or AP2.

    Surfaces:
      check(headers[, body])             Verify payment proof
      complete(messages)                 Run OpenAI-format messages through an Agent
      run_agent(agent, prompt[, deps])   Gate any pre-built Pydantic AI Agent
      as_tool(resource_fn, ...)          Return AlgoVoiPaymentTool for agent integration
      flask_guard()                      Convenience Flask handler
    """

    def __init__(
        self,
        algovoi_key: str,
        tenant_id: str,
        payout_address: str,
        openai_key: Optional[str] = None,
        protocol: str = "mpp",
        network: str = "algorand-mainnet",
        amount_microunits: int = 10000,
        model: str = "openai:gpt-4o",
        base_url: Optional[str] = None,
        resource_id: str = "ai-function",
    ) -> None:
        self._algovoi_key = algovoi_key
        self._tenant_id = tenant_id
        self._payout_address = payout_address
        self._openai_key = openai_key
        self._protocol = protocol
        self._network = network
        self._amount_microunits = amount_microunits
        self._model = model
        self._base_url = base_url
        self._resource_id = resource_id
        self._gate = self._build_gate()

    # ── Gate builder ──────────────────────────────────────────────────────

    def _build_gate(self) -> Any:
        root = _adapters_root()
        proto = self._protocol.lower()

        if proto == "mpp":
            _add_path(os.path.join(root, "mpp-adapter"))
            from mpp_algovoi import AlgoVoiMppGate

            return AlgoVoiMppGate(
                algovoi_key=self._algovoi_key,
                tenant_id=self._tenant_id,
                payout_address=self._payout_address,
                networks=[self._network],
                amount_microunits=self._amount_microunits,
                resource_id=self._resource_id,
            )

        if proto == "ap2":
            _add_path(os.path.join(root, "ap2-adapter"))
            from ap2_algovoi import AlgoVoiAp2Gate

            return AlgoVoiAp2Gate(
                algovoi_key=self._algovoi_key,
                tenant_id=self._tenant_id,
                payout_address=self._payout_address,
                networks=[self._network],
                amount_microunits=self._amount_microunits,
            )

        # x402 (default / fallback)
        _add_path(os.path.join(root, "ai-adapters", "openai"))
        from openai_algovoi import AlgoVoiX402Gate

        return AlgoVoiX402Gate(
            algovoi_key=self._algovoi_key,
            tenant_id=self._tenant_id,
            payout_address=self._payout_address,
            networks=[self._network],
            amount_microunits=self._amount_microunits,
        )

    # ── Payment check ─────────────────────────────────────────────────────

    def check(self, headers: dict, body: Optional[dict] = None) -> PydanticAIResult:
        """
        Verify payment proof from request headers.

        Args:
            headers: Request headers dict (lowercase or mixed-case keys are accepted
                     by the underlying gate).
            body:    Optional parsed request body dict.

        Returns:
            PydanticAIResult with requires_payment=True if a 402 challenge is
            needed, or requires_payment=False if the payment proof is verified.
        """
        try:
            gate_result = self._gate.check(headers, body or {})
        except TypeError:
            gate_result = self._gate.check(headers)
        return PydanticAIResult(
            requires_payment=gate_result.requires_payment,
            error=getattr(gate_result, "error", "") or "",
            gate=gate_result,
        )

    # ── Model invocation ──────────────────────────────────────────────────

    def complete(self, messages: list[dict]) -> str:
        """
        Run an OpenAI-format message list through a Pydantic AI Agent.

        Converts the messages list to a prompt string and runs it through an
        Agent configured for self._model. Sync wrapper — safe to call from
        synchronous Flask / WSGI handlers.

        For async contexts (FastAPI, etc.), use _complete_async() with await.

        Args:
            messages: List of {"role": ..., "content": ...} dicts.
                      Roles: "system", "user", "assistant".

        Returns:
            str(result.data) from the agent run.
        """
        return asyncio.run(self._complete_async(messages))

    async def _complete_async(self, messages: list[dict]) -> str:
        """Async implementation of complete()."""
        system_parts: list[str] = []
        prompt_parts: list[str] = []

        for m in messages:
            role = (m.get("role") or "user").lower()
            content = m.get("content", "")
            if role == "system":
                system_parts.append(content)
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
            else:
                prompt_parts.append(f"User: {content}")

        system_prompt: Optional[str] = "\n".join(system_parts) if system_parts else None
        prompt = "\n".join(prompt_parts) if prompt_parts else ""

        agent = self._ensure_agent(system_prompt=system_prompt)
        result = await agent.run(prompt)
        return str(result.data)

    def _ensure_agent(self, system_prompt: Optional[str] = None) -> Any:
        """
        Build a Pydantic AI Agent for the configured model.

        If openai_key or base_url were supplied to the constructor, an explicit
        AsyncOpenAI client is created and passed to OpenAIModel so that
        environment variables are not required. Otherwise the model string
        (e.g. "openai:gpt-4o") is passed directly and Pydantic AI resolves it
        using environment variables (OPENAI_API_KEY, etc.).
        """
        from pydantic_ai import Agent

        model: Any = self._model

        if self._openai_key or self._base_url:
            try:
                from pydantic_ai.models.openai import OpenAIModel
                from openai import AsyncOpenAI

                client_kwargs: dict[str, Any] = {}
                if self._openai_key:
                    client_kwargs["api_key"] = self._openai_key
                if self._base_url:
                    client_kwargs["base_url"] = self._base_url
                openai_client = AsyncOpenAI(**client_kwargs)
                # Strip provider prefix if present: "openai:gpt-4o" → "gpt-4o"
                model_name = (
                    self._model[len("openai:") :]
                    if self._model.startswith("openai:")
                    else self._model
                )
                model = OpenAIModel(model_name, openai_client=openai_client)
            except ImportError:
                pass  # pydantic_ai or openai not installed — use string model

        agent_kwargs: dict[str, Any] = {"model": model}
        if system_prompt:
            agent_kwargs["system_prompt"] = system_prompt
        return Agent(**agent_kwargs)

    # ── Agent gating ──────────────────────────────────────────────────────

    def run_agent(
        self,
        agent: Any,
        prompt: str,
        deps: Any = None,
        **kwargs: Any,
    ) -> str:
        """
        Gate any pre-built Pydantic AI Agent — sync wrapper around agent.run().

        The agent is called with agent.run(prompt, [deps=deps,] **kwargs).
        Use _run_async() directly if already inside an async context.

        Args:
            agent:  Pydantic AI Agent instance.
            prompt: User prompt string.
            deps:   Optional dependency injection value (Agent deps_type).
            **kwargs: Forwarded to agent.run() — e.g. message_history=[...].

        Returns:
            str(result.data) from the agent run.
        """
        return asyncio.run(self._run_async(agent, prompt, deps=deps, **kwargs))

    async def _run_async(
        self,
        agent: Any,
        prompt: str,
        deps: Any = None,
        **kwargs: Any,
    ) -> str:
        """Async implementation of run_agent()."""
        run_kwargs = {**kwargs}
        if deps is not None:
            run_kwargs["deps"] = deps
        result = await agent.run(prompt, **run_kwargs)
        return str(result.data)

    # ── Tool factory ──────────────────────────────────────────────────────

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
        Return an AlgoVoiPaymentTool wrapping resource_fn.

        The returned object is a plain callable compatible with Pydantic AI:

            from pydantic_ai.tools import Tool
            tool = gate.as_tool(resource_fn=my_handler)
            agent = Agent(
                "openai:gpt-4o",
                tools=[Tool(tool, name=tool.name, description=tool.description)],
            )

        Args:
            resource_fn:      Callable receiving (query: str) → str
            tool_name:        Tool name exposed to the LLM
            tool_description: Tool description shown in the agent prompt

        Returns:
            AlgoVoiPaymentTool instance (callable + .name + .description)
        """
        return AlgoVoiPaymentTool(self, resource_fn, tool_name, tool_description)

    # ── Flask convenience ─────────────────────────────────────────────────

    def flask_guard(self) -> Any:
        """
        Convenience Flask handler — check + complete in one call.

        Usage:
            @app.route("/ai/chat", methods=["POST"])
            def chat():
                return gate.flask_guard()
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

        messages = body.get("messages", [])
        content = self.complete(messages)
        return jsonify({"content": content})
