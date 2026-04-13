"""
Walmart AlgoVoi Adapter -- Tests
"""

import hashlib
import hmac as hmac_mod
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from walmart_algovoi import WalmartAlgoVoi, HOSTED_NETWORKS

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

    adapter = WalmartAlgoVoi(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        client_id="test_client_id",
        client_secret="test_client_secret",
        webhook_secret="test_secret",
        default_network="algorand_mainnet",
        base_currency="USD",
    )

    src = open(os.path.join(os.path.dirname(__file__), "walmart_algovoi.py")).read()

    print("Walmart AlgoVoi Adapter -- Tests")
    print("=" * 50)

    # 1. Network validation
    print("\n1. Network validation")
    test("4 hosted networks", len(HOSTED_NETWORKS) == 4)
    test("algorand_mainnet", "algorand_mainnet" in HOSTED_NETWORKS)
    test("voi_mainnet", "voi_mainnet" in HOSTED_NETWORKS)
    test("hedera_mainnet", "hedera_mainnet" in HOSTED_NETWORKS)
    test("stellar_mainnet", "stellar_mainnet" in HOSTED_NETWORKS)

    # 2. Webhook security — HMAC mode
    print("\n2. Webhook security")
    adapter_nosecret = WalmartAlgoVoi(webhook_secret="")
    test("empty secret returns None", adapter_nosecret.verify_webhook(b"body", "sig") is None)

    body = b'{"eventType":"PO_CREATED","order":{"purchaseOrderId":"PO-001","orderLines":{"orderLine":[{"charges":{"charge":[{"chargeType":"PRODUCT","chargeAmount":{"currency":"USD","amount":29.99}}]}}]}}}'
    valid_hmac = make_sig("test_secret", body)
    result_hmac = adapter.verify_webhook(body, valid_hmac)
    test("valid HMAC returns payload", result_hmac is not None)
    test("wrong HMAC returns None", adapter.verify_webhook(body, "wrong_sig") is None)

    # 3. Bearer token fallback mode
    print("\n3. Bearer token fallback")
    result_bearer = adapter.verify_webhook(body, "test_secret")
    test("bearer token (verbatim secret) passes", result_bearer is not None)
    test("wrong bearer token fails", adapter.verify_webhook(body, "not_the_secret") is None)

    # 4. Timing safety
    print("\n4. Timing safety")
    test("uses hmac.compare_digest", "compare_digest" in src)
    test("uses HMAC-SHA256", "sha256" in src)

    # 5. Order webhook parsing
    print("\n5. Order webhook parsing")
    webhook = {
        "eventType": "PO_CREATED",
        "order": {
            "purchaseOrderId": "PO-12345",
            "customerOrderId": "CO-999",
            "orderDate": "2026-04-01T10:00:00Z",
            "orderLines": {
                "orderLine": [
                    {
                        "charges": {
                            "charge": [
                                {
                                    "chargeType": "PRODUCT",
                                    "chargeAmount": {"currency": "USD", "amount": 49.99},
                                }
                            ]
                        }
                    },
                    {
                        "charges": {
                            "charge": [
                                {
                                    "chargeType": "PRODUCT",
                                    "chargeAmount": {"currency": "USD", "amount": 15.00},
                                }
                            ]
                        }
                    },
                ]
            },
        },
    }
    order = adapter.parse_order_webhook(webhook)
    test("parses purchaseOrderId", order and order["order_id"] == "PO-12345")
    test("parses customerOrderId", order and order["customer_order_id"] == "CO-999")
    test("sums PRODUCT charges", order and order["amount"] == 64.99)
    test("parses currency", order and order["currency"] == "USD")
    test("parses eventType", order and order["event_type"] == "PO_CREATED")
    test("parses orderDate", order and order["order_date"] == "2026-04-01T10:00:00Z")

    # 6. Shipping charge excluded from total
    webhook_mixed = {
        "eventType": "PO_CREATED",
        "order": {
            "purchaseOrderId": "PO-222",
            "orderLines": {
                "orderLine": [{
                    "charges": {
                        "charge": [
                            {"chargeType": "PRODUCT", "chargeAmount": {"currency": "USD", "amount": 20.00}},
                            {"chargeType": "SHIPPING", "chargeAmount": {"currency": "USD", "amount": 5.00}},
                        ]
                    }
                }]
            },
        },
    }
    order_mixed = adapter.parse_order_webhook(webhook_mixed)
    test("shipping charge excluded", order_mixed and order_mixed["amount"] == 20.00)

    # 7. Edge cases
    print("\n6. Edge cases")
    test("empty payload returns None", adapter.parse_order_webhook({}) is None)
    test("no order key returns None", adapter.parse_order_webhook({"eventType": "PO_CREATED"}) is None)
    test("missing purchaseOrderId returns None", adapter.parse_order_webhook({"order": {"foo": "bar"}}) is None)

    # Currency uppercase
    webhook_lower = {
        "eventType": "PO_CREATED",
        "order": {
            "purchaseOrderId": "PO-333",
            "orderLines": {
                "orderLine": [{
                    "charges": {"charge": [{"chargeType": "PRODUCT", "chargeAmount": {"currency": "usd", "amount": 10.0}}]}
                }]
            },
        },
    }
    order_lower = adapter.parse_order_webhook(webhook_lower)
    test("currency uppercased", order_lower and order_lower["currency"] == "USD")

    # 8. Payment verification
    print("\n7. Payment verification")
    test("empty token returns False", adapter.verify_payment("") is False)

    # 9. Order fulfilment guards
    print("\n8. Order fulfilment")
    test("empty tx_id rejected", adapter.fulfill_order("PO-123", "") is False)
    test(">200 char tx_id rejected", adapter.fulfill_order("PO-123", "X" * 201) is False)

    adapter_nocreds = WalmartAlgoVoi(client_id="", client_secret="")
    test("no client_id rejected", adapter_nocreds.fulfill_order("PO-123", "TXID") is False)

    adapter_nosecret2 = WalmartAlgoVoi(client_id="id", client_secret="")
    test("no client_secret rejected", adapter_nosecret2.fulfill_order("PO-123", "TXID") is False)

    # 10. SSL enforcement
    print("\n9. SSL enforcement")
    test("ssl.create_default_context used", "create_default_context" in src)

    # 11. No hardcoded secrets
    print("\n10. No hardcoded secrets")
    test("no real API keys", "algv_iedCPy" not in src)
    test("no real tenant IDs", "96eb0225" not in src)

    # 12. Walmart-specific
    print("\n11. Walmart-specific features")
    test("WM_SEC.AUTH_SIGNATURE header in source", "WM_SEC.AUTH_SIGNATURE" in src or "WM-SEC" in src)
    test("marketplace.walmartapis.com in source", "marketplace.walmartapis.com" in src)
    test("PO_CREATED event type in source", "PO_CREATED" in src)
    test("client_credentials grant in source", "client_credentials" in src)
    test("orderLines parsing in source", "orderLines" in src)

    # 13. Version
    print("\n12. Version")
    from walmart_algovoi import __version__
    test("version is 1.0.0", __version__ == "1.0.0")

    # Summary
    print("\n" + "=" * 50)
    print(f"Results: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
