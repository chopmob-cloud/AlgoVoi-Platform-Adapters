"""
AlgoVoi AutoGen Adapter
=======================

Payment-gate any AutoGen conversation or callable tool using x402, MPP, or
AP2 — paid in USDC on Algorand, VOI, Hedera, or Stellar.

Three integration modes:

  1. Server-side gate — wrap initiate_chat() (Flask / FastAPI)
     -----------------------------------------
     from autogen_algovoi import AlgoVoiAutoGen

     gate = AlgoVoiAutoGen(
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
         output = gate.initiate_chat(assistant, user_proxy, body["message"])
         return jsonify({"content": output})

     # Or use the convenience wrapper:
     @app.route("/ai/run", methods=["POST"])
     def run():
         return gate.flask_guard(user_proxy, assistant)

  2. AutoGen callable tool
     -----------------------------------------
     tool = gate.as_tool(resource_fn=lambda q: my_handler(q), tool_name="premium_kb")

     # AutoGen 0.2.x — register with two decorators
     @user_proxy.register_for_execution()
     @assistant.register_for_llm(description=tool.description, name=tool.name)
     def premium_kb(query: str, payment_proof: str = "") -> str:
         return tool(query=query, payment_proof=payment_proof)

     # AutoGen 0.4.x — wrap with FunctionTool
     from autogen_core.tools import FunctionTool
     fn_tool = FunctionTool(tool, description=tool.description, name=tool.name)
     agent = AssistantAgent("assistant", tools=[fn_tool], model_client=...)

  3. Custom initiate_chat helper
     -----------------------------------------
     result = gate.check(headers, body)
     if not result.requires_payment:
         output = gate.initiate_chat(
             recipient = assistant,
             sender    = user_proxy,
             message   = body["message"],
             max_turns = 10,
         )
         # output = ChatResult.summary or last message content (str)

Networks:
    algorand-mainnet, voi-mainnet, hedera-mainnet, stellar-mainnet,
    base-mainnet, solana-mainnet, tempo-mainnet

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

__version__ = "1.1.0"
__all__ = ["AlgoVoiAutoGen", "AlgoVoiPaymentTool", "AutoGenResult"]

# ── Path helpers ──────────────────────────────────────────────────────────────

# Three levels up from ai-agent-frameworks/autogen/autogen_algovoi.py
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

class AutoGenResult:
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

class AlgoVoiAutoGen:
    """
    Payment-gate wrapper for AutoGen (0.2.x / pyautogen).

    Supports three integration surfaces:

    * ``initiate_chat(recipient, sender, message)``
      — gates ``sender.initiate_chat(recipient, ...)`` and returns the reply
    * ``as_tool(resource_fn)``
      — callable tool compatible with AutoGen 0.2.x ``register_for_execution``
        and AutoGen 0.4.x ``FunctionTool``
    * ``llm_config``
      — property that returns an AutoGen-format ``llm_config`` dict built from
        ``openai_key`` / ``model`` / ``base_url``, ready to pass when creating
        ``ConversableAgent`` / ``AssistantAgent``

    Args:
        algovoi_key (str): AlgoVoi API key (``algv_...``).
        tenant_id (str): AlgoVoi tenant UUID.
        payout_address (str): On-chain address to receive payments.
        openai_key (str | None): OpenAI API key — used to build the default
            ``llm_config`` dict when agents are not supplied pre-configured.
        protocol (str): ``"mpp"`` | ``"ap2"`` | ``"x402"`` (default: ``"mpp"``).
        network (str): Chain network key (default: ``"algorand-mainnet"``).
        amount_microunits (int): Price per call in USDC microunits (default: ``10000``).
        model (str): OpenAI model ID used in the ``llm_config`` dict
            (default: ``"gpt-4o"``).
        base_url (str | None): Override OpenAI API base URL.
        resource_id (str): Resource identifier used in MPP challenges
            (default: ``"ai-conversation"``).
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
        resource_id: str = "ai-conversation",
    ) -> None:
        if protocol not in PROTOCOLS:
            raise ValueError(f"protocol must be one of {sorted(PROTOCOLS)}")
        if network not in NETWORKS:
            raise ValueError(f"network must be one of {sorted(NETWORKS)}")

        self._openai_key = openai_key
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

    def check(self, headers: dict, body: Optional[dict] = None) -> AutoGenResult:
        """
        Verify a payment proof from request headers.

        Returns an :class:`AutoGenResult` whose ``requires_payment`` flag
        indicates whether a 402 challenge should be returned to the client.
        """
        try:
            raw = self._gate.check(headers, body or {})
        except TypeError:
            raw = self._gate.check(headers)
        return AutoGenResult(raw)

    # ── LLM config helper ─────────────────────────────────────────────────────

    @property
    def llm_config(self) -> dict:
        """
        AutoGen-format ``llm_config`` dict built from ``openai_key`` / ``model``.

        Pass directly when creating agents::

            from autogen import AssistantAgent
            assistant = AssistantAgent("assistant", llm_config=gate.llm_config)
        """
        cfg: dict[str, Any] = {"model": self._model}
        if self._openai_key:
            cfg["api_key"] = self._openai_key
        if self._base_url:
            cfg["base_url"] = self._base_url
        return {"config_list": [cfg]}

    # ── Conversation gate ─────────────────────────────────────────────────────

    def initiate_chat(
        self,
        recipient: Any,
        sender: Any,
        message: str,
        max_turns: Optional[int] = None,
        **kwargs: Any,
    ) -> str:
        """
        Gate ``sender.initiate_chat(recipient, message=message)`` and return
        the conversation result as a plain string.

        Call only after ``gate.check()`` returns ``requires_payment = False``.

        Result extraction priority:
        1. ``ChatResult.summary`` — set when agents are configured with a
           ``summary_method`` (``"reflection_with_llm"`` or ``"last_msg"``).
        2. Last message in ``ChatResult.chat_history``.
        3. ``str(chat_result)`` fallback.

        Args:
            recipient: The AutoGen agent that receives and replies to the message
                (typically an ``AssistantAgent``).
            sender: The agent that initiates the conversation
                (typically a ``UserProxyAgent``).
            message (str): Initial message text.
            max_turns (int | None): Maximum number of conversation turns.
                Passed through to ``initiate_chat`` if provided.
            **kwargs: Additional keyword arguments forwarded to ``initiate_chat``.

        Example::

            result = gate.check(headers, body)
            if not result.requires_payment:
                output = gate.initiate_chat(
                    recipient = assistant,
                    sender    = user_proxy,
                    message   = body["message"],
                    max_turns = 3,
                )
                return jsonify({"content": output})
        """
        ic_kwargs: dict[str, Any] = {"message": message, **kwargs}
        if max_turns is not None:
            ic_kwargs["max_turns"] = max_turns

        chat_result = sender.initiate_chat(recipient, **ic_kwargs)
        return _extract_chat_result(chat_result)

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
        Return an :class:`AlgoVoiPaymentTool` wrapping this gate and
        ``resource_fn``.

        The returned tool is callable and compatible with:

        * **AutoGen 0.2.x** — register with ``@register_for_execution()``
          and ``@register_for_llm(description=..., name=...)``
        * **AutoGen 0.4.x** — wrap with ``FunctionTool(tool, ...)``

        Example::

            tool = gate.as_tool(resource_fn=my_handler, tool_name="premium_kb")

            # 0.2.x
            @user_proxy.register_for_execution()
            @assistant.register_for_llm(description=tool.description, name=tool.name)
            def premium_kb(query: str, payment_proof: str = "") -> str:
                return tool(query=query, payment_proof=payment_proof)

            # 0.4.x
            from autogen_core.tools import FunctionTool
            fn_tool = FunctionTool(tool, description=tool.description, name=tool.name)
        """
        return AlgoVoiPaymentTool(
            adapter=self,
            resource_fn=resource_fn,
            tool_name=tool_name,
            tool_description=tool_description,
        )

    # ── Flask convenience ─────────────────────────────────────────────────────

    def flask_guard(
        self,
        sender: Any,
        recipient: Any,
        message_fn: Optional[Any] = None,
        max_turns: Optional[int] = None,
    ) -> Any:
        """
        Convenience Flask handler — check + initiate_chat in one call.

        Reads ``request.headers`` and ``request.json`` automatically.

        Args:
            sender: AutoGen agent that initiates the conversation.
            recipient: AutoGen agent that receives and replies.
            message_fn: Optional callable ``(body: dict) -> str`` that extracts
                the message from the request body. If ``None``,
                ``body.get("message", "")`` is used.
            max_turns (int | None): Passed through to ``initiate_chat``.

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

        message = message_fn(body) if callable(message_fn) else body.get("message", "")
        return jsonify({"content": self.initiate_chat(
            recipient=recipient,
            sender=sender,
            message=message,
            max_turns=max_turns,
        )})


# ── Chat result extraction ────────────────────────────────────────────────────

def _extract_chat_result(chat_result: Any) -> str:
    """
    Extract a plain string from an AutoGen ``ChatResult``.

    Priority:
    1. ``chat_result.summary`` (set when ``summary_method`` is configured)
    2. Last ``content`` in ``chat_result.chat_history``
    3. ``str(chat_result)``
    """
    summary = getattr(chat_result, "summary", None)
    if summary:
        return str(summary)
    history = getattr(chat_result, "chat_history", None)
    if history and isinstance(history, list) and history:
        last = history[-1]
        if isinstance(last, dict):
            return str(last.get("content", ""))
    return str(chat_result)


# ── Agent tool class ──────────────────────────────────────────────────────────

class AlgoVoiPaymentTool:
    """
    Callable payment-gate tool for AutoGen agents.

    Register with any AutoGen agent::

        tool = gate.as_tool(resource_fn=my_handler, tool_name="premium_kb")

        # AutoGen 0.2.x:
        @user_proxy.register_for_execution()
        @assistant.register_for_llm(description=tool.description, name=tool.name)
        def premium_kb(query: str, payment_proof: str = "") -> str:
            return tool(query=query, payment_proof=payment_proof)

        # AutoGen 0.4.x:
        from autogen_core.tools import FunctionTool
        fn_tool = FunctionTool(tool, description=tool.description, name=tool.name)

    The agent passes ``query`` and ``payment_proof`` (base64-encoded).
    Returns challenge JSON if proof absent/invalid, or ``resource_fn(query)`` if
    payment is verified.
    """

    def __init__(
        self,
        adapter: Any,
        resource_fn: Any,
        tool_name: str = "algovoi_payment_gate",
        tool_description: str = (
            "Payment-gated resource. "
            "Provide 'query' with your question and 'payment_proof' (base64-encoded). "
            "Returns a payment challenge JSON if proof is absent or invalid, "
            "or the resource response when payment is verified."
        ),
    ) -> None:
        self.name = tool_name
        self.description = tool_description
        self._adapter = adapter
        self._resource_fn = resource_fn

    def __call__(self, query: str = "", payment_proof: str = "") -> str:
        """
        Verify payment and return challenge JSON or resource response.

        Used directly as a callable (AutoGen 0.4.x ``FunctionTool``) or
        delegated to from a registered function (AutoGen 0.2.x).
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
