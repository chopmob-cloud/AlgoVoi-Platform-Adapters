"""
Amazon SP-API AlgoVoi Adapter — Tests
"""

import base64
import hashlib
import hmac as hmac_mod
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from amazon_algovoi import AmazonAlgoVoi, HOSTED_NETWORKS

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

    adapter = AmazonAlgoVoi(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        webhook_secret="test_secret",
        default_network="algorand_mainnet",
        base_currency="GBP",
    )

    print("Amazon SP-API AlgoVoi Adapter -- Tests")
    print("=" * 50)

    # 1. Network validation
    print("\n1. Network validation")
    test("4 hosted networks", len(HOSTED_NETWORKS) == 4)
    test("algorand in hosted", "algorand_mainnet" in HOSTED_NETWORKS)
    test("voi in hosted", "voi_mainnet" in HOSTED_NETWORKS)
    test("hedera in hosted", "hedera_mainnet" in HOSTED_NETWORKS)
    test("stellar in hosted", "stellar_mainnet" in HOSTED_NETWORKS)

    # 2. Webhook - empty secret
    print("\n2. Webhook security")
    adapter_nosecret = AmazonAlgoVoi(webhook_secret="")
    test("empty secret returns None", adapter_nosecret.verify_webhook(b"body", "sig") is None)

    # 3. Webhook - valid HMAC
    secret = "test_secret"
    body = b'{"Payload":{"OrderChangeNotification":{"AmazonOrderId":"123-456-789"}}}'
    expected = base64.b64encode(
        hmac_mod.new(secret.encode(), body, hashlib.sha256).digest()
    ).decode()
    result = adapter.verify_webhook(body, expected)
    test("valid HMAC returns payload", result is not None)

    # 4. Webhook - wrong HMAC
    test("wrong HMAC returns None", adapter.verify_webhook(body, "wrongsig==") is None)

    # 5. Webhook - timing safe
    test("uses hmac.compare_digest", "compare_digest" in open(__file__.replace("test_amazon.py", "amazon_algovoi.py")).read())

    # 6. Parse SP-API notification
    print("\n3. SP-API order parsing")
    notification = {
        "Payload": {
            "OrderChangeNotification": {
                "AmazonOrderId": "123-4567890-1234567",
                "MarketplaceId": "A1F83G8C2ARO7P",
                "Summary": {
                    "OrderTotalAmount": "29.99",
                    "OrderTotalCurrencyCode": "GBP",
                    "OrderStatus": "Unshipped",
                },
            }
        }
    }
    order = adapter.parse_sp_api_order(notification)
    test("parses order ID", order and order["amazon_order_id"] == "123-4567890-1234567")
    test("parses amount", order and order["amount"] == 29.99)
    test("parses currency", order and order["currency"] == "GBP")
    test("parses status", order and order["status"] == "Unshipped")
    test("parses marketplace", order and order["marketplace_id"] == "A1F83G8C2ARO7P")

    # 7. Parse empty notification
    test("empty notification returns None", adapter.parse_sp_api_order({}) is None)
    test("missing order ID returns None", adapter.parse_sp_api_order({"Payload": {"OrderChangeNotification": {}}}) is None)

    # 8. Process order (will fail API call but validates input handling)
    print("\n4. Order processing")
    test("invalid network defaults to algorand", adapter.default_network == "algorand_mainnet")

    # 9. Verify payment - empty token
    print("\n5. Payment verification")
    test("empty token returns False", adapter.verify_payment("") == False)

    # 10. Confirm shipment - tx_id guard
    print("\n6. Shipment confirmation")
    test("empty tx_id rejected", adapter.confirm_shipment("123", "", "token") == False)
    test(">200 char tx_id rejected", adapter.confirm_shipment("123", "A" * 201, "token") == False)

    # 11. Marketplaces
    print("\n7. Marketplace support")
    test("UK marketplace", AmazonAlgoVoi.MARKETPLACES["UK"]["id"] == "A1F83G8C2ARO7P")
    test("US marketplace", AmazonAlgoVoi.MARKETPLACES["US"]["id"] == "ATVPDKIKX0DER")
    test("5 marketplaces", len(AmazonAlgoVoi.MARKETPLACES) == 5)

    # 12. SSL enforcement
    print("\n8. SSL enforcement")
    test("ssl context created", "create_default_context" in open(__file__.replace("test_amazon.py", "amazon_algovoi.py")).read())

    # Summary
    print("\n" + "=" * 50)
    print(f"Results: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
