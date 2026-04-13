"""
Mercado Libre AlgoVoi Adapter -- Tests
"""

import hashlib
import hmac as hmac_mod
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from mercadolibre_algovoi import MercadoLibreAlgoVoi, HOSTED_NETWORKS

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

    adapter = MercadoLibreAlgoVoi(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        access_token="test_access_token",
        client_secret="test_client_secret",
        webhook_secret="test_secret",
        default_network="algorand_mainnet",
        base_currency="BRL",
    )

    src = open(os.path.join(os.path.dirname(__file__), "mercadolibre_algovoi.py")).read()

    print("Mercado Libre AlgoVoi Adapter -- Tests")
    print("=" * 50)

    # 1. Network validation
    print("\n1. Network validation")
    test("4 hosted networks", len(HOSTED_NETWORKS) == 4)
    test("algorand", "algorand_mainnet" in HOSTED_NETWORKS)
    test("voi", "voi_mainnet" in HOSTED_NETWORKS)
    test("hedera", "hedera_mainnet" in HOSTED_NETWORKS)
    test("stellar", "stellar_mainnet" in HOSTED_NETWORKS)

    # 2. Webhook security — plain HMAC fallback
    print("\n2. Webhook security")
    adapter_nosecret = MercadoLibreAlgoVoi(webhook_secret="")
    test("empty secret returns None", adapter_nosecret.verify_webhook(b"body", "sig") is None)

    body = b'{"resource":"/orders/1234567890","user_id":123456789,"topic":"orders_v2"}'
    plain_sig = hmac_mod.new("test_secret".encode(), body, hashlib.sha256).hexdigest()
    result = adapter.verify_webhook(body, plain_sig)
    test("valid plain HMAC returns payload", result is not None)
    test("wrong HMAC returns None", adapter.verify_webhook(body, "wrong") is None)

    # 3. x-signature ts/v1 format
    print("\n3. x-signature ts/v1 format")
    # Build a valid ts/v1 signature
    body2 = b'{"resource":"/orders/9876","user_id":111,"topic":"orders_v2","data":{"id":"9876"}}'
    ts = "1640995200"
    data_id = "9876"
    sign_template = f"id:{data_id};request-id:{ts};ts:{ts};"
    v1_hex = hmac_mod.new("test_secret".encode(), sign_template.encode(), hashlib.sha256).hexdigest()
    xsig = f"ts={ts},v1={v1_hex}"
    result2 = adapter.verify_webhook(body2, xsig)
    test("valid ts/v1 signature returns payload", result2 is not None)
    bad_xsig = f"ts={ts},v1=badhex"
    result3 = adapter.verify_webhook(body2, bad_xsig)
    test("invalid ts/v1 v1 hash returns None", result3 is None)

    # 4. Timing safety
    print("\n4. Timing safety")
    test("uses hmac.compare_digest", "compare_digest" in src)

    # 5. Parse order webhook
    print("\n5. Order webhook parsing")
    webhook = {
        "resource": "/orders/1234567890",
        "user_id": 123456789,
        "topic": "orders_v2",
        "application_id": 987654321,
        "sent": "2024-01-15T10:30:00.000Z",
    }
    order = adapter.parse_order_webhook(webhook)
    test("parses order_id from resource URL", order and order["order_id"] == "1234567890")
    test("parses topic", order and order["topic"] == "orders_v2")
    test("parses user_id", order and order["user_id"] == "123456789")
    test("parses application_id", order and order["application_id"] == "987654321")
    test("parses sent", order and order["sent"] == "2024-01-15T10:30:00.000Z")
    test("default status is pending", order and order["status"] == "pending")

    # 6. Nested data.id path
    webhook2 = {
        "data": {"id": "9999999"},
        "topic": "orders_v2",
        "user_id": 555,
    }
    order2 = adapter.parse_order_webhook(webhook2)
    test("parses order_id from data.id", order2 and order2["order_id"] == "9999999")

    # 7. Invalid webhooks
    print("\n7. Invalid webhook payloads")
    test("empty payload returns None", adapter.parse_order_webhook({}) is None)
    test("unknown topic returns None", adapter.parse_order_webhook({"topic": "questions", "resource": "/q/1"}) is None)

    # 8. Payment verification
    print("\n8. Payment verification")
    test("empty token returns False", adapter.verify_payment("") is False)

    # 9. Order fulfilment
    print("\n9. Order fulfilment")
    test("empty tx_id rejected", adapter.fulfill_order("ML-123", "") is False)
    test(">200 char tx_id rejected", adapter.fulfill_order("ML-123", "A" * 201) is False)

    # No access token
    adapter_nokey = MercadoLibreAlgoVoi(access_token="")
    test("no access_token rejected", adapter_nokey.fulfill_order("ML-123", "TXID") is False)

    # 10. SSL
    print("\n10. SSL enforcement")
    test("ssl.create_default_context", "create_default_context" in src)

    # 11. No hardcoded secrets
    print("\n11. No hardcoded secrets")
    test("no real API keys", "algv_iedCPy" not in src)
    test("no real tenant IDs", "96eb0225" not in src)

    # 12. Mercado Libre-specific features
    print("\n12. Mercado Libre-specific features")
    test("x-signature header", "x-signature" in src)
    test("Mercado Libre API base URL", "api.mercadolibre.com" in src)
    test("orders_v2 topic", "orders_v2" in src)
    test("Shipments API endpoint", "shipments" in src)
    test("access_token param", "access_token" in src)
    test("client_secret param", "client_secret" in src)

    # 13. Version
    print("\n13. Version")
    from mercadolibre_algovoi import __version__
    test("__version__ is 1.0.0", __version__ == "1.0.0")

    # 14. Webhook body parse edge cases
    print("\n14. Webhook body parse edge cases")
    bad_json = b"not-json"
    test("invalid JSON body returns None — plain HMAC path", adapter.verify_webhook(
        bad_json,
        hmac_mod.new("test_secret".encode(), bad_json, hashlib.sha256).hexdigest()
    ) is None)

    # 15. CHAIN_LABELS
    print("\n15. CHAIN_LABELS")
    from mercadolibre_algovoi import CHAIN_LABELS
    test("algorand label set", "algorand_mainnet" in CHAIN_LABELS)
    test("voi label set", "voi_mainnet" in CHAIN_LABELS)

    # Summary
    print("\n" + "=" * 50)
    print(f"Results: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
