"""
AlgoVoi Google A2A Adapter
===========================

Payment-gate any Google A2A (Agent-to-Agent) endpoint using x402, MPP, or AP2 —
paid in USDC on Algorand, VOI, Hedera, or Stellar.

Google's Agent-to-Agent (A2A) protocol v1.0 uses REST-style endpoints over HTTPS
for agent interoperability. This adapter:

  - Gates incoming A2A requests with on-chain payment verification
  - Acts as an A2A client: sends POST /message:send requests with optional payment proof
  - Provides REST endpoint handlers for all six A2A v1.0 server routes
  - Generates compliant agent cards for /.well-known/agent.json
  - Provides an extended agent card for /extendedAgentCard (auth-required)
  - Exposes a payment tool callable for use inside A2A agent pipelines

A2A v1.0 server endpoints:
  GET  /.well-known/agent.json       — public agent discovery card
  GET  /extendedAgentCard            — auth-required extended card
  POST /message:send                 — send a message, get a task result
  GET  /tasks                        — list all tasks
  GET  /tasks/{id}                   — get a specific task by ID
  POST /tasks/{id}:cancel            — cancel a task

A2A specification: https://a2aproject.github.io/A2A/
x402 gate reused from ai-adapters/openai/openai_algovoi.py.
MPP and AP2 gates require the sibling mpp-adapter/ and ap2-adapter/ directories.

Version: 2.0.0
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

__version__ = "2.0.0"

_MAX_BODY = 1_048_576  # 1 MiB — cap request body reads

_ALGOVOI_API_BASE = os.environ.get(
    "ALGOVOI_API_BASE", "https://cloud.algovoi.co.uk"
)

# JSON-RPC 2.0 error codes (kept for legacy handle_request compatibility)
_JSONRPC_PARSE_ERROR       = -32700
_JSONRPC_METHOD_NOT_FOUND  = -32601
_JSONRPC_INTERNAL_ERROR    = -32603

# A2A-specific error codes
_A2A_PAYMENT_REQUIRED = -32000
_A2A_TASK_NOT_FOUND   = -32001


def _add_path(target: str) -> None:
    """Prepend *target* to sys.path (no-op if already present)."""
    if target not in sys.path:
        sys.path.insert(0, target)


def _adapters_root() -> str:
    """Return the repository root (three directories above this file)."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(here))


# ── Result wrapper ─────────────────────────────────────────────────────────────

class A2AResult:
    """
    Thin wrapper around the underlying gate result.

    Mirrors the surface of all other AlgoVoi adapter result objects:
      result.requires_payment   — True → client must pay; False → request allowed
      result.error              — human-readable reason for rejection
      result.as_wsgi_response() → (status_code, headers_list, body_bytes)
      result.as_flask_response() → Flask Response object (status 402)
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


# ── Payment tool ───────────────────────────────────────────────────────────────

class AlgoVoiPaymentTool:
    """
    Payment-gate callable for use inside A2A agent pipelines.

    Accepts ``query`` and ``payment_proof`` as arguments. Returns:
      - Challenge JSON ``{"error": "payment_required", ...}`` if proof absent/invalid
      - ``resource_fn(query)`` result as str if payment proof is verified
    """

    def __init__(
        self,
        adapter: "AlgoVoiA2A",
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
        self.__name__ = tool_name
        self.__doc__ = tool_description

    def __call__(self, query: str = "", payment_proof: str = "") -> str:
        headers: Dict[str, str] = {}
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


# ── Main adapter ───────────────────────────────────────────────────────────────

class AlgoVoiA2A:
    """
    Payment gate for Google A2A v1.0 (Agent-to-Agent) endpoints.

    Gates incoming A2A requests with on-chain payment verification using
    x402, MPP, or AP2. Model-agnostic — works with any LLM backend.

    REST endpoint Flask helpers (A2A v1.0):
      flask_agent_card()                     GET  /.well-known/agent.json   (public)
      flask_extended_agent_card()            GET  /extendedAgentCard        (auth)
      flask_message_send(handler)            POST /message:send             (auth)
      flask_list_tasks()                     GET  /tasks                    (auth)
      flask_get_task(task_id)                GET  /tasks/<task_id>          (auth)
      flask_cancel_task(task_id)             POST /tasks/<task_id>:cancel   (auth)

    Other surfaces:
      check(headers[, body])                 Verify payment proof
      send_message(agent_url, text, ...)     Call another A2A agent (client)
      agent_card(agent_url, ...)             Build /.well-known/agent.json dict
      extended_agent_card(agent_url, ...)    Build /extendedAgentCard dict
      list_tasks()                           List all tasks in task store
      as_tool(resource_fn, ...)              Payment tool for A2A pipelines

    Legacy (JSON-RPC compat):
      handle_request(body, handler[, hdrs])  Route JSON-RPC 2.0 request (v1.0 compat)
      flask_agent(message_handler)           Single-endpoint JSON-RPC Flask handler
    """

    def __init__(
        self,
        algovoi_key: str,
        tenant_id: str,
        payout_address: str,
        protocol: str = "mpp",
        network: str = "algorand-mainnet",
        amount_microunits: int = 10_000,
        resource_id: str = "ai-function",
        agent_name: str = "AlgoVoi Agent",
        agent_description: str = "Payment-gated AI agent powered by AlgoVoi",
        agent_version: str = "1.0.0",
        api_base: str = _ALGOVOI_API_BASE,
    ) -> None:
        self._algovoi_key       = algovoi_key
        self._tenant_id         = tenant_id
        self._payout_address    = payout_address
        self._protocol          = protocol
        self._network           = network
        self._amount_microunits = amount_microunits
        self._resource_id       = resource_id
        self._agent_name        = agent_name
        self._agent_description = agent_description
        self._agent_version     = agent_version
        self._api_base          = api_base.rstrip("/")
        self._tasks: Dict[str, dict] = {}
        self._gate              = self._build_gate()

    # ── Gate builder ──────────────────────────────────────────────────────────

    def _build_gate(self) -> Any:
        root  = _adapters_root()
        proto = self._protocol.lower()

        if proto == "mpp":
            _add_path(os.path.join(root, "mpp-adapter"))
            from mpp import MppGate  # type: ignore[import]

            return MppGate(
                api_base=self._api_base, api_key=self._algovoi_key,
                tenant_id=self._tenant_id,
                payout_address=self._payout_address,
                networks=[self._network],
                amount_microunits=self._amount_microunits,
                resource_id=self._resource_id,
            )

        if proto == "ap2":
            _add_path(os.path.join(root, "ap2-adapter"))
            from ap2 import Ap2Gate  # type: ignore

            return Ap2Gate(
                merchant_id=self._tenant_id, api_base=self._api_base,
                api_key=self._algovoi_key,
                payout_address=self._payout_address,
                networks=[self._network],
                amount_microunits=self._amount_microunits,
            )

        # x402 (default / fallback)
        _add_path(os.path.join(root, "ai-adapters", "openai"))
        from openai_algovoi import _X402Gate  # type: ignore

        return _X402Gate(
            api_base=self._api_base, api_key=self._algovoi_key,
            tenant_id=self._tenant_id,
            payout_address=self._payout_address,
            networks=[self._network],
            amount_microunits=self._amount_microunits,
        )

    # ── Payment check ─────────────────────────────────────────────────────────

    def check(self, headers: dict, body: Optional[dict] = None) -> A2AResult:
        """
        Verify payment proof from request headers.

        Args:
            headers: Request headers dict. Header names are case-normalised
                     internally by each gate.
            body:    Optional parsed request body dict.

        Returns:
            A2AResult with requires_payment=True if a 402 challenge is needed,
            or requires_payment=False if the payment proof is verified.
        """
        try:
            gate_result = self._gate.check(headers, body or {})
        except TypeError:
            gate_result = self._gate.check(headers)
        return A2AResult(
            requires_payment=gate_result.requires_payment,
            error=getattr(gate_result, "error", "") or "",
            gate=gate_result,
        )

    # ── Agent card ────────────────────────────────────────────────────────────

    def agent_card(
        self,
        agent_url: str,
        skills: Optional[List[dict]] = None,
        supports_streaming: bool = False,
        supports_push: bool = False,
    ) -> dict:
        """
        Generate a public A2A agent card dict.

        Serve this JSON at ``GET /.well-known/agent.json`` for client discovery.
        This endpoint is public (no auth required).

        Args:
            agent_url:          HTTPS URL of this agent's base endpoint.
            skills:             Optional list of A2A AgentSkill dicts.
            supports_streaming: Whether the agent supports message streaming.
            supports_push:      Whether the agent supports push notifications.

        Returns:
            Dict matching the A2A v1.0 AgentCard specification.
        """
        card: dict = {
            "name":        self._agent_name,
            "description": self._agent_description,
            "url":         agent_url,
            "version":     self._agent_version,
            "capabilities": {
                "streaming":              supports_streaming,
                "pushNotifications":      supports_push,
                "stateTransitionHistory": False,
            },
            "defaultInputModes":  ["text/plain"],
            "defaultOutputModes": ["text/plain"],
        }
        if skills:
            card["skills"] = skills
        return card

    def extended_agent_card(
        self,
        agent_url: str,
        skills: Optional[List[dict]] = None,
        supports_streaming: bool = False,
        supports_push: bool = False,
    ) -> dict:
        """
        Generate an extended A2A agent card dict including authentication details.

        Serve this JSON at ``GET /extendedAgentCard`` (auth required).
        Extends the public agent card with supported payment protocols and
        authentication scheme information.

        Args:
            agent_url:          HTTPS URL of this agent's base endpoint.
            skills:             Optional list of A2A AgentSkill dicts.
            supports_streaming: Whether the agent supports message streaming.
            supports_push:      Whether the agent supports push notifications.

        Returns:
            Extended AgentCard dict with authentication and protocol metadata.
        """
        card = self.agent_card(agent_url, skills, supports_streaming, supports_push)
        card["authentication"] = {
            "schemes": [self._protocol.upper()],
            "protocols": {
                "mpp":  "IETF draft-ryan-httpauth-payment",
                "x402": "x402 specification v1",
                "ap2":  "AP2 v0.1 agentic commerce",
            }.get(self._protocol.lower(), self._protocol),
            "networks": [self._network],
            "currency": "USDC",
            "amount_microunits": self._amount_microunits,
        }
        card["endpoints"] = {
            "agentCard":         f"{agent_url}/.well-known/agent.json",
            "extendedAgentCard": f"{agent_url}/extendedAgentCard",
            "messageSend":       f"{agent_url}/message:send",
            "tasks":             f"{agent_url}/tasks",
            "task":              f"{agent_url}/tasks/{{id}}",
            "taskCancel":        f"{agent_url}/tasks/{{id}}:cancel",
        }
        return card

    # ── Task store ────────────────────────────────────────────────────────────

    def list_tasks(self) -> List[dict]:
        """
        Return all tasks in the task store.

        Returns:
            List of task dicts, most recent first.
        """
        return list(reversed(list(self._tasks.values())))

    # ── A2A client ────────────────────────────────────────────────────────────

    def send_message(
        self,
        agent_url: str,
        text: str,
        payment_proof: str = "",
        message_id: Optional[str] = None,
        timeout: int = 30,
    ) -> dict:
        """
        Send a message to another A2A agent via ``POST /message:send``.

        Attaches ``Authorization: Payment <proof>`` if ``payment_proof`` is given.
        If the remote agent returns HTTP 402, returns a dict whose
        ``challenge_headers`` field holds the 402 challenge headers so the
        caller can pay and retry.

        Args:
            agent_url:     HTTPS base URL of the remote A2A agent.
            text:          Text content of the user message.
            payment_proof: Base64-encoded payment proof (omit to get a challenge).
            message_id:    Optional request ID (auto-generated if omitted).
            timeout:       HTTP timeout in seconds (default 30).

        Returns:
            Task dict on success, or ``{"error": ..., "challenge_headers": ...}``
            on 402.

        Raises:
            ValueError:              If ``agent_url`` does not start with ``https://``.
            urllib.error.HTTPError:  For non-402 HTTP errors.
        """
        import urllib.request
        import urllib.error

        if not agent_url.startswith("https://"):
            raise ValueError(f"A2A agent URL must use HTTPS: {agent_url!r}")

        endpoint = agent_url.rstrip("/") + "/message:send"
        req_headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "X-Request-Id": message_id or str(uuid.uuid4()),
        }
        if payment_proof:
            req_headers["Authorization"] = f"Payment {payment_proof}"

        payload = {
            "message": {
                "role":  "user",
                "parts": [{"type": "text", "text": text}],
                "messageId": message_id or str(uuid.uuid4()),
            }
        }

        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode(),
            headers=req_headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            if exc.code == 402:
                challenge: Dict[str, str] = {}
                for key in ("WWW-Authenticate", "X-PAYMENT-REQUIRED", "X-AP2-Cart-Mandate"):
                    val = exc.headers.get(key)
                    if val:
                        challenge[key] = val
                return {
                    "error": "payment_required",
                    "challenge_headers": challenge,
                    "request_id": req_headers["X-Request-Id"],
                }
            raise

    # ── Flask REST helpers (A2A v1.0) ─────────────────────────────────────────

    def flask_agent_card(
        self,
        agent_url: str,
        skills: Optional[List[dict]] = None,
        supports_streaming: bool = False,
        supports_push: bool = False,
    ) -> Any:
        """
        Flask handler for ``GET /.well-known/agent.json`` (public, no auth).

        Usage::

            @app.route("/.well-known/agent.json")
            def agent_card_endpoint():
                return gate.flask_agent_card("https://myhost.com")
        """
        from flask import jsonify
        return jsonify(self.agent_card(agent_url, skills, supports_streaming, supports_push))

    def flask_extended_agent_card(
        self,
        agent_url: str,
        skills: Optional[List[dict]] = None,
        supports_streaming: bool = False,
        supports_push: bool = False,
    ) -> Any:
        """
        Flask handler for ``GET /extendedAgentCard`` (GatewayAuth required).

        Usage::

            @app.route("/extendedAgentCard")
            def extended_card():
                return gate.flask_extended_agent_card("https://myhost.com")
        """
        from flask import jsonify
        guard = self.flask_guard()
        if guard is not None:
            return guard
        return jsonify(self.extended_agent_card(agent_url, skills, supports_streaming, supports_push))

    def flask_message_send(
        self,
        message_handler: Callable[[str], str],
    ) -> Any:
        """
        Flask handler for ``POST /message:send`` (GatewayAuth required).

        Parses the A2A message body, verifies payment, dispatches to
        ``message_handler``, stores the task, and returns it.

        Usage::

            @app.route("/message:send", methods=["POST"])
            def message_send():
                return gate.flask_message_send(lambda text: my_llm(text))
        """
        import flask
        from flask import jsonify

        raw = flask.request.get_data()
        if len(raw) > _MAX_BODY:
            raw = raw[:_MAX_BODY]
        try:
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return flask.Response(
                json.dumps({"error": "invalid_json"}),
                status=400,
                mimetype="application/json",
            )

        guard = self.flask_guard()
        if guard is not None:
            return guard

        message = body.get("message") or {}
        text    = self._extract_text(message)
        task_id = str(uuid.uuid4())
        ts      = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            result_text = message_handler(text)
            task: dict = {
                "id":        task_id,
                "status":    {"state": "completed", "timestamp": ts},
                "artifacts": [{"parts": [{"type": "text", "text": str(result_text)}]}],
            }
        except Exception as exc:
            task = {
                "id":        task_id,
                "status":    {"state": "failed", "timestamp": ts},
                "artifacts": [],
                "error":     str(exc),
            }

        self._tasks[task_id] = task
        return jsonify(task)

    def flask_list_tasks(self) -> Any:
        """
        Flask handler for ``GET /tasks`` (GatewayAuth required).

        Returns all tasks in reverse-chronological order.

        Usage::

            @app.route("/tasks")
            def list_tasks():
                return gate.flask_list_tasks()
        """
        from flask import jsonify

        guard = self.flask_guard()
        if guard is not None:
            return guard
        return jsonify({"tasks": self.list_tasks()})

    def flask_get_task(self, task_id: str) -> Any:
        """
        Flask handler for ``GET /tasks/<task_id>`` (GatewayAuth required).

        Usage::

            @app.route("/tasks/<task_id>")
            def get_task(task_id):
                return gate.flask_get_task(task_id)
        """
        import flask
        from flask import jsonify

        guard = self.flask_guard()
        if guard is not None:
            return guard

        task = self._tasks.get(task_id)
        if task is None:
            return flask.Response(
                json.dumps({"error": "task_not_found", "id": task_id}),
                status=404,
                mimetype="application/json",
            )
        return jsonify(task)

    def flask_cancel_task(self, task_id: str) -> Any:
        """
        Flask handler for ``POST /tasks/<task_id>:cancel`` (GatewayAuth required).

        Usage::

            @app.route("/tasks/<task_id>:cancel", methods=["POST"])
            def cancel_task(task_id):
                return gate.flask_cancel_task(task_id)
        """
        import flask
        from flask import jsonify

        guard = self.flask_guard()
        if guard is not None:
            return guard

        task = self._tasks.get(task_id)
        if task is None:
            return flask.Response(
                json.dumps({"error": "task_not_found", "id": task_id}),
                status=404,
                mimetype="application/json",
            )

        ts   = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        task = {**task, "status": {**task.get("status", {}), "state": "canceled", "timestamp": ts}}
        self._tasks[task_id] = task
        return jsonify(task)

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

        The tool checks payment before calling ``resource_fn`` and is suitable
        for use inside any A2A agent pipeline.

        Args:
            resource_fn:      ``Callable[[str], str]`` — receives query, returns answer.
            tool_name:        Tool identifier name.
            tool_description: Human-readable description.

        Returns:
            AlgoVoiPaymentTool instance (callable + ``.name`` + ``.description``).
        """
        return AlgoVoiPaymentTool(self, resource_fn, tool_name, tool_description)

    # ── Flask helpers (payment gate only) ─────────────────────────────────────

    def flask_guard(self) -> Any:
        """
        Payment-check-only Flask handler.

        Returns a 402 Flask Response if payment is required, otherwise ``None``
        so the caller can proceed with custom response logic.

        Usage::

            @app.route("/message:send", methods=["POST"])
            def message_send():
                guard = gate.flask_guard()
                if guard is not None:
                    return guard          # 402
                body = request.get_json()
                # ... handle message
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

    # ── Legacy JSON-RPC compat ────────────────────────────────────────────────

    def handle_request(
        self,
        body: dict,
        message_handler: Callable[[str], str],
        headers: Optional[dict] = None,
    ) -> dict:
        """
        Route an incoming A2A JSON-RPC 2.0 request (legacy compat).

        Dispatches ``message/send`` to ``message_handler``, handles ``tasks/get``
        and ``tasks/cancel`` from the internal task store.

        Prefer the REST Flask helpers (``flask_message_send``, ``flask_get_task``,
        ``flask_cancel_task``) for new A2A v1.0 deployments.

        Args:
            body:            Parsed JSON-RPC 2.0 request dict.
            message_handler: ``Callable[[str], str]`` — receives message text,
                             returns reply text.
            headers:         Optional request headers for payment verification.

        Returns:
            JSON-RPC 2.0 response dict.
        """
        rpc_id = body.get("id")
        method = body.get("method", "")
        params = body.get("params") or {}

        if headers:
            gate_result = self.check(headers, body)
            if gate_result.requires_payment:
                _, challenge_headers, _ = gate_result.as_wsgi_response()
                return self._rpc_error(
                    rpc_id,
                    _A2A_PAYMENT_REQUIRED,
                    "payment_required",
                    {"challenge_headers": {k: v for k, v in challenge_headers}},
                )

        if method == "message/send":
            return self._handle_message_send(rpc_id, params, message_handler)
        if method == "tasks/get":
            return self._handle_tasks_get(rpc_id, params)
        if method == "tasks/cancel":
            return self._handle_tasks_cancel(rpc_id, params)

        return self._rpc_error(
            rpc_id, _JSONRPC_METHOD_NOT_FOUND, f"Method not found: {method!r}"
        )

    def flask_agent(
        self,
        message_handler: Callable[[str], str],
    ) -> Any:
        """
        Full A2A JSON-RPC Flask endpoint handler (legacy compat).

        Prefer registering the individual REST Flask helpers for A2A v1.0
        deployments. Use this only for JSON-RPC single-endpoint servers.

        Usage::

            @app.route("/a2a", methods=["POST"])
            def a2a_endpoint():
                return gate.flask_agent(lambda text: my_llm(text))

            @app.route("/.well-known/agent.json")
            def card():
                return gate.flask_agent_card("https://myhost.com")
        """
        import flask
        from flask import jsonify

        raw = flask.request.get_data()
        if len(raw) > _MAX_BODY:
            raw = raw[:_MAX_BODY]
        try:
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return flask.Response(
                json.dumps(self._rpc_error(None, _JSONRPC_PARSE_ERROR, "Parse error")),
                status=400,
                mimetype="application/json",
            )

        headers = dict(flask.request.headers)
        result  = self.check(headers, body)
        if result.requires_payment:
            return result.as_flask_response()

        response = self.handle_request(body, message_handler)
        return jsonify(response)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _handle_message_send(
        self,
        rpc_id: Any,
        params: dict,
        message_handler: Callable[[str], str],
    ) -> dict:
        message = params.get("message") or {}
        text    = self._extract_text(message)
        task_id = str(uuid.uuid4())
        ts      = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            result_text = message_handler(text)
            task: dict = {
                "id":        task_id,
                "status":    {"state": "completed", "timestamp": ts},
                "artifacts": [{"parts": [{"type": "text", "text": str(result_text)}]}],
            }
        except Exception as exc:
            task = {
                "id":        task_id,
                "status":    {"state": "failed", "timestamp": ts},
                "artifacts": [],
                "error":     str(exc),
            }

        self._tasks[task_id] = task
        return {"jsonrpc": "2.0", "result": task, "id": rpc_id}

    def _handle_tasks_get(self, rpc_id: Any, params: dict) -> dict:
        task_id = str(params.get("id") or params.get("taskId") or "")
        task    = self._tasks.get(task_id)
        if task is None:
            return self._rpc_error(
                rpc_id, _A2A_TASK_NOT_FOUND, f"Task not found: {task_id!r}"
            )
        return {"jsonrpc": "2.0", "result": task, "id": rpc_id}

    def _handle_tasks_cancel(self, rpc_id: Any, params: dict) -> dict:
        task_id = str(params.get("id") or params.get("taskId") or "")
        task    = self._tasks.get(task_id)
        if task is None:
            return self._rpc_error(
                rpc_id, _A2A_TASK_NOT_FOUND, f"Task not found: {task_id!r}"
            )
        ts   = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        task = {**task, "status": {**task["status"], "state": "canceled", "timestamp": ts}}
        self._tasks[task_id] = task
        return {"jsonrpc": "2.0", "result": task, "id": rpc_id}

    @staticmethod
    def _extract_text(message: dict) -> str:
        """Concatenate text from all TextPart entries in an A2A message."""
        parts = message.get("parts") or []
        texts: List[str] = []
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                texts.append(str(part.get("text", "")))
        return " ".join(texts) if texts else ""

    @staticmethod
    def _rpc_error(rpc_id: Any, code: int, message: str, data: Any = None) -> dict:
        err: dict = {"code": code, "message": message}
        if data is not None:
            err["data"] = data
        return {"jsonrpc": "2.0", "error": err, "id": rpc_id}
