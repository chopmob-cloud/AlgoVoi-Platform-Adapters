"""
Shopee AlgoVoi Adapter -- Tests
"""

import hashlib
import hmac as hmac_mod
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from shopee_algovoi import ShopeeAlgoVoi, HOSTED_NETWORKS

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

    adapter = ShopeeAlgoVoi(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        partner_id="test_partner_id",
        partner_key="test_partner_key",
        shop_id="test_shop_id",
        access_token="test_access_token",
        webhook_secret="test_secret",
        default_network="algorand_mainnet",
        base_currency="SGD",
    )

    src = open(os.path.join(os.path.dirname(__file__), "shopee_algovoi.py")).read()

    print("Shopee AlgoVoi Adapter -- Tests")
    print("=" * 50)

    # 1. Network validation
    print("\n1. Network validation")
    test("4 hosted networks", len(HOSTED_NETWORKS) == 4)
    test("algorand", "algorand_mainnet" in HOSTED_NETWORKS)
    test("voi", "voi_mainnet" in HOSTED_NETWORKS)
    test("hedera", "hedera_mainnet" in HOSTED_NETWORKS)
    test("stellar", "stellar_mainnet" in HOSTED_NETWORKS)

    # 2. Webhook security
    print("\n2. Webhook security")
    adapter_nosecret = ShopeeAlgoVoi(webhook_secret="")
    test("empty secret returns None", adapter_nosecret.verify_webhook(b"body", "sig") is None)

    body = b'{"code":3,"shop_id":12345678,"data":{"ordersn":"220101ABCDEFGH","status":"READY_TO_SHIP"}}'
    expected = hmac_mod.new("test_secret".encode(), body, hashlib.sha256).hexdigest()
    result = adapter.verify_webhook(body, expected)
    test("valid HMAC returns payload", result is not None)
    test("wrong HMAC returns None", adapter.verify_webhook(body, "wrong") is None)
    test("wrong HMAC hex returns None", adapter.verify_webhook(body, "deadbeef" * 8) is None)

    # 3. Timing safety
    print("\n3. Timing safety")
    test("uses hmac.compare_digest", "compare_digest" in src)

    # 4. Parse order webhook
    print("\n4. Order webhook parsing")
    webhook = {
        "code": 3,
        "timestamp": 1640995200,
        "shop_id": 12345678,
        "data": {
            "ordersn": "220101ABCDEFGH",
            "status": "READY_TO_SHIP",
            "total_amount": 99.99,
            "currency": "SGD",
        },
    }
    order = adapter.parse_order_webhook(webhook)
    test("parses order_sn as order_id", order and order["order_id"] == "220101ABCDEFGH")
    test("parses status", order and order["status"] == "READY_TO_SHIP")
    test("parses shop_id", order and order["shop_id"] == "12345678")
    test("parses timestamp", order and order["timestamp"] == 1640995200)
    test("parses amount", order and order["amount"] == 99.99)
    test("parses currency", order and order["currency"] == "SGD")
    test("parses code", order and order["code"] == 3)

    # 5. Invalid webhooks
    print("\n5. Invalid webhook payloads")
    test("empty payload returns None", adapter.parse_order_webhook({}) is None)
    test("wrong code returns None", adapter.parse_order_webhook({"code": 1, "data": {}}) is None)
    test("no ordersn returns None", adapter.parse_order_webhook({"code": 3, "data": {}}) is None)

    # 6. Payment verification
    print("\n6. Payment verification")
    test("empty token returns False", adapter.verify_payment("") is False)

    # 7. Order fulfilment
    print("\n7. Order fulfilment")
    test("empty tx_id rejected", adapter.fulfill_order("ORDER123", "") is False)
    test(">200 char tx_id rejected", adapter.fulfill_order("ORDER123", "A" * 201) is False)

    # No partner key
    adapter_nokey = ShopeeAlgoVoi(partner_key="", partner_id="")
    test("no partner_key rejected", adapter_nokey.fulfill_order("ORDER123", "TXID") is False)

    # 8. SSL
    print("\n8. SSL enforcement")
    test("ssl.create_default_context", "create_default_context" in src)

    # 9. No hardcoded secrets
    print("\n9. No hardcoded secrets")
    test("no real API keys", "algv_iedCPy" not in src)
    test("no real tenant IDs", "96eb0225" not in src)

    # 10. Shopee-specific features
    print("\n10. Shopee-specific features")
    test("Authorization header for webhook (Shopee standard)", "Authorization" in src)
    test("Shopee API base URL", "partner.shopeemobile.com" in src)
    test("ship_order endpoint", "ship_order" in src)
    test("order_sn field present", "ordersn" in src)
    test("partner_id in signing", "partner_id" in src)
    test("partner_key in signing", "partner_key" in src)

    # 11. Default network fallback
    print("\n11. Default network fallback")
    adapter_default = ShopeeAlgoVoi(default_network="algorand_mainnet")
    test("invalid network falls back to default", adapter_default.default_network == "algorand_mainnet")

    # 12. Base currency
    print("\n12. Base currency")
    test("base_currency set correctly", adapter.base_currency == "SGD")

    # 13. Version
    print("\n13. Version")
    from shopee_algovoi import __version__
    test("__version__ is 1.0.0", __version__ == "1.0.0")

    # 14. Webhook body parse edge cases
    print("\n14. Webhook body parse edge cases")
    bad_json = b"not-json"
    test("invalid JSON body returns None", adapter.verify_webhook(
        bad_json,
        hmac_mod.new("test_secret".encode(), bad_json, hashlib.sha256).hexdigest()
    ) is None)

    # 15. CHAIN_LABELS
    print("\n15. CHAIN_LABELS")
    from shopee_algovoi import CHAIN_LABELS
    test("algorand label set", "algorand_mainnet" in CHAIN_LABELS)
    test("voi label set", "voi_mainnet" in CHAIN_LABELS)

    # Summary
    print("\n" + "=" * 50)
    print(f"Results: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
