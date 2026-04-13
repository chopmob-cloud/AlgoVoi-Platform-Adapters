"""
eBay AlgoVoi Adapter -- Tests
"""

import hashlib
import hmac as hmac_mod
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from ebay_algovoi import EbayAlgoVoi, HOSTED_NETWORKS

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

    adapter = EbayAlgoVoi(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        access_token="test_access_token",
        client_secret="test_client_secret",
        webhook_secret="test_secret",
        default_network="algorand_mainnet",
        base_currency="GBP",
    )

    src = open(os.path.join(os.path.dirname(__file__), "ebay_algovoi.py")).read()

    print("eBay AlgoVoi Adapter -- Tests")
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
    adapter_nosecret = EbayAlgoVoi(webhook_secret="")
    test("empty secret returns None", adapter_nosecret.verify_webhook(b"body", "sig") is None)

    import base64 as _b64, json as _json
    body = b'{"notification":{"topic":"checkout.order.created","data":{"orderId":"ORD-123","pricingSummary":{"total":{"value":"49.99","currency":"GBP"}}}}}'

    # ECDSA structural validation path (valid base64 JSON with required keys)
    ecdsa_payload = _b64.b64encode(_json.dumps({"alg":"ECDSA","kid":"test-kid","signature":"fakesig","digest":"SHA1"}).encode()).decode()
    result_ecdsa = adapter.verify_webhook(body, ecdsa_payload)
    test("valid ECDSA-structure header returns payload", result_ecdsa is not None)

    # Fallback HMAC path (non-base64-JSON sig falls through to HMAC check)
    valid_sig = make_sig("test_secret", body)
    result = adapter.verify_webhook(body, valid_sig)
    test("HMAC fallback valid sig returns payload", result is not None)
    test("HMAC fallback wrong sig returns None", adapter.verify_webhook(body, "wrong") is None)
    test("empty signature returns None", adapter.verify_webhook(body, "") is None)

    # 3. Timing safety
    print("\n3. Timing safety")
    test("uses hmac.compare_digest", "compare_digest" in src)
    test("uses HMAC-SHA256", "sha256" in src)

    # 4. Challenge-response
    print("\n4. Challenge-response")
    challenge = adapter.handle_challenge("testcode", "https://example.com/webhook/ebay")
    test("challenge returns non-empty string", isinstance(challenge, str) and len(challenge) > 0)
    test("challenge is hex", all(c in "0123456789abcdef" for c in (challenge or "")))

    adapter_nosecret2 = EbayAlgoVoi(webhook_secret="")
    test("challenge with empty secret returns None", adapter_nosecret2.handle_challenge("code", "url") is None)
    test("challenge with empty code returns None", adapter.handle_challenge("", "url") is None)

    # 5. Deterministic challenge
    ch1 = adapter.handle_challenge("abc", "https://example.com/wh")
    ch2 = adapter.handle_challenge("abc", "https://example.com/wh")
    test("challenge is deterministic", ch1 == ch2)

    # 6. Order webhook parsing
    print("\n5. Order webhook parsing")
    webhook = {
        "notification": {
            "topic": "checkout.order.created",
            "data": {
                "orderId": "ORD-EBAY-456",
                "pricingSummary": {
                    "total": {"value": "89.50", "currency": "GBP"}
                },
                "orderFulfillmentStatus": "NOT_STARTED",
                "buyer": {"username": "buyer123"},
            },
        }
    }
    order = adapter.parse_order_webhook(webhook)
    test("parses order ID", order and order["order_id"] == "ORD-EBAY-456")
    test("parses amount", order and order["amount"] == 89.50)
    test("parses currency", order and order["currency"] == "GBP")
    test("parses status", order and order["status"] == "NOT_STARTED")
    test("parses buyer_username", order and order["buyer_username"] == "buyer123")
    test("parses topic", order and order["topic"] == "checkout.order.created")

    # 7. Edge cases
    print("\n6. Edge cases")
    test("empty payload returns None", adapter.parse_order_webhook({}) is None)
    test("no orderId returns None", adapter.parse_order_webhook({"notification": {"data": {}}}) is None)

    # Amount missing gracefully
    webhook_noamt = {
        "notification": {
            "data": {"orderId": "ORD-999"},
        }
    }
    order_noamt = adapter.parse_order_webhook(webhook_noamt)
    test("missing amount defaults to 0", order_noamt and order_noamt["amount"] == 0.0)

    # 8. Payment verification
    print("\n7. Payment verification")
    test("empty token returns False", adapter.verify_payment("") is False)

    # 9. Order fulfilment guards
    print("\n8. Order fulfilment")
    test("empty tx_id rejected", adapter.fulfill_order("ORD-123", "") is False)
    test(">200 char tx_id rejected", adapter.fulfill_order("ORD-123", "X" * 201) is False)

    adapter_notoken = EbayAlgoVoi(access_token="")
    test("no access_token rejected", adapter_notoken.fulfill_order("ORD-123", "TXID") is False)

    # 10. SSL enforcement
    print("\n9. SSL enforcement")
    test("ssl.create_default_context used", "create_default_context" in src)

    # 11. No hardcoded secrets
    print("\n10. No hardcoded secrets")
    test("no real API keys", "algv_iedCPy" not in src)
    test("no real tenant IDs", "96eb0225" not in src)

    # 12. eBay-specific
    print("\n11. eBay-specific features")
    test("X-EBAY-SIGNATURE header in source", "X-EBAY-SIGNATURE" in src)
    test("ECDSA structural validation in source", "ECDSA" in src)
    test("sell/fulfillment/v1 endpoint in source", "sell/fulfillment/v1" in src)
    test("shipping_fulfillment in source", "shipping_fulfillment" in src)
    test("challengeResponse in source", "challengeResponse" in src)
    test("challenge_code handling in source", "challenge_code" in src)

    # 13. Version
    print("\n12. Version")
    from ebay_algovoi import __version__
    test("version is 1.0.0", __version__ == "1.0.0")

    # Summary
    print("\n" + "=" * 50)
    print(f"Results: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
