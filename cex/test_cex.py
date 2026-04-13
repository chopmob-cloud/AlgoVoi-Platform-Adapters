"""
CeX AlgoVoi Adapter -- Tests
"""

import hashlib
import hmac as hmac_mod
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from cex_algovoi import CexAlgoVoi, HOSTED_NETWORKS

PASS = FAIL = 0


def test(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} -- {detail}")


def make_sig(secret, body):
    return hmac_mod.new(secret.encode(), body, hashlib.sha256).hexdigest()


def main():
    global PASS, FAIL

    adapter = CexAlgoVoi(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        webhook_secret="test_secret",
        default_network="algorand_mainnet",
        base_currency="GBP",
    )

    src = open(os.path.join(os.path.dirname(__file__), "cex_algovoi.py")).read()

    print("CeX AlgoVoi Adapter -- Tests")
    print("=" * 50)

    # 1. Network validation
    print("\n1. Network validation")
    test("4 hosted networks", len(HOSTED_NETWORKS) == 4)
    test("algorand_mainnet", "algorand_mainnet" in HOSTED_NETWORKS)
    test("voi_mainnet", "voi_mainnet" in HOSTED_NETWORKS)
    test("hedera_mainnet", "hedera_mainnet" in HOSTED_NETWORKS)
    test("stellar_mainnet", "stellar_mainnet" in HOSTED_NETWORKS)

    # 2. Webhook / bypass verification
    print("\n2. Webhook HMAC verification")
    adapter_nosecret = CexAlgoVoi(webhook_secret="")
    body = b'{"event":"order.created","order":{"order_id":"CEX-1","currency":"GBP","totalPrice":49.99}}'
    test("empty secret returns None",
         adapter_nosecret.verify_webhook(body, make_sig("test_secret", body)) is None)

    sig = make_sig("test_secret", body)
    result = adapter.verify_webhook(body, sig)
    test("valid HMAC returns payload", result is not None)
    test("wrong HMAC returns None", adapter.verify_webhook(body, "wrongsig") is None)
    test("empty signature returns None", adapter.verify_webhook(body, "") is None)

    # 3. Timing-safe comparison
    print("\n3. Timing safety")
    test("uses hmac.compare_digest", "compare_digest" in src)

    # 4. Bypass order parsing
    print("\n4. Bypass order parsing")
    bypass_data = {
        "event": "order.created",
        "order": {
            "order_id": "CEX-123456",
            "currency": "GBP",
            "totalPrice": 49.99,
            "items": [
                {"box_id": "BX123456", "description": "Apple iPhone 13 128GB", "quantity": 1, "unit_price": "49.99"}
            ],
        },
    }
    parsed = adapter.parse_bypass_order(bypass_data)
    test("parses order_id", parsed and parsed["order_id"] == "CEX-123456")
    test("parses amount from totalPrice", parsed and parsed["amount"] == 49.99)
    test("parses currency", parsed and parsed["currency"] == "GBP")
    test("parses description from items", parsed and "Apple iPhone 13" in parsed["description"])

    # 5. Edge cases
    print("\n5. Edge cases")
    test("empty data returns None", adapter.parse_bypass_order({}) is None)
    test("unknown event returns None",
         adapter.parse_bypass_order({"event": "shipment.dispatched", "order": {"order_id": "1"}}) is None)

    # totalPrice absent returns sum items
    sum_data = {
        "event": "order.created",
        "order": {
            "order_id": "CEX-SUM",
            "currency": "GBP",
            "items": [
                {"quantity": 2, "unit_price": "10.00"},
                {"quantity": 1, "unit_price": "5.50"},
            ],
        },
    }
    summed = adapter.parse_bypass_order(sum_data)
    test("sums items when totalPrice absent", summed and summed["amount"] == 25.50)

    # No items and no totalPrice returns 0.0
    no_amount = {
        "event": "order.created",
        "order": {"order_id": "CEX-ZERO", "currency": "GBP"},
    }
    zero = adapter.parse_bypass_order(no_amount)
    test("no amount defaults to 0.0", zero and zero["amount"] == 0.0)

    # Empty event string (legacy)
    legacy = {
        "order": {"order_id": "CEX-LEG", "currency": "GBP", "totalPrice": 9.99},
    }
    leg = adapter.parse_bypass_order(legacy)
    test("empty event accepted (legacy)", leg and leg["order_id"] == "CEX-LEG")

    # 6. verify_payment
    print("\n6. Payment verification")
    test("empty token returns False", adapter.verify_payment("") is False)

    # 7. No fulfill_order
    print("\n7. No fulfill_order (CeX bypass-only)")
    test("no fulfill_order method", not hasattr(adapter, "fulfill_order"))
    test("bypass mode note in source", "bypass" in src.lower())
    test("share checkout_url manually note in source", "manually" in src.lower())

    # 8. Platform-specific checks
    print("\n8. CeX-specific checks")
    test("X-Cex-Signature in source", "X-Cex-Signature" in src)
    test("totalPrice in source", "totalPrice" in src)
    test("no public API note", "no public API" in src.lower() or "no public api" in src.lower())
    test("CEX prefix example in source", "CEX-" in src)
    test("wss2.cex mentioned in source", "wss2.cex" in src)

    # 9. SSL enforcement
    print("\n9. SSL enforcement")
    test("ssl.create_default_context", "create_default_context" in src)

    # 10. No hardcoded secrets
    print("\n10. No hardcoded secrets")
    test("no real API keys", "algv_" not in src)
    test("no real tenant IDs", "96eb0225" not in src)

    print("\n" + "=" * 50)
    print(f"Results: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
