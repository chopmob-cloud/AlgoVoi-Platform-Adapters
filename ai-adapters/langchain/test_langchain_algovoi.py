"""
AlgoVoi LangChain Adapter — Unit Tests
=======================================
All tests are fully mocked — no live LangChain, OpenAI, or AlgoVoi calls.

Run:
    python -m pytest test_langchain_algovoi.py -v
    python -m pytest test_langchain_algovoi.py -v --tb=short
"""

from __future__ import annotations

import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Path setup ────────────────────────────────────────────────────────────────

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))

sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "openai"))
sys.path.insert(0, os.path.join(_ROOT, "mpp-adapter"))
sys.path.insert(0, os.path.join(_ROOT, "ap2-adapter"))

# ── Fixtures ──────────────────────────────────────────────────────────────────

COMMON = dict(
    algovoi_key       = "algv_test",
    tenant_id         = "test-tenant",
    payout_address    = "ZVLRVYQSLJNVFMOIOKT35XH5SNQG45IVFMLLRFLHDQJQA5TO5H3SO4TVDQ",
    amount_microunits = 10000,
    openai_key        = "sk-test-EXAMPLE",
)

MESSAGES = [
    {"role": "system",    "content": "You are a helpful assistant."},
    {"role": "user",      "content": "Hello"},
    {"role": "assistant", "content": "Hi!"},
    {"role": "user",      "content": "What can you do?"},
]

MESSAGES_NO_SYSTEM = [
    {"role": "user",      "content": "Hello"},
    {"role": "assistant", "content": "Hi!"},
    {"role": "user",      "content": "What can you do?"},
]


def _make_inner(requires_payment: bool = False, error: str = None):
    inner = MagicMock()
    inner.requires_payment = requires_payment
    inner.error            = error
    inner.receipt          = None
    inner.mandate          = None
    inner.as_flask_response.return_value = (
        '{"error":"Payment Required"}', 402,
        {"WWW-Authenticate": "Payment realm=algovoi"},
    )
    inner.as_wsgi_response.return_value = (
        "402 Payment Required",
        [("WWW-Authenticate", "Payment realm=algovoi")],
        b'{"error":"Payment Required","detail":""}',
    )
    return inner


def _mock_lc_modules(reply_text: str = "Hello from LangChain!"):
    """Build fake langchain_openai + langchain_core.messages modules."""
    ai_msg        = MagicMock()
    ai_msg.content = reply_text

    chat_instance = MagicMock()
    chat_instance.invoke.return_value = ai_msg

    chat_cls = MagicMock(return_value=chat_instance)

    # langchain_openai.ChatOpenAI
    lc_openai_mod = MagicMock()
    lc_openai_mod.ChatOpenAI = chat_cls

    # langchain_core.messages
    lc_msgs_mod          = MagicMock()
    lc_msgs_mod.HumanMessage  = MagicMock(side_effect=lambda content: ("HumanMessage", content))
    lc_msgs_mod.SystemMessage = MagicMock(side_effect=lambda content: ("SystemMessage", content))
    lc_msgs_mod.AIMessage     = MagicMock(side_effect=lambda content: ("AIMessage", content))

    return lc_openai_mod, lc_msgs_mod, chat_cls, chat_instance, ai_msg


# ══════════════════════════════════════════════════════════════════════════════
# 1. Module-level
# ══════════════════════════════════════════════════════════════════════════════

class TestModule:
    def test_version_string(self):
        from langchain_algovoi import __version__
        assert __version__ == "1.0.0"

    def test_networks_list(self):
        from langchain_algovoi import NETWORKS
        assert "algorand-mainnet" in NETWORKS
        assert "stellar-mainnet"  in NETWORKS
        assert len(NETWORKS) == 4

    def test_protocols_list(self):
        from langchain_algovoi import PROTOCOLS
        assert set(PROTOCOLS) == {"x402", "mpp", "ap2"}


# ══════════════════════════════════════════════════════════════════════════════
# 2. Construction
# ══════════════════════════════════════════════════════════════════════════════

class TestConstruction:
    def test_mpp_construction(self):
        with patch("langchain_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from langchain_algovoi import AlgoVoiLangChain
            AlgoVoiLangChain(**COMMON, protocol="mpp")
            assert mock_gate.call_args[0][0] == "mpp"

    def test_x402_construction(self):
        with patch("langchain_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from langchain_algovoi import AlgoVoiLangChain
            AlgoVoiLangChain(**COMMON, protocol="x402")
            assert mock_gate.call_args[0][0] == "x402"

    def test_ap2_construction(self):
        with patch("langchain_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from langchain_algovoi import AlgoVoiLangChain
            AlgoVoiLangChain(**COMMON, protocol="ap2")
            assert mock_gate.call_args[0][0] == "ap2"

    def test_default_protocol_is_mpp(self):
        with patch("langchain_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from langchain_algovoi import AlgoVoiLangChain
            AlgoVoiLangChain(**COMMON)
            assert mock_gate.call_args[0][0] == "mpp"

    def test_default_model_is_gpt4o(self):
        with patch("langchain_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from langchain_algovoi import AlgoVoiLangChain
            gate = AlgoVoiLangChain(**COMMON)
            assert gate._model == "gpt-4o"

    def test_custom_model(self):
        with patch("langchain_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from langchain_algovoi import AlgoVoiLangChain
            gate = AlgoVoiLangChain(**COMMON, model="gpt-4-turbo")
            assert gate._model == "gpt-4-turbo"

    def test_openai_key_stored(self):
        with patch("langchain_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from langchain_algovoi import AlgoVoiLangChain
            gate = AlgoVoiLangChain(**COMMON)
            assert gate._openai_key == "sk-test-EXAMPLE"

    def test_custom_base_url(self):
        with patch("langchain_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from langchain_algovoi import AlgoVoiLangChain
            gate = AlgoVoiLangChain(**COMMON, base_url="https://custom.api/v1")
            assert gate._base_url == "https://custom.api/v1"

    def test_custom_llm_stored(self):
        with patch("langchain_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from langchain_algovoi import AlgoVoiLangChain
            fake_llm = MagicMock()
            gate = AlgoVoiLangChain(**COMMON, llm=fake_llm)
            assert gate._llm is fake_llm

    def test_default_network(self):
        with patch("langchain_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from langchain_algovoi import AlgoVoiLangChain
            AlgoVoiLangChain(**COMMON)
            assert mock_gate.call_args[0][4] == "algorand-mainnet"

    def test_invalid_network_raises(self):
        from langchain_algovoi import AlgoVoiLangChain
        with pytest.raises(ValueError, match="network must be one of"):
            AlgoVoiLangChain(**COMMON, network="bitcoin-mainnet")

    def test_invalid_protocol_raises(self):
        from langchain_algovoi import AlgoVoiLangChain
        with pytest.raises(ValueError, match="protocol must be one of"):
            AlgoVoiLangChain(**COMMON, protocol="grpc")

    def test_all_networks_accepted(self):
        networks = ["algorand-mainnet", "voi-mainnet", "hedera-mainnet", "stellar-mainnet"]
        for net in networks:
            with patch("langchain_algovoi._build_gate") as mock_gate:
                mock_gate.return_value = MagicMock()
                from langchain_algovoi import AlgoVoiLangChain
                AlgoVoiLangChain(**COMMON, network=net)

    def test_custom_resource_id_forwarded(self):
        with patch("langchain_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from langchain_algovoi import AlgoVoiLangChain
            AlgoVoiLangChain(**COMMON, resource_id="custom-resource")
            assert mock_gate.call_args[0][6] == "custom-resource"


# ══════════════════════════════════════════════════════════════════════════════
# 3. LangChainResult
# ══════════════════════════════════════════════════════════════════════════════

class TestLangChainResult:
    def test_requires_payment_propagated(self):
        from langchain_algovoi import LangChainResult
        inner = _make_inner(requires_payment=True)
        r = LangChainResult(inner)
        assert r.requires_payment is True

    def test_not_requires_payment(self):
        from langchain_algovoi import LangChainResult
        inner = _make_inner(requires_payment=False)
        r = LangChainResult(inner)
        assert r.requires_payment is False

    def test_receipt_propagated(self):
        from langchain_algovoi import LangChainResult
        inner         = _make_inner()
        inner.receipt = MagicMock(payer="ADDR", tx_id="TX1", amount=10000)
        r = LangChainResult(inner)
        assert r.receipt.payer == "ADDR"

    def test_mandate_propagated(self):
        from langchain_algovoi import LangChainResult
        inner          = _make_inner()
        inner.mandate  = MagicMock(payer_address="ADDR", network="algorand-mainnet")
        r = LangChainResult(inner)
        assert r.mandate.payer_address == "ADDR"

    def test_error_propagated(self):
        from langchain_algovoi import LangChainResult
        inner = _make_inner(error="bad proof")
        r = LangChainResult(inner)
        assert r.error == "bad proof"

    def test_as_flask_response_delegates_to_inner(self):
        from langchain_algovoi import LangChainResult
        inner = _make_inner(requires_payment=True)
        r     = LangChainResult(inner)
        body, status, headers = r.as_flask_response()
        assert status == 402
        inner.as_flask_response.assert_called_once()

    def test_as_wsgi_response_delegates_to_inner(self):
        from langchain_algovoi import LangChainResult
        inner = _make_inner(requires_payment=True)
        r     = LangChainResult(inner)
        status_str, hdrs, body_bytes = r.as_wsgi_response()
        assert "402" in status_str
        inner.as_wsgi_response.assert_called_once()

    def test_as_flask_fallback_no_inner_method(self):
        from langchain_algovoi import LangChainResult
        inner = MagicMock(spec=["requires_payment", "error", "receipt", "mandate"])
        inner.requires_payment = True
        inner.error            = "oops"
        r     = LangChainResult(inner)
        body, status, headers = r.as_flask_response()
        assert status == 402
        assert "Payment Required" in body

    def test_as_wsgi_fallback_no_inner_method(self):
        from langchain_algovoi import LangChainResult
        inner = MagicMock(spec=["requires_payment", "error", "receipt", "mandate"])
        inner.requires_payment = True
        inner.error            = None
        r = LangChainResult(inner)
        status_str, hdrs, body_bytes = r.as_wsgi_response()
        assert b"Payment Required" in body_bytes


# ══════════════════════════════════════════════════════════════════════════════
# 4. check()
# ══════════════════════════════════════════════════════════════════════════════

class TestCheck:
    def _gate(self, requires_payment=True, error=None):
        with patch("langchain_algovoi._build_gate") as mock_build:
            inner = _make_inner(requires_payment=requires_payment, error=error)
            mock_build.return_value       = MagicMock()
            mock_build.return_value.check = MagicMock(return_value=inner)
            from langchain_algovoi import AlgoVoiLangChain
            gate = AlgoVoiLangChain(**COMMON)
            gate._gate = mock_build.return_value
            return gate

    def test_no_payment_returns_requires_payment(self):
        gate   = self._gate(requires_payment=True)
        result = gate.check({})
        assert result.requires_payment is True

    def test_valid_payment_returns_not_required(self):
        gate   = self._gate(requires_payment=False)
        result = gate.check({"Authorization": "Payment proof123"})
        assert result.requires_payment is False

    def test_check_passes_headers_to_gate(self):
        gate  = self._gate()
        hdrs  = {"Authorization": "Payment abc"}
        gate.check(hdrs, {})
        gate._gate.check.assert_called_once_with(hdrs, {})

    def test_type_error_fallback_no_body(self):
        """MPP gate raises TypeError when body kwarg is passed — adapter catches it."""
        with patch("langchain_algovoi._build_gate") as mock_build:
            inner = _make_inner(requires_payment=True)
            mock_gate = MagicMock()
            mock_gate.check.side_effect = [TypeError("unexpected kwarg"), inner]
            mock_build.return_value = mock_gate
            from langchain_algovoi import AlgoVoiLangChain
            gate        = AlgoVoiLangChain(**COMMON)
            gate._gate  = mock_gate
            result      = gate.check({}, {})
            assert result.requires_payment is True

    def test_result_is_langchain_result_instance(self):
        from langchain_algovoi import AlgoVoiLangChain, LangChainResult
        gate   = self._gate()
        result = gate.check({})
        assert isinstance(result, LangChainResult)


# ══════════════════════════════════════════════════════════════════════════════
# 5. _to_lc_messages()
# ══════════════════════════════════════════════════════════════════════════════

class TestToLcMessages:
    def _run(self, messages):
        from langchain_algovoi import _to_lc_messages

        human_msg  = lambda content: ("HumanMessage", content)
        system_msg = lambda content: ("SystemMessage", content)
        ai_msg     = lambda content: ("AIMessage", content)

        lc_msgs_mod          = MagicMock()
        lc_msgs_mod.HumanMessage  = MagicMock(side_effect=human_msg)
        lc_msgs_mod.SystemMessage = MagicMock(side_effect=system_msg)
        lc_msgs_mod.AIMessage     = MagicMock(side_effect=ai_msg)

        with patch.dict("sys.modules", {"langchain_core.messages": lc_msgs_mod}):
            return _to_lc_messages(messages)

    def test_user_becomes_human_message(self):
        result = self._run([{"role": "user", "content": "Hello"}])
        assert result[0] == ("HumanMessage", "Hello")

    def test_system_becomes_system_message(self):
        result = self._run([{"role": "system", "content": "You are a bot."}])
        assert result[0] == ("SystemMessage", "You are a bot.")

    def test_assistant_becomes_ai_message(self):
        result = self._run([{"role": "assistant", "content": "Hi!"}])
        assert result[0] == ("AIMessage", "Hi!")

    def test_unknown_role_skipped(self):
        result = self._run([
            {"role": "tool",   "content": "result"},
            {"role": "user",   "content": "after"},
        ])
        assert len(result) == 1
        assert result[0] == ("HumanMessage", "after")

    def test_empty_list(self):
        result = self._run([])
        assert result == []

    def test_missing_role_defaults_to_user(self):
        result = self._run([{"content": "no role here"}])
        assert result[0] == ("HumanMessage", "no role here")

    def test_missing_content_defaults_to_empty(self):
        result = self._run([{"role": "user"}])
        assert result[0] == ("HumanMessage", "")

    def test_multiple_messages_order_preserved(self):
        result = self._run([
            {"role": "system", "content": "sys"},
            {"role": "user",   "content": "usr"},
            {"role": "assistant", "content": "ast"},
        ])
        assert len(result) == 3
        assert result[0][0] == "SystemMessage"
        assert result[1][0] == "HumanMessage"
        assert result[2][0] == "AIMessage"

    def test_import_error_raised(self):
        from langchain_algovoi import _to_lc_messages
        with patch.dict("sys.modules", {"langchain_core.messages": None}):
            with pytest.raises(ImportError, match="langchain-core"):
                _to_lc_messages([{"role": "user", "content": "hi"}])


# ══════════════════════════════════════════════════════════════════════════════
# 6. complete()
# ══════════════════════════════════════════════════════════════════════════════

class TestComplete:
    def _make_gate(self):
        with patch("langchain_algovoi._build_gate") as mock_build:
            mock_build.return_value = MagicMock()
            from langchain_algovoi import AlgoVoiLangChain
            gate = AlgoVoiLangChain(**COMMON)
            return gate

    def test_complete_with_chat_openai(self):
        gate = self._make_gate()
        lc_openai_mod, lc_msgs_mod, chat_cls, chat_instance, ai_msg = _mock_lc_modules(
            "Hello from LangChain!"
        )
        with patch.dict("sys.modules", {
            "langchain_openai":        lc_openai_mod,
            "langchain_core.messages": lc_msgs_mod,
        }):
            result = gate.complete(MESSAGES)
        assert result == "Hello from LangChain!"

    def test_complete_without_openai_key_raises(self):
        with patch("langchain_algovoi._build_gate") as mock_build:
            mock_build.return_value = MagicMock()
            from langchain_algovoi import AlgoVoiLangChain
            gate = AlgoVoiLangChain(
                algovoi_key="algv_test", tenant_id="t", payout_address="ADDR",
            )
        with pytest.raises(ValueError, match="openai_key is required"):
            with patch.dict("sys.modules", {"langchain_core.messages": MagicMock()}):
                gate.complete([{"role": "user", "content": "hi"}])

    def test_complete_missing_langchain_openai_raises(self):
        gate = self._make_gate()
        lc_msgs_mod = MagicMock()
        with patch.dict("sys.modules", {
            "langchain_openai":        None,
            "langchain_core.messages": lc_msgs_mod,
        }):
            with pytest.raises(ImportError, match="langchain-openai"):
                gate.complete(MESSAGES)

    def test_complete_with_pre_built_llm(self):
        ai_msg        = MagicMock()
        ai_msg.content = "reply from custom LLM"
        fake_llm      = MagicMock()
        fake_llm.invoke.return_value = ai_msg

        with patch("langchain_algovoi._build_gate") as mock_build:
            mock_build.return_value = MagicMock()
            from langchain_algovoi import AlgoVoiLangChain
            gate = AlgoVoiLangChain(**COMMON, llm=fake_llm)

        lc_msgs_mod = MagicMock()
        lc_msgs_mod.HumanMessage  = MagicMock(side_effect=lambda content: content)
        lc_msgs_mod.SystemMessage = MagicMock(side_effect=lambda content: content)
        lc_msgs_mod.AIMessage     = MagicMock(side_effect=lambda content: content)
        with patch.dict("sys.modules", {"langchain_core.messages": lc_msgs_mod}):
            result = gate.complete(MESSAGES)

        fake_llm.invoke.assert_called_once()
        assert result == "reply from custom LLM"

    def test_complete_with_model_override(self):
        gate = self._make_gate()
        lc_openai_mod, lc_msgs_mod, chat_cls, chat_instance, ai_msg = _mock_lc_modules()
        with patch.dict("sys.modules", {
            "langchain_openai":        lc_openai_mod,
            "langchain_core.messages": lc_msgs_mod,
        }):
            gate.complete(MESSAGES, model="gpt-4-turbo")
        call_kwargs = chat_cls.call_args[1]
        assert call_kwargs["model"] == "gpt-4-turbo"

    def test_complete_passes_base_url(self):
        with patch("langchain_algovoi._build_gate") as mock_build:
            mock_build.return_value = MagicMock()
            from langchain_algovoi import AlgoVoiLangChain
            gate = AlgoVoiLangChain(**COMMON, base_url="https://custom.ai/v1")
        lc_openai_mod, lc_msgs_mod, chat_cls, _, _ = _mock_lc_modules()
        with patch.dict("sys.modules", {
            "langchain_openai":        lc_openai_mod,
            "langchain_core.messages": lc_msgs_mod,
        }):
            gate.complete(MESSAGES)
        assert chat_cls.call_args[1]["base_url"] == "https://custom.ai/v1"

    def test_complete_skips_unknown_roles(self):
        gate     = self._make_gate()
        messages = [
            {"role": "tool",      "content": "tool result"},
            {"role": "user",      "content": "hi"},
        ]
        lc_openai_mod, lc_msgs_mod, chat_cls, chat_instance, _ = _mock_lc_modules()
        lc_msgs_mod.HumanMessage  = MagicMock(side_effect=lambda content: ("H", content))
        lc_msgs_mod.SystemMessage = MagicMock(side_effect=lambda content: ("S", content))
        lc_msgs_mod.AIMessage     = MagicMock(side_effect=lambda content: ("A", content))
        with patch.dict("sys.modules", {
            "langchain_openai":        lc_openai_mod,
            "langchain_core.messages": lc_msgs_mod,
        }):
            gate.complete(messages)
        lc_messages_passed = chat_instance.invoke.call_args[0][0]
        # Only one message — the tool role was skipped
        assert len(lc_messages_passed) == 1

    def test_complete_returns_string(self):
        gate = self._make_gate()
        lc_openai_mod, lc_msgs_mod, _, _, ai_msg = _mock_lc_modules()
        ai_msg.content = 42  # non-string content — adapter should str() it
        with patch.dict("sys.modules", {
            "langchain_openai":        lc_openai_mod,
            "langchain_core.messages": lc_msgs_mod,
        }):
            result = gate.complete(MESSAGES)
        assert isinstance(result, str)


# ══════════════════════════════════════════════════════════════════════════════
# 7. invoke_chain()
# ══════════════════════════════════════════════════════════════════════════════

class TestInvokeChain:
    def _make_gate(self):
        with patch("langchain_algovoi._build_gate") as mock_build:
            mock_build.return_value = MagicMock()
            from langchain_algovoi import AlgoVoiLangChain
            return AlgoVoiLangChain(**COMMON)

    def test_invoke_calls_chain_invoke(self):
        gate  = self._make_gate()
        chain = MagicMock()
        chain.invoke.return_value = "chain result"
        result = gate.invoke_chain(chain, {"question": "Hello"})
        chain.invoke.assert_called_once_with({"question": "Hello"})
        assert result == "chain result"

    def test_invoke_with_string_input(self):
        gate  = self._make_gate()
        chain = MagicMock()
        chain.invoke.return_value = "output"
        gate.invoke_chain(chain, "plain string input")
        chain.invoke.assert_called_once_with("plain string input")

    def test_invoke_invalid_chain_raises(self):
        gate = self._make_gate()
        with pytest.raises(TypeError, match="Runnable with .invoke"):
            gate.invoke_chain("not a chain", {})

    def test_invoke_returns_chain_output(self):
        gate   = self._make_gate()
        chain  = MagicMock()
        chain.invoke.return_value = {"answer": "42"}
        result = gate.invoke_chain(chain, {})
        assert result == {"answer": "42"}


# ══════════════════════════════════════════════════════════════════════════════
# 8. as_tool() / AlgoVoiPaymentTool
# ══════════════════════════════════════════════════════════════════════════════

class TestAsTool:
    def _make_gate_with_mock_inner(self, requires_payment=True):
        inner = _make_inner(requires_payment=requires_payment)
        with patch("langchain_algovoi._build_gate") as mock_build:
            mock_gate       = MagicMock()
            mock_gate.check = MagicMock(return_value=inner)
            mock_build.return_value = mock_gate
            from langchain_algovoi import AlgoVoiLangChain
            gate        = AlgoVoiLangChain(**COMMON)
            gate._gate  = mock_gate
            # Also wire the adapter's check() so the tool gets LangChainResult
            return gate, inner

    def test_as_tool_returns_payment_tool(self):
        from langchain_algovoi import AlgoVoiLangChain, AlgoVoiPaymentTool, _LC_CORE_AVAILABLE
        if not _LC_CORE_AVAILABLE:
            pytest.skip("langchain-core not installed")
        gate, _ = self._make_gate_with_mock_inner()
        tool = gate.as_tool(resource_fn=lambda q: "ok")
        assert isinstance(tool, AlgoVoiPaymentTool)

    def test_as_tool_custom_name(self):
        from langchain_algovoi import _LC_CORE_AVAILABLE
        if not _LC_CORE_AVAILABLE:
            pytest.skip("langchain-core not installed")
        gate, _ = self._make_gate_with_mock_inner()
        tool = gate.as_tool(resource_fn=lambda q: "ok", tool_name="my_gate")
        assert tool.name == "my_gate"

    def test_as_tool_custom_description(self):
        from langchain_algovoi import _LC_CORE_AVAILABLE
        if not _LC_CORE_AVAILABLE:
            pytest.skip("langchain-core not installed")
        gate, _ = self._make_gate_with_mock_inner()
        tool = gate.as_tool(
            resource_fn=lambda q: "ok",
            tool_description="Custom desc.",
        )
        assert "Custom desc." in tool.description

    def test_as_tool_without_langchain_raises(self):
        from langchain_algovoi import AlgoVoiLangChain, _LC_CORE_AVAILABLE
        if _LC_CORE_AVAILABLE:
            pytest.skip("langchain-core IS installed")
        with patch("langchain_algovoi._build_gate") as mock_build:
            mock_build.return_value = MagicMock()
            gate = AlgoVoiLangChain(**COMMON)
        with pytest.raises(ImportError, match="langchain-core"):
            gate.as_tool(resource_fn=lambda q: "ok")


# ══════════════════════════════════════════════════════════════════════════════
# 9. AlgoVoiPaymentTool._parse_input()
# ══════════════════════════════════════════════════════════════════════════════

class TestParseInput:
    def _tool(self):
        from langchain_algovoi import _LC_CORE_AVAILABLE
        if not _LC_CORE_AVAILABLE:
            pytest.skip("langchain-core not installed")
        from langchain_algovoi import AlgoVoiPaymentTool
        adapter = MagicMock()
        tool    = AlgoVoiPaymentTool.__new__(AlgoVoiPaymentTool)
        object.__setattr__(tool, "_adapter", adapter)
        object.__setattr__(tool, "_resource_fn", lambda q: q)
        return tool

    def test_json_with_proof(self):
        tool  = self._tool()
        query, headers = tool._parse_input('{"query": "hello", "payment_proof": "abc123"}')
        assert query == "hello"
        assert "abc123" in headers.get("Authorization", "")

    def test_json_without_proof(self):
        tool  = self._tool()
        query, headers = tool._parse_input('{"query": "hello"}')
        assert query == "hello"
        assert headers == {}

    def test_invalid_json_treated_as_query(self):
        tool  = self._tool()
        query, headers = tool._parse_input("plain text input")
        assert query == "plain text input"
        assert headers == {}

    def test_empty_proof_no_header(self):
        tool  = self._tool()
        query, headers = tool._parse_input('{"query": "hi", "payment_proof": ""}')
        assert headers == {}

    def test_missing_query_defaults_empty(self):
        tool  = self._tool()
        query, _ = tool._parse_input('{"payment_proof": "abc"}')
        assert query == ""


# ══════════════════════════════════════════════════════════════════════════════
# 10. AlgoVoiPaymentTool._run()
# ══════════════════════════════════════════════════════════════════════════════

class TestPaymentToolRun:
    def _tool(self, requires_payment=True, error=None):
        from langchain_algovoi import _LC_CORE_AVAILABLE
        if not _LC_CORE_AVAILABLE:
            pytest.skip("langchain-core not installed")
        from langchain_algovoi import AlgoVoiPaymentTool, LangChainResult

        inner   = _make_inner(requires_payment=requires_payment, error=error)
        adapter = MagicMock()
        adapter.check.return_value = LangChainResult(inner)

        tool = AlgoVoiPaymentTool.__new__(AlgoVoiPaymentTool)
        object.__setattr__(tool, "_adapter",     adapter)
        object.__setattr__(tool, "_resource_fn", lambda q: f"Answer to: {q}")
        return tool, adapter

    def test_no_proof_returns_challenge_json(self):
        tool, _ = self._tool(requires_payment=True)
        output  = tool._run('{"query": "hello"}')
        data    = json.loads(output)
        assert data["error"] == "payment_required"

    def test_invalid_proof_returns_challenge_json(self):
        tool, _ = self._tool(requires_payment=True, error="bad proof")
        output  = tool._run('{"query": "hi", "payment_proof": "BAD"}')
        data    = json.loads(output)
        assert "payment_required" in data["error"]

    def test_valid_proof_calls_resource_fn(self):
        tool, _ = self._tool(requires_payment=False)
        output  = tool._run('{"query": "hello", "payment_proof": "VALID"}')
        assert output == "Answer to: hello"

    def test_resource_fn_exception_returns_error_json(self):
        from langchain_algovoi import _LC_CORE_AVAILABLE, AlgoVoiPaymentTool, LangChainResult
        if not _LC_CORE_AVAILABLE:
            pytest.skip("langchain-core not installed")
        inner   = _make_inner(requires_payment=False)
        adapter = MagicMock()
        adapter.check.return_value = LangChainResult(inner)

        tool = AlgoVoiPaymentTool.__new__(AlgoVoiPaymentTool)
        object.__setattr__(tool, "_adapter",     adapter)
        object.__setattr__(tool, "_resource_fn", lambda q: (_ for _ in ()).throw(RuntimeError("boom")))

        output = tool._run('{"query": "hi", "payment_proof": "VALID"}')
        data   = json.loads(output)
        assert data["error"] == "resource_error"
        assert "boom" in data["detail"]

    def test_plain_string_input_no_payment(self):
        tool, _ = self._tool(requires_payment=True)
        output  = tool._run("plain text no JSON")
        data    = json.loads(output)
        assert data["error"] == "payment_required"

    def test_adapter_check_called_with_headers(self):
        tool, adapter = self._tool(requires_payment=False)
        tool._run('{"query": "q", "payment_proof": "P123"}')
        call_args = adapter.check.call_args
        hdrs = call_args[0][0]
        assert "P123" in hdrs.get("Authorization", "")

    def test_type_error_fallback(self):
        """If adapter.check() raises TypeError on body kwarg, retries without body."""
        from langchain_algovoi import _LC_CORE_AVAILABLE, AlgoVoiPaymentTool, LangChainResult
        if not _LC_CORE_AVAILABLE:
            pytest.skip("langchain-core not installed")
        inner   = _make_inner(requires_payment=False)
        adapter = MagicMock()
        adapter.check.side_effect = [TypeError("unexpected"), LangChainResult(inner)]

        tool = AlgoVoiPaymentTool.__new__(AlgoVoiPaymentTool)
        object.__setattr__(tool, "_adapter",     adapter)
        object.__setattr__(tool, "_resource_fn", lambda q: "ok")
        output = tool._run('{"query": "q", "payment_proof": "X"}')
        assert output == "ok"


# ══════════════════════════════════════════════════════════════════════════════
# 11. AlgoVoiPaymentTool._arun()
# ══════════════════════════════════════════════════════════════════════════════

class TestPaymentToolArun:
    def test_arun_delegates_to_run(self):
        from langchain_algovoi import _LC_CORE_AVAILABLE, AlgoVoiPaymentTool, LangChainResult
        if not _LC_CORE_AVAILABLE:
            pytest.skip("langchain-core not installed")
        inner   = _make_inner(requires_payment=False)
        adapter = MagicMock()
        adapter.check.return_value = LangChainResult(inner)

        tool = AlgoVoiPaymentTool.__new__(AlgoVoiPaymentTool)
        object.__setattr__(tool, "_adapter",     adapter)
        object.__setattr__(tool, "_resource_fn", lambda q: "async ok")

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            tool._arun('{"query": "hi", "payment_proof": "VALID"}')
        )
        assert result == "async ok"

    def test_arun_returns_string(self):
        from langchain_algovoi import _LC_CORE_AVAILABLE, AlgoVoiPaymentTool, LangChainResult
        if not _LC_CORE_AVAILABLE:
            pytest.skip("langchain-core not installed")
        inner   = _make_inner(requires_payment=True)
        adapter = MagicMock()
        adapter.check.return_value = LangChainResult(inner)

        tool = AlgoVoiPaymentTool.__new__(AlgoVoiPaymentTool)
        object.__setattr__(tool, "_adapter",     adapter)
        object.__setattr__(tool, "_resource_fn", lambda q: "result")

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(tool._arun("{}"))
        assert isinstance(result, str)


# ══════════════════════════════════════════════════════════════════════════════
# 12. flask_guard()
# ══════════════════════════════════════════════════════════════════════════════

class TestFlaskGuard:
    def _make_gate(self, requires_payment=False):
        inner = _make_inner(requires_payment=requires_payment)
        with patch("langchain_algovoi._build_gate") as mock_build:
            mock_gate       = MagicMock()
            mock_gate.check = MagicMock(return_value=inner)
            mock_build.return_value = mock_gate
            from langchain_algovoi import AlgoVoiLangChain
            gate       = AlgoVoiLangChain(**COMMON)
            gate._gate = mock_gate
            return gate

    def test_flask_guard_returns_402_when_no_payment(self):
        gate = self._make_gate(requires_payment=True)
        flask_mod = MagicMock()

        mock_request                = MagicMock()
        mock_request.headers        = {}
        mock_request.content_length = None
        mock_request.get_json       = MagicMock(return_value={})
        flask_mod.request           = mock_request
        flask_mod.Response          = MagicMock(return_value=MagicMock(status=402))
        flask_mod.jsonify           = MagicMock()

        with patch.dict("sys.modules", {"flask": flask_mod}):
            gate.flask_guard()

        flask_mod.Response.assert_called_once()
        call_kwargs = flask_mod.Response.call_args[1]
        assert call_kwargs["status"] == 402

    def test_flask_guard_calls_complete_on_payment(self):
        gate = self._make_gate(requires_payment=False)
        flask_mod = MagicMock()

        mock_request                = MagicMock()
        mock_request.headers        = {"Authorization": "Payment X"}
        mock_request.content_length = None
        mock_request.get_json       = MagicMock(return_value={"messages": MESSAGES})
        flask_mod.request           = mock_request
        flask_mod.jsonify           = MagicMock(return_value={"content": "ok"})

        lc_openai_mod, lc_msgs_mod, _, _, _ = _mock_lc_modules("flask reply")
        with patch.dict("sys.modules", {
            "flask":                   flask_mod,
            "langchain_openai":        lc_openai_mod,
            "langchain_core.messages": lc_msgs_mod,
        }):
            gate.flask_guard()

        flask_mod.jsonify.assert_called_once()

    def test_flask_guard_custom_messages_key(self):
        gate = self._make_gate(requires_payment=False)
        flask_mod = MagicMock()

        custom_msgs               = [{"role": "user", "content": "via custom key"}]
        mock_request                = MagicMock()
        mock_request.headers        = {}
        mock_request.content_length = None
        mock_request.get_json       = MagicMock(return_value={"msgs": custom_msgs})
        flask_mod.request           = mock_request
        flask_mod.jsonify           = MagicMock(return_value={})

        lc_openai_mod, lc_msgs_mod, _, chat_instance, _ = _mock_lc_modules()
        with patch.dict("sys.modules", {
            "flask":                   flask_mod,
            "langchain_openai":        lc_openai_mod,
            "langchain_core.messages": lc_msgs_mod,
        }):
            gate.flask_guard(messages_key="msgs")

        flask_mod.jsonify.assert_called_once()

    def test_flask_guard_empty_body(self):
        gate = self._make_gate(requires_payment=True)
        flask_mod = MagicMock()

        mock_request                = MagicMock()
        mock_request.headers        = {}
        mock_request.content_length = None
        mock_request.get_json       = MagicMock(return_value=None)
        flask_mod.request           = mock_request
        flask_mod.Response          = MagicMock()

        with patch.dict("sys.modules", {"flask": flask_mod}):
            gate.flask_guard()

        flask_mod.Response.assert_called_once()

    def test_flask_guard_rejects_oversized_body(self):
        gate = self._make_gate(requires_payment=False)
        flask_mod = MagicMock()

        mock_request                = MagicMock()
        mock_request.headers        = {}
        mock_request.content_length = 2_000_000  # 2 MB — over the 1 MB cap
        flask_mod.request           = mock_request
        flask_mod.Response          = MagicMock(return_value=MagicMock(status=413))

        with patch.dict("sys.modules", {"flask": flask_mod}):
            gate.flask_guard()

        call_kwargs = flask_mod.Response.call_args
        assert call_kwargs[1]["status"] == 413


# ══════════════════════════════════════════════════════════════════════════════
# 13. Import path assertion
# ══════════════════════════════════════════════════════════════════════════════

class TestImportPaths:
    def test_langchain_openai_import_key(self):
        """Complete() must import ChatOpenAI from langchain_openai (not langchain.llms)."""
        import ast, inspect
        from langchain_algovoi import AlgoVoiLangChain
        src = inspect.getsource(AlgoVoiLangChain.complete)
        assert "langchain_openai" in src

    def test_langchain_core_messages_import_key(self):
        import inspect
        from langchain_algovoi import _to_lc_messages
        src = inspect.getsource(_to_lc_messages)
        assert "langchain_core.messages" in src
