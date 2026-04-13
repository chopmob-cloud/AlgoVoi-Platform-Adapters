"""
Etsy AlgoVoi Adapter -- Tests
"""

import hashlib
import hmac as hmac_mod
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from etsy_algovoi import EtsyAlgoVoi, HOSTED_NETWORKS

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

    adapter = EtsyAlgoVoi(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        keystring="test_keystring",
        access_token="test_access_token",
        refresh_token="test_refresh_token",
        webhook_secret="test_secret",
        default_network="algorand_mainnet",
        base_currency="USD",
    )

    src = open(os.path.join(os.path.dirname(__file__), "etsy_algovoi.py")).read()

    print("Etsy AlgoVoi Adapter -- Tests")
    print("=" * 50)

    # 1. Network validation
    print("\n1. Network validation")
    test("4 hosted networks", len(HOSTED_NETWORKS) == 4)
    test("algorand_mainnet", "algorand_mainnet" in HOSTED_NETWORKS)
    test("voi_mainnet", "voi_mainnet" in HOSTED_NETWORKS)
    test("hedera_mainnet", "hedera_mainnet" in HOSTED_NETWORKS)
    test("stellar_mainnet", "stellar_mainnet" in HOSTED_NETWORKS)

    # 2. Webhook security
    print("\n2. Webhook security")
    adapter_nosecret = EtsyAlgoVoi(webhook_secret="")
    test("empty secret returns None", adapter_nosecret.verify_webhook(b"body", "sig") is None)

    body = b'{"event":"order.paid","data":{"receipt_id":99001,"grandtotal":{"amount":4999,"divisor":100,"currency_code":"USD"},"status":"paid"}}'
    valid_sig = make_sig("test_secret", body)
    result = adapter.verify_webhook(body, valid_sig)
    test("valid HMAC returns payload", result is not None)
    test("wrong HMAC returns None", adapter.verify_webhook(body, "wrong") is None)
    test("empty signature returns None", adapter.verify_webhook(body, "") is None)

    # 3. Timing safety
    print("\n3. Timing safety")
    test("uses hmac.compare_digest", "compare_digest" in src)
    test("uses HMAC-SHA256", "sha256" in src)

    # 4. Order webhook parsing — standard case
    print("\n4. Order webhook parsing")
    webhook = {
        "event": "order.paid",
        "data": {
            "receipt_id": 12345,
            "grandtotal": {"amount": 7500, "divisor": 100, "currency_code": "USD"},
            "status": "paid",
            "buyer_email": "buyer@example.com",
            "shop_id": 98765,
        },
    }
    order = adapter.parse_order_webhook(webhook)
    test("parses receipt_id as order_id", order and order["order_id"] == "12345")
    test("parses amount (minor to major units)", order and order["amount"] == 75.00)
    test("parses currency", order and order["currency"] == "USD")
    test("parses status", order and order["status"] == "paid")
    test("parses buyer_email", order and order["buyer_email"] == "buyer@example.com")
    test("parses shop_id", order and order["shop_id"] == "98765")
    test("parses event", order and order["event"] == "order.paid")

    # 5. Amount without divisor
    webhook_nodiv = {
        "event": "order.paid",
        "data": {
            "receipt_id": 22222,
            "grandtotal": {"amount": 29.99, "divisor": 1, "currency_code": "GBP"},
            "status": "paid",
        },
    }
    order_nodiv = adapter.parse_order_webhook(webhook_nodiv)
    test("amount with divisor=1 left unchanged", order_nodiv and order_nodiv["amount"] == 29.99)

    # 6. Edge cases
    print("\n5. Edge cases")
    test("empty payload returns None", adapter.parse_order_webhook({}) is None)
    test("missing receipt_id returns None", adapter.parse_order_webhook({"event": "order.paid", "data": {}}) is None)

    # Currency uppercase
    webhook_lower = {
        "event": "order.paid",
        "data": {
            "receipt_id": 33333,
            "grandtotal": {"amount": 100, "divisor": 100, "currency_code": "eur"},
        },
    }
    order_lower = adapter.parse_order_webhook(webhook_lower)
    test("currency uppercased", order_lower and order_lower["currency"] == "EUR")

    # Fallback currency
    webhook_nocur = {
        "event": "order.paid",
        "data": {"receipt_id": 44444, "grandtotal": {"amount": 500, "divisor": 100}},
    }
    order_nocur = adapter.parse_order_webhook(webhook_nocur)
    test("fallback to base_currency", order_nocur and order_nocur["currency"] == "USD")

    # 7. Payment verification
    print("\n6. Payment verification")
    test("empty token returns False", adapter.verify_payment("") is False)

    # 8. Order fulfilment guards
    print("\n7. Order fulfilment")
    test("empty tx_id rejected", adapter.fulfill_order("123", "", "98765") is False)
    test(">200 char tx_id rejected", adapter.fulfill_order("123", "X" * 201, "98765") is False)

    adapter_notoken = EtsyAlgoVoi(access_token="", keystring="ks")
    test("no access_token rejected", adapter_notoken.fulfill_order("123", "TXID", "98765") is False)

    adapter_nokey = EtsyAlgoVoi(access_token="tok", keystring="")
    test("no keystring rejected", adapter_nokey.fulfill_order("123", "TXID", "98765") is False)

    adapter_noshop = EtsyAlgoVoi(access_token="tok", keystring="ks")
    test("no shop_id rejected", adapter_noshop.fulfill_order("123", "TXID", "") is False)

    # 9. SSL enforcement
    print("\n8. SSL enforcement")
    test("ssl.create_default_context used", "create_default_context" in src)

    # 10. No hardcoded secrets
    print("\n9. No hardcoded secrets")
    test("no real API keys", "algv_iedCPy" not in src)
    test("no real tenant IDs", "96eb0225" not in src)

    # 11. Etsy-specific
    print("\n10. Etsy-specific features")
    test("webhook-signature header in source", "webhook-signature" in src)
    test("openapi.etsy.com URL in source", "openapi.etsy.com" in src)
    test("x-api-key header in source", "x-api-key" in src)
    test("receipt_id field handled in source", "receipt_id" in src)
    test("PUT method used for fulfill", '"PUT"' in src)

    # 12. Version
    print("\n11. Version")
    from etsy_algovoi import __version__
    test("version is 1.0.0", __version__ == "1.0.0")

    # Summary
    print("\n" + "=" * 50)
    print(f"Results: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
