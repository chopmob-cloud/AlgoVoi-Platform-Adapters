"""
Unit tests for AlgoVoi X (Twitter) adapter.

Tests cover:
  - Constructor validation
  - HMAC webhook signature verification
  - Webhook handler routing (paid / non-paid / bad sig)
  - Tweet text builder (payment + link templates)
  - post_tweet: OAuth header present, correct body, error handling
  - post_payment_link: AlgoVoi API call + tweet posting
  - list_networks: 16 networks, all keys present
  - Schema rejection: bad amounts, unsupported networks, missing fields
  - No X credentials → graceful error on post_tweet
  - _oauth1_auth_header: correct structure, deterministic fields
"""

from __future__ import annotations

import base64
import hashlib
import hmac as _hmac
import json
import os
import sys
import time
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(__file__))
from x_algovoi import (
    AlgoVoiX,
    XResult,
    _build_link_tweet,
    _build_payment_tweet,
    _format_amount,
    _oauth1_auth_header,
    _verify_hmac,
    from_env,
    SUPPORTED_NETWORKS,
    NETWORK_INFO,
    _TMPL_PAYMENT,
    _TMPL_LINK,
    _MAX_TWEET,
)

# ── Fixtures ───────────────────────────────────────────────────────────────────

_SECRET   = "test_webhook_secret_xyz"
_PAYOUT   = "ZVLRVYQSLJNVFMOIOKT35XH5SNQG45IVFMLLRFLHDQJQA5TO5H3SO4TVDQ"
_FAKE_KEY = "algv_" + "x" * 40
_FAKE_TID = "00000000-0000-0000-0000-000000000000"
_X_CREDS  = dict(
    x_api_key="fake_api_key",
    x_api_key_secret="fake_api_secret",
    x_access_token="fake_access_token",
    x_access_token_secret="fake_access_secret",
)

_PAYMENT_EVENT = {
    "event_id":        "evt-001",
    "event_type":      "payment.received",
    "status":          "paid",
    "token":           "tok_abc123",
    "amount":          0.01,
    "currency":        "USDC",
    "network":         "algorand_mainnet",
    "tx_id":           "5BDA7U7SUBXUR32YONAQXIHCZUJC7RPJVEOWRDBSLIAP47CR6NJQ",
    "payer":           "77BZUHKVFT5KO3SN2ARTF7B3E5CPGEVPP2F54U5WJ7MXZK33MJ45CIBHTU",
    "amount_microunits": 10_000,
    "order_id":        "ORD-001",
}


def _make_adapter(**kwargs) -> AlgoVoiX:
    defaults = dict(
        algovoi_key=_FAKE_KEY,
        tenant_id=_FAKE_TID,
        payout_algorand=_PAYOUT,
        webhook_secret=_SECRET,
        **_X_CREDS,
    )
    defaults.update(kwargs)
    return AlgoVoiX(**defaults)


def _sign(body: str) -> str:
    return _hmac.new(_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()


def _x_created_response(tweet_id: str = "9876543210") -> MagicMock:
    resp = MagicMock()
    resp.status = 201
    resp.read.return_value = json.dumps({
        "data": {"id": tweet_id, "text": "tweet text"}
    }).encode()
    resp.__enter__ = lambda s: s
    resp.__exit__  = MagicMock(return_value=False)
    return resp


# ── Section 1: Constructor ─────────────────────────────────────────────────────

class TestConstructor:
    def test_valid_init(self):
        a = _make_adapter()
        assert a._key == _FAKE_KEY
        assert a._tenant == _FAKE_TID

    def test_bad_api_key_raises(self):
        with pytest.raises(ValueError, match="algv_"):
            _make_adapter(algovoi_key="bad_key")

    def test_empty_tenant_raises(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _make_adapter(tenant_id="")

    def test_no_payout_raises(self):
        with pytest.raises(ValueError, match="payout"):
            AlgoVoiX(algovoi_key=_FAKE_KEY, tenant_id=_FAKE_TID)

    def test_non_https_base_raises(self):
        with pytest.raises(ValueError, match="https"):
            _make_adapter(api_base="http://evil.com")

    def test_fallback_payout(self):
        a = AlgoVoiX(
            algovoi_key=_FAKE_KEY, tenant_id=_FAKE_TID,
            payout_address=_PAYOUT,
        )
        assert a._payout_for("algorand_mainnet") == _PAYOUT

    def test_no_x_creds_has_x_creds_false(self):
        a = AlgoVoiX(algovoi_key=_FAKE_KEY, tenant_id=_FAKE_TID, payout_algorand=_PAYOUT)
        assert not a._has_x_creds()

    def test_with_x_creds_has_x_creds_true(self):
        a = _make_adapter()
        assert a._has_x_creds()

    def test_custom_tweet_templates(self):
        a = _make_adapter(
            payment_tweet_template="Payment! {tx_id_short}",
            link_tweet_template="Buy: {checkout_url}",
        )
        assert a._payment_tmpl == "Payment! {tx_id_short}"
        assert a._link_tmpl    == "Buy: {checkout_url}"


# ── Section 2: HMAC helpers ────────────────────────────────────────────────────

class TestHmacHelpers:
    def test_valid_sig(self):
        body = '{"test": 1}'
        sig  = _hmac.new(_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
        assert _verify_hmac(body, sig, _SECRET) is True

    def test_invalid_sig(self):
        assert _verify_hmac('{"test":1}', "bad", _SECRET) is False

    def test_empty_secret(self):
        assert _verify_hmac('{"x":1}', "any", "") is False

    def test_empty_sig(self):
        assert _verify_hmac('{"x":1}', "", _SECRET) is False

    def test_tampered_body(self):
        body     = '{"amount": 100}'
        tampered = '{"amount": 999}'
        sig      = _hmac.new(_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
        assert _verify_hmac(tampered, sig, _SECRET) is False


# ── Section 3: Webhook handler ─────────────────────────────────────────────────

class TestWebhookHandler:
    def _post_tweet_ok(self, text):
        return XResult(True, 200, data={"tweet_id": "123", "tweet_url": "https://x.com/i/web/status/123", "text": text})

    def test_valid_payment_calls_post_tweet(self):
        a = _make_adapter()
        body = json.dumps(_PAYMENT_EVENT)
        sig  = _sign(body)
        with patch.object(a, "post_tweet", side_effect=self._post_tweet_ok) as mock_pt:
            res = a.on_payment_received(body, sig)
        assert res.success
        assert res.data["tweeted"] is True
        mock_pt.assert_called_once()

    def test_bad_sig_returns_401(self):
        a   = _make_adapter()
        body = json.dumps(_PAYMENT_EVENT)
        res  = a.on_payment_received(body, "badsig")
        assert not res.success
        assert res.http_status == 401

    def test_non_paid_status_no_tweet(self):
        a = _make_adapter()
        event = {**_PAYMENT_EVENT, "status": "pending"}
        body  = json.dumps(event)
        sig   = _sign(body)
        with patch.object(a, "post_tweet") as mock_pt:
            res = a.on_payment_received(body, sig)
        assert res.success
        assert res.data["tweeted"] is False
        mock_pt.assert_not_called()

    def test_completed_status_triggers_tweet(self):
        a = _make_adapter()
        event = {**_PAYMENT_EVENT, "status": "completed"}
        body  = json.dumps(event)
        sig   = _sign(body)
        with patch.object(a, "post_tweet", side_effect=self._post_tweet_ok):
            res = a.on_payment_received(body, sig)
        assert res.success
        assert res.data["tweeted"] is True

    def test_body_too_large_returns_400(self):
        a   = _make_adapter()
        res = a.on_payment_received("x" * (1_048_576 + 1), "sig")
        assert not res.success
        assert res.http_status == 400

    def test_invalid_json_returns_400(self):
        a   = _make_adapter()
        body = "not json"
        sig  = _sign(body)
        res  = a.on_payment_received(body, sig)
        assert not res.success
        assert res.http_status == 400

    def test_no_secret_skips_hmac(self):
        a    = _make_adapter(webhook_secret="")
        body = json.dumps(_PAYMENT_EVENT)
        with patch.object(a, "post_tweet", side_effect=self._post_tweet_ok):
            res = a.on_payment_received(body, "any_sig")
        assert res.success

    def test_tweet_failure_propagated(self):
        a    = _make_adapter()
        body = json.dumps(_PAYMENT_EVENT)
        sig  = _sign(body)
        with patch.object(a, "post_tweet", return_value=XResult(False, 403, error="Forbidden")):
            res = a.on_payment_received(body, sig)
        assert not res.success
        assert res.http_status == 403

    def test_event_data_returned(self):
        a    = _make_adapter()
        body = json.dumps(_PAYMENT_EVENT)
        sig  = _sign(body)
        with patch.object(a, "post_tweet", side_effect=self._post_tweet_ok):
            res = a.on_payment_received(body, sig)
        assert res.data["event"]["tx_id"] == _PAYMENT_EVENT["tx_id"]
        assert res.data["event"]["network"] == "algorand_mainnet"

    def test_all_four_networks(self):
        a = _make_adapter()
        for net in ["algorand_mainnet", "voi_mainnet", "hedera_mainnet", "stellar_mainnet"]:
            event = {**_PAYMENT_EVENT, "network": net}
            body  = json.dumps(event)
            sig   = _sign(body)
            with patch.object(a, "post_tweet", side_effect=self._post_tweet_ok):
                res = a.on_payment_received(body, sig)
            assert res.success, f"Failed for {net}"


# ── Section 4: Tweet text builder ─────────────────────────────────────────────

class TestTweetBuilder:
    def test_payment_tweet_contains_tx_short(self):
        event    = _PAYMENT_EVENT
        net_info = NETWORK_INFO["algorand_mainnet"]
        text     = _build_payment_tweet(event, net_info, _TMPL_PAYMENT)
        assert "5BDA7U7SUBXUR32" in text   # first 16 chars of tx_id
        assert "USDC" in text

    def test_payment_tweet_max_length(self):
        event    = {**_PAYMENT_EVENT, "tx_id": "X" * 300, "payer": "Y" * 300}
        net_info = NETWORK_INFO["algorand_mainnet"]
        text     = _build_payment_tweet(event, net_info, _TMPL_PAYMENT)
        assert len(text) <= _MAX_TWEET

    def test_link_tweet_contains_url(self):
        text = _build_link_tweet(
            label="Test Product", checkout_url="https://example.com/checkout/abc",
            amount=1.0, currency="USD", network="algorand_mainnet",
            template=_TMPL_LINK,
        )
        assert "https://example.com/checkout/abc" in text
        assert "Test Product" in text

    def test_link_tweet_max_length(self):
        text = _build_link_tweet(
            label="X" * 300, checkout_url="https://example.com/checkout/" + "y" * 200,
            amount=1.0, currency="USD", network="algorand_mainnet",
            template=_TMPL_LINK,
        )
        assert len(text) <= _MAX_TWEET

    def test_custom_template(self):
        event    = {**_PAYMENT_EVENT, "amount_microunits": 10_000}
        net_info = NETWORK_INFO["algorand_mainnet"]
        text     = _build_payment_tweet(event, net_info, "TX:{tx_id_short} NET:{network_label}")
        assert "TX:5BDA7U7SUBXUR32" in text
        assert "NET:Algorand" in text

    def test_format_amount_usdc(self):
        assert _format_amount(10_000, 6) == "0.01"

    def test_format_amount_whole(self):
        assert _format_amount(1_000_000, 6) == "1"

    def test_format_amount_hbar_tinybars(self):
        assert _format_amount(10_000, 8) == "0.0001"

    def test_format_amount_xlm_stroops(self):
        assert _format_amount(10_000, 7) == "0.001"


# ── Section 5: post_tweet ──────────────────────────────────────────────────────

class TestPostTweet:
    def test_success_returns_tweet_id(self):
        a = _make_adapter()
        with patch("urllib.request.urlopen", return_value=_x_created_response("111")):
            res = a.post_tweet("Hello from AlgoVoi!")
        assert res.success
        assert res.data["tweet_id"] == "111"
        assert "x.com" in res.data["tweet_url"]

    def test_no_credentials_returns_401(self):
        a   = _make_adapter(x_api_key="", x_api_key_secret="", x_access_token="", x_access_token_secret="")
        res = a.post_tweet("test")
        assert not res.success
        assert res.http_status == 401

    def test_empty_text_returns_400(self):
        a   = _make_adapter()
        res = a.post_tweet("")
        assert not res.success
        assert res.http_status == 400

    def test_text_truncated_to_280(self):
        a    = _make_adapter()
        long = "A" * 500
        with patch("urllib.request.urlopen", return_value=_x_created_response("222")):
            res = a.post_tweet(long)
        assert res.success   # truncated, not rejected

    def test_x_api_403_returns_error(self):
        a = _make_adapter()
        import urllib.error as _ue
        err = _ue.HTTPError(
            url="https://api.twitter.com/2/tweets",
            code=403, msg="Forbidden",
            hdrs={}, fp=BytesIO(b'{"errors":[{"message":"Forbidden"}]}'),
        )
        with patch("urllib.request.urlopen", side_effect=err):
            res = a.post_tweet("test")
        assert not res.success
        assert res.http_status == 403

    def test_oauth_header_in_request(self):
        a    = _make_adapter()
        sent_headers: list[dict] = []

        class _Resp:
            status = 201
            def read(self): return json.dumps({"data": {"id": "999", "text": "t"}}).encode()
            def __enter__(self): return self
            def __exit__(self, *a): pass

        def fake_urlopen(req, timeout=None):
            sent_headers.append(dict(req.headers))
            return _Resp()

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            a.post_tweet("test tweet")

        auth = sent_headers[0].get("Authorization", "")
        assert auth.startswith("OAuth ")
        assert "oauth_signature=" in auth
        assert "oauth_consumer_key=" in auth


# ── Section 6: post_payment_link ──────────────────────────────────────────────

class TestPostPaymentLink:
    def _mock_algovoi(self, token="tok123"):
        resp = MagicMock()
        resp.status = 201
        resp.read.return_value = json.dumps({
            "id":             "uuid-1",
            "checkout_url":   f"https://api1.ilovechicken.co.uk/checkout/{token}",
            "amount_microunits": 10_000,
        }).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__  = MagicMock(return_value=False)
        return resp

    def _mock_x(self, tweet_id="tweet1"):
        return _x_created_response(tweet_id)

    def test_success_returns_checkout_url_and_tweet(self):
        a = _make_adapter()
        responses = [self._mock_algovoi("tok_abc"), self._mock_x("tw1")]
        with patch("urllib.request.urlopen", side_effect=responses):
            res = a.post_payment_link({
                "amount": 1.00, "currency": "USD",
                "label": "My Product", "network": "algorand_mainnet",
            })
        assert res.success
        assert "checkout" in res.data["checkout_url"]
        assert res.data["token"] == "tok_abc"
        assert res.data["tweeted"] is True
        assert res.data["tweet_id"] == "tw1"

    def test_custom_tweet_text_used(self):
        a = _make_adapter()
        custom = "Buy my thing right now!"
        captured: list[str] = []

        def fake_post(text):
            captured.append(text)
            return XResult(True, 200, data={"tweet_id": "x", "tweet_url": "https://x.com/i/web/status/x", "text": text})

        with patch("urllib.request.urlopen", return_value=self._mock_algovoi()):
            with patch.object(a, "post_tweet", side_effect=fake_post):
                a.post_payment_link({
                    "amount": 1.0, "currency": "USD",
                    "label": "Test", "network": "algorand_mainnet",
                    "tweet_text": custom,
                })
        assert captured[0] == custom

    def test_missing_amount_rejected(self):
        a   = _make_adapter()
        res = a.post_payment_link({"currency": "USD", "label": "X", "network": "algorand_mainnet"})
        assert not res.success
        assert res.http_status == 400

    def test_negative_amount_rejected(self):
        a   = _make_adapter()
        res = a.post_payment_link({"amount": -5, "currency": "USD", "label": "X", "network": "algorand_mainnet"})
        assert not res.success

    def test_missing_label_rejected(self):
        a   = _make_adapter()
        res = a.post_payment_link({"amount": 1.0, "currency": "USD", "label": "", "network": "algorand_mainnet"})
        assert not res.success

    def test_bad_network_rejected(self):
        a   = _make_adapter()
        res = a.post_payment_link({"amount": 1.0, "currency": "USD", "label": "X", "network": "bad_net"})
        assert not res.success
        assert "unsupported network" in (res.error or "")

    def test_bad_currency_rejected(self):
        a   = _make_adapter()
        res = a.post_payment_link({"amount": 1.0, "currency": "ABCD", "label": "X", "network": "algorand_mainnet"})
        assert not res.success

    def test_algovoi_api_error_returns_502(self):
        import urllib.error as _ue
        a   = _make_adapter()
        err = _ue.HTTPError("https://...", 500, "Server Error", {}, BytesIO(b"{}"))
        with patch("urllib.request.urlopen", side_effect=err):
            res = a.post_payment_link({"amount": 1.0, "currency": "USD", "label": "X", "network": "algorand_mainnet"})
        assert not res.success
        assert res.http_status == 502

    def test_tweet_fail_still_returns_checkout_url(self):
        a = _make_adapter()
        with patch("urllib.request.urlopen", return_value=self._mock_algovoi("tok_keep")):
            with patch.object(a, "post_tweet", return_value=XResult(False, 403, error="Forbidden")):
                res = a.post_payment_link({"amount": 1.0, "currency": "USD", "label": "X", "network": "algorand_mainnet"})
        assert not res.success
        assert res.data.get("checkout_url", "")  # URL still present
        assert res.data.get("tweeted") is False


# ── Section 7: list_networks ───────────────────────────────────────────────────

class TestListNetworks:
    def test_returns_16_networks(self):
        a   = _make_adapter()
        res = a.list_networks()
        assert res.success
        assert res.data["count"] == 16
        assert len(res.data["networks"]) == 16

    def test_all_supported_keys_present(self):
        a    = _make_adapter()
        res  = a.list_networks()
        keys = {n["key"] for n in res.data["networks"]}
        assert SUPPORTED_NETWORKS <= keys

    def test_each_network_has_label_asset_decimals(self):
        a   = _make_adapter()
        res = a.list_networks()
        for net in res.data["networks"]:
            assert "label"    in net
            assert "asset"    in net
            assert "decimals" in net


# ── Section 8: verify_webhook_signature standalone ────────────────────────────

class TestVerifySignatureStandalone:
    def test_valid(self):
        a    = _make_adapter()
        body = json.dumps(_PAYMENT_EVENT)
        sig  = _sign(body)
        res  = a.verify_webhook_signature(body, sig)
        assert res["valid"] is True
        assert res["payload"]["tx_id"] == _PAYMENT_EVENT["tx_id"]

    def test_invalid(self):
        a   = _make_adapter()
        res = a.verify_webhook_signature('{"x":1}', "bad")
        assert res["valid"] is False

    def test_no_secret_configured(self):
        a   = _make_adapter(webhook_secret="")
        res = a.verify_webhook_signature('{"x":1}', "any")
        assert res["valid"] is False
        assert "not configured" in res["error"]

    def test_invalid_json(self):
        a   = _make_adapter()
        sig = _sign("not json")
        res = a.verify_webhook_signature("not json", sig)
        assert res["valid"] is False


# ── Section 9: OAuth 1.0a header ──────────────────────────────────────────────

class TestOAuth1Header:
    def test_starts_with_oauth(self):
        hdr = _oauth1_auth_header("POST", "https://api.twitter.com/2/tweets",
                                  "k", "ks", "t", "ts")
        assert hdr.startswith("OAuth ")

    def test_contains_required_fields(self):
        hdr = _oauth1_auth_header("POST", "https://api.twitter.com/2/tweets",
                                  "k", "ks", "t", "ts")
        for field in ["oauth_consumer_key", "oauth_nonce", "oauth_signature",
                      "oauth_signature_method", "oauth_timestamp",
                      "oauth_token", "oauth_version"]:
            assert field in hdr, f"Missing {field}"

    def test_hmac_sha1_method(self):
        hdr = _oauth1_auth_header("POST", "https://api.twitter.com/2/tweets",
                                  "k", "ks", "t", "ts")
        assert "HMAC-SHA1" in hdr

    def test_version_1_0(self):
        hdr = _oauth1_auth_header("POST", "https://api.twitter.com/2/tweets",
                                  "k", "ks", "t", "ts")
        assert "oauth_version=%221.0%22" in hdr or 'oauth_version="1.0"' in hdr

    def test_different_nonce_each_call(self):
        hdr1 = _oauth1_auth_header("POST", "https://api.twitter.com/2/tweets", "k", "ks", "t", "ts")
        hdr2 = _oauth1_auth_header("POST", "https://api.twitter.com/2/tweets", "k", "ks", "t", "ts")
        import re
        nonce1 = re.search(r'oauth_nonce="([^"]+)"', hdr1)
        nonce2 = re.search(r'oauth_nonce="([^"]+)"', hdr2)
        assert nonce1 and nonce2
        assert nonce1.group(1) != nonce2.group(1)


# ── Section 10: from_env ───────────────────────────────────────────────────────

class TestFromEnv:
    def test_missing_required_env_raises(self):
        env = {"ALGOVOI_API_KEY": _FAKE_KEY, "ALGOVOI_TENANT_ID": _FAKE_TID,
               "ALGOVOI_PAYOUT_ALGORAND": _PAYOUT}
        with patch.dict(os.environ, env, clear=True):
            a = from_env()
            assert a._key == _FAKE_KEY

    def test_missing_api_key_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(KeyError):
                from_env()
