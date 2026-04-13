"""
Printify AlgoVoi Adapter -- Tests
"""

import hashlib
import hmac as hmac_mod
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from printify_algovoi import PrintifyAlgoVoi, HOSTED_NETWORKS, PRINTIFY_API_BASE

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

    adapter = PrintifyAlgoVoi(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        printify_token="pfy_test_token",
        shop_id="shop-001",
        webhook_secret="test_secret",
        default_network="algorand_mainnet",
        base_currency="USD",
    )

    src = open(os.path.join(os.path.dirname(__file__), "printify_algovoi.py")).read()

    print("Printify AlgoVoi Adapter -- Tests")
    print("=" * 50)

    # 1. Network validation
    print("\n1. Network validation")
    test("4 hosted networks", len(HOSTED_NETWORKS) == 4)
    test("algorand_mainnet", "algorand_mainnet" in HOSTED_NETWORKS)
    test("voi_mainnet", "voi_mainnet" in HOSTED_NETWORKS)
    test("hedera_mainnet", "hedera_mainnet" in HOSTED_NETWORKS)
    test("stellar_mainnet", "stellar_mainnet" in HOSTED_NETWORKS)

    # 2. Webhook verification
    print("\n2. Webhook HMAC verification")
    adapter_nosecret = PrintifyAlgoVoi(webhook_secret="")
    body = b'{"type":"order:created","data":{"id":"pfy-123","total_price":2499,"currency":"USD"}}'
    test("empty secret returns None",
         adapter_nosecret.verify_webhook(body, make_sig("test_secret", body)) is None)

    sig = make_sig("test_secret", body)
    result = adapter.verify_webhook(body, sig)
    test("valid HMAC returns payload", result is not None)
    test("wrong HMAC returns None", adapter.verify_webhook(body, "wrongsig") is None)

    # 3. Timing-safe comparison
    print("\n3. Timing safety")
    test("uses hmac.compare_digest", "compare_digest" in src)

    # 4. Order parsing
    print("\n4. Order webhook parsing")
    order_payload = {
        "type": "order:created",
        "data": {
            "id": "pfy-order-456",
            "total_price": 4999,   # 49.99 in cents
            "currency": "USD",
            "status": "on-hold",
        },
    }
    parsed = adapter.parse_order_webhook(order_payload)
    test("parses order_id", parsed and parsed["order_id"] == "pfy-order-456")
    test("converts cents to dollars", parsed and parsed["amount"] == 49.99)
    test("parses currency", parsed and parsed["currency"] == "USD")
    test("parses event type", parsed and parsed["type"] == "order:created")
    test("parses status", parsed and parsed["status"] == "on-hold")

    # Zero cents
    zero_payload = {
        "type": "order:created",
        "data": {"id": "pfy-zero", "total_price": 0, "currency": "USD"},
    }
    zero = adapter.parse_order_webhook(zero_payload)
    test("zero cents returns 0.00", zero and zero["amount"] == 0.0)

    # 5. Edge cases
    print("\n5. Edge cases")
    test("empty payload returns None", adapter.parse_order_webhook({}) is None)
    test("unknown type returns None",
         adapter.parse_order_webhook({"type": "shipment:delivered", "data": {}}) is None)
    test("missing order_id returns None",
         adapter.parse_order_webhook({"type": "order:created", "data": {}}) is None)

    # Integer rounding: 1 cent = 0.01
    penny_payload = {
        "type": "order:created",
        "data": {"id": "penny", "total_price": 1, "currency": "USD"},
    }
    penny = adapter.parse_order_webhook(penny_payload)
    test("1 cent returns 0.01", penny and penny["amount"] == 0.01)

    # 6. submit_order guards
    print("\n6. submit_order guards")
    adapter_notoken = PrintifyAlgoVoi(printify_token="", shop_id="shop-1")
    test("no token returns False", adapter_notoken.submit_order("ord-1") is False)
    adapter_noshop = PrintifyAlgoVoi(printify_token="tok", shop_id="")
    test("no shop_id returns False", adapter_noshop.submit_order("ord-1") is False)
    test("empty order_id returns False", adapter.submit_order("") is False)

    # 7. Platform-specific checks
    print("\n7. Printify-specific checks")
    test("PRINTIFY_API_BASE correct", PRINTIFY_API_BASE == "https://api.printify.com/v1")
    test("X-Pfy-Signature (official header) in source", "X-Pfy-Signature" in src)
    test("x-pfy-signature fallback in source", "x-pfy-signature" in src)
    test("send_to_production in source", "send_to_production" in src)
    test("total_price in source", "total_price" in src)
    test("cents division by 100", "/ 100" in src)
    test("1800 expiry seconds", "1800" in src)

    # 8. SSL enforcement
    print("\n8. SSL enforcement")
    test("ssl.create_default_context", "create_default_context" in src)

    # 9. No hardcoded secrets
    print("\n9. No hardcoded secrets")
    test("no real API keys", "algv_" not in src)
    test("no real tenant IDs", "96eb0225" not in src)

    print("\n" + "=" * 50)
    print(f"Results: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
