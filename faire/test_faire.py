"""
Faire AlgoVoi Adapter -- Tests
"""

import hashlib
import hmac as hmac_mod
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from faire_algovoi import FaireAlgoVoi, HOSTED_NETWORKS

PASS = FAIL = 0

def test(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} -- {detail}")


def make_sig(secret, body):
    return hmac_mod.new(secret.encode(), body, hashlib.sha256).hexdigest()


def main():
    global PASS, FAIL

    adapter = FaireAlgoVoi(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        access_token="test_access_token",
        brand_id="test_brand_id",
        webhook_secret="test_secret",
        default_network="algorand_mainnet",
        base_currency="GBP",
    )

    src = open(os.path.join(os.path.dirname(__file__), "faire_algovoi.py")).read()

    print("Faire AlgoVoi Adapter -- Tests")
    print("=" * 50)

    # 1. Network validation
    print("\n1. Network validation")
    test("4 hosted networks", len(HOSTED_NETWORKS) == 4)
    test("algorand_mainnet", "algorand_mainnet" in HOSTED_NETWORKS)
    test("voi_mainnet", "voi_mainnet" in HOSTED_NETWORKS)
    test("hedera_mainnet", "hedera_mainnet" in HOSTED_NETWORKS)
    test("stellar_mainnet", "stellar_mainnet" in HOSTED_NETWORKS)

    # 2. Webhook security
    print("\n2. Webhook security")
    adapter_nosecret = FaireAlgoVoi(webhook_secret="")
    test("empty secret returns None", adapter_nosecret.verify_webhook(b"body", "sig") is None)

    body = b'{"type":"order.created","payload":{"id":"FAIRE-ORD-001","amount_cents":12500,"currency":"GBP","state":"NEW","retailer_id":"RET-99"}}'
    valid_sig = make_sig("test_secret", body)
    result = adapter.verify_webhook(body, valid_sig)
    test("valid HMAC returns payload", result is not None)
    test("wrong HMAC returns None", adapter.verify_webhook(body, "wrong") is None)
    test("empty signature returns None", adapter.verify_webhook(body, "") is None)

    # 3. Timing safety
    print("\n3. Timing safety")
    test("uses hmac.compare_digest", "compare_digest" in src)
    test("uses HMAC-SHA256", "sha256" in src)

    # 4. Order webhook parsing — amount_cents
    print("\n4. Order webhook parsing")
    webhook = {
        "type": "order.created",
        "payload": {
            "id": "FAIRE-ORD-001",
            "amount_cents": 12500,
            "currency": "GBP",
            "state": "NEW",
            "retailer_id": "RET-99",
        },
    }
    order = adapter.parse_order_webhook(webhook)
    test("parses order id", order and order["order_id"] == "FAIRE-ORD-001")
    test("converts amount_cents to major units", order and order["amount"] == 125.00)
    test("parses currency", order and order["currency"] == "GBP")
    test("parses state as status", order and order["status"] == "NEW")
    test("parses retailer_id", order and order["retailer_id"] == "RET-99")
    test("parses event_type", order and order["event_type"] == "order.created")

    # 5. Amount via nested amount dict
    webhook_nested = {
        "type": "order.created",
        "payload": {
            "id": "FAIRE-ORD-002",
            "amount": {"amount_cents": 5000},
            "currency": "USD",
            "state": "OPEN",
        },
    }
    order_nested = adapter.parse_order_webhook(webhook_nested)
    test("nested amount_cents parsed", order_nested and order_nested["amount"] == 50.00)

    # 6. Edge cases
    print("\n5. Edge cases")
    test("empty payload returns None", adapter.parse_order_webhook({}) is None)
    test("missing order id returns None", adapter.parse_order_webhook({"type": "order.created", "payload": {}}) is None)

    # Currency uppercase
    webhook_lower = {
        "type": "order.created",
        "payload": {
            "id": "FAIRE-ORD-003",
            "amount_cents": 1000,
            "currency": "eur",
        },
    }
    order_lower = adapter.parse_order_webhook(webhook_lower)
    test("currency uppercased", order_lower and order_lower["currency"] == "EUR")

    # Fallback to base_currency
    webhook_nocur = {
        "type": "order.created",
        "payload": {"id": "FAIRE-ORD-004", "amount_cents": 2000},
    }
    order_nocur = adapter.parse_order_webhook(webhook_nocur)
    test("fallback to base_currency", order_nocur and order_nocur["currency"] == "GBP")

    # 7. Payment verification
    print("\n6. Payment verification")
    test("empty token returns False", adapter.verify_payment("") is False)

    # 8. Order fulfilment guards
    print("\n7. Order fulfilment")
    test("empty tx_id rejected", adapter.fulfill_order("FAIRE-ORD-001", "") is False)
    test(">200 char tx_id rejected", adapter.fulfill_order("FAIRE-ORD-001", "X" * 201) is False)

    adapter_notoken = FaireAlgoVoi(access_token="", brand_id="bid")
    test("no access_token rejected", adapter_notoken.fulfill_order("ORD-1", "TXID") is False)

    adapter_nobrand = FaireAlgoVoi(access_token="tok", brand_id="")
    test("no brand_id rejected", adapter_nobrand.fulfill_order("ORD-1", "TXID") is False)

    # 9. poll_orders guards
    print("\n8. poll_orders guards")
    adapter_nopoll = FaireAlgoVoi(access_token="", brand_id="")
    test("poll_orders no token returns None", adapter_nopoll.poll_orders() is None)

    adapter_nopoll2 = FaireAlgoVoi(access_token="tok", brand_id="")
    test("poll_orders no brand_id returns None", adapter_nopoll2.poll_orders() is None)

    # 10. SSL enforcement
    print("\n9. SSL enforcement")
    test("ssl.create_default_context used", "create_default_context" in src)

    # 11. No hardcoded secrets
    print("\n10. No hardcoded secrets")
    test("no real API keys", "algv_iedCPy" not in src)
    test("no real tenant IDs", "96eb0225" not in src)

    # 12. Faire-specific
    print("\n11. Faire-specific features")
    test("X-Faire-Hmac-SHA256 header in source", "X-Faire-Hmac-SHA256" in src)
    test("faire.com API URL in source", "faire.com" in src)
    test("X-FAIRE-BRAND-ID header in source", "X-FAIRE-BRAND-ID" in src)
    test("/accept endpoint in source", "/accept" in src)
    test("poll_orders method exists", callable(getattr(adapter, "poll_orders", None)))

    # 13. Version
    print("\n12. Version")
    from faire_algovoi import __version__
    test("version is 1.0.0", __version__ == "1.0.0")

    # Summary
    print("\n" + "=" * 50)
    print(f"Results: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
