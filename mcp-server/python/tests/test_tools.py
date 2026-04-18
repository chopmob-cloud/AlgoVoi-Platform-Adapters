"""
Unit tests for the 8 AlgoVoi MCP tools plus the new hardening modules
(schemas, redact, audit, idempotency, MCP_ENABLED_TOOLS filter).

All HTTP calls are mocked — no network traffic.
"""

from __future__ import annotations

import base64
import hashlib
import hmac as _hmac
import json
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from algovoi_mcp import audit, redact, server
from algovoi_mcp.client import AlgoVoiClient
from algovoi_mcp.idempotency import IdempotencyCache
from algovoi_mcp.schemas import (
    CreatePaymentLinkInput,
    GenerateAp2MandateInput,
    GenerateMppChallengeInput,
    GenerateX402ChallengeInput,
    ListNetworksInput,
    PrepareExtensionPaymentInput,
    VerifyAp2PaymentInput,
    VerifyMppReceiptInput,
    VerifyPaymentInput,
    VerifyWebhookInput,
    VerifyX402ProofInput,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def make_client(**overrides) -> AlgoVoiClient:
    defaults = dict(
        api_base         = "https://api1.example.test",
        api_key          = "algv_test",
        tenant_id        = "tenant-test",
        payout_addresses = {
            "algorand_mainnet": "PAYOUT_ADDR_TEST",
            "voi_mainnet":      "PAYOUT_ADDR_TEST",
            "hedera_mainnet":   "PAYOUT_ADDR_TEST",
            "stellar_mainnet":  "PAYOUT_ADDR_TEST",
        },
    )
    defaults.update(overrides)
    c = AlgoVoiClient(**defaults)
    c._post                = MagicMock()          # type: ignore[attr-defined]
    c._get                 = MagicMock()          # type: ignore[attr-defined]
    c._post_raw            = MagicMock()          # type: ignore[attr-defined]
    c.verify_hosted_return = MagicMock(           # type: ignore[assignment]
        return_value={"paid": False, "status": "unknown", "raw": {}}
    )
    return c


# ── Tool schemas (3 tests) ────────────────────────────────────────────────────

class TestToolSchemas:
    def test_eight_tools(self):
        assert len(server.TOOL_SCHEMAS) == 11

    def test_every_schema_shape(self):
        for t in server.TOOL_SCHEMAS:
            assert isinstance(t["name"], str)
            assert len(t["description"]) > 20
            assert t["inputSchema"]["type"] == "object"
            # §4.1 — MCP-wire JSON Schema also forbids extras
            assert t["inputSchema"].get("additionalProperties") is False

    def test_names_unique(self):
        names = [t["name"] for t in server.TOOL_SCHEMAS]
        assert len(set(names)) == len(names)


# ── Pydantic strict validation (7 tests) ──────────────────────────────────────

class TestPydanticStrict:
    def test_create_rejects_extra_field(self):
        with pytest.raises(ValidationError):
            CreatePaymentLinkInput(
                amount=1, currency="USD", label="x",
                network="algorand_mainnet", bogus="field",  # type: ignore[call-arg]
            )

    def test_create_rejects_string_amount(self):
        # strict mode forbids int/float coercion from string
        with pytest.raises(ValidationError):
            CreatePaymentLinkInput(
                amount="5.00", currency="USD", label="x",           # type: ignore[arg-type]
                network="algorand_mainnet",
            )

    def test_create_rejects_zero_amount(self):
        with pytest.raises(ValidationError):
            CreatePaymentLinkInput(
                amount=0, currency="USD", label="x",
                network="algorand_mainnet",
            )

    def test_create_rejects_bad_network(self):
        with pytest.raises(ValidationError):
            CreatePaymentLinkInput(
                amount=1, currency="USD", label="x",
                network="solana_mainnet",                           # type: ignore[arg-type]
            )

    def test_idempotency_key_length_bounds(self):
        with pytest.raises(ValidationError):
            CreatePaymentLinkInput(
                amount=1, currency="USD", label="x",
                network="algorand_mainnet",
                idempotency_key="tooshort",
            )
        # valid 16-char key passes
        CreatePaymentLinkInput(
            amount=1, currency="USD", label="x",
            network="algorand_mainnet",
            idempotency_key="a" * 16,
        )

    def test_verify_token_length(self):
        with pytest.raises(ValidationError):
            VerifyPaymentInput(token="x" * 500)

    def test_generate_mpp_negative_amount(self):
        with pytest.raises(ValidationError):
            GenerateMppChallengeInput(resource_id="kb", amount_microunits=-1)


# ── redact (6 tests) ──────────────────────────────────────────────────────────

class TestRedact:
    def test_redacts_mnemonic(self):
        assert redact.scrub({"mnemonic": "abandon abandon..."})["mnemonic"] == "[REDACTED]"

    def test_redacts_api_key(self):
        assert redact.scrub({"api_key": "algv_123"})["api_key"] == "[REDACTED]"

    def test_case_insensitive(self):
        assert redact.scrub({"Private_Key": "0x..."})["Private_Key"] == "[REDACTED]"

    def test_preserves_checkout_token(self):
        # Our `token` field is a public checkout ID — must NOT be redacted
        out = redact.scrub({"token": "abc123", "checkout_url": "https://x/checkout/abc123"})
        assert out["token"] == "abc123"
        assert out["checkout_url"] == "https://x/checkout/abc123"

    def test_truncates_long_strings(self):
        long = "x" * 1000
        out = redact.scrub({"memo": long})
        assert len(out["memo"]) < 600
        assert "[truncated" in out["memo"]

    def test_recurses_into_nested(self):
        src = {"outer": {"secret": "s", "list": [{"password": "p"}]}}
        out = redact.scrub(src)
        assert out["outer"]["secret"] == "[REDACTED]"
        assert out["outer"]["list"][0]["password"] == "[REDACTED]"


# ── audit (3 tests) ───────────────────────────────────────────────────────────

class TestAudit:
    def test_log_call_writes_json(self, capsys):
        audit.log_call(
            tool_name="create_payment_link",
            args={"amount": 5, "currency": "USD"},
            status="ok",
            duration_ms=12.3,
        )
        err = capsys.readouterr().err.strip()
        entry = json.loads(err.splitlines()[-1])
        assert entry["tool_name"]   == "create_payment_link"
        assert entry["status"]      == "ok"
        assert entry["duration_ms"] == 12.3
        assert "trace_id" in entry
        assert len(entry["args_hash"]) == 16

    def test_log_call_hashes_not_raw(self, capsys):
        audit.log_call(
            tool_name="x",
            args={"api_key": "algv_supersecret"},
            status="ok",
            duration_ms=0,
        )
        err = capsys.readouterr().err
        assert "algv_supersecret" not in err

    def test_log_call_includes_error_code(self, capsys):
        audit.log_call(
            tool_name="x", args={}, status="rejected",
            duration_ms=0, error_code="ValidationError",
        )
        err = capsys.readouterr().err.strip()
        entry = json.loads(err.splitlines()[-1])
        assert entry["error_code"] == "ValidationError"


# ── idempotency cache (3 tests) ───────────────────────────────────────────────

class TestIdempotency:
    def test_set_get(self):
        c = IdempotencyCache()
        c.set("k", {"result": 1})
        assert c.get("k") == {"result": 1}

    def test_missing_returns_none(self):
        assert IdempotencyCache().get("missing") is None

    def test_ttl_expires(self, monkeypatch):
        c = IdempotencyCache(ttl_seconds=1)
        c.set("k", "value")
        import algovoi_mcp.idempotency as mod
        real = mod.monotonic
        monkeypatch.setattr(mod, "monotonic", lambda: real() + 10)
        assert c.get("k") is None


# ── create_payment_link (6 tests) ─────────────────────────────────────────────

class TestCreatePaymentLink:
    def _ok_link(self):
        return {
            "checkout_url":      "https://api1.example.test/checkout/abc123",
            "chain":             "algorand-mainnet",
            "amount_microunits": 5_000_000,
        }

    def test_happy_path(self):
        c = make_client()
        c._post.return_value = self._ok_link()
        args = CreatePaymentLinkInput(
            amount=5, currency="usd", label="Order #1", network="algorand_mainnet",
        )
        out = server.tool_create_payment_link(c, args)
        assert out["token"]             == "abc123"
        assert out["chain"]             == "algorand-mainnet"
        assert out["amount_microunits"] == 5_000_000
        assert out["amount_display"]    == "5.00 USD"

    def test_invalid_network_rejected_by_schema(self):
        with pytest.raises(ValidationError):
            CreatePaymentLinkInput(
                amount=5, currency="USD", label="x",
                network="eth_mainnet",                              # type: ignore[arg-type]
            )

    def test_non_positive_amount_rejected_by_schema(self):
        with pytest.raises(ValidationError):
            CreatePaymentLinkInput(
                amount=0, currency="USD", label="x",
                network="algorand_mainnet",
            )

    def test_redirect_url_passed(self):
        c = make_client()
        c._post.return_value = self._ok_link()
        args = CreatePaymentLinkInput(
            amount=5, currency="USD", label="x",
            network="algorand_mainnet",
            redirect_url="https://shop.example.com/thanks",
        )
        server.tool_create_payment_link(c, args)
        sent = c._post.call_args[0][1]
        assert sent["redirect_url"] == "https://shop.example.com/thanks"

    def test_http_redirect_url_rejected(self):
        c = make_client()
        c._post.return_value = self._ok_link()
        args = CreatePaymentLinkInput(
            amount=1, currency="USD", label="x",
            network="algorand_mainnet",
            redirect_url="http://shop.example.com/thanks",
        )
        with pytest.raises(ValueError, match="https://"):
            server.tool_create_payment_link(c, args)

    def test_idempotency_caches_result(self):
        c = make_client()
        c._post.return_value = self._ok_link()
        args = CreatePaymentLinkInput(
            amount=5, currency="USD", label="x",
            network="algorand_mainnet",
            idempotency_key="test_key_" + "x" * 8,
        )
        first  = server.tool_create_payment_link(c, args)
        second = server.tool_create_payment_link(c, args)
        assert first == second
        # HTTP only hit once
        assert c._post.call_count == 1


# ── verify_payment (4 tests) ──────────────────────────────────────────────────

class TestVerifyPayment:
    def test_without_tx_id_paid(self):
        c = make_client()
        c.verify_hosted_return = MagicMock(  # type: ignore[assignment]
            return_value={"paid": True, "status": "paid", "raw": {}}
        )
        out = server.tool_verify_payment(c, VerifyPaymentInput(token="abc123"))
        assert out["paid"] is True
        assert out["status"] == "paid"

    def test_without_tx_id_unpaid(self):
        c = make_client()
        c.verify_hosted_return = MagicMock(  # type: ignore[assignment]
            return_value={"paid": False, "status": "pending", "raw": {}}
        )
        out = server.tool_verify_payment(c, VerifyPaymentInput(token="abc123"))
        assert out["paid"] is False

    def test_with_tx_id_verified(self):
        c = make_client()
        c.verify_extension_payment = MagicMock(return_value={"success": True})  # type: ignore[assignment]
        out = server.tool_verify_payment(c, VerifyPaymentInput(token="abc", tx_id="TX1"))
        assert out["paid"] is True
        assert out["status"] == "verified"

    def test_oversized_token_rejected_by_schema(self):
        with pytest.raises(ValidationError):
            VerifyPaymentInput(token="x" * 500)


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
            c,
            PrepareExtensionPaymentInput(
                amount=0.1, currency="USD", label="x", network="algorand_mainnet",
            ),
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
            c,
            PrepareExtensionPaymentInput(
                amount=1, currency="USD", label="x", network="voi_mainnet",
            ),
        )
        assert out["ticker"] == "aUSDC"

    def test_hedera_rejected_by_schema(self):
        with pytest.raises(ValidationError):
            PrepareExtensionPaymentInput(
                amount=1, currency="USD", label="x",
                network="hedera_mainnet",                           # type: ignore[arg-type]
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
        out  = server.tool_verify_webhook(
            self.SECRET, VerifyWebhookInput(raw_body=body, signature=sig)
        )
        assert out["valid"] is True
        assert out["payload"] == {"order_id": "1", "status": "paid"}

    def test_wrong_signature(self):
        out = server.tool_verify_webhook(
            self.SECRET,
            VerifyWebhookInput(raw_body="{}", signature="AAAA"),
        )
        assert out["valid"] is False
        assert "mismatch" in out["error"]

    def test_missing_secret(self):
        out = server.tool_verify_webhook(
            None, VerifyWebhookInput(raw_body="{}", signature="x"),
        )
        assert out["valid"] is False
        assert "webhook_secret not configured" in out["error"]

    def test_empty_signature_rejected_by_schema(self):
        with pytest.raises(ValidationError):
            VerifyWebhookInput(raw_body="{}", signature="")

    def test_oversized_body_rejected_by_schema(self):
        big = "x" * 70_000
        with pytest.raises(ValidationError):
            VerifyWebhookInput(raw_body=big, signature="x")

    def test_non_json_body_after_valid_sig(self):
        body = "not-json"
        sig  = _sign(self.SECRET, body)
        out  = server.tool_verify_webhook(
            self.SECRET, VerifyWebhookInput(raw_body=body, signature=sig)
        )
        assert out["valid"] is False
        assert "valid JSON" in out["error"]


# ── list_networks (2 tests) ───────────────────────────────────────────────────

class TestListNetworks:
    def test_sixteen_networks(self):
        out = server.tool_list_networks(ListNetworksInput())
        assert len(out["networks"]) == 16

    def test_caip2_and_asset_id(self):
        out = server.tool_list_networks(ListNetworksInput())
        algo = next(n for n in out["networks"] if n["key"] == "algorand_mainnet")
        assert algo["caip2"]    == "algorand:mainnet"
        assert algo["asset_id"] == "31566704"


# ── generate_mpp_challenge (5 tests) ──────────────────────────────────────────

class TestGenerateMppChallenge:
    def test_defaults_to_algorand(self):
        c   = make_client()
        out = server.tool_generate_mpp_challenge(
            c, GenerateMppChallengeInput(resource_id="kb", amount_microunits=10_000)
        )
        assert out["status_code"]           == 402
        assert len(out["accepts"])          == 1
        assert out["accepts"][0]["network"] == "algorand:mainnet"

    def test_www_authenticate_shape(self):
        c   = make_client()
        out = server.tool_generate_mpp_challenge(
            c, GenerateMppChallengeInput(resource_id="kb", amount_microunits=10_000)
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
            GenerateMppChallengeInput(
                resource_id="kb",
                amount_microunits=10_000,
                networks=["algorand_mainnet", "hedera_mainnet"],
            ),
        )
        assert len(out["accepts"]) == 2

    def test_unknown_network_rejected_by_schema(self):
        with pytest.raises(ValidationError):
            GenerateMppChallengeInput(
                resource_id="kb",
                amount_microunits=10_000,
                networks=["solana_mainnet"],                        # type: ignore[list-item]
            )

    def test_receiver_is_payout_address(self):
        c   = make_client()
        out = server.tool_generate_mpp_challenge(
            c, GenerateMppChallengeInput(resource_id="kb", amount_microunits=10_000)
        )
        assert out["accepts"][0]["receiver"] == "PAYOUT_ADDR_TEST"


# ── verify_mpp_receipt (3 tests) ──────────────────────────────────────────────

class TestVerifyMppReceipt:
    def test_verified(self):
        c = make_client()
        c.verify_mpp_receipt = MagicMock(                # type: ignore[assignment]
            return_value={"verified": True, "tx_id": "TX1"}
        )
        out = server.tool_verify_mpp_receipt(
            c, VerifyMppReceiptInput(resource_id="kb", tx_id="TX1", network="algorand_mainnet")
        )
        assert out["verified"] is True

    def test_missing_tx_id_rejected_by_schema(self):
        with pytest.raises(ValidationError):
            VerifyMppReceiptInput(resource_id="kb", tx_id="", network="algorand_mainnet")

    def test_unknown_network_rejected_by_schema(self):
        with pytest.raises(ValidationError):
            VerifyMppReceiptInput(
                resource_id="kb", tx_id="TX1", network="eth_mainnet"  # type: ignore[arg-type]
            )


# ── verify_x402_proof (3 tests) ───────────────────────────────────────────────

class TestVerifyX402Proof:
    def test_verified_passthrough(self):
        import base64, json
        c = make_client()
        c.verify_x402_proof = MagicMock(return_value={"verified": True})  # type: ignore[assignment]
        proof = base64.b64encode(json.dumps({"tx_id": "TX1"}).encode()).decode()
        out = server.tool_verify_x402_proof(
            c, VerifyX402ProofInput(proof=proof, network="algorand_mainnet")
        )
        assert out["verified"] is True

    def test_empty_proof_rejected_by_schema(self):
        with pytest.raises(ValidationError):
            VerifyX402ProofInput(proof="", network="algorand_mainnet")

    def test_bad_network_rejected_by_schema(self):
        with pytest.raises(ValidationError):
            VerifyX402ProofInput(proof="abc", network="bitcoin")      # type: ignore[arg-type]


# ── Dispatcher & MCP_ENABLED_TOOLS (5 tests) ──────────────────────────────────

class TestDispatcher:
    def test_unknown_tool(self):
        c = make_client()
        with pytest.raises(ValueError, match="unknown tool"):
            server._dispatch(c, None, "nonexistent_tool", {})

    def test_list_networks_via_dispatch(self):
        c = make_client()
        out = server._dispatch(c, None, "list_networks", {})
        assert len(out["networks"]) == 16

    def test_dispatch_redacts(self):
        c = make_client()
        c.create_payment_link = MagicMock(return_value={                 # type: ignore[assignment]
            "checkout_url":      "https://api1.example.test/checkout/a",
            "chain":             "algorand-mainnet",
            "amount_microunits": 100,
            "api_key":           "algv_should_be_scrubbed",
        })
        out = server._dispatch(
            c, None, "create_payment_link",
            {"amount": 1, "currency": "USD", "label": "x", "network": "algorand_mainnet"},
        )
        # The tool function's return dict is whitelisted, so this leaked
        # field never reaches the output; scrub guarantees that even if it
        # did, it would be redacted.
        assert "api_key" not in out
        assert out["token"] == "a"

    def test_parse_enabled_tools_all(self):
        assert server._parse_enabled_tools(None) is None
        assert server._parse_enabled_tools("") is None

    def test_parse_enabled_tools_subset(self):
        out = server._parse_enabled_tools("create_payment_link, list_networks ,bogus_tool")
        assert out == {"create_payment_link", "list_networks"}


# ── build_server (2 tests) ────────────────────────────────────────────────────

class TestBuildServer:
    def test_all_tools_by_default(self):
        c = make_client()
        srv = server.build_server(c, None)
        assert srv is not None

    def test_enabled_subset_only(self):
        c = make_client()
        srv = server.build_server(c, None, enabled_tools={"list_networks"})
        assert srv is not None


# ── Client TLS 1.3 (1 test) ───────────────────────────────────────────────────

class TestClientTLS:
    def test_ssl_minimum_version_is_tlsv1_3(self):
        import ssl
        c = AlgoVoiClient(
            api_base         = "https://api1.example.test",
            api_key          = "k",
            tenant_id        = "t",
            payout_addresses = {"algorand_mainnet": "p"},
        )
        assert c._ssl_ctx.minimum_version == ssl.TLSVersion.TLSv1_3


# ── generate_x402_challenge (4 tests) ────────────────────────────────────────

class TestGenerateX402Challenge:
    def test_returns_402_with_header(self):
        c   = make_client()
        out = server.tool_generate_x402_challenge(
            c, GenerateX402ChallengeInput(resource="https://api.example.com/kb", amount_microunits=1_000_000)
        )
        assert out["status_code"] == 402
        assert "X-Payment-Required" in out["headers"]

    def test_header_is_valid_base64_json(self):
        import base64
        c   = make_client()
        out = server.tool_generate_x402_challenge(
            c, GenerateX402ChallengeInput(resource="https://api.example.com/kb", amount_microunits=500_000)
        )
        decoded = json.loads(base64.b64decode(out["headers"]["X-Payment-Required"]))
        assert decoded["version"]           == "1"
        assert decoded["payTo"]             == "PAYOUT_ADDR_TEST"
        assert decoded["maxAmountRequired"] == "500000"

    def test_defaults_to_algorand(self):
        c   = make_client()
        out = server.tool_generate_x402_challenge(
            c, GenerateX402ChallengeInput(resource="https://example.com/r", amount_microunits=100)
        )
        assert out["payload"]["networkId"] == "algorand:mainnet"

    def test_bad_amount_rejected_by_schema(self):
        with pytest.raises(ValidationError):
            GenerateX402ChallengeInput(resource="https://x.com/r", amount_microunits=0)


# ── generate_ap2_mandate (4 tests) ────────────────────────────────────────────

class TestGenerateAp2Mandate:
    def test_returns_mandate_id_and_b64(self):
        c   = make_client()
        out = server.tool_generate_ap2_mandate(
            c, GenerateAp2MandateInput(resource_id="task-42", amount_microunits=1_000_000)
        )
        assert len(out["mandate_id"])  == 16
        assert "mandate_b64"           in out
        assert out["mandate"]["type"]  == "PaymentMandate"

    def test_mandate_b64_decodes_correctly(self):
        import base64
        c   = make_client()
        out = server.tool_generate_ap2_mandate(
            c, GenerateAp2MandateInput(resource_id="task-42", amount_microunits=2_000_000)
        )
        mandate = json.loads(base64.b64decode(out["mandate_b64"]))
        assert mandate["payee"]["address"]  == "PAYOUT_ADDR_TEST"
        assert mandate["amount"]["value"]   == "2000000"
        assert mandate["protocol"]          == "algovoi-ap2/0.1"

    def test_payout_address_in_mandate(self):
        c   = make_client()
        out = server.tool_generate_ap2_mandate(
            c, GenerateAp2MandateInput(resource_id="r", amount_microunits=1_000_000)
        )
        assert out["mandate"]["payee"]["address"] == "PAYOUT_ADDR_TEST"

    def test_bad_amount_rejected_by_schema(self):
        with pytest.raises(ValidationError):
            GenerateAp2MandateInput(resource_id="r", amount_microunits=-1)


# ── verify_ap2_payment (3 tests) ──────────────────────────────────────────────

class TestVerifyAp2Payment:
    def test_verified(self):
        c = make_client()
        c.verify_ap2_payment = MagicMock(return_value={"verified": True})  # type: ignore[assignment]
        out = server.tool_verify_ap2_payment(
            c, VerifyAp2PaymentInput(mandate_id="a" * 16, tx_id="TX1", network="algorand_mainnet")
        )
        assert out["verified"] is True

    def test_empty_mandate_id_rejected_by_schema(self):
        with pytest.raises(ValidationError):
            VerifyAp2PaymentInput(mandate_id="", tx_id="TX1", network="algorand_mainnet")

    def test_bad_network_rejected_by_schema(self):
        with pytest.raises(ValidationError):
            VerifyAp2PaymentInput(mandate_id="a" * 16, tx_id="TX1", network="bitcoin")  # type: ignore[arg-type]
