"""
Unit tests for llamaindex_algovoi.py
=====================================
All network and LlamaIndex SDK calls are mocked — no live requests, no API keys.

Run:
    cd ai-agent-frameworks/llamaindex
    pytest test_llamaindex_algovoi.py -v
"""

from __future__ import annotations

import base64
import json
import sys
import types
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

VALID_KWARGS = dict(
    algovoi_key="algv_test",
    tenant_id="tenant-uuid",
    payout_address="ZVLR...",
    protocol="mpp",
    network="algorand-mainnet",
)


def _make_gate_result(requires_payment: bool = True) -> MagicMock:
    r = MagicMock()
    r.requires_payment = requires_payment
    r.error = "Payment required" if requires_payment else None
    r.receipt = None if requires_payment else MagicMock(
        payer="ADDR", tx_id="TX123", amount=10_000
    )
    r.mandate = None
    r.as_flask_response.return_value = (
        b'{"error":"Payment Required"}',
        402,
        {"WWW-Authenticate": "Payment challenge=..."},
    )
    r.as_wsgi_response.return_value = (
        b'{"error":"Payment Required"}',
        402,
        {"WWW-Authenticate": "Payment challenge=..."},
    )
    return r


def _make_gate(requires_payment: bool = True) -> MagicMock:
    g = MagicMock()
    g.check.return_value = _make_gate_result(requires_payment)
    return g


def _mpp_proof(network: str, tx_id: str) -> str:
    return base64.b64encode(
        json.dumps({"network": network, "payload": {"txId": tx_id}}).encode()
    ).decode()


# ---------------------------------------------------------------------------
# Import module under test
# ---------------------------------------------------------------------------

import llamaindex_algovoi
from llamaindex_algovoi import (
    NETWORKS,
    PROTOCOLS,
    AlgoVoiLlamaIndex,
    AlgoVoiPaymentTool,
    LlamaIndexResult,
    _MAX_FLASK_BODY,
    _to_li_messages,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_gate():
    return _make_gate(requires_payment=True)


@pytest.fixture()
def verified_gate():
    return _make_gate(requires_payment=False)


@pytest.fixture()
def adapter(mock_gate):
    with patch("llamaindex_algovoi._build_gate", return_value=mock_gate):
        return AlgoVoiLlamaIndex(**VALID_KWARGS)


@pytest.fixture()
def verified_adapter(verified_gate):
    with patch("llamaindex_algovoi._build_gate", return_value=verified_gate):
        return AlgoVoiLlamaIndex(**VALID_KWARGS)


# ---------------------------------------------------------------------------
# TestModule
# ---------------------------------------------------------------------------

class TestModule:
    def test_version_string(self):
        assert isinstance(llamaindex_algovoi.__version__, str)
        assert llamaindex_algovoi.__version__ == "1.0.0"

    def test_algovoillamaindex_exported(self):
        assert "AlgoVoiLlamaIndex" in llamaindex_algovoi.__all__

    def test_algovoipaymenttool_exported(self):
        assert "AlgoVoiPaymentTool" in llamaindex_algovoi.__all__

    def test_llamaindexresult_exported(self):
        assert "LlamaIndexResult" in llamaindex_algovoi.__all__


# ---------------------------------------------------------------------------
# TestConstruction
# ---------------------------------------------------------------------------

class TestConstruction:
    def test_construct_with_openai_key(self):
        with patch("llamaindex_algovoi._build_gate", return_value=_make_gate()):
            gate = AlgoVoiLlamaIndex(openai_key="sk-test", **VALID_KWARGS)
        assert gate._openai_key == "sk-test"

    def test_construct_with_llm(self):
        mock_llm = MagicMock()
        with patch("llamaindex_algovoi._build_gate", return_value=_make_gate()):
            gate = AlgoVoiLlamaIndex(llm=mock_llm, **VALID_KWARGS)
        assert gate._llm is mock_llm

    def test_default_protocol_is_mpp(self):
        with patch("llamaindex_algovoi._build_gate", return_value=_make_gate()) as bg:
            AlgoVoiLlamaIndex(**VALID_KWARGS)
        assert bg.call_args.kwargs["protocol"] == "mpp"

    def test_default_network_is_algorand(self):
        with patch("llamaindex_algovoi._build_gate", return_value=_make_gate()) as bg:
            AlgoVoiLlamaIndex(**{**VALID_KWARGS, "protocol": "mpp"})
        assert bg.call_args.kwargs["network"] == "algorand-mainnet"

    def test_default_model_is_gpt4o(self):
        with patch("llamaindex_algovoi._build_gate", return_value=_make_gate()):
            gate = AlgoVoiLlamaIndex(**VALID_KWARGS)
        assert gate._model == "gpt-4o"

    def test_invalid_protocol_raises(self):
        with pytest.raises(ValueError, match="protocol"):
            with patch("llamaindex_algovoi._build_gate", return_value=_make_gate()):
                AlgoVoiLlamaIndex(protocol="grpc", **{k: v for k, v in VALID_KWARGS.items() if k != "protocol"})

    def test_invalid_network_raises(self):
        with pytest.raises(ValueError, match="network"):
            with patch("llamaindex_algovoi._build_gate", return_value=_make_gate()):
                AlgoVoiLlamaIndex(network="bitcoin-mainnet", **{k: v for k, v in VALID_KWARGS.items() if k != "network"})

    def test_all_protocols_accepted(self):
        for proto in ("mpp", "ap2", "x402"):
            kw = {**VALID_KWARGS, "protocol": proto}
            with patch("llamaindex_algovoi._build_gate", return_value=_make_gate()):
                gate = AlgoVoiLlamaIndex(**kw)
            assert gate is not None

    def test_all_networks_accepted(self):
        for net in NETWORKS:
            kw = {**VALID_KWARGS, "network": net}
            with patch("llamaindex_algovoi._build_gate", return_value=_make_gate()):
                gate = AlgoVoiLlamaIndex(**kw)
            assert gate is not None


# ---------------------------------------------------------------------------
# TestLlamaIndexResult
# ---------------------------------------------------------------------------

class TestLlamaIndexResult:
    def test_requires_payment_true(self):
        r = LlamaIndexResult(_make_gate_result(requires_payment=True))
        assert r.requires_payment is True

    def test_requires_payment_false(self):
        r = LlamaIndexResult(_make_gate_result(requires_payment=False))
        assert r.requires_payment is False

    def test_error_when_requires_payment(self):
        r = LlamaIndexResult(_make_gate_result(requires_payment=True))
        assert r.error == "Payment required"

    def test_error_none_when_verified(self):
        r = LlamaIndexResult(_make_gate_result(requires_payment=False))
        assert r.error is None

    def test_receipt_forwarded(self):
        raw = _make_gate_result(requires_payment=False)
        r = LlamaIndexResult(raw)
        assert r.receipt is raw.receipt

    def test_mandate_forwarded(self):
        raw = _make_gate_result(requires_payment=True)
        raw.mandate = MagicMock()
        r = LlamaIndexResult(raw)
        assert r.mandate is raw.mandate

    def test_as_flask_response_delegates(self):
        raw = _make_gate_result(requires_payment=True)
        r = LlamaIndexResult(raw)
        resp = r.as_flask_response()
        raw.as_flask_response.assert_called_once()
        assert resp == raw.as_flask_response.return_value

    def test_as_wsgi_response_delegates(self):
        raw = _make_gate_result(requires_payment=True)
        r = LlamaIndexResult(raw)
        resp = r.as_wsgi_response()
        raw.as_wsgi_response.assert_called_once()
        assert resp == raw.as_wsgi_response.return_value


# ---------------------------------------------------------------------------
# TestCheck
# ---------------------------------------------------------------------------

class TestCheck:
    def test_check_returns_llamaindex_result(self, adapter, mock_gate):
        result = adapter.check({})
        assert isinstance(result, LlamaIndexResult)

    def test_check_requires_payment_when_no_proof(self, adapter):
        result = adapter.check({})
        assert result.requires_payment is True

    def test_check_verified_when_proof_present(self, verified_adapter):
        result = verified_adapter.check({"Authorization": "Payment proof123"})
        assert result.requires_payment is False

    def test_check_passes_headers_to_gate(self, adapter, mock_gate):
        headers = {"Authorization": "Payment xyz"}
        adapter.check(headers)
        mock_gate.check.assert_called()
        args = mock_gate.check.call_args
        assert args[0][0] == headers or args[1].get("headers") == headers

    def test_check_body_defaults_to_empty_dict(self, adapter, mock_gate):
        adapter.check({})
        mock_gate.check.assert_called()

    def test_check_receipt_on_verified(self, verified_adapter):
        result = verified_adapter.check({"Authorization": "Payment proof123"})
        assert result.receipt is not None

    def test_check_mpp_gate_called(self):
        gate = _make_gate(requires_payment=True)
        with patch("llamaindex_algovoi._build_gate", return_value=gate):
            a = AlgoVoiLlamaIndex(protocol="mpp", **{k: v for k, v in VALID_KWARGS.items() if k != "protocol"})
        a.check({"Authorization": "Payment x"})
        gate.check.assert_called()

    def test_check_with_body(self, adapter, mock_gate):
        adapter.check({"Authorization": "Payment x"}, {"key": "val"})
        mock_gate.check.assert_called()


# ---------------------------------------------------------------------------
# TestToLiMessages
# ---------------------------------------------------------------------------

class TestToLiMessages:
    """Test _to_li_messages() with injected llama_index.core.llms mock."""

    def _li_mocks(self):
        class FakeRole:
            SYSTEM = "system"
            USER = "user"
            ASSISTANT = "assistant"

        captured = []

        def FakeChatMessage(role, content):
            m = MagicMock()
            m.role = role
            m.content = content
            captured.append(m)
            return m

        mod = MagicMock()
        mod.MessageRole = FakeRole
        mod.ChatMessage = FakeChatMessage
        return mod, captured

    def _patched_modules(self, li_mod):
        return {
            "llama_index": MagicMock(),
            "llama_index.core": MagicMock(),
            "llama_index.core.llms": li_mod,
        }

    def test_user_message_converted(self):
        li, captured = self._li_mocks()
        with patch.dict("sys.modules", self._patched_modules(li)):
            result = _to_li_messages([{"role": "user", "content": "Hello"}])
        assert len(result) == 1
        assert result[0].role == "user"
        assert result[0].content == "Hello"

    def test_system_message_converted(self):
        li, _ = self._li_mocks()
        with patch.dict("sys.modules", self._patched_modules(li)):
            result = _to_li_messages([{"role": "system", "content": "You are helpful"}])
        assert result[0].role == "system"

    def test_assistant_message_converted(self):
        li, _ = self._li_mocks()
        with patch.dict("sys.modules", self._patched_modules(li)):
            result = _to_li_messages([{"role": "assistant", "content": "Sure!"}])
        assert result[0].role == "assistant"

    def test_unknown_role_skipped(self):
        li, _ = self._li_mocks()
        with patch.dict("sys.modules", self._patched_modules(li)):
            result = _to_li_messages([
                {"role": "tool",   "content": "tool result"},
                {"role": "user",   "content": "Hello"},
            ])
        assert len(result) == 1
        assert result[0].role == "user"

    def test_multiple_messages_in_order(self):
        li, _ = self._li_mocks()
        with patch.dict("sys.modules", self._patched_modules(li)):
            result = _to_li_messages([
                {"role": "system",    "content": "sys"},
                {"role": "user",      "content": "hi"},
                {"role": "assistant", "content": "bye"},
            ])
        assert len(result) == 3
        assert [m.role for m in result] == ["system", "user", "assistant"]

    def test_empty_list_returns_empty(self):
        li, _ = self._li_mocks()
        with patch.dict("sys.modules", self._patched_modules(li)):
            result = _to_li_messages([])
        assert result == []

    def test_function_role_skipped(self):
        li, _ = self._li_mocks()
        with patch.dict("sys.modules", self._patched_modules(li)):
            result = _to_li_messages([{"role": "function", "content": "fn result"}])
        assert result == []


# ---------------------------------------------------------------------------
# TestComplete
# ---------------------------------------------------------------------------

class TestComplete:
    def _make_llm_response(self, content: str) -> MagicMock:
        resp = MagicMock()
        resp.message.content = content
        return resp

    def _li_mocks(self):
        class FakeRole:
            SYSTEM = "system"
            USER = "user"
            ASSISTANT = "assistant"

        def FakeChatMessage(role, content):
            m = MagicMock()
            m.role = role
            m.content = content
            return m

        mod = MagicMock()
        mod.MessageRole = FakeRole
        mod.ChatMessage = FakeChatMessage
        return mod

    def test_complete_calls_llm_chat(self, verified_adapter):
        mock_llm = MagicMock()
        mock_llm.chat.return_value = self._make_llm_response("Hello from LlamaIndex!")
        verified_adapter._llm = mock_llm

        li = self._li_mocks()
        with patch.dict("sys.modules", {"llama_index": MagicMock(), "llama_index.core": MagicMock(), "llama_index.core.llms": li}):
            result = verified_adapter.complete([{"role": "user", "content": "Hi"}])

        mock_llm.chat.assert_called_once()
        assert result == "Hello from LlamaIndex!"

    def test_complete_returns_string(self, verified_adapter):
        mock_llm = MagicMock()
        mock_llm.chat.return_value = self._make_llm_response("A string response")
        verified_adapter._llm = mock_llm

        li = self._li_mocks()
        with patch.dict("sys.modules", {"llama_index": MagicMock(), "llama_index.core": MagicMock(), "llama_index.core.llms": li}):
            result = verified_adapter.complete([{"role": "user", "content": "test"}])
        assert isinstance(result, str)

    def test_complete_with_system_message(self, verified_adapter):
        mock_llm = MagicMock()
        mock_llm.chat.return_value = self._make_llm_response("reply")
        verified_adapter._llm = mock_llm

        li = self._li_mocks()
        with patch.dict("sys.modules", {"llama_index": MagicMock(), "llama_index.core": MagicMock(), "llama_index.core.llms": li}):
            result = verified_adapter.complete([
                {"role": "system", "content": "You are helpful."},
                {"role": "user",   "content": "Hi"},
            ])
        mock_llm.chat.assert_called_once()
        li_args = mock_llm.chat.call_args[0][0]
        assert len(li_args) == 2

    def test_complete_skips_unknown_roles(self, verified_adapter):
        mock_llm = MagicMock()
        mock_llm.chat.return_value = self._make_llm_response("ok")
        verified_adapter._llm = mock_llm

        li = self._li_mocks()
        with patch.dict("sys.modules", {"llama_index": MagicMock(), "llama_index.core": MagicMock(), "llama_index.core.llms": li}):
            verified_adapter.complete([
                {"role": "tool", "content": "ignored"},
                {"role": "user", "content": "kept"},
            ])
        li_args = mock_llm.chat.call_args[0][0]
        assert len(li_args) == 1

    def test_complete_builds_openai_llm_when_no_llm(self):
        gate = _make_gate(requires_payment=False)
        with patch("llamaindex_algovoi._build_gate", return_value=gate):
            a = AlgoVoiLlamaIndex(openai_key="sk-test", **VALID_KWARGS)

        mock_openai_cls = MagicMock()
        mock_openai_instance = MagicMock()
        mock_openai_instance.chat.return_value = MagicMock(message=MagicMock(content="from openai"))
        mock_openai_cls.return_value = mock_openai_instance

        li = self._li_mocks()
        openai_mod = MagicMock()
        openai_mod.OpenAI = mock_openai_cls

        with patch.dict("sys.modules", {
            "llama_index": MagicMock(),
            "llama_index.core": MagicMock(),
            "llama_index.core.llms": li,
            "llama_index.llms": MagicMock(),
            "llama_index.llms.openai": openai_mod,
        }):
            result = a.complete([{"role": "user", "content": "hi"}])

        mock_openai_cls.assert_called_once()
        assert result == "from openai"

    def test_complete_passes_base_url_as_api_base(self):
        gate = _make_gate(requires_payment=False)
        with patch("llamaindex_algovoi._build_gate", return_value=gate):
            a = AlgoVoiLlamaIndex(
                openai_key="sk-test",
                base_url="https://api.together.xyz/v1",
                **VALID_KWARGS,
            )

        mock_openai_cls = MagicMock()
        mock_openai_cls.return_value = MagicMock(
            chat=MagicMock(return_value=MagicMock(message=MagicMock(content="ok")))
        )
        li = self._li_mocks()
        openai_mod = MagicMock()
        openai_mod.OpenAI = mock_openai_cls

        with patch.dict("sys.modules", {
            "llama_index": MagicMock(),
            "llama_index.core": MagicMock(),
            "llama_index.core.llms": li,
            "llama_index.llms": MagicMock(),
            "llama_index.llms.openai": openai_mod,
        }):
            a.complete([{"role": "user", "content": "hi"}])

        call_kwargs = mock_openai_cls.call_args.kwargs
        assert call_kwargs.get("api_base") == "https://api.together.xyz/v1"


# ---------------------------------------------------------------------------
# TestQueryEngineQuery
# ---------------------------------------------------------------------------

class TestQueryEngineQuery:
    def test_query_engine_called_with_query_str(self, verified_adapter):
        engine = MagicMock()
        engine.query.return_value = MagicMock(__str__=lambda self: "Answer to the question")
        verified_adapter.query_engine_query(engine, "What is AlgoVoi?")
        engine.query.assert_called_once_with("What is AlgoVoi?")

    def test_query_engine_returns_string(self, verified_adapter):
        engine = MagicMock()
        engine.query.return_value = "Direct string response"
        result = verified_adapter.query_engine_query(engine, "query")
        assert isinstance(result, str)
        assert result == "Direct string response"

    def test_query_engine_converts_response_to_str(self, verified_adapter):
        engine = MagicMock()
        response_obj = MagicMock()
        response_obj.__str__ = MagicMock(return_value="converted response")
        engine.query.return_value = response_obj
        result = verified_adapter.query_engine_query(engine, "q")
        assert result == "converted response"

    def test_query_engine_passes_exact_query_str(self, verified_adapter):
        engine = MagicMock()
        engine.query.return_value = "ok"
        verified_adapter.query_engine_query(engine, "specific question text")
        engine.query.assert_called_once_with("specific question text")


# ---------------------------------------------------------------------------
# TestChatEngineChat
# ---------------------------------------------------------------------------

class TestChatEngineChat:
    def test_chat_engine_called_with_message(self, verified_adapter):
        engine = MagicMock()
        engine.chat.return_value = "Response"
        verified_adapter.chat_engine_chat(engine, "Hello there")
        engine.chat.assert_called_once_with("Hello there")

    def test_chat_engine_returns_string(self, verified_adapter):
        engine = MagicMock()
        engine.chat.return_value = "chat reply"
        result = verified_adapter.chat_engine_chat(engine, "hi")
        assert isinstance(result, str)

    def test_chat_engine_converts_response_to_str(self, verified_adapter):
        engine = MagicMock()
        response_obj = MagicMock()
        response_obj.__str__ = MagicMock(return_value="str version")
        engine.chat.return_value = response_obj
        result = verified_adapter.chat_engine_chat(engine, "msg")
        assert result == "str version"

    def test_chat_engine_passes_exact_message(self, verified_adapter):
        engine = MagicMock()
        engine.chat.return_value = "ok"
        verified_adapter.chat_engine_chat(engine, "exact message here")
        engine.chat.assert_called_once_with("exact message here")


# ---------------------------------------------------------------------------
# TestAsTool
# ---------------------------------------------------------------------------

class TestAsTool:
    def test_as_tool_returns_payment_tool(self, adapter):
        tool = adapter.as_tool(resource_fn=lambda q: "ok")
        assert isinstance(tool, AlgoVoiPaymentTool)

    def test_as_tool_metadata_name(self, adapter):
        tool = adapter.as_tool(resource_fn=lambda q: "ok", tool_name="my_gate")
        assert tool.metadata.name == "my_gate"

    def test_as_tool_metadata_description(self, adapter):
        tool = adapter.as_tool(resource_fn=lambda q: "ok", tool_description="Pay to access")
        assert tool.metadata.description == "Pay to access"

    def test_as_tool_default_name(self, adapter):
        tool = adapter.as_tool(resource_fn=lambda q: "ok")
        assert tool.metadata.name == "algovoi_payment_gate"

    def test_as_tool_default_description_mentions_payment(self, adapter):
        tool = adapter.as_tool(resource_fn=lambda q: "ok")
        assert "payment" in tool.metadata.description.lower()

    def test_as_tool_adapter_reference(self, adapter):
        tool = adapter.as_tool(resource_fn=lambda q: "ok")
        assert tool._adapter is adapter


# ---------------------------------------------------------------------------
# TestParseInput
# ---------------------------------------------------------------------------

class TestParseInput:
    def _tool(self, adapter):
        return AlgoVoiPaymentTool(
            adapter=adapter,
            resource_fn=lambda q: "ok",
            tool_name="test",
            tool_description="desc",
        )

    def test_json_with_query_and_proof(self, adapter):
        tool = self._tool(adapter)
        query, headers = tool._parse_input(json.dumps({"query": "hello", "payment_proof": "abc123"}))
        assert query == "hello"
        assert headers == {"Authorization": "Payment abc123"}

    def test_json_with_query_no_proof(self, adapter):
        tool = self._tool(adapter)
        query, headers = tool._parse_input(json.dumps({"query": "hello"}))
        assert query == "hello"
        assert headers == {}

    def test_plain_string_becomes_query(self, adapter):
        tool = self._tool(adapter)
        query, headers = tool._parse_input("plain text question")
        assert query == "plain text question"
        assert headers == {}

    def test_invalid_json_uses_raw_string(self, adapter):
        tool = self._tool(adapter)
        query, headers = tool._parse_input("not {json at all")
        assert query == "not {json at all"
        assert headers == {}

    def test_empty_proof_produces_no_auth_header(self, adapter):
        tool = self._tool(adapter)
        _, headers = tool._parse_input(json.dumps({"query": "hi", "payment_proof": ""}))
        assert "Authorization" not in headers


# ---------------------------------------------------------------------------
# TestPaymentToolRun
# ---------------------------------------------------------------------------

class TestPaymentToolRun:
    def _make_tool(self, gate, resource_fn=None):
        with patch("llamaindex_algovoi._build_gate", return_value=gate):
            adapter = AlgoVoiLlamaIndex(**VALID_KWARGS)
        return AlgoVoiPaymentTool(
            adapter=adapter,
            resource_fn=resource_fn or (lambda q: f"resource: {q}"),
            tool_name="gate",
            tool_description="desc",
        )

    def test_no_proof_returns_challenge_json(self):
        tool = self._make_tool(_make_gate(requires_payment=True))
        output = tool._run(json.dumps({"query": "hello"}))
        data = json.loads(output)
        assert data["error"] == "payment_required"

    def test_invalid_proof_returns_challenge_json(self):
        tool = self._make_tool(_make_gate(requires_payment=True))
        output = tool._run(json.dumps({"query": "hi", "payment_proof": "bad_proof"}))
        data = json.loads(output)
        assert data["error"] == "payment_required"

    def test_valid_proof_calls_resource_fn(self):
        resource_fn = MagicMock(return_value="Protected content")
        tool = self._make_tool(_make_gate(requires_payment=False), resource_fn=resource_fn)
        proof = _mpp_proof("algorand-mainnet", "TXID123")
        output = tool._run(json.dumps({"query": "hello", "payment_proof": proof}))
        resource_fn.assert_called_once_with("hello")
        assert output == "Protected content"

    def test_resource_fn_exception_returns_error_json(self):
        def bad_fn(q):
            raise RuntimeError("DB is down")
        tool = self._make_tool(_make_gate(requires_payment=False), resource_fn=bad_fn)
        proof = _mpp_proof("algorand-mainnet", "TXID123")
        output = tool._run(json.dumps({"query": "hi", "payment_proof": proof}))
        data = json.loads(output)
        assert data["error"] == "resource_error"
        assert "DB is down" in data["detail"]

    def test_plain_string_input_no_payment(self):
        tool = self._make_tool(_make_gate(requires_payment=True))
        output = tool._run("raw query string")
        data = json.loads(output)
        assert data["error"] == "payment_required"

    def test_challenge_contains_detail_field(self):
        tool = self._make_tool(_make_gate(requires_payment=True))
        output = tool._run("{}")
        data = json.loads(output)
        assert "detail" in data


# ---------------------------------------------------------------------------
# TestPaymentToolCall
# ---------------------------------------------------------------------------

class TestPaymentToolCall:
    def _make_tool(self, gate, resource_fn=None):
        with patch("llamaindex_algovoi._build_gate", return_value=gate):
            adapter = AlgoVoiLlamaIndex(**VALID_KWARGS)
        return AlgoVoiPaymentTool(
            adapter=adapter,
            resource_fn=resource_fn or (lambda q: f"result: {q}"),
            tool_name="my_tool",
            tool_description="desc",
        )

    def test_call_returns_tool_output(self):
        tool = self._make_tool(_make_gate(requires_payment=True))
        output = tool(json.dumps({"query": "hi"}))
        # ToolOutput (real or stub) has a content attribute
        assert hasattr(output, "content")

    def test_call_content_matches_run(self):
        tool = self._make_tool(_make_gate(requires_payment=True))
        inp = json.dumps({"query": "test"})
        output = tool(inp)
        expected = tool._run(inp)
        assert output.content == expected

    def test_call_tool_name_in_output(self):
        tool = self._make_tool(_make_gate(requires_payment=True))
        output = tool("{}")
        assert output.tool_name == "my_tool"

    def test_call_raw_input_in_output(self):
        tool = self._make_tool(_make_gate(requires_payment=True))
        inp = json.dumps({"query": "q"})
        output = tool(inp)
        assert output.raw_input == {"input": inp}


# ---------------------------------------------------------------------------
# TestFlaskGuard
# ---------------------------------------------------------------------------

class TestFlaskGuard:
    def _make_adapter(self, gate):
        with patch("llamaindex_algovoi._build_gate", return_value=gate):
            return AlgoVoiLlamaIndex(**VALID_KWARGS)

    def _mock_request(self, content_length=None, body=None):
        mock_req = MagicMock()
        mock_req.content_length = content_length
        mock_req.headers = {}
        mock_req.get_json.return_value = body or {}
        return mock_req

    def test_flask_guard_returns_402_on_no_proof(self):
        adapter = self._make_adapter(_make_gate(requires_payment=True))
        mock_req = self._mock_request(content_length=None, body={})

        import flask as _flask
        with patch.object(_flask, "request", mock_req), \
             patch("flask.jsonify"):
            result = adapter.flask_guard()

        assert result is not None

    def test_flask_guard_rejects_oversized_body(self):
        adapter = self._make_adapter(_make_gate(requires_payment=False))
        mock_req = self._mock_request(content_length=2_000_000)
        captured_status = {}

        def fake_response(body, status, mimetype):
            captured_status["status"] = status
            return MagicMock(status_code=status)

        import flask as _flask
        with patch.object(_flask, "request", mock_req), \
             patch("flask.Response", side_effect=fake_response), \
             patch("flask.jsonify"):
            adapter.flask_guard()

        assert captured_status["status"] == 413

    def test_flask_guard_calls_complete_when_verified(self):
        adapter = self._make_adapter(_make_gate(requires_payment=False))
        mock_req = self._mock_request(
            content_length=None,
            body={"messages": [{"role": "user", "content": "hi"}]},
        )

        import flask as _flask
        with patch.object(_flask, "request", mock_req), \
             patch("flask.jsonify") as mock_jsonify, \
             patch.object(adapter, "complete", return_value="LI reply") as mock_complete:
            adapter.flask_guard()

        mock_complete.assert_called_once_with([{"role": "user", "content": "hi"}])
        mock_jsonify.assert_called_once_with({"content": "LI reply"})

    def test_flask_guard_empty_body_uses_empty_messages(self):
        adapter = self._make_adapter(_make_gate(requires_payment=False))
        mock_req = self._mock_request(content_length=None, body={})

        import flask as _flask
        with patch.object(_flask, "request", mock_req), \
             patch("flask.jsonify") as mock_jsonify, \
             patch.object(adapter, "complete", return_value="empty") as mock_complete:
            adapter.flask_guard()

        mock_complete.assert_called_once_with([])

    def test_flask_guard_small_body_not_rejected(self):
        adapter = self._make_adapter(_make_gate(requires_payment=False))
        mock_req = self._mock_request(content_length=512, body={"messages": []})

        import flask as _flask
        with patch.object(_flask, "request", mock_req), \
             patch("flask.jsonify") as mock_jsonify, \
             patch.object(adapter, "complete", return_value="ok"):
            adapter.flask_guard()

        mock_jsonify.assert_called_once()

    def test_flask_guard_none_content_length_not_rejected(self):
        adapter = self._make_adapter(_make_gate(requires_payment=False))
        mock_req = self._mock_request(content_length=None, body={"messages": []})

        import flask as _flask
        with patch.object(_flask, "request", mock_req), \
             patch("flask.jsonify") as mock_jsonify, \
             patch.object(adapter, "complete", return_value="ok"):
            adapter.flask_guard()

        mock_jsonify.assert_called_once()


# ---------------------------------------------------------------------------
# TestImportPaths
# ---------------------------------------------------------------------------

class TestImportPaths:
    def test_import_path_matches_public_api(self):
        """AlgoVoiLlamaIndex must be importable from llamaindex_algovoi."""
        import importlib
        mod = importlib.import_module("llamaindex_algovoi")
        assert hasattr(mod, "AlgoVoiLlamaIndex")
        assert hasattr(mod, "AlgoVoiPaymentTool")
        assert hasattr(mod, "LlamaIndexResult")

    def test_stub_tool_metadata_has_name_and_description(self):
        """Stub ToolMetadata (when llama_index not installed) works for tests."""
        from llamaindex_algovoi import ToolMetadata
        tm = ToolMetadata(name="test_tool", description="A test tool")
        assert tm.name == "test_tool"
        assert tm.description == "A test tool"

    def test_max_flask_body_is_one_mib(self):
        assert _MAX_FLASK_BODY == 1_048_576
