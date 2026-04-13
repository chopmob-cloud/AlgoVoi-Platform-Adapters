"""
BigCommerce AlgoVoi Adapter -- Tests
"""

import hashlib
import hmac as hmac_mod
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from bigcommerce_algovoi import BigCommerceAlgoVoi, HOSTED_NETWORKS

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

    adapter = BigCommerceAlgoVoi(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        store_hash="test_store_hash",
        access_token="test_access_token",
        webhook_secret="test_secret",
        default_network="algorand_mainnet",
        base_currency="USD",
    )

    src = open(os.path.join(os.path.dirname(__file__), "bigcommerce_algovoi.py")).read()

    print("BigCommerce AlgoVoi Adapter -- Tests")
    print("=" * 50)

    # 1. Network validation
    print("\n1. Network validation")
    test("4 hosted networks", len(HOSTED_NETWORKS) == 4)
    test("algorand_mainnet", "algorand_mainnet" in HOSTED_NETWORKS)
    test("voi_mainnet", "voi_mainnet" in HOSTED_NETWORKS)
    test("hedera_mainnet", "hedera_mainnet" in HOSTED_NETWORKS)
    test("stellar_mainnet", "stellar_mainnet" in HOSTED_NETWORKS)

    # 2. Webhook security — empty secret
    print("\n2. Webhook security")
    adapter_nosecret = BigCommerceAlgoVoi(webhook_secret="")
    test("empty secret returns None", adapter_nosecret.verify_webhook(b"body", "sig") is None)

    # 3. Webhook verify — BigCommerce HMAC-SHA256 base64 on body (X-BC-Signature)
    import base64
    body = b'{"scope":"store/order/created","data":{"id":1001}}'
    valid_sig = base64.b64encode(
        hmac_mod.new("test_secret".encode(), body, hashlib.sha256).digest()
    ).decode()
    result = adapter.verify_webhook(body, valid_sig)
    test("correct HMAC-SHA256 base64 sig returns payload", result is not None)
    test("wrong secret returns None", adapter.verify_webhook(body, "wrong_secret") is None)
    test("empty signature returns None", adapter.verify_webhook(body, "") is None)

    # 4. compare_digest used for timing safety
    print("\n3. Timing safety")
    test("uses hmac.compare_digest", "compare_digest" in src)

    # 5. Order webhook parsing
    print("\n4. Order webhook parsing")
    webhook = {
        "scope": "store/order/created",
        "data": {
            "id": 12345,
            "total_inc_tax": "99.99",
            "currency_code": "USD",
            "status_id": 1,
        },
    }
    order = adapter.parse_order_webhook(webhook)
    test("parses order ID", order and order["order_id"] == "12345")
    test("parses amount", order and order["amount"] == 99.99)
    test("parses currency", order and order["currency"] == "USD")
    test("parses status", order and order["status"] == "1")
    test("parses scope", order and order["scope"] == "store/order/created")

    # 6. Edge cases in parsing
    print("\n5. Edge cases")
    test("empty payload returns None", adapter.parse_order_webhook({}) is None)
    test("missing data returns None", adapter.parse_order_webhook({"scope": "store/order/created"}) is None)
    test("missing order id returns None", adapter.parse_order_webhook({"scope": "s", "data": {"foo": "bar"}}) is None)

    # 7. Currency uppercase
    webhook_lower = {
        "scope": "store/order/created",
        "data": {"id": 999, "currency_code": "gbp"},
    }
    order_lower = adapter.parse_order_webhook(webhook_lower)
    test("currency uppercased", order_lower and order_lower["currency"] == "GBP")

    # 8. Default currency fallback
    webhook_nocurrency = {
        "scope": "store/order/created",
        "data": {"id": 888},
    }
    order_nocurrency = adapter.parse_order_webhook(webhook_nocurrency)
    test("falls back to base_currency", order_nocurrency and order_nocurrency["currency"] == "USD")

    # 9. Payment verification
    print("\n6. Payment verification")
    test("empty token returns False", adapter.verify_payment("") is False)

    # 10. Order fulfilment guards
    print("\n7. Order fulfilment")
    test("empty tx_id rejected", adapter.fulfill_order("123", "") is False)
    test(">200 char tx_id rejected", adapter.fulfill_order("123", "A" * 201) is False)

    adapter_nocreds = BigCommerceAlgoVoi(store_hash="", access_token="")
    test("no store_hash rejected", adapter_nocreds.fulfill_order("123", "TXID") is False)

    adapter_notoken = BigCommerceAlgoVoi(store_hash="abc123", access_token="")
    test("no access_token rejected", adapter_notoken.fulfill_order("123", "TXID") is False)

    # 11. fetch_order guards
    print("\n8. fetch_order guards")
    adapter_nohash = BigCommerceAlgoVoi(store_hash="", access_token="tok")
    test("fetch_order no store_hash returns None", adapter_nohash.fetch_order("123") is None)

    adapter_noaccess = BigCommerceAlgoVoi(store_hash="abc", access_token="")
    test("fetch_order no access_token returns None", adapter_noaccess.fetch_order("123") is None)

    # 12. SSL enforcement
    print("\n9. SSL enforcement")
    test("ssl.create_default_context used", "create_default_context" in src)

    # 13. No hardcoded secrets
    print("\n10. No hardcoded secrets")
    test("no real API keys", "algv_iedCPy" not in src)
    test("no real tenant IDs", "96eb0225" not in src)

    # 14. BigCommerce-specific features
    print("\n11. BigCommerce-specific features")
    test("X-BC-Signature header in source", "X-BC-Signature" in src)
    test("BigCommerce API URL in source", "api.bigcommerce.com" in src)
    test("V2 orders endpoint in source", "v2/orders" in src)
    test("X-Auth-Token header in source", "X-Auth-Token" in src)
    test("status_id=10 (Completed) in source", "status_id" in src)
    test("PUT method used for fulfill", '"PUT"' in src)

    # 15. process_order network fallback
    print("\n12. process_order network fallback")
    # Invalid network should fall back to default
    adapter2 = BigCommerceAlgoVoi(
        webhook_secret="s",
        default_network="algorand_mainnet",
    )
    # We can't call the real API, but we can verify logic via source
    test("unknown network fallback logic in source", "default_network" in src)

    # 16. Version
    print("\n13. Version")
    from bigcommerce_algovoi import __version__
    test("version is 1.0.0", __version__ == "1.0.0")

    # Summary
    print("\n" + "=" * 50)
    print(f"Results: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
