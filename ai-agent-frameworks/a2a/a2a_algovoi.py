"""
AlgoVoi Google A2A Adapter
===========================

Payment-gate any Google A2A (Agent-to-Agent) endpoint using x402, MPP, or AP2 —
paid in USDC on Algorand, VOI, Hedera, or Stellar.

Google's Agent-to-Agent (A2A) protocol is a JSON-RPC 2.0 over HTTP standard for
agent interoperability. This adapter:

  - Gates incoming A2A requests with on-chain payment verification
  - Acts as an A2A client: sends message/send requests with optional payment proof
  - Provides a JSON-RPC 2.0 server handler (message/send, tasks/get, tasks/cancel)
  - Generates compliant agent cards for /.well-known/agent-card.json
  - Exposes a payment tool callable for use inside A2A agent pipelines

A2A specification: https://google.github.io/A2A/
JSON-RPC 2.0:      https://www.jsonrpc.org/specification

x402 gate reused from ai-adapters/openai/openai_algovoi.py.
MPP and AP2 gates require the sibling mpp-adapter/ and ap2-adapter/ directories.

Version: 1.0.0
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

__version__ = "1.0.0"

_MAX_BODY = 1_048_576  # 1 MiB — cap request body reads

# JSON-RPC 2.0 error codes
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
        # Set __name__ and __doc__ for frameworks that read tool metadata
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
    Payment gate for Google A2A (Agent-to-Agent) endpoints.

    Gates incoming A2A JSON-RPC requests with on-chain payment verification
    using x402, MPP, or AP2. Model-agnostic — works with any LLM backend.

    Surfaces:
      check(headers[, body])                 Verify payment proof
      send_message(agent_url, text, ...)     Call another A2A agent (client)
      handle_request(body, handler[, hdrs])  Route incoming JSON-RPC (server)
      agent_card(agent_url, ...)             Generate /.well-known/agent-card.json
      as_tool(resource_fn, ...)              Payment tool for A2A pipelines
      flask_guard()                          Convenience Flask check-only handler
      flask_agent(message_handler)           Full A2A Flask server endpoint
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
        self._tasks: Dict[str, dict] = {}
        self._gate              = self._build_gate()

    # ── Gate builder ──────────────────────────────────────────────────────────

    def _build_gate(self) -> Any:
        root  = _adapters_root()
        proto = self._protocol.lower()

        if proto == "mpp":
            _add_path(os.path.join(root, "mpp-adapter"))
            from mpp_algovoi import AlgoVoiMppGate  # type: ignore[import]

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
            from ap2_algovoi import AlgoVoiAp2Gate  # type: ignore[import]

            return AlgoVoiAp2Gate(
                algovoi_key=self._algovoi_key,
                tenant_id=self._tenant_id,
                payout_address=self._payout_address,
                networks=[self._network],
                amount_microunits=self._amount_microunits,
            )

        # x402 (default / fallback)
        _add_path(os.path.join(root, "ai-adapters", "openai"))
        from openai_algovoi import AlgoVoiX402Gate  # type: ignore[import]

        return AlgoVoiX402Gate(
            algovoi_key=self._algovoi_key,
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
        Send a ``message/send`` JSON-RPC request to another A2A agent.

        Attaches ``Authorization: Payment <proof>`` if ``payment_proof`` is given.
        If the remote agent returns HTTP 402, returns a JSON-RPC error dict whose
        ``data.challenge_headers`` field holds the 402 challenge headers so the
        caller can pay and retry.

        Args:
            agent_url:     HTTPS URL of the remote A2A agent endpoint.
            text:          Text content of the user message.
            payment_proof: Base64-encoded payment proof (omit to get a challenge).
            message_id:    Optional JSON-RPC request ID (auto-generated if omitted).
            timeout:       HTTP timeout in seconds (default 30).

        Returns:
            JSON-RPC 2.0 response dict — ``result`` on success, ``error`` on failure.

        Raises:
            ValueError:              If ``agent_url`` does not start with ``https://``.
            urllib.error.HTTPError:  For non-402 HTTP errors.
        """
        import urllib.request
        import urllib.error

        if not agent_url.startswith("https://"):
            raise ValueError(f"A2A agent URL must use HTTPS: {agent_url!r}")

        rpc_id = message_id or str(uuid.uuid4())
        req_headers: Dict[str, str] = {"Content-Type": "application/json"}
        if payment_proof:
            req_headers["Authorization"] = f"Payment {payment_proof}"

        payload = {
            "jsonrpc": "2.0",
            "method":  "message/send",
            "params": {
                "message": {
                    "role":  "user",
                    "parts": [{"type": "text", "text": text}],
                }
            },
            "id": rpc_id,
        }

        req = urllib.request.Request(
            agent_url,
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
                    "jsonrpc": "2.0",
                    "error": {
                        "code":    _A2A_PAYMENT_REQUIRED,
                        "message": "payment_required",
                        "data":    {"challenge_headers": challenge},
                    },
                    "id": rpc_id,
                }
            raise

    # ── A2A server ────────────────────────────────────────────────────────────

    def handle_request(
        self,
        body: dict,
        message_handler: Callable[[str], str],
        headers: Optional[dict] = None,
    ) -> dict:
        """
        Route an incoming A2A JSON-RPC 2.0 request.

        Dispatches ``message/send`` to ``message_handler``, handles ``tasks/get``
        and ``tasks/cancel`` from the internal task store, and rejects unknown
        methods with a standard JSON-RPC error.

        If ``headers`` are provided, payment is verified before routing. An
        unverified request returns a JSON-RPC error with payment challenge data.

        Args:
            body:            Parsed JSON-RPC 2.0 request dict.
            message_handler: ``Callable[[str], str]`` — receives extracted message
                             text, returns reply text. Called only for ``message/send``.
            headers:         Optional request headers for payment verification.

        Returns:
            JSON-RPC 2.0 response dict.
        """
        rpc_id = body.get("id")
        method = body.get("method", "")
        params = body.get("params") or {}

        # Optional payment check
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
        task = {**task, "status": {**task["status"], "state": "canceled"}}
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

    # ── Agent card ────────────────────────────────────────────────────────────

    def agent_card(
        self,
        agent_url: str,
        skills: Optional[List[dict]] = None,
        supports_streaming: bool = False,
        supports_push: bool = False,
    ) -> dict:
        """
        Generate a compliant A2A agent card dict.

        Serve this JSON at ``/.well-known/agent-card.json`` for client discovery.

        Args:
            agent_url:          HTTPS URL of this agent's A2A endpoint.
            skills:             Optional list of A2A AgentSkill dicts.
            supports_streaming: Whether the agent supports ``message/stream``.
            supports_push:      Whether the agent supports push notifications.

        Returns:
            Dict matching the A2A AgentCard specification.
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

    # ── Flask helpers ─────────────────────────────────────────────────────────

    def flask_guard(self) -> Any:
        """
        Payment-check-only Flask handler.

        Returns a 402 Flask Response if payment is required, otherwise ``None``
        so the caller can proceed with custom response logic.

        Usage::

            @app.route("/a2a", methods=["POST"])
            def a2a_endpoint():
                guard = gate.flask_guard()
                if guard is not None:
                    return guard          # 402
                body = request.get_json()
                return jsonify(gate.handle_request(body, my_handler))
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
        message_handler: Callable[[str], str],
    ) -> Any:
        """
        Full A2A Flask endpoint handler — payment check + JSON-RPC routing.

        Parses the JSON-RPC body, verifies payment, then routes ``message/send``
        to ``message_handler`` and manages task state for ``tasks/get`` /
        ``tasks/cancel``.

        Usage::

            @app.route("/a2a", methods=["POST"])
            def a2a_endpoint():
                return gate.flask_agent(lambda text: my_llm(text))

            @app.route("/.well-known/agent-card.json")
            def card():
                return jsonify(gate.agent_card("https://myhost.com/a2a"))
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
