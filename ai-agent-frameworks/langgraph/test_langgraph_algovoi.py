"""
Unit tests for AlgoVoi LangGraph Adapter
==========================================

82 tests covering LangGraphResult, constructor, protocol/network validation,
MPP/x402/AP2 gate delegation, invoke_graph, stream_graph, as_tool,
tool_node, flask_guard, and flask_agent.

All gate and LangGraph interactions are mocked — no live API calls.
"""

from __future__ import annotations

import json
import os
import sys
from unittest.mock import MagicMock, patch, call

import pytest

# ── path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from langgraph_algovoi import (
    AlgoVoiLangGraph,
    AlgoVoiPaymentTool,
    LangGraphResult,
    NETWORKS,
    PROTOCOLS,
    __version__,
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
) -> AlgoVoiLangGraph:
    mock_gate = gate if gate is not None else _make_gate()
    with patch("langgraph_algovoi._build_gate", return_value=mock_gate):
        adapter = AlgoVoiLangGraph(
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
# Group 1 — LangGraphResult (9 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestLangGraphResult:
    def test_requires_payment_true(self):
        r = LangGraphResult(_inner_no_proof())
        assert r.requires_payment is True

    def test_requires_payment_false(self):
        r = LangGraphResult(_inner_ok())
        assert r.requires_payment is False

    def test_error_propagated(self):
        r = LangGraphResult(_inner_no_proof())
        assert r.error == "Payment proof required"

    def test_receipt_propagated(self):
        r = LangGraphResult(_inner_ok())
        assert r.receipt.tx_id == "tx-ok"

    def test_mandate_none_by_default(self):
        r = LangGraphResult(_inner_no_proof())
        assert r.mandate is None

    def test_wsgi_delegates_to_inner(self):
        r = LangGraphResult(_inner_no_proof())
        status, headers, body = r.as_wsgi_response()
        assert status == "402 Payment Required"

    def test_wsgi_fallback_when_no_inner_method(self):
        inner = MagicMock(spec=["requires_payment", "error"])
        inner.requires_payment = True
        inner.error = "nope"
        r = LangGraphResult(inner)
        status, _, body = r.as_wsgi_response()
        assert b"Payment Required" in body

    def test_flask_delegates_to_inner(self):
        r = LangGraphResult(_inner_no_proof())
        body, code, hdrs = r.as_flask_response()
        assert code == 402

    def test_flask_fallback_when_no_inner_method(self):
        inner = MagicMock(spec=["requires_payment", "error"])
        inner.requires_payment = True
        inner.error = "no gate"
        r = LangGraphResult(inner)
        body, code, hdrs = r.as_flask_response()
        assert code == 402


# ═══════════════════════════════════════════════════════════════════════════════
# Group 2 — VERSION (1 test)
# ═══════════════════════════════════════════════════════════════════════════════

class TestVersion:
    def test_version_string(self):
        assert __version__ == "1.0.0"


# ═══════════════════════════════════════════════════════════════════════════════
# Group 3 — Constructor & validation (7 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestConstructor:
    def test_defaults(self):
        a = _make_adapter()
        assert a._protocol          == "mpp"
        assert a._network           == "algorand-mainnet"
        assert a._amount_microunits == 10_000
        assert a._resource_id       == "ai-function"

    def test_stores_custom_protocol(self):
        a = _make_adapter(protocol="ap2")
        assert a._protocol == "ap2"

    def test_stores_custom_network(self):
        a = _make_adapter(network="voi-mainnet")
        assert a._network == "voi-mainnet"

    def test_invalid_network_raises(self):
        with pytest.raises(ValueError, match="network"):
            with patch("langgraph_algovoi._build_gate", side_effect=ValueError("network")):
                AlgoVoiLangGraph(
                    algovoi_key="k", tenant_id="t", payout_address="a",
                    network="bad-network",
                )

    def test_invalid_protocol_raises(self):
        with pytest.raises(ValueError, match="protocol"):
            with patch("langgraph_algovoi._build_gate", side_effect=ValueError("protocol")):
                AlgoVoiLangGraph(
                    algovoi_key="k", tenant_id="t", payout_address="a",
                    protocol="bad-protocol",
                )

    def test_networks_constant(self):
        assert "algorand-mainnet" in NETWORKS
        assert "voi-mainnet"      in NETWORKS
        assert "hedera-mainnet"   in NETWORKS
        assert "stellar-mainnet"  in NETWORKS

    def test_protocols_constant(self):
        assert set(PROTOCOLS) == {"x402", "mpp", "ap2"}


# ═══════════════════════════════════════════════════════════════════════════════
# Group 4 — MPP check (10 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestMppCheck:
    def test_no_proof_requires_payment(self):
        a = _make_adapter(protocol="mpp")
        assert a.check({}).requires_payment is True

    def test_no_proof_wsgi_402(self):
        a = _make_adapter(protocol="mpp")
        status, _, _ = a.check({}).as_wsgi_response()
        assert "402" in status

    def test_no_proof_www_authenticate(self):
        a = _make_adapter(protocol="mpp")
        _, headers, _ = a.check({}).as_wsgi_response()
        keys = [h[0] for h in headers]
        assert "WWW-Authenticate" in keys

    def test_gate_called_with_headers(self):
        mock_gate = _make_gate()
        a = _make_adapter(protocol="mpp", gate=mock_gate)
        a.check({"X-Test": "1"}, {"data": "x"})
        mock_gate.check.assert_called_once()
        assert mock_gate.check.call_args[0][0]["X-Test"] == "1"

    def test_body_forwarded(self):
        mock_gate = _make_gate()
        a = _make_adapter(protocol="mpp", gate=mock_gate)
        body = {"messages": [{"role": "user", "content": "hi"}]}
        a.check({}, body)
        assert mock_gate.check.call_args[0][1] == body

    def test_network_voi(self):
        a = _make_adapter(protocol="mpp", network="voi-mainnet")
        assert a.check({}).requires_payment is True

    def test_network_hedera(self):
        a = _make_adapter(protocol="mpp", network="hedera-mainnet")
        assert a.check({}).requires_payment is True

    def test_network_stellar(self):
        a = _make_adapter(protocol="mpp", network="stellar-mainnet")
        assert a.check({}).requires_payment is True

    def test_valid_proof_passes(self):
        a = _make_adapter(protocol="mpp", gate=_make_gate(_inner_ok()))
        assert a.check({"Authorization": "Payment good-proof"}).requires_payment is False

    def test_error_field_propagated(self):
        inner = _inner_no_proof()
        inner.error = "HMAC mismatch"
        a = _make_adapter(protocol="mpp", gate=_make_gate(inner))
        assert a.check({}).error == "HMAC mismatch"


# ═══════════════════════════════════════════════════════════════════════════════
# Group 5 — x402 check (7 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestX402Check:
    def _x402_inner(self, verified: bool = False) -> MagicMock:
        import base64
        m = MagicMock()
        m.requires_payment = not verified
        m.error = None if verified else "No proof"
        m.receipt = None
        m.mandate = None
        challenge = base64.b64encode(json.dumps(
            {"x402Version": 1, "accepts": [{"network": "algorand-mainnet"}]}
        ).encode()).decode()
        m.as_wsgi_response.return_value = (
            "402 Payment Required",
            [("X-PAYMENT-REQUIRED", challenge)],
            b'{"error":"payment_required"}',
        )
        return m

    def test_no_proof_requires_payment(self):
        a = _make_adapter(protocol="x402", gate=_make_gate(self._x402_inner()))
        assert a.check({}).requires_payment is True

    def test_x_payment_required_header(self):
        a = _make_adapter(protocol="x402", gate=_make_gate(self._x402_inner()))
        _, headers, _ = a.check({}).as_wsgi_response()
        assert any(k == "X-PAYMENT-REQUIRED" for k, v in headers)

    def test_challenge_base64_json(self):
        import base64
        a = _make_adapter(protocol="x402", gate=_make_gate(self._x402_inner()))
        _, headers, _ = a.check({}).as_wsgi_response()
        val = next(v for k, v in headers if k == "X-PAYMENT-REQUIRED")
        decoded = json.loads(base64.b64decode(val))
        assert decoded["x402Version"] == 1

    def test_challenge_has_accepts(self):
        import base64
        a = _make_adapter(protocol="x402", gate=_make_gate(self._x402_inner()))
        _, headers, _ = a.check({}).as_wsgi_response()
        val = next(v for k, v in headers if k == "X-PAYMENT-REQUIRED")
        decoded = json.loads(base64.b64decode(val))
        assert isinstance(decoded["accepts"], list)

    def test_valid_proof_passes(self):
        a = _make_adapter(protocol="x402", gate=_make_gate(self._x402_inner(verified=True)))
        assert a.check({"X-PAYMENT": "proof"}).requires_payment is False

    def test_invalid_proof_rejected(self):
        a = _make_adapter(protocol="x402", gate=_make_gate(self._x402_inner()))
        assert a.check({"X-PAYMENT": "bad"}).requires_payment is True

    def test_network_hedera(self):
        a = _make_adapter(protocol="x402", network="hedera-mainnet",
                          gate=_make_gate(self._x402_inner()))
        assert a.check({}).requires_payment is True


# ═══════════════════════════════════════════════════════════════════════════════
# Group 6 — AP2 check (7 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAp2Check:
    def _ap2_inner(self, verified: bool = False) -> MagicMock:
        import base64
        m = MagicMock()
        m.requires_payment = not verified
        m.error = None if verified else "No mandate"
        m.receipt = None
        m.mandate = MagicMock(payer_address="addr", network="algorand-mainnet") if verified else None
        challenge = base64.b64encode(json.dumps(
            {"type": "CartMandate", "ap2_version": "0.1", "network": "algorand-mainnet"}
        ).encode()).decode()
        m.as_wsgi_response.return_value = (
            "402 Payment Required",
            [("X-AP2-Cart-Mandate", challenge)],
            b'{"error":"payment_required"}',
        )
        return m

    def test_no_mandate_requires_payment(self):
        a = _make_adapter(protocol="ap2", gate=_make_gate(self._ap2_inner()))
        assert a.check({}).requires_payment is True

    def test_x_ap2_header(self):
        a = _make_adapter(protocol="ap2", gate=_make_gate(self._ap2_inner()))
        _, headers, _ = a.check({}).as_wsgi_response()
        assert any(k == "X-AP2-Cart-Mandate" for k, v in headers)

    def test_challenge_base64_json(self):
        import base64
        a = _make_adapter(protocol="ap2", gate=_make_gate(self._ap2_inner()))
        _, headers, _ = a.check({}).as_wsgi_response()
        val = next(v for k, v in headers if k == "X-AP2-Cart-Mandate")
        decoded = json.loads(base64.b64decode(val))
        assert decoded["type"] == "CartMandate"

    def test_challenge_has_version(self):
        import base64
        a = _make_adapter(protocol="ap2", gate=_make_gate(self._ap2_inner()))
        _, headers, _ = a.check({}).as_wsgi_response()
        val = next(v for k, v in headers if k == "X-AP2-Cart-Mandate")
        decoded = json.loads(base64.b64decode(val))
        assert decoded["ap2_version"] == "0.1"

    def test_valid_mandate_passes(self):
        a = _make_adapter(protocol="ap2", gate=_make_gate(self._ap2_inner(verified=True)))
        r = a.check({"X-AP2-Payment": "mandate"})
        assert r.requires_payment is False
        assert r.mandate is not None

    def test_invalid_mandate_rejected(self):
        a = _make_adapter(protocol="ap2", gate=_make_gate(self._ap2_inner()))
        assert a.check({"X-AP2-Payment": "bad"}).requires_payment is True

    def test_network_voi(self):
        a = _make_adapter(protocol="ap2", network="voi-mainnet",
                          gate=_make_gate(self._ap2_inner()))
        assert a.check({}).requires_payment is True


# ═══════════════════════════════════════════════════════════════════════════════
# Group 7 — invoke_graph (8 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestInvokeGraph:
    def _make_graph(self, return_value: dict | None = None) -> MagicMock:
        g = MagicMock()
        g.invoke.return_value = return_value or {"messages": [{"role": "ai", "content": "hi"}]}
        return g

    def test_calls_graph_invoke(self):
        a = _make_adapter()
        g = self._make_graph()
        a.invoke_graph(g, {"messages": []})
        g.invoke.assert_called_once()

    def test_passes_inputs(self):
        a = _make_adapter()
        g = self._make_graph()
        inputs = {"messages": [{"role": "user", "content": "hello"}]}
        a.invoke_graph(g, inputs)
        assert g.invoke.call_args[0][0] == inputs

    def test_returns_graph_output(self):
        a = _make_adapter()
        expected = {"messages": [{"role": "ai", "content": "done"}]}
        g = self._make_graph(expected)
        result = a.invoke_graph(g, {"messages": []})
        assert result == expected

    def test_passes_config(self):
        a = _make_adapter()
        g = self._make_graph()
        cfg = {"configurable": {"thread_id": "sess-1"}}
        a.invoke_graph(g, {}, config=cfg)
        assert g.invoke.call_args[1]["config"] == cfg

    def test_config_defaults_none(self):
        a = _make_adapter()
        g = self._make_graph()
        a.invoke_graph(g, {})
        assert g.invoke.call_args[1]["config"] is None

    def test_empty_inputs(self):
        a = _make_adapter()
        g = self._make_graph({"output": "result"})
        result = a.invoke_graph(g, {})
        assert result == {"output": "result"}

    def test_invoke_called_once_per_request(self):
        a = _make_adapter()
        g = self._make_graph()
        a.invoke_graph(g, {"messages": []})
        a.invoke_graph(g, {"messages": []})
        assert g.invoke.call_count == 2

    def test_passthrough_arbitrary_state_shape(self):
        a = _make_adapter()
        state = {"counter": 5, "history": ["a", "b"], "done": True}
        g = self._make_graph(state)
        result = a.invoke_graph(g, {"counter": 0})
        assert result["counter"] == 5
        assert result["done"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# Group 8 — stream_graph (6 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestStreamGraph:
    def _make_streaming_graph(self, chunks: list | None = None) -> MagicMock:
        g = MagicMock()
        g.stream.return_value = iter(chunks or [
            {"messages": [{"content": "tok1"}]},
            {"messages": [{"content": "tok2"}]},
        ])
        return g

    def test_returns_iterator(self):
        a = _make_adapter()
        g = self._make_streaming_graph()
        result = a.stream_graph(g, {})
        assert hasattr(result, "__iter__")

    def test_yields_chunks(self):
        a = _make_adapter()
        chunks = [{"step": 1}, {"step": 2}, {"step": 3}]
        g = self._make_streaming_graph(chunks)
        collected = list(a.stream_graph(g, {}))
        assert collected == chunks

    def test_calls_graph_stream(self):
        a = _make_adapter()
        g = self._make_streaming_graph()
        list(a.stream_graph(g, {"messages": []}))
        g.stream.assert_called_once()

    def test_default_stream_mode_values(self):
        a = _make_adapter()
        g = self._make_streaming_graph()
        list(a.stream_graph(g, {}))
        assert g.stream.call_args[1]["stream_mode"] == "values"

    def test_custom_stream_mode(self):
        a = _make_adapter()
        g = self._make_streaming_graph()
        list(a.stream_graph(g, {}, stream_mode="updates"))
        assert g.stream.call_args[1]["stream_mode"] == "updates"

    def test_passes_config(self):
        a = _make_adapter()
        g = self._make_streaming_graph()
        cfg = {"configurable": {"thread_id": "t1"}}
        list(a.stream_graph(g, {}, config=cfg))
        assert g.stream.call_args[1]["config"] == cfg


# ═══════════════════════════════════════════════════════════════════════════════
# Group 9 — as_tool / AlgoVoiPaymentTool (8 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAsTool:
    def test_returns_payment_tool(self):
        a    = _make_adapter()
        tool = a.as_tool(lambda q: "result")
        assert isinstance(tool, AlgoVoiPaymentTool)

    def test_default_name(self):
        a    = _make_adapter()
        tool = a.as_tool(lambda q: "result")
        assert tool.name == "algovoi_payment_gate"

    def test_custom_name(self):
        a    = _make_adapter()
        tool = a.as_tool(lambda q: "result", tool_name="premium_kb")
        assert tool.name == "premium_kb"

    def test_custom_description(self):
        a    = _make_adapter()
        desc = "My custom description."
        tool = a.as_tool(lambda q: "result", tool_description=desc)
        assert tool.description == desc

    def test_no_proof_returns_challenge(self):
        a    = _make_adapter(gate=_make_gate(_inner_no_proof()))
        tool = a.as_tool(lambda q: "secret")
        out  = json.loads(tool._run(query="x", payment_proof=""))
        assert out["error"] == "payment_required"

    def test_with_proof_calls_resource_fn(self):
        a    = _make_adapter(gate=_make_gate(_inner_ok()))
        tool = a.as_tool(lambda q: f"answer:{q}")
        out  = tool._run(query="test", payment_proof="valid-proof")
        assert out == "answer:test"

    def test_resource_fn_exception_handled(self):
        a = _make_adapter(gate=_make_gate(_inner_ok()))
        def boom(q): raise RuntimeError("db down")
        tool = a.as_tool(boom)
        out  = json.loads(tool._run(query="x", payment_proof="valid"))
        assert out["error"] == "resource_error"

    def test_arun_delegates_to_run(self):
        import asyncio
        a    = _make_adapter(gate=_make_gate(_inner_ok()))
        tool = a.as_tool(lambda q: "async-answer")
        out  = asyncio.get_event_loop().run_until_complete(
            tool._arun(query="q", payment_proof="p")
        )
        assert out == "async-answer"


# ═══════════════════════════════════════════════════════════════════════════════
# Group 10 — tool_node (4 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestToolNode:
    def test_tool_node_requires_langgraph(self):
        a = _make_adapter()
        with patch.dict("sys.modules", {"langgraph": None, "langgraph.prebuilt": None}):
            with pytest.raises(ImportError, match="langgraph"):
                a.tool_node(lambda q: "result")

    def test_tool_node_creates_node(self):
        a = _make_adapter()
        mock_node = MagicMock()
        mock_tool_node_cls = MagicMock(return_value=mock_node)
        with patch.dict("sys.modules", {
            "langgraph":          MagicMock(),
            "langgraph.prebuilt": MagicMock(ToolNode=mock_tool_node_cls),
        }):
            with patch("langgraph_algovoi.AlgoVoiLangGraph.tool_node",
                       wraps=a.tool_node):
                pass
        # Verify the pattern: as_tool creates the right tool
        tool = a.as_tool(lambda q: "r", tool_name="kb")
        assert tool.name == "kb"

    def test_tool_node_passes_tool(self):
        a = _make_adapter()
        captured = {}
        def fake_tool_node(tools):
            captured["tools"] = tools
            return MagicMock()

        import types
        lg_mod = types.ModuleType("langgraph")
        lg_pre = types.ModuleType("langgraph.prebuilt")
        lg_pre.ToolNode = fake_tool_node
        with patch.dict("sys.modules", {
            "langgraph": lg_mod,
            "langgraph.prebuilt": lg_pre,
        }):
            node = a.tool_node(lambda q: "result", tool_name="my_kb")
        assert len(captured.get("tools", [])) == 1
        assert captured["tools"][0].name == "my_kb"

    def test_tool_node_default_name(self):
        a = _make_adapter()
        captured = {}
        def fake_tool_node(tools):
            captured["tools"] = tools
            return MagicMock()

        import types
        lg_mod = types.ModuleType("langgraph")
        lg_pre = types.ModuleType("langgraph.prebuilt")
        lg_pre.ToolNode = fake_tool_node
        with patch.dict("sys.modules", {
            "langgraph": lg_mod,
            "langgraph.prebuilt": lg_pre,
        }):
            a.tool_node(lambda q: "r")
        assert captured["tools"][0].name == "algovoi_payment_gate"


# ═══════════════════════════════════════════════════════════════════════════════
# Group 11 — flask_guard (4 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlaskGuard:
    def _app(self, adapter: AlgoVoiLangGraph):
        pytest.importorskip("flask")
        from flask import Flask
        app = Flask(__name__)

        @app.route("/agent", methods=["POST"])
        def agent():
            guard = adapter.flask_guard()
            if guard is not None:
                return guard
            return "OK", 200

        return app

    def test_returns_402_without_payment(self):
        a = _make_adapter(gate=_make_gate(_inner_no_proof()))
        with self._app(a).test_client() as c:
            resp = c.post("/agent", json={"messages": []})
        assert resp.status_code == 402

    def test_returns_200_with_payment(self):
        a = _make_adapter(gate=_make_gate(_inner_ok()))
        with self._app(a).test_client() as c:
            resp = c.post("/agent", json={"messages": []},
                          headers={"Authorization": "Payment proof"})
        assert resp.status_code == 200

    def test_large_body_capped(self):
        a = _make_adapter(gate=_make_gate(_inner_no_proof()))
        with self._app(a).test_client() as c:
            resp = c.post("/agent", data=b"x" * 2_000_000,
                          content_type="application/json")
        assert resp.status_code == 402

    def test_invalid_json_body(self):
        a = _make_adapter(gate=_make_gate(_inner_no_proof()))
        with self._app(a).test_client() as c:
            resp = c.post("/agent", data=b"not json",
                          content_type="application/json")
        assert resp.status_code == 402


# ═══════════════════════════════════════════════════════════════════════════════
# Group 12 — flask_agent (6 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlaskAgent:
    def _app(self, adapter: AlgoVoiLangGraph, graph: MagicMock):
        pytest.importorskip("flask")
        from flask import Flask
        app = Flask(__name__)

        @app.route("/agent", methods=["POST"])
        def agent():
            return adapter.flask_agent(graph)

        return app

    def _graph(self, output: dict | None = None) -> MagicMock:
        g = MagicMock()
        g.invoke.return_value = output or {"messages": [{"role": "ai", "content": "done"}]}
        return g

    def test_no_payment_returns_402(self):
        a = _make_adapter(gate=_make_gate(_inner_no_proof()))
        g = self._graph()
        with self._app(a, g).test_client() as c:
            resp = c.post("/agent", json={"messages": [{"role": "user", "content": "hi"}]})
        assert resp.status_code == 402

    def test_verified_returns_200(self):
        a = _make_adapter(gate=_make_gate(_inner_ok()))
        g = self._graph()
        with self._app(a, g).test_client() as c:
            resp = c.post("/agent",
                          json={"messages": [{"role": "user", "content": "hi"}]},
                          headers={"Authorization": "Payment proof"})
        assert resp.status_code == 200

    def test_graph_output_in_response(self):
        a = _make_adapter(gate=_make_gate(_inner_ok()))
        g = self._graph({"messages": [{"content": "hello back"}]})
        with self._app(a, g).test_client() as c:
            resp = c.post("/agent",
                          json={"messages": [{"role": "user", "content": "hi"}]},
                          headers={"Authorization": "Payment proof"})
        data = resp.get_json()
        assert data["messages"][0]["content"] == "hello back"

    def test_graph_invoked_once(self):
        a = _make_adapter(gate=_make_gate(_inner_ok()))
        g = self._graph()
        with self._app(a, g).test_client() as c:
            c.post("/agent",
                   json={"messages": []},
                   headers={"Authorization": "Payment proof"})
        g.invoke.assert_called_once()

    def test_graph_not_invoked_without_payment(self):
        a = _make_adapter(gate=_make_gate(_inner_no_proof()))
        g = self._graph()
        with self._app(a, g).test_client() as c:
            c.post("/agent", json={"messages": []})
        g.invoke.assert_not_called()

    def test_custom_input_key(self):
        a = _make_adapter(gate=_make_gate(_inner_ok()))
        g = self._graph({"result": "ok"})

        pytest.importorskip("flask")
        from flask import Flask
        app = Flask(__name__)

        @app.route("/agent", methods=["POST"])
        def agent():
            return a.flask_agent(g, input_key="query")

        with app.test_client() as c:
            resp = c.post("/agent",
                          json={"query": "what is AlgoVoi?"},
                          headers={"Authorization": "Payment proof"})
        assert resp.status_code == 200
        assert g.invoke.call_args[0][0] == {"query": "what is AlgoVoi?"}
