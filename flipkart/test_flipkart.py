"""
Flipkart AlgoVoi Adapter -- Tests
"""

import hashlib
import hmac as hmac_mod
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from flipkart_algovoi import FlipkartAlgoVoi, HOSTED_NETWORKS

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

    adapter = FlipkartAlgoVoi(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        app_id="test_app_id",
        app_secret="test_app_secret",
        access_token="test_access_token",
        webhook_secret="test_secret",
        default_network="algorand_mainnet",
        base_currency="INR",
    )

    src = open(os.path.join(os.path.dirname(__file__), "flipkart_algovoi.py")).read()

    print("Flipkart AlgoVoi Adapter -- Tests")
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
    adapter_nosecret = FlipkartAlgoVoi(webhook_secret="")
    test("empty secret returns None", adapter_nosecret.verify_webhook(b"body", "sig") is None)

    body = b'{"orderId":"FK-ORD-123","orderStatus":"APPROVED","eventType":"shipment_created"}'
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
        "orderId": "FK-ORD-789",
        "orderStatus": "APPROVED",
        "eventType": "shipment_created",
        "shipmentId": "SHP-001",
        "amount": 4999.0,
        "currency": "INR",
    }
    order = adapter.parse_order_webhook(webhook)
    test("parses orderId", order and order["order_id"] == "FK-ORD-789")
    test("parses orderStatus", order and order["status"] == "APPROVED")
    test("parses eventType", order and order["event_type"] == "shipment_created")
    test("parses shipmentId", order and order["shipment_id"] == "SHP-001")
    test("parses amount", order and order["amount"] == 4999.0)
    test("parses currency", order and order["currency"] == "INR")

    # 5. OMNS orderItemIds array
    webhook2 = {
        "orderItemIds": ["FK-ITEM-111", "FK-ITEM-222"],
        "orderStatus": "PENDING",
    }
    order2 = adapter.parse_order_webhook(webhook2)
    test("parses orderItemIds[0] as order_id", order2 and order2["order_id"] == "FK-ITEM-111")

    # 6. Invalid webhooks
    print("\n6. Invalid webhook payloads")
    test("empty payload returns None", adapter.parse_order_webhook({}) is None)

    # 7. Payment verification
    print("\n7. Payment verification")
    test("empty token returns False", adapter.verify_payment("") is False)

    # 8. Order fulfilment
    print("\n8. Order fulfilment")
    test("empty tx_id rejected", adapter.fulfill_order("FK-123", "") is False)
    test(">200 char tx_id rejected", adapter.fulfill_order("FK-123", "A" * 201) is False)

    # No app secret
    adapter_nokey = FlipkartAlgoVoi(app_secret="", app_id="")
    test("no app_secret rejected", adapter_nokey.fulfill_order("FK-123", "TXID") is False)

    # 9. SSL
    print("\n9. SSL enforcement")
    test("ssl.create_default_context", "create_default_context" in src)

    # 10. No hardcoded secrets
    print("\n10. No hardcoded secrets")
    test("no real API keys", "algv_iedCPy" not in src)
    test("no real tenant IDs", "96eb0225" not in src)

    # 11. Flipkart-specific features
    print("\n11. Flipkart-specific features")
    test("X-Flipkart-Signature header", "X-Flipkart-Signature" in src)
    test("Flipkart API base URL", "api.flipkart.net" in src)
    test("shipments/dispatch endpoint", "shipments/dispatch" in src)
    test("app_id param", "app_id" in src)
    test("app_secret param", "app_secret" in src)
    test("OMNS reference", "OMNS" in src or "Notification" in src)

    # 12. Default network fallback
    print("\n12. Default network fallback")
    adapter_default = FlipkartAlgoVoi(default_network="hedera_mainnet")
    test("custom default_network stored", adapter_default.default_network == "hedera_mainnet")

    # 13. Version
    print("\n13. Version")
    from flipkart_algovoi import __version__
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
    from flipkart_algovoi import CHAIN_LABELS
    test("algorand label set", "algorand_mainnet" in CHAIN_LABELS)
    test("voi label set", "voi_mainnet" in CHAIN_LABELS)

    # Summary
    print("\n" + "=" * 50)
    print(f"Results: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
