"""
AlgoVoi xAI Adapter — Unit Tests
================================
All tests are fully mocked — no live xAI or AlgoVoi calls.

Run:
    python -m pytest test_xai_algovoi.py -v
    python -m pytest test_xai_algovoi.py -v --tb=short
"""

from __future__ import annotations

import base64
import json
import os
import sys
from unittest.mock import MagicMock, patch, call

import pytest

# ── Path setup ────────────────────────────────────────────────────────────────

_HERE  = os.path.dirname(os.path.abspath(__file__))
_ROOT  = os.path.dirname(os.path.dirname(_HERE))

sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "openai"))
sys.path.insert(0, os.path.join(_ROOT, "mpp-adapter"))
sys.path.insert(0, os.path.join(_ROOT, "ap2-adapter"))

# ── Fixtures ──────────────────────────────────────────────────────────────────

COMMON = dict(
    xai_key           = "xai-test-key-EXAMPLE",
    algovoi_key       = "algv_test",
    tenant_id         = "test-tenant",
    payout_address    = "ZVLRVYQSLJNVFMOIOKT35XH5SNQG45IVFMLLRFLHDQJQA5TO5H3SO4TVDQ",
    amount_microunits = 10000,
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
        '{"error":"Payment Required"}', 402, {"WWW-Authenticate": "Payment ..."}
    )
    inner.as_wsgi_response.return_value = (
        "402 Payment Required",
        [("WWW-Authenticate", "Payment ...")],
        b'{"error":"Payment Required"}',
    )
    return inner


def _mock_xai_sdk(reply_text: str = "Hello from Grok!"):
    """Build a fake xai_sdk module tree that the adapter can import."""
    # Response with .content == reply_text
    response = MagicMock()
    response.content = reply_text

    # Chat instance: append() returns self; sample() returns response
    chat_instance = MagicMock()
    chat_instance.append.return_value = chat_instance
    chat_instance.sample.return_value = response

    # Client().chat.create(...) returns chat_instance
    client_instance = MagicMock()
    client_instance.chat.create.return_value = chat_instance

    # The top-level Client class constructs client_instance
    xai_sdk = MagicMock()
    xai_sdk.Client.return_value = client_instance

    # Role helpers — just tag the message so we can inspect what was appended
    def _user(text):
        return {"role": "user", "content": text}

    def _system(text):
        return {"role": "system", "content": text}

    def _assistant(text):
        return {"role": "assistant", "content": text}

    xai_sdk_chat = MagicMock()
    xai_sdk_chat.user      = _user
    xai_sdk_chat.system    = _system
    xai_sdk_chat.assistant = _assistant

    return xai_sdk, xai_sdk_chat, client_instance, chat_instance


# ══════════════════════════════════════════════════════════════════════════════
# 1. Construction
# ══════════════════════════════════════════════════════════════════════════════

class TestConstruction:
    def test_x402_construction(self):
        with patch("xai_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from xai_algovoi import AlgoVoiXai
            AlgoVoiXai(**COMMON, protocol="x402")
            assert mock_gate.call_args[0][0] == "x402"

    def test_mpp_construction(self):
        with patch("xai_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from xai_algovoi import AlgoVoiXai
            AlgoVoiXai(**COMMON, protocol="mpp")
            assert mock_gate.call_args[0][0] == "mpp"

    def test_ap2_construction(self):
        with patch("xai_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from xai_algovoi import AlgoVoiXai
            AlgoVoiXai(**COMMON, protocol="ap2")
            assert mock_gate.call_args[0][0] == "ap2"

    def test_default_protocol_is_mpp(self):
        with patch("xai_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from xai_algovoi import AlgoVoiXai
            AlgoVoiXai(**COMMON)
            assert mock_gate.call_args[0][0] == "mpp"

    def test_default_model_is_grok_4(self):
        with patch("xai_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from xai_algovoi import AlgoVoiXai
            gate = AlgoVoiXai(**COMMON)
            assert gate._model == "grok-4"

    def test_custom_model(self):
        with patch("xai_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from xai_algovoi import AlgoVoiXai
            gate = AlgoVoiXai(**COMMON, model="grok-3-mini")
            assert gate._model == "grok-3-mini"

    def test_xai_key_stored(self):
        with patch("xai_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from xai_algovoi import AlgoVoiXai
            gate = AlgoVoiXai(**COMMON)
            assert gate._xai_key == "xai-test-key-EXAMPLE"

    def test_default_network(self):
        with patch("xai_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from xai_algovoi import AlgoVoiXai
            AlgoVoiXai(**COMMON)
            # positional: network is arg[4]
            assert mock_gate.call_args[0][4] == "algorand-mainnet"

    def test_invalid_network(self):
        from xai_algovoi import AlgoVoiXai
        with pytest.raises(ValueError, match="network must be one of"):
            AlgoVoiXai(**COMMON, network="invalid-net")

    def test_invalid_protocol(self):
        from xai_algovoi import AlgoVoiXai
        with pytest.raises(ValueError, match="protocol must be one of"):
            AlgoVoiXai(**COMMON, protocol="grpc")

    def test_all_networks_accepted(self):
        for net in ["algorand-mainnet", "voi-mainnet", "hedera-mainnet", "stellar-mainnet"]:
            with patch("xai_algovoi._build_gate") as mock_gate:
                mock_gate.return_value = MagicMock()
                from xai_algovoi import AlgoVoiXai
                AlgoVoiXai(**COMMON, network=net)  # should not raise

    def test_custom_resource_id(self):
        with patch("xai_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from xai_algovoi import AlgoVoiXai
            AlgoVoiXai(**COMMON, resource_id="custom-resource")
            assert mock_gate.call_args[0][6] == "custom-resource"


# ══════════════════════════════════════════════════════════════════════════════
# 2. check() — payment required
# ══════════════════════════════════════════════════════════════════════════════

class TestCheckPaymentRequired:
    def _gate(self, protocol="mpp"):
        with patch("xai_algovoi._build_gate") as mock_build:
            mock_build.return_value = MagicMock()
            from xai_algovoi import AlgoVoiXai
            gate = AlgoVoiXai(**COMMON, protocol=protocol)
            gate._gate = MagicMock()
            return gate

    def test_no_payment_returns_requires_payment(self):
        gate = self._gate()
        gate._gate.check.return_value = _make_inner(requires_payment=True)
        result = gate.check({})
        assert result.requires_payment is True

    def test_as_flask_response_402(self):
        gate = self._gate()
        gate._gate.check.return_value = _make_inner(requires_payment=True)
        result = gate.check({})
        body, status, headers = result.as_flask_response()
        assert status == 402

    def test_as_wsgi_response_402(self):
        gate = self._gate()
        gate._gate.check.return_value = _make_inner(requires_payment=True)
        result = gate.check({})
        status_str, header_list, body_bytes = result.as_wsgi_response()
        assert "402" in status_str

    def test_mpp_falls_back_to_headers_only(self):
        gate = self._gate("mpp")
        gate._gate.check.side_effect = [TypeError, _make_inner()]
        gate.check({"Authorization": "Payment abc"}, {"messages": []})
        # Second call (after TypeError) should be headers-only
        assert gate._gate.check.call_count == 2

    def test_ap2_passes_body(self):
        gate = self._gate("ap2")
        gate._gate.check.return_value = _make_inner()
        gate.check({"X-AP2": "mandate"}, {"messages": []})
        gate._gate.check.assert_called_once()

    def test_error_message_exposed(self):
        gate = self._gate()
        gate._gate.check.return_value = _make_inner(requires_payment=True, error="TX expired")
        result = gate.check({})
        assert result.error == "TX expired"


# ══════════════════════════════════════════════════════════════════════════════
# 3. check() — payment accepted
# ══════════════════════════════════════════════════════════════════════════════

class TestCheckPaymentAccepted:
    def _gate(self):
        with patch("xai_algovoi._build_gate") as mock_build:
            mock_build.return_value = MagicMock()
            from xai_algovoi import AlgoVoiXai
            gate = AlgoVoiXai(**COMMON)
            gate._gate = MagicMock()
            return gate

    def test_valid_payment_not_requires_payment(self):
        gate = self._gate()
        gate._gate.check.return_value = _make_inner(requires_payment=False)
        result = gate.check({"Authorization": "Payment abc"})
        assert result.requires_payment is False

    def test_mpp_receipt_exposed(self):
        gate = self._gate()
        receipt = MagicMock(payer="ADDR", tx_id="TX123", amount=10000)
        inner = _make_inner()
        inner.receipt = receipt
        gate._gate.check.return_value = inner
        result = gate.check({"Authorization": "Payment abc"})
        assert result.receipt.payer == "ADDR"
        assert result.receipt.tx_id == "TX123"
        assert result.receipt.amount == 10000

    def test_ap2_mandate_exposed(self):
        gate = self._gate()
        mandate = MagicMock(payer_address="ADDR", network="algorand-mainnet", tx_id="TX456")
        inner = _make_inner()
        inner.mandate = mandate
        gate._gate.check.return_value = inner
        result = gate.check({})
        assert result.mandate.payer_address == "ADDR"


# ══════════════════════════════════════════════════════════════════════════════
# 4. complete() — message conversion
# ══════════════════════════════════════════════════════════════════════════════

class TestCompleteMessageConversion:
    def _gate(self, **kwargs):
        with patch("xai_algovoi._build_gate") as mock_build:
            mock_build.return_value = MagicMock()
            from xai_algovoi import AlgoVoiXai
            return AlgoVoiXai(**COMMON, **kwargs)

    def _patch_modules(self, reply_text="Hello!"):
        xai_sdk, xai_sdk_chat, client_instance, chat_instance = _mock_xai_sdk(reply_text)
        return (
            patch.dict("sys.modules", {
                "xai_sdk": xai_sdk,
                "xai_sdk.chat": xai_sdk_chat,
            }),
            client_instance,
            chat_instance,
        )

    def test_system_role_appended_as_system(self):
        gate = self._gate()
        ctx, client, chat = self._patch_modules()
        with ctx:
            gate.complete(MESSAGES)
        # Examine what was appended — first append call = system
        first_arg = chat.append.call_args_list[0][0][0]
        assert first_arg["role"] == "system"
        assert first_arg["content"] == "You are a helpful assistant."

    def test_user_role_appended_as_user(self):
        gate = self._gate()
        ctx, client, chat = self._patch_modules()
        with ctx:
            gate.complete([{"role": "user", "content": "Hello"}])
        arg = chat.append.call_args_list[0][0][0]
        assert arg["role"] == "user"
        assert arg["content"] == "Hello"

    def test_assistant_role_appended_as_assistant(self):
        gate = self._gate()
        ctx, client, chat = self._patch_modules()
        with ctx:
            gate.complete([{"role": "assistant", "content": "Hi"}])
        arg = chat.append.call_args_list[0][0][0]
        assert arg["role"] == "assistant"

    def test_multi_turn_all_messages_appended(self):
        gate = self._gate()
        ctx, client, chat = self._patch_modules()
        with ctx:
            gate.complete(MESSAGES)
        assert chat.append.call_count == 4

    def test_multi_turn_order_preserved(self):
        gate = self._gate()
        ctx, client, chat = self._patch_modules()
        with ctx:
            gate.complete(MESSAGES)
        roles = [c[0][0]["role"] for c in chat.append.call_args_list]
        assert roles == ["system", "user", "assistant", "user"]

    def test_messages_without_system_work(self):
        gate = self._gate()
        ctx, client, chat = self._patch_modules()
        with ctx:
            gate.complete(MESSAGES_NO_SYSTEM)
        assert chat.append.call_count == 3
        # No system role appended
        roles = [c[0][0]["role"] for c in chat.append.call_args_list]
        assert "system" not in roles

    def test_unknown_role_skipped(self):
        """Unknown roles (e.g. 'tool') should be skipped, not mapped to user.
        Silently injecting a tool turn as a user message would corrupt the
        conversation shape (Grok has no native tool-role concept)."""
        gate = self._gate()
        ctx, client, chat = self._patch_modules()
        with ctx:
            gate.complete([
                {"role": "user", "content": "Hi"},
                {"role": "tool", "content": "tool-output"},
                {"role": "user", "content": "Bye"},
            ])
        # Two user messages appended, tool message skipped.
        assert chat.append.call_count == 2
        roles = [c[0][0]["role"] for c in chat.append.call_args_list]
        assert roles == ["user", "user"]

    def test_unknown_role_only_messages_yields_no_appends(self):
        gate = self._gate()
        ctx, client, chat = self._patch_modules()
        with ctx:
            gate.complete([{"role": "tool", "content": "x"}])
        assert chat.append.call_count == 0

    def test_missing_role_defaults_to_user(self):
        gate = self._gate()
        ctx, client, chat = self._patch_modules()
        with ctx:
            gate.complete([{"content": "Hello"}])
        arg = chat.append.call_args_list[0][0][0]
        assert arg["role"] == "user"

    def test_missing_content_treated_as_empty(self):
        gate = self._gate()
        ctx, client, chat = self._patch_modules()
        with ctx:
            gate.complete([{"role": "user"}])
        arg = chat.append.call_args_list[0][0][0]
        assert arg["content"] == ""

    def test_returns_text_string(self):
        gate = self._gate()
        ctx, client, chat = self._patch_modules("Hello from Grok!")
        with ctx:
            result = gate.complete([{"role": "user", "content": "Hi"}])
        assert result == "Hello from Grok!"

    def test_returns_string_even_for_non_string_content(self):
        gate = self._gate()
        xai_sdk, xai_sdk_chat, client_instance, chat_instance = _mock_xai_sdk()
        # Force response.content to an int — adapter should str() it
        chat_instance.sample.return_value.content = 12345
        with patch.dict("sys.modules", {"xai_sdk": xai_sdk, "xai_sdk.chat": xai_sdk_chat}):
            result = gate.complete([{"role": "user", "content": "Hi"}])
        assert result == "12345"

    def test_default_model_used(self):
        gate = self._gate()
        ctx, client, chat = self._patch_modules()
        with ctx:
            gate.complete([{"role": "user", "content": "Hi"}])
        call_kwargs = client.chat.create.call_args[1]
        assert call_kwargs["model"] == "grok-4"

    def test_model_override(self):
        gate = self._gate()
        ctx, client, chat = self._patch_modules()
        with ctx:
            gate.complete([{"role": "user", "content": "Hi"}], model="grok-3-mini")
        call_kwargs = client.chat.create.call_args[1]
        assert call_kwargs["model"] == "grok-3-mini"

    def test_kwargs_forwarded_to_create(self):
        gate = self._gate()
        ctx, client, chat = self._patch_modules()
        with ctx:
            gate.complete([{"role": "user", "content": "Hi"}], temperature=0.5)
        call_kwargs = client.chat.create.call_args[1]
        assert call_kwargs["temperature"] == 0.5

    def test_xai_sdk_import_error(self):
        gate = self._gate()
        # Simulate xai_sdk not being importable
        with patch.dict("sys.modules", {"xai_sdk": None, "xai_sdk.chat": None}):
            with pytest.raises(ImportError, match="xai-sdk"):
                gate.complete([{"role": "user", "content": "Hi"}])


# ══════════════════════════════════════════════════════════════════════════════
# 5. complete() — client construction
# ══════════════════════════════════════════════════════════════════════════════

class TestCompleteClientConstruction:
    def _gate(self, **kwargs):
        with patch("xai_algovoi._build_gate") as mock_build:
            mock_build.return_value = MagicMock()
            from xai_algovoi import AlgoVoiXai
            return AlgoVoiXai(**COMMON, **kwargs)

    def test_xai_key_passed_to_client(self):
        gate = self._gate()
        xai_sdk, xai_sdk_chat, client_instance, chat_instance = _mock_xai_sdk()
        with patch.dict("sys.modules", {"xai_sdk": xai_sdk, "xai_sdk.chat": xai_sdk_chat}):
            gate.complete([{"role": "user", "content": "Hi"}])
        call_kwargs = xai_sdk.Client.call_args[1]
        assert call_kwargs["api_key"] == "xai-test-key-EXAMPLE"

    def test_client_is_persistent_across_complete_calls(self):
        """Regression — previously created a new Client per complete()
        call, paying a gRPC handshake each time. Should now reuse."""
        gate = self._gate()
        xai_sdk, xai_sdk_chat, client_instance, chat_instance = _mock_xai_sdk()
        with patch.dict("sys.modules", {"xai_sdk": xai_sdk, "xai_sdk.chat": xai_sdk_chat}):
            gate.complete([{"role": "user", "content": "Hi"}])
            gate.complete([{"role": "user", "content": "Hi again"}])
        assert xai_sdk.Client.call_count == 1   # constructed once
        assert client_instance.chat.create.call_count == 2  # reused for each call

    def test_client_lazy_initialized(self):
        """Client should not be constructed until first complete() call."""
        gate = self._gate()
        assert gate._xai_client is None

    def test_chat_create_called(self):
        gate = self._gate()
        xai_sdk, xai_sdk_chat, client_instance, chat_instance = _mock_xai_sdk()
        with patch.dict("sys.modules", {"xai_sdk": xai_sdk, "xai_sdk.chat": xai_sdk_chat}):
            gate.complete([{"role": "user", "content": "Hi"}])
        client_instance.chat.create.assert_called_once()

    def test_sample_called(self):
        gate = self._gate()
        xai_sdk, xai_sdk_chat, client_instance, chat_instance = _mock_xai_sdk()
        with patch.dict("sys.modules", {"xai_sdk": xai_sdk, "xai_sdk.chat": xai_sdk_chat}):
            gate.complete([{"role": "user", "content": "Hi"}])
        chat_instance.sample.assert_called_once()

    def test_close_releases_client(self):
        gate = self._gate()
        xai_sdk, xai_sdk_chat, client_instance, chat_instance = _mock_xai_sdk()
        with patch.dict("sys.modules", {"xai_sdk": xai_sdk, "xai_sdk.chat": xai_sdk_chat}):
            gate.complete([{"role": "user", "content": "Hi"}])
        assert gate._xai_client is not None
        gate.close()
        client_instance.close.assert_called_once()
        assert gate._xai_client is None

    def test_close_idempotent(self):
        gate = self._gate()
        # close() on an uninitialised adapter should be a no-op.
        gate.close()
        gate.close()   # Second call should also be fine.

    def test_close_swallows_client_close_error(self):
        """If client.close() raises, the adapter's close() should NOT propagate."""
        gate = self._gate()
        xai_sdk, xai_sdk_chat, client_instance, chat_instance = _mock_xai_sdk()
        client_instance.close.side_effect = RuntimeError("close failed")
        with patch.dict("sys.modules", {"xai_sdk": xai_sdk, "xai_sdk.chat": xai_sdk_chat}):
            gate.complete([{"role": "user", "content": "Hi"}])
        gate.close()   # Must not raise.
        assert gate._xai_client is None

    def test_context_manager_closes_on_exit(self):
        gate = self._gate()
        xai_sdk, xai_sdk_chat, client_instance, chat_instance = _mock_xai_sdk()
        with patch.dict("sys.modules", {"xai_sdk": xai_sdk, "xai_sdk.chat": xai_sdk_chat}):
            with gate as g:
                g.complete([{"role": "user", "content": "Hi"}])
            # After exit, client should have been closed
        client_instance.close.assert_called_once()
        assert gate._xai_client is None

    def test_context_manager_closes_on_exception(self):
        gate = self._gate()
        xai_sdk, xai_sdk_chat, client_instance, chat_instance = _mock_xai_sdk()
        chat_instance.sample.side_effect = RuntimeError("boom")
        with patch.dict("sys.modules", {"xai_sdk": xai_sdk, "xai_sdk.chat": xai_sdk_chat}):
            with pytest.raises(RuntimeError):
                with gate as g:
                    g.complete([{"role": "user", "content": "Hi"}])
        # Client still constructed; cleanup still happens.
        client_instance.close.assert_called_once()

    def test_concurrent_first_calls_construct_client_once(self):
        """Double-checked locking in _ensure_client must prevent two
        concurrent first-calls from constructing two clients."""
        import threading
        gate = self._gate()
        xai_sdk, xai_sdk_chat, client_instance, chat_instance = _mock_xai_sdk()

        start = threading.Event()
        def worker():
            start.wait()
            with patch.dict("sys.modules", {"xai_sdk": xai_sdk, "xai_sdk.chat": xai_sdk_chat}):
                gate.complete([{"role": "user", "content": "Hi"}])

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        start.set()
        for t in threads:
            t.join()

        assert xai_sdk.Client.call_count == 1   # constructed ONCE across 8 threads


# ══════════════════════════════════════════════════════════════════════════════
# 6. XaiAiResult
# ══════════════════════════════════════════════════════════════════════════════

class TestXaiAiResult:
    def test_requires_payment_true(self):
        from xai_algovoi import XaiAiResult
        inner = _make_inner(requires_payment=True)
        r = XaiAiResult(inner)
        assert r.requires_payment is True

    def test_requires_payment_false(self):
        from xai_algovoi import XaiAiResult
        inner = _make_inner(requires_payment=False)
        r = XaiAiResult(inner)
        assert r.requires_payment is False

    def test_flask_response_delegates(self):
        from xai_algovoi import XaiAiResult
        inner = _make_inner(requires_payment=True)
        r = XaiAiResult(inner)
        body, status, headers = r.as_flask_response()
        assert status == 402

    def test_wsgi_response_delegates(self):
        from xai_algovoi import XaiAiResult
        inner = _make_inner(requires_payment=True)
        r = XaiAiResult(inner)
        status_str, header_list, body_bytes = r.as_wsgi_response()
        assert "402" in status_str

    def test_flask_fallback_when_no_method(self):
        from xai_algovoi import XaiAiResult
        inner = MagicMock(spec=[])
        inner.requires_payment = True
        inner.error = "expired"
        r = XaiAiResult(inner)
        body, status, headers = r.as_flask_response()
        assert status == 402
        assert "expired" in body

    def test_wsgi_fallback_when_no_method(self):
        from xai_algovoi import XaiAiResult
        inner = MagicMock(spec=[])
        inner.requires_payment = True
        inner.error = ""
        r = XaiAiResult(inner)
        status_str, header_list, body_bytes = r.as_wsgi_response()
        assert "402" in status_str
        assert b"Payment Required" in body_bytes

    def test_receipt_none_by_default(self):
        from xai_algovoi import XaiAiResult
        inner = _make_inner()
        r = XaiAiResult(inner)
        assert r.receipt is None

    def test_mandate_none_by_default(self):
        from xai_algovoi import XaiAiResult
        inner = _make_inner()
        r = XaiAiResult(inner)
        assert r.mandate is None


# ══════════════════════════════════════════════════════════════════════════════
# 7. flask_guard()
# ══════════════════════════════════════════════════════════════════════════════

class TestFlaskGuard:
    def _gate(self):
        with patch("xai_algovoi._build_gate") as mock_build:
            mock_build.return_value = MagicMock()
            from xai_algovoi import AlgoVoiXai
            gate = AlgoVoiXai(**COMMON)
            gate._gate = MagicMock()
            return gate

    def test_guard_returns_402_without_payment(self):
        gate = self._gate()
        gate._gate.check.return_value = _make_inner(requires_payment=True)
        flask = MagicMock()
        flask.request.get_json.return_value = {}
        flask.request.headers = {}
        with patch.dict("sys.modules", {"flask": flask}):
            gate.flask_guard()
        flask.Response.assert_called_once()

    def test_guard_calls_complete_on_success(self):
        gate = self._gate()
        gate._gate.check.return_value = _make_inner(requires_payment=False)
        xai_sdk, xai_sdk_chat, client_instance, chat_instance = _mock_xai_sdk("Hi!")
        flask = MagicMock()
        flask.request.get_json.return_value = {"messages": [{"role": "user", "content": "Hello"}]}
        flask.request.headers = {"Authorization": "Payment abc"}
        with patch.dict("sys.modules",
                        {"flask": flask, "xai_sdk": xai_sdk, "xai_sdk.chat": xai_sdk_chat}):
            gate.flask_guard()
        flask.jsonify.assert_called_once_with({"content": "Hi!"})

    def test_guard_uses_custom_messages_key(self):
        gate = self._gate()
        gate._gate.check.return_value = _make_inner(requires_payment=False)
        xai_sdk, xai_sdk_chat, client_instance, chat_instance = _mock_xai_sdk("Hi!")
        flask = MagicMock()
        flask.request.get_json.return_value = {"msgs": [{"role": "user", "content": "Hello"}]}
        flask.request.headers = {}
        with patch.dict("sys.modules",
                        {"flask": flask, "xai_sdk": xai_sdk, "xai_sdk.chat": xai_sdk_chat}):
            gate.flask_guard(messages_key="msgs")
        flask.jsonify.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
# 8. Gate factory — path injection
# ══════════════════════════════════════════════════════════════════════════════

class TestBuildGate:
    def test_x402_loads_from_openai_adapter(self):
        x402_mock = MagicMock()
        x402_mock._X402Gate.return_value = MagicMock()
        with patch.dict("sys.modules", {"openai_algovoi": x402_mock}):
            from xai_algovoi import _build_gate
            _build_gate("x402", "algv_test", "tenant", "ADDR",
                        "algorand-mainnet", 10000, "ai-chat")
        x402_mock._X402Gate.assert_called_once()

    def test_mpp_loads_mpp_gate(self):
        mpp_mock = MagicMock()
        mpp_mock.MppGate.return_value = MagicMock()
        with patch.dict("sys.modules", {"mpp": mpp_mock}):
            from xai_algovoi import _build_gate
            _build_gate("mpp", "algv_test", "tenant", "ADDR",
                        "algorand-mainnet", 10000, "ai-chat")
        mpp_mock.MppGate.assert_called_once()

    def test_ap2_loads_ap2_gate(self):
        ap2_mock = MagicMock()
        ap2_mock.Ap2Gate.return_value = MagicMock()
        with patch.dict("sys.modules", {"ap2": ap2_mock}):
            from xai_algovoi import _build_gate
            _build_gate("ap2", "algv_test", "tenant", "ADDR",
                        "algorand-mainnet", 10000, "ai-chat")
        ap2_mock.Ap2Gate.assert_called_once()

    def test_mpp_uses_snake_case_network(self):
        mpp_mock = MagicMock()
        mpp_mock.MppGate.return_value = MagicMock()
        with patch.dict("sys.modules", {"mpp": mpp_mock}):
            from xai_algovoi import _build_gate
            _build_gate("mpp", "algv_test", "tenant", "ADDR",
                        "voi-mainnet", 10000, "ai-chat")
        call_kwargs = mpp_mock.MppGate.call_args[1]
        assert "voi_mainnet" in call_kwargs["networks"]

    def test_all_four_networks_valid_for_mpp(self):
        for net in ["algorand-mainnet", "voi-mainnet", "hedera-mainnet", "stellar-mainnet"]:
            mpp_mock = MagicMock()
            mpp_mock.MppGate.return_value = MagicMock()
            with patch.dict("sys.modules", {"mpp": mpp_mock}):
                from xai_algovoi import _build_gate
                _build_gate("mpp", "k", "t", "A", net, 10000, "r")

    def test_ap2_uses_kebab_case_network(self):
        """AP2 uses kebab-case network IDs (unlike MPP which uses snake_case)."""
        ap2_mock = MagicMock()
        ap2_mock.Ap2Gate.return_value = MagicMock()
        with patch.dict("sys.modules", {"ap2": ap2_mock}):
            from xai_algovoi import _build_gate
            _build_gate("ap2", "algv_test", "tenant", "ADDR",
                        "stellar-mainnet", 10000, "ai-chat")
        call_kwargs = ap2_mock.Ap2Gate.call_args[1]
        assert "stellar-mainnet" in call_kwargs["networks"]


# ══════════════════════════════════════════════════════════════════════════════
# 9. Module constants
# ══════════════════════════════════════════════════════════════════════════════

class TestModuleConstants:
    def test_networks_constant(self):
        from xai_algovoi import NETWORKS
        assert "algorand-mainnet" in NETWORKS
        assert "voi-mainnet" in NETWORKS
        assert "hedera-mainnet" in NETWORKS
        assert "stellar-mainnet" in NETWORKS
        assert len(NETWORKS) == 4

    def test_protocols_constant(self):
        from xai_algovoi import PROTOCOLS
        assert set(PROTOCOLS) == {"x402", "mpp", "ap2"}

    def test_snake_map_covers_all_networks(self):
        from xai_algovoi import _SNAKE, NETWORKS
        for net in NETWORKS:
            assert net in _SNAKE
            # snake case means underscores not dashes
            assert "-" not in _SNAKE[net]
            assert "_" in _SNAKE[net]

    def test_version(self):
        from xai_algovoi import __version__
        assert __version__ == "1.0.0"

    def test_api_base_is_production(self):
        from xai_algovoi import _API_BASE
        assert _API_BASE.startswith("https://")
        assert "ilovechicken.co.uk" in _API_BASE
