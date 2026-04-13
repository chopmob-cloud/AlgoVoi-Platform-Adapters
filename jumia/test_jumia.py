"""
Jumia AlgoVoi Adapter -- Tests
"""

import hashlib
import hmac as hmac_mod
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from jumia_algovoi import JumiaAlgoVoi, HOSTED_NETWORKS

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

    adapter = JumiaAlgoVoi(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        jumia_api_key="test_jumia_api_key",
        api_secret="test_api_secret",
        country_domain="jumia.com.ng",
        access_token="test_access_token",
        webhook_secret="test_secret",
        default_network="algorand_mainnet",
        base_currency="NGN",
    )

    src = open(os.path.join(os.path.dirname(__file__), "jumia_algovoi.py")).read()

    print("Jumia AlgoVoi Adapter -- Tests")
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
    adapter_nosecret = JumiaAlgoVoi(webhook_secret="")
    test("empty secret returns None", adapter_nosecret.verify_webhook(b"body", "sig") is None)

    body = b'{"Event":"Order.Created","OrderId":"JUMIA-123","Timestamp":"2024-01-15T10:30:00Z"}'
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
        "Event": "Order.Created",
        "OrderId": "JUMIA-ORDER-456",
        "Status": "pending",
        "Timestamp": "2024-01-15T10:30:00Z",
        "Price": 15000.0,
        "Currency": "NGN",
    }
    order = adapter.parse_order_webhook(webhook)
    test("parses OrderId", order and order["order_id"] == "JUMIA-ORDER-456")
    test("parses Status", order and order["status"] == "pending")
    test("parses Event", order and order["event"] == "Order.Created")
    test("parses Timestamp", order and order["timestamp"] == "2024-01-15T10:30:00Z")
    test("parses amount", order and order["amount"] == 15000.0)
    test("parses Currency", order and order["currency"] == "NGN")

    # 5. StatusChanged event
    webhook2 = {
        "Event": "Order.StatusChanged",
        "OrderId": "JUMIA-ORDER-789",
        "Status": "shipped",
    }
    order2 = adapter.parse_order_webhook(webhook2)
    test("parses StatusChanged event", order2 and order2["order_id"] == "JUMIA-ORDER-789")

    # 6. Invalid webhooks
    print("\n6. Invalid webhook payloads")
    test("empty payload returns None", adapter.parse_order_webhook({}) is None)
    test("unknown event returns None", adapter.parse_order_webhook({"Event": "Product.Updated", "OrderId": "123"}) is None)

    # 7. Payment verification
    print("\n7. Payment verification")
    test("empty token returns False", adapter.verify_payment("") is False)

    # 8. Order fulfilment
    print("\n8. Order fulfilment")
    test("empty tx_id rejected", adapter.fulfill_order("JUMIA-123", "") is False)
    test(">200 char tx_id rejected", adapter.fulfill_order("JUMIA-123", "A" * 201) is False)

    # No API key
    adapter_nokey = JumiaAlgoVoi(jumia_api_key="")
    test("no jumia_api_key rejected", adapter_nokey.fulfill_order("JUMIA-123", "TXID") is False)

    # 9. SSL
    print("\n9. SSL enforcement")
    test("ssl.create_default_context", "create_default_context" in src)

    # 10. No hardcoded secrets
    print("\n10. No hardcoded secrets")
    test("no real API keys", "algv_iedCPy" not in src)
    test("no real tenant IDs", "96eb0225" not in src)

    # 11. Jumia-specific features
    print("\n11. Jumia-specific features")
    test("X-Jumia-Signature header", "X-Jumia-Signature" in src)
    test("sellercenter base URL", "sellerapi.sellercenter" in src)
    test("UpdateOrderStatus action", "UpdateOrderStatus" in src or "orders/status" in src)
    test("Order.Created event", "Order.Created" in src)
    test("country_domain param", "country_domain" in src)

    # 12. Country domains
    print("\n12. Country domain support")
    from jumia_algovoi import JUMIA_COUNTRY_DOMAINS
    test("Nigeria domain", "jumia.com.ng" in JUMIA_COUNTRY_DOMAINS.values())
    test("Kenya domain", "jumia.co.ke" in JUMIA_COUNTRY_DOMAINS.values())
    test("Egypt domain", "jumia.com.eg" in JUMIA_COUNTRY_DOMAINS.values())
    test("10 countries", len(JUMIA_COUNTRY_DOMAINS) == 10)

    # 13. Version
    print("\n13. Version")
    from jumia_algovoi import __version__
    test("__version__ is 1.0.0", __version__ == "1.0.0")

    # 14. Webhook body parse edge cases
    print("\n14. Webhook body parse edge cases")
    bad_json = b"not-json"
    test("invalid JSON body returns None", adapter.verify_webhook(
        bad_json,
        hmac_mod.new("test_secret".encode(), bad_json, hashlib.sha256).hexdigest()
    ) is None)

    # 15. API base URL
    print("\n15. API base URL")
    test("api_base country domain used", adapter._jumia_api_base == "https://sellerapi.sellercenter.jumia.com.ng")

    # Summary
    print("\n" + "=" * 50)
    print(f"Results: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
