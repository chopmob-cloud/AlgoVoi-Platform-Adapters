"""
AlgoVoi Agno Adapter
====================

Payment-gate any Agno Agent using x402, MPP, or AP2 — paid in USDC on
Algorand, VOI, Hedera, or Stellar.

Agno (agno-agi/agno, formerly Phidata) is a multi-modal AI agent framework
featuring pre/post run hooks, AgentOS (FastAPI-based production runtime),
and a rich tool ecosystem. This adapter gates Agno agents behind on-chain
payment verification.

Three integration surfaces:

  1. Direct wrapper
     gate = AlgoVoiAgno(algovoi_key="algv_...", ...)

     # Explicit check then run
     result = gate.check(dict(request.headers), request.get_json())
     if result.requires_payment:
         return result.as_flask_response()
     output = agent.run("user message")

     # Or combined wrapper
     output = gate.run_agent(agent, "user message",
                             headers=dict(request.headers))

  2. Agno pre-hook factory
     hook = gate.make_pre_hook(headers={"Authorization": "Payment ..."})
     gated_agent = Agent(model=..., pre_hooks=[hook])
     gated_agent.run("message")   # raises AgnoPaymentRequired if unpaid

  3. FastAPI / AgentOS middleware
     app = agent_os.get_app()          # AgentOS FastAPI app
     gate.fastapi_middleware(app)      # add payment gate to all routes

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
from typing import Any, Callable, Optional

__version__ = "1.0.0"

_API_BASE = "https://api1.ilovechicken.co.uk"
_MAX_BODY = 1_048_576  # 1 MiB

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


# ── Exceptions ─────────────────────────────────────────────────────────────────

class AgnoPaymentRequired(Exception):
    """
    Raised by ``make_pre_hook`` callbacks and ``run_agent`` / ``arun_agent``
    when a payment proof is absent or invalid.

    Attributes:
        result: The ``AgnoResult`` that triggered the exception.
    """

    def __init__(self, result: "AgnoResult") -> None:
        self.result = result
        super().__init__(result.error or "Payment Required")


# ── Result ─────────────────────────────────────────────────────────────────────

class AgnoResult:
    """
    Unified payment-check result for all three protocols.

    Attributes:
        requires_payment: True if the caller must pay before proceeding.
        receipt:          MppReceipt on MPP success (else None).
        mandate:          Ap2Mandate on AP2 success (else None).
        error:            Error message if verification failed (else None).
    """

    def __init__(self, inner: Any) -> None:
        self._inner           = inner
        self.requires_payment: bool          = inner.requires_payment
        self.receipt:          Any           = getattr(inner, "receipt",  None)
        self.mandate:          Any           = getattr(inner, "mandate",  None)
        self.error:            Optional[str] = getattr(inner, "error",    None)

    def as_flask_response(self):
        """Return a Flask-compatible ``(body, 402, headers)`` tuple."""
        if hasattr(self._inner, "as_wsgi_response"):
            _, wsgi_headers, body_bytes = self._inner.as_wsgi_response()
            return body_bytes.decode(), 402, dict(wsgi_headers)
        body = json.dumps({"error": "Payment Required", "detail": self.error or ""})
        return body, 402, {"Content-Type": "application/json"}

    def as_wsgi_response(self):
        """Return a WSGI 3-tuple ``(status, headers, body_bytes)``."""
        if hasattr(self._inner, "as_wsgi_response"):
            return self._inner.as_wsgi_response()
        body = json.dumps(
            {"error": "Payment Required", "detail": self.error or ""}
        ).encode()
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


# ── ASGI payment middleware ────────────────────────────────────────────────────

class _AgnoPaymentMiddleware:
    """
    ASGI middleware that intercepts every HTTP request and enforces the
    AlgoVoi payment gate before forwarding to the wrapped application.

    Non-HTTP ASGI connections (WebSocket, lifespan) pass through unchanged.
    """

    def __init__(self, app: Any, gate: "AlgoVoiAgno") -> None:
        self._app  = app
        self._gate = gate

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return

        # Decode headers from ASGI scope (list of (bytes, bytes) tuples)
        raw_headers = scope.get("headers", [])
        headers = {
            k.decode("latin-1"): v.decode("latin-1")
            for k, v in raw_headers
        }

        result = self._gate.check(headers)
        if not result.requires_payment:
            await self._app(scope, receive, send)
            return

        # Build 402 response
        status_line, resp_headers, body_bytes = result.as_wsgi_response()
        status_code = int(status_line.split()[0])

        # Encode headers for ASGI
        asgi_headers = [
            (k.encode("latin-1"), v.encode("latin-1"))
            for k, v in resp_headers
        ]
        if not any(k == b"content-type" for k, _ in asgi_headers):
            asgi_headers.append((b"content-type", b"application/json"))

        await send({
            "type": "http.response.start",
            "status": status_code,
            "headers": asgi_headers,
        })
        await send({
            "type": "http.response.body",
            "body": body_bytes,
        })


# ── Main adapter ───────────────────────────────────────────────────────────────

class AlgoVoiAgno:
    """
    Payment gate for Agno agents.

    Gates any Agno ``Agent`` (sync or async) behind on-chain payment
    verification using x402, MPP, or AP2.  Three integration surfaces:

    **Direct check + run wrapper**::

        gate = AlgoVoiAgno(algovoi_key="algv_...", ...)
        output = gate.run_agent(agent, "What is 2+2?",
                                headers=dict(request.headers))

    **Pre-hook injection**::

        hook = gate.make_pre_hook(headers={"Authorization": "Payment ..."})
        agent = Agent(model=OpenAIChat("gpt-4o"), pre_hooks=[hook])
        agent.run("What is 2+2?")   # raises AgnoPaymentRequired if no proof

    **FastAPI / AgentOS middleware**::

        app = agent_os.get_app()
        gate.fastapi_middleware(app)

    Attributes:
        NETWORKS:  Supported blockchain networks.
        PROTOCOLS: Supported payment protocols.
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
        """
        Args:
            algovoi_key:       AlgoVoi API key (``algv_...``).
            tenant_id:         AlgoVoi tenant ID.
            payout_address:    Blockchain address to receive payments.
            protocol:          ``"mpp"``, ``"x402"``, or ``"ap2"``.
            network:           One of :data:`NETWORKS`.
            amount_microunits: Payment amount in micro-units (e.g. 10_000 = $0.01).
            resource_id:       Logical resource identifier for MPP challenges.
        """
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

    def check(self, headers: dict, body: Optional[dict] = None) -> AgnoResult:
        """
        Verify payment proof from request headers.

        Args:
            headers: Request headers dict (e.g. ``dict(request.headers)``).
            body:    Optional parsed request body dict.

        Returns:
            :class:`AgnoResult` — ``requires_payment=True`` means the caller
            must supply a valid payment proof; ``False`` means verified.
        """
        try:
            inner = self._gate.check(headers, body or {})
        except TypeError:
            inner = self._gate.check(headers)
        return AgnoResult(inner)

    # ── Sync agent runner ─────────────────────────────────────────────────────

    def run_agent(
        self,
        agent: Any,
        message: str,
        headers: Optional[dict] = None,
        body: Optional[dict] = None,
    ) -> Any:
        """
        Check payment proof then run an Agno agent synchronously.

        Args:
            agent:   An Agno ``Agent`` instance.
            message: The user message / prompt to pass to ``agent.run()``.
            headers: Request headers dict containing the payment proof.
            body:    Optional parsed request body dict.

        Returns:
            The ``RunResponse`` (or whatever ``agent.run()`` returns) on success.

        Raises:
            AgnoPaymentRequired: If the payment proof is absent or invalid.
        """
        result = self.check(headers or {}, body)
        if result.requires_payment:
            raise AgnoPaymentRequired(result)
        return agent.run(message)

    # ── Async agent runner ────────────────────────────────────────────────────

    async def arun_agent(
        self,
        agent: Any,
        message: str,
        headers: Optional[dict] = None,
        body: Optional[dict] = None,
    ) -> Any:
        """
        Check payment proof then run an Agno agent asynchronously.

        Args:
            agent:   An Agno ``Agent`` instance.
            message: The user message / prompt to pass to ``await agent.arun()``.
            headers: Request headers dict containing the payment proof.
            body:    Optional parsed request body dict.

        Returns:
            The async ``RunResponse`` on success.

        Raises:
            AgnoPaymentRequired: If the payment proof is absent or invalid.
        """
        result = self.check(headers or {}, body)
        if result.requires_payment:
            raise AgnoPaymentRequired(result)
        return await agent.arun(message)

    # ── Pre-hook factory ──────────────────────────────────────────────────────

    def make_pre_hook(
        self,
        headers: Optional[dict] = None,
        body: Optional[dict] = None,
    ) -> Callable:
        """
        Return an Agno-compatible pre-hook that enforces payment.

        The returned callable accepts any positional/keyword arguments (Agno
        passes context objects to hooks) and raises :class:`AgnoPaymentRequired`
        if the payment proof captured in ``headers`` is absent or invalid.

        Usage::

            hook = gate.make_pre_hook(headers={"Authorization": "Payment ..."})
            agent = Agent(model=OpenAIChat("gpt-4o"), pre_hooks=[hook])
            agent.run("user prompt")

        Args:
            headers: Headers dict to check — typically captured from the
                     HTTP request before constructing the agent.
            body:    Optional body dict.

        Returns:
            A callable suitable for use in ``Agent(pre_hooks=[...])``.

        Raises:
            AgnoPaymentRequired: Raised inside the hook at agent run time
                                 if the payment proof is missing or invalid.
        """
        _headers = headers or {}
        _body    = body

        def _hook(*args: Any, **kwargs: Any) -> None:
            result = self.check(_headers, _body)
            if result.requires_payment:
                raise AgnoPaymentRequired(result)

        return _hook

    # ── FastAPI / AgentOS middleware ───────────────────────────────────────────

    def fastapi_middleware(self, app: Any) -> Any:
        """
        Add AlgoVoi payment verification as ASGI middleware to a FastAPI app.

        Intercepts every HTTP request before it reaches any route handler.
        Non-HTTP connections (WebSocket, lifespan) pass through unchanged.

        Usage::

            from agno.os import AgentOS
            agent_os = AgentOS(agents=[my_agent])
            app = agent_os.get_app()
            gate.fastapi_middleware(app)    # mutates app in-place

        Args:
            app: A FastAPI application (or any ASGI app).

        Returns:
            The same ``app`` object (for chaining).
        """
        app.add_middleware(_AgnoPaymentMiddleware, gate=self)
        return app

    # ── Flask helpers ─────────────────────────────────────────────────────────

    def flask_guard(self) -> Any:
        """
        Payment-check-only Flask handler.

        Reads the current Flask request, verifies the payment proof, and
        returns a ``(body, 402, headers)`` Flask tuple if payment is required,
        or ``None`` if the proof is valid.

        Usage::

            @app.route("/agent", methods=["POST"])
            def agent_route():
                guard = gate.flask_guard()
                if guard is not None:
                    return guard          # 402
                output = my_agent.run(request.get_json()["message"])
                return jsonify({"response": output.content})
        """
        import flask

        raw = flask.request.get_data()
        if len(raw) > _MAX_BODY:
            raw = raw[:_MAX_BODY]
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
        agent: Any,
        message_key: str = "message",
    ) -> Any:
        """
        Full Flask endpoint handler — payment check + ``agent.run()``.

        Reads the current Flask request body, checks payment, extracts
        ``body[message_key]`` (default ``"message"``), calls ``agent.run()``,
        and returns the agent's ``content`` as JSON.

        Usage::

            @app.route("/agent", methods=["POST"])
            def agent_route():
                return gate.flask_agent(my_agent)

        Args:
            agent:       An Agno ``Agent`` instance.
            message_key: Key in the JSON body that holds the user message
                         (default ``"message"``).

        Returns:
            Flask JSON response with ``{"response": "<agent content>"}`` on
            success, or a ``402`` response if payment is required.
        """
        import flask
        from flask import jsonify

        raw = flask.request.get_data()
        if len(raw) > _MAX_BODY:
            raw = raw[:_MAX_BODY]
        try:
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            body = {}

        result = self.check(dict(flask.request.headers), body)
        if result.requires_payment:
            return result.as_flask_response()

        message = body.get(message_key, "")
        output  = agent.run(message)
        content = getattr(output, "content", str(output))
        return jsonify({"response": content})
