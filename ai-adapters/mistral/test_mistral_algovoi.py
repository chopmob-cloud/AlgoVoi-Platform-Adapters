"""
AlgoVoi Mistral Adapter — Unit Tests
=====================================
All tests are fully mocked — no live Mistral or AlgoVoi calls.

Run:
    python -m pytest test_mistral_algovoi.py -v
    python -m pytest test_mistral_algovoi.py -v --tb=short
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

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
    mistral_key       = "MISTRAL-test-key-EXAMPLE",
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


def _mock_mistral_sdk(reply_text: str = "Bonjour from Mistral!"):
    """Build a fake mistralai.client module tree that the adapter can import."""
    # Response shape: resp.choices[0].message.content
    message = MagicMock()
    message.content = reply_text
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]

    # client.chat.complete(...) returns response
    client_instance = MagicMock()
    client_instance.chat.complete.return_value = response
    # __exit__ is the teardown path used by close()
    client_instance.__exit__ = MagicMock(return_value=False)

    # mistralai.client exposes Mistral class
    sdk_mod = MagicMock()
    sdk_mod.Mistral.return_value = client_instance

    return sdk_mod, client_instance, response


# ══════════════════════════════════════════════════════════════════════════════
# 1. Construction
# ══════════════════════════════════════════════════════════════════════════════

class TestConstruction:
    def test_x402_construction(self):
        with patch("mistral_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from mistral_algovoi import AlgoVoiMistral
            AlgoVoiMistral(**COMMON, protocol="x402")
            assert mock_gate.call_args[0][0] == "x402"

    def test_mpp_construction(self):
        with patch("mistral_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from mistral_algovoi import AlgoVoiMistral
            AlgoVoiMistral(**COMMON, protocol="mpp")
            assert mock_gate.call_args[0][0] == "mpp"

    def test_ap2_construction(self):
        with patch("mistral_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from mistral_algovoi import AlgoVoiMistral
            AlgoVoiMistral(**COMMON, protocol="ap2")
            assert mock_gate.call_args[0][0] == "ap2"

    def test_default_protocol_is_mpp(self):
        with patch("mistral_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from mistral_algovoi import AlgoVoiMistral
            AlgoVoiMistral(**COMMON)
            assert mock_gate.call_args[0][0] == "mpp"

    def test_default_model_is_large_latest(self):
        with patch("mistral_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from mistral_algovoi import AlgoVoiMistral
            gate = AlgoVoiMistral(**COMMON)
            assert gate._model == "mistral-large-latest"

    def test_custom_model(self):
        with patch("mistral_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from mistral_algovoi import AlgoVoiMistral
            gate = AlgoVoiMistral(**COMMON, model="codestral-latest")
            assert gate._model == "codestral-latest"

    def test_mistral_key_stored(self):
        with patch("mistral_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from mistral_algovoi import AlgoVoiMistral
            gate = AlgoVoiMistral(**COMMON)
            assert gate._mistral_key == "MISTRAL-test-key-EXAMPLE"

    def test_default_network(self):
        with patch("mistral_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from mistral_algovoi import AlgoVoiMistral
            AlgoVoiMistral(**COMMON)
            assert mock_gate.call_args[0][4] == "algorand-mainnet"

    def test_invalid_network(self):
        from mistral_algovoi import AlgoVoiMistral
        with pytest.raises(ValueError, match="network must be one of"):
            AlgoVoiMistral(**COMMON, network="invalid-net")

    def test_invalid_protocol(self):
        from mistral_algovoi import AlgoVoiMistral
        with pytest.raises(ValueError, match="protocol must be one of"):
            AlgoVoiMistral(**COMMON, protocol="grpc")

    def test_all_networks_accepted(self):
        for net in ["algorand-mainnet", "voi-mainnet", "hedera-mainnet", "stellar-mainnet"]:
            with patch("mistral_algovoi._build_gate") as mock_gate:
                mock_gate.return_value = MagicMock()
                from mistral_algovoi import AlgoVoiMistral
                AlgoVoiMistral(**COMMON, network=net)

    def test_custom_resource_id(self):
        with patch("mistral_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from mistral_algovoi import AlgoVoiMistral
            AlgoVoiMistral(**COMMON, resource_id="custom-resource")
            assert mock_gate.call_args[0][6] == "custom-resource"


# ══════════════════════════════════════════════════════════════════════════════
# 2. check() — payment required
# ══════════════════════════════════════════════════════════════════════════════

class TestCheckPaymentRequired:
    def _gate(self, protocol="mpp"):
        with patch("mistral_algovoi._build_gate") as mock_build:
            mock_build.return_value = MagicMock()
            from mistral_algovoi import AlgoVoiMistral
            gate = AlgoVoiMistral(**COMMON, protocol=protocol)
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
        _, status, _ = result.as_flask_response()
        assert status == 402

    def test_as_wsgi_response_402(self):
        gate = self._gate()
        gate._gate.check.return_value = _make_inner(requires_payment=True)
        result = gate.check({})
        status_str, _, _ = result.as_wsgi_response()
        assert "402" in status_str

    def test_mpp_falls_back_to_headers_only(self):
        gate = self._gate("mpp")
        gate._gate.check.side_effect = [TypeError, _make_inner()]
        gate.check({"Authorization": "Payment abc"}, {"messages": []})
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
        with patch("mistral_algovoi._build_gate") as mock_build:
            mock_build.return_value = MagicMock()
            from mistral_algovoi import AlgoVoiMistral
            gate = AlgoVoiMistral(**COMMON)
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
        with patch("mistral_algovoi._build_gate") as mock_build:
            mock_build.return_value = MagicMock()
            from mistral_algovoi import AlgoVoiMistral
            return AlgoVoiMistral(**COMMON, **kwargs)

    def _patch_modules(self, reply_text="Bonjour!"):
        sdk_mod, client_instance, response = _mock_mistral_sdk(reply_text)
        return (
            patch.dict("sys.modules", {"mistralai.client": sdk_mod}),
            client_instance,
        )

    def test_system_role_passed_through(self):
        gate = self._gate()
        ctx, client = self._patch_modules()
        with ctx:
            gate.complete(MESSAGES)
        call_kwargs = client.chat.complete.call_args[1]
        system_msgs = [m for m in call_kwargs["messages"] if m["role"] == "system"]
        assert len(system_msgs) == 1
        assert system_msgs[0]["content"] == "You are a helpful assistant."

    def test_user_role_passed_through(self):
        gate = self._gate()
        ctx, client = self._patch_modules()
        with ctx:
            gate.complete([{"role": "user", "content": "Hi"}])
        call_kwargs = client.chat.complete.call_args[1]
        assert call_kwargs["messages"] == [{"role": "user", "content": "Hi"}]

    def test_assistant_role_passed_through(self):
        gate = self._gate()
        ctx, client = self._patch_modules()
        with ctx:
            gate.complete([{"role": "assistant", "content": "Hello"}])
        call_kwargs = client.chat.complete.call_args[1]
        assert call_kwargs["messages"][0]["role"] == "assistant"

    def test_multi_turn_all_messages_passed(self):
        gate = self._gate()
        ctx, client = self._patch_modules()
        with ctx:
            gate.complete(MESSAGES)
        call_kwargs = client.chat.complete.call_args[1]
        assert len(call_kwargs["messages"]) == 4

    def test_multi_turn_order_preserved(self):
        gate = self._gate()
        ctx, client = self._patch_modules()
        with ctx:
            gate.complete(MESSAGES)
        call_kwargs = client.chat.complete.call_args[1]
        roles = [m["role"] for m in call_kwargs["messages"]]
        assert roles == ["system", "user", "assistant", "user"]

    def test_messages_without_system_work(self):
        gate = self._gate()
        ctx, client = self._patch_modules()
        with ctx:
            gate.complete(MESSAGES_NO_SYSTEM)
        call_kwargs = client.chat.complete.call_args[1]
        assert len(call_kwargs["messages"]) == 3
        assert "system" not in [m["role"] for m in call_kwargs["messages"]]

    def test_unknown_role_skipped(self):
        """Unknown roles (e.g. 'tool') should be skipped, not mapped to user."""
        gate = self._gate()
        ctx, client = self._patch_modules()
        with ctx:
            gate.complete([
                {"role": "user", "content": "Hi"},
                {"role": "tool", "content": "tool-output"},
                {"role": "user", "content": "Bye"},
            ])
        call_kwargs = client.chat.complete.call_args[1]
        # Two user messages, tool skipped
        assert len(call_kwargs["messages"]) == 2
        assert all(m["role"] == "user" for m in call_kwargs["messages"])

    def test_unknown_role_only_yields_empty_list(self):
        gate = self._gate()
        ctx, client = self._patch_modules()
        with ctx:
            gate.complete([{"role": "tool", "content": "x"}])
        call_kwargs = client.chat.complete.call_args[1]
        assert call_kwargs["messages"] == []

    def test_missing_role_defaults_to_user(self):
        gate = self._gate()
        ctx, client = self._patch_modules()
        with ctx:
            gate.complete([{"content": "Hello"}])
        call_kwargs = client.chat.complete.call_args[1]
        assert call_kwargs["messages"] == [{"role": "user", "content": "Hello"}]

    def test_missing_content_treated_as_empty(self):
        gate = self._gate()
        ctx, client = self._patch_modules()
        with ctx:
            gate.complete([{"role": "user"}])
        call_kwargs = client.chat.complete.call_args[1]
        assert call_kwargs["messages"] == [{"role": "user", "content": ""}]

    def test_returns_text_string(self):
        gate = self._gate()
        ctx, client = self._patch_modules("Bonjour from Mistral!")
        with ctx:
            result = gate.complete([{"role": "user", "content": "Hi"}])
        assert result == "Bonjour from Mistral!"

    def test_returns_string_even_for_non_string_content(self):
        """resp.choices[0].message.content coerced to str()."""
        gate = self._gate()
        sdk_mod, client_instance, response = _mock_mistral_sdk()
        response.choices[0].message.content = 12345
        with patch.dict("sys.modules", {"mistralai.client": sdk_mod}):
            result = gate.complete([{"role": "user", "content": "Hi"}])
        assert result == "12345"

    def test_default_model_used(self):
        gate = self._gate()
        ctx, client = self._patch_modules()
        with ctx:
            gate.complete([{"role": "user", "content": "Hi"}])
        call_kwargs = client.chat.complete.call_args[1]
        assert call_kwargs["model"] == "mistral-large-latest"

    def test_model_override(self):
        gate = self._gate()
        ctx, client = self._patch_modules()
        with ctx:
            gate.complete([{"role": "user", "content": "Hi"}], model="codestral-latest")
        call_kwargs = client.chat.complete.call_args[1]
        assert call_kwargs["model"] == "codestral-latest"

    def test_kwargs_forwarded_to_complete(self):
        gate = self._gate()
        ctx, client = self._patch_modules()
        with ctx:
            gate.complete([{"role": "user", "content": "Hi"}], temperature=0.5)
        call_kwargs = client.chat.complete.call_args[1]
        assert call_kwargs["temperature"] == 0.5

    def test_mistralai_import_error(self):
        gate = self._gate()
        with patch.dict("sys.modules", {"mistralai.client": None}):
            with pytest.raises(ImportError, match="mistralai"):
                gate.complete([{"role": "user", "content": "Hi"}])


# ══════════════════════════════════════════════════════════════════════════════
# 5. complete() — client construction + lifecycle
# ══════════════════════════════════════════════════════════════════════════════

class TestCompleteClientConstruction:
    def _gate(self, **kwargs):
        with patch("mistral_algovoi._build_gate") as mock_build:
            mock_build.return_value = MagicMock()
            from mistral_algovoi import AlgoVoiMistral
            return AlgoVoiMistral(**COMMON, **kwargs)

    def test_mistral_key_passed_to_client(self):
        gate = self._gate()
        sdk_mod, client_instance, _ = _mock_mistral_sdk()
        with patch.dict("sys.modules", {"mistralai.client": sdk_mod}):
            gate.complete([{"role": "user", "content": "Hi"}])
        call_kwargs = sdk_mod.Mistral.call_args[1]
        assert call_kwargs["api_key"] == "MISTRAL-test-key-EXAMPLE"

    def test_client_is_persistent_across_complete_calls(self):
        """Regression — should reuse client across calls (not reconstruct per call)."""
        gate = self._gate()
        sdk_mod, client_instance, _ = _mock_mistral_sdk()
        with patch.dict("sys.modules", {"mistralai.client": sdk_mod}):
            gate.complete([{"role": "user", "content": "Hi"}])
            gate.complete([{"role": "user", "content": "Hi again"}])
        assert sdk_mod.Mistral.call_count == 1
        assert client_instance.chat.complete.call_count == 2

    def test_client_lazy_initialized(self):
        gate = self._gate()
        assert gate._mistral_client is None

    def test_complete_called(self):
        gate = self._gate()
        sdk_mod, client_instance, _ = _mock_mistral_sdk()
        with patch.dict("sys.modules", {"mistralai.client": sdk_mod}):
            gate.complete([{"role": "user", "content": "Hi"}])
        client_instance.chat.complete.assert_called_once()

    def test_close_releases_client(self):
        gate = self._gate()
        sdk_mod, client_instance, _ = _mock_mistral_sdk()
        with patch.dict("sys.modules", {"mistralai.client": sdk_mod}):
            gate.complete([{"role": "user", "content": "Hi"}])
        assert gate._mistral_client is not None
        gate.close()
        # close() calls __exit__ for teardown
        client_instance.__exit__.assert_called_once()
        assert gate._mistral_client is None

    def test_close_idempotent(self):
        gate = self._gate()
        gate.close()
        gate.close()  # must not raise

    def test_close_swallows_client_error(self):
        gate = self._gate()
        sdk_mod, client_instance, _ = _mock_mistral_sdk()
        client_instance.__exit__.side_effect = RuntimeError("close failed")
        with patch.dict("sys.modules", {"mistralai.client": sdk_mod}):
            gate.complete([{"role": "user", "content": "Hi"}])
        gate.close()  # must not raise
        assert gate._mistral_client is None

    def test_context_manager_closes_on_exit(self):
        gate = self._gate()
        sdk_mod, client_instance, _ = _mock_mistral_sdk()
        with patch.dict("sys.modules", {"mistralai.client": sdk_mod}):
            with gate as g:
                g.complete([{"role": "user", "content": "Hi"}])
        client_instance.__exit__.assert_called_once()
        assert gate._mistral_client is None

    def test_context_manager_closes_on_exception(self):
        gate = self._gate()
        sdk_mod, client_instance, _ = _mock_mistral_sdk()
        client_instance.chat.complete.side_effect = RuntimeError("boom")
        with patch.dict("sys.modules", {"mistralai.client": sdk_mod}):
            with pytest.raises(RuntimeError):
                with gate as g:
                    g.complete([{"role": "user", "content": "Hi"}])
        client_instance.__exit__.assert_called_once()

    def test_concurrent_first_calls_construct_client_once(self):
        """Double-checked locking prevents two concurrent first-calls from
        constructing two clients."""
        import threading
        gate = self._gate()
        sdk_mod, client_instance, _ = _mock_mistral_sdk()

        start = threading.Event()
        def worker():
            start.wait()
            with patch.dict("sys.modules", {"mistralai.client": sdk_mod}):
                gate.complete([{"role": "user", "content": "Hi"}])

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        start.set()
        for t in threads:
            t.join()

        assert sdk_mod.Mistral.call_count == 1


# ══════════════════════════════════════════════════════════════════════════════
# 6. MistralAiResult
# ══════════════════════════════════════════════════════════════════════════════

class TestMistralAiResult:
    def test_requires_payment_true(self):
        from mistral_algovoi import MistralAiResult
        r = MistralAiResult(_make_inner(requires_payment=True))
        assert r.requires_payment is True

    def test_requires_payment_false(self):
        from mistral_algovoi import MistralAiResult
        r = MistralAiResult(_make_inner(requires_payment=False))
        assert r.requires_payment is False

    def test_flask_response_delegates(self):
        from mistral_algovoi import MistralAiResult
        r = MistralAiResult(_make_inner(requires_payment=True))
        _, status, _ = r.as_flask_response()
        assert status == 402

    def test_wsgi_response_delegates(self):
        from mistral_algovoi import MistralAiResult
        r = MistralAiResult(_make_inner(requires_payment=True))
        status_str, _, _ = r.as_wsgi_response()
        assert "402" in status_str

    def test_flask_fallback_when_no_method(self):
        from mistral_algovoi import MistralAiResult
        inner = MagicMock(spec=[])
        inner.requires_payment = True
        inner.error = "expired"
        r = MistralAiResult(inner)
        body, status, _ = r.as_flask_response()
        assert status == 402
        assert "expired" in body

    def test_wsgi_fallback_when_no_method(self):
        from mistral_algovoi import MistralAiResult
        inner = MagicMock(spec=[])
        inner.requires_payment = True
        inner.error = ""
        r = MistralAiResult(inner)
        status_str, _, body_bytes = r.as_wsgi_response()
        assert "402" in status_str
        assert b"Payment Required" in body_bytes

    def test_receipt_none_by_default(self):
        from mistral_algovoi import MistralAiResult
        r = MistralAiResult(_make_inner())
        assert r.receipt is None

    def test_mandate_none_by_default(self):
        from mistral_algovoi import MistralAiResult
        r = MistralAiResult(_make_inner())
        assert r.mandate is None


# ══════════════════════════════════════════════════════════════════════════════
# 7. flask_guard()
# ══════════════════════════════════════════════════════════════════════════════

class TestFlaskGuard:
    def _gate(self):
        with patch("mistral_algovoi._build_gate") as mock_build:
            mock_build.return_value = MagicMock()
            from mistral_algovoi import AlgoVoiMistral
            gate = AlgoVoiMistral(**COMMON)
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
        sdk_mod, client_instance, _ = _mock_mistral_sdk("Bonjour!")
        flask = MagicMock()
        flask.request.get_json.return_value = {"messages": [{"role": "user", "content": "Hello"}]}
        flask.request.headers = {"Authorization": "Payment abc"}
        with patch.dict("sys.modules", {"flask": flask, "mistralai.client": sdk_mod}):
            gate.flask_guard()
        flask.jsonify.assert_called_once_with({"content": "Bonjour!"})

    def test_guard_uses_custom_messages_key(self):
        gate = self._gate()
        gate._gate.check.return_value = _make_inner(requires_payment=False)
        sdk_mod, client_instance, _ = _mock_mistral_sdk("Bonjour!")
        flask = MagicMock()
        flask.request.get_json.return_value = {"msgs": [{"role": "user", "content": "Hello"}]}
        flask.request.headers = {}
        with patch.dict("sys.modules", {"flask": flask, "mistralai.client": sdk_mod}):
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
            from mistral_algovoi import _build_gate
            _build_gate("x402", "algv_test", "tenant", "ADDR",
                        "algorand-mainnet", 10000, "ai-chat")
        x402_mock._X402Gate.assert_called_once()

    def test_mpp_loads_mpp_gate(self):
        mpp_mock = MagicMock()
        mpp_mock.MppGate.return_value = MagicMock()
        with patch.dict("sys.modules", {"mpp": mpp_mock}):
            from mistral_algovoi import _build_gate
            _build_gate("mpp", "algv_test", "tenant", "ADDR",
                        "algorand-mainnet", 10000, "ai-chat")
        mpp_mock.MppGate.assert_called_once()

    def test_ap2_loads_ap2_gate(self):
        ap2_mock = MagicMock()
        ap2_mock.Ap2Gate.return_value = MagicMock()
        with patch.dict("sys.modules", {"ap2": ap2_mock}):
            from mistral_algovoi import _build_gate
            _build_gate("ap2", "algv_test", "tenant", "ADDR",
                        "algorand-mainnet", 10000, "ai-chat")
        ap2_mock.Ap2Gate.assert_called_once()

    def test_mpp_uses_snake_case_network(self):
        mpp_mock = MagicMock()
        mpp_mock.MppGate.return_value = MagicMock()
        with patch.dict("sys.modules", {"mpp": mpp_mock}):
            from mistral_algovoi import _build_gate
            _build_gate("mpp", "algv_test", "tenant", "ADDR",
                        "voi-mainnet", 10000, "ai-chat")
        call_kwargs = mpp_mock.MppGate.call_args[1]
        assert "voi_mainnet" in call_kwargs["networks"]

    def test_all_four_networks_valid_for_mpp(self):
        for net in ["algorand-mainnet", "voi-mainnet", "hedera-mainnet", "stellar-mainnet"]:
            mpp_mock = MagicMock()
            mpp_mock.MppGate.return_value = MagicMock()
            with patch.dict("sys.modules", {"mpp": mpp_mock}):
                from mistral_algovoi import _build_gate
                _build_gate("mpp", "k", "t", "A", net, 10000, "r")

    def test_ap2_uses_kebab_case_network(self):
        ap2_mock = MagicMock()
        ap2_mock.Ap2Gate.return_value = MagicMock()
        with patch.dict("sys.modules", {"ap2": ap2_mock}):
            from mistral_algovoi import _build_gate
            _build_gate("ap2", "algv_test", "tenant", "ADDR",
                        "stellar-mainnet", 10000, "ai-chat")
        call_kwargs = ap2_mock.Ap2Gate.call_args[1]
        assert "stellar-mainnet" in call_kwargs["networks"]


# ══════════════════════════════════════════════════════════════════════════════
# 9. Module constants
# ══════════════════════════════════════════════════════════════════════════════

class TestModuleConstants:
    def test_networks_constant(self):
        from mistral_algovoi import NETWORKS
        assert set(NETWORKS) == {"algorand-mainnet", "voi-mainnet", "hedera-mainnet", "stellar-mainnet"}

    def test_protocols_constant(self):
        from mistral_algovoi import PROTOCOLS
        assert set(PROTOCOLS) == {"x402", "mpp", "ap2"}

    def test_snake_map_covers_all_networks(self):
        from mistral_algovoi import _SNAKE, NETWORKS
        for net in NETWORKS:
            assert net in _SNAKE
            assert "-" not in _SNAKE[net]
            assert "_" in _SNAKE[net]

    def test_version(self):
        from mistral_algovoi import __version__
        assert __version__ == "1.0.0"

    def test_api_base_is_production(self):
        from mistral_algovoi import _API_BASE
        assert _API_BASE.startswith("https://")
        assert "ilovechicken.co.uk" in _API_BASE

    def test_import_path_matches_public_api(self):
        """Regression — the adapter must use the documented public import
        `from mistralai.client import Mistral` (per mistralai>=2.0.0 README).
        Earlier draft used the Speakeasy-internal `mistralai.client.sdk`
        path which is not guaranteed stable across SDK regenerations."""
        import inspect
        import mistral_algovoi
        src = inspect.getsource(mistral_algovoi)
        assert "from mistralai.client import Mistral" in src
        # The fragile internal path must NOT be used
        assert "from mistralai.client.sdk import" not in src
