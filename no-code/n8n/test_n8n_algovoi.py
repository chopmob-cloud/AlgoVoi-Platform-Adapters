"""
Unit tests for AlgoVoi n8n Adapter
=====================================

75 tests covering constructor validation, webhook receiver, create_payment_link,
verify_payment, list_networks, generate_mpp_challenge, generate_x402_challenge,
generate_ap2_mandate, verify_webhook_signature, and payout address routing.

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

from n8n_algovoi import (
    AlgoVoiN8n,
    SUPPORTED_NETWORKS,
    NETWORK_INFO,
    __version__,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def make_n8n(**kwargs):
    defaults = dict(algovoi_key="algv_test", tenant_id="tid", payout_algorand="ALGO_ADDR")
    defaults.update(kwargs)
    return AlgoVoiN8n(**defaults)


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
        h = make_n8n()
        assert h is not None

    def test_version(self):
        assert __version__ == "1.0.0"

    def test_missing_key_prefix_raises(self):
        with pytest.raises(ValueError, match="algv_"):
            make_n8n(algovoi_key="bad_key")

    def test_empty_key_raises(self):
        with pytest.raises(ValueError, match="algv_"):
            make_n8n(algovoi_key="")

    def test_missing_tenant_id_raises(self):
        with pytest.raises(ValueError, match="tenant_id"):
            make_n8n(tenant_id="")

    def test_bad_api_base_raises(self):
        with pytest.raises(ValueError, match="https"):
            make_n8n(api_base="http://insecure.example.com")

    def test_no_payout_address_raises(self):
        with pytest.raises(ValueError, match="payout"):
            AlgoVoiN8n(algovoi_key="algv_test", tenant_id="tid")

    def test_fallback_payout_accepted(self):
        h = AlgoVoiN8n(
            algovoi_key="algv_test",
            tenant_id="tid",
            payout_address="FALLBACK_ADDR",
        )
        assert h is not None

    def test_all_four_payout_chains_accepted(self):
        h = AlgoVoiN8n(
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

class TestWebhookReceiver:
    def test_valid_webhook_no_secret_success_true(self):
        h = make_n8n()
        body = json.dumps({"event_id": "e1", "status": "paid"})
        item = h.receive_webhook(body, "")
        assert item["json"]["success"] is True

    def test_valid_webhook_with_hmac_success_true(self):
        secret = "whsec_n8n"
        h = make_n8n(webhook_secret=secret)
        body = json.dumps({"event_id": "e2", "status": "paid"})
        sig = make_sig(body, secret)
        item = h.receive_webhook(body, sig)
        assert item["json"]["success"] is True

    def test_bad_signature_has_error(self):
        h = make_n8n(webhook_secret="secret")
        body = json.dumps({"event_id": "e3"})
        item = h.receive_webhook(body, "badsig")
        assert "error" in item["json"]

    def test_bad_signature_error_code(self):
        h = make_n8n(webhook_secret="secret")
        body = json.dumps({"event_id": "e3"})
        item = h.receive_webhook(body, "badsig")
        assert item["json"]["code"] == "INVALID_SIGNATURE"

    def test_body_too_large_has_error(self):
        h = make_n8n()
        big_body = "x" * (1_048_576 + 1)
        item = h.receive_webhook(big_body, "")
        assert "error" in item["json"]
        assert item["json"]["code"] == "BODY_TOO_LARGE"

    def test_invalid_json_has_error(self):
        h = make_n8n()
        item = h.receive_webhook("not-json", "")
        assert "error" in item["json"]
        assert item["json"]["code"] == "INVALID_JSON"

    def test_event_id_in_json(self):
        h = make_n8n()
        body = json.dumps({"event_id": "evt-77"})
        item = h.receive_webhook(body, "")
        assert item["json"]["event_id"] == "evt-77"

    def test_status_in_json(self):
        h = make_n8n()
        body = json.dumps({"event_id": "e4", "status": "completed"})
        item = h.receive_webhook(body, "")
        assert item["json"]["status"] == "completed"

    def test_verified_false_when_no_secret(self):
        h = make_n8n()
        body = json.dumps({"event_id": "e5"})
        item = h.receive_webhook(body, "")
        assert item["json"]["verified"] is False

    def test_verified_true_when_secret_set(self):
        secret = "s"
        h = make_n8n(webhook_secret=secret)
        body = json.dumps({"event_id": "e6"})
        sig = make_sig(body, secret)
        item = h.receive_webhook(body, sig)
        assert item["json"]["verified"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# Group 3 — execute_create_payment_link (13 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCreatePaymentLink:
    def _ok_resp(self):
        return {"checkout_url": "https://api1.ilovechicken.co.uk/checkout/n8nTok", "amount_microunits": 5_000_000}

    def test_success_true(self):
        h = make_n8n()
        with patch("urllib.request.urlopen", mock_urlopen(self._ok_resp())):
            item = h.execute_create_payment_link({"amount": 5.0, "currency": "USD", "label": "Order"})
        assert item["json"]["success"] is True

    def test_checkout_url_in_json(self):
        h = make_n8n()
        with patch("urllib.request.urlopen", mock_urlopen(self._ok_resp())):
            item = h.execute_create_payment_link({"amount": 5.0, "currency": "USD", "label": "Order"})
        assert "checkout_url" in item["json"]

    def test_token_extracted(self):
        h = make_n8n()
        with patch("urllib.request.urlopen", mock_urlopen(self._ok_resp())):
            item = h.execute_create_payment_link({"amount": 5.0, "currency": "USD", "label": "Order"})
        assert item["json"]["token"] == "n8nTok"

    def test_missing_amount_has_error(self):
        h = make_n8n()
        item = h.execute_create_payment_link({"currency": "USD", "label": "Test"})
        assert "error" in item["json"]
        assert item["json"]["code"] == "INVALID_AMOUNT"

    def test_zero_amount_has_error(self):
        h = make_n8n()
        item = h.execute_create_payment_link({"amount": 0, "currency": "USD", "label": "Test"})
        assert "error" in item["json"]

    def test_negative_amount_has_error(self):
        h = make_n8n()
        item = h.execute_create_payment_link({"amount": -1.0, "currency": "USD", "label": "Test"})
        assert "error" in item["json"]

    def test_amount_too_large_has_error(self):
        h = make_n8n()
        item = h.execute_create_payment_link({"amount": 10_000_001, "currency": "USD", "label": "T"})
        assert "error" in item["json"]

    def test_bad_currency_has_error(self):
        h = make_n8n()
        item = h.execute_create_payment_link({"amount": 5.0, "currency": "USDC", "label": "T"})
        assert "error" in item["json"]
        assert item["json"]["code"] == "INVALID_CURRENCY"

    def test_missing_label_has_error(self):
        h = make_n8n()
        item = h.execute_create_payment_link({"amount": 5.0, "currency": "USD", "label": ""})
        assert "error" in item["json"]
        assert item["json"]["code"] == "MISSING_LABEL"

    def test_bad_network_has_error(self):
        h = make_n8n()
        item = h.execute_create_payment_link({
            "amount": 5.0, "currency": "USD", "label": "T",
            "network": "ethereum_mainnet",
        })
        assert "error" in item["json"]
        assert item["json"]["code"] == "INVALID_NETWORK"

    def test_https_redirect_url_accepted(self):
        h = make_n8n()
        with patch("urllib.request.urlopen", mock_urlopen(self._ok_resp())):
            item = h.execute_create_payment_link({
                "amount": 5.0, "currency": "USD", "label": "Test",
                "redirect_url": "https://example.com/thanks",
            })
        assert item["json"]["success"] is True

    def test_api_error_has_error(self):
        h = make_n8n()
        with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
            item = h.execute_create_payment_link({"amount": 5.0, "currency": "USD", "label": "T"})
        assert "error" in item["json"]
        assert item["json"]["code"] == "API_ERROR"

    def test_api_missing_checkout_url_has_error(self):
        h = make_n8n()
        with patch("urllib.request.urlopen", mock_urlopen({"status": "ok"})):
            item = h.execute_create_payment_link({"amount": 5.0, "currency": "USD", "label": "T"})
        assert "error" in item["json"]


# ═══════════════════════════════════════════════════════════════════════════════
# Group 4 — execute_verify_payment (6 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestVerifyPayment:
    def test_success_paid(self):
        h = make_n8n()
        with patch("urllib.request.urlopen", mock_urlopen({"status": "paid"})):
            item = h.execute_verify_payment({"token": "tok123"})
        assert item["json"]["success"] is True
        assert item["json"]["paid"] is True

    def test_success_unpaid(self):
        h = make_n8n()
        with patch("urllib.request.urlopen", mock_urlopen({"status": "pending"})):
            item = h.execute_verify_payment({"token": "tok456"})
        assert item["json"]["paid"] is False

    def test_completed_is_paid(self):
        h = make_n8n()
        with patch("urllib.request.urlopen", mock_urlopen({"status": "completed"})):
            item = h.execute_verify_payment({"token": "tok789"})
        assert item["json"]["paid"] is True

    def test_confirmed_is_paid(self):
        h = make_n8n()
        with patch("urllib.request.urlopen", mock_urlopen({"status": "confirmed"})):
            item = h.execute_verify_payment({"token": "tokABC"})
        assert item["json"]["paid"] is True

    def test_missing_token_has_error(self):
        h = make_n8n()
        item = h.execute_verify_payment({})
        assert "error" in item["json"]
        assert item["json"]["code"] == "MISSING_TOKEN"

    def test_api_error_has_error(self):
        h = make_n8n()
        with patch("urllib.request.urlopen", side_effect=Exception("network error")):
            item = h.execute_verify_payment({"token": "tok"})
        assert "error" in item["json"]
        assert item["json"]["code"] == "API_ERROR"


# ═══════════════════════════════════════════════════════════════════════════════
# Group 5 — execute_list_networks (5 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestListNetworks:
    def test_success_true(self):
        h = make_n8n()
        item = h.execute_list_networks()
        assert item["json"]["success"] is True

    def test_count_is_16(self):
        h = make_n8n()
        item = h.execute_list_networks()
        assert item["json"]["count"] == 16

    def test_networks_list_length(self):
        h = make_n8n()
        item = h.execute_list_networks()
        assert len(item["json"]["networks"]) == 16

    def test_all_supported_networks_present(self):
        h = make_n8n()
        item = h.execute_list_networks()
        keys = {n["key"] for n in item["json"]["networks"]}
        assert keys == SUPPORTED_NETWORKS

    def test_network_has_required_fields(self):
        h = make_n8n()
        item = h.execute_list_networks()
        net = item["json"]["networks"][0]
        for field in ("key", "label", "asset", "decimals"):
            assert field in net


# ═══════════════════════════════════════════════════════════════════════════════
# Group 6 — execute_generate_mpp_challenge (8 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestMppChallenge:
    def _base_params(self):
        return {
            "resource_id": "https://api.example.com/resource",
            "amount_microunits": 1_000_000,
            "network": "algorand_mainnet",
        }

    def test_success_true(self):
        h = make_n8n()
        item = h.execute_generate_mpp_challenge(self._base_params())
        assert item["json"]["success"] is True

    def test_protocol_is_mpp(self):
        h = make_n8n()
        item = h.execute_generate_mpp_challenge(self._base_params())
        assert item["json"]["protocol"] == "mpp"

    def test_header_name_www_authenticate(self):
        h = make_n8n()
        item = h.execute_generate_mpp_challenge(self._base_params())
        assert item["json"]["header_name"] == "WWW-Authenticate"

    def test_header_value_contains_realm(self):
        h = make_n8n()
        item = h.execute_generate_mpp_challenge(self._base_params())
        assert "realm=" in item["json"]["header_value"]

    def test_header_value_contains_payout_address(self):
        h = make_n8n()
        item = h.execute_generate_mpp_challenge(self._base_params())
        assert "ALGO_ADDR" in item["json"]["header_value"]

    def test_missing_resource_id_has_error(self):
        h = make_n8n()
        params = self._base_params()
        params["resource_id"] = ""
        item = h.execute_generate_mpp_challenge(params)
        assert "error" in item["json"]
        assert item["json"]["code"] == "MISSING_RESOURCE"

    def test_zero_amount_has_error(self):
        h = make_n8n()
        params = self._base_params()
        params["amount_microunits"] = 0
        item = h.execute_generate_mpp_challenge(params)
        assert "error" in item["json"]
        assert item["json"]["code"] == "INVALID_AMOUNT"

    def test_bad_network_has_error(self):
        h = make_n8n()
        params = self._base_params()
        params["network"] = "bitcoin_mainnet"
        item = h.execute_generate_mpp_challenge(params)
        assert "error" in item["json"]
        assert item["json"]["code"] == "INVALID_NETWORK"


# ═══════════════════════════════════════════════════════════════════════════════
# Group 7 — execute_generate_x402_challenge (7 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestX402Challenge:
    def _base_params(self):
        return {
            "resource_id": "https://api.example.com/resource",
            "amount_microunits": 2_000_000,
            "network": "algorand_mainnet",
        }

    def test_success_true(self):
        h = make_n8n()
        item = h.execute_generate_x402_challenge(self._base_params())
        assert item["json"]["success"] is True

    def test_protocol_is_x402(self):
        h = make_n8n()
        item = h.execute_generate_x402_challenge(self._base_params())
        assert item["json"]["protocol"] == "x402"

    def test_header_name(self):
        h = make_n8n()
        item = h.execute_generate_x402_challenge(self._base_params())
        assert item["json"]["header_name"] == "X-Payment-Required"

    def test_mandate_id_present(self):
        h = make_n8n()
        item = h.execute_generate_x402_challenge(self._base_params())
        assert "mandate_id" in item["json"]

    def test_missing_resource_id_has_error(self):
        h = make_n8n()
        params = self._base_params()
        params["resource_id"] = ""
        item = h.execute_generate_x402_challenge(params)
        assert "error" in item["json"]

    def test_zero_amount_has_error(self):
        h = make_n8n()
        params = self._base_params()
        params["amount_microunits"] = 0
        item = h.execute_generate_x402_challenge(params)
        assert "error" in item["json"]

    def test_bad_network_has_error(self):
        h = make_n8n()
        params = self._base_params()
        params["network"] = "solana_mainnet"
        item = h.execute_generate_x402_challenge(params)
        assert "error" in item["json"]


# ═══════════════════════════════════════════════════════════════════════════════
# Group 8 — execute_generate_ap2_mandate (7 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAp2Mandate:
    def _base_params(self):
        return {
            "resource_id": "https://api.example.com/resource",
            "amount_microunits": 3_000_000,
            "network": "algorand_mainnet",
        }

    def test_success_true(self):
        h = make_n8n()
        item = h.execute_generate_ap2_mandate(self._base_params())
        assert item["json"]["success"] is True

    def test_protocol_is_ap2(self):
        h = make_n8n()
        item = h.execute_generate_ap2_mandate(self._base_params())
        assert item["json"]["protocol"] == "ap2"

    def test_mandate_id_present(self):
        h = make_n8n()
        item = h.execute_generate_ap2_mandate(self._base_params())
        assert "mandate_id" in item["json"]

    def test_mandate_b64_present(self):
        h = make_n8n()
        item = h.execute_generate_ap2_mandate(self._base_params())
        assert "mandate_b64" in item["json"]

    def test_missing_resource_id_has_error(self):
        h = make_n8n()
        params = self._base_params()
        params["resource_id"] = ""
        item = h.execute_generate_ap2_mandate(params)
        assert "error" in item["json"]
        assert item["json"]["code"] == "MISSING_RESOURCE"

    def test_zero_amount_has_error(self):
        h = make_n8n()
        params = self._base_params()
        params["amount_microunits"] = 0
        item = h.execute_generate_ap2_mandate(params)
        assert "error" in item["json"]

    def test_bad_network_has_error(self):
        h = make_n8n()
        params = self._base_params()
        params["network"] = "tron_mainnet"
        item = h.execute_generate_ap2_mandate(params)
        assert "error" in item["json"]


# ═══════════════════════════════════════════════════════════════════════════════
# Group 9 — execute_verify_webhook_signature (7 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestVerifyWebhookSignature:
    def test_valid_signature_success_true(self):
        secret = "whsec_n8n"
        h = make_n8n(webhook_secret=secret)
        body = json.dumps({"event": "payment.received"})
        sig = make_sig(body, secret)
        item = h.execute_verify_webhook_signature({"raw_body": body, "signature": sig})
        assert item["json"]["success"] is True

    def test_valid_returns_valid_true(self):
        secret = "s"
        h = make_n8n(webhook_secret=secret)
        body = json.dumps({"k": "v"})
        sig = make_sig(body, secret)
        item = h.execute_verify_webhook_signature({"raw_body": body, "signature": sig})
        assert item["json"]["valid"] is True

    def test_bad_signature_has_error(self):
        h = make_n8n(webhook_secret="secret")
        body = json.dumps({"event": "x"})
        item = h.execute_verify_webhook_signature({"raw_body": body, "signature": "badsig"})
        assert "error" in item["json"]
        assert item["json"]["code"] == "INVALID_SIGNATURE"

    def test_no_secret_not_configured_error(self):
        h = make_n8n()  # no webhook_secret
        body = json.dumps({"event": "x"})
        item = h.execute_verify_webhook_signature({"raw_body": body, "signature": "sig"})
        assert "error" in item["json"]
        assert item["json"]["code"] == "NOT_CONFIGURED"

    def test_non_json_body_has_error(self):
        secret = "s"
        h = make_n8n(webhook_secret=secret)
        body = "not-json"
        sig = make_sig(body, secret)
        item = h.execute_verify_webhook_signature({"raw_body": body, "signature": sig})
        assert "error" in item["json"]
        assert item["json"]["code"] == "INVALID_JSON"

    def test_payload_returned_on_success(self):
        secret = "s"
        h = make_n8n(webhook_secret=secret)
        body = json.dumps({"order_id": "ORD-42"})
        sig = make_sig(body, secret)
        item = h.execute_verify_webhook_signature({"raw_body": body, "signature": sig})
        assert item["json"]["payload"] == {"order_id": "ORD-42"}

    def test_success_false_on_bad_sig(self):
        h = make_n8n(webhook_secret="secret")
        item = h.execute_verify_webhook_signature({"raw_body": "{}", "signature": "wrong"})
        assert item["json"].get("success") is False


# ═══════════════════════════════════════════════════════════════════════════════
# Group 10 — Payout address routing (5 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPayoutAddress:
    def test_algorand_only_used_in_mpp_challenge(self):
        h = make_n8n(payout_algorand="MY_ALGO_ADDR")
        item = h.execute_generate_mpp_challenge({
            "resource_id": "r1",
            "amount_microunits": 100,
            "network": "algorand_mainnet",
        })
        assert "MY_ALGO_ADDR" in item["json"]["header_value"]

    def test_native_coin_inherits_parent_chain(self):
        h = make_n8n(payout_algorand="NATIVE_ALGO")
        item = h.execute_generate_mpp_challenge({
            "resource_id": "r2",
            "amount_microunits": 500,
            "network": "algorand_mainnet_algo",
        })
        assert item["json"]["success"] is True
        assert "NATIVE_ALGO" in item["json"]["header_value"]

    def test_voi_payout_used_for_voi_network(self):
        h = AlgoVoiN8n(
            algovoi_key="algv_test",
            tenant_id="tid",
            payout_algorand="ALGO",
            payout_voi="MY_VOI_ADDR",
        )
        item = h.execute_generate_mpp_challenge({
            "resource_id": "r3",
            "amount_microunits": 500,
            "network": "voi_mainnet",
        })
        assert "MY_VOI_ADDR" in item["json"]["header_value"]

    def test_fallback_when_only_one_chain_set(self):
        h = make_n8n(payout_algorand="ONLY_ALGO")
        item = h.execute_generate_mpp_challenge({
            "resource_id": "r4",
            "amount_microunits": 500,
            "network": "stellar_mainnet",
        })
        assert item["json"]["success"] is True

    def test_hedera_payout_used_for_hedera_network(self):
        h = AlgoVoiN8n(
            algovoi_key="algv_test",
            tenant_id="tid",
            payout_algorand="ALGO",
            payout_hedera="0.0.99999",
        )
        item = h.execute_generate_mpp_challenge({
            "resource_id": "r5",
            "amount_microunits": 500,
            "network": "hedera_mainnet",
        })
        assert "0.0.99999" in item["json"]["header_value"]
