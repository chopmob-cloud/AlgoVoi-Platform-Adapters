"""
Ecwid AlgoVoi Adapter -- Tests
"""

import base64
import hashlib
import hmac as hmac_mod
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from ecwid_algovoi import EcwidAlgoVoi, HOSTED_NETWORKS

PASS = FAIL = 0

def test(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} -- {detail}")


def make_sig_b64(secret, body):
    """Ecwid signature: base64(HMAC-SHA256(secret, body))"""
    digest = hmac_mod.new(secret.encode(), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def main():
    global PASS, FAIL

    adapter = EcwidAlgoVoi(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        store_id="12345678",
        client_secret="test_client_secret",
        webhook_secret="test_secret",
        default_network="algorand_mainnet",
        base_currency="USD",
    )

    src = open(os.path.join(os.path.dirname(__file__), "ecwid_algovoi.py")).read()

    print("Ecwid AlgoVoi Adapter -- Tests")
    print("=" * 50)

    # 1. Network validation
    print("\n1. Network validation")
    test("4 hosted networks", len(HOSTED_NETWORKS) == 4)
    test("algorand_mainnet", "algorand_mainnet" in HOSTED_NETWORKS)
    test("voi_mainnet", "voi_mainnet" in HOSTED_NETWORKS)
    test("hedera_mainnet", "hedera_mainnet" in HOSTED_NETWORKS)
    test("stellar_mainnet", "stellar_mainnet" in HOSTED_NETWORKS)

    # 2. Webhook security — base64 signature
    print("\n2. Webhook security")
    adapter_nosecret = EcwidAlgoVoi(webhook_secret="")
    test("empty secret returns None", adapter_nosecret.verify_webhook(b"body", "sig") is None)

    body = b'{"eventType":"UNFINISHED_ORDER_CREATED","entityId":98765,"storeId":12345678}'
    valid_sig = make_sig_b64("test_secret", body)
    result = adapter.verify_webhook(body, valid_sig)
    test("valid base64 HMAC returns payload", result is not None)
    test("wrong signature returns None", adapter.verify_webhook(body, "wrongsig==") is None)
    test("empty signature returns None", adapter.verify_webhook(body, "") is None)

    # 3. Timing safety
    print("\n3. Timing safety")
    test("uses hmac.compare_digest", "compare_digest" in src)
    test("uses HMAC-SHA256", "sha256" in src)
    test("base64 encoding used", "base64" in src)

    # 4. Order webhook parsing — entityId only
    print("\n4. Order webhook parsing")
    webhook = {
        "eventType": "UNFINISHED_ORDER_CREATED",
        "entityId": 98765,
        "storeId": 12345678,
    }
    order = adapter.parse_order_webhook(webhook)
    test("parses entityId as order_id", order and order["order_id"] == "98765")
    test("parses eventType", order and order["event_type"] == "UNFINISHED_ORDER_CREATED")
    test("parses storeId", order and order["store_id"] == "12345678")

    # 5. Order with embedded data
    webhook_data = {
        "eventType": "ORDER_CREATED",
        "entityId": 11111,
        "storeId": 12345678,
        "data": {"total": 79.99, "currency": "GBP"},
    }
    order_data = adapter.parse_order_webhook(webhook_data)
    test("parses embedded total", order_data and order_data["amount"] == 79.99)
    test("parses embedded currency", order_data and order_data["currency"] == "GBP")

    # 6. Edge cases
    print("\n5. Edge cases")
    test("empty payload returns None", adapter.parse_order_webhook({}) is None)
    test("missing entityId returns None", adapter.parse_order_webhook({"eventType": "ORDER_CREATED"}) is None)

    # Currency uppercase
    webhook_lower = {
        "eventType": "ORDER_CREATED",
        "entityId": 22222,
        "data": {"total": 10.0, "currency": "eur"},
    }
    order_lower = adapter.parse_order_webhook(webhook_lower)
    test("currency uppercased", order_lower and order_lower["currency"] == "EUR")

    # Fallback currency
    webhook_nocur = {"eventType": "ORDER_CREATED", "entityId": 33333}
    order_nocur = adapter.parse_order_webhook(webhook_nocur)
    test("fallback to base_currency", order_nocur and order_nocur["currency"] == "USD")

    # 7. Payment verification
    print("\n6. Payment verification")
    test("empty token returns False", adapter.verify_payment("") is False)

    # 8. fetch_order guards
    print("\n7. fetch_order guards")
    adapter_nostoreid = EcwidAlgoVoi(store_id="", client_secret="tok")
    test("fetch_order no store_id returns None", adapter_nostoreid.fetch_order("99") is None)

    adapter_nosecret2 = EcwidAlgoVoi(store_id="123", client_secret="")
    test("fetch_order no client_secret returns None", adapter_nosecret2.fetch_order("99") is None)

    # 9. Order fulfilment guards
    print("\n8. Order fulfilment")
    test("empty tx_id rejected", adapter.fulfill_order("99", "") is False)
    test(">200 char tx_id rejected", adapter.fulfill_order("99", "X" * 201) is False)

    adapter_nofulfill = EcwidAlgoVoi(store_id="", client_secret="")
    test("no store_id rejected", adapter_nofulfill.fulfill_order("99", "TXID") is False)

    adapter_nofulfill2 = EcwidAlgoVoi(store_id="123", client_secret="")
    test("no client_secret rejected", adapter_nofulfill2.fulfill_order("99", "TXID") is False)

    # 10. SSL enforcement
    print("\n9. SSL enforcement")
    test("ssl.create_default_context used", "create_default_context" in src)

    # 11. No hardcoded secrets
    print("\n10. No hardcoded secrets")
    test("no real API keys", "algv_iedCPy" not in src)
    test("no real tenant IDs", "96eb0225" not in src)

    # 12. Ecwid-specific
    print("\n11. Ecwid-specific features")
    test("X-Ecwid-Webhook-Signature header in source", "X-Ecwid-Webhook-Signature" in src or "X-Ecwid-Signature" in src)
    test("app.ecwid.com URL in source", "app.ecwid.com" in src)
    test("entityId field handled in source", "entityId" in src)
    test("paymentStatus PAID in source", "PAID" in src)
    test("PUT method used for fulfill", '"PUT"' in src)
    test("fetch_order method exists", callable(getattr(adapter, "fetch_order", None)))

    # 13. Version
    print("\n12. Version")
    from ecwid_algovoi import __version__
    test("version is 1.0.0", __version__ == "1.0.0")

    # Summary
    print("\n" + "=" * 50)
    print(f"Results: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
