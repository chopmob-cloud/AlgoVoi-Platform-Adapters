"""
Cdiscount AlgoVoi Adapter -- Tests
"""

import hashlib
import hmac as hmac_mod
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from cdiscount_algovoi import CdiscountAlgoVoi, HOSTED_NETWORKS

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

    adapter = CdiscountAlgoVoi(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        cdiscount_api_key="test_api_key",
        cdiscount_api_secret="test_api_secret",
        seller_id="SELLER123",
        webhook_secret="test_secret",
        default_network="algorand_mainnet",
        base_currency="EUR",
    )

    src = open(os.path.join(os.path.dirname(__file__), "cdiscount_algovoi.py")).read()

    print("Cdiscount AlgoVoi Adapter -- Tests")
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
    adapter_nosecret = CdiscountAlgoVoi(webhook_secret="")
    test("empty secret returns None", adapter_nosecret.verify_webhook(b"body", "sig") is None)

    body = b'{"orderId":"cdisc-001","totalAmount":99.99,"currency":"EUR","status":"WaitingAcceptance"}'
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
        "orderId": "CDISC-789",
        "status": "WaitingAcceptance",
        "totalAmount": 79.50,
        "currency": "EUR",
        "buyer": {"email": "acheteur@example.fr"},
    }
    order = adapter.parse_order(order_data)
    test("parses order_id", order and order["order_id"] == "CDISC-789")
    test("parses amount", order and order["amount"] == 79.50)
    test("parses currency", order and order["currency"] == "EUR")
    test("parses status", order and order["status"] == "WaitingAcceptance")
    test("parses buyer_email", order and order["buyer_email"] == "acheteur@example.fr")

    # Missing orderId
    test("missing orderId returns None", adapter.parse_order({}) is None)

    # 'amount' field fallback
    order_data2 = {
        "orderId": "CDISC-000",
        "status": "WaitingAcceptance",
        "amount": 15.00,
        "customer": {"email": "test@test.fr"},
    }
    order2 = adapter.parse_order(order_data2)
    test("amount field fallback", order2 and order2["amount"] == 15.00)
    test("customer dict fallback", order2 and order2["buyer_email"] == "test@test.fr")

    # 5. Payment verification
    print("\n5. Payment verification")
    test("empty token returns False", adapter.verify_payment("") is False)

    # 6. Order fulfilment
    print("\n6. Order fulfilment")
    test("empty tx_id rejected", adapter.fulfill_order("123", "") is False)
    test("tx_id >200 chars rejected", adapter.fulfill_order("123", "A" * 201) is False)

    adapter_nocreds = CdiscountAlgoVoi(cdiscount_api_key="", cdiscount_api_secret="")
    test("no credentials rejects fulfill", adapter_nocreds.fulfill_order("CDISC-001", "TX001") is False)

    # 7. SSL
    print("\n7. SSL enforcement")
    test("ssl.create_default_context in source", "create_default_context" in src)

    # 8. No hardcoded secrets
    print("\n8. No hardcoded secrets")
    test("no real API key literals", "algv_iedCPy" not in src)
    test("no real tenant IDs", "96eb0225" not in src)

    # 9. Cdiscount/Octopia-specific API details
    print("\n9. Cdiscount/Octopia-specific features")
    test("Octopia API URL in source", "api.octopia-io.net" in src)
    test("Octopia auth URL in source", "auth.octopia.com" in src)
    test("SellerId header in source", "SellerId" in src)
    test("WaitingAcceptance status", "WaitingAcceptance" in src)
    test("accept endpoint", "/accept" in src)
    test("ship endpoint", "/ship" in src)
    test("client_credentials grant", "client_credentials" in src)
    test("AlgoVoi carrier name", "AlgoVoi" in src)

    # 10. Polling returns list on no creds
    print("\n10. Polling")
    adapter_noaccess = CdiscountAlgoVoi(cdiscount_api_key="", cdiscount_api_secret="")
    result_poll = adapter_noaccess.poll_orders()
    test("poll_orders returns list", isinstance(result_poll, list))
    result_poll2 = adapter_noaccess.poll_orders(since_datetime="2026-01-01T00:00:00Z")
    test("poll_orders with since returns list", isinstance(result_poll2, list))

    # 11. Default currency fallback
    print("\n11. Default currency fallback")
    adapter_usd = CdiscountAlgoVoi(base_currency="USD")
    order_nocurr = adapter_usd.parse_order({
        "orderId": "X1",
        "totalAmount": 5.00,
        "currency": "",
    })
    test("empty currency falls back to base_currency", order_nocurr and order_nocurr["currency"] == "USD")

    # 12. accept_order requires credentials
    print("\n12. accept_order")
    adapter_nocreds2 = CdiscountAlgoVoi(cdiscount_api_key="", cdiscount_api_secret="")
    test("accept_order no creds returns False", adapter_nocreds2.accept_order("CDISC-001") is False)

    # Summary
    print("\n" + "=" * 50)
    print(f"Results: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
