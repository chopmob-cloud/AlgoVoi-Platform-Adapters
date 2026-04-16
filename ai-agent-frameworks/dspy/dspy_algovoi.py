"""
AlgoVoi DSPy Adapter
=====================

Payment-gate any DSPy module, program, or chain using x402, MPP, or AP2 —
paid in USDC on Algorand, VOI, Hedera, or Stellar.

Wraps DSPy's modules (Predict, ChainOfThought, ReAct, and any compiled
program) behind on-chain payment verification. LLM-agnostic — works with any
provider DSPy supports (OpenAI, Anthropic, Google, Cohere, Groq, Ollama, etc.).

DSPy uses a `provider/model` string (e.g. "openai/gpt-4o") and the global
`dspy.configure(lm=...)` / `dspy.context(lm=...)` pattern. This adapter uses
`dspy.context` to avoid permanently modifying global state.

x402 gate reused from ai-adapters/openai/openai_algovoi.py.
MPP and AP2 gates require the sibling mpp-adapter/ and ap2-adapter/ directories.

Version: 1.0.0
"""

from __future__ import annotations

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

class DSPyResult:
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
    Payment-gate tool compatible with DSPy ReAct agents.

    DSPy's ReAct module accepts plain Python callables as tools:

        tool  = gate.as_tool(resource_fn=my_handler, tool_name="premium_kb")
        react = dspy.ReAct(QA, tools=[tool])

    The tool docstring is used as the tool description by DSPy's tool-calling
    mechanism. The callable accepts `query` and `payment_proof` as positional
    or keyword arguments.

    Returns:
      - Challenge JSON {"error": "payment_required", ...} if proof absent/invalid
      - resource_fn(query) result as str if payment verified
    """

    def __init__(
        self,
        adapter: "AlgoVoiDSPy",
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
        # Set __name__ and __doc__ so DSPy sees the right tool metadata
        self.__name__ = tool_name
        self.__doc__ = tool_description

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

class AlgoVoiDSPy:
    """
    Payment gate for DSPy modules and programs.

    Gates any DSPy module (Predict, ChainOfThought, ReAct, compiled program)
    behind on-chain payment verification using x402, MPP, or AP2. Uses
    dspy.context(lm=...) to avoid modifying global state.

    Surfaces:
      check(headers[, body])          Verify payment proof
      complete(messages)              Run OpenAI-format messages through a Predict module
      run_module(module, **kwargs)    Gate any pre-built DSPy module / program
      as_tool(resource_fn, ...)       Return AlgoVoiPaymentTool for ReAct integration
      flask_guard()                   Convenience Flask handler
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
        model: str = "openai/gpt-4o",
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

    # ── LM factory ────────────────────────────────────────────────────────

    def _ensure_lm(self) -> Any:
        """
        Build a dspy.LM for the configured model.

        Passes api_key and api_base (base_url) if supplied; otherwise DSPy
        picks up credentials from environment variables (OPENAI_API_KEY, etc.).

        DSPy uses provider/model format (e.g. "openai/gpt-4o").
        """
        import dspy

        lm_kwargs: dict[str, Any] = {}
        if self._openai_key:
            lm_kwargs["api_key"] = self._openai_key
        if self._base_url:
            lm_kwargs["api_base"] = self._base_url
        return dspy.LM(self._model, **lm_kwargs)

    # ── Payment check ─────────────────────────────────────────────────────

    def check(self, headers: dict, body: Optional[dict] = None) -> DSPyResult:
        """
        Verify payment proof from request headers.

        Args:
            headers: Request headers dict.
            body:    Optional parsed request body dict.

        Returns:
            DSPyResult with requires_payment=True if a 402 challenge is needed,
            or requires_payment=False if the payment proof is verified.
        """
        try:
            gate_result = self._gate.check(headers, body or {})
        except TypeError:
            gate_result = self._gate.check(headers)
        return DSPyResult(
            requires_payment=gate_result.requires_payment,
            error=getattr(gate_result, "error", "") or "",
            gate=gate_result,
        )

    # ── Model invocation ──────────────────────────────────────────────────

    def complete(self, messages: list[dict]) -> str:
        """
        Run an OpenAI-format message list through a DSPy Predict module.

        Converts the messages list to a prompt string and runs it through a
        temporary dspy.Predict module scoped to self._model via dspy.context.

        Args:
            messages: List of {"role": ..., "content": ...} dicts.
                      Roles: "system", "user", "assistant".

        Returns:
            String response from the Predict module's `response` output field.
        """
        import dspy

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

        system_text = (
            "\n".join(system_parts)
            if system_parts
            else "You are a helpful assistant."
        )
        prompt_text = "\n".join(prompt_parts) if prompt_parts else ""

        # Define signature inline so the docstring (system prompt) can be set
        class _Completion(dspy.Signature):
            prompt: str = dspy.InputField(desc="User message or conversation")
            response: str = dspy.OutputField(desc="Assistant response")

        _Completion.__doc__ = system_text

        lm = self._ensure_lm()
        with dspy.context(lm=lm):
            result = dspy.Predict(_Completion)(prompt=prompt_text)
        return str(getattr(result, "response", result))

    # ── Module gating ─────────────────────────────────────────────────────

    def run_module(self, module: Any, **kwargs: Any) -> str:
        """
        Gate any pre-built DSPy module or compiled program.

        Runs module(**kwargs) inside dspy.context(lm=self._ensure_lm()) so the
        adapter's model is used without permanently changing global state.

        Args:
            module:   Any callable DSPy module — Predict, ChainOfThought,
                      ReAct, compiled Program, etc.
            **kwargs: Forwarded to module(**kwargs).

        Returns:
            First string-valued output field of the Prediction, or str(result).
        """
        import dspy

        lm = self._ensure_lm()
        with dspy.context(lm=lm):
            result = module(**kwargs)
        return self._extract_prediction(result)

    @staticmethod
    def _extract_prediction(result: Any) -> str:
        """
        Extract a string output from a dspy.Prediction (or any object).

        Priority:
          1. First string-valued non-private attribute from instance __dict__
          2. First string-valued non-private attribute from class __dict__
          3. str(result)
        """
        for d in (getattr(result, "__dict__", {}), getattr(type(result), "__dict__", {})):
            for k, v in d.items():
                if not k.startswith("_") and isinstance(v, str):
                    return v
        return str(result)

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

        The returned object is a plain callable compatible with dspy.ReAct:

            tool  = gate.as_tool(resource_fn=my_handler)
            react = dspy.ReAct(QA, tools=[tool])

        DSPy reads tool.__name__ and tool.__doc__ for its tool descriptions.
        Both are set on the returned AlgoVoiPaymentTool.

        Args:
            resource_fn:      Callable receiving (query: str) → str
            tool_name:        Tool name (sets .__name__ for DSPy)
            tool_description: Tool description (sets .__doc__ for DSPy)

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
