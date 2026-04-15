"""
Squarespace AlgoVoi Adapter -- Tests
"""

import hashlib
import hmac as hmac_mod
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from squarespace_algovoi import SquarespaceAlgoVoi, HOSTED_NETWORKS

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

    adapter = SquarespaceAlgoVoi(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        squarespace_api_key="test_sq_key",
        webhook_secret="test_secret",
        default_network="algorand_mainnet",
        base_currency="GBP",
    )

    print("Squarespace AlgoVoi Adapter -- Tests")
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
    adapter_nosecret = SquarespaceAlgoVoi(webhook_secret="")
    test("empty secret returns None", adapter_nosecret.verify_webhook(b"body", "sig") is None)

    body = b'{"topic":"order.create","data":{"id":"abc123","grandTotal":{"value":"29.99","currency":"GBP"}}}'
    expected = hmac_mod.new("test_secret".encode(), body, hashlib.sha256).hexdigest()
    result = adapter.verify_webhook(body, expected)
    test("valid HMAC returns payload", result is not None)
    test("wrong HMAC returns None", adapter.verify_webhook(body, "wrong") is None)

    # 3. Timing-safe
    print("\n3. Timing safety")
    src = open(__file__.replace("test_squarespace.py", "squarespace_algovoi.py")).read()
    test("uses hmac.compare_digest", "compare_digest" in src)

    # 3a. Type guards (v1.1.0)
    test("bytes sig returns None (no crash)",
         adapter.verify_webhook(body, expected.encode()) is None)
    test("None sig returns None (no crash)",
         adapter.verify_webhook(body, None) is None)
    test("int sig returns None (no crash)",
         adapter.verify_webhook(body, 12345) is None)
    test("non-bytes body returns None (no crash)",
         adapter.verify_webhook("not-bytes", expected) is None)
    test("64 KB+ body rejected",
         adapter.verify_webhook(b'{"x":"' + b'A' * 70_000 + b'"}', "x") is None)

    # 4. Parse order webhook
    print("\n4. Order webhook parsing")
    webhook = {
        "topic": "order.create",
        "data": {
            "id": "sq-order-123",
            "orderNumber": "1042",
            "grandTotal": {"value": "49.99", "currency": "GBP"},
            "fulfillmentStatus": "PENDING",
            "customerEmail": "test@example.com",
        },
    }
    order = adapter.parse_order_webhook(webhook)
    test("parses order ID", order and order["order_id"] == "sq-order-123")
    test("parses order number", order and order["order_number"] == "1042")
    test("parses amount", order and order["amount"] == 49.99)
    test("parses currency", order and order["currency"] == "GBP")
    test("parses status", order and order["status"] == "PENDING")
    test("parses email", order and order["customer_email"] == "test@example.com")
    test("parses topic", order and order["topic"] == "order.create")

    # 5. Order update event
    webhook2 = {
        "topic": "order.update",
        "data": {
            "id": "sq-order-456",
            "orderNumber": "1043",
            "grandTotal": {"value": "10.00", "currency": "USD"},
            "fulfillmentStatus": "PENDING",
        },
    }
    order2 = adapter.parse_order_webhook(webhook2)
    test("parses update event", order2 and order2["order_id"] == "sq-order-456")

    # 6. Invalid webhooks
    test("empty payload returns None", adapter.parse_order_webhook({}) is None)
    test("unknown topic returns None", adapter.parse_order_webhook({"topic": "page.update", "data": {}}) is None)

    # 6a. Null-key fuzzing (v1.1.0)
    test("payload=None returns None (no crash)",
         adapter.parse_order_webhook(None) is None)
    test("payload=list returns None (no crash)",
         adapter.parse_order_webhook([1, 2, 3]) is None)
    test("payload=str returns None (no crash)",
         adapter.parse_order_webhook("not-a-dict") is None)
    test("data=null returns None (no crash)",
         adapter.parse_order_webhook({"topic": "order.create", "data": None}) is None)
    test("grandTotal=null returns None (no silent 0.0)",
         adapter.parse_order_webhook({"topic": "order.create",
             "data": {"id": "X", "grandTotal": None}}) is None)
    test("grandTotal=string returns None (malformed)",
         adapter.parse_order_webhook({"topic": "order.create",
             "data": {"id": "X", "grandTotal": "oops"}}) is None)
    test("flat payload (no data wrapper) returns None",
         adapter.parse_order_webhook({"topic": "order.create",
             "id": "X", "grandTotal": {"value": "1.00"}}) is None)

    # 6b. Amount sanity
    def _wh(amount, oid="SQ-1"):
        return {"topic": "order.create", "data": {
            "id": oid,
            "grandTotal": {"value": amount, "currency": "GBP"},
            "fulfillmentStatus": "PENDING"}}
    test("negative amount rejected", adapter.parse_order_webhook(_wh("-1.00")) is None)
    test("NaN amount rejected", adapter.parse_order_webhook(_wh("nan")) is None)
    test("Infinity amount rejected", adapter.parse_order_webhook(_wh("inf")) is None)
    test("zero amount rejected", adapter.parse_order_webhook(_wh("0")) is None)

    # 6c. process_order amount + redirect_url (v1.1.0)
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

    # 7. Payment verification
    print("\n5. Payment verification")
    test("empty token returns False", adapter.verify_payment("") == False)
    insecure = SquarespaceAlgoVoi(api_base="http://api1.ilovechicken.co.uk",
                                  webhook_secret="s")
    test("http:// api_base rejects verify_payment",
         insecure.verify_payment("tok") == False)

    # 8. Order fulfilment
    print("\n6. Order fulfilment")
    test("empty tx_id rejected", adapter.fulfill_order("123", "", None) == False)
    test(">200 char tx_id rejected", adapter.fulfill_order("123", "A" * 201, None) == False)
    test("empty order_id rejected", adapter.fulfill_order("", "TX", None) == False)

    # No API key
    adapter_nokey = SquarespaceAlgoVoi(squarespace_api_key="")
    test("no sq api key rejected", adapter_nokey.fulfill_order("123", "TXID", None) == False)

    # 9. SSL
    print("\n7. SSL enforcement")
    test("ssl.create_default_context", "create_default_context" in src)

    # 10. No secrets
    print("\n8. No hardcoded secrets")
    test("no real API keys", "algv_iedCPy" not in src)
    test("no real tenant IDs", "96eb0225" not in src)

    # 11. Squarespace-specific
    print("\n9. Squarespace-specific features")
    test("Squarespace-Signature header", "Squarespace-Signature" in src)
    test("Squarespace API URL", "api.squarespace.com" in src)
    test("Fulfilment endpoint", "fulfillments" in src)
    test("Carrier name AlgoVoi", "AlgoVoi" in src)

    # Summary
    print("\n" + "=" * 50)
    print(f"Results: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
