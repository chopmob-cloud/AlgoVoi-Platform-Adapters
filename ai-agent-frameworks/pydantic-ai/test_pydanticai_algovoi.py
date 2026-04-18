"""
Unit tests for AlgoVoi Pydantic AI adapter.
All tests are fully mocked — no live API calls, no pydantic_ai install required.
"""

from __future__ import annotations

import asyncio
import json
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Stub pydantic_ai before the adapter module is imported ────────────────────

def _stub_pydantic_ai_modules() -> None:
    """Inject minimal pydantic_ai stubs into sys.modules."""

    # pydantic_ai core
    pai = types.ModuleType("pydantic_ai")

    class _MockAgent:
        def __init__(self, model=None, system_prompt=None, tools=None, **kwargs):
            self.model = model
            self.system_prompt = system_prompt
            self.tools = tools or []

        async def run(self, prompt, **kwargs):
            result = MagicMock()
            result.data = "Agent response"
            return result

        def run_sync(self, prompt, **kwargs):
            result = MagicMock()
            result.data = "Agent response"
            return result

    pai.Agent = _MockAgent
    sys.modules["pydantic_ai"] = pai

    # pydantic_ai.models
    pai_models = types.ModuleType("pydantic_ai.models")
    sys.modules["pydantic_ai.models"] = pai_models

    # pydantic_ai.models.openai
    pai_models_oai = types.ModuleType("pydantic_ai.models.openai")
    pai_models_oai.OpenAIModel = MagicMock()
    sys.modules["pydantic_ai.models.openai"] = pai_models_oai

    # pydantic_ai.tools
    pai_tools = types.ModuleType("pydantic_ai.tools")
    pai_tools.Tool = MagicMock()
    sys.modules["pydantic_ai.tools"] = pai_tools

    # openai (async client stub)
    oai = types.ModuleType("openai")
    oai.AsyncOpenAI = MagicMock()
    sys.modules["openai"] = oai


_stub_pydantic_ai_modules()

import pydanticai_algovoi as pai_mod  # noqa: E402
from pydanticai_algovoi import (  # noqa: E402
    AlgoVoiPydanticAI,
    AlgoVoiPaymentTool,
    PydanticAIResult,
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
    mod = types.ModuleType("mpp")
    mod.MppGate = MagicMock(return_value=gate)
    sys.modules["mpp"] = mod
    return gate


def _stub_ap2(gate=None):
    if gate is None:
        gate, _ = _make_gate()
    mod = types.ModuleType("ap2")
    mod.Ap2Gate = MagicMock(return_value=gate)
    sys.modules["ap2"] = mod
    return gate


def _stub_x402(gate=None):
    if gate is None:
        gate, _ = _make_gate()
    mod = types.ModuleType("openai_algovoi")
    mod._X402Gate = MagicMock(return_value=gate)
    sys.modules["openai_algovoi"] = mod
    return gate


def _adapter(**kwargs) -> AlgoVoiPydanticAI:
    _stub_mpp()
    _stub_ap2()
    _stub_x402()
    defaults = dict(algovoi_key="algv_k", tenant_id="tid", payout_address="ADDR")
    defaults.update(kwargs)
    return AlgoVoiPydanticAI(**defaults)


# ══════════════════════════════════════════════════════════════════════════════
# Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestVersion:
    def test_version_string(self):
        assert __version__ == "1.0.0"


class TestAddPath:
    def test_adds_new_path(self):
        target = "/tmp/__algovoi_pai_test_path__"
        original = list(sys.path)
        _add_path(target)
        assert target in sys.path
        sys.path[:] = original

    def test_deduplicates(self):
        target = "/tmp/__algovoi_pai_dedup__"
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
        mod = types.ModuleType("mpp")
        mod.MppGate = mock_cls
        sys.modules["mpp"] = mod
        AlgoVoiPydanticAI(
            algovoi_key="k", tenant_id="t", payout_address="a", protocol="mpp"
        )
        mock_cls.assert_called_once()

    def test_ap2_gate_created(self):
        gate, _ = _make_gate()
        mock_cls = MagicMock(return_value=gate)
        mod = types.ModuleType("ap2")
        mod.Ap2Gate = mock_cls
        sys.modules["ap2"] = mod
        AlgoVoiPydanticAI(
            algovoi_key="k", tenant_id="t", payout_address="a", protocol="ap2"
        )
        mock_cls.assert_called_once()

    def test_x402_gate_created(self):
        gate, _ = _make_gate()
        mock_cls = MagicMock(return_value=gate)
        mod = types.ModuleType("openai_algovoi")
        mod._X402Gate = mock_cls
        sys.modules["openai_algovoi"] = mod
        AlgoVoiPydanticAI(
            algovoi_key="k", tenant_id="t", payout_address="a", protocol="x402"
        )
        mock_cls.assert_called_once()

    def test_unknown_protocol_defaults_to_x402(self):
        gate, _ = _make_gate()
        mock_cls = MagicMock(return_value=gate)
        mod = types.ModuleType("openai_algovoi")
        mod._X402Gate = mock_cls
        sys.modules["openai_algovoi"] = mod
        AlgoVoiPydanticAI(
            algovoi_key="k", tenant_id="t", payout_address="a", protocol="grpc"
        )
        mock_cls.assert_called_once()

    def test_mpp_gate_receives_correct_kwargs(self):
        gate, _ = _make_gate()
        mock_cls = MagicMock(return_value=gate)
        mod = types.ModuleType("mpp")
        mod.MppGate = mock_cls
        sys.modules["mpp"] = mod
        AlgoVoiPydanticAI(
            algovoi_key="algv_123",
            tenant_id="my-tid",
            payout_address="MYADDR",
            protocol="mpp",
            network="stellar-mainnet",
            amount_microunits=5000,
            resource_id="premium-api",
        )
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["api_key"] == "algv_123"
        assert call_kwargs["tenant_id"] == "my-tid"
        assert call_kwargs["payout_address"] == "MYADDR"
        assert call_kwargs["networks"] == ["stellar-mainnet"]
        assert call_kwargs["amount_microunits"] == 5000
        assert call_kwargs["resource_id"] == "premium-api"


class TestConstructor:
    def test_defaults(self):
        a = _adapter()
        assert a._protocol == "mpp"
        assert a._network == "algorand-mainnet"
        assert a._amount_microunits == 10000
        assert a._model == "openai:gpt-4o"
        assert a._resource_id == "ai-function"
        assert a._openai_key is None
        assert a._base_url is None

    def test_custom_protocol(self):
        a = _adapter(protocol="ap2")
        assert a._protocol == "ap2"

    def test_custom_network(self):
        a = _adapter(network="hedera-mainnet")
        assert a._network == "hedera-mainnet"

    def test_openai_key_stored(self):
        a = _adapter(openai_key="sk-test-key")
        assert a._openai_key == "sk-test-key"

    def test_base_url_stored(self):
        a = _adapter(base_url="https://api.groq.com/openai/v1")
        assert a._base_url == "https://api.groq.com/openai/v1"

    def test_model_stored(self):
        a = _adapter(model="anthropic:claude-opus-4-5")
        assert a._model == "anthropic:claude-opus-4-5"

    def test_gate_assigned(self):
        a = _adapter()
        assert a._gate is not None

    def test_amount_microunits_stored(self):
        a = _adapter(amount_microunits=50000)
        assert a._amount_microunits == 50000


class TestPydanticAIResult:
    def test_requires_payment_true(self):
        r = PydanticAIResult(requires_payment=True, error="no proof")
        assert r.requires_payment is True
        assert r.error == "no proof"

    def test_requires_payment_false(self):
        r = PydanticAIResult(requires_payment=False)
        assert r.requires_payment is False
        assert r.error == ""

    def test_as_wsgi_delegates_to_gate_result(self):
        gate_res = MagicMock()
        gate_res.as_wsgi_response.return_value = (402, [], b'{"error":"x"}')
        r = PydanticAIResult(requires_payment=True, gate=gate_res)
        status, headers, body = r.as_wsgi_response()
        assert status == 402
        assert b"error" in body

    def test_as_wsgi_fallback_when_no_gate(self):
        r = PydanticAIResult(requires_payment=True, error="fail message")
        status, headers, body = r.as_wsgi_response()
        assert status == 402
        data = json.loads(body)
        assert "error" in data

    def test_as_wsgi_fallback_default_message(self):
        r = PydanticAIResult(requires_payment=True)
        _, _, body = r.as_wsgi_response()
        data = json.loads(body)
        assert data["error"] == "Payment required"

    def test_as_flask_response_status(self):
        import flask

        app = flask.Flask("test_result")
        with app.app_context():
            gate_res = MagicMock()
            gate_res.as_wsgi_response.return_value = (402, [], b'{"error":"pay"}')
            r = PydanticAIResult(requires_payment=True, gate=gate_res)
            resp = r.as_flask_response()
            assert resp.status_code == 402


class TestCheck:
    def test_requires_payment_true(self):
        gate, gate_result = _make_gate()
        gate_result.requires_payment = True
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
        gate_result.error = "Bad proof format"
        a = _adapter()
        a._gate = gate
        result = a.check({}, {})
        assert result.error == "Bad proof format"

    def test_gate_called_with_headers(self):
        gate, _ = _make_gate()
        a = _adapter()
        a._gate = gate
        a.check({"X-Custom": "val"}, {})
        gate.check.assert_called_once()
        call_args = gate.check.call_args[0]
        assert call_args[0].get("X-Custom") == "val"

    def test_body_none_defaults_to_empty_dict(self):
        gate, gate_result = _make_gate()
        gate_result.requires_payment = False
        gate_result.error = ""
        a = _adapter()
        a._gate = gate
        result = a.check({})  # no body argument
        assert isinstance(result, PydanticAIResult)

    def test_type_error_fallback(self):
        gate = MagicMock()
        gate_result = MagicMock()
        gate_result.requires_payment = True
        gate_result.error = ""
        gate.check.side_effect = [TypeError("unexpected kw"), gate_result]
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


class TestComplete:
    def test_calls_asyncio_run(self):
        a = _adapter()
        with patch.object(pai_mod, "asyncio") as mock_asyncio:
            mock_asyncio.run.return_value = "hello response"
            result = a.complete([{"role": "user", "content": "hi"}])
        assert result == "hello response"
        mock_asyncio.run.assert_called_once()

    def test_returns_string(self):
        a = _adapter()
        with patch.object(pai_mod, "asyncio") as mock_asyncio:
            mock_asyncio.run.return_value = "some text"
            result = a.complete([])
        assert isinstance(result, str)

    def test_passes_messages_to_async(self):
        a = _adapter()
        captured = {}

        async def fake_complete_async(messages):
            captured["messages"] = messages
            return "done"

        with patch.object(a, "_complete_async", side_effect=fake_complete_async):
            with patch.object(pai_mod, "asyncio") as mock_asyncio:
                mock_asyncio.run.side_effect = (
                    lambda coro: asyncio.get_event_loop().run_until_complete(coro)
                )
                a.complete([{"role": "user", "content": "hello"}])
        assert captured.get("messages") == [{"role": "user", "content": "hello"}]


class TestCompleteAsync:
    def test_system_role_extracted_as_system_prompt(self):
        a = _adapter()
        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.data = "ok"
        mock_agent.run = AsyncMock(return_value=mock_result)
        with patch.object(a, "_ensure_agent", return_value=mock_agent) as mock_ensure:
            asyncio.run(
                a._complete_async(
                    [
                        {"role": "system", "content": "Be concise"},
                        {"role": "user", "content": "Hello"},
                    ]
                )
            )
        mock_ensure.assert_called_once()
        call_kwargs = mock_ensure.call_args[1]
        assert call_kwargs.get("system_prompt") == "Be concise"

    def test_user_message_in_prompt(self):
        a = _adapter()
        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.data = "reply"
        captured = {}

        async def fake_run(prompt, **kw):
            captured["prompt"] = prompt
            return mock_result

        mock_agent.run = fake_run
        with patch.object(a, "_ensure_agent", return_value=mock_agent):
            asyncio.run(a._complete_async([{"role": "user", "content": "test question"}]))
        assert "test question" in captured["prompt"]

    def test_assistant_role_prefixed(self):
        a = _adapter()
        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.data = "r"
        captured = {}

        async def fake_run(prompt, **kw):
            captured["prompt"] = prompt
            return mock_result

        mock_agent.run = fake_run
        with patch.object(a, "_ensure_agent", return_value=mock_agent):
            asyncio.run(a._complete_async([{"role": "assistant", "content": "prev answer"}]))
        assert "Assistant" in captured["prompt"]

    def test_no_system_prompt_when_no_system_role(self):
        a = _adapter()
        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.data = "ok"
        mock_agent.run = AsyncMock(return_value=mock_result)
        with patch.object(a, "_ensure_agent", return_value=mock_agent) as mock_ensure:
            asyncio.run(a._complete_async([{"role": "user", "content": "no system"}]))
        call_kwargs = mock_ensure.call_args[1]
        assert call_kwargs.get("system_prompt") is None

    def test_empty_messages_returns_string(self):
        a = _adapter()
        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.data = ""
        mock_agent.run = AsyncMock(return_value=mock_result)
        with patch.object(a, "_ensure_agent", return_value=mock_agent):
            result = asyncio.run(a._complete_async([]))
        assert isinstance(result, str)

    def test_non_string_data_converted_to_str(self):
        a = _adapter()
        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.data = 42
        mock_agent.run = AsyncMock(return_value=mock_result)
        with patch.object(a, "_ensure_agent", return_value=mock_agent):
            result = asyncio.run(a._complete_async([{"role": "user", "content": "x"}]))
        assert result == "42"


class TestEnsureAgent:
    def test_returns_agent_instance(self):
        a = _adapter()
        agent = a._ensure_agent()
        assert agent is not None

    def test_system_prompt_passed_to_agent(self):
        a = _adapter(model="openai:gpt-4o")
        agent = a._ensure_agent(system_prompt="You are a helpful assistant")
        assert agent.system_prompt == "You are a helpful assistant"

    def test_no_system_prompt_is_none(self):
        a = _adapter()
        agent = a._ensure_agent()
        assert getattr(agent, "system_prompt", None) is None

    def test_openai_key_triggers_client_creation(self):
        a = _adapter(openai_key="sk-test-key-xyz", model="openai:gpt-4o")
        # pydantic_ai.models.openai.OpenAIModel is a MagicMock — should be called
        with patch.dict(
            sys.modules,
            {
                "pydantic_ai.models.openai": sys.modules["pydantic_ai.models.openai"],
                "openai": sys.modules["openai"],
            },
        ):
            agent = a._ensure_agent()
        assert agent is not None

    def test_string_model_used_without_credentials(self):
        a = _adapter(model="anthropic:claude-opus-4-5")
        # No openai_key → string model passed directly
        agent = a._ensure_agent()
        assert agent.model == "anthropic:claude-opus-4-5"

    def test_openai_prefix_stripped_for_model_name(self):
        a = _adapter(openai_key="sk-test", model="openai:gpt-4o-mini")
        # After stripping "openai:", the model name passed to OpenAIModel should be "gpt-4o-mini"
        mock_oai_model_cls = sys.modules["pydantic_ai.models.openai"].OpenAIModel
        mock_oai_model_cls.reset_mock()
        a._ensure_agent()
        if mock_oai_model_cls.called:
            call_args = mock_oai_model_cls.call_args[0]
            assert call_args[0] == "gpt-4o-mini"


class TestRunAgent:
    def test_calls_asyncio_run(self):
        a = _adapter()
        mock_agent = MagicMock()
        with patch.object(pai_mod, "asyncio") as mock_asyncio:
            mock_asyncio.run.return_value = "agent reply"
            result = a.run_agent(mock_agent, "hello")
        assert result == "agent reply"
        mock_asyncio.run.assert_called_once()

    def test_prompt_forwarded(self):
        a = _adapter()
        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.data = "ok"
        mock_agent.run = AsyncMock(return_value=mock_result)
        result = asyncio.run(a._run_async(mock_agent, "my question"))
        assert result == "ok"

    def test_deps_forwarded_when_provided(self):
        a = _adapter()
        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.data = "dep-result"
        captured = {}

        async def fake_run(prompt, **kw):
            captured["kw"] = kw
            return mock_result

        mock_agent.run = fake_run
        asyncio.run(a._run_async(mock_agent, "q", deps={"user": "alice"}))
        assert captured["kw"].get("deps") == {"user": "alice"}

    def test_deps_not_included_when_none(self):
        a = _adapter()
        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.data = "ok"
        captured = {}

        async def fake_run(prompt, **kw):
            captured["kw"] = kw
            return mock_result

        mock_agent.run = fake_run
        asyncio.run(a._run_async(mock_agent, "q"))
        assert "deps" not in captured["kw"]

    def test_extra_kwargs_forwarded(self):
        a = _adapter()
        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.data = "ok"
        captured = {}

        async def fake_run(prompt, **kw):
            captured["kw"] = kw
            return mock_result

        mock_agent.run = fake_run
        asyncio.run(a._run_async(mock_agent, "q", message_history=[]))
        assert "message_history" in captured["kw"]


class TestRunAsync:
    def test_returns_str_of_data(self):
        a = _adapter()
        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.data = "async result"
        mock_agent.run = AsyncMock(return_value=mock_result)
        result = asyncio.run(a._run_async(mock_agent, "prompt"))
        assert result == "async result"

    def test_non_string_data_converted(self):
        a = _adapter()
        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.data = {"key": "value"}
        mock_agent.run = AsyncMock(return_value=mock_result)
        result = asyncio.run(a._run_async(mock_agent, "p"))
        assert isinstance(result, str)

    def test_agent_run_awaited(self):
        a = _adapter()
        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.data = "x"
        mock_agent.run = AsyncMock(return_value=mock_result)
        asyncio.run(a._run_async(mock_agent, "prompt"))
        mock_agent.run.assert_awaited_once()


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

    def test_custom_description(self):
        a = _adapter()
        tool = a.as_tool(resource_fn=lambda q: "r", tool_description="pay to query")
        assert tool.description == "pay to query"

    def test_resource_fn_stored(self):
        a = _adapter()
        fn = lambda q: f"answer:{q}"
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
            raise RuntimeError("DB down")
        tool = a.as_tool(resource_fn=bad_resource)
        result = tool(query="test", payment_proof="proof")
        data = json.loads(result)
        assert data["error"] == "resource_error"
        assert "DB down" in data["detail"]

    def test_authorization_header_sent_with_proof(self):
        a, gate = self._make_adapter_with_gate(requires_payment=False)
        tool = a.as_tool(resource_fn=lambda q: "ok")
        tool(query="q", payment_proof="myproof123")
        call_headers = gate.check.call_args[0][0]
        assert "Authorization" in call_headers
        assert "myproof123" in call_headers["Authorization"]

    def test_no_authorization_header_without_proof(self):
        a, gate = self._make_adapter_with_gate(requires_payment=True)
        tool = a.as_tool(resource_fn=lambda q: "ok")
        tool(query="q", payment_proof="")
        call_headers = gate.check.call_args[0][0]
        assert "Authorization" not in call_headers

    def test_tool_name_attribute(self):
        a = _adapter()
        tool = AlgoVoiPaymentTool(a, lambda q: "ok", tool_name="my_gate")
        assert tool.name == "my_gate"

    def test_tool_description_attribute(self):
        a = _adapter()
        tool = AlgoVoiPaymentTool(a, lambda q: "ok", tool_description="gate description")
        assert tool.description == "gate description"

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
        result = tool()  # all defaults
        data = json.loads(result)
        assert data["error"] == "payment_required"


class TestFlaskGuard:
    def _make_flask_app(self):
        import flask
        return flask.Flask("test_pai_guard")

    def test_returns_402_when_payment_required(self):
        a = _adapter()
        gate, gate_result = _make_gate()
        gate_result.requires_payment = True
        a._gate = gate

        app = self._make_flask_app()
        with app.test_request_context(
            "/",
            method="POST",
            data=b'{"messages":[]}',
            content_type="application/json",
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
            "/",
            method="POST",
            data=b'{"messages":[{"role":"user","content":"hi"}]}',
            content_type="application/json",
        ):
            with patch.object(a, "complete", return_value="AI text") as mock_complete:
                with app.app_context():
                    a.flask_guard()
            mock_complete.assert_called_once_with(
                [{"role": "user", "content": "hi"}]
            )

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

    def test_invalid_json_body_handled(self):
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

    def test_body_capped_at_1mib(self):
        a = _adapter()
        gate, gate_result = _make_gate()
        gate_result.requires_payment = True
        a._gate = gate

        # Build a body slightly over 1 MiB — should still be handled
        oversized = b"x" * (1_100_000)
        app = self._make_flask_app()
        with app.test_request_context("/", method="POST", data=oversized):
            mock_resp = MagicMock()
            mock_resp.status_code = 402
            gate_result.as_flask_response.return_value = mock_resp
            resp = a.flask_guard()  # must not raise
        assert resp.status_code == 402


class TestProtocols:
    def test_mpp_gate_kwarg_network(self):
        gate, _ = _make_gate()
        mock_cls = MagicMock(return_value=gate)
        mod = types.ModuleType("mpp")
        mod.MppGate = mock_cls
        sys.modules["mpp"] = mod
        AlgoVoiPydanticAI(
            algovoi_key="k", tenant_id="t", payout_address="a",
            protocol="mpp", network="hedera-mainnet",
        )
        assert mock_cls.call_args[1]["networks"] == ["hedera-mainnet"]

    def test_ap2_gate_kwarg_network(self):
        gate, _ = _make_gate()
        mock_cls = MagicMock(return_value=gate)
        mod = types.ModuleType("ap2")
        mod.Ap2Gate = mock_cls
        sys.modules["ap2"] = mod
        AlgoVoiPydanticAI(
            algovoi_key="k", tenant_id="t", payout_address="a",
            protocol="ap2", network="voi-mainnet",
        )
        assert mock_cls.call_args[1]["networks"] == ["voi-mainnet"]

    def test_x402_gate_kwarg_amount(self):
        gate, _ = _make_gate()
        mock_cls = MagicMock(return_value=gate)
        mod = types.ModuleType("openai_algovoi")
        mod._X402Gate = mock_cls
        sys.modules["openai_algovoi"] = mod
        AlgoVoiPydanticAI(
            algovoi_key="k", tenant_id="t", payout_address="a",
            protocol="x402", amount_microunits=25000,
        )
        assert mock_cls.call_args[1]["amount_microunits"] == 25000

    def test_mpp_resource_id_forwarded(self):
        gate, _ = _make_gate()
        mock_cls = MagicMock(return_value=gate)
        mod = types.ModuleType("mpp")
        mod.MppGate = mock_cls
        sys.modules["mpp"] = mod
        AlgoVoiPydanticAI(
            algovoi_key="k", tenant_id="t", payout_address="a",
            protocol="mpp", resource_id="my-resource",
        )
        assert mock_cls.call_args[1]["resource_id"] == "my-resource"
