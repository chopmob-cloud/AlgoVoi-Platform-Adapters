"""
Tokopedia AlgoVoi Adapter -- Tests
"""

import hashlib
import hmac as hmac_mod
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from tokopedia_algovoi import TokopediaAlgoVoi, HOSTED_NETWORKS

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

    adapter = TokopediaAlgoVoi(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        client_id="test_client_id",
        client_secret="test_client_secret",
        fs_id="test_fs_id",
        webhook_secret="test_secret",
        default_network="algorand_mainnet",
        base_currency="IDR",
    )

    src = open(os.path.join(os.path.dirname(__file__), "tokopedia_algovoi.py")).read()

    print("Tokopedia AlgoVoi Adapter -- Tests")
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
    adapter_nosecret = TokopediaAlgoVoi(webhook_secret="")
    test("empty secret returns None", adapter_nosecret.verify_webhook(b"body", "sig") is None)

    body = b'{"order_id":"TOKO-123","status":"new_order","shop_id":"SHOP1","total_price":250000}'
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
        "order_id": "TOKO-ORDER-789",
        "status": "new_order",
        "shop_id": "SHOP123",
        "fs_id": "FS_TEST",
        "total_price": 250000.0,
        "currency": "IDR",
    }
    order = adapter.parse_order_webhook(webhook)
    test("parses order_id", order and order["order_id"] == "TOKO-ORDER-789")
    test("parses status", order and order["status"] == "new_order")
    test("parses shop_id", order and order["shop_id"] == "SHOP123")
    test("parses fs_id", order and order["fs_id"] == "FS_TEST")
    test("parses amount", order and order["amount"] == 250000.0)
    test("parses currency", order and order["currency"] == "IDR")

    # 5. Alternate field name
    webhook2 = {
        "id": "TOKO-ORDER-999",
        "order_status": "processing",
        "amount": 100000.0,
    }
    order2 = adapter.parse_order_webhook(webhook2)
    test("parses alternate id field", order2 and order2["order_id"] == "TOKO-ORDER-999")
    test("parses alternate status field", order2 and order2["status"] == "processing")

    # 6. Invalid webhooks
    print("\n6. Invalid webhook payloads")
    test("empty payload returns None", adapter.parse_order_webhook({}) is None)

    # 7. Payment verification
    print("\n7. Payment verification")
    test("empty token returns False", adapter.verify_payment("") is False)

    # 8. Order fulfilment
    print("\n8. Order fulfilment")
    test("empty tx_id rejected", adapter.fulfill_order("TOKO-123", "") is False)
    test(">200 char tx_id rejected", adapter.fulfill_order("TOKO-123", "A" * 201) is False)

    # No client secret
    adapter_nokey = TokopediaAlgoVoi(client_secret="", client_id="")
    test("no client_secret rejected", adapter_nokey.fulfill_order("TOKO-123", "TXID") is False)

    # 9. SSL
    print("\n9. SSL enforcement")
    test("ssl.create_default_context", "create_default_context" in src)

    # 10. No hardcoded secrets
    print("\n10. No hardcoded secrets")
    test("no real API keys", "algv_iedCPy" not in src)
    test("no real tenant IDs", "96eb0225" not in src)

    # 11. Tokopedia-specific features
    print("\n11. Tokopedia-specific features")
    test("X-Tokopedia-Signature header", "X-Tokopedia-Signature" in src)
    test("Tokopedia FS base URL", "fs.tokopedia.net" in src)
    test("accept_order endpoint", "accept-order" in src)
    test("client_id param", "client_id" in src)
    test("client_secret param", "client_secret" in src)
    test("fs_id param", "fs_id" in src)

    # 12. Default network fallback
    print("\n12. Default network fallback")
    adapter_default = TokopediaAlgoVoi(default_network="voi_mainnet")
    test("custom default_network stored", adapter_default.default_network == "voi_mainnet")

    # 13. Version
    print("\n13. Version")
    from tokopedia_algovoi import __version__
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
    from tokopedia_algovoi import CHAIN_LABELS
    test("algorand label set", "algorand_mainnet" in CHAIN_LABELS)
    test("voi label set", "voi_mainnet" in CHAIN_LABELS)

    # Summary
    print("\n" + "=" * 50)
    print(f"Results: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
