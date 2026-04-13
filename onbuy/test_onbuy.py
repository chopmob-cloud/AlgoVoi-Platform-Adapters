"""
OnBuy AlgoVoi Adapter -- Tests
"""

import hashlib
import hmac as hmac_mod
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from onbuy_algovoi import OnbuyAlgoVoi, HOSTED_NETWORKS

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

    adapter = OnbuyAlgoVoi(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        site_id="2000",
        onbuy_api_key="test_api_key",
        webhook_secret="test_secret",
        default_network="algorand_mainnet",
        base_currency="GBP",
    )

    src = open(os.path.join(os.path.dirname(__file__), "onbuy_algovoi.py")).read()

    print("OnBuy AlgoVoi Adapter -- Tests")
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
    adapter_nosecret = OnbuyAlgoVoi(webhook_secret="")
    test("empty secret returns None", adapter_nosecret.verify_webhook(b"body", "sig") is None)

    body = b'{"order_id":"onbuy-001","total":59.99,"currency_code":"GBP","order_status":"awaiting_dispatch"}'
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
        "order_id": "ONBUY-12345",
        "order_status": "awaiting_dispatch",
        "total": 34.99,
        "currency_code": "GBP",
        "buyer_email": "buyer@onbuy.com",
    }
    order = adapter.parse_order(order_data)
    test("parses order_id", order and order["order_id"] == "ONBUY-12345")
    test("parses amount", order and order["amount"] == 34.99)
    test("parses currency", order and order["currency"] == "GBP")
    test("parses status", order and order["status"] == "awaiting_dispatch")
    test("parses buyer_email", order and order["buyer_email"] == "buyer@onbuy.com")

    # Missing order_id
    test("missing order_id returns None", adapter.parse_order({}) is None)

    # order_total field fallback
    order_data2 = {
        "id": "ONBUY-99",
        "status": "awaiting_dispatch",
        "order_total": "22.50",
        "currency": "GBP",
        "email": "test@test.com",
    }
    order2 = adapter.parse_order(order_data2)
    test("order_total field fallback", order2 and order2["amount"] == 22.50)
    test("id field fallback", order2 and order2["order_id"] == "ONBUY-99")
    test("email field fallback", order2 and order2["buyer_email"] == "test@test.com")

    # 5. Payment verification
    print("\n5. Payment verification")
    test("empty token returns False", adapter.verify_payment("") is False)

    # 6. Order fulfilment
    print("\n6. Order fulfilment")
    test("empty tx_id rejected", adapter.fulfill_order("123", "") is False)
    test("tx_id >200 chars rejected", adapter.fulfill_order("123", "A" * 201) is False)

    adapter_nocreds = OnbuyAlgoVoi(onbuy_api_key="")
    test("no credentials rejects fulfill", adapter_nocreds.fulfill_order("ONBUY-001", "TX001") is False)

    # 7. SSL
    print("\n7. SSL enforcement")
    test("ssl.create_default_context in source", "create_default_context" in src)

    # 8. No hardcoded secrets
    print("\n8. No hardcoded secrets")
    test("no real API key literals", "algv_iedCPy" not in src)
    test("no real tenant IDs", "96eb0225" not in src)

    # 9. OnBuy-specific API details
    print("\n9. OnBuy-specific features")
    test("OnBuy API URL in source", "api.onbuy.com" in src)
    test("OnBuy auth URL in source", "onbuy.com/v2/oauth/token" in src)
    test("site_id in source", "site_id" in src)
    test("default site_id 2000", "2000" in src)
    test("awaiting_dispatch status", "awaiting_dispatch" in src)
    test("dispatch endpoint", "/dispatch" in src)
    test("client_credentials grant", "client_credentials" in src)
    test("AlgoVoi courier name", "AlgoVoi" in src)

    # 10. HMAC request signing
    print("\n10. HMAC request signing")
    sig = adapter._sign_request("GET", "/v2/orders", b"")
    test("_sign_request returns non-empty string", isinstance(sig, str) and len(sig) > 0)
    adapter_nokey = OnbuyAlgoVoi(onbuy_api_key="")
    sig_empty = adapter_nokey._sign_request("GET", "/v2/orders", b"")
    test("_sign_request no key returns empty", sig_empty == "")

    # 11. Polling returns list on no creds
    print("\n11. Polling")
    adapter_noaccess = OnbuyAlgoVoi(onbuy_api_key="")
    result_poll = adapter_noaccess.poll_orders()
    test("poll_orders returns list", isinstance(result_poll, list))
    result_poll2 = adapter_noaccess.poll_orders(since_datetime="2026-01-01T00:00:00Z")
    test("poll_orders with since returns list", isinstance(result_poll2, list))

    # 12. Default currency fallback
    print("\n12. Default currency fallback")
    adapter_eur = OnbuyAlgoVoi(base_currency="EUR")
    order_nocurr = adapter_eur.parse_order({
        "order_id": "X1",
        "total": 5.00,
        "currency_code": "",
    })
    test("empty currency_code falls back to base_currency", order_nocurr and order_nocurr["currency"] == "EUR")

    # Summary
    print("\n" + "=" * 50)
    print(f"Results: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
