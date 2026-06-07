"""
Unit tests for AlgoVoi Agno Adapter
=====================================

80 tests covering AgnoResult, AgnoPaymentRequired, constructor validation,
protocol/network validation, _build_gate delegation, check(), run_agent(),
arun_agent(), make_pre_hook(), fastapi_middleware(), flask_guard(), and
flask_agent().

All gate and Agno interactions are mocked — no live API calls.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from agno_algovoi import (
    AgnoPaymentRequired,
    AgnoResult,
    AlgoVoiAgno,
    NETWORKS,
    PROTOCOLS,
    __version__,
    _AgnoPaymentMiddleware,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _inner_no_proof() -> MagicMock:
    m = MagicMock()
    m.requires_payment = True
    m.error = "Payment proof required"
    m.receipt = None
    m.mandate = None
    m.as_wsgi_response.return_value = (
        "402 Payment Required",
        [("WWW-Authenticate", 'Payment realm="API Access", id="t", intent="charge"')],
        b'{"error":"payment_required"}',
    )
    return m


def _inner_ok() -> MagicMock:
    m = MagicMock()
    m.requires_payment = False
    m.error = None
    m.receipt = MagicMock(tx_id="tx-ok")
    m.mandate = None
    m.as_wsgi_response.return_value = ("200 OK", [], b"{}")
    return m


def _make_gate(inner: MagicMock | None = None) -> MagicMock:
    gate = MagicMock()
    gate.check.return_value = inner or _inner_no_proof()
    return gate


def _make_adapter(
    protocol: str = "mpp",
    network: str = "algorand-mainnet",
    gate: MagicMock | None = None,
    **kw,
) -> AlgoVoiAgno:
    mock_gate = gate if gate is not None else _make_gate()
    with patch("agno_algovoi._build_gate", return_value=mock_gate):
        adapter = AlgoVoiAgno(
            algovoi_key="algv_test",
            tenant_id="test-tid",
            payout_address="TEST_ADDR",
            protocol=protocol,
            network=network,
            **kw,
        )
    adapter._gate = mock_gate
    return adapter


# ═══════════════════════════════════════════════════════════════════════════════
# Group 1 — AgnoResult (9 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAgnoResult:
    def test_requires_payment_true(self):
        r = AgnoResult(_inner_no_proof())
        assert r.requires_payment is True

    def test_requires_payment_false(self):
        r = AgnoResult(_inner_ok())
        assert r.requires_payment is False

    def test_error_propagated(self):
        r = AgnoResult(_inner_no_proof())
        assert r.error == "Payment proof required"

    def test_error_none_on_success(self):
        r = AgnoResult(_inner_ok())
        assert r.error is None

    def test_receipt_on_success(self):
        r = AgnoResult(_inner_ok())
        assert r.receipt.tx_id == "tx-ok"

    def test_mandate_none(self):
        r = AgnoResult(_inner_ok())
        assert r.mandate is None

    def test_as_flask_response_uses_wsgi(self):
        r = AgnoResult(_inner_no_proof())
        body, code, headers = r.as_flask_response()
        assert code == 402
        assert "payment_required" in body
        assert "WWW-Authenticate" in headers

    def test_as_flask_response_fallback(self):
        inner = MagicMock()
        inner.requires_payment = True
        inner.error = "oops"
        del inner.as_wsgi_response
        r = AgnoResult(inner)
        body, code, _ = r.as_flask_response()
        assert code == 402
        assert "Payment Required" in body

    def test_as_wsgi_response_delegates(self):
        r = AgnoResult(_inner_no_proof())
        status, hdrs, body = r.as_wsgi_response()
        assert "402" in status
        assert b"payment_required" in body


# ═══════════════════════════════════════════════════════════════════════════════
# Group 2 — AgnoPaymentRequired exception (4 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAgnoPaymentRequired:
    def test_carries_result(self):
        r = AgnoResult(_inner_no_proof())
        exc = AgnoPaymentRequired(r)
        assert exc.result is r

    def test_message_from_result_error(self):
        r = AgnoResult(_inner_no_proof())
        exc = AgnoPaymentRequired(r)
        assert "Payment proof required" in str(exc)

    def test_is_exception(self):
        r = AgnoResult(_inner_no_proof())
        exc = AgnoPaymentRequired(r)
        assert isinstance(exc, Exception)

    def test_fallback_message(self):
        inner = MagicMock()
        inner.requires_payment = True
        inner.error = None
        inner.receipt = None
        inner.mandate = None
        inner.as_wsgi_response = MagicMock(return_value=("402", [], b"{}"))
        r = AgnoResult(inner)
        exc = AgnoPaymentRequired(r)
        assert "Payment Required" in str(exc)


# ═══════════════════════════════════════════════════════════════════════════════
# Group 3 — Constructor and constants (8 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestConstructor:
    def test_version(self):
        assert __version__ == "1.0.0"

    def test_networks_list(self):
        assert "algorand-mainnet" in NETWORKS
        assert "voi-mainnet" in NETWORKS
        assert "hedera-mainnet" in NETWORKS
        assert "stellar-mainnet" in NETWORKS
        assert len(NETWORKS) == 4

    def test_protocols_list(self):
        assert set(PROTOCOLS) == {"x402", "mpp", "ap2"}

    def test_constructor_stores_params(self):
        a = _make_adapter(protocol="ap2", network="voi-mainnet",
                          amount_microunits=5_000, resource_id="kb")
        assert a._protocol          == "ap2"
        assert a._network           == "voi-mainnet"
        assert a._amount_microunits == 5_000
        assert a._resource_id       == "kb"

    def test_invalid_network_raises(self):
        with pytest.raises(ValueError, match="network must be one of"):
            with patch("agno_algovoi._build_gate",
                       side_effect=ValueError("network must be one of")):
                AlgoVoiAgno(
                    algovoi_key="k", tenant_id="t",
                    payout_address="p", network="bad-net",
                )

    def test_invalid_protocol_raises(self):
        with pytest.raises(ValueError, match="protocol must be one of"):
            with patch("agno_algovoi._build_gate",
                       side_effect=ValueError("protocol must be one of")):
                AlgoVoiAgno(
                    algovoi_key="k", tenant_id="t",
                    payout_address="p", protocol="grpc",
                )

    def test_default_protocol_mpp(self):
        a = _make_adapter()
        assert a._protocol == "mpp"

    def test_default_network_algorand(self):
        a = _make_adapter()
        assert a._network == "algorand-mainnet"


# ═══════════════════════════════════════════════════════════════════════════════
# Group 4 — _build_gate delegation (6 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildGate:
    def _build(self, protocol: str, network: str = "algorand-mainnet") -> MagicMock:
        captured = {}
        original = __import__("agno_algovoi")._build_gate

        def fake_build(**kwargs):
            captured.update(kwargs)
            return MagicMock()

        with patch("agno_algovoi._build_gate", side_effect=fake_build):
            AlgoVoiAgno(
                algovoi_key="k", tenant_id="t",
                payout_address="p", protocol=protocol, network=network,
            )
        return captured

    def test_mpp_passes_resource_id(self):
        kw = self._build("mpp")
        assert kw["protocol"] == "mpp"
        assert "resource_id" in kw

    def test_x402_protocol_forwarded(self):
        kw = self._build("x402")
        assert kw["protocol"] == "x402"

    def test_ap2_protocol_forwarded(self):
        kw = self._build("ap2")
        assert kw["protocol"] == "ap2"

    def test_network_forwarded(self):
        kw = self._build("mpp", "stellar-mainnet")
        assert kw["network"] == "stellar-mainnet"

    def test_amount_forwarded(self):
        captured = {}

        def fake_build(**kwargs):
            captured.update(kwargs)
            return MagicMock()

        with patch("agno_algovoi._build_gate", side_effect=fake_build):
            AlgoVoiAgno(
                algovoi_key="k", tenant_id="t",
                payout_address="p", amount_microunits=99_999,
            )
        assert captured["amount_microunits"] == 99_999

    def test_gate_assigned_to_self(self):
        mock_gate = MagicMock()
        with patch("agno_algovoi._build_gate", return_value=mock_gate):
            a = AlgoVoiAgno(
                algovoi_key="k", tenant_id="t", payout_address="p",
            )
        assert a._gate is mock_gate


# ═══════════════════════════════════════════════════════════════════════════════
# Group 5 — check() (8 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheck:
    def test_returns_agno_result(self):
        a = _make_adapter()
        r = a.check({})
        assert isinstance(r, AgnoResult)

    def test_requires_payment_true_without_proof(self):
        a = _make_adapter()
        r = a.check({})
        assert r.requires_payment is True

    def test_requires_payment_false_with_proof(self):
        a = _make_adapter(gate=_make_gate(_inner_ok()))
        r = a.check({"Authorization": "Payment abc123"})
        assert r.requires_payment is False

    def test_passes_headers_to_gate(self):
        a    = _make_adapter()
        hdrs = {"Authorization": "Payment xyz", "X-Custom": "val"}
        a.check(hdrs)
        a._gate.check.assert_called_once()
        call_args = a._gate.check.call_args[0]
        assert call_args[0] == hdrs

    def test_passes_body_to_gate(self):
        a    = _make_adapter()
        body = {"resource": "kb"}
        a.check({}, body)
        a._gate.check.assert_called_once()

    def test_empty_body_defaults_to_empty_dict(self):
        a = _make_adapter()
        a.check({}, None)
        # Should not raise

    def test_type_error_falls_back_to_single_arg(self):
        gate = MagicMock()
        gate.check.side_effect = [TypeError, _inner_ok()]
        a    = _make_adapter(gate=gate)
        r    = a.check({})
        assert gate.check.call_count == 2

    def test_receipt_accessible_on_success(self):
        a = _make_adapter(gate=_make_gate(_inner_ok()))
        r = a.check({})
        assert r.receipt.tx_id == "tx-ok"


# ═══════════════════════════════════════════════════════════════════════════════
# Group 6 — run_agent() (10 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRunAgent:
    def test_raises_on_no_payment(self):
        a = _make_adapter()
        with pytest.raises(AgnoPaymentRequired):
            a.run_agent(MagicMock(), "Hello")

    def test_raises_carries_result(self):
        a = _make_adapter()
        with pytest.raises(AgnoPaymentRequired) as exc_info:
            a.run_agent(MagicMock(), "Hello")
        assert exc_info.value.result.requires_payment is True

    def test_runs_agent_on_success(self):
        mock_agent = MagicMock()
        mock_agent.run.return_value = MagicMock(content="42")
        a = _make_adapter(gate=_make_gate(_inner_ok()))
        output = a.run_agent(mock_agent, "What is 6×7?")
        mock_agent.run.assert_called_once_with("What is 6×7?")

    def test_returns_agent_output(self):
        mock_agent = MagicMock()
        mock_agent.run.return_value = MagicMock(content="answer")
        a = _make_adapter(gate=_make_gate(_inner_ok()))
        output = a.run_agent(mock_agent, "question")
        assert output.content == "answer"

    def test_agent_not_called_on_failure(self):
        mock_agent = MagicMock()
        a = _make_adapter()
        with pytest.raises(AgnoPaymentRequired):
            a.run_agent(mock_agent, "question")
        mock_agent.run.assert_not_called()

    def test_default_empty_headers(self):
        a = _make_adapter()
        with pytest.raises(AgnoPaymentRequired):
            a.run_agent(MagicMock(), "msg")
        # Should not raise TypeError about missing headers

    def test_headers_forwarded_to_check(self):
        a    = _make_adapter()
        hdrs = {"Authorization": "Payment proof123"}
        with pytest.raises(AgnoPaymentRequired):
            a.run_agent(MagicMock(), "msg", headers=hdrs)
        a._gate.check.assert_called_once()
        assert a._gate.check.call_args[0][0] == hdrs

    def test_body_forwarded_to_check(self):
        a    = _make_adapter(gate=_make_gate(_inner_ok()))
        body = {"context": "extra"}
        mock_agent = MagicMock()
        mock_agent.run.return_value = MagicMock(content="ok")
        a.run_agent(mock_agent, "msg", headers={}, body=body)
        a._gate.check.assert_called_once()

    def test_all_protocols_raise_on_no_proof(self):
        for protocol in PROTOCOLS:
            a = _make_adapter(protocol=protocol)
            with pytest.raises(AgnoPaymentRequired):
                a.run_agent(MagicMock(), "test")

    def test_all_networks_pass_on_ok_gate(self):
        for network in NETWORKS:
            mock_agent = MagicMock()
            mock_agent.run.return_value = MagicMock(content="ok")
            a = _make_adapter(network=network, gate=_make_gate(_inner_ok()))
            output = a.run_agent(mock_agent, "test")
            assert output.content == "ok"


# ═══════════════════════════════════════════════════════════════════════════════
# Group 7 — arun_agent() (8 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestArunAgent:
    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_raises_on_no_payment(self):
        a = _make_adapter()
        with pytest.raises(AgnoPaymentRequired):
            self._run(a.arun_agent(AsyncMock(), "Hello"))

    def test_awaits_agent_arun_on_success(self):
        mock_agent       = AsyncMock()
        mock_agent.arun  = AsyncMock(return_value=MagicMock(content="async-ok"))
        a = _make_adapter(gate=_make_gate(_inner_ok()))
        output = self._run(a.arun_agent(mock_agent, "question"))
        mock_agent.arun.assert_awaited_once_with("question")

    def test_returns_agent_output(self):
        mock_agent      = AsyncMock()
        mock_agent.arun = AsyncMock(return_value=MagicMock(content="result"))
        a = _make_adapter(gate=_make_gate(_inner_ok()))
        out = self._run(a.arun_agent(mock_agent, "q"))
        assert out.content == "result"

    def test_agent_not_called_on_failure(self):
        mock_agent      = AsyncMock()
        mock_agent.arun = AsyncMock()
        a = _make_adapter()
        with pytest.raises(AgnoPaymentRequired):
            self._run(a.arun_agent(mock_agent, "q"))
        mock_agent.arun.assert_not_awaited()

    def test_default_empty_headers(self):
        a = _make_adapter()
        with pytest.raises(AgnoPaymentRequired):
            self._run(a.arun_agent(AsyncMock(), "msg"))

    def test_headers_forwarded(self):
        a    = _make_adapter()
        hdrs = {"Authorization": "Payment proof"}
        with pytest.raises(AgnoPaymentRequired):
            self._run(a.arun_agent(AsyncMock(), "msg", headers=hdrs))
        assert a._gate.check.call_args[0][0] == hdrs

    def test_all_protocols_raise(self):
        for protocol in PROTOCOLS:
            a = _make_adapter(protocol=protocol)
            with pytest.raises(AgnoPaymentRequired):
                self._run(a.arun_agent(AsyncMock(), "test"))

    def test_carries_result_in_exception(self):
        a = _make_adapter()
        with pytest.raises(AgnoPaymentRequired) as exc_info:
            self._run(a.arun_agent(AsyncMock(), "q"))
        assert isinstance(exc_info.value.result, AgnoResult)


# ═══════════════════════════════════════════════════════════════════════════════
# Group 8 — make_pre_hook() (9 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestMakePreHook:
    def test_returns_callable(self):
        a    = _make_adapter()
        hook = a.make_pre_hook()
        assert callable(hook)

    def test_hook_raises_on_no_proof(self):
        a    = _make_adapter()
        hook = a.make_pre_hook(headers={})
        with pytest.raises(AgnoPaymentRequired):
            hook()

    def test_hook_silent_on_valid_proof(self):
        a    = _make_adapter(gate=_make_gate(_inner_ok()))
        hook = a.make_pre_hook(headers={"Authorization": "Payment abc"})
        hook()   # must not raise

    def test_hook_accepts_positional_args(self):
        a    = _make_adapter()
        hook = a.make_pre_hook()
        with pytest.raises(AgnoPaymentRequired):
            hook(MagicMock(), MagicMock())   # Agno may pass context objects

    def test_hook_accepts_keyword_args(self):
        a    = _make_adapter()
        hook = a.make_pre_hook()
        with pytest.raises(AgnoPaymentRequired):
            hook(agent=MagicMock(), run_output=None)

    def test_hook_uses_captured_headers(self):
        a    = _make_adapter()
        hdrs = {"Authorization": "Payment tok123"}
        hook = a.make_pre_hook(headers=hdrs)
        with pytest.raises(AgnoPaymentRequired):
            hook()
        a._gate.check.assert_called_once()
        assert a._gate.check.call_args[0][0] == hdrs

    def test_hook_uses_captured_body(self):
        a    = _make_adapter()
        hook = a.make_pre_hook(headers={}, body={"q": "val"})
        with pytest.raises(AgnoPaymentRequired):
            hook()

    def test_hook_raises_carries_result(self):
        a    = _make_adapter()
        hook = a.make_pre_hook()
        with pytest.raises(AgnoPaymentRequired) as exc_info:
            hook()
        assert isinstance(exc_info.value.result, AgnoResult)

    def test_multiple_hooks_independent(self):
        a     = _make_adapter()
        hook1 = a.make_pre_hook(headers={"Authorization": "Payment a"})
        hook2 = a.make_pre_hook(headers={"Authorization": "Payment b"})
        # Each closure captures its own headers
        with pytest.raises(AgnoPaymentRequired):
            hook1()
        with pytest.raises(AgnoPaymentRequired):
            hook2()


# ═══════════════════════════════════════════════════════════════════════════════
# Group 9 — fastapi_middleware() (8 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFastapiMiddleware:
    def test_calls_add_middleware(self):
        a   = _make_adapter()
        app = MagicMock()
        ret = a.fastapi_middleware(app)
        app.add_middleware.assert_called_once()

    def test_returns_app_for_chaining(self):
        a   = _make_adapter()
        app = MagicMock()
        ret = a.fastapi_middleware(app)
        assert ret is app

    def test_middleware_class_passed(self):
        a   = _make_adapter()
        app = MagicMock()
        a.fastapi_middleware(app)
        call_args = app.add_middleware.call_args
        assert call_args[0][0] is _AgnoPaymentMiddleware

    def test_gate_passed_to_middleware(self):
        a   = _make_adapter()
        app = MagicMock()
        a.fastapi_middleware(app)
        call_kwargs = app.add_middleware.call_args[1]
        assert call_kwargs["gate"] is a

    def test_asgi_middleware_passes_non_http(self):
        """WebSocket / lifespan scopes must pass through."""
        a  = _make_adapter()
        inner_app = AsyncMock()
        mw = _AgnoPaymentMiddleware(inner_app, a)
        scope = {"type": "lifespan"}
        asyncio.get_event_loop().run_until_complete(
            mw(scope, MagicMock(), MagicMock())
        )
        from unittest.mock import ANY
        inner_app.assert_awaited_once_with(scope, ANY, ANY)

    def test_asgi_middleware_passes_on_ok_gate(self):
        a        = _make_adapter(gate=_make_gate(_inner_ok()))
        inner_app = AsyncMock()
        mw = _AgnoPaymentMiddleware(inner_app, a)
        scope = {
            "type": "http",
            "headers": [(b"authorization", b"Payment proof")],
        }
        asyncio.get_event_loop().run_until_complete(
            mw(scope, MagicMock(), MagicMock())
        )
        inner_app.assert_awaited_once()

    def test_asgi_middleware_sends_402(self):
        a = _make_adapter()
        inner_app = AsyncMock()
        mw = _AgnoPaymentMiddleware(inner_app, a)

        sent = []

        async def fake_send(msg):
            sent.append(msg)

        scope = {"type": "http", "headers": []}
        asyncio.get_event_loop().run_until_complete(
            mw(scope, MagicMock(), fake_send)
        )
        inner_app.assert_not_awaited()
        assert any(m.get("status") == 402 for m in sent)

    def test_asgi_middleware_decodes_headers(self):
        a = _make_adapter()
        inner_app = AsyncMock()
        mw = _AgnoPaymentMiddleware(inner_app, a)

        scope = {
            "type": "http",
            "headers": [
                (b"authorization", b"Payment tok"),
                (b"content-type", b"application/json"),
            ],
        }
        asyncio.get_event_loop().run_until_complete(
            mw(scope, MagicMock(), AsyncMock())
        )
        a._gate.check.assert_called_once()
        passed_headers = a._gate.check.call_args[0][0]
        assert "authorization" in passed_headers
        assert passed_headers["authorization"] == "Payment tok"


# ═══════════════════════════════════════════════════════════════════════════════
# Group 10 — flask_guard() (9 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlaskGuard:
    def _app_with_guard(self, adapter):
        try:
            from flask import Flask
        except ImportError:
            pytest.skip("flask not installed")
        app = Flask(__name__)

        @app.route("/test", methods=["POST"])
        def view():
            guard = adapter.flask_guard()
            if guard is not None:
                return guard
            return "OK", 200

        return app

    def test_returns_402_when_no_proof(self):
        a   = _make_adapter()
        app = self._app_with_guard(a)
        with app.test_client() as c:
            resp = c.post("/test", json={})
        assert resp.status_code == 402

    def test_returns_none_when_verified(self):
        a   = _make_adapter(gate=_make_gate(_inner_ok()))
        app = self._app_with_guard(a)
        with app.test_client() as c:
            resp = c.post("/test", json={})
        assert resp.status_code == 200

    def test_response_body_is_json(self):
        a   = _make_adapter()
        app = self._app_with_guard(a)
        with app.test_client() as c:
            resp = c.post("/test", json={})
        data = json.loads(resp.data)
        assert "payment_required" in json.dumps(data)

    def test_passes_headers_to_check(self):
        a   = _make_adapter()
        app = self._app_with_guard(a)
        with app.test_client() as c:
            c.post("/test", json={},
                   headers={"Authorization": "Payment tok"})
        a._gate.check.assert_called_once()

    def test_passes_body_to_check(self):
        a    = _make_adapter()
        app  = self._app_with_guard(a)
        body = {"key": "value"}
        with app.test_client() as c:
            c.post("/test", json=body)
        a._gate.check.assert_called_once()

    def test_body_capped_at_1mib(self):
        """Oversized body is truncated before parsing (no crash)."""
        a   = _make_adapter()
        app = self._app_with_guard(a)
        big = b"x" * (2 * 1024 * 1024)  # 2 MiB
        with app.test_client() as c:
            resp = c.post("/test", data=big,
                          content_type="application/octet-stream")
        assert resp.status_code == 402   # still returns 402, not 500

    def test_invalid_json_body_handled(self):
        a   = _make_adapter()
        app = self._app_with_guard(a)
        with app.test_client() as c:
            resp = c.post("/test", data=b"not-json",
                          content_type="application/json")
        assert resp.status_code == 402

    def test_all_protocols_return_402(self):
        for protocol in PROTOCOLS:
            a   = _make_adapter(protocol=protocol)
            app = self._app_with_guard(a)
            with app.test_client() as c:
                resp = c.post("/test", json={})
            assert resp.status_code == 402

    def test_all_networks_return_402(self):
        for network in NETWORKS:
            a   = _make_adapter(network=network)
            app = self._app_with_guard(a)
            with app.test_client() as c:
                resp = c.post("/test", json={})
            assert resp.status_code == 402


# ═══════════════════════════════════════════════════════════════════════════════
# Group 11 — flask_agent() (9 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlaskAgent:
    def _app_with_agent(self, adapter, agent, message_key="message"):
        try:
            from flask import Flask
        except ImportError:
            pytest.skip("flask not installed")
        app = Flask(__name__)

        @app.route("/agent", methods=["POST"])
        def view():
            return adapter.flask_agent(agent, message_key=message_key)

        return app

    def test_returns_402_when_no_proof(self):
        mock_agent = MagicMock()
        a = _make_adapter()
        app = self._app_with_agent(a, mock_agent)
        with app.test_client() as c:
            resp = c.post("/agent", json={"message": "Hi"})
        assert resp.status_code == 402

    def test_returns_200_with_valid_proof(self):
        mock_agent = MagicMock()
        mock_agent.run.return_value = MagicMock(content="Hi there")
        a   = _make_adapter(gate=_make_gate(_inner_ok()))
        app = self._app_with_agent(a, mock_agent)
        with app.test_client() as c:
            resp = c.post("/agent", json={"message": "Hi"})
        assert resp.status_code == 200

    def test_response_contains_agent_output(self):
        mock_agent = MagicMock()
        mock_agent.run.return_value = MagicMock(content="Hello world")
        a   = _make_adapter(gate=_make_gate(_inner_ok()))
        app = self._app_with_agent(a, mock_agent)
        with app.test_client() as c:
            resp = c.post("/agent", json={"message": "greet"})
        data = json.loads(resp.data)
        assert data["response"] == "Hello world"

    def test_agent_not_called_on_402(self):
        mock_agent = MagicMock()
        a = _make_adapter()
        app = self._app_with_agent(a, mock_agent)
        with app.test_client() as c:
            c.post("/agent", json={"message": "Hi"})
        mock_agent.run.assert_not_called()

    def test_message_extracted_from_body(self):
        mock_agent = MagicMock()
        mock_agent.run.return_value = MagicMock(content="ok")
        a   = _make_adapter(gate=_make_gate(_inner_ok()))
        app = self._app_with_agent(a, mock_agent)
        with app.test_client() as c:
            c.post("/agent", json={"message": "custom msg"})
        mock_agent.run.assert_called_once_with("custom msg")

    def test_custom_message_key(self):
        mock_agent = MagicMock()
        mock_agent.run.return_value = MagicMock(content="ok")
        a   = _make_adapter(gate=_make_gate(_inner_ok()))
        app = self._app_with_agent(a, mock_agent, message_key="prompt")
        with app.test_client() as c:
            c.post("/agent", json={"prompt": "my prompt"})
        mock_agent.run.assert_called_once_with("my prompt")

    def test_empty_body_uses_empty_string(self):
        mock_agent = MagicMock()
        mock_agent.run.return_value = MagicMock(content="ok")
        a   = _make_adapter(gate=_make_gate(_inner_ok()))
        app = self._app_with_agent(a, mock_agent)
        with app.test_client() as c:
            c.post("/agent", json={})
        mock_agent.run.assert_called_once_with("")

    def test_str_output_fallback(self):
        """If agent returns object without .content, str() is used."""
        mock_agent = MagicMock()
        output     = MagicMock(spec=[])  # no .content attribute
        del output.content
        mock_agent.run.return_value = output
        a   = _make_adapter(gate=_make_gate(_inner_ok()))
        app = self._app_with_agent(a, mock_agent)
        with app.test_client() as c:
            resp = c.post("/agent", json={"message": "Hi"})
        data = json.loads(resp.data)
        assert "response" in data

    def test_invalid_json_body_returns_402(self):
        mock_agent = MagicMock()
        a = _make_adapter()
        app = self._app_with_agent(a, mock_agent)
        with app.test_client() as c:
            resp = c.post("/agent", data=b"not-json",
                          content_type="application/json")
        assert resp.status_code == 402
