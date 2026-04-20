"""
Unit tests for AlgoVoi Google A2A Adapter v2.0.0
=================================================

108 tests covering A2AResult, constructor, MPP/x402/AP2 gate delegation,
send_message (REST), handle_request (legacy JSON-RPC), agent_card,
extended_agent_card, list_tasks, all six Flask REST endpoint helpers,
as_tool, flask_guard, and flask_agent (legacy).

All gate interactions are mocked — no live API calls.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

# ── path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from a2a_algovoi import (
    A2AResult,
    AlgoVoiA2A,
    AlgoVoiPaymentTool,
    __version__,
    _A2A_PAYMENT_REQUIRED,
    _A2A_TASK_NOT_FOUND,
    _JSONRPC_METHOD_NOT_FOUND,
    _JSONRPC_PARSE_ERROR,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _no_proof_gate() -> MagicMock:
    """Mock gate that always requires payment."""
    gate   = MagicMock()
    result = MagicMock()
    result.requires_payment = True
    result.error = "Payment proof required"
    result.as_wsgi_response.return_value = (
        402,
        [("WWW-Authenticate", 'Payment realm="API Access", id="tid", intent="charge"')],
        b'{"error":"payment_required"}',
    )
    gate.check.return_value = result
    return gate


def _ok_gate() -> MagicMock:
    """Mock gate that always passes payment."""
    gate   = MagicMock()
    result = MagicMock()
    result.requires_payment = False
    result.error = ""
    result.as_wsgi_response.return_value = (200, [], b"{}")
    gate.check.return_value = result
    return gate


def _make_adapter(
    protocol: str = "mpp",
    network: str = "algorand-mainnet",
    gate: Optional[MagicMock] = None,
    **kwargs,
) -> AlgoVoiA2A:
    """Create an AlgoVoiA2A with _build_gate mocked."""
    mock_gate = gate if gate is not None else _no_proof_gate()
    with patch.object(AlgoVoiA2A, "_build_gate", return_value=mock_gate):
        adapter = AlgoVoiA2A(
            algovoi_key="algv_test",
            tenant_id="test-tid",
            payout_address="TEST_ADDR",
            protocol=protocol,
            network=network,
            **kwargs,
        )
    adapter._gate = mock_gate
    return adapter


# ═══════════════════════════════════════════════════════════════════════════════
# Group 1 — A2AResult (9 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestA2AResult:
    def test_requires_payment_true(self):
        r = A2AResult(requires_payment=True)
        assert r.requires_payment is True

    def test_requires_payment_false(self):
        r = A2AResult(requires_payment=False)
        assert r.requires_payment is False

    def test_error_field(self):
        r = A2AResult(requires_payment=True, error="bad proof")
        assert r.error == "bad proof"

    def test_error_defaults_empty(self):
        r = A2AResult(requires_payment=True)
        assert r.error == ""

    def test_wsgi_fallback_status(self):
        r = A2AResult(requires_payment=True, error="nope")
        status, _, _ = r.as_wsgi_response()
        assert status == 402

    def test_wsgi_fallback_body_json(self):
        r = A2AResult(requires_payment=True, error="nope")
        _, _, body = r.as_wsgi_response()
        assert json.loads(body)["error"] == "nope"

    def test_wsgi_delegates_to_gate_result(self):
        mock_gate = MagicMock()
        mock_gate.as_wsgi_response.return_value = (402, [("X-Custom", "val")], b"body")
        r = A2AResult(requires_payment=True, gate=mock_gate)
        status, headers, body = r.as_wsgi_response()
        assert status == 402
        assert headers[0] == ("X-Custom", "val")

    def test_wsgi_fallback_no_gate(self):
        r = A2AResult(requires_payment=True)
        status, headers, body = r.as_wsgi_response()
        assert status == 402
        assert headers == []

    def test_flask_response_status_402(self):
        pytest.importorskip("flask")
        from flask import Flask
        app = Flask(__name__)
        with app.app_context():
            r = A2AResult(requires_payment=True, error="payment_required")
            resp = r.as_flask_response()
            assert resp.status_code == 402


# ═══════════════════════════════════════════════════════════════════════════════
# Group 2 — VERSION (1 test)
# ═══════════════════════════════════════════════════════════════════════════════

class TestVersion:
    def test_version_string(self):
        assert __version__ == "2.0.0"


# ═══════════════════════════════════════════════════════════════════════════════
# Group 3 — Constructor (6 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestConstructor:
    def test_defaults(self):
        a = _make_adapter()
        assert a._protocol          == "mpp"
        assert a._network           == "algorand-mainnet"
        assert a._amount_microunits == 10_000
        assert a._resource_id       == "ai-function"

    def test_custom_protocol(self):
        a = _make_adapter(protocol="x402")
        assert a._protocol == "x402"

    def test_custom_network(self):
        a = _make_adapter(network="hedera-mainnet")
        assert a._network == "hedera-mainnet"

    def test_custom_agent_name(self):
        a = _make_adapter(agent_name="MyBot")
        assert a._agent_name == "MyBot"

    def test_task_store_initialized_empty(self):
        a = _make_adapter()
        assert isinstance(a._tasks, dict)
        assert len(a._tasks) == 0

    def test_custom_api_base(self):
        a = _make_adapter(api_base="https://api1.ilovechicken.co.uk")
        assert a._api_base == "https://api1.ilovechicken.co.uk"


# ═══════════════════════════════════════════════════════════════════════════════
# Group 4 — MPP check (10 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestMppCheck:
    def test_no_proof_requires_payment(self):
        a = _make_adapter(protocol="mpp")
        r = a.check({})
        assert r.requires_payment is True

    def test_no_proof_wsgi_402(self):
        a = _make_adapter(protocol="mpp")
        r = a.check({})
        status, _, _ = r.as_wsgi_response()
        assert status == 402

    def test_no_proof_www_authenticate_header(self):
        a = _make_adapter(protocol="mpp")
        r = a.check({})
        _, headers, _ = r.as_wsgi_response()
        keys = [h[0] for h in headers]
        assert "WWW-Authenticate" in keys

    def test_gate_check_called_with_headers(self):
        gate = _no_proof_gate()
        a = _make_adapter(protocol="mpp", gate=gate)
        a.check({"X-Test": "1"}, {"body": "data"})
        gate.check.assert_called_once()
        call_args = gate.check.call_args
        assert call_args[0][0]["X-Test"] == "1"

    def test_network_voi(self):
        a = _make_adapter(protocol="mpp", network="voi-mainnet")
        r = a.check({})
        assert r.requires_payment is True

    def test_network_hedera(self):
        a = _make_adapter(protocol="mpp", network="hedera-mainnet")
        r = a.check({})
        assert r.requires_payment is True

    def test_valid_proof_passes(self):
        a = _make_adapter(protocol="mpp", gate=_ok_gate())
        r = a.check({"Authorization": "Payment valid-proof"})
        assert r.requires_payment is False

    def test_invalid_proof_rejected(self):
        a = _make_adapter(protocol="mpp")
        r = a.check({"Authorization": "Payment bad-proof"})
        assert r.requires_payment is True

    def test_error_field_propagated(self):
        gate   = _no_proof_gate()
        result = gate.check.return_value
        result.error = "HMAC mismatch"
        a = _make_adapter(protocol="mpp", gate=gate)
        r = a.check({})
        assert r.error == "HMAC mismatch"

    def test_check_passes_body_to_gate(self):
        gate = _no_proof_gate()
        a = _make_adapter(protocol="mpp", gate=gate)
        body = {"message": {"parts": []}}
        a.check({}, body)
        call_args = gate.check.call_args
        assert call_args[0][1] == body


# ═══════════════════════════════════════════════════════════════════════════════
# Group 5 — x402 check (8 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestX402Check:
    def _x402_gate(self, verified: bool = False) -> MagicMock:
        gate   = MagicMock()
        result = MagicMock()
        result.requires_payment = not verified
        result.error = "" if verified else "No x402 proof"
        import base64
        challenge = base64.b64encode(json.dumps({
            "x402Version": 1,
            "accepts":     [{"network": "algorand-mainnet", "asset": "USDC"}],
        }).encode()).decode()
        result.as_wsgi_response.return_value = (
            402,
            [("X-PAYMENT-REQUIRED", challenge)],
            b'{"error":"payment_required"}',
        )
        gate.check.return_value = result
        return gate

    def test_no_proof_requires_payment(self):
        a = _make_adapter(protocol="x402", gate=self._x402_gate())
        r = a.check({})
        assert r.requires_payment is True

    def test_no_proof_wsgi_402(self):
        a = _make_adapter(protocol="x402", gate=self._x402_gate())
        r = a.check({})
        status, _, _ = r.as_wsgi_response()
        assert status == 402

    def test_no_proof_x_payment_required_header(self):
        a = _make_adapter(protocol="x402", gate=self._x402_gate())
        r = a.check({})
        _, headers, _ = r.as_wsgi_response()
        keys = [h[0] for h in headers]
        assert "X-PAYMENT-REQUIRED" in keys

    def test_challenge_is_base64_json(self):
        import base64
        a = _make_adapter(protocol="x402", gate=self._x402_gate())
        r = a.check({})
        _, headers, _ = r.as_wsgi_response()
        hdr_val = next(v for k, v in headers if k == "X-PAYMENT-REQUIRED")
        decoded = json.loads(base64.b64decode(hdr_val))
        assert decoded["x402Version"] == 1

    def test_challenge_has_accepts(self):
        import base64
        a = _make_adapter(protocol="x402", gate=self._x402_gate())
        r = a.check({})
        _, headers, _ = r.as_wsgi_response()
        hdr_val = next(v for k, v in headers if k == "X-PAYMENT-REQUIRED")
        decoded = json.loads(base64.b64decode(hdr_val))
        assert isinstance(decoded["accepts"], list)

    def test_valid_proof_passes(self):
        a = _make_adapter(protocol="x402", gate=self._x402_gate(verified=True))
        r = a.check({"X-PAYMENT": "valid-proof"})
        assert r.requires_payment is False

    def test_invalid_proof_rejected(self):
        a = _make_adapter(protocol="x402", gate=self._x402_gate())
        r = a.check({"X-PAYMENT": "bad"})
        assert r.requires_payment is True

    def test_network_hedera(self):
        a = _make_adapter(protocol="x402", network="hedera-mainnet", gate=self._x402_gate())
        r = a.check({})
        assert r.requires_payment is True


# ═══════════════════════════════════════════════════════════════════════════════
# Group 6 — AP2 check (8 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAp2Check:
    def _ap2_gate(self, verified: bool = False) -> MagicMock:
        gate   = MagicMock()
        result = MagicMock()
        result.requires_payment = not verified
        result.error = "" if verified else "No AP2 mandate"
        import base64
        challenge = base64.b64encode(json.dumps({
            "type":        "CartMandate",
            "ap2_version": "0.1",
            "network":     "algorand-mainnet",
        }).encode()).decode()
        result.as_wsgi_response.return_value = (
            402,
            [("X-AP2-Cart-Mandate", challenge)],
            b'{"error":"payment_required"}',
        )
        gate.check.return_value = result
        return gate

    def test_no_mandate_requires_payment(self):
        a = _make_adapter(protocol="ap2", gate=self._ap2_gate())
        r = a.check({})
        assert r.requires_payment is True

    def test_no_mandate_wsgi_402(self):
        a = _make_adapter(protocol="ap2", gate=self._ap2_gate())
        r = a.check({})
        status, _, _ = r.as_wsgi_response()
        assert status == 402

    def test_no_mandate_x_ap2_header(self):
        a = _make_adapter(protocol="ap2", gate=self._ap2_gate())
        r = a.check({})
        _, headers, _ = r.as_wsgi_response()
        keys = [h[0] for h in headers]
        assert "X-AP2-Cart-Mandate" in keys

    def test_challenge_is_base64_json(self):
        import base64
        a = _make_adapter(protocol="ap2", gate=self._ap2_gate())
        r = a.check({})
        _, headers, _ = r.as_wsgi_response()
        hdr_val = next(v for k, v in headers if k == "X-AP2-Cart-Mandate")
        decoded = json.loads(base64.b64decode(hdr_val))
        assert decoded["type"] == "CartMandate"

    def test_challenge_has_ap2_version(self):
        import base64
        a = _make_adapter(protocol="ap2", gate=self._ap2_gate())
        r = a.check({})
        _, headers, _ = r.as_wsgi_response()
        hdr_val = next(v for k, v in headers if k == "X-AP2-Cart-Mandate")
        decoded = json.loads(base64.b64decode(hdr_val))
        assert decoded["ap2_version"] == "0.1"

    def test_valid_mandate_passes(self):
        a = _make_adapter(protocol="ap2", gate=self._ap2_gate(verified=True))
        r = a.check({"X-AP2-Payment": "valid-mandate"})
        assert r.requires_payment is False

    def test_invalid_mandate_rejected(self):
        a = _make_adapter(protocol="ap2", gate=self._ap2_gate())
        r = a.check({"X-AP2-Payment": "bad"})
        assert r.requires_payment is True

    def test_network_voi(self):
        a = _make_adapter(protocol="ap2", network="voi-mainnet", gate=self._ap2_gate())
        r = a.check({})
        assert r.requires_payment is True


# ═══════════════════════════════════════════════════════════════════════════════
# Group 7 — send_message (8 tests) — REST v2 format
# ═══════════════════════════════════════════════════════════════════════════════

class TestSendMessage:
    def _adapter(self) -> AlgoVoiA2A:
        return _make_adapter()

    def test_https_required(self):
        a = self._adapter()
        with pytest.raises(ValueError, match="HTTPS"):
            a.send_message("http://example.com", "hi")

    def test_with_proof_sends_auth_header(self):
        a = self._adapter()
        captured: dict = {}

        def fake_urlopen(req, timeout=30):
            captured["headers"] = dict(req.headers)
            resp = MagicMock()
            resp.read.return_value = json.dumps(
                {"id": "t1", "status": {"state": "completed"}}
            ).encode()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            return resp

        with patch("urllib.request.urlopen", fake_urlopen):
            a.send_message("https://agent.example.com", "hello", payment_proof="myproof")
        assert "Authorization" in captured["headers"]
        assert "myproof" in captured["headers"]["Authorization"]

    def test_no_proof_omits_auth_header(self):
        a = self._adapter()
        captured: dict = {}

        def fake_urlopen(req, timeout=30):
            captured["headers"] = dict(req.headers)
            resp = MagicMock()
            resp.read.return_value = json.dumps({"id": "t1", "status": {"state": "completed"}}).encode()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            return resp

        with patch("urllib.request.urlopen", fake_urlopen):
            a.send_message("https://agent.example.com", "hello")
        assert "Authorization" not in captured["headers"]

    def test_rest_payload_format(self):
        """Payload is REST style — top-level message, no jsonrpc wrapper."""
        a = self._adapter()
        captured: dict = {}

        def fake_urlopen(req, timeout=30):
            captured["data"] = json.loads(req.data.decode())
            resp = MagicMock()
            resp.read.return_value = b'{"id":"t1","status":{"state":"completed"}}'
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            return resp

        with patch("urllib.request.urlopen", fake_urlopen):
            a.send_message("https://agent.example.com", "test text", message_id="req-1")
        payload = captured["data"]
        assert "jsonrpc" not in payload
        assert payload["message"]["parts"][0]["text"] == "test text"
        assert payload["message"]["messageId"] == "req-1"

    def test_endpoint_url_uses_message_send_path(self):
        """Client POSTs to /message:send on the agent base URL."""
        a = self._adapter()
        captured: dict = {}

        def fake_urlopen(req, timeout=30):
            captured["url"] = req.full_url
            resp = MagicMock()
            resp.read.return_value = b'{"id":"t1","status":{"state":"completed"}}'
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            return resp

        with patch("urllib.request.urlopen", fake_urlopen):
            a.send_message("https://agent.example.com", "hi")
        assert captured["url"].endswith("/message:send")

    def test_success_returns_task(self):
        a = self._adapter()
        mock_task = {"id": "t1", "status": {"state": "completed"}}

        def fake_urlopen(req, timeout=30):
            resp = MagicMock()
            resp.read.return_value = json.dumps(mock_task).encode()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            return resp

        with patch("urllib.request.urlopen", fake_urlopen):
            result = a.send_message("https://agent.example.com", "hi")
        assert result["status"]["state"] == "completed"

    def test_402_returns_error_dict(self):
        a = self._adapter()
        mock_hdrs = MagicMock()
        mock_hdrs.get = lambda key, default=None: (
            'Payment realm="test"' if key == "WWW-Authenticate" else default
        )
        exc = urllib.error.HTTPError("https://x.com", 402, "Payment Required", mock_hdrs, None)
        with patch("urllib.request.urlopen", side_effect=exc):
            result = a.send_message("https://x.com", "hi")
        assert result["error"] == "payment_required"

    def test_402_includes_challenge_headers(self):
        a = self._adapter()
        mock_hdrs = MagicMock()
        mock_hdrs.get = lambda key, default=None: (
            'Payment realm="api"' if key == "WWW-Authenticate" else default
        )
        exc = urllib.error.HTTPError("https://x.com", 402, "Payment Required", mock_hdrs, None)
        with patch("urllib.request.urlopen", side_effect=exc):
            result = a.send_message("https://x.com", "hi")
        assert result["challenge_headers"].get("WWW-Authenticate") == 'Payment realm="api"'

    def test_non_402_http_error_reraises(self):
        a = self._adapter()
        exc = urllib.error.HTTPError("https://x.com", 500, "Internal Server Error", {}, None)
        with patch("urllib.request.urlopen", side_effect=exc):
            with pytest.raises(urllib.error.HTTPError):
                a.send_message("https://x.com", "hi")


# ═══════════════════════════════════════════════════════════════════════════════
# Group 8 — handle_request (12 tests) — legacy JSON-RPC compat
# ═══════════════════════════════════════════════════════════════════════════════

class TestHandleRequest:
    def _adapter(self) -> AlgoVoiA2A:
        return _make_adapter()

    def _send_body(self, text: str = "hello", rpc_id: object = "req-1") -> dict:
        return {
            "jsonrpc": "2.0",
            "method":  "message/send",
            "params":  {"message": {"role": "user", "parts": [{"type": "text", "text": text}]}},
            "id":      rpc_id,
        }

    def test_message_send_returns_jsonrpc_result(self):
        a = self._adapter()
        resp = a.handle_request(self._send_body(), lambda t: "reply")
        assert resp["jsonrpc"] == "2.0"
        assert "result" in resp

    def test_message_send_result_has_task_id(self):
        a = self._adapter()
        resp = a.handle_request(self._send_body(), lambda t: "reply")
        assert "id" in resp["result"]

    def test_message_send_task_state_completed(self):
        a = self._adapter()
        resp = a.handle_request(self._send_body(), lambda t: "reply")
        assert resp["result"]["status"]["state"] == "completed"

    def test_message_send_artifact_contains_reply(self):
        a = self._adapter()
        resp = a.handle_request(self._send_body(), lambda t: f"echo:{t}")
        part = resp["result"]["artifacts"][0]["parts"][0]
        assert part["type"]  == "text"
        assert "echo:hello" in part["text"]

    def test_message_send_handler_exception_gives_failed_state(self):
        a = self._adapter()
        def boom(t):
            raise RuntimeError("handler crashed")
        resp = a.handle_request(self._send_body(), boom)
        assert resp["result"]["status"]["state"] == "failed"
        assert "handler crashed" in resp["result"]["error"]

    def test_message_send_id_echoed(self):
        a = self._adapter()
        resp = a.handle_request(self._send_body(rpc_id="my-rpc"), lambda t: "ok")
        assert resp["id"] == "my-rpc"

    def test_tasks_get_found(self):
        a    = self._adapter()
        send = a.handle_request(self._send_body(), lambda t: "result")
        task_id = send["result"]["id"]
        get_resp = a.handle_request(
            {"jsonrpc": "2.0", "method": "tasks/get", "params": {"id": task_id}, "id": "g1"},
            lambda t: "",
        )
        assert get_resp["result"]["id"]                == task_id
        assert get_resp["result"]["status"]["state"]   == "completed"

    def test_tasks_get_not_found(self):
        a = self._adapter()
        resp = a.handle_request(
            {"jsonrpc": "2.0", "method": "tasks/get", "params": {"id": "no-such"}, "id": "g2"},
            lambda t: "",
        )
        assert resp["error"]["code"] == _A2A_TASK_NOT_FOUND

    def test_tasks_cancel(self):
        a    = self._adapter()
        send = a.handle_request(self._send_body(), lambda t: "ok")
        task_id = send["result"]["id"]
        cancel = a.handle_request(
            {"jsonrpc": "2.0", "method": "tasks/cancel", "params": {"id": task_id}, "id": "c1"},
            lambda t: "",
        )
        assert cancel["result"]["status"]["state"] == "canceled"

    def test_tasks_cancel_not_found(self):
        a = self._adapter()
        resp = a.handle_request(
            {"jsonrpc": "2.0", "method": "tasks/cancel", "params": {"id": "ghost"}, "id": "c2"},
            lambda t: "",
        )
        assert resp["error"]["code"] == _A2A_TASK_NOT_FOUND

    def test_unknown_method_error(self):
        a = self._adapter()
        resp = a.handle_request(
            {"jsonrpc": "2.0", "method": "tasks/subscribe", "params": {}, "id": "u1"},
            lambda t: "",
        )
        assert resp["error"]["code"] == _JSONRPC_METHOD_NOT_FOUND

    def test_payment_check_rejects_unverified(self):
        a = _make_adapter(gate=_no_proof_gate())
        resp = a.handle_request(
            self._send_body(),
            lambda t: "ok",
            headers={"X-Test": "1"},
        )
        assert resp["error"]["code"] == _A2A_PAYMENT_REQUIRED


# ═══════════════════════════════════════════════════════════════════════════════
# Group 9 — agent_card (5 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAgentCard:
    def test_name(self):
        a    = _make_adapter(agent_name="TestBot")
        card = a.agent_card("https://api1.ilovechicken.co.uk")
        assert card["name"] == "TestBot"

    def test_url(self):
        a    = _make_adapter()
        card = a.agent_card("https://api1.ilovechicken.co.uk")
        assert card["url"] == "https://api1.ilovechicken.co.uk"

    def test_capabilities_defaults(self):
        a    = _make_adapter()
        card = a.agent_card("https://api1.ilovechicken.co.uk")
        assert card["capabilities"]["streaming"]         is False
        assert card["capabilities"]["pushNotifications"] is False

    def test_capabilities_streaming_flag(self):
        a    = _make_adapter()
        card = a.agent_card("https://api1.ilovechicken.co.uk", supports_streaming=True)
        assert card["capabilities"]["streaming"] is True

    def test_skills_included_when_provided(self):
        a    = _make_adapter()
        skill = {"id": "kb", "name": "Knowledge Base", "description": "Premium KB"}
        card  = a.agent_card("https://api1.ilovechicken.co.uk", skills=[skill])
        assert card["skills"][0]["id"] == "kb"


# ═══════════════════════════════════════════════════════════════════════════════
# Group 10 — extended_agent_card (5 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestExtendedAgentCard:
    def test_has_authentication_key(self):
        a    = _make_adapter(protocol="mpp")
        card = a.extended_agent_card("https://api1.ilovechicken.co.uk")
        assert "authentication" in card

    def test_auth_scheme_matches_protocol(self):
        a    = _make_adapter(protocol="x402")
        card = a.extended_agent_card("https://api1.ilovechicken.co.uk")
        assert "X402" in card["authentication"]["schemes"]

    def test_has_endpoints_key(self):
        a    = _make_adapter()
        card = a.extended_agent_card("https://api1.ilovechicken.co.uk")
        assert "endpoints" in card

    def test_endpoints_contain_message_send(self):
        a    = _make_adapter()
        card = a.extended_agent_card("https://api1.ilovechicken.co.uk")
        assert "/message:send" in card["endpoints"]["messageSend"]

    def test_inherits_base_card_name(self):
        a    = _make_adapter(agent_name="PayBot")
        card = a.extended_agent_card("https://api1.ilovechicken.co.uk")
        assert card["name"] == "PayBot"


# ═══════════════════════════════════════════════════════════════════════════════
# Group 11 — list_tasks (3 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestListTasks:
    def test_empty_initially(self):
        a = _make_adapter()
        assert a.list_tasks() == []

    def test_tasks_added_after_handle_request(self):
        a = _make_adapter()
        a.handle_request(
            {"jsonrpc": "2.0", "method": "message/send",
             "params": {"message": {"parts": [{"type": "text", "text": "q"}]}}, "id": "1"},
            lambda t: "reply",
        )
        assert len(a.list_tasks()) == 1

    def test_returns_most_recent_first(self):
        a = _make_adapter()
        body = lambda t: {"jsonrpc": "2.0", "method": "message/send",
                          "params": {"message": {"parts": [{"type": "text", "text": t}]}}, "id": t}
        a.handle_request(body("first"), lambda t: "r1")
        a.handle_request(body("second"), lambda t: "r2")
        tasks = a.list_tasks()
        assert len(tasks) == 2
        # reversed — second task is first in the list
        assert tasks[0]["artifacts"][0]["parts"][0]["text"] == "r2"


# ═══════════════════════════════════════════════════════════════════════════════
# Group 12 — as_tool / AlgoVoiPaymentTool (8 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAsTool:
    def test_returns_payment_tool(self):
        a    = _make_adapter()
        tool = a.as_tool(lambda q: "result")
        assert isinstance(tool, AlgoVoiPaymentTool)

    def test_default_tool_name(self):
        a    = _make_adapter()
        tool = a.as_tool(lambda q: "result")
        assert tool.name == "algovoi_payment_gate"

    def test_custom_tool_name(self):
        a    = _make_adapter()
        tool = a.as_tool(lambda q: "result", tool_name="premium_kb")
        assert tool.name         == "premium_kb"
        assert tool.__name__     == "premium_kb"

    def test_tool_dunder_doc(self):
        a    = _make_adapter()
        desc = "Access premium knowledge base."
        tool = a.as_tool(lambda q: "result", tool_description=desc)
        assert tool.__doc__ == desc

    def test_tool_no_proof_returns_challenge_json(self):
        a    = _make_adapter(gate=_no_proof_gate())
        tool = a.as_tool(lambda q: "secret")
        out  = json.loads(tool(query="anything", payment_proof=""))
        assert out["error"] == "payment_required"

    def test_tool_with_proof_calls_resource_fn(self):
        a    = _make_adapter(gate=_ok_gate())
        tool = a.as_tool(lambda q: f"answer:{q}")
        out  = tool(query="test", payment_proof="valid-proof")
        assert out == "answer:test"

    def test_tool_resource_fn_exception(self):
        a = _make_adapter(gate=_ok_gate())
        def boom(q):
            raise RuntimeError("db offline")
        tool = a.as_tool(boom)
        out  = json.loads(tool(query="x", payment_proof="valid"))
        assert out["error"] == "resource_error"
        assert "db offline" in out["detail"]

    def test_tool_invalid_proof(self):
        a    = _make_adapter(gate=_no_proof_gate())
        tool = a.as_tool(lambda q: "secret")
        out  = json.loads(tool(query="q", payment_proof="bad-proof"))
        assert out["error"] == "payment_required"


# ═══════════════════════════════════════════════════════════════════════════════
# Group 13 — flask_guard (4 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlaskGuard:
    def _flask_app(self, adapter: AlgoVoiA2A):
        pytest.importorskip("flask")
        from flask import Flask
        app = Flask(__name__)

        @app.route("/a2a", methods=["POST"])
        def a2a():
            guard = adapter.flask_guard()
            if guard is not None:
                return guard
            return "OK", 200

        return app

    def test_guard_returns_402_without_payment(self):
        a    = _make_adapter(gate=_no_proof_gate())
        app  = self._flask_app(a)
        with app.test_client() as client:
            resp = client.post("/a2a", json={"message": {"parts": []}})
        assert resp.status_code == 402

    def test_guard_returns_200_with_payment(self):
        a    = _make_adapter(gate=_ok_gate())
        app  = self._flask_app(a)
        with app.test_client() as client:
            resp = client.post(
                "/a2a",
                json={"message": {"parts": []}},
                headers={"Authorization": "Payment valid"},
            )
        assert resp.status_code == 200

    def test_guard_large_body_capped(self):
        a    = _make_adapter(gate=_no_proof_gate())
        app  = self._flask_app(a)
        with app.test_client() as client:
            resp = client.post(
                "/a2a",
                data=b"x" * (2 * 1024 * 1024),
                content_type="application/json",
            )
        assert resp.status_code == 402

    def test_guard_invalid_json_body(self):
        a    = _make_adapter(gate=_no_proof_gate())
        app  = self._flask_app(a)
        with app.test_client() as client:
            resp = client.post("/a2a", data=b"not json", content_type="application/json")
        assert resp.status_code == 402


# ═══════════════════════════════════════════════════════════════════════════════
# Group 14 — flask_agent_card (3 tests) — public, no auth
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlaskAgentCard:
    def _flask_app(self, adapter: AlgoVoiA2A):
        pytest.importorskip("flask")
        from flask import Flask
        app = Flask(__name__)

        @app.route("/.well-known/agent.json")
        def agent_card():
            return adapter.flask_agent_card("https://api1.ilovechicken.co.uk")

        return app

    def test_returns_200(self):
        a   = _make_adapter(gate=_no_proof_gate())  # no auth needed
        app = self._flask_app(a)
        with app.test_client() as client:
            resp = client.get("/.well-known/agent.json")
        assert resp.status_code == 200

    def test_returns_agent_name(self):
        a   = _make_adapter(agent_name="AlgoVoi Gateway")
        app = self._flask_app(a)
        with app.test_client() as client:
            resp = client.get("/.well-known/agent.json")
        assert resp.get_json()["name"] == "AlgoVoi Gateway"

    def test_public_no_payment_required(self):
        """Agent card is public — gate is _no_proof_ but still returns 200."""
        a   = _make_adapter(gate=_no_proof_gate())
        app = self._flask_app(a)
        with app.test_client() as client:
            resp = client.get("/.well-known/agent.json")
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# Group 15 — flask_extended_agent_card (4 tests) — auth required
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlaskExtendedAgentCard:
    def _flask_app(self, adapter: AlgoVoiA2A):
        pytest.importorskip("flask")
        from flask import Flask
        app = Flask(__name__)

        @app.route("/extendedAgentCard")
        def extended_card():
            return adapter.flask_extended_agent_card("https://api1.ilovechicken.co.uk")

        return app

    def test_returns_402_without_payment(self):
        a   = _make_adapter(gate=_no_proof_gate())
        app = self._flask_app(a)
        with app.test_client() as client:
            resp = client.get("/extendedAgentCard")
        assert resp.status_code == 402

    def test_returns_200_with_payment(self):
        a   = _make_adapter(gate=_ok_gate())
        app = self._flask_app(a)
        with app.test_client() as client:
            resp = client.get("/extendedAgentCard")
        assert resp.status_code == 200

    def test_card_has_authentication(self):
        a   = _make_adapter(gate=_ok_gate())
        app = self._flask_app(a)
        with app.test_client() as client:
            resp = client.get("/extendedAgentCard")
        assert "authentication" in resp.get_json()

    def test_card_has_endpoints(self):
        a   = _make_adapter(gate=_ok_gate())
        app = self._flask_app(a)
        with app.test_client() as client:
            resp = client.get("/extendedAgentCard")
        assert "endpoints" in resp.get_json()


# ═══════════════════════════════════════════════════════════════════════════════
# Group 16 — flask_message_send (6 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlaskMessageSend:
    def _flask_app(self, adapter: AlgoVoiA2A, handler=None):
        pytest.importorskip("flask")
        from flask import Flask
        app = Flask(__name__)
        _handler = handler or (lambda text: f"echo:{text}")

        @app.route("/message:send", methods=["POST"])
        def message_send():
            return adapter.flask_message_send(_handler)

        return app

    def test_returns_402_without_payment(self):
        a   = _make_adapter(gate=_no_proof_gate())
        app = self._flask_app(a)
        with app.test_client() as client:
            resp = client.post("/message:send", json={"message": {"parts": [{"type": "text", "text": "hi"}]}})
        assert resp.status_code == 402

    def test_returns_200_with_payment(self):
        a   = _make_adapter(gate=_ok_gate())
        app = self._flask_app(a)
        with app.test_client() as client:
            resp = client.post(
                "/message:send",
                json={"message": {"parts": [{"type": "text", "text": "hi"}]}},
                headers={"Authorization": "Payment proof"},
            )
        assert resp.status_code == 200

    def test_response_has_task_id(self):
        a   = _make_adapter(gate=_ok_gate())
        app = self._flask_app(a)
        with app.test_client() as client:
            resp = client.post(
                "/message:send",
                json={"message": {"parts": [{"type": "text", "text": "hi"}]}},
                headers={"Authorization": "Payment proof"},
            )
        assert "id" in resp.get_json()

    def test_response_task_completed(self):
        a   = _make_adapter(gate=_ok_gate())
        app = self._flask_app(a)
        with app.test_client() as client:
            resp = client.post(
                "/message:send",
                json={"message": {"parts": [{"type": "text", "text": "hi"}]}},
                headers={"Authorization": "Payment proof"},
            )
        assert resp.get_json()["status"]["state"] == "completed"

    def test_invalid_json_returns_400(self):
        a   = _make_adapter(gate=_ok_gate())
        app = self._flask_app(a)
        with app.test_client() as client:
            resp = client.post(
                "/message:send",
                data=b"{{bad json",
                content_type="application/json",
            )
        assert resp.status_code == 400

    def test_handler_exception_returns_failed_task(self):
        def boom(t):
            raise RuntimeError("crash")
        a   = _make_adapter(gate=_ok_gate())
        app = self._flask_app(a, handler=boom)
        with app.test_client() as client:
            resp = client.post(
                "/message:send",
                json={"message": {"parts": [{"type": "text", "text": "hi"}]}},
                headers={"Authorization": "Payment proof"},
            )
        assert resp.get_json()["status"]["state"] == "failed"


# ═══════════════════════════════════════════════════════════════════════════════
# Group 17 — flask_list_tasks (4 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlaskListTasks:
    def _flask_app(self, adapter: AlgoVoiA2A):
        pytest.importorskip("flask")
        from flask import Flask
        app = Flask(__name__)

        @app.route("/tasks")
        def list_tasks():
            return adapter.flask_list_tasks()

        @app.route("/message:send", methods=["POST"])
        def message_send():
            return adapter.flask_message_send(lambda t: "reply")

        return app

    def test_returns_402_without_payment(self):
        a   = _make_adapter(gate=_no_proof_gate())
        app = self._flask_app(a)
        with app.test_client() as client:
            resp = client.get("/tasks")
        assert resp.status_code == 402

    def test_returns_200_with_payment(self):
        a   = _make_adapter(gate=_ok_gate())
        app = self._flask_app(a)
        with app.test_client() as client:
            resp = client.get("/tasks")
        assert resp.status_code == 200

    def test_returns_empty_list_initially(self):
        a   = _make_adapter(gate=_ok_gate())
        app = self._flask_app(a)
        with app.test_client() as client:
            resp = client.get("/tasks")
        assert resp.get_json()["tasks"] == []

    def test_returns_task_after_message_send(self):
        a   = _make_adapter(gate=_ok_gate())
        app = self._flask_app(a)
        with app.test_client() as client:
            client.post(
                "/message:send",
                json={"message": {"parts": [{"type": "text", "text": "hi"}]}},
                headers={"Authorization": "Payment proof"},
            )
            resp = client.get("/tasks")
        assert len(resp.get_json()["tasks"]) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Group 18 — flask_get_task (4 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlaskGetTask:
    def _flask_app(self, adapter: AlgoVoiA2A):
        pytest.importorskip("flask")
        from flask import Flask
        app = Flask(__name__)

        @app.route("/tasks/<task_id>")
        def get_task(task_id):
            return adapter.flask_get_task(task_id)

        @app.route("/message:send", methods=["POST"])
        def message_send():
            return adapter.flask_message_send(lambda t: "reply")

        return app

    def test_returns_402_without_payment(self):
        a   = _make_adapter(gate=_no_proof_gate())
        app = self._flask_app(a)
        with app.test_client() as client:
            resp = client.get("/tasks/some-id")
        assert resp.status_code == 402

    def test_returns_404_for_unknown_task(self):
        a   = _make_adapter(gate=_ok_gate())
        app = self._flask_app(a)
        with app.test_client() as client:
            resp = client.get("/tasks/no-such-task")
        assert resp.status_code == 404

    def test_returns_task_when_found(self):
        a   = _make_adapter(gate=_ok_gate())
        app = self._flask_app(a)
        with app.test_client() as client:
            send = client.post(
                "/message:send",
                json={"message": {"parts": [{"type": "text", "text": "hi"}]}},
                headers={"Authorization": "Payment proof"},
            )
            task_id = send.get_json()["id"]
            resp = client.get(f"/tasks/{task_id}")
        assert resp.status_code == 200
        assert resp.get_json()["id"] == task_id

    def test_task_state_completed(self):
        a   = _make_adapter(gate=_ok_gate())
        app = self._flask_app(a)
        with app.test_client() as client:
            send = client.post(
                "/message:send",
                json={"message": {"parts": [{"type": "text", "text": "hi"}]}},
                headers={"Authorization": "Payment proof"},
            )
            task_id = send.get_json()["id"]
            resp = client.get(f"/tasks/{task_id}")
        assert resp.get_json()["status"]["state"] == "completed"


# ═══════════════════════════════════════════════════════════════════════════════
# Group 19 — flask_cancel_task (5 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlaskCancelTask:
    def _flask_app(self, adapter: AlgoVoiA2A):
        pytest.importorskip("flask")
        from flask import Flask
        app = Flask(__name__)

        @app.route("/tasks/<task_id>:cancel", methods=["POST"])
        def cancel_task(task_id):
            return adapter.flask_cancel_task(task_id)

        @app.route("/message:send", methods=["POST"])
        def message_send():
            return adapter.flask_message_send(lambda t: "reply")

        return app

    def test_returns_402_without_payment(self):
        a   = _make_adapter(gate=_no_proof_gate())
        app = self._flask_app(a)
        with app.test_client() as client:
            resp = client.post("/tasks/some-id:cancel")
        assert resp.status_code == 402

    def test_returns_404_for_unknown_task(self):
        a   = _make_adapter(gate=_ok_gate())
        app = self._flask_app(a)
        with app.test_client() as client:
            resp = client.post("/tasks/no-such:cancel")
        assert resp.status_code == 404

    def test_cancels_task(self):
        a   = _make_adapter(gate=_ok_gate())
        app = self._flask_app(a)
        with app.test_client() as client:
            send = client.post(
                "/message:send",
                json={"message": {"parts": [{"type": "text", "text": "hi"}]}},
                headers={"Authorization": "Payment proof"},
            )
            task_id = send.get_json()["id"]
            resp = client.post(f"/tasks/{task_id}:cancel")
        assert resp.status_code == 200
        assert resp.get_json()["status"]["state"] == "canceled"

    def test_cancel_updates_task_in_store(self):
        a   = _make_adapter(gate=_ok_gate())
        app = self._flask_app(a)
        with app.test_client() as client:
            send = client.post(
                "/message:send",
                json={"message": {"parts": [{"type": "text", "text": "hi"}]}},
                headers={"Authorization": "Payment proof"},
            )
            task_id = send.get_json()["id"]
            client.post(f"/tasks/{task_id}:cancel")
        assert a._tasks[task_id]["status"]["state"] == "canceled"

    def test_cancel_response_has_timestamp(self):
        a   = _make_adapter(gate=_ok_gate())
        app = self._flask_app(a)
        with app.test_client() as client:
            send = client.post(
                "/message:send",
                json={"message": {"parts": [{"type": "text", "text": "hi"}]}},
                headers={"Authorization": "Payment proof"},
            )
            task_id = send.get_json()["id"]
            resp = client.post(f"/tasks/{task_id}:cancel")
        assert "timestamp" in resp.get_json()["status"]


# ═══════════════════════════════════════════════════════════════════════════════
# Group 20 — flask_agent legacy (6 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlaskAgent:
    def _flask_app(self, adapter: AlgoVoiA2A):
        pytest.importorskip("flask")
        from flask import Flask
        app = Flask(__name__)

        @app.route("/a2a", methods=["POST"])
        def a2a():
            return adapter.flask_agent(lambda text: f"echo:{text}")

        return app

    def test_no_payment_returns_402(self):
        a    = _make_adapter(gate=_no_proof_gate())
        app  = self._flask_app(a)
        with app.test_client() as client:
            resp = client.post(
                "/a2a",
                json={"jsonrpc": "2.0", "method": "message/send",
                      "params": {"message": {"parts": [{"type": "text", "text": "hi"}]}},
                      "id": "1"},
            )
        assert resp.status_code == 402

    def test_verified_message_send_200(self):
        a    = _make_adapter(gate=_ok_gate())
        app  = self._flask_app(a)
        with app.test_client() as client:
            resp = client.post(
                "/a2a",
                json={"jsonrpc": "2.0", "method": "message/send",
                      "params": {"message": {"parts": [{"type": "text", "text": "hello"}]}},
                      "id": "1"},
                headers={"Authorization": "Payment proof"},
            )
        assert resp.status_code == 200

    def test_verified_message_send_echo(self):
        a    = _make_adapter(gate=_ok_gate())
        app  = self._flask_app(a)
        with app.test_client() as client:
            resp = client.post(
                "/a2a",
                json={"jsonrpc": "2.0", "method": "message/send",
                      "params": {"message": {"parts": [{"type": "text", "text": "world"}]}},
                      "id": "1"},
                headers={"Authorization": "Payment proof"},
            )
        data = resp.get_json()
        assert "echo:world" in data["result"]["artifacts"][0]["parts"][0]["text"]

    def test_invalid_json_returns_400(self):
        a    = _make_adapter(gate=_ok_gate())
        app  = self._flask_app(a)
        with app.test_client() as client:
            resp = client.post(
                "/a2a",
                data=b"{{bad json",
                content_type="application/json",
            )
        assert resp.status_code == 400

    def test_parse_error_body_has_code(self):
        a    = _make_adapter(gate=_ok_gate())
        app  = self._flask_app(a)
        with app.test_client() as client:
            resp = client.post(
                "/a2a",
                data=b"{{bad json",
                content_type="application/json",
            )
        data = json.loads(resp.data)
        assert data["error"]["code"] == _JSONRPC_PARSE_ERROR

    def test_tasks_get_via_flask_agent(self):
        a   = _make_adapter(gate=_ok_gate())
        app = self._flask_app(a)
        with app.test_client() as client:
            send = client.post(
                "/a2a",
                json={"jsonrpc": "2.0", "method": "message/send",
                      "params": {"message": {"parts": [{"type": "text", "text": "q"}]}},
                      "id": "s1"},
                headers={"Authorization": "Payment proof"},
            )
            task_id = send.get_json()["result"]["id"]
            get = client.post(
                "/a2a",
                json={"jsonrpc": "2.0", "method": "tasks/get",
                      "params": {"id": task_id}, "id": "g1"},
                headers={"Authorization": "Payment proof"},
            )
        assert get.status_code == 200
        assert get.get_json()["result"]["id"] == task_id
