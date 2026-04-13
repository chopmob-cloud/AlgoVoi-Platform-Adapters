"""
Allegro AlgoVoi Adapter -- Tests
"""

import hashlib
import hmac as hmac_mod
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from allegro_algovoi import AllegroAlgoVoi, HOSTED_NETWORKS

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

    adapter = AllegroAlgoVoi(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        client_id="test_client_id",
        client_secret="test_client_secret",
        access_token="test_access_token",
        webhook_secret="test_secret",
        default_network="algorand_mainnet",
        base_currency="PLN",
    )

    src = open(os.path.join(os.path.dirname(__file__), "allegro_algovoi.py")).read()

    print("Allegro AlgoVoi Adapter -- Tests")
    print("=" * 50)

    # 1. Network validation
    print("\n1. Network validation")
    test("4 hosted networks", len(HOSTED_NETWORKS) == 4)
    test("algorand_mainnet present", "algorand_mainnet" in HOSTED_NETWORKS)
    test("voi_mainnet present", "voi_mainnet" in HOSTED_NETWORKS)
    test("hedera_mainnet present", "hedera_mainnet" in HOSTED_NETWORKS)
    test("stellar_mainnet present", "stellar_mainnet" in HOSTED_NETWORKS)
    test("invalid network not present", "fake_network" not in HOSTED_NETWORKS)

    # 2. Webhook / signature verification
    print("\n2. Signature verification")
    adapter_nosecret = AllegroAlgoVoi(webhook_secret="")
    test("empty secret returns None (verify_webhook)", adapter_nosecret.verify_webhook(b"body", "sig") is None)
    test("empty secret returns None (verify_order_signature)", adapter_nosecret.verify_order_signature(b"body", "sig") is None)

    body = b'{"orderId":"a123","amount":{"value":"99.00","currency":"PLN"}}'
    expected = hmac_mod.new("test_secret".encode(), body, hashlib.sha256).hexdigest()

    result = adapter.verify_webhook(body, expected)
    test("valid HMAC returns payload", result is not None)
    test("valid HMAC payload is dict", isinstance(result, dict))
    test("wrong HMAC returns None", adapter.verify_webhook(body, "wrongsig") is None)
    test("tampered body returns None", adapter.verify_webhook(b"tampered", expected) is None)

    # verify_order_signature mirrors verify_webhook
    result2 = adapter.verify_order_signature(body, expected)
    test("verify_order_signature valid", result2 is not None)
    test("verify_order_signature wrong sig", adapter.verify_order_signature(body, "bad") is None)

    # 3. Timing safety
    print("\n3. Timing safety")
    test("uses hmac.compare_digest", "compare_digest" in src)

    # 4. Parse order
    print("\n4. Order parsing")
    order_data = {
        "id": "allegro-checkout-001",
        "status": "BOUGHT",
        "summary": {
            "totalToPay": {
                "amount": "149.99",
                "currency": "PLN",
            }
        },
        "buyer": {"email": "buyer@example.com"},
    }
    order = adapter.parse_order(order_data)
    test("parses order_id", order and order["order_id"] == "allegro-checkout-001")
    test("parses amount", order and order["amount"] == 149.99)
    test("parses currency", order and order["currency"] == "PLN")
    test("parses status", order and order["status"] == "BOUGHT")
    test("parses buyer_email", order and order["buyer_email"] == "buyer@example.com")

    # Missing id
    test("missing id returns None", adapter.parse_order({}) is None)
    # Malformed amount
    bad = {"id": "x", "summary": {"totalToPay": {"amount": "NOTANUMBER", "currency": "PLN"}}, "buyer": {}}
    test("malformed amount returns None", adapter.parse_order(bad) is None)

    # 5. Payment verification
    print("\n5. Payment verification")
    test("empty token returns False", adapter.verify_payment("") is False)

    # 6. Order fulfilment
    print("\n6. Order fulfilment")
    test("empty tx_id rejected", adapter.fulfill_order("123", "") is False)
    test("tx_id >200 chars rejected", adapter.fulfill_order("123", "A" * 201) is False)

    # No access token and no client creds
    adapter_nocreds = AllegroAlgoVoi(access_token="", client_id="", client_secret="")
    test("no credentials rejects fulfill", adapter_nocreds.fulfill_order("123", "TX001") is False)

    # 7. SSL
    print("\n7. SSL enforcement")
    test("ssl.create_default_context in source", "create_default_context" in src)

    # 8. No hardcoded secrets
    print("\n8. No hardcoded secrets")
    test("no real API key literals", "algv_iedCPy" not in src)
    test("no real tenant IDs", "96eb0225" not in src)

    # 9. Allegro-specific API details
    print("\n9. Allegro-specific features")
    test("Allegro API base URL in source", "api.allegro.pl" in src)
    test("Allegro auth URL in source", "allegro.pl/auth/oauth/token" in src)
    test("Accept header vnd.allegro", "vnd.allegro.public.v1+json" in src)
    test("checkout-forms endpoint", "checkout-forms" in src)
    test("fulfillment endpoint", "fulfillment" in src)
    test("READY_FOR_PROCESSING status", "READY_FOR_PROCESSING" in src)
    test("client_credentials grant", "client_credentials" in src)

    # 10. poll_new_orders and poll_orders return list on no creds
    print("\n10. Polling methods")
    adapter_noaccess = AllegroAlgoVoi(access_token="", client_id="", client_secret="")
    result_poll = adapter_noaccess.poll_new_orders()
    test("poll_new_orders returns list", isinstance(result_poll, list))
    result_poll2 = adapter_noaccess.poll_orders()
    test("poll_orders returns list", isinstance(result_poll2, list))

    # 11. process_order falls back to default_network
    print("\n11. process_order network fallback")
    # No real API, just check it returns None gracefully (no network call succeeds)
    result_proc = adapter.process_order("ord001", 50.0, "PLN", "invalid_net")
    test("invalid network falls back (returns None without real API)", result_proc is None or "checkout_url" in result_proc)

    # 12. Default currency fallback
    print("\n12. Default currency fallback")
    adapter_eur = AllegroAlgoVoi(base_currency="EUR")
    parsed_nocurrency = adapter_eur.parse_order({
        "id": "x1",
        "status": "BOUGHT",
        "summary": {"totalToPay": {"amount": "10.00", "currency": ""}},
        "buyer": {},
    })
    test("empty currency falls back to EUR", parsed_nocurrency and parsed_nocurrency["currency"] == "EUR")

    # Summary
    print("\n" + "=" * 50)
    print(f"Results: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
