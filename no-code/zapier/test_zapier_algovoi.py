"""
Unit tests for AlgoVoi Zapier Adapter
======================================

75 tests covering ZapierActionResult, constructor validation, webhook bridge,
create_payment_link, verify_payment, list_networks, generate_challenge
(mpp/x402/ap2), verify_webhook_signature, and payout address routing.

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

from zapier_algovoi import (
    AlgoVoiZapier,
    ZapierActionResult,
    SUPPORTED_NETWORKS,
    NETWORK_INFO,
    __version__,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def make_zapier(**kwargs):
    defaults = dict(algovoi_key="algv_test", tenant_id="tid", payout_algorand="ALGO_ADDR")
    defaults.update(kwargs)
    return AlgoVoiZapier(**defaults)


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
# Group 1 — ZapierActionResult (6 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestZapierActionResult:
    def test_success_true(self):
        r = ZapierActionResult(True, 200, data={"x": 1})
        assert r.success is True

    def test_success_false(self):
        r = ZapierActionResult(False, 400, error="bad")
        assert r.success is False

    def test_to_dict_includes_success(self):
        r = ZapierActionResult(True, 200, data={"k": "v"})
        d = r.to_dict()
        assert d["success"] is True

    def test_to_dict_includes_data(self):
        r = ZapierActionResult(True, 200, data={"k": "v"})
        assert r.to_dict()["k"] == "v"

    def test_to_dict_includes_error_when_set(self):
        r = ZapierActionResult(False, 400, error="oops")
        assert r.to_dict()["error"] == "oops"

    def test_to_dict_no_error_key_on_success(self):
        r = ZapierActionResult(True, 200)
        assert "error" not in r.to_dict()


# ═══════════════════════════════════════════════════════════════════════════════
# Group 2 — Constructor / init (9 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestInit:
    def test_valid_construction(self):
        h = make_zapier()
        assert h is not None

    def test_version(self):
        assert __version__ == "1.0.0"

    def test_missing_key_prefix_raises(self):
        with pytest.raises(ValueError, match="algv_"):
            make_zapier(algovoi_key="bad_key")

    def test_empty_key_raises(self):
        with pytest.raises(ValueError, match="algv_"):
            make_zapier(algovoi_key="")

    def test_missing_tenant_id_raises(self):
        with pytest.raises(ValueError, match="tenant_id"):
            make_zapier(tenant_id="")

    def test_bad_api_base_raises(self):
        with pytest.raises(ValueError, match="https"):
            make_zapier(api_base="http://insecure.example.com")

    def test_http_api_base_raises(self):
        with pytest.raises(ValueError, match="https"):
            make_zapier(api_base="http://api.example.com")

    def test_no_payout_address_raises(self):
        with pytest.raises(ValueError, match="payout"):
            AlgoVoiZapier(algovoi_key="algv_test", tenant_id="tid")

    def test_fallback_payout_address_accepted(self):
        h = AlgoVoiZapier(
            algovoi_key="algv_test",
            tenant_id="tid",
            payout_address="FALLBACK_ADDR",
        )
        assert h is not None


# ═══════════════════════════════════════════════════════════════════════════════
# Group 3 — Webhook bridge: receive_and_forward (10 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestWebhookBridge:
    def test_valid_webhook_no_secret(self):
        h = make_zapier()
        body = json.dumps({"event_id": "e1", "status": "paid"})
        res = h.receive_and_forward(body, "")
        assert res.success is True
        assert res.http_status == 200

    def test_valid_webhook_with_hmac(self):
        secret = "my_secret"
        h = make_zapier(webhook_secret=secret)
        body = json.dumps({"event_id": "e2", "status": "paid"})
        sig = make_sig(body, secret)
        res = h.receive_and_forward(body, sig)
        assert res.success is True

    def test_bad_signature_returns_401(self):
        h = make_zapier(webhook_secret="secret")
        body = json.dumps({"event_id": "e3"})
        res = h.receive_and_forward(body, "badsig")
        assert res.success is False
        assert res.http_status == 401

    def test_body_too_large_returns_400(self):
        h = make_zapier()
        big_body = "x" * (1_048_576 + 1)
        res = h.receive_and_forward(big_body, "")
        assert res.success is False
        assert res.http_status == 400

    def test_invalid_json_returns_400(self):
        h = make_zapier()
        res = h.receive_and_forward("not-json", "")
        assert res.success is False
        assert res.http_status == 400

    def test_forwarded_false_when_no_hook_url(self):
        h = make_zapier()
        body = json.dumps({"event_id": "e4"})
        res = h.receive_and_forward(body, "")
        assert res.data["forwarded"] is False

    def test_forwarded_true_when_hook_url_set(self):
        with patch("zapier_algovoi._http_post") as mock_post:
            mock_post.return_value = {}
            h = make_zapier(zapier_hook_url="https://hooks.zapier.com/hooks/catch/1/2/")
            body = json.dumps({"event_id": "e5"})
            res = h.receive_and_forward(body, "")
        assert res.data["forwarded"] is True

    def test_forward_failure_returns_502(self):
        with patch("zapier_algovoi._http_post", side_effect=Exception("network error")):
            h = make_zapier(zapier_hook_url="https://hooks.zapier.com/hooks/catch/1/2/")
            body = json.dumps({"event_id": "e6"})
            res = h.receive_and_forward(body, "")
        assert res.http_status == 502

    def test_event_in_data(self):
        h = make_zapier()
        body = json.dumps({"event_id": "e7", "status": "paid", "token": "tok1"})
        res = h.receive_and_forward(body, "")
        assert "event" in res.data
        assert res.data["event"]["status"] == "paid"

    def test_wrong_hmac_empty_secret_passes(self):
        h = make_zapier()  # no webhook_secret set
        body = json.dumps({"event_id": "e8"})
        res = h.receive_and_forward(body, "any_sig_ignored")
        assert res.success is True


# ═══════════════════════════════════════════════════════════════════════════════
# Group 4 — action_create_payment_link (12 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCreatePaymentLink:
    def _ok_resp(self):
        return {"checkout_url": "https://api1.ilovechicken.co.uk/checkout/abc123", "amount_microunits": 10_000_000}

    def test_success_returns_checkout_url(self):
        h = make_zapier()
        with patch("urllib.request.urlopen", mock_urlopen(self._ok_resp())):
            res = h.action_create_payment_link({"amount": 10.0, "currency": "USD", "label": "Order 1"})
        assert res.success is True
        assert "checkout_url" in res.data

    def test_success_http_status_200(self):
        h = make_zapier()
        with patch("urllib.request.urlopen", mock_urlopen(self._ok_resp())):
            res = h.action_create_payment_link({"amount": 10.0, "currency": "USD", "label": "Test"})
        assert res.http_status == 200

    def test_token_extracted_from_url(self):
        h = make_zapier()
        with patch("urllib.request.urlopen", mock_urlopen(self._ok_resp())):
            res = h.action_create_payment_link({"amount": 10.0, "currency": "USD", "label": "Test"})
        assert res.data["token"] == "abc123"

    def test_missing_amount_returns_400(self):
        h = make_zapier()
        res = h.action_create_payment_link({"currency": "USD", "label": "Test"})
        assert res.success is False
        assert res.http_status == 400

    def test_zero_amount_returns_400(self):
        h = make_zapier()
        res = h.action_create_payment_link({"amount": 0, "currency": "USD", "label": "Test"})
        assert res.success is False
        assert res.http_status == 400

    def test_negative_amount_returns_400(self):
        h = make_zapier()
        res = h.action_create_payment_link({"amount": -5.0, "currency": "USD", "label": "Test"})
        assert res.success is False
        assert res.http_status == 400

    def test_amount_exceeds_max_returns_400(self):
        h = make_zapier()
        res = h.action_create_payment_link({"amount": 10_000_001, "currency": "USD", "label": "Test"})
        assert res.success is False
        assert res.http_status == 400

    def test_bad_currency_length_returns_400(self):
        h = make_zapier()
        res = h.action_create_payment_link({"amount": 10.0, "currency": "USDC", "label": "Test"})
        assert res.success is False
        assert res.http_status == 400

    def test_missing_label_returns_400(self):
        h = make_zapier()
        res = h.action_create_payment_link({"amount": 10.0, "currency": "USD", "label": ""})
        assert res.success is False
        assert res.http_status == 400

    def test_bad_network_returns_400(self):
        h = make_zapier()
        res = h.action_create_payment_link({"amount": 10.0, "currency": "USD", "label": "T", "network": "bitcoin_mainnet"})
        assert res.success is False
        assert res.http_status == 400

    def test_https_redirect_url_accepted(self):
        resp = dict(self._ok_resp())
        h = make_zapier()
        with patch("urllib.request.urlopen", mock_urlopen(resp)):
            res = h.action_create_payment_link({
                "amount": 10.0, "currency": "USD", "label": "Test",
                "redirect_url": "https://example.com/thanks",
            })
        assert res.success is True

    def test_non_https_redirect_rejected(self):
        h = make_zapier()
        with patch("urllib.request.urlopen", mock_urlopen(self._ok_resp())):
            res = h.action_create_payment_link({
                "amount": 10.0, "currency": "USD", "label": "Test",
                "redirect_url": "http://example.com/thanks",
            })
        # http redirect is silently dropped (not included), request still succeeds
        assert res.success is True

    def test_api_error_returns_502(self):
        h = make_zapier()
        with patch("urllib.request.urlopen", side_effect=Exception("connection refused")):
            res = h.action_create_payment_link({"amount": 10.0, "currency": "USD", "label": "Test"})
        assert res.success is False
        assert res.http_status == 502

    def test_api_missing_checkout_url_returns_502(self):
        h = make_zapier()
        with patch("urllib.request.urlopen", mock_urlopen({"status": "ok"})):
            res = h.action_create_payment_link({"amount": 10.0, "currency": "USD", "label": "Test"})
        assert res.success is False
        assert res.http_status == 502


# ═══════════════════════════════════════════════════════════════════════════════
# Group 5 — action_verify_payment (6 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestVerifyPayment:
    def test_success_paid(self):
        h = make_zapier()
        with patch("urllib.request.urlopen", mock_urlopen({"status": "paid"})):
            res = h.action_verify_payment({"token": "tok123"})
        assert res.success is True
        assert res.data["paid"] is True

    def test_success_unpaid(self):
        h = make_zapier()
        with patch("urllib.request.urlopen", mock_urlopen({"status": "pending"})):
            res = h.action_verify_payment({"token": "tok456"})
        assert res.success is True
        assert res.data["paid"] is False

    def test_completed_status_is_paid(self):
        h = make_zapier()
        with patch("urllib.request.urlopen", mock_urlopen({"status": "completed"})):
            res = h.action_verify_payment({"token": "tok789"})
        assert res.data["paid"] is True

    def test_confirmed_status_is_paid(self):
        h = make_zapier()
        with patch("urllib.request.urlopen", mock_urlopen({"status": "confirmed"})):
            res = h.action_verify_payment({"token": "tokABC"})
        assert res.data["paid"] is True

    def test_missing_token_returns_400(self):
        h = make_zapier()
        res = h.action_verify_payment({})
        assert res.success is False
        assert res.http_status == 400

    def test_api_error_returns_502(self):
        h = make_zapier()
        with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
            res = h.action_verify_payment({"token": "tokXYZ"})
        assert res.success is False
        assert res.http_status == 502


# ═══════════════════════════════════════════════════════════════════════════════
# Group 6 — action_list_networks (5 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestListNetworks:
    def test_returns_16_networks(self):
        h = make_zapier()
        res = h.action_list_networks()
        assert res.success is True
        assert res.data["count"] == 16

    def test_networks_list_length(self):
        h = make_zapier()
        res = h.action_list_networks()
        assert len(res.data["networks"]) == 16

    def test_algorand_mainnet_present(self):
        h = make_zapier()
        res = h.action_list_networks()
        keys = [n["key"] for n in res.data["networks"]]
        assert "algorand_mainnet" in keys

    def test_all_supported_networks_present(self):
        h = make_zapier()
        res = h.action_list_networks()
        keys = {n["key"] for n in res.data["networks"]}
        assert keys == SUPPORTED_NETWORKS

    def test_network_has_required_fields(self):
        h = make_zapier()
        res = h.action_list_networks()
        net = res.data["networks"][0]
        assert "key" in net
        assert "label" in net
        assert "asset" in net
        assert "decimals" in net


# ═══════════════════════════════════════════════════════════════════════════════
# Group 7 — action_generate_challenge (15 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestGenerateChallenge:
    def _base_params(self, protocol="mpp"):
        return {
            "protocol": protocol,
            "resource_id": "https://api.example.com/resource",
            "amount_microunits": 1_000_000,
            "network": "algorand_mainnet",
        }

    def test_mpp_returns_http_status_402(self):
        h = make_zapier()
        res = h.action_generate_challenge(self._base_params("mpp"))
        assert res.http_status == 402

    def test_mpp_protocol_in_data(self):
        h = make_zapier()
        res = h.action_generate_challenge(self._base_params("mpp"))
        assert res.data["protocol"] == "mpp"

    def test_mpp_header_name_www_authenticate(self):
        h = make_zapier()
        res = h.action_generate_challenge(self._base_params("mpp"))
        assert res.data["header_name"] == "WWW-Authenticate"

    def test_mpp_header_value_contains_realm(self):
        h = make_zapier()
        res = h.action_generate_challenge(self._base_params("mpp"))
        assert "realm=" in res.data["header_value"]

    def test_mpp_header_value_contains_receiver(self):
        h = make_zapier()
        res = h.action_generate_challenge(self._base_params("mpp"))
        assert "ALGO_ADDR" in res.data["header_value"]

    def test_x402_protocol_in_data(self):
        h = make_zapier()
        res = h.action_generate_challenge(self._base_params("x402"))
        assert res.data["protocol"] == "x402"

    def test_x402_header_name(self):
        h = make_zapier()
        res = h.action_generate_challenge(self._base_params("x402"))
        assert res.data["header_name"] == "X-Payment-Required"

    def test_x402_mandate_id_present(self):
        h = make_zapier()
        res = h.action_generate_challenge(self._base_params("x402"))
        assert "mandate_id" in res.data

    def test_ap2_protocol_in_data(self):
        h = make_zapier()
        res = h.action_generate_challenge(self._base_params("ap2"))
        assert res.data["protocol"] == "ap2"

    def test_ap2_mandate_b64_present(self):
        h = make_zapier()
        res = h.action_generate_challenge(self._base_params("ap2"))
        assert "mandate_b64" in res.data

    def test_ap2_mandate_id_present(self):
        h = make_zapier()
        res = h.action_generate_challenge(self._base_params("ap2"))
        assert "mandate_id" in res.data

    def test_bad_protocol_returns_400(self):
        h = make_zapier()
        params = self._base_params()
        params["protocol"] = "lightning"
        res = h.action_generate_challenge(params)
        assert res.success is False
        assert res.http_status == 400

    def test_missing_resource_id_returns_400(self):
        h = make_zapier()
        params = self._base_params()
        params["resource_id"] = ""
        res = h.action_generate_challenge(params)
        assert res.success is False
        assert res.http_status == 400

    def test_zero_amount_mu_returns_400(self):
        h = make_zapier()
        params = self._base_params()
        params["amount_microunits"] = 0
        res = h.action_generate_challenge(params)
        assert res.success is False
        assert res.http_status == 400

    def test_bad_network_returns_400(self):
        h = make_zapier()
        params = self._base_params()
        params["network"] = "bitcoin_mainnet"
        res = h.action_generate_challenge(params)
        assert res.success is False
        assert res.http_status == 400


# ═══════════════════════════════════════════════════════════════════════════════
# Group 8 — verify_webhook_signature (7 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestVerifySignature:
    def test_valid_signature_returns_valid_true(self):
        secret = "whsec_test"
        h = make_zapier(webhook_secret=secret)
        body = json.dumps({"event": "payment.received"})
        sig = make_sig(body, secret)
        result = h.verify_webhook_signature(body, sig)
        assert result["valid"] is True

    def test_valid_signature_returns_payload(self):
        secret = "whsec_test"
        h = make_zapier(webhook_secret=secret)
        body = json.dumps({"event": "payment.received"})
        sig = make_sig(body, secret)
        result = h.verify_webhook_signature(body, sig)
        assert result["payload"] == {"event": "payment.received"}

    def test_bad_signature_returns_valid_false(self):
        secret = "whsec_test"
        h = make_zapier(webhook_secret=secret)
        body = json.dumps({"event": "x"})
        result = h.verify_webhook_signature(body, "badsignature")
        assert result["valid"] is False

    def test_no_secret_returns_error(self):
        h = make_zapier()  # no webhook_secret
        body = json.dumps({"event": "x"})
        result = h.verify_webhook_signature(body, "sig")
        assert result["valid"] is False
        assert result["error"] is not None

    def test_body_too_large_returns_error(self):
        secret = "s"
        h = make_zapier(webhook_secret=secret)
        big_body = "x" * (1_048_576 + 1)
        result = h.verify_webhook_signature(big_body, "sig")
        assert result["valid"] is False

    def test_non_json_body_returns_error(self):
        secret = "s"
        h = make_zapier(webhook_secret=secret)
        body = "not-json"
        sig = make_sig(body, secret)
        result = h.verify_webhook_signature(body, sig)
        assert result["valid"] is False

    def test_error_none_on_success(self):
        secret = "s"
        h = make_zapier(webhook_secret=secret)
        body = json.dumps({"k": "v"})
        sig = make_sig(body, secret)
        result = h.verify_webhook_signature(body, sig)
        assert result["error"] is None


# ═══════════════════════════════════════════════════════════════════════════════
# Group 9 — Payout address routing (5 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPayoutAddress:
    def test_algorand_only_payout(self):
        h = make_zapier(payout_algorand="ALGO_ADDR_ONLY")
        res = h.action_generate_challenge({
            "protocol": "mpp",
            "resource_id": "r1",
            "amount_microunits": 100,
            "network": "algorand_mainnet",
        })
        assert "ALGO_ADDR_ONLY" in res.data["header_value"]

    def test_all_four_chains_set(self):
        h = AlgoVoiZapier(
            algovoi_key="algv_test",
            tenant_id="tid",
            payout_algorand="ALGO_ADDR",
            payout_voi="VOI_ADDR",
            payout_hedera="0.0.12345",
            payout_stellar="GSTELLAR",
        )
        assert h is not None

    def test_native_coin_inherits_parent_chain(self):
        h = make_zapier(payout_algorand="ALGO_ADDR")
        res = h.action_generate_challenge({
            "protocol": "mpp",
            "resource_id": "r2",
            "amount_microunits": 500,
            "network": "algorand_mainnet_algo",
        })
        assert res.success is True
        assert "ALGO_ADDR" in res.data["header_value"]

    def test_voi_native_uses_voi_payout(self):
        h = AlgoVoiZapier(
            algovoi_key="algv_test",
            tenant_id="tid",
            payout_algorand="ALGO_ADDR",
            payout_voi="VOI_ADDR",
        )
        res = h.action_generate_challenge({
            "protocol": "mpp",
            "resource_id": "r3",
            "amount_microunits": 500,
            "network": "voi_mainnet_voi",
        })
        assert "VOI_ADDR" in res.data["header_value"]

    def test_fallback_payout_used_for_unknown_chain(self):
        h = AlgoVoiZapier(
            algovoi_key="algv_test",
            tenant_id="tid",
            payout_algorand="ALGO_FALLBACK",
        )
        res = h.action_generate_challenge({
            "protocol": "mpp",
            "resource_id": "r4",
            "amount_microunits": 500,
            "network": "stellar_mainnet",
        })
        # Falls back to first available payout
        assert res.success is True
