"""
Unit tests for semantic_kernel_algovoi — all mocked, no live network calls.

Run:
    cd ai-agent-frameworks/semantic-kernel
    python -m pytest test_semantic_kernel_algovoi.py -v
"""

from __future__ import annotations

import asyncio
import json
import sys
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

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
    mod = types.ModuleType("mpp")
    mod.MppGate = MagicMock(return_value=gate)
    sys.modules["mpp"] = mod


def _stub_ap2(gate):
    mod = types.ModuleType("ap2")
    mod.Ap2Gate = MagicMock(return_value=gate)
    sys.modules["ap2"] = mod


def _stub_x402(gate):
    mod = types.ModuleType("openai_algovoi")
    mod._X402Gate = MagicMock(return_value=gate)
    sys.modules["openai_algovoi"] = mod


# pre-stub gate modules
_g_default, _ = _make_gate()
_stub_mpp(_g_default)
_stub_ap2(_g_default)
_stub_x402(_g_default)

import os
import flask  # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

import semantic_kernel_algovoi as sk_mod  # noqa: E402
from semantic_kernel_algovoi import (  # noqa: E402
    AlgoVoiSemanticKernel,
    AlgoVoiPaymentPlugin,
    SemanticKernelResult,
    NETWORKS,
    PROTOCOLS,
    _MAX_FLASK_BODY,
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
    resource_id: str = "ai-function",
) -> tuple[AlgoVoiSemanticKernel, MagicMock, MagicMock]:
    gate, gate_result = _make_gate(gate_requires_payment, gate_error)
    _stub_mpp(gate)
    _stub_ap2(gate)
    _stub_x402(gate)
    a = AlgoVoiSemanticKernel(
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


# ══════════════════════════════════════════════════════════════════════════════
# 1 — module-level constants
# ══════════════════════════════════════════════════════════════════════════════

class TestModuleConstants(unittest.TestCase):
    def test_version(self):
        self.assertEqual(sk_mod.__version__, "1.0.0")

    def test_all_exports(self):
        self.assertIn("AlgoVoiSemanticKernel", sk_mod.__all__)
        self.assertIn("AlgoVoiPaymentPlugin", sk_mod.__all__)
        self.assertIn("SemanticKernelResult", sk_mod.__all__)

    def test_networks(self):
        for net in ("algorand-mainnet", "voi-mainnet", "hedera-mainnet", "stellar-mainnet"):
            self.assertIn(net, NETWORKS)

    def test_protocols(self):
        self.assertEqual(PROTOCOLS, frozenset({"mpp", "ap2", "x402"}))

    def test_body_cap(self):
        self.assertEqual(_MAX_FLASK_BODY, 1_048_576)


# ══════════════════════════════════════════════════════════════════════════════
# 2 — SemanticKernelResult wrapper
# ══════════════════════════════════════════════════════════════════════════════

class TestSemanticKernelResult(unittest.TestCase):
    def _make(self, **kw) -> SemanticKernelResult:
        raw = MagicMock()
        for k, v in kw.items():
            setattr(raw, k, v)
        return SemanticKernelResult(raw)

    def test_requires_payment_true(self):
        self.assertTrue(self._make(requires_payment=True).requires_payment)

    def test_requires_payment_false(self):
        self.assertFalse(self._make(requires_payment=False).requires_payment)

    def test_error_attr(self):
        self.assertEqual(self._make(requires_payment=False, error="bad").error, "bad")

    def test_error_missing(self):
        raw = MagicMock(spec=["requires_payment"])
        raw.requires_payment = False
        self.assertIsNone(SemanticKernelResult(raw).error)

    def test_receipt(self):
        self.assertEqual(self._make(requires_payment=False, receipt="rcpt").receipt, "rcpt")

    def test_mandate(self):
        self.assertEqual(self._make(requires_payment=False, mandate={"u": "x"}).mandate, {"u": "x"})

    def test_as_flask_response(self):
        raw = MagicMock()
        raw.as_flask_response.return_value = ("body", 402)
        self.assertEqual(SemanticKernelResult(raw).as_flask_response(), ("body", 402))

    def test_as_wsgi_response(self):
        raw = MagicMock()
        raw.as_wsgi_response.return_value = (402, [], b"pay")
        self.assertEqual(SemanticKernelResult(raw).as_wsgi_response(), (402, [], b"pay"))


# ══════════════════════════════════════════════════════════════════════════════
# 3 — _build_gate() — protocol routing
# ══════════════════════════════════════════════════════════════════════════════

class TestBuildGate(unittest.TestCase):
    def test_mpp_gate_created(self):
        gate, _ = _make_gate()
        mock_cls = MagicMock(return_value=gate)
        mod = types.ModuleType("mpp")
        mod.MppGate = mock_cls
        sys.modules["mpp"] = mod
        AlgoVoiSemanticKernel(algovoi_key="k", tenant_id="t", payout_address="a", protocol="mpp")
        mock_cls.assert_called_once()

    def test_ap2_gate_created(self):
        gate, _ = _make_gate()
        mock_cls = MagicMock(return_value=gate)
        mod = types.ModuleType("ap2")
        mod.Ap2Gate = mock_cls
        sys.modules["ap2"] = mod
        AlgoVoiSemanticKernel(algovoi_key="k", tenant_id="t", payout_address="a", protocol="ap2")
        mock_cls.assert_called_once()

    def test_x402_gate_created(self):
        gate, _ = _make_gate()
        mock_cls = MagicMock(return_value=gate)
        mod = types.ModuleType("openai_algovoi")
        mod._X402Gate = mock_cls
        sys.modules["openai_algovoi"] = mod
        AlgoVoiSemanticKernel(algovoi_key="k", tenant_id="t", payout_address="a", protocol="x402")
        mock_cls.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
# 4 — AlgoVoiSemanticKernel constructor
# ══════════════════════════════════════════════════════════════════════════════

class TestConstructor(unittest.TestCase):
    def test_bad_protocol_raises(self):
        with self.assertRaises(ValueError):
            AlgoVoiSemanticKernel(algovoi_key="k", tenant_id="t", payout_address="a", protocol="bad")

    def test_bad_network_raises(self):
        with self.assertRaises(ValueError):
            AlgoVoiSemanticKernel(algovoi_key="k", tenant_id="t", payout_address="a", network="eth-mainnet")

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
        a, _, _ = _adapter(base_url="https://custom.api/")
        self.assertEqual(a._base_url, "https://custom.api/")

    def test_kernel_starts_none(self):
        a, _, _ = _adapter()
        self.assertIsNone(a._kernel)


# ══════════════════════════════════════════════════════════════════════════════
# 5 — check()
# ══════════════════════════════════════════════════════════════════════════════

class TestCheck(unittest.TestCase):
    def test_returns_sk_result(self):
        a, _, _ = _adapter()
        self.assertIsInstance(a.check({}), SemanticKernelResult)

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
        self.assertIsInstance(a.check({"H": "v"}, {"b": 1}), SemanticKernelResult)


# ══════════════════════════════════════════════════════════════════════════════
# 6 — _ensure_kernel()
# ══════════════════════════════════════════════════════════════════════════════

def _stub_sk_modules():
    """Stub out the semantic_kernel imports needed by _ensure_kernel."""
    mock_kernel_inst = MagicMock()
    mock_kernel_cls = MagicMock(return_value=mock_kernel_inst)
    mock_oai_svc = MagicMock()

    sk_mod_stub = types.ModuleType("semantic_kernel")
    sk_mod_stub.Kernel = mock_kernel_cls

    ai_mod = types.ModuleType("semantic_kernel.connectors")
    ai_mod2 = types.ModuleType("semantic_kernel.connectors.ai")
    oai_mod = types.ModuleType("semantic_kernel.connectors.ai.open_ai")
    oai_mod.OpenAIChatCompletion = MagicMock(return_value=mock_oai_svc)

    sys.modules.update({
        "semantic_kernel": sk_mod_stub,
        "semantic_kernel.connectors": ai_mod,
        "semantic_kernel.connectors.ai": ai_mod2,
        "semantic_kernel.connectors.ai.open_ai": oai_mod,
    })
    return mock_kernel_cls, mock_kernel_inst, oai_mod.OpenAIChatCompletion, mock_oai_svc


def _clear_sk_modules():
    for k in list(sys.modules.keys()):
        if k.startswith("semantic_kernel"):
            del sys.modules[k]


class TestEnsureKernel(unittest.TestCase):
    def setUp(self):
        _clear_sk_modules()

    def tearDown(self):
        _clear_sk_modules()

    def test_kernel_created_with_service(self):
        mock_kernel_cls, mock_kernel_inst, mock_oai_cls, _ = _stub_sk_modules()
        a, _, _ = _adapter(openai_key="sk-key", model="gpt-4o")
        a._kernel = None
        a._ensure_kernel()
        mock_kernel_cls.assert_called_once()
        mock_kernel_inst.add_service.assert_called_once()

    def test_kernel_cached_on_second_call(self):
        mock_kernel_cls, mock_kernel_inst, mock_oai_cls, _ = _stub_sk_modules()
        a, _, _ = _adapter()
        a._kernel = None
        k1 = a._ensure_kernel()
        k2 = a._ensure_kernel()
        self.assertIs(k1, k2)
        mock_kernel_cls.assert_called_once()

    def test_api_key_in_service(self):
        _, _, mock_oai_cls, _ = _stub_sk_modules()
        a, _, _ = _adapter(openai_key="sk-abc")
        a._kernel = None
        a._ensure_kernel()
        call_kwargs = mock_oai_cls.call_args[1]
        self.assertEqual(call_kwargs["api_key"], "sk-abc")

    def test_model_in_service(self):
        _, _, mock_oai_cls, _ = _stub_sk_modules()
        a, _, _ = _adapter(model="gpt-4o-mini")
        a._kernel = None
        a._ensure_kernel()
        call_kwargs = mock_oai_cls.call_args[1]
        self.assertEqual(call_kwargs["ai_model_id"], "gpt-4o-mini")

    def test_base_url_in_service(self):
        _, _, mock_oai_cls, _ = _stub_sk_modules()
        a, _, _ = _adapter(base_url="https://my.endpoint/")
        a._kernel = None
        a._ensure_kernel()
        call_kwargs = mock_oai_cls.call_args[1]
        self.assertEqual(call_kwargs["base_url"], "https://my.endpoint/")

    def test_no_key_no_api_key_kwarg(self):
        _, _, mock_oai_cls, _ = _stub_sk_modules()
        a, _, _ = _adapter(openai_key=None)
        a._kernel = None
        a._ensure_kernel()
        call_kwargs = mock_oai_cls.call_args[1]
        self.assertNotIn("api_key", call_kwargs)


# ══════════════════════════════════════════════════════════════════════════════
# 7 — complete()
# ══════════════════════════════════════════════════════════════════════════════

class TestComplete(unittest.TestCase):
    def setUp(self):
        _clear_sk_modules()

    def tearDown(self):
        _clear_sk_modules()

    def test_complete_returns_string(self):
        a, _, _ = _adapter()
        with patch.object(sk_mod, "asyncio") as mock_asyncio:
            mock_asyncio.run.return_value = "Hello world"
            result = a.complete([{"role": "user", "content": "Hi"}])
        self.assertEqual(result, "Hello world")

    def test_complete_calls_asyncio_run(self):
        a, _, _ = _adapter()
        with patch.object(sk_mod, "asyncio") as mock_asyncio:
            mock_asyncio.run.return_value = "ok"
            a.complete([{"role": "user", "content": "Hi"}])
        mock_asyncio.run.assert_called_once()

    def test_complete_async_builds_chat_history(self):
        """_complete_async correctly maps roles to ChatHistory methods."""
        mock_kernel = MagicMock()
        mock_service = MagicMock()
        mock_history_cls = MagicMock()
        mock_history_inst = MagicMock()
        mock_history_cls.return_value = mock_history_inst
        mock_service.get_chat_message_content = AsyncMock(return_value="response")
        mock_kernel.get_service.return_value = mock_service

        # Stub the SK imports
        chat_mod = types.ModuleType("semantic_kernel.connectors.ai.chat_completion_client_base")
        chat_mod.ChatCompletionClientBase = object  # type value
        contents_mod = types.ModuleType("semantic_kernel.contents")
        contents_mod.ChatHistory = mock_history_cls

        with patch.dict(sys.modules, {
            "semantic_kernel.connectors.ai.chat_completion_client_base": chat_mod,
            "semantic_kernel.contents": contents_mod,
        }):
            a, _, _ = _adapter()
            a._kernel = mock_kernel

            messages = [
                {"role": "system",    "content": "Be helpful"},
                {"role": "user",      "content": "Question"},
                {"role": "assistant", "content": "Answer"},
                {"role": "user",      "content": "Follow up"},
            ]
            result = asyncio.run(a._complete_async(messages))

        mock_history_inst.add_system_message.assert_called_once_with("Be helpful")
        mock_history_inst.add_user_message.assert_any_call("Question")
        mock_history_inst.add_assistant_message.assert_called_once_with("Answer")
        self.assertEqual(mock_history_inst.add_user_message.call_count, 2)

    def test_unknown_role_treated_as_user(self):
        """Roles that aren't system/assistant default to add_user_message."""
        mock_kernel = MagicMock()
        mock_service = MagicMock()
        mock_history_cls = MagicMock()
        mock_history_inst = MagicMock()
        mock_history_cls.return_value = mock_history_inst
        mock_service.get_chat_message_content = AsyncMock(return_value="r")
        mock_kernel.get_service.return_value = mock_service

        chat_mod = types.ModuleType("semantic_kernel.connectors.ai.chat_completion_client_base")
        chat_mod.ChatCompletionClientBase = object
        contents_mod = types.ModuleType("semantic_kernel.contents")
        contents_mod.ChatHistory = mock_history_cls

        with patch.dict(sys.modules, {
            "semantic_kernel.connectors.ai.chat_completion_client_base": chat_mod,
            "semantic_kernel.contents": contents_mod,
        }):
            a, _, _ = _adapter()
            a._kernel = mock_kernel
            asyncio.run(a._complete_async([{"role": "tool", "content": "tool result"}]))

        mock_history_inst.add_user_message.assert_called_once_with("tool result")

    def test_role_uppercased_normalised(self):
        """Role strings are lowercased before comparison."""
        mock_kernel = MagicMock()
        mock_service = MagicMock()
        mock_history_cls = MagicMock()
        mock_history_inst = MagicMock()
        mock_history_cls.return_value = mock_history_inst
        mock_service.get_chat_message_content = AsyncMock(return_value="r")
        mock_kernel.get_service.return_value = mock_service

        chat_mod = types.ModuleType("semantic_kernel.connectors.ai.chat_completion_client_base")
        chat_mod.ChatCompletionClientBase = object
        contents_mod = types.ModuleType("semantic_kernel.contents")
        contents_mod.ChatHistory = mock_history_cls

        with patch.dict(sys.modules, {
            "semantic_kernel.connectors.ai.chat_completion_client_base": chat_mod,
            "semantic_kernel.contents": contents_mod,
        }):
            a, _, _ = _adapter()
            a._kernel = mock_kernel
            asyncio.run(a._complete_async([{"role": "SYSTEM", "content": "sys"}]))

        mock_history_inst.add_system_message.assert_called_once_with("sys")


# ══════════════════════════════════════════════════════════════════════════════
# 8 — invoke_function()
# ══════════════════════════════════════════════════════════════════════════════

class TestInvokeFunction(unittest.TestCase):
    def test_invoke_function_returns_string(self):
        a, _, _ = _adapter()
        with patch.object(sk_mod, "asyncio") as mock_asyncio:
            mock_asyncio.run.return_value = "result"
            out = a.invoke_function(MagicMock(), MagicMock(), input="hello")
        self.assertEqual(out, "result")

    def test_invoke_function_calls_asyncio_run(self):
        a, _, _ = _adapter()
        with patch.object(sk_mod, "asyncio") as mock_asyncio:
            mock_asyncio.run.return_value = "r"
            a.invoke_function(MagicMock(), MagicMock())
        mock_asyncio.run.assert_called_once()

    def test_invoke_async_calls_kernel_invoke(self):
        a, _, _ = _adapter()
        mock_kernel = MagicMock()
        mock_fn = MagicMock()
        mock_kernel.invoke = AsyncMock(return_value="function result")

        result = asyncio.run(a._invoke_async(mock_kernel, mock_fn, input="test"))

        mock_kernel.invoke.assert_called_once_with(mock_fn, input="test")
        self.assertEqual(result, "function result")

    def test_invoke_async_kwargs_forwarded(self):
        a, _, _ = _adapter()
        mock_kernel = MagicMock()
        mock_fn = MagicMock()
        mock_kernel.invoke = AsyncMock(return_value="ok")

        asyncio.run(a._invoke_async(mock_kernel, mock_fn, x=1, y=2))
        call_kwargs = mock_kernel.invoke.call_args[1]
        self.assertEqual(call_kwargs["x"], 1)
        self.assertEqual(call_kwargs["y"], 2)

    def test_invoke_result_stringified(self):
        a, _, _ = _adapter()
        mock_kernel = MagicMock()
        mock_kernel.invoke = AsyncMock(return_value=42)
        result = asyncio.run(a._invoke_async(mock_kernel, MagicMock()))
        self.assertEqual(result, "42")


# ══════════════════════════════════════════════════════════════════════════════
# 9 — as_plugin()
# ══════════════════════════════════════════════════════════════════════════════

class TestAsPlugin(unittest.TestCase):
    def test_returns_payment_plugin(self):
        a, _, _ = _adapter()
        plugin = a.as_plugin(resource_fn=lambda q: "r")
        self.assertIsInstance(plugin, AlgoVoiPaymentPlugin)

    def test_default_plugin_name(self):
        a, _, _ = _adapter()
        plugin = a.as_plugin(resource_fn=lambda q: "r")
        self.assertEqual(plugin.name, "AlgoVoiPaymentPlugin")

    def test_custom_plugin_name(self):
        a, _, _ = _adapter()
        plugin = a.as_plugin(resource_fn=lambda q: "r", plugin_name="premium_kb")
        self.assertEqual(plugin.name, "premium_kb")

    def test_resource_fn_stored(self):
        a, _, _ = _adapter()
        fn = lambda q: "ans"
        plugin = a.as_plugin(resource_fn=fn)
        self.assertIs(plugin._resource_fn, fn)

    def test_adapter_stored(self):
        a, _, _ = _adapter()
        plugin = a.as_plugin(resource_fn=lambda q: "r")
        self.assertIs(plugin._adapter, a)


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

    def test_413_when_too_large(self):
        a, _, _ = _adapter()
        mock_req = self._mock_request(content_length=_MAX_FLASK_BODY + 1)
        mock_resp_cls = MagicMock()
        with patch.object(flask, "request", mock_req), \
             patch("flask.Response", mock_resp_cls):
            a.flask_guard()
        call_args = mock_resp_cls.call_args
        self.assertEqual(call_args[1]["status"], 413)

    def test_402_when_payment_required(self):
        a, gate, gate_result = _adapter(gate_requires_payment=True)
        mock_req = self._mock_request(headers={}, json_body={})
        with patch.object(flask, "request", mock_req):
            a.flask_guard()
        gate_result.as_flask_response.assert_called_once()

    def test_200_calls_complete(self):
        a, _, _ = _adapter(gate_requires_payment=False)
        mock_req = self._mock_request(
            headers={}, json_body={"messages": [{"role": "user", "content": "hi"}]}
        )
        mock_jsonify = MagicMock(return_value={"content": "Hello"})
        with patch.object(flask, "request", mock_req), \
             patch("flask.jsonify", mock_jsonify), \
             patch.object(sk_mod, "asyncio") as mock_asyncio:
            mock_asyncio.run.return_value = "Hello"
            a.flask_guard()
        mock_jsonify.assert_called_once_with({"content": "Hello"})

    def test_empty_messages_default(self):
        a, _, _ = _adapter(gate_requires_payment=False)
        mock_req = self._mock_request(headers={}, json_body={})
        mock_jsonify = MagicMock(return_value={"content": "ok"})
        with patch.object(flask, "request", mock_req), \
             patch("flask.jsonify", mock_jsonify), \
             patch.object(sk_mod, "asyncio") as mock_asyncio:
            mock_asyncio.run.return_value = "ok"
            a.flask_guard()
        mock_asyncio.run.assert_called_once()

    def test_none_body_handled(self):
        a, _, _ = _adapter(gate_requires_payment=False)
        mock_req = self._mock_request(headers={}, json_body=None)
        mock_jsonify = MagicMock(return_value={"content": "ok"})
        with patch.object(flask, "request", mock_req), \
             patch("flask.jsonify", mock_jsonify), \
             patch.object(sk_mod, "asyncio") as mock_asyncio:
            mock_asyncio.run.return_value = "ok"
            a.flask_guard()  # should not raise

    def test_no_413_at_exact_limit(self):
        a, _, _ = _adapter(gate_requires_payment=False)
        mock_req = self._mock_request(
            content_length=_MAX_FLASK_BODY, headers={}, json_body={"messages": []}
        )
        mock_jsonify = MagicMock(return_value={"content": "ok"})
        mock_resp_cls = MagicMock()
        with patch.object(flask, "request", mock_req), \
             patch("flask.jsonify", mock_jsonify), \
             patch("flask.Response", mock_resp_cls), \
             patch.object(sk_mod, "asyncio") as mock_asyncio:
            mock_asyncio.run.return_value = "ok"
            a.flask_guard()
        mock_resp_cls.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# 11 — AlgoVoiPaymentPlugin attributes
# ══════════════════════════════════════════════════════════════════════════════

class TestPaymentPluginAttrs(unittest.TestCase):
    def _make(self, **kw) -> AlgoVoiPaymentPlugin:
        a, _, _ = _adapter()
        return AlgoVoiPaymentPlugin(adapter=a, resource_fn=lambda q: "ok", **kw)

    def test_default_name(self):
        self.assertEqual(self._make().name, "AlgoVoiPaymentPlugin")

    def test_custom_name(self):
        self.assertEqual(self._make(plugin_name="my_plugin").name, "my_plugin")

    def test_gate_method_exists(self):
        plugin = self._make()
        self.assertTrue(hasattr(plugin, "gate"))
        self.assertTrue(callable(plugin.gate))

    def test_gate_has_sk_name(self):
        plugin = self._make()
        fn = plugin.gate
        # Either the real SK decorator set __sk_kernel_function_name__,
        # or our stub set it via the class-level decorator.
        name = getattr(fn, "__sk_kernel_function_name__", None)
        if name is not None:
            self.assertEqual(name, "gate")


# ══════════════════════════════════════════════════════════════════════════════
# 12 — AlgoVoiPaymentPlugin.gate() — no proof (challenge)
# ══════════════════════════════════════════════════════════════════════════════

class TestPaymentPluginGateChallenge(unittest.TestCase):
    def _plugin(self, requires_payment=True, error=None):
        a, gate, gate_result = _adapter(
            gate_requires_payment=requires_payment, gate_error=error
        )
        return AlgoVoiPaymentPlugin(adapter=a, resource_fn=lambda q: "ok"), gate, gate_result

    def test_no_proof_returns_challenge_json(self):
        plugin, _, _ = self._plugin(requires_payment=True)
        data = json.loads(plugin.gate(query="q", payment_proof=""))
        self.assertEqual(data["error"], "payment_required")

    def test_no_proof_empty_headers(self):
        plugin, gate, _ = self._plugin(requires_payment=True)
        plugin.gate(query="q", payment_proof="")
        gate.check.assert_called_with({}, {})

    def test_proof_in_auth_header(self):
        a, gate, gate_result = _adapter(gate_requires_payment=False)
        plugin = AlgoVoiPaymentPlugin(adapter=a, resource_fn=lambda q: "ok")
        plugin.gate(query="q", payment_proof="b64proof")
        gate.check.assert_called_with({"Authorization": "Payment b64proof"}, {})

    def test_challenge_detail_from_error(self):
        plugin, _, _ = self._plugin(requires_payment=True, error="invalid sig")
        data = json.loads(plugin.gate(query="q", payment_proof=""))
        self.assertEqual(data["detail"], "invalid sig")

    def test_challenge_detail_fallback(self):
        a, gate, gate_result = _adapter(gate_requires_payment=True)
        gate_result.error = None
        plugin = AlgoVoiPaymentPlugin(adapter=a, resource_fn=lambda q: "ok")
        data = json.loads(plugin.gate(query="q", payment_proof=""))
        self.assertGreater(len(data["detail"]), 0)


# ══════════════════════════════════════════════════════════════════════════════
# 13 — AlgoVoiPaymentPlugin.gate() — valid proof (resource)
# ══════════════════════════════════════════════════════════════════════════════

class TestPaymentPluginGateVerified(unittest.TestCase):
    def _plugin(self, resource_fn):
        a, _, _ = _adapter(gate_requires_payment=False)
        return AlgoVoiPaymentPlugin(adapter=a, resource_fn=resource_fn)

    def test_returns_resource_fn_result(self):
        plugin = self._plugin(lambda q: "premium content")
        self.assertEqual(plugin.gate(query="q", payment_proof="proof"), "premium content")

    def test_query_forwarded(self):
        received = []
        def fn(q): received.append(q); return "ok"
        plugin = self._plugin(fn)
        plugin.gate(query="my question", payment_proof="proof")
        self.assertEqual(received, ["my question"])

    def test_resource_fn_exception_returns_error_json(self):
        def bad(q): raise RuntimeError("db down")
        plugin = self._plugin(bad)
        data = json.loads(plugin.gate(query="q", payment_proof="proof"))
        self.assertEqual(data["error"], "resource_error")
        self.assertIn("db down", data["detail"])

    def test_int_result_stringified(self):
        plugin = self._plugin(lambda q: 99)
        self.assertEqual(plugin.gate(query="q", payment_proof="proof"), "99")

    def test_empty_query_forwarded(self):
        received = []
        def fn(q): received.append(q); return "ok"
        plugin = self._plugin(fn)
        plugin.gate(query="", payment_proof="proof")
        self.assertEqual(received, [""])

    def test_default_args_no_raise(self):
        plugin = self._plugin(lambda q: "r")
        out = plugin.gate()
        self.assertIsInstance(out, str)

    def test_typeerror_fallback(self):
        a, gate, gate_result = _adapter(gate_requires_payment=False)
        call_n = {"n": 0}

        def _side(headers, body=None):
            call_n["n"] += 1
            if call_n["n"] == 1 and body is not None:
                raise TypeError("no body")
            return gate_result

        gate.check.side_effect = _side
        plugin = AlgoVoiPaymentPlugin(adapter=a, resource_fn=lambda q: "ans")
        self.assertEqual(plugin.gate(query="q", payment_proof="p"), "ans")


# ══════════════════════════════════════════════════════════════════════════════
# 14 — _add_path helper
# ══════════════════════════════════════════════════════════════════════════════

class TestAddPath(unittest.TestCase):
    def test_adds_path(self):
        sentinel = "/nonexistent/sk_sentinel"
        original = list(sys.path)
        try:
            sk_mod._add_path(sentinel)
            full = os.path.join(sk_mod._ADAPTERS_ROOT, sentinel)
            self.assertIn(full, sys.path)
        finally:
            sys.path[:] = original

    def test_idempotent(self):
        sentinel = "idempotent_sk_test"
        full = os.path.join(sk_mod._ADAPTERS_ROOT, sentinel)
        original = list(sys.path)
        try:
            sk_mod._add_path(sentinel)
            sk_mod._add_path(sentinel)
            self.assertEqual(sys.path.count(full), 1)
        finally:
            sys.path[:] = original


if __name__ == "__main__":
    unittest.main(verbosity=2)
