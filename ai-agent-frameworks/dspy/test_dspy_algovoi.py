"""
Unit tests for AlgoVoi DSPy adapter.
All tests are fully mocked — no live API calls, no dspy install required.
"""

from __future__ import annotations

import json
import sys
import types
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# ── Stub dspy before the adapter module is imported ───────────────────────────

def _stub_dspy_modules() -> None:
    """Inject minimal dspy stubs into sys.modules."""

    dspy = types.ModuleType("dspy")

    # Signature base class
    class _Signature:
        pass

    dspy.Signature = _Signature

    # Field descriptors — return None so class attrs can be assigned
    dspy.InputField = MagicMock(return_value=None)
    dspy.OutputField = MagicMock(return_value=None)

    # Predict module — returns a Prediction-like object with instance attrs
    class _MockPredict:
        def __init__(self, sig):
            self.sig = sig

        def __call__(self, **kwargs):
            from types import SimpleNamespace
            return SimpleNamespace(response="Mock DSPy response")

    dspy.Predict = _MockPredict

    # LM class
    class _MockLM:
        def __init__(self, model, **kwargs):
            self.model = model
            self.api_key = kwargs.get("api_key")
            self.api_base = kwargs.get("api_base")

    dspy.LM = _MockLM

    # context manager
    @contextmanager
    def _context(**kwargs):
        yield

    dspy.context = _context

    # configure (global LM setter)
    dspy.configure = MagicMock()

    sys.modules["dspy"] = dspy


_stub_dspy_modules()

import dspy_algovoi as dspy_mod  # noqa: E402
from dspy_algovoi import (  # noqa: E402
    AlgoVoiDSPy,
    AlgoVoiPaymentTool,
    DSPyResult,
    _add_path,
    _adapters_root,
    __version__,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_gate():
    """Return (mock_gate, mock_result) with requires_payment=True by default."""
    mock_gate = MagicMock()
    mock_result = MagicMock()
    mock_result.requires_payment = True
    mock_result.error = "Payment proof required"
    mock_result.as_wsgi_response.return_value = (
        402,
        [("X-Test", "v")],
        b'{"error":"payment_required"}',
    )
    mock_flask_resp = MagicMock()
    mock_flask_resp.status_code = 402
    mock_result.as_flask_response.return_value = mock_flask_resp
    mock_gate.check.return_value = mock_result
    return mock_gate, mock_result


def _stub_mpp(gate=None):
    if gate is None:
        gate, _ = _make_gate()
    mod = types.ModuleType("mpp_algovoi")
    mod.AlgoVoiMppGate = MagicMock(return_value=gate)
    sys.modules["mpp_algovoi"] = mod
    return gate


def _stub_ap2(gate=None):
    if gate is None:
        gate, _ = _make_gate()
    mod = types.ModuleType("ap2_algovoi")
    mod.AlgoVoiAp2Gate = MagicMock(return_value=gate)
    sys.modules["ap2_algovoi"] = mod
    return gate


def _stub_x402(gate=None):
    if gate is None:
        gate, _ = _make_gate()
    mod = types.ModuleType("openai_algovoi")
    mod.AlgoVoiX402Gate = MagicMock(return_value=gate)
    sys.modules["openai_algovoi"] = mod
    return gate


def _adapter(**kwargs) -> AlgoVoiDSPy:
    _stub_mpp()
    _stub_ap2()
    _stub_x402()
    defaults = dict(algovoi_key="algv_k", tenant_id="tid", payout_address="ADDR")
    defaults.update(kwargs)
    return AlgoVoiDSPy(**defaults)


# ══════════════════════════════════════════════════════════════════════════════
# Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestVersion:
    def test_version_string(self):
        assert __version__ == "1.0.0"


class TestAddPath:
    def test_adds_new_path(self):
        target = "/tmp/__algovoi_dspy_test_path__"
        original = list(sys.path)
        _add_path(target)
        assert target in sys.path
        sys.path[:] = original

    def test_deduplicates(self):
        target = "/tmp/__algovoi_dspy_dedup__"
        if target in sys.path:
            sys.path.remove(target)
        _add_path(target)
        _add_path(target)
        assert sys.path.count(target) == 1
        sys.path.remove(target)


class TestAdaptersRoot:
    def test_returns_non_empty_string(self):
        root = _adapters_root()
        assert isinstance(root, str)
        assert len(root) > 0

    def test_is_absolute_path(self):
        import os
        root = _adapters_root()
        assert os.path.isabs(root)


class TestBuildGate:
    def test_mpp_gate_created(self):
        gate, _ = _make_gate()
        mock_cls = MagicMock(return_value=gate)
        mod = types.ModuleType("mpp_algovoi")
        mod.AlgoVoiMppGate = mock_cls
        sys.modules["mpp_algovoi"] = mod
        AlgoVoiDSPy(algovoi_key="k", tenant_id="t", payout_address="a", protocol="mpp")
        mock_cls.assert_called_once()

    def test_ap2_gate_created(self):
        gate, _ = _make_gate()
        mock_cls = MagicMock(return_value=gate)
        mod = types.ModuleType("ap2_algovoi")
        mod.AlgoVoiAp2Gate = mock_cls
        sys.modules["ap2_algovoi"] = mod
        AlgoVoiDSPy(algovoi_key="k", tenant_id="t", payout_address="a", protocol="ap2")
        mock_cls.assert_called_once()

    def test_x402_gate_created(self):
        gate, _ = _make_gate()
        mock_cls = MagicMock(return_value=gate)
        mod = types.ModuleType("openai_algovoi")
        mod.AlgoVoiX402Gate = mock_cls
        sys.modules["openai_algovoi"] = mod
        AlgoVoiDSPy(algovoi_key="k", tenant_id="t", payout_address="a", protocol="x402")
        mock_cls.assert_called_once()

    def test_unknown_protocol_defaults_to_x402(self):
        gate, _ = _make_gate()
        mock_cls = MagicMock(return_value=gate)
        mod = types.ModuleType("openai_algovoi")
        mod.AlgoVoiX402Gate = mock_cls
        sys.modules["openai_algovoi"] = mod
        AlgoVoiDSPy(algovoi_key="k", tenant_id="t", payout_address="a", protocol="grpc")
        mock_cls.assert_called_once()

    def test_mpp_receives_correct_kwargs(self):
        gate, _ = _make_gate()
        mock_cls = MagicMock(return_value=gate)
        mod = types.ModuleType("mpp_algovoi")
        mod.AlgoVoiMppGate = mock_cls
        sys.modules["mpp_algovoi"] = mod
        AlgoVoiDSPy(
            algovoi_key="algv_k",
            tenant_id="my-tid",
            payout_address="MY_ADDR",
            protocol="mpp",
            network="voi-mainnet",
            amount_microunits=5000,
            resource_id="my-resource",
        )
        kw = mock_cls.call_args[1]
        assert kw["algovoi_key"] == "algv_k"
        assert kw["networks"] == ["voi-mainnet"]
        assert kw["amount_microunits"] == 5000
        assert kw["resource_id"] == "my-resource"


class TestConstructor:
    def test_defaults(self):
        a = _adapter()
        assert a._protocol == "mpp"
        assert a._network == "algorand-mainnet"
        assert a._amount_microunits == 10000
        assert a._model == "openai/gpt-4o"
        assert a._resource_id == "ai-function"
        assert a._openai_key is None
        assert a._base_url is None

    def test_model_stored(self):
        a = _adapter(model="anthropic/claude-opus-4-5")
        assert a._model == "anthropic/claude-opus-4-5"

    def test_openai_key_stored(self):
        a = _adapter(openai_key="sk-test")
        assert a._openai_key == "sk-test"

    def test_base_url_stored(self):
        a = _adapter(base_url="https://api.groq.com/openai/v1")
        assert a._base_url == "https://api.groq.com/openai/v1"

    def test_custom_network(self):
        a = _adapter(network="stellar-mainnet")
        assert a._network == "stellar-mainnet"

    def test_custom_amount(self):
        a = _adapter(amount_microunits=25000)
        assert a._amount_microunits == 25000

    def test_protocol_ap2(self):
        a = _adapter(protocol="ap2")
        assert a._protocol == "ap2"

    def test_gate_assigned(self):
        a = _adapter()
        assert a._gate is not None


class TestDSPyResult:
    def test_requires_payment_true(self):
        r = DSPyResult(requires_payment=True, error="no proof")
        assert r.requires_payment is True
        assert r.error == "no proof"

    def test_requires_payment_false(self):
        r = DSPyResult(requires_payment=False)
        assert r.requires_payment is False
        assert r.error == ""

    def test_as_wsgi_delegates_to_gate_result(self):
        gate_res = MagicMock()
        gate_res.as_wsgi_response.return_value = (402, [], b'{"error":"x"}')
        r = DSPyResult(requires_payment=True, gate=gate_res)
        status, _, body = r.as_wsgi_response()
        assert status == 402
        assert b"error" in body

    def test_as_wsgi_fallback_no_gate(self):
        r = DSPyResult(requires_payment=True, error="fail")
        status, _, body = r.as_wsgi_response()
        assert status == 402
        data = json.loads(body)
        assert "error" in data

    def test_as_wsgi_fallback_default_message(self):
        r = DSPyResult(requires_payment=True)
        _, _, body = r.as_wsgi_response()
        assert json.loads(body)["error"] == "Payment required"

    def test_as_flask_response_status(self):
        import flask
        app = flask.Flask("test_dspy_result")
        with app.app_context():
            gate_res = MagicMock()
            gate_res.as_wsgi_response.return_value = (402, [], b'{"error":"pay"}')
            r = DSPyResult(requires_payment=True, gate=gate_res)
            resp = r.as_flask_response()
            assert resp.status_code == 402


class TestCheck:
    def test_requires_payment_true(self):
        gate, gate_result = _make_gate()
        a = _adapter()
        a._gate = gate
        result = a.check({}, {})
        assert result.requires_payment is True

    def test_payment_verified(self):
        gate, gate_result = _make_gate()
        gate_result.requires_payment = False
        gate_result.error = ""
        a = _adapter()
        a._gate = gate
        result = a.check({"Authorization": "Payment proof123"}, {})
        assert result.requires_payment is False

    def test_error_propagated(self):
        gate, gate_result = _make_gate()
        gate_result.error = "Bad proof"
        a = _adapter()
        a._gate = gate
        result = a.check({}, {})
        assert result.error == "Bad proof"

    def test_gate_called_with_headers(self):
        gate, _ = _make_gate()
        a = _adapter()
        a._gate = gate
        a.check({"X-Custom": "val"}, {})
        call_headers = gate.check.call_args[0][0]
        assert call_headers.get("X-Custom") == "val"

    def test_body_none_defaults_to_empty_dict(self):
        gate, gate_result = _make_gate()
        gate_result.requires_payment = False
        gate_result.error = ""
        a = _adapter()
        a._gate = gate
        result = a.check({})
        assert isinstance(result, DSPyResult)

    def test_type_error_fallback(self):
        gate = MagicMock()
        gate_result = MagicMock()
        gate_result.requires_payment = True
        gate_result.error = ""
        gate.check.side_effect = [TypeError("no kw"), gate_result]
        a = _adapter()
        a._gate = gate
        result = a.check({})
        assert result.requires_payment is True

    def test_missing_error_attr_defaults_to_empty(self):
        gate = MagicMock()
        gate_result = MagicMock(spec=[])  # no error attr
        gate_result.requires_payment = True
        gate.check.return_value = gate_result
        a = _adapter()
        a._gate = gate
        result = a.check({}, {})
        assert result.error == ""


class TestEnsureLm:
    def test_returns_lm_instance(self):
        a = _adapter()
        lm = a._ensure_lm()
        assert lm is not None

    def test_model_passed_to_lm(self):
        a = _adapter(model="openai/gpt-3.5-turbo")
        lm = a._ensure_lm()
        assert lm.model == "openai/gpt-3.5-turbo"

    def test_api_key_passed_when_set(self):
        a = _adapter(openai_key="sk-my-key")
        lm = a._ensure_lm()
        assert lm.api_key == "sk-my-key"

    def test_api_base_passed_when_set(self):
        a = _adapter(base_url="https://api.groq.com/openai/v1")
        lm = a._ensure_lm()
        assert lm.api_base == "https://api.groq.com/openai/v1"

    def test_no_api_key_when_not_set(self):
        a = _adapter()
        lm = a._ensure_lm()
        assert lm.api_key is None


class TestComplete:
    def test_returns_string(self):
        a = _adapter()
        result = a.complete([{"role": "user", "content": "Hello"}])
        assert isinstance(result, str)

    def test_system_role_sets_docstring(self):
        a = _adapter()
        captured_doc = {}

        original_predict = sys.modules["dspy"].Predict

        class _TrackingPredict:
            def __init__(self, sig):
                self.sig = sig
                captured_doc["doc"] = sig.__doc__

            def __call__(self, **kwargs):
                return SimpleNamespace(response="ok")

        with patch.dict(sys.modules["dspy"].__dict__, {"Predict": _TrackingPredict}):
            a.complete([
                {"role": "system", "content": "Be brief"},
                {"role": "user", "content": "Hi"},
            ])

        assert captured_doc.get("doc") == "Be brief"

    def test_default_system_prompt_when_no_system_role(self):
        a = _adapter()
        captured_doc = {}

        class _TrackingPredict:
            def __init__(self, sig):
                captured_doc["doc"] = sig.__doc__
            def __call__(self, **kwargs):
                return SimpleNamespace(response="ok")

        with patch.dict(sys.modules["dspy"].__dict__, {"Predict": _TrackingPredict}):
            a.complete([{"role": "user", "content": "Hello"}])

        assert "helpful" in captured_doc.get("doc", "").lower()

    def test_user_message_in_prompt(self):
        a = _adapter()
        captured_prompt = {}

        class _TrackingPredict:
            def __init__(self, sig):
                pass
            def __call__(self, **kwargs):
                captured_prompt.update(kwargs)
                return SimpleNamespace(response="ok")

        with patch.dict(sys.modules["dspy"].__dict__, {"Predict": _TrackingPredict}):
            a.complete([{"role": "user", "content": "my question"}])

        assert "my question" in captured_prompt.get("prompt", "")

    def test_assistant_role_prefixed(self):
        a = _adapter()
        captured = {}

        class _TrackingPredict:
            def __init__(self, sig):
                pass
            def __call__(self, **kwargs):
                captured.update(kwargs)
                return SimpleNamespace(response="ok")

        with patch.dict(sys.modules["dspy"].__dict__, {"Predict": _TrackingPredict}):
            a.complete([{"role": "assistant", "content": "prev answer"}])

        assert "Assistant" in captured.get("prompt", "")

    def test_empty_messages_returns_string(self):
        a = _adapter()
        result = a.complete([])
        assert isinstance(result, str)


class TestRunModule:
    def test_calls_module_with_kwargs(self):
        a = _adapter()
        mock_module = MagicMock(return_value=SimpleNamespace(answer="42"))
        a.run_module(mock_module, question="What is 2+2?")
        mock_module.assert_called_once_with(question="What is 2+2?")

    def test_returns_string(self):
        a = _adapter()
        mock_module = MagicMock(return_value=SimpleNamespace(answer="hello"))
        result = a.run_module(mock_module, question="hi")
        assert isinstance(result, str)

    def test_extracts_first_string_field(self):
        a = _adapter()
        pred = SimpleNamespace(answer="the answer")
        mock_module = MagicMock(return_value=pred)
        result = a.run_module(mock_module, question="q")
        assert result == "the answer"

    def test_uses_lm_context(self):
        a = _adapter()
        entered_context = {}

        @contextmanager
        def _tracking_context(**kwargs):
            entered_context["kwargs"] = kwargs
            yield

        mock_module = MagicMock(return_value=SimpleNamespace(x="y"))
        with patch.dict(sys.modules["dspy"].__dict__, {"context": _tracking_context}):
            a.run_module(mock_module)

        assert "lm" in entered_context.get("kwargs", {})

    def test_extra_kwargs_forwarded(self):
        a = _adapter()
        captured = {}
        def fn(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(r="x")
        a.run_module(fn, question="q", context="some context")
        assert captured.get("context") == "some context"


class TestExtractPrediction:
    def test_returns_first_string_attr(self):
        pred = SimpleNamespace(answer="hello", reasoning="because")
        result = AlgoVoiDSPy._extract_prediction(pred)
        assert result in ("hello", "because")

    def test_skips_private_attrs(self):
        pred = SimpleNamespace(answer="show")
        pred.__dict__["_private"] = "skip"  # inject private attr
        result = AlgoVoiDSPy._extract_prediction(pred)
        assert result == "show"

    def test_skips_non_string_attrs(self):
        pred = SimpleNamespace(label="positive")
        pred.__dict__["score"] = 42  # non-string attr
        result = AlgoVoiDSPy._extract_prediction(pred)
        assert result == "positive"

    def test_str_fallback_no_dict(self):
        result = AlgoVoiDSPy._extract_prediction("plain string")
        assert result == "plain string"

    def test_str_fallback_no_string_attrs(self):
        pred = SimpleNamespace(score=0.9)
        result = AlgoVoiDSPy._extract_prediction(pred)
        assert isinstance(result, str)


class TestAsTool:
    def test_returns_payment_tool_instance(self):
        a = _adapter()
        tool = a.as_tool(resource_fn=lambda q: "result")
        assert isinstance(tool, AlgoVoiPaymentTool)

    def test_default_tool_name(self):
        a = _adapter()
        tool = a.as_tool(resource_fn=lambda q: "r")
        assert tool.name == "algovoi_payment_gate"

    def test_custom_tool_name(self):
        a = _adapter()
        tool = a.as_tool(resource_fn=lambda q: "r", tool_name="premium_kb")
        assert tool.name == "premium_kb"

    def test_dunder_name_set(self):
        a = _adapter()
        tool = a.as_tool(resource_fn=lambda q: "r", tool_name="my_gate")
        assert tool.__name__ == "my_gate"

    def test_dunder_doc_set(self):
        a = _adapter()
        tool = a.as_tool(resource_fn=lambda q: "r", tool_description="gate desc")
        assert tool.__doc__ == "gate desc"

    def test_resource_fn_stored(self):
        a = _adapter()
        fn = lambda q: f"ans:{q}"
        tool = a.as_tool(resource_fn=fn)
        assert tool._resource_fn is fn


class TestPaymentTool:
    def _make_adapter_with_gate(self, requires_payment=True):
        gate, gate_result = _make_gate()
        gate_result.requires_payment = requires_payment
        gate_result.error = "" if not requires_payment else "Payment proof required"
        a = _adapter()
        a._gate = gate
        return a, gate

    def test_challenge_returned_when_no_proof(self):
        a, _ = self._make_adapter_with_gate(requires_payment=True)
        tool = a.as_tool(resource_fn=lambda q: "content")
        result = tool(query="test", payment_proof="")
        data = json.loads(result)
        assert data["error"] == "payment_required"

    def test_resource_called_when_proof_verified(self):
        a, _ = self._make_adapter_with_gate(requires_payment=False)
        tool = a.as_tool(resource_fn=lambda q: f"Answer: {q}")
        result = tool(query="What is AlgoVoi?", payment_proof="valid_b64_proof")
        assert "Answer" in result

    def test_resource_error_returns_json(self):
        a, _ = self._make_adapter_with_gate(requires_payment=False)
        def bad_resource(q):
            raise ValueError("DB gone")
        tool = a.as_tool(resource_fn=bad_resource)
        result = tool(query="q", payment_proof="proof")
        data = json.loads(result)
        assert data["error"] == "resource_error"
        assert "DB gone" in data["detail"]

    def test_authorization_header_sent_with_proof(self):
        a, gate = self._make_adapter_with_gate(requires_payment=False)
        tool = a.as_tool(resource_fn=lambda q: "ok")
        tool(query="q", payment_proof="myproof")
        call_headers = gate.check.call_args[0][0]
        assert "Authorization" in call_headers
        assert "myproof" in call_headers["Authorization"]

    def test_no_authorization_header_without_proof(self):
        a, gate = self._make_adapter_with_gate(requires_payment=True)
        tool = a.as_tool(resource_fn=lambda q: "ok")
        tool(query="q", payment_proof="")
        call_headers = gate.check.call_args[0][0]
        assert "Authorization" not in call_headers

    def test_tool_name_attribute(self):
        a = _adapter()
        tool = AlgoVoiPaymentTool(a, lambda q: "ok", tool_name="my_tool")
        assert tool.name == "my_tool"

    def test_tool_dunder_name_attribute(self):
        a = _adapter()
        tool = AlgoVoiPaymentTool(a, lambda q: "ok", tool_name="my_tool")
        assert tool.__name__ == "my_tool"

    def test_tool_description_attribute(self):
        a = _adapter()
        tool = AlgoVoiPaymentTool(a, lambda q: "ok", tool_description="my desc")
        assert tool.description == "my desc"

    def test_tool_dunder_doc_attribute(self):
        a = _adapter()
        tool = AlgoVoiPaymentTool(a, lambda q: "ok", tool_description="my desc")
        assert tool.__doc__ == "my desc"

    def test_type_error_fallback_on_check(self):
        gate = MagicMock()
        gate_result = MagicMock()
        gate_result.requires_payment = True
        gate_result.error = "err"
        gate.check.side_effect = [TypeError("no kw"), gate_result]
        a = _adapter()
        a._gate = gate
        tool = a.as_tool(resource_fn=lambda q: "ok")
        result = tool(query="q", payment_proof="")
        data = json.loads(result)
        assert data["error"] == "payment_required"

    def test_default_callable_no_args(self):
        a, _ = self._make_adapter_with_gate(requires_payment=True)
        tool = a.as_tool(resource_fn=lambda q: "ok")
        result = tool()
        data = json.loads(result)
        assert data["error"] == "payment_required"


class TestFlaskGuard:
    def _make_flask_app(self):
        import flask
        return flask.Flask("test_dspy_guard")

    def test_returns_402_when_payment_required(self):
        a = _adapter()
        gate, gate_result = _make_gate()
        gate_result.requires_payment = True
        a._gate = gate

        app = self._make_flask_app()
        with app.test_request_context(
            "/", method="POST", data=b'{"messages":[]}', content_type="application/json"
        ):
            mock_resp = MagicMock()
            mock_resp.status_code = 402
            gate_result.as_flask_response.return_value = mock_resp
            resp = a.flask_guard()
        assert resp.status_code == 402

    def test_calls_complete_when_verified(self):
        a = _adapter()
        gate, gate_result = _make_gate()
        gate_result.requires_payment = False
        a._gate = gate

        import flask
        app = self._make_flask_app()
        with app.test_request_context(
            "/", method="POST",
            data=b'{"messages":[{"role":"user","content":"hi"}]}',
            content_type="application/json",
        ):
            with patch.object(a, "complete", return_value="DSPy text") as mock_complete:
                with app.app_context():
                    a.flask_guard()
            mock_complete.assert_called_once_with([{"role": "user", "content": "hi"}])

    def test_empty_body_handled(self):
        a = _adapter()
        gate, gate_result = _make_gate()
        gate_result.requires_payment = True
        a._gate = gate

        app = self._make_flask_app()
        with app.test_request_context("/", method="POST", data=b""):
            mock_resp = MagicMock()
            mock_resp.status_code = 402
            gate_result.as_flask_response.return_value = mock_resp
            resp = a.flask_guard()
        assert resp.status_code == 402

    def test_invalid_json_handled(self):
        a = _adapter()
        gate, gate_result = _make_gate()
        gate_result.requires_payment = True
        a._gate = gate

        app = self._make_flask_app()
        with app.test_request_context(
            "/", method="POST", data=b"not-valid-json"
        ):
            mock_resp = MagicMock()
            mock_resp.status_code = 402
            gate_result.as_flask_response.return_value = mock_resp
            resp = a.flask_guard()
        assert resp.status_code == 402

    def test_oversized_body_truncated(self):
        a = _adapter()
        gate, gate_result = _make_gate()
        gate_result.requires_payment = True
        a._gate = gate

        app = self._make_flask_app()
        with app.test_request_context("/", method="POST", data=b"x" * 1_100_000):
            mock_resp = MagicMock()
            mock_resp.status_code = 402
            gate_result.as_flask_response.return_value = mock_resp
            resp = a.flask_guard()
        assert resp.status_code == 402


class TestProtocols:
    def test_mpp_network_forwarded(self):
        gate, _ = _make_gate()
        mock_cls = MagicMock(return_value=gate)
        mod = types.ModuleType("mpp_algovoi")
        mod.AlgoVoiMppGate = mock_cls
        sys.modules["mpp_algovoi"] = mod
        AlgoVoiDSPy(
            algovoi_key="k", tenant_id="t", payout_address="a",
            protocol="mpp", network="hedera-mainnet",
        )
        assert mock_cls.call_args[1]["networks"] == ["hedera-mainnet"]

    def test_ap2_amount_forwarded(self):
        gate, _ = _make_gate()
        mock_cls = MagicMock(return_value=gate)
        mod = types.ModuleType("ap2_algovoi")
        mod.AlgoVoiAp2Gate = mock_cls
        sys.modules["ap2_algovoi"] = mod
        AlgoVoiDSPy(
            algovoi_key="k", tenant_id="t", payout_address="a",
            protocol="ap2", amount_microunits=30000,
        )
        assert mock_cls.call_args[1]["amount_microunits"] == 30000

    def test_x402_network_forwarded(self):
        gate, _ = _make_gate()
        mock_cls = MagicMock(return_value=gate)
        mod = types.ModuleType("openai_algovoi")
        mod.AlgoVoiX402Gate = mock_cls
        sys.modules["openai_algovoi"] = mod
        AlgoVoiDSPy(
            algovoi_key="k", tenant_id="t", payout_address="a",
            protocol="x402", network="stellar-mainnet",
        )
        assert mock_cls.call_args[1]["networks"] == ["stellar-mainnet"]

    def test_mpp_resource_id_forwarded(self):
        gate, _ = _make_gate()
        mock_cls = MagicMock(return_value=gate)
        mod = types.ModuleType("mpp_algovoi")
        mod.AlgoVoiMppGate = mock_cls
        sys.modules["mpp_algovoi"] = mod
        AlgoVoiDSPy(
            algovoi_key="k", tenant_id="t", payout_address="a",
            protocol="mpp", resource_id="custom-id",
        )
        assert mock_cls.call_args[1]["resource_id"] == "custom-id"
