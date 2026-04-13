"""
Rakuten AlgoVoi Adapter -- Tests
"""

import hashlib
import hmac as hmac_mod
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from rakuten_algovoi import RakutenAlgoVoi, HOSTED_NETWORKS

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

    adapter = RakutenAlgoVoi(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        service_secret="test_service_secret",
        license_key="test_license_key",
        webhook_secret="test_secret",
        default_network="algorand_mainnet",
        base_currency="JPY",
    )

    src = open(os.path.join(os.path.dirname(__file__), "rakuten_algovoi.py")).read()

    print("Rakuten AlgoVoi Adapter -- Tests")
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
    adapter_nosecret = RakutenAlgoVoi(webhook_secret="")
    test("empty secret returns None", adapter_nosecret.verify_webhook(b"body", "sig") is None)

    body = b'{"orderNumber":"RAK-001","goodsPrice":3500,"currency":"JPY","orderStatus":"100"}'
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
        "orderNumber": "RAK-12345",
        "orderStatus": "100",
        "goodsPrice": 5800,
        "currency": "JPY",
        "mailAddress": "rakuten-buyer@example.jp",
    }
    order = adapter.parse_order(order_data)
    test("parses order_id", order and order["order_id"] == "RAK-12345")
    test("parses amount", order and order["amount"] == 5800.0)
    test("parses currency", order and order["currency"] == "JPY")
    test("parses status", order and order["status"] == "100")
    test("parses buyer_email", order and order["buyer_email"] == "rakuten-buyer@example.jp")

    # Missing orderNumber
    test("missing orderNumber returns None", adapter.parse_order({}) is None)

    # totalPrice fallback
    order_data2 = {
        "orderId": "RAK-99",
        "status": "200",
        "totalPrice": 12000,
        "buyerEmail": "test@rakuten.fr",
    }
    order2 = adapter.parse_order(order_data2)
    test("orderId fallback field", order2 and order2["order_id"] == "RAK-99")
    test("totalPrice fallback", order2 and order2["amount"] == 12000.0)
    test("buyerEmail fallback", order2 and order2["buyer_email"] == "test@rakuten.fr")

    # EUR base currency for rakuten.fr
    adapter_eur = RakutenAlgoVoi(base_currency="EUR")
    order_eur = adapter_eur.parse_order({
        "order_number": "FR-001",
        "amount": 25.00,
        "currency": "",
    })
    test("empty currency falls back to EUR base_currency", order_eur and order_eur["currency"] == "EUR")

    # 5. Payment verification
    print("\n5. Payment verification")
    test("empty token returns False", adapter.verify_payment("") is False)

    # 6. Order fulfilment
    print("\n6. Order fulfilment")
    test("empty tx_id rejected", adapter.fulfill_order("RAK-001", "") is False)
    test("tx_id >200 chars rejected", adapter.fulfill_order("RAK-001", "A" * 201) is False)

    adapter_nocreds = RakutenAlgoVoi(service_secret="", license_key="")
    test("no credentials rejects fulfill", adapter_nocreds.fulfill_order("RAK-001", "TX001") is False)

    # 7. SSL
    print("\n7. SSL enforcement")
    test("ssl.create_default_context in source", "create_default_context" in src)

    # 8. No hardcoded secrets
    print("\n8. No hardcoded secrets")
    test("no real API key literals", "algv_iedCPy" not in src)
    test("no real tenant IDs", "96eb0225" not in src)

    # 9. Rakuten-specific API details
    print("\n9. Rakuten-specific features")
    test("RMS API URL in source", "api.rms.rakuten.co.jp" in src)
    test("searchOrder endpoint in source", "searchOrder" in src)
    test("updateOrder endpoint in source", "updateOrder" in src)
    test("ESA auth scheme in source", "ESA " in src)
    test("service_secret in source", "service_secret" in src)
    test("license_key in source", "license_key" in src)
    test("orderModelList in source", "orderModelList" in src)
    test("AlgoVoi TX reference in source", "AlgoVoi TX" in src)

    # 10. Auth header construction
    print("\n10. Auth header")
    auth = adapter._rms_auth_header()
    test("_rms_auth_header returns non-empty", bool(auth))
    test("_rms_auth_header starts with ESA ", auth.startswith("ESA "))

    adapter_nocreds2 = RakutenAlgoVoi(service_secret="", license_key="")
    auth_empty = adapter_nocreds2._rms_auth_header()
    test("_rms_auth_header no creds returns empty", auth_empty == "")

    # 11. Polling returns list on no creds
    print("\n11. Polling")
    adapter_noaccess = RakutenAlgoVoi(service_secret="", license_key="")
    result_poll = adapter_noaccess.poll_orders()
    test("poll_orders returns list", isinstance(result_poll, list))
    result_poll2 = adapter_noaccess.poll_orders(since_datetime="2026-01-01T00:00:00+0900")
    test("poll_orders with since returns list", isinstance(result_poll2, list))

    # 12. Default JPY currency
    print("\n12. Default currency JPY")
    adapter_jpy = RakutenAlgoVoi(base_currency="JPY")
    test("default base_currency is JPY", adapter_jpy.base_currency == "JPY")

    # Summary
    print("\n" + "=" * 50)
    print(f"Results: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
