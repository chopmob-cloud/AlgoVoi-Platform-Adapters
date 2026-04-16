"""
Unit tests for the 8 AlgoVoi MCP tools.

Mocks AlgoVoiClient's HTTP methods — no network calls.
"""

from __future__ import annotations

import base64
import hashlib
import hmac as _hmac
import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from algovoi_mcp import server
from algovoi_mcp.client import AlgoVoiClient
from algovoi_mcp.networks import NETWORKS


# ── helpers ───────────────────────────────────────────────────────────────────

def make_client(**overrides) -> AlgoVoiClient:
    defaults = dict(
        api_base       = "https://api1.example.test",
        api_key        = "algv_test",
        tenant_id      = "tenant-test",
        payout_address = "PAYOUT_ADDR_TEST",
    )
    defaults.update(overrides)
    c = AlgoVoiClient(**defaults)
    # Replace HTTP methods with mocks so tests never hit the network
    c._post               = MagicMock()
    c._get                = MagicMock()
    c._post_raw           = MagicMock()
    c.verify_hosted_return = MagicMock(  # type: ignore[assignment]
        return_value={"paid": False, "status": "unknown", "raw": {}}
    )
    return c


# ── Tool schemas (3 tests) ────────────────────────────────────────────────────

class TestToolSchemas:
    def test_eight_tools(self):
        assert len(server.TOOL_SCHEMAS) == 8

    def test_every_schema_shape(self):
        for t in server.TOOL_SCHEMAS:
            assert isinstance(t["name"], str)
            assert len(t["description"]) > 20
            assert t["inputSchema"]["type"] == "object"

    def test_names_unique(self):
        names = [t["name"] for t in server.TOOL_SCHEMAS]
        assert len(set(names)) == len(names)


# ── create_payment_link (5 tests) ─────────────────────────────────────────────

class TestCreatePaymentLink:
    def _ok_link(self):
        return {
            "checkout_url":       "https://api1.example.test/checkout/abc123",
            "chain":              "algorand-mainnet",
            "amount_microunits":  5_000_000,
        }

    def test_happy_path(self):
        c = make_client()
        c._post.return_value = self._ok_link()
        out = server.tool_create_payment_link(
            c, {"amount": 5, "currency": "usd", "label": "Order #1", "network": "algorand_mainnet"}
        )
        assert out["token"]             == "abc123"
        assert out["chain"]             == "algorand-mainnet"
        assert out["amount_microunits"] == 5_000_000
        assert out["amount_display"]    == "5.00 USD"

    def test_invalid_network_rejected(self):
        c = make_client()
        with pytest.raises(ValueError, match="network must be one of"):
            server.tool_create_payment_link(
                c, {"amount": 5, "currency": "USD", "label": "x", "network": "eth_mainnet"}
            )

    def test_non_positive_amount_rejected(self):
        c = make_client()
        c._post.return_value = self._ok_link()
        with pytest.raises(ValueError):
            server.tool_create_payment_link(
                c, {"amount": 0, "currency": "USD", "label": "x", "network": "algorand_mainnet"}
            )

    def test_redirect_url_passed(self):
        c = make_client()
        c._post.return_value = self._ok_link()
        server.tool_create_payment_link(
            c,
            {
                "amount": 5, "currency": "USD", "label": "x",
                "network": "algorand_mainnet",
                "redirect_url": "https://shop.example.com/thanks",
            },
        )
        sent = c._post.call_args[0][1]
        assert sent["redirect_url"] == "https://shop.example.com/thanks"

    def test_http_redirect_url_rejected(self):
        c = make_client()
        with pytest.raises(ValueError, match="https://"):
            server.tool_create_payment_link(
                c,
                {
                    "amount": 1, "currency": "USD", "label": "x",
                    "network": "algorand_mainnet",
                    "redirect_url": "http://shop.example.com/thanks",
                },
            )


# ── verify_payment (4 tests) ──────────────────────────────────────────────────

class TestVerifyPayment:
    def test_without_tx_id_paid(self):
        c = make_client()
        c.verify_hosted_return = MagicMock(  # type: ignore[assignment]
            return_value={"paid": True, "status": "paid", "raw": {}}
        )
        out = server.tool_verify_payment(c, {"token": "abc123"})
        assert out["paid"] is True
        assert out["status"] == "paid"

    def test_without_tx_id_unpaid(self):
        c = make_client()
        c.verify_hosted_return = MagicMock(  # type: ignore[assignment]
            return_value={"paid": False, "status": "pending", "raw": {}}
        )
        out = server.tool_verify_payment(c, {"token": "abc123"})
        assert out["paid"] is False

    def test_with_tx_id_verified(self):
        c = make_client()
        c.verify_extension_payment = MagicMock(return_value={"success": True})  # type: ignore[assignment]
        out = server.tool_verify_payment(c, {"token": "abc", "tx_id": "TX1"})
        assert out["paid"] is True
        assert out["status"] == "verified"

    def test_oversized_token_rejected(self):
        c = make_client()
        with pytest.raises(ValueError, match="token must be"):
            server.tool_verify_payment(c, {"token": "x" * 500})


# ── prepare_extension_payment (3 tests) ───────────────────────────────────────

class TestPrepareExtensionPayment:
    def test_algorand_returns_usdc(self):
        c = make_client()
        c._post.return_value = {
            "checkout_url":      "https://api1.example.test/checkout/ext1",
            "chain":             "algorand-mainnet",
            "amount_microunits": 100_000,
        }
        out = server.tool_prepare_extension_payment(
            c, {"amount": 0.1, "currency": "USD", "label": "x", "network": "algorand_mainnet"}
        )
        assert out["token"]    == "ext1"
        assert out["asset_id"] == "31566704"
        assert out["ticker"]   == "USDC"

    def test_voi_returns_ausdc(self):
        c = make_client()
        c._post.return_value = {
            "checkout_url":      "https://api1.example.test/checkout/voi1",
            "chain":             "voi-mainnet",
            "amount_microunits": 1_000_000,
        }
        out = server.tool_prepare_extension_payment(
            c, {"amount": 1, "currency": "USD", "label": "x", "network": "voi_mainnet"}
        )
        assert out["ticker"] == "aUSDC"

    def test_hedera_rejected(self):
        c = make_client()
        with pytest.raises(ValueError, match="extension payments require"):
            server.tool_prepare_extension_payment(
                c, {"amount": 1, "currency": "USD", "label": "x", "network": "hedera_mainnet"}
            )


# ── verify_webhook (6 tests) ──────────────────────────────────────────────────

def _sign(secret: str, body: str) -> str:
    return base64.b64encode(
        _hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()
    ).decode()


class TestVerifyWebhook:
    SECRET = "whsec_test"

    def test_valid_signature(self):
        body = json.dumps({"order_id": "1", "status": "paid"})
        sig  = _sign(self.SECRET, body)
        out  = server.tool_verify_webhook(self.SECRET, {"raw_body": body, "signature": sig})
        assert out["valid"] is True
        assert out["payload"] == {"order_id": "1", "status": "paid"}

    def test_wrong_signature(self):
        out = server.tool_verify_webhook(
            self.SECRET, {"raw_body": "{}", "signature": "AAAA"}
        )
        assert out["valid"] is False
        assert "mismatch" in out["error"]

    def test_missing_secret(self):
        out = server.tool_verify_webhook(None, {"raw_body": "{}", "signature": "x"})
        assert out["valid"] is False
        assert "webhook_secret not configured" in out["error"]

    def test_empty_signature(self):
        out = server.tool_verify_webhook(self.SECRET, {"raw_body": "{}", "signature": ""})
        assert out["valid"] is False

    def test_oversized_body(self):
        big = "x" * 70_000
        sig = _sign(self.SECRET, big)
        out = server.tool_verify_webhook(self.SECRET, {"raw_body": big, "signature": sig})
        assert out["valid"] is False
        assert "64 KiB cap" in out["error"]

    def test_non_json_body_after_valid_sig(self):
        body = "not-json"
        sig  = _sign(self.SECRET, body)
        out  = server.tool_verify_webhook(self.SECRET, {"raw_body": body, "signature": sig})
        assert out["valid"] is False
        assert "valid JSON" in out["error"]


# ── list_networks (2 tests) ───────────────────────────────────────────────────

class TestListNetworks:
    def test_four_networks(self):
        out = server.tool_list_networks({})
        assert len(out["networks"]) == 4

    def test_caip2_and_asset_id(self):
        out = server.tool_list_networks({})
        algo = next(n for n in out["networks"] if n["key"] == "algorand_mainnet")
        assert algo["caip2"]    == "algorand:mainnet"
        assert algo["asset_id"] == "31566704"


# ── generate_mpp_challenge (5 tests) ──────────────────────────────────────────

class TestGenerateMppChallenge:
    def test_defaults_to_algorand(self):
        c   = make_client()
        out = server.tool_generate_mpp_challenge(
            c, {"resource_id": "kb", "amount_microunits": 10_000}
        )
        assert out["status_code"]          == 402
        assert len(out["accepts"])         == 1
        assert out["accepts"][0]["network"] == "algorand:mainnet"

    def test_www_authenticate_shape(self):
        c   = make_client()
        out = server.tool_generate_mpp_challenge(
            c, {"resource_id": "kb", "amount_microunits": 10_000}
        )
        h = out["headers"]["WWW-Authenticate"]
        assert h.startswith("Payment ")
        assert "realm=" in h
        assert 'intent="charge"' in h
        assert "id=" in h
        assert "expires=" in h
        assert "request=" in h

    def test_multi_network(self):
        c   = make_client()
        out = server.tool_generate_mpp_challenge(
            c,
            {
                "resource_id": "kb",
                "amount_microunits": 10_000,
                "networks": ["algorand_mainnet", "hedera_mainnet"],
            },
        )
        assert len(out["accepts"]) == 2

    def test_unknown_network_rejected(self):
        c = make_client()
        with pytest.raises(ValueError, match="unsupported network"):
            server.tool_generate_mpp_challenge(
                c,
                {
                    "resource_id": "kb",
                    "amount_microunits": 10_000,
                    "networks": ["solana_mainnet"],
                },
            )

    def test_receiver_is_payout_address(self):
        c   = make_client()
        out = server.tool_generate_mpp_challenge(
            c, {"resource_id": "kb", "amount_microunits": 10_000}
        )
        assert out["accepts"][0]["receiver"] == "PAYOUT_ADDR_TEST"


# ── verify_mpp_receipt (3 tests) ──────────────────────────────────────────────

class TestVerifyMppReceipt:
    def test_verified(self):
        c = make_client()
        c.verify_mpp_receipt = MagicMock(return_value={"verified": True, "tx_id": "TX1"})  # type: ignore[assignment]
        out = server.tool_verify_mpp_receipt(
            c, {"resource_id": "kb", "tx_id": "TX1", "network": "algorand_mainnet"}
        )
        assert out["verified"] is True

    def test_missing_tx_id(self):
        c = make_client()
        with pytest.raises(ValueError):
            server.tool_verify_mpp_receipt(
                c, {"resource_id": "kb", "tx_id": "", "network": "algorand_mainnet"}
            )

    def test_unknown_network(self):
        c = make_client()
        with pytest.raises(ValueError, match="unsupported network"):
            server.tool_verify_mpp_receipt(
                c, {"resource_id": "kb", "tx_id": "TX1", "network": "eth_mainnet"}
            )


# ── verify_x402_proof (3 tests) ───────────────────────────────────────────────

class TestVerifyX402Proof:
    def test_verified_passthrough(self):
        c = make_client()
        c.verify_x402_proof = MagicMock(return_value={"verified": True})  # type: ignore[assignment]
        out = server.tool_verify_x402_proof(
            c, {"proof": "abc", "network": "algorand_mainnet"}
        )
        assert out["verified"] is True

    def test_empty_proof_rejected(self):
        c = make_client()
        with pytest.raises(ValueError, match="proof is required"):
            server.tool_verify_x402_proof(
                c, {"proof": "", "network": "algorand_mainnet"}
            )

    def test_bad_network_rejected(self):
        c = make_client()
        with pytest.raises(ValueError, match="unsupported network"):
            server.tool_verify_x402_proof(c, {"proof": "abc", "network": "bitcoin"})


# ── Dispatcher (2 tests) ──────────────────────────────────────────────────────

class TestDispatcher:
    def test_unknown_tool(self):
        c = make_client()
        with pytest.raises(ValueError, match="unknown tool"):
            server._dispatch(c, None, "nonexistent_tool", {})

    def test_list_networks_via_dispatch(self):
        c   = make_client()
        out = server._dispatch(c, None, "list_networks", {})
        assert len(out["networks"]) == 4
