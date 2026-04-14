"""
AlgoVoi Bedrock Adapter — Unit Tests
=====================================
All tests are fully mocked — no live AWS or AlgoVoi calls.

Run:
    python -m pytest test_bedrock_algovoi.py -v
    python -m pytest test_bedrock_algovoi.py -v --tb=short
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
    aws_access_key_id     = "TEST-ACCESS-KEY-EXAMPLE",
    aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    algovoi_key           = "algv_test",
    tenant_id             = "test-tenant",
    payout_address        = "ZVLRVYQSLJNVFMOIOKT35XH5SNQG45IVFMLLRFLHDQJQA5TO5H3SO4TVDQ",
    amount_microunits     = 10000,
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

def _make_bedrock_response(text: str = "Hello from Bedrock!") -> dict:
    return {
        "output": {
            "message": {
                "role":    "assistant",
                "content": [{"text": text}],
            }
        },
        "stopReason": "end_turn",
        "usage": {"inputTokens": 10, "outputTokens": 5},
    }


# ── 1. Construction ───────────────────────────────────────────────────────────

class TestConstruction:
    def test_x402_construction(self):
        with patch("bedrock_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from bedrock_algovoi import AlgoVoiBedrock
            gate = AlgoVoiBedrock(**COMMON, protocol="x402")
            mock_gate.assert_called_once()
            assert mock_gate.call_args[0][0] == "x402"

    def test_mpp_construction(self):
        with patch("bedrock_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from bedrock_algovoi import AlgoVoiBedrock
            gate = AlgoVoiBedrock(**COMMON, protocol="mpp")
            assert mock_gate.call_args[0][0] == "mpp"

    def test_ap2_construction(self):
        with patch("bedrock_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from bedrock_algovoi import AlgoVoiBedrock
            gate = AlgoVoiBedrock(**COMMON, protocol="ap2")
            assert mock_gate.call_args[0][0] == "ap2"

    def test_default_model(self):
        with patch("bedrock_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from bedrock_algovoi import AlgoVoiBedrock
            gate = AlgoVoiBedrock(**COMMON)
            assert gate._model == "amazon.nova-pro-v1:0"

    def test_custom_model(self):
        with patch("bedrock_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from bedrock_algovoi import AlgoVoiBedrock
            gate = AlgoVoiBedrock(**COMMON, model="anthropic.claude-3-5-sonnet-20241022-v2:0")
            assert gate._model == "anthropic.claude-3-5-sonnet-20241022-v2:0"

    def test_default_region(self):
        with patch("bedrock_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from bedrock_algovoi import AlgoVoiBedrock
            gate = AlgoVoiBedrock(**COMMON)
            assert gate._aws_region == "us-east-1"

    def test_custom_region(self):
        with patch("bedrock_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from bedrock_algovoi import AlgoVoiBedrock
            gate = AlgoVoiBedrock(**COMMON, aws_region="eu-west-1")
            assert gate._aws_region == "eu-west-1"

    def test_invalid_network(self):
        from bedrock_algovoi import AlgoVoiBedrock
        with pytest.raises(ValueError, match="network must be one of"):
            AlgoVoiBedrock(**COMMON, network="invalid-net")

    def test_invalid_protocol(self):
        from bedrock_algovoi import AlgoVoiBedrock
        with pytest.raises(ValueError, match="protocol must be one of"):
            AlgoVoiBedrock(**COMMON, protocol="grpc")

    def test_all_networks_accepted(self):
        for net in ["algorand-mainnet", "voi-mainnet", "hedera-mainnet", "stellar-mainnet"]:
            with patch("bedrock_algovoi._build_gate") as mock_gate:
                mock_gate.return_value = MagicMock()
                from bedrock_algovoi import AlgoVoiBedrock
                AlgoVoiBedrock(**COMMON, network=net)  # should not raise

    def test_no_aws_keys_uses_env(self):
        """Keys can be omitted — boto3 reads from env vars."""
        with patch("bedrock_algovoi._build_gate") as mock_gate:
            mock_gate.return_value = MagicMock()
            from bedrock_algovoi import AlgoVoiBedrock
            gate = AlgoVoiBedrock(
                algovoi_key="algv_test", tenant_id="t", payout_address="ADDR",
                protocol="mpp",
            )
            assert gate._aws_key is None
            assert gate._aws_secret is None


# ── 2. check() — payment required ─────────────────────────────────────────────

class TestCheckPaymentRequired:
    def _gate(self, protocol="mpp"):
        with patch("bedrock_algovoi._build_gate") as mock_build:
            mock_build.return_value = MagicMock()
            from bedrock_algovoi import AlgoVoiBedrock
            gate = AlgoVoiBedrock(**COMMON, protocol=protocol)
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

    def test_mpp_calls_check_with_headers_only(self):
        gate = self._gate("mpp")
        gate._gate.check.side_effect = [TypeError, _make_inner()]
        gate.check({"Authorization": "Payment abc"}, {"messages": []})
        # Second call (after TypeError) should be headers-only
        assert gate._gate.check.call_count == 2

    def test_ap2_calls_check_with_body(self):
        gate = self._gate("ap2")
        gate._gate.check.return_value = _make_inner()
        gate.check({"X-AP2": "mandate"}, {"messages": []})
        gate._gate.check.assert_called_once()

    def test_error_message_exposed(self):
        gate = self._gate()
        gate._gate.check.return_value = _make_inner(requires_payment=True, error="TX expired")
        result = gate.check({})
        assert result.error == "TX expired"


# ── 3. check() — payment accepted ─────────────────────────────────────────────

class TestCheckPaymentAccepted:
    def _gate(self):
        with patch("bedrock_algovoi._build_gate") as mock_build:
            mock_build.return_value = MagicMock()
            from bedrock_algovoi import AlgoVoiBedrock
            gate = AlgoVoiBedrock(**COMMON)
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


# ── 4. complete() — message conversion ────────────────────────────────────────

class TestCompleteMessageConversion:
    def _gate(self):
        with patch("bedrock_algovoi._build_gate") as mock_build:
            mock_build.return_value = MagicMock()
            from bedrock_algovoi import AlgoVoiBedrock
            gate = AlgoVoiBedrock(**COMMON)
            return gate

    def _mock_boto3(self, response_text="Hello!"):
        mock_client = MagicMock()
        mock_client.converse.return_value = _make_bedrock_response(response_text)
        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_client
        return mock_boto3, mock_client

    def test_system_extracted_to_system_param(self):
        gate = self._gate()
        mock_boto3, mock_client = self._mock_boto3()
        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            gate.complete(MESSAGES)
        call_kwargs = mock_client.converse.call_args[1]
        assert "system" in call_kwargs
        assert call_kwargs["system"] == [{"text": "You are a helpful assistant."}]

    def test_system_not_in_messages(self):
        gate = self._gate()
        mock_boto3, mock_client = self._mock_boto3()
        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            gate.complete(MESSAGES)
        call_kwargs = mock_client.converse.call_args[1]
        for msg in call_kwargs["messages"]:
            assert msg["role"] != "system"

    def test_no_system_omits_system_param(self):
        gate = self._gate()
        mock_boto3, mock_client = self._mock_boto3()
        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            gate.complete(MESSAGES_NO_SYSTEM)
        call_kwargs = mock_client.converse.call_args[1]
        assert "system" not in call_kwargs

    def test_messages_use_bedrock_format(self):
        gate = self._gate()
        mock_boto3, mock_client = self._mock_boto3()
        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            gate.complete([{"role": "user", "content": "Hello"}])
        call_kwargs = mock_client.converse.call_args[1]
        assert call_kwargs["messages"] == [
            {"role": "user", "content": [{"text": "Hello"}]}
        ]

    def test_assistant_role_preserved(self):
        gate = self._gate()
        mock_boto3, mock_client = self._mock_boto3()
        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            gate.complete(MESSAGES_NO_SYSTEM)
        call_kwargs = mock_client.converse.call_args[1]
        roles = [m["role"] for m in call_kwargs["messages"]]
        assert "assistant" in roles

    def test_returns_text_string(self):
        gate = self._gate()
        mock_boto3, mock_client = self._mock_boto3("Hello from Nova!")
        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            result = gate.complete([{"role": "user", "content": "Hi"}])
        assert result == "Hello from Nova!"

    def test_default_model_used(self):
        gate = self._gate()
        mock_boto3, mock_client = self._mock_boto3()
        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            gate.complete([{"role": "user", "content": "Hi"}])
        call_kwargs = mock_client.converse.call_args[1]
        assert call_kwargs["modelId"] == "amazon.nova-pro-v1:0"

    def test_model_override(self):
        gate = self._gate()
        mock_boto3, mock_client = self._mock_boto3()
        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            gate.complete([{"role": "user", "content": "Hi"}],
                          model="anthropic.claude-3-5-sonnet-20241022-v2:0")
        call_kwargs = mock_client.converse.call_args[1]
        assert call_kwargs["modelId"] == "anthropic.claude-3-5-sonnet-20241022-v2:0"

    def test_max_tokens_default(self):
        gate = self._gate()
        mock_boto3, mock_client = self._mock_boto3()
        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            gate.complete([{"role": "user", "content": "Hi"}])
        call_kwargs = mock_client.converse.call_args[1]
        assert call_kwargs["inferenceConfig"]["maxTokens"] == 1024

    def test_max_tokens_override(self):
        gate = self._gate()
        mock_boto3, mock_client = self._mock_boto3()
        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            gate.complete([{"role": "user", "content": "Hi"}], max_tokens=512)
        call_kwargs = mock_client.converse.call_args[1]
        assert call_kwargs["inferenceConfig"]["maxTokens"] == 512

    def test_temperature_kwarg_in_inference_config(self):
        gate = self._gate()
        mock_boto3, mock_client = self._mock_boto3()
        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            gate.complete([{"role": "user", "content": "Hi"}], temperature=0.5)
        call_kwargs = mock_client.converse.call_args[1]
        assert call_kwargs["inferenceConfig"]["temperature"] == 0.5

    def test_boto3_import_error(self):
        gate = self._gate()
        with patch.dict("sys.modules", {"boto3": None}):
            with pytest.raises(ImportError, match="boto3"):
                gate.complete([{"role": "user", "content": "Hi"}])


# ── 5. complete() — AWS client construction ───────────────────────────────────

class TestCompleteClientConstruction:
    def _gate(self, **kwargs):
        with patch("bedrock_algovoi._build_gate") as mock_build:
            mock_build.return_value = MagicMock()
            from bedrock_algovoi import AlgoVoiBedrock
            return AlgoVoiBedrock(**COMMON, **kwargs)

    def _mock_boto3(self):
        mock_client = MagicMock()
        mock_client.converse.return_value = _make_bedrock_response()
        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_client
        return mock_boto3

    def test_explicit_keys_passed_to_client(self):
        gate = self._gate()
        mock_boto3 = self._mock_boto3()
        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            gate.complete([{"role": "user", "content": "Hi"}])
        call_kwargs = mock_boto3.client.call_args[1]
        assert call_kwargs["aws_access_key_id"]     == "TEST-ACCESS-KEY-EXAMPLE"
        assert call_kwargs["aws_secret_access_key"] == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        assert call_kwargs["region_name"]           == "us-east-1"

    def test_no_keys_omits_key_params(self):
        with patch("bedrock_algovoi._build_gate") as mock_build:
            mock_build.return_value = MagicMock()
            from bedrock_algovoi import AlgoVoiBedrock
            gate = AlgoVoiBedrock(
                algovoi_key="algv_test", tenant_id="t", payout_address="ADDR"
            )
        mock_boto3 = self._mock_boto3()
        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            gate.complete([{"role": "user", "content": "Hi"}])
        call_kwargs = mock_boto3.client.call_args[1]
        assert "aws_access_key_id"     not in call_kwargs
        assert "aws_secret_access_key" not in call_kwargs

    def test_custom_region_used(self):
        gate = self._gate(aws_region="ap-southeast-1")
        mock_boto3 = self._mock_boto3()
        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            gate.complete([{"role": "user", "content": "Hi"}])
        call_kwargs = mock_boto3.client.call_args[1]
        assert call_kwargs["region_name"] == "ap-southeast-1"

    def test_service_name_is_bedrock_runtime(self):
        gate = self._gate()
        mock_boto3 = self._mock_boto3()
        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            gate.complete([{"role": "user", "content": "Hi"}])
        assert mock_boto3.client.call_args[0][0] == "bedrock-runtime"


# ── 6. BedrockAiResult ────────────────────────────────────────────────────────

class TestBedrockAiResult:
    def test_requires_payment_true(self):
        from bedrock_algovoi import BedrockAiResult
        inner = _make_inner(requires_payment=True)
        r = BedrockAiResult(inner)
        assert r.requires_payment is True

    def test_requires_payment_false(self):
        from bedrock_algovoi import BedrockAiResult
        inner = _make_inner(requires_payment=False)
        r = BedrockAiResult(inner)
        assert r.requires_payment is False

    def test_flask_response_delegates(self):
        from bedrock_algovoi import BedrockAiResult
        inner = _make_inner(requires_payment=True)
        r = BedrockAiResult(inner)
        body, status, headers = r.as_flask_response()
        assert status == 402

    def test_wsgi_response_delegates(self):
        from bedrock_algovoi import BedrockAiResult
        inner = _make_inner(requires_payment=True)
        r = BedrockAiResult(inner)
        status_str, header_list, body_bytes = r.as_wsgi_response()
        assert "402" in status_str

    def test_flask_fallback_when_no_method(self):
        from bedrock_algovoi import BedrockAiResult
        inner = MagicMock(spec=[])
        inner.requires_payment = True
        inner.error = "expired"
        r = BedrockAiResult(inner)
        body, status, headers = r.as_flask_response()
        assert status == 402
        assert "expired" in body

    def test_receipt_none_by_default(self):
        from bedrock_algovoi import BedrockAiResult
        inner = _make_inner()
        r = BedrockAiResult(inner)
        assert r.receipt is None

    def test_mandate_none_by_default(self):
        from bedrock_algovoi import BedrockAiResult
        inner = _make_inner()
        r = BedrockAiResult(inner)
        assert r.mandate is None


# ── 7. flask_guard() ──────────────────────────────────────────────────────────

class TestFlaskGuard:
    def _gate(self):
        with patch("bedrock_algovoi._build_gate") as mock_build:
            mock_build.return_value = MagicMock()
            from bedrock_algovoi import AlgoVoiBedrock
            gate = AlgoVoiBedrock(**COMMON)
            gate._gate = MagicMock()
            return gate

    def test_guard_returns_402_without_payment(self):
        gate = self._gate()
        gate._gate.check.return_value = _make_inner(requires_payment=True)
        flask = MagicMock()
        flask.request.get_json.return_value = {}
        flask.request.headers = {}
        flask.Response.return_value = MagicMock(status_code=402)
        with patch.dict("sys.modules", {"flask": flask}):
            resp = gate.flask_guard()
        flask.Response.assert_called_once()

    def test_guard_calls_complete_on_success(self):
        gate = self._gate()
        gate._gate.check.return_value = _make_inner(requires_payment=False)
        mock_boto3 = MagicMock()
        mock_client = MagicMock()
        mock_client.converse.return_value = _make_bedrock_response("Hi!")
        mock_boto3.client.return_value = mock_client
        flask = MagicMock()
        flask.request.get_json.return_value = {"messages": [{"role": "user", "content": "Hello"}]}
        flask.request.headers = {"Authorization": "Payment abc"}
        with patch.dict("sys.modules", {"flask": flask, "boto3": mock_boto3}):
            gate.flask_guard()
        flask.jsonify.assert_called_once_with({"content": "Hi!"})

    def test_guard_uses_custom_messages_key(self):
        gate = self._gate()
        gate._gate.check.return_value = _make_inner(requires_payment=False)
        mock_boto3 = MagicMock()
        mock_client = MagicMock()
        mock_client.converse.return_value = _make_bedrock_response("Hi!")
        mock_boto3.client.return_value = mock_client
        flask = MagicMock()
        flask.request.get_json.return_value = {"msgs": [{"role": "user", "content": "Hello"}]}
        flask.request.headers = {}
        with patch.dict("sys.modules", {"flask": flask, "boto3": mock_boto3}):
            gate.flask_guard(messages_key="msgs")
        flask.jsonify.assert_called_once()


# ── 8. Gate factory — path injection ─────────────────────────────────────────

class TestBuildGate:
    def test_x402_loads_from_openai_adapter(self):
        x402_mock = MagicMock()
        x402_mock._X402Gate.return_value = MagicMock()
        with patch.dict("sys.modules", {"openai_algovoi": x402_mock}):
            from bedrock_algovoi import _build_gate
            _build_gate("x402", "algv_test", "tenant", "ADDR",
                        "algorand-mainnet", 10000, "ai-chat")
        x402_mock._X402Gate.assert_called_once()

    def test_mpp_loads_mpp_gate(self):
        mpp_mock = MagicMock()
        mpp_mock.MppGate.return_value = MagicMock()
        with patch.dict("sys.modules", {"mpp": mpp_mock}):
            from bedrock_algovoi import _build_gate
            _build_gate("mpp", "algv_test", "tenant", "ADDR",
                        "algorand-mainnet", 10000, "ai-chat")
        mpp_mock.MppGate.assert_called_once()

    def test_ap2_loads_ap2_gate(self):
        ap2_mock = MagicMock()
        ap2_mock.Ap2Gate.return_value = MagicMock()
        with patch.dict("sys.modules", {"ap2": ap2_mock}):
            from bedrock_algovoi import _build_gate
            _build_gate("ap2", "algv_test", "tenant", "ADDR",
                        "algorand-mainnet", 10000, "ai-chat")
        ap2_mock.Ap2Gate.assert_called_once()

    def test_mpp_uses_snake_case_network(self):
        mpp_mock = MagicMock()
        mpp_mock.MppGate.return_value = MagicMock()
        with patch.dict("sys.modules", {"mpp": mpp_mock}):
            from bedrock_algovoi import _build_gate
            _build_gate("mpp", "algv_test", "tenant", "ADDR",
                        "voi-mainnet", 10000, "ai-chat")
        call_kwargs = mpp_mock.MppGate.call_args[1]
        assert "voi_mainnet" in call_kwargs["networks"]

    def test_all_four_networks_valid_for_mpp(self):
        for net in ["algorand-mainnet", "voi-mainnet", "hedera-mainnet", "stellar-mainnet"]:
            mpp_mock = MagicMock()
            mpp_mock.MppGate.return_value = MagicMock()
            with patch.dict("sys.modules", {"mpp": mpp_mock}):
                from bedrock_algovoi import _build_gate
                _build_gate("mpp", "k", "t", "A", net, 10000, "r")


# ── 9. Model constants ────────────────────────────────────────────────────────

class TestModelConstants:
    def test_models_list_contains_nova_pro(self):
        from bedrock_algovoi import MODELS
        assert "amazon.nova-pro-v1:0" in MODELS

    def test_models_list_contains_claude(self):
        from bedrock_algovoi import MODELS
        assert any("claude" in m for m in MODELS)

    def test_models_list_contains_llama(self):
        from bedrock_algovoi import MODELS
        assert any("llama" in m for m in MODELS)

    def test_networks_constant(self):
        from bedrock_algovoi import NETWORKS
        assert "algorand-mainnet" in NETWORKS
        assert len(NETWORKS) == 4

    def test_protocols_constant(self):
        from bedrock_algovoi import PROTOCOLS
        assert set(PROTOCOLS) == {"x402", "mpp", "ap2"}

    def test_version(self):
        from bedrock_algovoi import __version__
        assert __version__ == "1.0.0"
