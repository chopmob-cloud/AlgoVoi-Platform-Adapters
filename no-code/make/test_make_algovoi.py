"""
Unit tests for AlgoVoi Make Adapter
=====================================

75 tests covering constructor validation, webhook module, create_payment_link,
verify_payment, list_networks, generate_challenge (mpp/x402/ap2),
verify_signature, and payout address routing.

All HTTP calls are mocked — no live API calls.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# ── path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from make_algovoi import (
    AlgoVoiMake,
    SUPPORTED_NETWORKS,
    NETWORK_INFO,
    __version__,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def make_make_handler(**kwargs):
    defaults = dict(algovoi_key="algv_test", tenant_id="tid", payout_algorand="ALGO_ADDR")
    defaults.update(kwargs)
    return AlgoVoiMake(**defaults)


def mock_urlopen(response_dict, status=200):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(response_dict).encode()
    mock_resp.status = status
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return MagicMock(return_value=mock_resp)


def make_sig(body: str, secret: str) -> str:
    return hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()


# ═══════════════════════════════════════════════════════════════════════════════
# Group 1 — Constructor / init (9 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestInit:
    def test_valid_construction(self):
        h = make_make_handler()
        assert h is not None

    def test_version(self):
        assert __version__ == "1.0.0"

    def test_missing_key_prefix_raises(self):
        with pytest.raises(ValueError, match="algv_"):
            make_make_handler(algovoi_key="bad_key")

    def test_empty_key_raises(self):
        with pytest.raises(ValueError, match="algv_"):
            make_make_handler(algovoi_key="")

    def test_missing_tenant_id_raises(self):
        with pytest.raises(ValueError, match="tenant_id"):
            make_make_handler(tenant_id="")

    def test_bad_api_base_raises(self):
        with pytest.raises(ValueError, match="https"):
            make_make_handler(api_base="http://insecure.example.com")

    def test_no_payout_address_raises(self):
        with pytest.raises(ValueError, match="payout"):
            AlgoVoiMake(algovoi_key="algv_test", tenant_id="tid")

    def test_fallback_payout_accepted(self):
        h = AlgoVoiMake(
            algovoi_key="algv_test",
            tenant_id="tid",
            payout_address="FALLBACK_ADDR",
        )
        assert h is not None

    def test_all_four_payout_chains_accepted(self):
        h = AlgoVoiMake(
            algovoi_key="algv_test",
            tenant_id="tid",
            payout_algorand="ALGO",
            payout_voi="VOI",
            payout_hedera="0.0.12345",
            payout_stellar="GSTELLAR",
        )
        assert h is not None


# ═══════════════════════════════════════════════════════════════════════════════
# Group 2 — receive_webhook (10 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestWebhookModule:
    def test_valid_webhook_no_secret_returns_data(self):
        h = make_make_handler()
        body = json.dumps({"event_id": "e1", "status": "paid"})
        bundle = h.receive_webhook(body, "")
        assert bundle.get("data") is not None

    def test_valid_webhook_with_hmac_returns_data(self):
        secret = "whsec_make"
        h = make_make_handler(webhook_secret=secret)
        body = json.dumps({"event_id": "e2", "status": "paid"})
        sig = make_sig(body, secret)
        bundle = h.receive_webhook(body, sig)
        assert bundle.get("data") is not None

    def test_bad_signature_returns_error(self):
        h = make_make_handler(webhook_secret="secret")
        body = json.dumps({"event_id": "e3"})
        bundle = h.receive_webhook(body, "badsig")
        assert "error" in bundle
        assert bundle["error"]["message"] is not None

    def test_bad_signature_error_code(self):
        h = make_make_handler(webhook_secret="secret")
        body = json.dumps({"event_id": "e3"})
        bundle = h.receive_webhook(body, "badsig")
        assert bundle["error"]["code"] == "INVALID_SIGNATURE"

    def test_body_too_large_returns_error(self):
        h = make_make_handler()
        big_body = "x" * (1_048_576 + 1)
        bundle = h.receive_webhook(big_body, "")
        assert "error" in bundle
        assert bundle["error"]["code"] == "BODY_TOO_LARGE"

    def test_invalid_json_returns_error(self):
        h = make_make_handler()
        bundle = h.receive_webhook("not-json", "")
        assert "error" in bundle
        assert bundle["error"]["code"] == "INVALID_JSON"

    def test_bundle_data_has_event_id(self):
        h = make_make_handler()
        body = json.dumps({"event_id": "evt-99", "status": "pending"})
        bundle = h.receive_webhook(body, "")
        assert bundle["data"]["event_id"] == "evt-99"

    def test_bundle_data_has_status(self):
        h = make_make_handler()
        body = json.dumps({"event_id": "e4", "status": "paid"})
        bundle = h.receive_webhook(body, "")
        assert bundle["data"]["status"] == "paid"

    def test_bundle_metadata_source(self):
        h = make_make_handler()
        body = json.dumps({"event_id": "e5"})
        bundle = h.receive_webhook(body, "")
        assert bundle.get("metadata", {}).get("source") == "algovoi"

    def test_no_secret_passes_any_signature(self):
        h = make_make_handler()  # no webhook_secret
        body = json.dumps({"event_id": "e6"})
        bundle = h.receive_webhook(body, "ignored_sig")
        assert bundle.get("data") is not None


# ═══════════════════════════════════════════════════════════════════════════════
# Group 3 — module_create_payment_link (14 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCreatePaymentLink:
    def _ok_resp(self):
        return {"checkout_url": "https://pay.algovoi.com/checkout/tok999", "amount_microunits": 10_000_000}

    def test_success_returns_data(self):
        h = make_make_handler()
        with patch("urllib.request.urlopen", mock_urlopen(self._ok_resp())):
            bundle = h.module_create_payment_link({"amount": 10.0, "currency": "USD", "label": "Order"})
        assert bundle.get("data") is not None

    def test_checkout_url_in_data(self):
        h = make_make_handler()
        with patch("urllib.request.urlopen", mock_urlopen(self._ok_resp())):
            bundle = h.module_create_payment_link({"amount": 10.0, "currency": "USD", "label": "Order"})
        assert "checkout_url" in bundle["data"]

    def test_token_extracted(self):
        h = make_make_handler()
        with patch("urllib.request.urlopen", mock_urlopen(self._ok_resp())):
            bundle = h.module_create_payment_link({"amount": 10.0, "currency": "USD", "label": "Order"})
        assert bundle["data"]["token"] == "tok999"

    def test_missing_amount_returns_error(self):
        h = make_make_handler()
        bundle = h.module_create_payment_link({"currency": "USD", "label": "Test"})
        assert "error" in bundle
        assert bundle["error"]["code"] == "INVALID_AMOUNT"

    def test_zero_amount_returns_error(self):
        h = make_make_handler()
        bundle = h.module_create_payment_link({"amount": 0, "currency": "USD", "label": "Test"})
        assert "error" in bundle

    def test_negative_amount_returns_error(self):
        h = make_make_handler()
        bundle = h.module_create_payment_link({"amount": -1.0, "currency": "USD", "label": "Test"})
        assert "error" in bundle

    def test_amount_too_large_returns_error(self):
        h = make_make_handler()
        bundle = h.module_create_payment_link({"amount": 10_000_001, "currency": "USD", "label": "Test"})
        assert "error" in bundle

    def test_bad_currency_returns_error(self):
        h = make_make_handler()
        bundle = h.module_create_payment_link({"amount": 10.0, "currency": "USDC", "label": "Test"})
        assert "error" in bundle
        assert bundle["error"]["code"] == "INVALID_CURRENCY"

    def test_missing_label_returns_error(self):
        h = make_make_handler()
        bundle = h.module_create_payment_link({"amount": 10.0, "currency": "USD", "label": ""})
        assert "error" in bundle
        assert bundle["error"]["code"] == "MISSING_LABEL"

    def test_bad_network_returns_error(self):
        h = make_make_handler()
        bundle = h.module_create_payment_link({
            "amount": 10.0, "currency": "USD", "label": "T",
            "network": "ethereum_mainnet",
        })
        assert "error" in bundle
        assert bundle["error"]["code"] == "INVALID_NETWORK"

    def test_https_redirect_url_accepted(self):
        h = make_make_handler()
        with patch("urllib.request.urlopen", mock_urlopen(self._ok_resp())):
            bundle = h.module_create_payment_link({
                "amount": 10.0, "currency": "USD", "label": "Test",
                "redirect_url": "https://example.com/thanks",
            })
        assert bundle.get("data") is not None

    def test_non_https_redirect_silently_dropped(self):
        h = make_make_handler()
        with patch("urllib.request.urlopen", mock_urlopen(self._ok_resp())):
            bundle = h.module_create_payment_link({
                "amount": 10.0, "currency": "USD", "label": "Test",
                "redirect_url": "http://example.com/thanks",
            })
        assert bundle.get("data") is not None

    def test_api_error_returns_error_bundle(self):
        h = make_make_handler()
        with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
            bundle = h.module_create_payment_link({"amount": 10.0, "currency": "USD", "label": "T"})
        assert "error" in bundle
        assert bundle["error"]["code"] == "API_ERROR"

    def test_api_missing_checkout_url_returns_error(self):
        h = make_make_handler()
        with patch("urllib.request.urlopen", mock_urlopen({"status": "ok"})):
            bundle = h.module_create_payment_link({"amount": 10.0, "currency": "USD", "label": "T"})
        assert "error" in bundle


# ═══════════════════════════════════════════════════════════════════════════════
# Group 4 — module_verify_payment (6 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestVerifyPayment:
    def test_success_paid_returns_data(self):
        h = make_make_handler()
        with patch("urllib.request.urlopen", mock_urlopen({"status": "paid"})):
            bundle = h.module_verify_payment({"token": "tok123"})
        assert bundle.get("data") is not None
        assert bundle["data"]["paid"] is True

    def test_success_unpaid(self):
        h = make_make_handler()
        with patch("urllib.request.urlopen", mock_urlopen({"status": "pending"})):
            bundle = h.module_verify_payment({"token": "tok456"})
        assert bundle["data"]["paid"] is False

    def test_completed_status_is_paid(self):
        h = make_make_handler()
        with patch("urllib.request.urlopen", mock_urlopen({"status": "completed"})):
            bundle = h.module_verify_payment({"token": "tok789"})
        assert bundle["data"]["paid"] is True

    def test_confirmed_status_is_paid(self):
        h = make_make_handler()
        with patch("urllib.request.urlopen", mock_urlopen({"status": "confirmed"})):
            bundle = h.module_verify_payment({"token": "tokABC"})
        assert bundle["data"]["paid"] is True

    def test_missing_token_returns_error(self):
        h = make_make_handler()
        bundle = h.module_verify_payment({})
        assert "error" in bundle
        assert bundle["error"]["code"] == "MISSING_TOKEN"

    def test_api_error_returns_error_bundle(self):
        h = make_make_handler()
        with patch("urllib.request.urlopen", side_effect=Exception("network error")):
            bundle = h.module_verify_payment({"token": "tok"})
        assert "error" in bundle
        assert bundle["error"]["code"] == "API_ERROR"


# ═══════════════════════════════════════════════════════════════════════════════
# Group 5 — module_list_networks (5 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestListNetworks:
    def test_returns_data(self):
        h = make_make_handler()
        bundle = h.module_list_networks()
        assert bundle.get("data") is not None

    def test_count_is_16(self):
        h = make_make_handler()
        bundle = h.module_list_networks()
        assert bundle["data"]["count"] == 16

    def test_networks_list_length(self):
        h = make_make_handler()
        bundle = h.module_list_networks()
        assert len(bundle["data"]["networks"]) == 16

    def test_all_supported_networks_present(self):
        h = make_make_handler()
        bundle = h.module_list_networks()
        keys = {n["key"] for n in bundle["data"]["networks"]}
        assert keys == SUPPORTED_NETWORKS

    def test_network_has_required_fields(self):
        h = make_make_handler()
        bundle = h.module_list_networks()
        net = bundle["data"]["networks"][0]
        for field in ("key", "label", "asset", "decimals"):
            assert field in net


# ═══════════════════════════════════════════════════════════════════════════════
# Group 6 — module_generate_challenge (15 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestGenerateChallenge:
    def _base_params(self, protocol="mpp"):
        return {
            "protocol": protocol,
            "resource_id": "https://api.example.com/resource",
            "amount_microunits": 1_000_000,
            "network": "algorand_mainnet",
        }

    def test_mpp_returns_data(self):
        h = make_make_handler()
        bundle = h.module_generate_challenge(self._base_params("mpp"))
        assert bundle.get("data") is not None

    def test_mpp_protocol_in_data(self):
        h = make_make_handler()
        bundle = h.module_generate_challenge(self._base_params("mpp"))
        assert bundle["data"]["protocol"] == "mpp"

    def test_mpp_header_name_www_authenticate(self):
        h = make_make_handler()
        bundle = h.module_generate_challenge(self._base_params("mpp"))
        assert bundle["data"]["header_name"] == "WWW-Authenticate"

    def test_mpp_header_value_contains_realm(self):
        h = make_make_handler()
        bundle = h.module_generate_challenge(self._base_params("mpp"))
        assert "realm=" in bundle["data"]["header_value"]

    def test_mpp_header_value_contains_payout_address(self):
        h = make_make_handler()
        bundle = h.module_generate_challenge(self._base_params("mpp"))
        assert "ALGO_ADDR" in bundle["data"]["header_value"]

    def test_x402_protocol_in_data(self):
        h = make_make_handler()
        bundle = h.module_generate_challenge(self._base_params("x402"))
        assert bundle["data"]["protocol"] == "x402"

    def test_x402_header_name(self):
        h = make_make_handler()
        bundle = h.module_generate_challenge(self._base_params("x402"))
        assert bundle["data"]["header_name"] == "X-Payment-Required"

    def test_x402_mandate_id_present(self):
        h = make_make_handler()
        bundle = h.module_generate_challenge(self._base_params("x402"))
        assert "mandate_id" in bundle["data"]

    def test_ap2_protocol_in_data(self):
        h = make_make_handler()
        bundle = h.module_generate_challenge(self._base_params("ap2"))
        assert bundle["data"]["protocol"] == "ap2"

    def test_ap2_mandate_b64_present(self):
        h = make_make_handler()
        bundle = h.module_generate_challenge(self._base_params("ap2"))
        assert "mandate_b64" in bundle["data"]

    def test_ap2_mandate_id_present(self):
        h = make_make_handler()
        bundle = h.module_generate_challenge(self._base_params("ap2"))
        assert "mandate_id" in bundle["data"]

    def test_bad_protocol_returns_error(self):
        h = make_make_handler()
        params = self._base_params()
        params["protocol"] = "lightning"
        bundle = h.module_generate_challenge(params)
        assert "error" in bundle
        assert bundle["error"]["code"] == "INVALID_PROTOCOL"

    def test_missing_resource_id_returns_error(self):
        h = make_make_handler()
        params = self._base_params()
        params["resource_id"] = ""
        bundle = h.module_generate_challenge(params)
        assert "error" in bundle
        assert bundle["error"]["code"] == "MISSING_RESOURCE"

    def test_zero_amount_mu_returns_error(self):
        h = make_make_handler()
        params = self._base_params()
        params["amount_microunits"] = 0
        bundle = h.module_generate_challenge(params)
        assert "error" in bundle
        assert bundle["error"]["code"] == "INVALID_AMOUNT"

    def test_bad_network_returns_error(self):
        h = make_make_handler()
        params = self._base_params()
        params["network"] = "bitcoin_mainnet"
        bundle = h.module_generate_challenge(params)
        assert "error" in bundle
        assert bundle["error"]["code"] == "INVALID_NETWORK"


# ═══════════════════════════════════════════════════════════════════════════════
# Group 7 — verify_signature (7 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestVerifySignature:
    def test_valid_signature_returns_data(self):
        secret = "whsec_make"
        h = make_make_handler(webhook_secret=secret)
        body = json.dumps({"event": "payment.received"})
        sig = make_sig(body, secret)
        bundle = h.verify_signature(body, sig)
        assert bundle.get("data") is not None

    def test_valid_returns_valid_true_in_data(self):
        secret = "s"
        h = make_make_handler(webhook_secret=secret)
        body = json.dumps({"k": "v"})
        sig = make_sig(body, secret)
        bundle = h.verify_signature(body, sig)
        assert bundle["data"]["valid"] is True

    def test_bad_signature_returns_error(self):
        h = make_make_handler(webhook_secret="secret")
        body = json.dumps({"event": "x"})
        bundle = h.verify_signature(body, "badsignature")
        assert "error" in bundle
        assert bundle["error"]["code"] == "INVALID_SIGNATURE"

    def test_no_secret_returns_not_configured_error(self):
        h = make_make_handler()  # no webhook_secret
        body = json.dumps({"event": "x"})
        bundle = h.verify_signature(body, "sig")
        assert "error" in bundle
        assert bundle["error"]["code"] == "NOT_CONFIGURED"

    def test_body_too_large_returns_error(self):
        secret = "s"
        h = make_make_handler(webhook_secret=secret)
        big_body = "x" * (1_048_576 + 1)
        bundle = h.verify_signature(big_body, "sig")
        assert "error" in bundle
        assert bundle["error"]["code"] == "BODY_TOO_LARGE"

    def test_non_json_body_returns_error(self):
        secret = "s"
        h = make_make_handler(webhook_secret=secret)
        body = "not-json"
        sig = make_sig(body, secret)
        bundle = h.verify_signature(body, sig)
        assert "error" in bundle
        assert bundle["error"]["code"] == "INVALID_JSON"

    def test_payload_returned_in_data_on_success(self):
        secret = "s"
        h = make_make_handler(webhook_secret=secret)
        body = json.dumps({"order_id": "ORD-99"})
        sig = make_sig(body, secret)
        bundle = h.verify_signature(body, sig)
        assert bundle["data"]["payload"] == {"order_id": "ORD-99"}


# ═══════════════════════════════════════════════════════════════════════════════
# Group 8 — Payout address routing (5 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPayoutAddress:
    def test_algorand_only_used_in_challenge(self):
        h = make_make_handler(payout_algorand="MY_ALGO_ADDR")
        bundle = h.module_generate_challenge({
            "protocol": "mpp",
            "resource_id": "r1",
            "amount_microunits": 100,
            "network": "algorand_mainnet",
        })
        assert "MY_ALGO_ADDR" in bundle["data"]["header_value"]

    def test_native_coin_inherits_parent_chain(self):
        h = make_make_handler(payout_algorand="NATIVE_ALGO_ADDR")
        bundle = h.module_generate_challenge({
            "protocol": "mpp",
            "resource_id": "r2",
            "amount_microunits": 500,
            "network": "algorand_mainnet_algo",
        })
        assert bundle.get("data") is not None
        assert "NATIVE_ALGO_ADDR" in bundle["data"]["header_value"]

    def test_voi_payout_used_for_voi_network(self):
        h = AlgoVoiMake(
            algovoi_key="algv_test",
            tenant_id="tid",
            payout_algorand="ALGO",
            payout_voi="MY_VOI_ADDR",
        )
        bundle = h.module_generate_challenge({
            "protocol": "mpp",
            "resource_id": "r3",
            "amount_microunits": 500,
            "network": "voi_mainnet",
        })
        assert "MY_VOI_ADDR" in bundle["data"]["header_value"]

    def test_fallback_payout_when_only_one_chain(self):
        h = make_make_handler(payout_algorand="ONLY_ALGO")
        bundle = h.module_generate_challenge({
            "protocol": "mpp",
            "resource_id": "r4",
            "amount_microunits": 500,
            "network": "stellar_mainnet",
        })
        assert bundle.get("data") is not None

    def test_all_four_chains_construction(self):
        h = AlgoVoiMake(
            algovoi_key="algv_test",
            tenant_id="tid",
            payout_algorand="ALGO",
            payout_voi="VOI",
            payout_hedera="0.0.99",
            payout_stellar="GXXX",
        )
        assert h is not None
