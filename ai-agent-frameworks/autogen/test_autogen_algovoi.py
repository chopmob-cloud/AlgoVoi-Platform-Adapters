"""
Unit tests for autogen_algovoi — all mocked, no live network calls.

Run:
    cd ai-agent-frameworks/autogen
    python -m pytest test_autogen_algovoi.py -v
"""

from __future__ import annotations

import json
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# ── inject stub gate modules before importing adapter ──────────────────────────

def _make_gate(requires_payment: bool = False, error: str | None = None):
    g = MagicMock()
    r = MagicMock()
    r.requires_payment = requires_payment
    r.error = error
    r.receipt = "rcpt-1"
    r.mandate = {"pay": "here"}
    r.as_flask_response.return_value = ("flask-402", 402)
    r.as_wsgi_response.return_value = (402, [("X-Pay", "1")], b"pay")
    g.check.return_value = r
    return g, r


def _stub_mpp(gate):
    mod = types.ModuleType("mpp_algovoi")
    mod.AlgoVoiMppGate = MagicMock(return_value=gate)
    sys.modules["mpp_algovoi"] = mod


def _stub_ap2(gate):
    mod = types.ModuleType("ap2_algovoi")
    mod.AlgoVoiAp2Gate = MagicMock(return_value=gate)
    sys.modules["ap2_algovoi"] = mod


def _stub_x402(gate):
    mod = types.ModuleType("openai_algovoi")
    mod.AlgoVoiX402Gate = MagicMock(return_value=gate)
    sys.modules["openai_algovoi"] = mod


# pre-stub so adapter can import
_g_default, _ = _make_gate()
_stub_mpp(_g_default)
_stub_ap2(_g_default)
_stub_x402(_g_default)

import os
import flask  # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

import autogen_algovoi as ag_mod  # noqa: E402
from autogen_algovoi import (  # noqa: E402
    AlgoVoiAutoGen,
    AlgoVoiPaymentTool,
    AutoGenResult,
    NETWORKS,
    PROTOCOLS,
    _MAX_FLASK_BODY,
    _extract_chat_result,
)


# ── helpers ────────────────────────────────────────────────────────────────────

def _adapter(
    *,
    protocol: str = "mpp",
    network: str = "algorand-mainnet",
    amount: int = 10_000,
    gate_requires_payment: bool = False,
    gate_error: str | None = None,
    openai_key: str | None = "sk-test",
    model: str = "gpt-4o",
    base_url: str | None = None,
    resource_id: str = "ai-conversation",
) -> tuple[AlgoVoiAutoGen, MagicMock, MagicMock]:
    gate, gate_result = _make_gate(gate_requires_payment, gate_error)
    _stub_mpp(gate)
    _stub_ap2(gate)
    _stub_x402(gate)
    a = AlgoVoiAutoGen(
        algovoi_key="algv_test",
        tenant_id="tid",
        payout_address="ADDR",
        openai_key=openai_key,
        protocol=protocol,
        network=network,
        amount_microunits=amount,
        model=model,
        base_url=base_url,
        resource_id=resource_id,
    )
    return a, gate, gate_result


# ── fake ChatResult ────────────────────────────────────────────────────────────

class _ChatResult:
    def __init__(self, summary=None, history=None):
        if summary is not None:
            self.summary = summary
        self.chat_history = history or []

    def __str__(self):
        return "str-fallback"


# ══════════════════════════════════════════════════════════════════════════════
# 1 — module-level constants
# ══════════════════════════════════════════════════════════════════════════════

class TestModuleConstants(unittest.TestCase):
    def test_version(self):
        self.assertEqual(ag_mod.__version__, "1.0.0")

    def test_all_exports(self):
        self.assertIn("AlgoVoiAutoGen", ag_mod.__all__)
        self.assertIn("AlgoVoiPaymentTool", ag_mod.__all__)
        self.assertIn("AutoGenResult", ag_mod.__all__)

    def test_networks(self):
        for net in ("algorand-mainnet", "voi-mainnet", "hedera-mainnet", "stellar-mainnet"):
            self.assertIn(net, NETWORKS)

    def test_protocols(self):
        self.assertEqual(PROTOCOLS, frozenset({"mpp", "ap2", "x402"}))

    def test_body_cap(self):
        self.assertEqual(_MAX_FLASK_BODY, 1_048_576)


# ══════════════════════════════════════════════════════════════════════════════
# 2 — AutoGenResult wrapper
# ══════════════════════════════════════════════════════════════════════════════

class TestAutoGenResult(unittest.TestCase):
    def _make(self, **kw) -> AutoGenResult:
        raw = MagicMock()
        for k, v in kw.items():
            setattr(raw, k, v)
        return AutoGenResult(raw)

    def test_requires_payment_true(self):
        self.assertTrue(self._make(requires_payment=True).requires_payment)

    def test_requires_payment_false(self):
        self.assertFalse(self._make(requires_payment=False).requires_payment)

    def test_error_attr(self):
        self.assertEqual(self._make(requires_payment=False, error="bad").error, "bad")

    def test_error_missing(self):
        raw = MagicMock(spec=["requires_payment"])
        raw.requires_payment = False
        self.assertIsNone(AutoGenResult(raw).error)

    def test_receipt(self):
        self.assertEqual(self._make(requires_payment=False, receipt="rcpt").receipt, "rcpt")

    def test_mandate(self):
        self.assertEqual(self._make(requires_payment=False, mandate={"u": "x"}).mandate, {"u": "x"})

    def test_as_flask_response(self):
        raw = MagicMock()
        raw.as_flask_response.return_value = ("body", 402)
        self.assertEqual(AutoGenResult(raw).as_flask_response(), ("body", 402))

    def test_as_wsgi_response(self):
        raw = MagicMock()
        raw.as_wsgi_response.return_value = (402, [], b"pay")
        self.assertEqual(AutoGenResult(raw).as_wsgi_response(), (402, [], b"pay"))


# ══════════════════════════════════════════════════════════════════════════════
# 3 — _build_gate() — protocol routing
# ══════════════════════════════════════════════════════════════════════════════

class TestBuildGate(unittest.TestCase):
    def test_mpp_gate_created(self):
        gate, _ = _make_gate()
        mock_cls = MagicMock(return_value=gate)
        mod = types.ModuleType("mpp_algovoi")
        mod.AlgoVoiMppGate = mock_cls
        sys.modules["mpp_algovoi"] = mod
        AlgoVoiAutoGen(algovoi_key="k", tenant_id="t", payout_address="a", protocol="mpp")
        mock_cls.assert_called_once()

    def test_ap2_gate_created(self):
        gate, _ = _make_gate()
        mock_cls = MagicMock(return_value=gate)
        mod = types.ModuleType("ap2_algovoi")
        mod.AlgoVoiAp2Gate = mock_cls
        sys.modules["ap2_algovoi"] = mod
        AlgoVoiAutoGen(algovoi_key="k", tenant_id="t", payout_address="a", protocol="ap2")
        mock_cls.assert_called_once()

    def test_x402_gate_created(self):
        gate, _ = _make_gate()
        mock_cls = MagicMock(return_value=gate)
        mod = types.ModuleType("openai_algovoi")
        mod.AlgoVoiX402Gate = mock_cls
        sys.modules["openai_algovoi"] = mod
        AlgoVoiAutoGen(algovoi_key="k", tenant_id="t", payout_address="a", protocol="x402")
        mock_cls.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
# 4 — AlgoVoiAutoGen constructor
# ══════════════════════════════════════════════════════════════════════════════

class TestConstructor(unittest.TestCase):
    def test_bad_protocol_raises(self):
        with self.assertRaises(ValueError):
            AlgoVoiAutoGen(algovoi_key="k", tenant_id="t", payout_address="a", protocol="bad")

    def test_bad_network_raises(self):
        with self.assertRaises(ValueError):
            AlgoVoiAutoGen(algovoi_key="k", tenant_id="t", payout_address="a", network="eth-mainnet")

    def test_all_valid_networks(self):
        for net in NETWORKS:
            a, _, _ = _adapter(network=net)
            self.assertIsNotNone(a)

    def test_all_valid_protocols(self):
        for proto in PROTOCOLS:
            a, _, _ = _adapter(protocol=proto)
            self.assertIsNotNone(a)

    def test_openai_key_stored(self):
        a, _, _ = _adapter(openai_key="sk-abc")
        self.assertEqual(a._openai_key, "sk-abc")

    def test_model_stored(self):
        a, _, _ = _adapter(model="gpt-4o-mini")
        self.assertEqual(a._model, "gpt-4o-mini")

    def test_default_model(self):
        a, _, _ = _adapter()
        self.assertEqual(a._model, "gpt-4o")

    def test_base_url_stored(self):
        a, _, _ = _adapter(base_url="https://my.endpoint/")
        self.assertEqual(a._base_url, "https://my.endpoint/")

    def test_resource_id_default(self):
        a, _, _ = _adapter()
        # resource_id is passed to _build_gate; check the gate was called with it
        # (gate is a MagicMock so we just verify no error)
        self.assertIsNotNone(a)


# ══════════════════════════════════════════════════════════════════════════════
# 5 — llm_config property
# ══════════════════════════════════════════════════════════════════════════════

class TestLlmConfig(unittest.TestCase):
    def test_returns_dict_with_config_list(self):
        a, _, _ = _adapter(openai_key="sk-key", model="gpt-4o")
        cfg = a.llm_config
        self.assertIn("config_list", cfg)
        self.assertIsInstance(cfg["config_list"], list)
        self.assertEqual(len(cfg["config_list"]), 1)

    def test_model_in_config(self):
        a, _, _ = _adapter(model="gpt-4o-mini")
        self.assertEqual(a.llm_config["config_list"][0]["model"], "gpt-4o-mini")

    def test_api_key_in_config(self):
        a, _, _ = _adapter(openai_key="sk-test123")
        self.assertEqual(a.llm_config["config_list"][0]["api_key"], "sk-test123")

    def test_no_key_no_api_key_field(self):
        a, _, _ = _adapter(openai_key=None)
        self.assertNotIn("api_key", a.llm_config["config_list"][0])

    def test_base_url_in_config(self):
        a, _, _ = _adapter(base_url="https://custom.api/")
        self.assertEqual(a.llm_config["config_list"][0]["base_url"], "https://custom.api/")

    def test_no_base_url_no_field(self):
        a, _, _ = _adapter(base_url=None)
        self.assertNotIn("base_url", a.llm_config["config_list"][0])


# ══════════════════════════════════════════════════════════════════════════════
# 6 — check()
# ══════════════════════════════════════════════════════════════════════════════

class TestCheck(unittest.TestCase):
    def test_returns_autogen_result(self):
        a, _, _ = _adapter()
        r = a.check({})
        self.assertIsInstance(r, AutoGenResult)

    def test_requires_payment_false(self):
        a, _, _ = _adapter(gate_requires_payment=False)
        self.assertFalse(a.check({}).requires_payment)

    def test_requires_payment_true(self):
        a, _, _ = _adapter(gate_requires_payment=True)
        self.assertTrue(a.check({}).requires_payment)

    def test_body_passed_to_gate(self):
        a, gate, _ = _adapter()
        a.check({"H": "v"}, {"k": "v"})
        gate.check.assert_called_once_with({"H": "v"}, {"k": "v"})

    def test_none_body_becomes_empty_dict(self):
        a, gate, _ = _adapter()
        a.check({"H": "v"}, None)
        gate.check.assert_called_with({"H": "v"}, {})

    def test_typeerror_fallback(self):
        a, gate, _ = _adapter()
        call_count = {"n": 0}

        def _side(headers, body=None):
            call_count["n"] += 1
            if call_count["n"] == 1 and body is not None:
                raise TypeError("unexpected body")
            return gate.check.return_value

        gate.check.side_effect = _side
        r = a.check({"H": "v"}, {"b": 1})
        self.assertIsInstance(r, AutoGenResult)


# ══════════════════════════════════════════════════════════════════════════════
# 7 — _extract_chat_result()
# ══════════════════════════════════════════════════════════════════════════════

class TestExtractChatResult(unittest.TestCase):
    def test_summary_returned_first(self):
        cr = _ChatResult(summary="Final answer", history=[{"role": "user", "content": "ignored"}])
        self.assertEqual(_extract_chat_result(cr), "Final answer")

    def test_last_history_message_when_no_summary(self):
        cr = _ChatResult(history=[
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello there"},
        ])
        self.assertEqual(_extract_chat_result(cr), "Hello there")

    def test_str_fallback_when_no_summary_no_history(self):
        cr = _ChatResult()
        self.assertEqual(_extract_chat_result(cr), "str-fallback")

    def test_empty_history_str_fallback(self):
        cr = _ChatResult(history=[])
        self.assertEqual(_extract_chat_result(cr), "str-fallback")

    def test_summary_empty_string_falls_through(self):
        # Empty string is falsy — should fall through to history
        cr = _ChatResult(history=[{"role": "assistant", "content": "last msg"}])
        cr.summary = ""
        self.assertEqual(_extract_chat_result(cr), "last msg")

    def test_non_dict_history_entry_str_fallback(self):
        cr = _ChatResult(history=["plain string entry"])
        self.assertEqual(_extract_chat_result(cr), "str-fallback")

    def test_history_missing_content_key(self):
        cr = _ChatResult(history=[{"role": "assistant"}])  # no "content"
        self.assertEqual(_extract_chat_result(cr), "")

    def test_mock_chat_result(self):
        raw = MagicMock()
        raw.summary = "Summary text"
        self.assertEqual(_extract_chat_result(raw), "Summary text")


# ══════════════════════════════════════════════════════════════════════════════
# 8 — initiate_chat()
# ══════════════════════════════════════════════════════════════════════════════

class TestInitiateChat(unittest.TestCase):
    def _agents(self, summary="agent reply"):
        cr = _ChatResult(summary=summary)
        sender = MagicMock()
        sender.initiate_chat.return_value = cr
        recipient = MagicMock()
        return sender, recipient, cr

    def test_calls_sender_initiate_chat(self):
        a, _, _ = _adapter()
        sender, recipient, _ = self._agents()
        a.initiate_chat(recipient, sender, "Hello")
        sender.initiate_chat.assert_called_once()

    def test_recipient_is_first_positional_arg(self):
        a, _, _ = _adapter()
        sender, recipient, _ = self._agents()
        a.initiate_chat(recipient, sender, "Hello")
        call_args = sender.initiate_chat.call_args
        self.assertIs(call_args[0][0], recipient)

    def test_message_passed_as_kwarg(self):
        a, _, _ = _adapter()
        sender, recipient, _ = self._agents()
        a.initiate_chat(recipient, sender, "My question")
        call_kwargs = sender.initiate_chat.call_args[1]
        self.assertEqual(call_kwargs["message"], "My question")

    def test_max_turns_passed_when_provided(self):
        a, _, _ = _adapter()
        sender, recipient, _ = self._agents()
        a.initiate_chat(recipient, sender, "q", max_turns=5)
        call_kwargs = sender.initiate_chat.call_args[1]
        self.assertEqual(call_kwargs["max_turns"], 5)

    def test_max_turns_omitted_when_none(self):
        a, _, _ = _adapter()
        sender, recipient, _ = self._agents()
        a.initiate_chat(recipient, sender, "q", max_turns=None)
        call_kwargs = sender.initiate_chat.call_args[1]
        self.assertNotIn("max_turns", call_kwargs)

    def test_returns_summary_string(self):
        a, _, _ = _adapter()
        sender, recipient, _ = self._agents(summary="Final answer")
        result = a.initiate_chat(recipient, sender, "q")
        self.assertEqual(result, "Final answer")

    def test_returns_last_history_when_no_summary(self):
        a, _, _ = _adapter()
        cr = _ChatResult(history=[
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Last msg"},
        ])
        sender = MagicMock()
        sender.initiate_chat.return_value = cr
        result = a.initiate_chat(MagicMock(), sender, "Hi")
        self.assertEqual(result, "Last msg")

    def test_extra_kwargs_forwarded(self):
        a, _, _ = _adapter()
        sender, recipient, _ = self._agents()
        a.initiate_chat(recipient, sender, "q", silent=True)
        call_kwargs = sender.initiate_chat.call_args[1]
        self.assertTrue(call_kwargs.get("silent"))


# ══════════════════════════════════════════════════════════════════════════════
# 9 — as_tool()
# ══════════════════════════════════════════════════════════════════════════════

class TestAsTool(unittest.TestCase):
    def test_returns_payment_tool(self):
        a, _, _ = _adapter()
        tool = a.as_tool(resource_fn=lambda q: "r")
        self.assertIsInstance(tool, AlgoVoiPaymentTool)

    def test_default_tool_name(self):
        a, _, _ = _adapter()
        tool = a.as_tool(resource_fn=lambda q: "r")
        self.assertEqual(tool.name, "algovoi_payment_gate")

    def test_custom_tool_name(self):
        a, _, _ = _adapter()
        tool = a.as_tool(resource_fn=lambda q: "r", tool_name="premium_search")
        self.assertEqual(tool.name, "premium_search")

    def test_custom_description(self):
        a, _, _ = _adapter()
        tool = a.as_tool(resource_fn=lambda q: "r", tool_description="Custom desc")
        self.assertEqual(tool.description, "Custom desc")

    def test_resource_fn_stored(self):
        a, _, _ = _adapter()
        fn = lambda q: "ans"
        tool = a.as_tool(resource_fn=fn)
        self.assertIs(tool._resource_fn, fn)

    def test_adapter_stored_in_tool(self):
        a, _, _ = _adapter()
        tool = a.as_tool(resource_fn=lambda q: "r")
        self.assertIs(tool._adapter, a)


# ══════════════════════════════════════════════════════════════════════════════
# 10 — flask_guard()
# ══════════════════════════════════════════════════════════════════════════════

class TestFlaskGuard(unittest.TestCase):
    def _mock_request(self, headers=None, json_body=None, content_length=None):
        req = MagicMock()
        req.headers = headers or {}
        req.get_json.return_value = json_body
        req.content_length = content_length
        return req

    def _agents(self, summary="answer"):
        cr = _ChatResult(summary=summary)
        sender = MagicMock()
        sender.initiate_chat.return_value = cr
        return sender, MagicMock()

    def test_413_when_too_large(self):
        a, _, _ = _adapter()
        mock_req = self._mock_request(content_length=_MAX_FLASK_BODY + 1)
        mock_resp_cls = MagicMock()
        with patch.object(flask, "request", mock_req), \
             patch("flask.Response", mock_resp_cls):
            a.flask_guard(MagicMock(), MagicMock())
        call_args = mock_resp_cls.call_args
        self.assertEqual(call_args[1]["status"], 413)

    def test_402_when_payment_required(self):
        a, gate, gate_result = _adapter(gate_requires_payment=True)
        mock_req = self._mock_request(headers={}, json_body={})
        with patch.object(flask, "request", mock_req):
            a.flask_guard(MagicMock(), MagicMock())
        gate_result.as_flask_response.assert_called_once()

    def test_200_calls_initiate_chat(self):
        a, _, _ = _adapter(gate_requires_payment=False)
        sender, recipient = self._agents("response text")
        mock_req = self._mock_request(
            headers={}, json_body={"message": "Hello agent"}
        )
        mock_jsonify = MagicMock(return_value={"content": "response text"})
        with patch.object(flask, "request", mock_req), \
             patch("flask.jsonify", mock_jsonify):
            a.flask_guard(sender, recipient)
        sender.initiate_chat.assert_called_once()
        call_kwargs = sender.initiate_chat.call_args[1]
        self.assertEqual(call_kwargs["message"], "Hello agent")

    def test_message_fn_used_when_provided(self):
        a, _, _ = _adapter(gate_requires_payment=False)
        sender, recipient = self._agents("ok")
        mock_req = self._mock_request(headers={}, json_body={"query": "custom"})
        mock_jsonify = MagicMock(return_value={"content": "ok"})
        with patch.object(flask, "request", mock_req), \
             patch("flask.jsonify", mock_jsonify):
            a.flask_guard(sender, recipient, message_fn=lambda b: b.get("query", ""))
        call_kwargs = sender.initiate_chat.call_args[1]
        self.assertEqual(call_kwargs["message"], "custom")

    def test_default_message_from_body(self):
        a, _, _ = _adapter(gate_requires_payment=False)
        sender, recipient = self._agents("ok")
        mock_req = self._mock_request(headers={}, json_body={"message": "default msg"})
        mock_jsonify = MagicMock(return_value={"content": "ok"})
        with patch.object(flask, "request", mock_req), \
             patch("flask.jsonify", mock_jsonify):
            a.flask_guard(sender, recipient)
        call_kwargs = sender.initiate_chat.call_args[1]
        self.assertEqual(call_kwargs["message"], "default msg")

    def test_max_turns_forwarded(self):
        a, _, _ = _adapter(gate_requires_payment=False)
        sender, recipient = self._agents("ok")
        mock_req = self._mock_request(headers={}, json_body={"message": "hi"})
        mock_jsonify = MagicMock(return_value={"content": "ok"})
        with patch.object(flask, "request", mock_req), \
             patch("flask.jsonify", mock_jsonify):
            a.flask_guard(sender, recipient, max_turns=3)
        call_kwargs = sender.initiate_chat.call_args[1]
        self.assertEqual(call_kwargs["max_turns"], 3)

    def test_none_body_handled(self):
        a, _, _ = _adapter(gate_requires_payment=False)
        sender, recipient = self._agents("ok")
        mock_req = self._mock_request(headers={}, json_body=None)
        mock_jsonify = MagicMock(return_value={"content": "ok"})
        with patch.object(flask, "request", mock_req), \
             patch("flask.jsonify", mock_jsonify):
            a.flask_guard(sender, recipient)  # should not raise

    def test_no_413_at_exact_limit(self):
        a, _, _ = _adapter(gate_requires_payment=False)
        sender, recipient = self._agents("ok")
        mock_req = self._mock_request(
            content_length=_MAX_FLASK_BODY, headers={}, json_body={"message": "hi"}
        )
        mock_jsonify = MagicMock(return_value={"content": "ok"})
        mock_resp_cls = MagicMock()
        with patch.object(flask, "request", mock_req), \
             patch("flask.jsonify", mock_jsonify), \
             patch("flask.Response", mock_resp_cls):
            a.flask_guard(sender, recipient)
        mock_resp_cls.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# 11 — AlgoVoiPaymentTool attributes
# ══════════════════════════════════════════════════════════════════════════════

class TestPaymentToolAttrs(unittest.TestCase):
    def _make(self, **kw) -> AlgoVoiPaymentTool:
        a, _, _ = _adapter()
        return AlgoVoiPaymentTool(adapter=a, resource_fn=lambda q: "ok", **kw)

    def test_default_name(self):
        self.assertEqual(self._make().name, "algovoi_payment_gate")

    def test_custom_name(self):
        self.assertEqual(self._make(tool_name="my_tool").name, "my_tool")

    def test_default_description_contains_payment(self):
        self.assertIn("payment", self._make().description.lower())

    def test_custom_description(self):
        self.assertEqual(self._make(tool_description="Custom").description, "Custom")

    def test_callable(self):
        tool = self._make()
        self.assertTrue(callable(tool))


# ══════════════════════════════════════════════════════════════════════════════
# 12 — AlgoVoiPaymentTool.__call__() — no proof (challenge)
# ══════════════════════════════════════════════════════════════════════════════

class TestPaymentToolCallChallenge(unittest.TestCase):
    def _tool(self, requires_payment=True, error=None):
        a, gate, gate_result = _adapter(
            gate_requires_payment=requires_payment, gate_error=error
        )
        return AlgoVoiPaymentTool(adapter=a, resource_fn=lambda q: "ok")

    def test_no_proof_returns_challenge_json(self):
        tool = self._tool(requires_payment=True)
        out = tool(query="q", payment_proof="")
        data = json.loads(out)
        self.assertEqual(data["error"], "payment_required")

    def test_no_proof_empty_headers_sent(self):
        a, gate, _ = _adapter(gate_requires_payment=True)
        tool = AlgoVoiPaymentTool(adapter=a, resource_fn=lambda q: "ok")
        tool(query="q", payment_proof="")
        gate.check.assert_called_with({}, {})

    def test_proof_in_auth_header(self):
        a, gate, gate_result = _adapter(gate_requires_payment=False)
        tool = AlgoVoiPaymentTool(adapter=a, resource_fn=lambda q: "ok")
        tool(query="q", payment_proof="b64proof")
        gate.check.assert_called_with({"Authorization": "Payment b64proof"}, {})

    def test_challenge_detail_from_error(self):
        tool = self._tool(requires_payment=True, error="invalid sig")
        data = json.loads(tool(query="q", payment_proof=""))
        self.assertEqual(data["detail"], "invalid sig")

    def test_challenge_detail_fallback_when_no_error(self):
        a, gate, gate_result = _adapter(gate_requires_payment=True)
        gate_result.error = None
        tool = AlgoVoiPaymentTool(adapter=a, resource_fn=lambda q: "ok")
        data = json.loads(tool(query="q", payment_proof=""))
        self.assertIn("detail", data)
        self.assertGreater(len(data["detail"]), 0)


# ══════════════════════════════════════════════════════════════════════════════
# 13 — AlgoVoiPaymentTool.__call__() — valid proof (resource)
# ══════════════════════════════════════════════════════════════════════════════

class TestPaymentToolCallVerified(unittest.TestCase):
    def _tool(self, resource_fn):
        a, _, _ = _adapter(gate_requires_payment=False)
        return AlgoVoiPaymentTool(adapter=a, resource_fn=resource_fn)

    def test_returns_resource_fn_result(self):
        tool = self._tool(lambda q: "premium answer")
        self.assertEqual(tool(query="q", payment_proof="proof"), "premium answer")

    def test_query_forwarded(self):
        received = []
        def fn(q):
            received.append(q)
            return "ok"
        tool = self._tool(fn)
        tool(query="the question", payment_proof="proof")
        self.assertEqual(received, ["the question"])

    def test_resource_fn_exception_returns_error_json(self):
        def bad(q): raise RuntimeError("db down")
        tool = self._tool(bad)
        data = json.loads(tool(query="q", payment_proof="proof"))
        self.assertEqual(data["error"], "resource_error")
        self.assertIn("db down", data["detail"])

    def test_int_result_stringified(self):
        tool = self._tool(lambda q: 42)
        self.assertEqual(tool(query="q", payment_proof="proof"), "42")

    def test_empty_query_forwarded(self):
        received = []
        def fn(q): received.append(q); return "ok"
        tool = self._tool(fn)
        tool(query="", payment_proof="proof")
        self.assertEqual(received, [""])

    def test_default_args_no_raise(self):
        tool = self._tool(lambda q: "r")
        out = tool()
        self.assertIsInstance(out, str)

    def test_typeerror_fallback_in_call(self):
        a, gate, gate_result = _adapter(gate_requires_payment=False)
        call_n = {"n": 0}

        def _side(headers, body=None):
            call_n["n"] += 1
            if call_n["n"] == 1 and body is not None:
                raise TypeError("no body")
            return gate_result

        gate.check.side_effect = _side
        tool = AlgoVoiPaymentTool(adapter=a, resource_fn=lambda q: "ans")
        self.assertEqual(tool(query="q", payment_proof="p"), "ans")


# ══════════════════════════════════════════════════════════════════════════════
# 14 — _add_path helper
# ══════════════════════════════════════════════════════════════════════════════

class TestAddPath(unittest.TestCase):
    def test_adds_path(self):
        import autogen_algovoi as agm
        sentinel = "/nonexistent/sentinel_path_ag"
        original = list(sys.path)
        try:
            agm._add_path(sentinel)
            full = os.path.join(agm._ADAPTERS_ROOT, sentinel)
            self.assertIn(full, sys.path)
        finally:
            sys.path[:] = original

    def test_idempotent(self):
        import autogen_algovoi as agm
        sentinel = "idempotent_ag_test"
        full = os.path.join(agm._ADAPTERS_ROOT, sentinel)
        original = list(sys.path)
        try:
            agm._add_path(sentinel)
            agm._add_path(sentinel)
            self.assertEqual(sys.path.count(full), 1)
        finally:
            sys.path[:] = original


if __name__ == "__main__":
    unittest.main(verbosity=2)
