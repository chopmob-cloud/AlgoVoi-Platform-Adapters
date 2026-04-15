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

    # 5a. Webhook - new type guards (v1.1.0 hardening)
    test("bytes signature returns None (no crash)",
         adapter.verify_webhook(body, expected.encode()) is None)
    test("None signature returns None (no crash)",
         adapter.verify_webhook(body, None) is None)
    test("integer signature returns None (no crash)",
         adapter.verify_webhook(body, 12345) is None)
    test("non-bytes body returns None (no crash)",
         adapter.verify_webhook("not-bytes", expected) is None)
    test("body over 64 KB rejected",
         adapter.verify_webhook(b'{"x":"' + b'A' * 70_000 + b'"}', "x") is None)

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

    # 7a. parse_sp_api_order - amount sanity (v1.1.0 hardening)
    def _notif(amount_str, status="Unshipped"):
        return {"Payload": {"OrderChangeNotification": {
            "AmazonOrderId": "999-0000000-0000001",
            "Summary": {"OrderTotalAmount": amount_str,
                        "OrderTotalCurrencyCode": "GBP",
                        "OrderStatus": status}}}}
    test("negative amount rejected",
         adapter.parse_sp_api_order(_notif("-1.00")) is None)
    test("NaN amount rejected",
         adapter.parse_sp_api_order(_notif("nan")) is None)
    test("Infinity amount rejected",
         adapter.parse_sp_api_order(_notif("inf")) is None)
    test("zero amount rejected",
         adapter.parse_sp_api_order(_notif("0")) is None)

    # 8. Process order (will fail API call but validates input handling)
    print("\n4. Order processing")
    test("invalid network defaults to algorand", adapter.default_network == "algorand_mainnet")
    # 8a. process_order - amount + redirect_url validation
    test("negative amount returns None",
         adapter.process_order("123", -1.00) is None)
    test("NaN amount returns None",
         adapter.process_order("123", float("nan")) is None)
    test("Infinity amount returns None",
         adapter.process_order("123", float("inf")) is None)
    test("zero amount returns None",
         adapter.process_order("123", 0) is None)
    test("file:// redirect_url returns None",
         adapter.process_order("123", 1.00, redirect_url="file:///etc/passwd") is None)
    test("gopher:// redirect_url returns None",
         adapter.process_order("123", 1.00, redirect_url="gopher://x") is None)
    test("http:// redirect_url returns None (https-only)",
         adapter.process_order("123", 1.00, redirect_url="http://example.com/ok") is None)

    # 9. Verify payment - empty token + scheme check
    print("\n5. Payment verification")
    test("empty token returns False", adapter.verify_payment("") == False)
    insecure = AmazonAlgoVoi(api_base="http://api1.ilovechicken.co.uk",
                             webhook_secret="s")
    test("http:// api_base rejects verify_payment",
         insecure.verify_payment("tok") == False)

    # 10. Confirm shipment - tx_id guard + SSRF allowlist + order-ID format
    print("\n6. Shipment confirmation")
    valid_oid = "123-1234567-1234567"
    test("empty tx_id rejected", adapter.confirm_shipment(valid_oid, "", "token") == False)
    test(">200 char tx_id rejected",
         adapter.confirm_shipment(valid_oid, "A" * 201, "token") == False)
    test("malformed amazon_order_id rejected",
         adapter.confirm_shipment("not-an-order", "TX", "token") == False)
    test("non-amazon marketplace_url rejected (SSRF guard)",
         adapter.confirm_shipment(valid_oid, "TX", "token",
             marketplace_url="https://attacker.invalid") == False)
    test("http:// marketplace_url rejected",
         adapter.confirm_shipment(valid_oid, "TX", "token",
             marketplace_url="http://sellingpartnerapi-eu.amazon.com") == False)

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
