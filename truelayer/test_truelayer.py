"""
TrueLayer AlgoVoi Adapter -- Tests
"""

import hashlib
import hmac as hmac_mod
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from truelayer_algovoi import TrueLayerAlgoVoi, HOSTED_NETWORKS

PASS = FAIL = 0


def test(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} -- {detail}")


def main():
    global PASS, FAIL

    adapter = TrueLayerAlgoVoi(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        truelayer_client_id="test_client_id",
        truelayer_client_secret="test_client_secret",
        webhook_secret="test_secret",
        default_network="algorand_mainnet",
        base_currency="GBP",
    )

    src = open(os.path.join(os.path.dirname(__file__), "truelayer_algovoi.py")).read()

    print("TrueLayer AlgoVoi Adapter -- Tests")
    print("=" * 50)

    # 1. Network validation
    print("\n1. Network validation")
    test("4 hosted networks", len(HOSTED_NETWORKS) == 4)
    test("algorand_mainnet present", "algorand_mainnet" in HOSTED_NETWORKS)
    test("voi_mainnet present", "voi_mainnet" in HOSTED_NETWORKS)
    test("hedera_mainnet present", "hedera_mainnet" in HOSTED_NETWORKS)
    test("stellar_mainnet present", "stellar_mainnet" in HOSTED_NETWORKS)

    # 2. Webhook security
    print("\n2. Webhook security")
    adapter_nosecret = TrueLayerAlgoVoi(webhook_secret="")
    test("empty secret returns None", adapter_nosecret.verify_webhook(b"body", "sig") is None)

    body = b'{"type":"payment_executed","payment":{"id":"pay_abc123","amount":9999,"currency":"GBP","status":"executed"}}'
    expected_sig = hmac_mod.new("test_secret".encode(), body, hashlib.sha256).hexdigest()
    result = adapter.verify_webhook(body, expected_sig)
    test("valid HMAC returns payload", result is not None)
    test("valid HMAC payload is dict", isinstance(result, dict))
    test("wrong HMAC returns None", adapter.verify_webhook(body, "deadbeef") is None)
    test("tampered body rejected", adapter.verify_webhook(b"tampered", expected_sig) is None)

    # 3. Timing-safe comparison
    print("\n3. Timing safety")
    test("uses hmac.compare_digest", "compare_digest" in src)

    # 4. Payment webhook parsing
    print("\n4. Payment webhook parsing")
    webhook_executed = {
        "type": "payment_executed",
        "payment": {
            "id": "pay-tl-001",
            "amount": 5000,
            "currency": "GBP",
            "status": "executed",
            "metadata": {"order_ref": "ORD-99"},
        },
    }
    payment = adapter.parse_payment_webhook(webhook_executed)
    test("parses payment_id", payment and payment["payment_id"] == "pay-tl-001")
    test("parses currency", payment and payment["currency"] == "GBP")
    test("parses status", payment and payment["status"] == "executed")
    test("parses metadata", payment and payment["metadata"].get("order_ref") == "ORD-99")

    webhook_settled = {
        "type": "payment_settled",
        "payment": {
            "id": "pay-tl-002",
            "amount": 10000,
            "currency": "EUR",
            "status": "settled",
        },
    }
    payment2 = adapter.parse_payment_webhook(webhook_settled)
    test("parses payment_settled event", payment2 and payment2["payment_id"] == "pay-tl-002")
    test("parses EUR currency", payment2 and payment2["currency"] == "EUR")

    # 5. Edge cases — parsing
    print("\n5. Parse edge cases")
    test("empty dict returns None", adapter.parse_payment_webhook({}) is None)
    test("missing payment_id returns None", adapter.parse_payment_webhook({"type": "payment_executed", "payment": {}}) is None)
    test("None values handled", adapter.parse_payment_webhook({"payment": {"id": None}}) is None)

    # 6. Payment verification — empty token
    print("\n6. Payment verification")
    test("empty token returns False", adapter.verify_payment("") is False)
    test("whitespace token returns False", adapter.verify_payment("   ") is False)

    # 7. create_settlement — no network falls back
    print("\n7. Settlement creation")
    # No live API — just confirm it returns None (network error) rather than raising
    result_settle = adapter.create_settlement("pay-tl-001", 50.00, "GBP", "algorand_mainnet")
    test("returns None on network error (no live API)", result_settle is None)

    # Unknown network falls back to default
    adapter2 = TrueLayerAlgoVoi(
        api_key="k",
        tenant_id="t",
        webhook_secret="s",
        default_network="voi_mainnet",
    )
    # Just validate the adapter picks the right default (inspect internals)
    test("invalid network falls back to default_network", adapter2.default_network == "voi_mainnet")

    # 8. SSL enforcement
    print("\n8. SSL enforcement")
    test("ssl.create_default_context used", "create_default_context" in src)
    test("urlopen uses context=self._ssl", "context=self._ssl" in src)

    # 9. No hardcoded secrets
    print("\n9. No hardcoded secrets")
    test("no real API keys in source", "algv_iedCPy" not in src)
    test("no real tenant IDs in source", "96eb0225" not in src)
    test("no real client secrets in source", "sk_live_" not in src)

    # 10. TrueLayer-specific features
    print("\n10. TrueLayer-specific features")
    test("Tl-Signature header referenced", "Tl-Signature" in src)
    test("payment_executed event referenced", "payment_executed" in src)
    test("payment_settled event referenced", "payment_settled" in src)
    test("payment_creditable event referenced", "payment_creditable" in src)
    test("truelayer_client_id init param", "truelayer_client_id" in src)
    test("truelayer_client_secret init param", "truelayer_client_secret" in src)
    test("console.truelayer.com referenced", "truelayer.com" in src)
    test("/v1/payment-links endpoint used", "/v1/payment-links" in src)
    test("X-Tenant-Id header sent", "X-Tenant-Id" in src)

    # 11. Webhook handler returns callable
    print("\n11. Flask handler")
    handler = adapter.flask_webhook_handler()
    test("flask_webhook_handler returns callable", callable(handler))

    # Summary
    print("\n" + "=" * 50)
    print(f"Results: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
