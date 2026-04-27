"""
AlgoVoi Semantic Kernel Adapter
================================

Payment-gate any Semantic Kernel function, chat completion, or kernel plugin
using x402, MPP, or AP2 — paid in USDC on Algorand, VOI, Hedera, or Stellar.

Three integration modes:

  1. Server-side gate — chat completion (Flask / FastAPI)
     -----------------------------------------
     from semantic_kernel_algovoi import AlgoVoiSemanticKernel

     gate = AlgoVoiSemanticKernel(
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
         body   = request.get_json(silent=True) or {}
         result = gate.check(dict(request.headers), body)
         if result.requires_payment:
             return result.as_flask_response()
         return jsonify({"content": gate.complete(body["messages"])})

     # Or use the convenience wrapper:
     @app.route("/ai/chat", methods=["POST"])
     def chat():
         return gate.flask_guard()

  2. Gate any KernelFunction
     -----------------------------------------
     result = gate.check(headers, body)
     if not result.requires_payment:
         output = gate.invoke_function(kernel, my_function, input=body["input"])

  3. Kernel plugin (add to any Kernel)
     -----------------------------------------
     plugin = gate.as_plugin(resource_fn=lambda q: my_handler(q), plugin_name="premium_kb")
     kernel.add_plugin(plugin, plugin_name="premium_kb")
     # The agent can then call: kernel.invoke(kernel.plugins["premium_kb"]["gate"], ...)
     # or the LLM can select the function via function calling.

Networks:
    algorand-mainnet, voi-mainnet, hedera-mainnet, stellar-mainnet

Protocols:
    mpp  — IETF draft-ryan-httpauth-payment (WWW-Authenticate: Payment)
    ap2  — AP2 v0.1 CartMandate/PaymentMandate + AlgoVoi crypto-algo extension
    x402 — x402 spec v1 (X-PAYMENT-REQUIRED / X-PAYMENT)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any, Optional

__version__ = "1.1.0"
__all__ = ["AlgoVoiSemanticKernel", "AlgoVoiPaymentPlugin", "SemanticKernelResult"]

# ── Path helpers ──────────────────────────────────────────────────────────────

# Three levels up from ai-agent-frameworks/semantic-kernel/semantic_kernel_algovoi.py
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
    "base-mainnet",
    "solana-mainnet",
    "tempo-mainnet",
})

PROTOCOLS = frozenset({"mpp", "ap2", "x402"})

# ── Body-size cap for flask_guard ─────────────────────────────────────────────

_MAX_FLASK_BODY = 1_048_576  # 1 MiB

# ── @kernel_function decorator stub ──────────────────────────────────────────
# Used at class-definition time by AlgoVoiPaymentPlugin.
# Real SK decorator sets rich metadata; stub sets minimal attrs so tests run
# without semantic_kernel installed.

_SK_AVAILABLE = False
try:
    from semantic_kernel.functions import kernel_function as _kf_decorator  # type: ignore
    _SK_AVAILABLE = True
except ImportError:
    def _kf_decorator(  # type: ignore[misc]
        name: Optional[str] = None,
        description: Optional[str] = None,
        **_kwargs: Any,
    ):
        def _wrap(fn: Any) -> Any:
            fn.__sk_kernel_function_name__ = name or getattr(fn, "__name__", "gate")
            fn.__sk_kernel_function_description__ = description or ""
            return fn
        return _wrap


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

class SemanticKernelResult:
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

class AlgoVoiSemanticKernel:
    """
    Payment-gate wrapper for Semantic Kernel (Python SDK, v1.x).

    Supports three integration surfaces:

    * ``complete(messages)``
      — build a Kernel with OpenAI chat service and call chat completion
    * ``invoke_function(kernel, function, **kwargs)``
      — gate ``kernel.invoke(function, ...)`` for any ``KernelFunction``
    * ``as_plugin(resource_fn, ...)``
      — return an ``AlgoVoiPaymentPlugin`` that can be added to any ``Kernel``

    All async SK operations are wrapped with ``asyncio.run()`` for synchronous use.

    Args:
        algovoi_key (str): AlgoVoi API key (``algv_...``).
        tenant_id (str): AlgoVoi tenant UUID.
        payout_address (str): On-chain address to receive payments.
        openai_key (str | None): OpenAI API key — used to build the default
            Kernel / ``OpenAIChatCompletion`` service.
        protocol (str): ``"mpp"`` | ``"ap2"`` | ``"x402"`` (default: ``"mpp"``).
        network (str): Chain network key (default: ``"algorand-mainnet"``).
        amount_microunits (int): Price per call in USDC microunits (default: ``10000``).
        model (str): OpenAI model ID used when building the default Kernel
            (default: ``"gpt-4o"``).
        base_url (str | None): Override OpenAI API base URL.
        resource_id (str): Resource identifier used in MPP challenges
            (default: ``"ai-function"``).
    """

    def __init__(
        self,
        algovoi_key: str,
        tenant_id: str,
        payout_address: str,
        openai_key: Optional[str] = None,
        protocol: str = "mpp",
        network: str = "algorand-mainnet",
        amount_microunits: int = 10_000,
        model: str = "gpt-4o",
        base_url: Optional[str] = None,
        resource_id: str = "ai-function",
    ) -> None:
        if protocol not in PROTOCOLS:
            raise ValueError(f"protocol must be one of {sorted(PROTOCOLS)}")
        if network not in NETWORKS:
            raise ValueError(f"network must be one of {sorted(NETWORKS)}")

        self._openai_key = openai_key
        self._model = model
        self._base_url = base_url
        self._kernel: Any = None  # lazy Kernel

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

    def check(self, headers: dict, body: Optional[dict] = None) -> SemanticKernelResult:
        """
        Verify a payment proof from request headers.

        Returns a :class:`SemanticKernelResult` whose ``requires_payment`` flag
        indicates whether a 402 challenge should be returned to the client.
        """
        try:
            raw = self._gate.check(headers, body or {})
        except TypeError:
            raw = self._gate.check(headers)
        return SemanticKernelResult(raw)

    # ── Kernel helper ─────────────────────────────────────────────────────────

    def _ensure_kernel(self) -> Any:
        """Lazy-create a Kernel with OpenAIChatCompletion service."""
        if self._kernel is not None:
            return self._kernel
        from semantic_kernel import Kernel  # type: ignore
        from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion  # type: ignore

        service_kwargs: dict[str, Any] = {
            "ai_model_id": self._model,
            "service_id": "chat",
        }
        if self._openai_key:
            service_kwargs["api_key"] = self._openai_key
        if self._base_url:
            service_kwargs["base_url"] = self._base_url

        self._kernel = Kernel()
        self._kernel.add_service(OpenAIChatCompletion(**service_kwargs))
        return self._kernel

    # ── Chat completion ───────────────────────────────────────────────────────

    def complete(self, messages: list[dict]) -> str:
        """
        Call SK ``ChatCompletionClientBase.get_chat_message_content()`` with
        OpenAI-format messages and return the reply as a plain string.

        Accepted roles: ``system``, ``user``, ``assistant``.

        This is a synchronous wrapper — uses ``asyncio.run()`` internally.

        Call only after ``gate.check()`` returns ``requires_payment = False``.

        Example::

            result = gate.check(headers, body)
            if not result.requires_payment:
                reply = gate.complete(body["messages"])
        """
        return asyncio.run(self._complete_async(messages))

    async def _complete_async(self, messages: list[dict]) -> str:
        from semantic_kernel.connectors.ai.chat_completion_client_base import (  # type: ignore
            ChatCompletionClientBase,
        )
        from semantic_kernel.contents import ChatHistory  # type: ignore

        kernel = self._ensure_kernel()
        service = kernel.get_service(type=ChatCompletionClientBase)

        history = ChatHistory()
        for m in messages:
            role = (m.get("role") or "user").lower()
            content = m.get("content", "")
            if role == "system":
                history.add_system_message(content)
            elif role == "assistant":
                history.add_assistant_message(content)
            else:
                history.add_user_message(content)

        response = await service.get_chat_message_content(history, settings=None)
        return str(response)

    # ── KernelFunction gate ───────────────────────────────────────────────────

    def invoke_function(self, kernel: Any, function: Any, **kwargs: Any) -> str:
        """
        Gate ``kernel.invoke(function, **kwargs)`` and return the result as
        a plain string.

        Call only after ``gate.check()`` returns ``requires_payment = False``.

        This is a synchronous wrapper — uses ``asyncio.run()`` internally.

        Args:
            kernel: A ``semantic_kernel.Kernel`` instance.
            function: A ``KernelFunction`` to invoke (looked up from
                ``kernel.plugins`` or created with ``KernelFunctionFromPrompt``).
            **kwargs: Arguments forwarded to ``kernel.invoke()``.

        Example::

            fn = kernel.plugins["MyPlugin"]["summarise"]
            result = gate.check(headers, body)
            if not result.requires_payment:
                output = gate.invoke_function(kernel, fn, input=body["text"])
        """
        return asyncio.run(self._invoke_async(kernel, function, **kwargs))

    async def _invoke_async(self, kernel: Any, function: Any, **kwargs: Any) -> str:
        result = await kernel.invoke(function, **kwargs)
        return str(result)

    # ── Plugin ────────────────────────────────────────────────────────────────

    def as_plugin(
        self,
        resource_fn: Any,
        plugin_name: str = "AlgoVoiPaymentPlugin",
        gate_description: str = (
            "Payment-gated resource. "
            "Provide 'query' with your question and 'payment_proof' (base64-encoded). "
            "Returns a payment challenge JSON if proof is absent or invalid, "
            "or the resource response when payment is verified."
        ),
    ) -> "AlgoVoiPaymentPlugin":
        """
        Return an :class:`AlgoVoiPaymentPlugin` that can be added to any Kernel.

        The plugin exposes a single ``@kernel_function`` named ``gate``.

        Example::

            plugin = gate.as_plugin(resource_fn=my_handler, plugin_name="premium_kb")
            kernel.add_plugin(plugin, plugin_name="premium_kb")
            # Invoke directly:
            fn = kernel.plugins["premium_kb"]["gate"]
            output = gate.invoke_function(kernel, fn, query="...", payment_proof="...")
        """
        return AlgoVoiPaymentPlugin(
            adapter=self,
            resource_fn=resource_fn,
            plugin_name=plugin_name,
            gate_description=gate_description,
        )

    # ── Flask convenience ─────────────────────────────────────────────────────

    def flask_guard(self) -> Any:
        """
        Convenience Flask handler — check + complete in one call.

        Reads ``request.headers`` and ``request.json`` automatically.
        Returns a Flask ``Response`` (402 + challenge) or a JSON dict with
        ``{"content": "..."}`` that the view can return directly.

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


# ── Plugin class ──────────────────────────────────────────────────────────────

class AlgoVoiPaymentPlugin:
    """
    Semantic Kernel plugin that wraps an AlgoVoi payment gate.

    Add to any ``Kernel``::

        plugin = gate.as_plugin(resource_fn=my_handler, plugin_name="premium_kb")
        kernel.add_plugin(plugin, plugin_name="premium_kb")

    The plugin exposes one ``@kernel_function`` named ``gate``:

        query         — the question or task
        payment_proof — base64-encoded payment proof (empty → challenge returned)

    Returns challenge JSON (``{"error": "payment_required", ...}``) when proof
    is absent or invalid, or ``str(resource_fn(query))`` when verified.
    """

    def __init__(
        self,
        adapter: Any,
        resource_fn: Any,
        plugin_name: str = "AlgoVoiPaymentPlugin",
        gate_description: str = (
            "Payment-gated resource. "
            "Provide 'query' with your question and 'payment_proof' (base64-encoded). "
            "Returns a payment challenge JSON if proof is absent or invalid, "
            "or the resource response when payment is verified."
        ),
    ) -> None:
        self.name = plugin_name
        self._adapter = adapter
        self._resource_fn = resource_fn
        # Re-apply the description to the gate method at instance level
        self.gate.__func__.__sk_kernel_function_description__ = gate_description  # type: ignore[attr-defined]

    @_kf_decorator(
        name="gate",
        description=(
            "Payment-gated resource. "
            "Provide 'query' with your question and 'payment_proof' (base64-encoded). "
            "Returns a payment challenge JSON if proof is absent or invalid, "
            "or the resource response when payment is verified."
        ),
    )
    def gate(self, query: str = "", payment_proof: str = "") -> str:
        """
        Verify payment and return challenge JSON or resource response.

        Can be invoked directly via ``kernel.invoke(fn, query=..., payment_proof=...)``
        or called by the LLM through SK function calling.
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
