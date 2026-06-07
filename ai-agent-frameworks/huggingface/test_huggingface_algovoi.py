"""
Unit tests for huggingface_algovoi — all mocked, no live network calls.

Run:
    cd ai-agent-frameworks/huggingface
    python -m pytest test_huggingface_algovoi.py -v
"""

from __future__ import annotations

import json
import sys
import types
import unittest
from typing import Any
from unittest.mock import MagicMock, patch, PropertyMock


# ── inject stub modules before importing adapter ───────────────────────────────

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
    parent = types.ModuleType("openai_algovoi")
    parent._X402Gate = MagicMock(return_value=gate)
    sys.modules["openai_algovoi"] = parent


def _clear_gate_stubs():
    for k in ("mpp", "ap2", "openai_algovoi"):
        sys.modules.pop(k, None)


# pre-stub gate modules so the adapter can import
_g_default, _ = _make_gate()
_stub_mpp(_g_default)
_stub_ap2(_g_default)
_stub_x402(_g_default)

# stub smolagents so no install needed
_smolagents_mod = types.ModuleType("smolagents")

class _FakeTool:
    name: str = ""
    description: str = ""
    inputs: dict = {}
    output_type: str = "string"

    def __init__(self) -> None:
        pass

    def forward(self, **kwargs: Any) -> str:
        raise NotImplementedError

_smolagents_mod.Tool = _FakeTool
sys.modules["smolagents"] = _smolagents_mod

# stub huggingface_hub so no install needed
_hfhub_mod = types.ModuleType("huggingface_hub")
_hfhub_mod.InferenceClient = MagicMock()
sys.modules["huggingface_hub"] = _hfhub_mod

import flask  # noqa: E402
import importlib, os  # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

import huggingface_algovoi as hf_mod  # noqa: E402
from huggingface_algovoi import (  # noqa: E402
    AlgoVoiHuggingFace,
    AlgoVoiPaymentTool,
    HuggingFaceResult,
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
    hf_token: str | None = "hf_tok",
    model: str = "meta-llama/Meta-Llama-3-8B-Instruct",
    base_url: str | None = None,
    resource_id: str = "ai-inference",
) -> tuple[AlgoVoiHuggingFace, MagicMock, MagicMock]:
    gate, gate_result = _make_gate(gate_requires_payment, gate_error)
    _stub_mpp(gate)
    _stub_ap2(gate)
    _stub_x402(gate)
    a = AlgoVoiHuggingFace(
        algovoi_key="algv_test",
        tenant_id="tid",
        payout_address="ADDR",
        hf_token=hf_token,
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
        self.assertEqual(hf_mod.__version__, "1.0.0")

    def test_all_exports(self):
        self.assertIn("AlgoVoiHuggingFace", hf_mod.__all__)
        self.assertIn("AlgoVoiPaymentTool", hf_mod.__all__)
        self.assertIn("HuggingFaceResult", hf_mod.__all__)

    def test_networks(self):
        self.assertIn("algorand-mainnet", NETWORKS)
        self.assertIn("voi-mainnet", NETWORKS)
        self.assertIn("hedera-mainnet", NETWORKS)
        self.assertIn("stellar-mainnet", NETWORKS)

    def test_protocols(self):
        self.assertEqual(PROTOCOLS, frozenset({"mpp", "ap2", "x402"}))

    def test_body_cap(self):
        self.assertEqual(_MAX_FLASK_BODY, 1_048_576)


# ══════════════════════════════════════════════════════════════════════════════
# 2 — HuggingFaceResult wrapper
# ══════════════════════════════════════════════════════════════════════════════

class TestHuggingFaceResult(unittest.TestCase):
    def _make(self, **kw) -> HuggingFaceResult:
        raw = MagicMock()
        for k, v in kw.items():
            setattr(raw, k, v)
        return HuggingFaceResult(raw)

    def test_requires_payment_true(self):
        r = self._make(requires_payment=True)
        self.assertTrue(r.requires_payment)

    def test_requires_payment_false(self):
        r = self._make(requires_payment=False)
        self.assertFalse(r.requires_payment)

    def test_error_attr(self):
        r = self._make(requires_payment=False, error="bad proof")
        self.assertEqual(r.error, "bad proof")

    def test_error_missing(self):
        raw = MagicMock(spec=["requires_payment"])
        raw.requires_payment = False
        r = HuggingFaceResult(raw)
        self.assertIsNone(r.error)

    def test_receipt(self):
        r = self._make(requires_payment=False, receipt="rcpt")
        self.assertEqual(r.receipt, "rcpt")

    def test_mandate(self):
        r = self._make(requires_payment=False, mandate={"url": "x"})
        self.assertEqual(r.mandate, {"url": "x"})

    def test_as_flask_response(self):
        raw = MagicMock()
        raw.as_flask_response.return_value = ("body", 402)
        r = HuggingFaceResult(raw)
        self.assertEqual(r.as_flask_response(), ("body", 402))

    def test_as_wsgi_response(self):
        raw = MagicMock()
        raw.as_wsgi_response.return_value = (402, [], b"pay")
        r = HuggingFaceResult(raw)
        self.assertEqual(r.as_wsgi_response(), (402, [], b"pay"))


# ══════════════════════════════════════════════════════════════════════════════
# 3 — _build_gate() — protocol routing
# ══════════════════════════════════════════════════════════════════════════════

class TestBuildGate(unittest.TestCase):
    def test_mpp_gate_created(self):
        gate, gate_result = _make_gate()
        mock_cls = MagicMock(return_value=gate)
        mod = types.ModuleType("mpp")
        mod.MppGate = mock_cls
        sys.modules["mpp"] = mod
        AlgoVoiHuggingFace(
            algovoi_key="k", tenant_id="t", payout_address="a",
            protocol="mpp", network="algorand-mainnet",
        )
        mock_cls.assert_called_once()

    def test_ap2_gate_created(self):
        gate, gate_result = _make_gate()
        mock_cls = MagicMock(return_value=gate)
        mod = types.ModuleType("ap2")
        mod.Ap2Gate = mock_cls
        sys.modules["ap2"] = mod
        AlgoVoiHuggingFace(
            algovoi_key="k", tenant_id="t", payout_address="a",
            protocol="ap2", network="algorand-mainnet",
        )
        mock_cls.assert_called_once()

    def test_x402_gate_created(self):
        gate, gate_result = _make_gate()
        mock_cls = MagicMock(return_value=gate)
        mod = types.ModuleType("openai_algovoi")
        mod._X402Gate = mock_cls
        sys.modules["openai_algovoi"] = mod
        AlgoVoiHuggingFace(
            algovoi_key="k", tenant_id="t", payout_address="a",
            protocol="x402", network="algorand-mainnet",
        )
        mock_cls.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
# 4 — AlgoVoiHuggingFace constructor
# ══════════════════════════════════════════════════════════════════════════════

class TestAlgoVoiHuggingFaceConstructor(unittest.TestCase):
    def test_bad_protocol_raises(self):
        with self.assertRaises(ValueError):
            AlgoVoiHuggingFace(
                algovoi_key="k", tenant_id="t", payout_address="a",
                protocol="bad",
            )

    def test_bad_network_raises(self):
        with self.assertRaises(ValueError):
            AlgoVoiHuggingFace(
                algovoi_key="k", tenant_id="t", payout_address="a",
                network="ethereum-mainnet",
            )

    def test_all_valid_networks(self):
        for net in NETWORKS:
            a, _, _ = _adapter(network=net)
            self.assertIsNotNone(a)

    def test_all_valid_protocols(self):
        for proto in PROTOCOLS:
            a, _, _ = _adapter(protocol=proto)
            self.assertIsNotNone(a)

    def test_default_model(self):
        a, _, _ = _adapter()
        self.assertEqual(a._model, "meta-llama/Meta-Llama-3-8B-Instruct")

    def test_custom_model(self):
        a, _, _ = _adapter(model="HuggingFaceH4/zephyr-7b-beta")
        self.assertEqual(a._model, "HuggingFaceH4/zephyr-7b-beta")

    def test_hf_token_stored(self):
        a, _, _ = _adapter(hf_token="hf_abc")
        self.assertEqual(a._hf_token, "hf_abc")

    def test_base_url_stored(self):
        a, _, _ = _adapter(base_url="https://my.endpoint/")
        self.assertEqual(a._base_url, "https://my.endpoint/")

    def test_client_starts_none(self):
        a, _, _ = _adapter()
        self.assertIsNone(a._client)


# ══════════════════════════════════════════════════════════════════════════════
# 5 — check()
# ══════════════════════════════════════════════════════════════════════════════

class TestCheck(unittest.TestCase):
    def test_returns_huggingface_result(self):
        a, _, _ = _adapter()
        r = a.check({"X-Payment": "tok"}, {})
        self.assertIsInstance(r, HuggingFaceResult)

    def test_requires_payment_false(self):
        a, _, _ = _adapter(gate_requires_payment=False)
        r = a.check({}, {})
        self.assertFalse(r.requires_payment)

    def test_requires_payment_true(self):
        a, _, _ = _adapter(gate_requires_payment=True)
        r = a.check({}, {})
        self.assertTrue(r.requires_payment)

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
        gate.check.side_effect = [TypeError("no body"), gate.check.return_value]
        gate.check.side_effect = None
        # simulate TypeError on first call
        call_count = {"n": 0}

        def _side(headers, body=None):
            call_count["n"] += 1
            if call_count["n"] == 1 and body is not None:
                raise TypeError("unexpected body arg")
            return gate.check.return_value

        gate.check.side_effect = _side
        r = a.check({"H": "v"}, {"b": 1})
        self.assertIsInstance(r, HuggingFaceResult)


# ══════════════════════════════════════════════════════════════════════════════
# 6 — _ensure_client() / complete()
# ══════════════════════════════════════════════════════════════════════════════

class TestEnsureClientAndComplete(unittest.TestCase):
    def _mock_inference_client(self, content: str = "reply"):
        mock_client_cls = MagicMock()
        mock_client = MagicMock()
        response = MagicMock()
        response.choices[0].message.content = content
        mock_client.chat_completion.return_value = response
        mock_client_cls.return_value = mock_client
        return mock_client_cls, mock_client

    def test_client_created_with_token(self):
        a, _, _ = _adapter(hf_token="hf_tok123")
        mock_cls, mock_client = self._mock_inference_client()
        mod = types.ModuleType("huggingface_hub")
        mod.InferenceClient = mock_cls
        with patch.dict(sys.modules, {"huggingface_hub": mod}):
            a._client = None
            client = a._ensure_client()
        mock_cls.assert_called_once()
        call_kwargs = mock_cls.call_args[1]
        self.assertEqual(call_kwargs["token"], "hf_tok123")

    def test_client_created_with_model(self):
        a, _, _ = _adapter(model="HuggingFaceH4/zephyr-7b-beta")
        mock_cls, mock_client = self._mock_inference_client()
        mod = types.ModuleType("huggingface_hub")
        mod.InferenceClient = mock_cls
        with patch.dict(sys.modules, {"huggingface_hub": mod}):
            a._client = None
            a._ensure_client()
        call_kwargs = mock_cls.call_args[1]
        self.assertEqual(call_kwargs["model"], "HuggingFaceH4/zephyr-7b-beta")

    def test_client_created_with_base_url(self):
        a, _, _ = _adapter(base_url="https://custom.endpoint/")
        mock_cls, mock_client = self._mock_inference_client()
        mod = types.ModuleType("huggingface_hub")
        mod.InferenceClient = mock_cls
        with patch.dict(sys.modules, {"huggingface_hub": mod}):
            a._client = None
            a._ensure_client()
        call_kwargs = mock_cls.call_args[1]
        self.assertEqual(call_kwargs["base_url"], "https://custom.endpoint/")

    def test_client_cached_on_second_call(self):
        a, _, _ = _adapter()
        mock_cls, mock_client = self._mock_inference_client()
        mod = types.ModuleType("huggingface_hub")
        mod.InferenceClient = mock_cls
        with patch.dict(sys.modules, {"huggingface_hub": mod}):
            a._client = None
            c1 = a._ensure_client()
            c2 = a._ensure_client()
        self.assertIs(c1, c2)
        mock_cls.assert_called_once()  # only one construction

    def test_complete_returns_content(self):
        a, _, _ = _adapter()
        mock_cls, mock_client = self._mock_inference_client("Hello world")
        a._client = mock_client
        result = a.complete([{"role": "user", "content": "Hi"}])
        self.assertEqual(result, "Hello world")
        mock_client.chat_completion.assert_called_once_with(
            messages=[{"role": "user", "content": "Hi"}]
        )

    def test_complete_passes_messages_through(self):
        a, _, _ = _adapter()
        mock_cls, mock_client = self._mock_inference_client("ok")
        a._client = mock_client
        msgs = [
            {"role": "system", "content": "Be helpful"},
            {"role": "user", "content": "Question"},
        ]
        a.complete(msgs)
        call_args = mock_client.chat_completion.call_args[1]
        self.assertEqual(call_args["messages"], msgs)

    def test_no_token_no_token_kwarg(self):
        a, _, _ = _adapter(hf_token=None)
        mock_cls, mock_client = self._mock_inference_client()
        mod = types.ModuleType("huggingface_hub")
        mod.InferenceClient = mock_cls
        with patch.dict(sys.modules, {"huggingface_hub": mod}):
            a._client = None
            a._ensure_client()
        call_kwargs = mock_cls.call_args[1]
        self.assertNotIn("token", call_kwargs)


# ══════════════════════════════════════════════════════════════════════════════
# 7 — inference_pipeline()
# ══════════════════════════════════════════════════════════════════════════════

class TestInferencePipeline(unittest.TestCase):
    def _run(self, pipe_output):
        a, _, _ = _adapter()
        mock_pipe = MagicMock(return_value=pipe_output)
        return a.inference_pipeline(mock_pipe, "input text")

    def test_chat_format_output(self):
        # pipeline returns list of dicts where generated_text is a list (chat template)
        result = self._run([{"generated_text": [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello there"},
        ]}])
        self.assertEqual(result, "Hello there")

    def test_plain_string_generated_text(self):
        # pipeline returns list of dicts where generated_text is a plain string
        result = self._run([{"generated_text": "The answer is 42"}])
        self.assertEqual(result, "The answer is 42")

    def test_empty_list_result(self):
        result = self._run([])
        self.assertEqual(result, "[]")

    def test_string_result(self):
        result = self._run("just a string")
        self.assertEqual(result, "just a string")

    def test_non_dict_first_element(self):
        result = self._run(["text output"])
        self.assertEqual(result, "['text output']")

    def test_empty_chat_format_list(self):
        # generated_text is an empty list — falls through to str(generated)
        result = self._run([{"generated_text": []}])
        self.assertEqual(result, "[]")

    def test_missing_content_key(self):
        result = self._run([{"generated_text": [
            {"role": "assistant"}  # no "content" key
        ]}])
        self.assertEqual(result, "")

    def test_input_passed_to_pipe(self):
        a, _, _ = _adapter()
        mock_pipe = MagicMock(return_value=["output"])
        a.inference_pipeline(mock_pipe, [{"role": "user", "content": "q"}])
        mock_pipe.assert_called_once_with([{"role": "user", "content": "q"}])


# ══════════════════════════════════════════════════════════════════════════════
# 8 — as_tool()
# ══════════════════════════════════════════════════════════════════════════════

class TestAsTool(unittest.TestCase):
    def test_returns_payment_tool(self):
        a, _, _ = _adapter()
        tool = a.as_tool(resource_fn=lambda q: "result")
        self.assertIsInstance(tool, AlgoVoiPaymentTool)

    def test_default_tool_name(self):
        a, _, _ = _adapter()
        tool = a.as_tool(resource_fn=lambda q: "r")
        self.assertEqual(tool.name, "algovoi_payment_gate")

    def test_custom_tool_name(self):
        a, _, _ = _adapter()
        tool = a.as_tool(resource_fn=lambda q: "r", tool_name="premium_search")
        self.assertEqual(tool.name, "premium_search")

    def test_custom_tool_description(self):
        a, _, _ = _adapter()
        tool = a.as_tool(
            resource_fn=lambda q: "r",
            tool_description="Search premium data",
        )
        self.assertEqual(tool.description, "Search premium data")

    def test_resource_fn_stored(self):
        a, _, _ = _adapter()
        fn = lambda q: "answer"
        tool = a.as_tool(resource_fn=fn)
        self.assertIs(tool._resource_fn, fn)

    def test_adapter_stored_in_tool(self):
        a, _, _ = _adapter()
        tool = a.as_tool(resource_fn=lambda q: "r")
        self.assertIs(tool._adapter, a)


# ══════════════════════════════════════════════════════════════════════════════
# 9 — flask_guard()
# ══════════════════════════════════════════════════════════════════════════════

class TestFlaskGuard(unittest.TestCase):
    def _mock_request(
        self,
        headers: dict | None = None,
        json_body: dict | None = None,
        content_length: int | None = None,
    ) -> MagicMock:
        req = MagicMock()
        req.headers = headers or {}
        req.get_json.return_value = json_body
        req.content_length = content_length
        return req

    def test_413_when_too_large(self):
        a, _, _ = _adapter()
        mock_req = self._mock_request(content_length=_MAX_FLASK_BODY + 1)
        mock_response_cls = MagicMock()
        mock_response_cls.return_value = MagicMock(status_code=413)
        with patch.object(flask, "request", mock_req), \
             patch("flask.Response", mock_response_cls):
            resp = a.flask_guard()
        mock_response_cls.assert_called_once()
        call_args = mock_response_cls.call_args
        self.assertEqual(call_args[1]["status"], 413)

    def test_402_when_payment_required(self):
        a, gate, gate_result = _adapter(gate_requires_payment=True)
        mock_req = self._mock_request(headers={"X-Payment": "tok"}, json_body={})
        with patch.object(flask, "request", mock_req):
            resp = a.flask_guard()
        gate_result.as_flask_response.assert_called_once()

    def test_200_calls_complete(self):
        a, _, _ = _adapter(gate_requires_payment=False)
        messages = [{"role": "user", "content": "Hi"}]
        mock_req = self._mock_request(
            headers={"X-Payment": "tok"},
            json_body={"messages": messages},
        )
        mock_client = MagicMock()
        response = MagicMock()
        response.choices[0].message.content = "Hello"
        mock_client.chat_completion.return_value = response
        a._client = mock_client

        mock_jsonify = MagicMock(return_value={"content": "Hello"})
        with patch.object(flask, "request", mock_req), \
             patch("flask.jsonify", mock_jsonify):
            a.flask_guard()
        mock_jsonify.assert_called_once_with({"content": "Hello"})

    def test_empty_messages_defaults(self):
        a, _, _ = _adapter(gate_requires_payment=False)
        mock_req = self._mock_request(
            headers={},
            json_body={},  # no "messages" key
        )
        mock_client = MagicMock()
        response = MagicMock()
        response.choices[0].message.content = "Ok"
        mock_client.chat_completion.return_value = response
        a._client = mock_client

        mock_jsonify = MagicMock(return_value={"content": "Ok"})
        with patch.object(flask, "request", mock_req), \
             patch("flask.jsonify", mock_jsonify):
            a.flask_guard()
        call_kwargs = mock_client.chat_completion.call_args[1]
        self.assertEqual(call_kwargs["messages"], [])

    def test_none_body_handled(self):
        a, _, _ = _adapter(gate_requires_payment=False)
        mock_req = self._mock_request(headers={}, json_body=None)
        mock_client = MagicMock()
        response = MagicMock()
        response.choices[0].message.content = "Ok"
        mock_client.chat_completion.return_value = response
        a._client = mock_client

        mock_jsonify = MagicMock(return_value={"content": "Ok"})
        with patch.object(flask, "request", mock_req), \
             patch("flask.jsonify", mock_jsonify):
            a.flask_guard()  # should not raise

    def test_no_413_at_exact_limit(self):
        a, _, _ = _adapter(gate_requires_payment=False)
        mock_req = self._mock_request(
            content_length=_MAX_FLASK_BODY,
            headers={},
            json_body={"messages": []},
        )
        mock_client = MagicMock()
        response = MagicMock()
        response.choices[0].message.content = "Ok"
        mock_client.chat_completion.return_value = response
        a._client = mock_client

        mock_jsonify = MagicMock(return_value={"content": "Ok"})
        mock_response_cls = MagicMock()
        with patch.object(flask, "request", mock_req), \
             patch("flask.jsonify", mock_jsonify), \
             patch("flask.Response", mock_response_cls):
            a.flask_guard()
        mock_response_cls.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# 10 — AlgoVoiPaymentTool class attributes
# ══════════════════════════════════════════════════════════════════════════════

class TestPaymentToolClassAttrs(unittest.TestCase):
    def _make_tool(self, **kw) -> AlgoVoiPaymentTool:
        gate, gate_result = _make_gate()
        _stub_mpp(gate)
        a, _, _ = _adapter()
        return AlgoVoiPaymentTool(
            adapter=a,
            resource_fn=lambda q: "ok",
            **kw,
        )

    def test_default_name(self):
        t = self._make_tool()
        self.assertEqual(t.name, "algovoi_payment_gate")

    def test_custom_name(self):
        t = self._make_tool(tool_name="my_tool")
        self.assertEqual(t.name, "my_tool")

    def test_default_description_contains_payment(self):
        t = self._make_tool()
        self.assertIn("payment", t.description.lower())

    def test_custom_description(self):
        t = self._make_tool(tool_description="My custom desc")
        self.assertEqual(t.description, "My custom desc")

    def test_inputs_has_query(self):
        t = self._make_tool()
        self.assertIn("query", t.inputs)

    def test_inputs_has_payment_proof(self):
        t = self._make_tool()
        self.assertIn("payment_proof", t.inputs)

    def test_inputs_query_type_string(self):
        t = self._make_tool()
        self.assertEqual(t.inputs["query"]["type"], "string")

    def test_inputs_payment_proof_type_string(self):
        t = self._make_tool()
        self.assertEqual(t.inputs["payment_proof"]["type"], "string")

    def test_output_type_string(self):
        t = self._make_tool()
        self.assertEqual(t.output_type, "string")


# ══════════════════════════════════════════════════════════════════════════════
# 11 — AlgoVoiPaymentTool.forward() — no proof (challenge)
# ══════════════════════════════════════════════════════════════════════════════

class TestPaymentToolForwardChallenge(unittest.TestCase):
    def _tool(self, requires_payment=True, error=None, resource_fn=None):
        a, gate, gate_result = _adapter(
            gate_requires_payment=requires_payment,
            gate_error=error,
        )
        return AlgoVoiPaymentTool(
            adapter=a,
            resource_fn=resource_fn or (lambda q: "ok"),
        )

    def test_no_proof_returns_challenge_json(self):
        tool = self._tool(requires_payment=True)
        out = tool.forward(query="question", payment_proof="")
        data = json.loads(out)
        self.assertEqual(data["error"], "payment_required")

    def test_no_proof_empty_headers(self):
        a, gate, gate_result = _adapter(gate_requires_payment=True)
        tool = AlgoVoiPaymentTool(adapter=a, resource_fn=lambda q: "ok")
        tool.forward(query="q", payment_proof="")
        gate.check.assert_called_with({}, {})

    def test_proof_passed_in_auth_header(self):
        a, gate, gate_result = _adapter(gate_requires_payment=False)
        tool = AlgoVoiPaymentTool(adapter=a, resource_fn=lambda q: "ok")
        tool.forward(query="q", payment_proof="base64proof")
        gate.check.assert_called_with(
            {"Authorization": "Payment base64proof"}, {}
        )

    def test_challenge_detail_from_error(self):
        tool = self._tool(requires_payment=True, error="invalid signature")
        out = tool.forward(query="q", payment_proof="")
        data = json.loads(out)
        self.assertEqual(data["detail"], "invalid signature")

    def test_challenge_detail_fallback_when_no_error(self):
        a, gate, gate_result = _adapter(gate_requires_payment=True)
        gate_result.error = None
        tool = AlgoVoiPaymentTool(adapter=a, resource_fn=lambda q: "ok")
        out = tool.forward(query="q", payment_proof="")
        data = json.loads(out)
        self.assertIn("detail", data)
        self.assertTrue(len(data["detail"]) > 0)


# ══════════════════════════════════════════════════════════════════════════════
# 12 — AlgoVoiPaymentTool.forward() — valid proof (resource)
# ══════════════════════════════════════════════════════════════════════════════

class TestPaymentToolForwardVerified(unittest.TestCase):
    def _tool(self, resource_fn):
        a, _, _ = _adapter(gate_requires_payment=False)
        return AlgoVoiPaymentTool(adapter=a, resource_fn=resource_fn)

    def test_returns_resource_fn_result(self):
        tool = self._tool(resource_fn=lambda q: "premium answer")
        out = tool.forward(query="my question", payment_proof="proof123")
        self.assertEqual(out, "premium answer")

    def test_query_passed_to_resource_fn(self):
        received = []
        def fn(q):
            received.append(q)
            return "ok"
        tool = self._tool(resource_fn=fn)
        tool.forward(query="the question", payment_proof="proof")
        self.assertEqual(received, ["the question"])

    def test_resource_fn_exception_returns_error_json(self):
        def bad_fn(q):
            raise ValueError("db offline")
        tool = self._tool(resource_fn=bad_fn)
        out = tool.forward(query="q", payment_proof="proof")
        data = json.loads(out)
        self.assertEqual(data["error"], "resource_error")
        self.assertIn("db offline", data["detail"])

    def test_resource_fn_int_result_stringified(self):
        tool = self._tool(resource_fn=lambda q: 42)
        out = tool.forward(query="q", payment_proof="proof")
        self.assertEqual(out, "42")

    def test_empty_query_forwarded(self):
        received = []
        def fn(q):
            received.append(q)
            return "ok"
        tool = self._tool(resource_fn=fn)
        tool.forward(query="", payment_proof="proof")
        self.assertEqual(received, [""])

    def test_default_query_empty_string(self):
        tool = self._tool(resource_fn=lambda q: "r")
        # forward() with no args should not raise
        out = tool.forward()
        self.assertIsInstance(out, str)

    def test_typeerror_fallback_in_forward(self):
        a, gate, gate_result = _adapter(gate_requires_payment=False)
        call_n = {"n": 0}

        def _side(headers, body=None):
            call_n["n"] += 1
            if call_n["n"] == 1 and body is not None:
                raise TypeError("no body")
            return gate_result

        gate.check.side_effect = _side
        tool = AlgoVoiPaymentTool(adapter=a, resource_fn=lambda q: "ans")
        out = tool.forward(query="q", payment_proof="p")
        self.assertEqual(out, "ans")


# ══════════════════════════════════════════════════════════════════════════════
# 13 — smolagents stub fallback
# ══════════════════════════════════════════════════════════════════════════════

class TestSmolAgentsStub(unittest.TestCase):
    def test_tool_subclass_works_without_smolagents(self):
        # AlgoVoiPaymentTool inherits from Tool (stub or real)
        # If smolagents not present, the stub is used — verify it still works
        a, _, _ = _adapter()
        tool = a.as_tool(resource_fn=lambda q: "ok")
        self.assertIsInstance(tool, AlgoVoiPaymentTool)
        self.assertEqual(tool.output_type, "string")

    def test_smolagents_available_flag(self):
        # We stubbed smolagents so _SMOLAGENTS_AVAILABLE should be True
        # (our stub is importable, so smolagents IS seen as available)
        # Just verify the attribute exists
        self.assertIsInstance(hf_mod._SMOLAGENTS_AVAILABLE, bool)


# ══════════════════════════════════════════════════════════════════════════════
# 14 — _add_path helper
# ══════════════════════════════════════════════════════════════════════════════

class TestAddPath(unittest.TestCase):
    def test_adds_path_to_sys(self):
        import huggingface_algovoi as hfm
        test_dir = "/nonexistent/test_path_sentinel"
        original = list(sys.path)
        try:
            hfm._add_path(test_dir)
            full = os.path.join(hfm._ADAPTERS_ROOT, test_dir)
            self.assertIn(full, sys.path)
        finally:
            sys.path[:] = original

    def test_does_not_duplicate_path(self):
        import huggingface_algovoi as hfm
        test_dir = "idempotent_sentinel"
        full = os.path.join(hfm._ADAPTERS_ROOT, test_dir)
        original = list(sys.path)
        try:
            hfm._add_path(test_dir)
            hfm._add_path(test_dir)
            self.assertEqual(sys.path.count(full), 1)
        finally:
            sys.path[:] = original


if __name__ == "__main__":
    unittest.main(verbosity=2)
