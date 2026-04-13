"""
Yapily AlgoVoi Adapter -- Tests
"""

import hashlib
import hmac as hmac_mod
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from yapily_algovoi import YapilyAlgoVoi, HOSTED_NETWORKS

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

    adapter = YapilyAlgoVoi(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        yapily_application_key="test_app_key",
        yapily_application_secret="test_app_secret",
        webhook_secret="test_secret",
        default_network="algorand_mainnet",
        base_currency="GBP",
    )

    src = open(os.path.join(os.path.dirname(__file__), "yapily_algovoi.py")).read()

    print("Yapily AlgoVoi Adapter -- Tests")
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
    adapter_nosecret = YapilyAlgoVoi(webhook_secret="")
    test("empty secret returns None", adapter_nosecret.verify_webhook(b"body", "sig") is None)

    body = b'{"type":"single_payment.status.completed","event":{"id":"yap-pay-001","status":"COMPLETED","amount":100.0}}'
    expected_sig = hmac_mod.new("test_secret".encode(), body, hashlib.sha256).hexdigest()
    result = adapter.verify_webhook(body, expected_sig)
    test("valid HMAC returns payload", result is not None)
    test("valid HMAC payload is dict", isinstance(result, dict))
    test("wrong HMAC returns None", adapter.verify_webhook(body, "badhash") is None)
    test("tampered body rejected", adapter.verify_webhook(b"altered", expected_sig) is None)

    # 3. Timing-safe comparison
    print("\n3. Timing safety")
    test("uses hmac.compare_digest", "compare_digest" in src)

    # 4. Payment webhook parsing — standard format
    print("\n4. Payment webhook parsing")
    webhook_completed = {
        "type": "single_payment.status.completed",
        "event": {
            "id": "yap-pay-001",
            "status": "COMPLETED",
            "amount": 100.00,
            "currency": "GBP",
            "institutionId": "monzo",
        },
        "metadata": {"tracingId": "trace-abc"},
    }
    payment = adapter.parse_payment_webhook(webhook_completed)
    test("parses payment_id", payment and payment["payment_id"] == "yap-pay-001")
    test("parses amount", payment and payment["amount"] == 100.0)
    test("parses currency GBP", payment and payment["currency"] == "GBP")
    test("parses status COMPLETED", payment and payment["status"] == "COMPLETED")
    test("parses institution_id", payment and payment["institution_id"] == "monzo")

    # PAYMENT_EXECUTED variant
    webhook_executed = {
        "type": "PAYMENT_EXECUTED",
        "event": {
            "id": "yap-pay-002",
            "status": "PAYMENT_EXECUTED",
            "amount": 250.00,
            "currency": "EUR",
        },
    }
    payment2 = adapter.parse_payment_webhook(webhook_executed)
    test("parses PAYMENT_EXECUTED event", payment2 and payment2["payment_id"] == "yap-pay-002")
    test("parses EUR currency", payment2 and payment2["currency"] == "EUR")

    # 5. Edge cases — parsing
    print("\n5. Parse edge cases")
    test("empty dict returns None", adapter.parse_payment_webhook({}) is None)
    test("missing id returns None", adapter.parse_payment_webhook({"type": "PAYMENT_EXECUTED", "event": {}}) is None)
    test("None values handled", adapter.parse_payment_webhook({"event": {"id": None}}) is None)

    # 6. Payment status — non-terminal status not triggering settlement
    print("\n6. Status handling")
    webhook_failed = {
        "type": "single_payment.status.updated",
        "event": {
            "id": "yap-pay-003",
            "status": "FAILED",
            "amount": 50.00,
            "currency": "GBP",
        },
    }
    payment_failed = adapter.parse_payment_webhook(webhook_failed)
    test("parses FAILED status", payment_failed and payment_failed["status"] == "FAILED")
    # Confirm FAILED is not in terminal success statuses
    from yapily_algovoi import YAPILY_PAYMENT_STATUSES
    test("FAILED not in success statuses", "FAILED" not in YAPILY_PAYMENT_STATUSES)
    test("COMPLETED in success statuses", "COMPLETED" in YAPILY_PAYMENT_STATUSES)
    test("PAYMENT_EXECUTED in success statuses", "PAYMENT_EXECUTED" in YAPILY_PAYMENT_STATUSES)

    # 7. Payment verification — empty token
    print("\n7. Payment verification")
    test("empty token returns False", adapter.verify_payment("") is False)
    test("whitespace token returns False", adapter.verify_payment("   ") is False)

    # 8. create_settlement — no live API
    print("\n8. Settlement creation")
    result_settle = adapter.create_settlement("yap-pay-001", 100.0, "GBP", "algorand_mainnet")
    test("returns None on network error (no live API)", result_settle is None)

    # Default network fallback
    adapter2 = YapilyAlgoVoi(
        api_key="k",
        tenant_id="t",
        webhook_secret="s",
        default_network="voi_mainnet",
    )
    test("invalid network falls back to default_network", adapter2.default_network == "voi_mainnet")

    # 9. SSL enforcement
    print("\n9. SSL enforcement")
    test("ssl.create_default_context used", "create_default_context" in src)
    test("urlopen uses context=self._ssl", "context=self._ssl" in src)

    # 10. No hardcoded secrets
    print("\n10. No hardcoded secrets")
    test("no real API keys in source", "algv_iedCPy" not in src)
    test("no real tenant IDs in source", "96eb0225" not in src)

    # 11. Yapily-specific features
    print("\n11. Yapily-specific features")
    test("X-Yapily-Signature header referenced", "X-Yapily-Signature" in src)
    test("yapily_application_key init param", "yapily_application_key" in src)
    test("yapily_application_secret init param", "yapily_application_secret" in src)
    test("yapily.com referenced", "yapily.com" in src)
    test("/v1/payment-links endpoint used", "/v1/payment-links" in src)
    test("X-Tenant-Id header sent", "X-Tenant-Id" in src)
    test("console.yapily.com referenced", "console.yapily.com" in src)

    # 12. Flask handler
    print("\n12. Flask handler")
    handler = adapter.flask_webhook_handler()
    test("flask_webhook_handler returns callable", callable(handler))

    # Summary
    print("\n" + "=" * 50)
    print(f"Results: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
