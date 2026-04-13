"""
Bol.com AlgoVoi Adapter -- Tests
"""

import hashlib
import hmac as hmac_mod
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from bolcom_algovoi import BolcomAlgoVoi, HOSTED_NETWORKS

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

    adapter = BolcomAlgoVoi(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        client_id="test_client_id",
        client_secret="test_client_secret",
        webhook_secret="test_secret",
        default_network="algorand_mainnet",
        base_currency="EUR",
    )

    src = open(os.path.join(os.path.dirname(__file__), "bolcom_algovoi.py")).read()

    print("Bol.com AlgoVoi Adapter -- Tests")
    print("=" * 50)

    # 1. Network validation
    print("\n1. Network validation")
    test("4 hosted networks", len(HOSTED_NETWORKS) == 4)
    test("algorand_mainnet present", "algorand_mainnet" in HOSTED_NETWORKS)
    test("voi_mainnet present", "voi_mainnet" in HOSTED_NETWORKS)
    test("hedera_mainnet present", "hedera_mainnet" in HOSTED_NETWORKS)
    test("stellar_mainnet present", "stellar_mainnet" in HOSTED_NETWORKS)

    # 2. Webhook / signature verification
    print("\n2. Signature verification")
    adapter_nosecret = BolcomAlgoVoi(webhook_secret="")
    test("empty secret returns None", adapter_nosecret.verify_webhook(b"body", "sig") is None)

    body = b'{"orderId":"bol-001","orderItems":[{"unitPrice":"29.99","quantity":1}]}'
    expected = hmac_mod.new("test_secret".encode(), body, hashlib.sha256).hexdigest()

    result = adapter.verify_webhook(body, expected)
    test("valid HMAC returns payload", result is not None)
    test("valid HMAC payload is dict", isinstance(result, dict))
    test("wrong HMAC returns None", adapter.verify_webhook(body, "wrongsig") is None)
    test("tampered body returns None", adapter.verify_webhook(b"tampered", expected) is None)

    # 3. Timing safety
    print("\n3. Timing safety")
    test("uses hmac.compare_digest", "compare_digest" in src)

    # 4. Parse order
    print("\n4. Order parsing")
    order_data = {
        "orderId": "BOL123456",
        "status": "OPEN",
        "currency": "EUR",
        "orderItems": [
            {"unitPrice": "49.99", "quantity": 2},
            {"unitPrice": "10.00", "quantity": 1},
        ],
        "billingDetails": {"email": "buyer@bol.nl"},
    }
    order = adapter.parse_order(order_data)
    test("parses order_id", order and order["order_id"] == "BOL123456")
    test("parses amount correctly", order and order["amount"] == 109.98)
    test("parses currency", order and order["currency"] == "EUR")
    test("parses status", order and order["status"] == "OPEN")
    test("parses buyer_email", order and order["buyer_email"] == "buyer@bol.nl")

    # Missing orderId
    test("missing orderId returns None", adapter.parse_order({}) is None)

    # order with totalAmount fallback
    order_data2 = {
        "orderId": "BOL789",
        "status": "OPEN",
        "currency": "EUR",
        "totalAmount": "25.50",
        "orderItems": [],
        "shipmentDetails": {"email": "ship@bol.nl"},
    }
    order2 = adapter.parse_order(order_data2)
    test("totalAmount fallback", order2 and order2["amount"] == 25.50)
    test("shipmentDetails email fallback", order2 and order2["buyer_email"] == "ship@bol.nl")

    # 5. Payment verification
    print("\n5. Payment verification")
    test("empty token returns False", adapter.verify_payment("") is False)

    # 6. Order fulfilment
    print("\n6. Order fulfilment")
    test("empty tx_id rejected", adapter.fulfill_order("123", "") is False)
    test("tx_id >200 chars rejected", adapter.fulfill_order("123", "A" * 201) is False)

    adapter_nocreds = BolcomAlgoVoi(client_id="", client_secret="")
    test("no credentials rejects fulfill", adapter_nocreds.fulfill_order("BOL123", "TX001") is False)

    # 7. SSL
    print("\n7. SSL enforcement")
    test("ssl.create_default_context in source", "create_default_context" in src)

    # 8. No hardcoded secrets
    print("\n8. No hardcoded secrets")
    test("no real API key literals", "algv_iedCPy" not in src)
    test("no real tenant IDs", "96eb0225" not in src)

    # 9. Bol.com-specific API details
    print("\n9. Bol.com-specific features")
    test("Bol.com API URL in source", "api.bol.com" in src)
    test("Bol.com auth URL in source", "login.bol.com/token" in src)
    test("Retailer API v10 header", "retailer.v10" in src)
    test("shipment endpoint", "shipment" in src)
    test("OPEN status filter", "status=OPEN" in src)
    test("client_credentials grant", "client_credentials" in src)

    # 10. Polling returns list on no creds
    print("\n10. Polling")
    adapter_noaccess = BolcomAlgoVoi(client_id="", client_secret="")
    result_poll = adapter_noaccess.poll_orders()
    test("poll_orders returns list", isinstance(result_poll, list))
    result_poll2 = adapter_noaccess.poll_orders(since_datetime="2026-01-01T00:00:00Z")
    test("poll_orders with since returns list", isinstance(result_poll2, list))

    # 11. Default currency fallback
    print("\n11. Default currency fallback")
    adapter_gbp = BolcomAlgoVoi(base_currency="GBP")
    order_nocurr = adapter_gbp.parse_order({
        "orderId": "X1",
        "orderItems": [{"unitPrice": "10.00", "quantity": 1}],
        "currency": "",
    })
    test("empty currency falls back to base_currency", order_nocurr and order_nocurr["currency"] == "GBP")

    # Summary
    print("\n" + "=" * 50)
    print(f"Results: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
