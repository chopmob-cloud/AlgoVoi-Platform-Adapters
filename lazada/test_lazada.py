"""
Lazada AlgoVoi Adapter -- Tests
"""

import hashlib
import hmac as hmac_mod
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from lazada_algovoi import LazadaAlgoVoi, HOSTED_NETWORKS

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

    adapter = LazadaAlgoVoi(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        app_key="test_app_key",
        app_secret="test_app_secret",
        access_token="test_access_token",
        webhook_secret="test_secret",
        default_network="algorand_mainnet",
        base_currency="USD",
    )

    src = open(os.path.join(os.path.dirname(__file__), "lazada_algovoi.py")).read()

    print("Lazada AlgoVoi Adapter -- Tests")
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
    adapter_nosecret = LazadaAlgoVoi(webhook_secret="")
    test("empty secret returns None", adapter_nosecret.verify_webhook(b"body", "sig") is None)

    body = b'{"tradeOrderId":"123456789","status":"pending","buyerId":"buyer001"}'
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
        "tradeOrderId": "LZ-ORDER-123",
        "status": "pending",
        "buyerId": "buyer001",
        "price": 149.50,
        "currency": "USD",
        "createTime": 1640995200,
    }
    order = adapter.parse_order_webhook(webhook)
    test("parses order_id", order and order["order_id"] == "LZ-ORDER-123")
    test("parses status", order and order["status"] == "pending")
    test("parses buyer_id", order and order["buyer_id"] == "buyer001")
    test("parses amount", order and order["amount"] == 149.50)
    test("parses currency", order and order["currency"] == "USD")
    test("parses timestamp", order and order["timestamp"] == 1640995200)

    # 5. Alternate field name
    webhook2 = {
        "order_id": "LZ-ORDER-456",
        "orderStatus": "SHIPPED",
        "amount": 55.0,
    }
    order2 = adapter.parse_order_webhook(webhook2)
    test("parses alternate order_id field", order2 and order2["order_id"] == "LZ-ORDER-456")
    test("parses alternate status field", order2 and order2["status"] == "SHIPPED")

    # 6. Invalid webhooks
    print("\n6. Invalid webhook payloads")
    test("empty payload returns None", adapter.parse_order_webhook({}) is None)

    # 7. Payment verification
    print("\n7. Payment verification")
    test("empty token returns False", adapter.verify_payment("") is False)

    # 8. Order fulfilment
    print("\n8. Order fulfilment")
    test("empty tx_id rejected", adapter.fulfill_order("LZ-123", "") is False)
    test(">200 char tx_id rejected", adapter.fulfill_order("LZ-123", "A" * 201) is False)

    # No app secret
    adapter_nokey = LazadaAlgoVoi(app_secret="", app_key="")
    test("no app_secret rejected", adapter_nokey.fulfill_order("LZ-123", "TXID") is False)

    # 9. SSL
    print("\n9. SSL enforcement")
    test("ssl.create_default_context", "create_default_context" in src)

    # 10. No hardcoded secrets
    print("\n10. No hardcoded secrets")
    test("no real API keys", "algv_iedCPy" not in src)
    test("no real tenant IDs", "96eb0225" not in src)

    # 11. Lazada-specific features
    print("\n11. Lazada-specific features")
    test("X-Lazada-Signature header", "X-Lazada-Signature" in src)
    test("Lazada API base URL", "api.lazada.com" in src)
    test("SetStatusToPackedByMarketplace action", "SetStatusToPackedByMarketplace" in src)
    test("app_key param", "app_key" in src)
    test("app_secret param", "app_secret" in src)

    # 12. Default network fallback
    print("\n12. Default network fallback")
    adapter_default = LazadaAlgoVoi(default_network="voi_mainnet")
    test("custom default_network stored", adapter_default.default_network == "voi_mainnet")

    # 13. Version
    print("\n13. Version")
    from lazada_algovoi import __version__
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
    from lazada_algovoi import CHAIN_LABELS
    test("algorand label set", "algorand_mainnet" in CHAIN_LABELS)
    test("voi label set", "voi_mainnet" in CHAIN_LABELS)

    # Summary
    print("\n" + "=" * 50)
    print(f"Results: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
