"""
WhatsApp AlgoVoi Adapter -- Tests
"""

import hashlib
import hmac as hmac_mod
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from whatsapp_algovoi import WhatsAppAlgoVoi, HOSTED_NETWORKS, GRAPH_API_BASE

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
    return "sha256=" + hmac_mod.new(secret.encode(), body, hashlib.sha256).hexdigest()


def main():
    global PASS, FAIL

    adapter = WhatsAppAlgoVoi(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        whatsapp_token="wa_test_token",
        phone_number_id="12345678901",
        verify_token="verify_me",
        webhook_secret="test_secret",
        default_network="algorand_mainnet",
        base_currency="GBP",
    )

    src = open(os.path.join(os.path.dirname(__file__), "whatsapp_algovoi.py")).read()

    print("WhatsApp AlgoVoi Adapter -- Tests")
    print("=" * 50)

    # 1. Network validation
    print("\n1. Network validation")
    test("4 hosted networks", len(HOSTED_NETWORKS) == 4)
    test("algorand_mainnet", "algorand_mainnet" in HOSTED_NETWORKS)
    test("voi_mainnet", "voi_mainnet" in HOSTED_NETWORKS)
    test("hedera_mainnet", "hedera_mainnet" in HOSTED_NETWORKS)
    test("stellar_mainnet", "stellar_mainnet" in HOSTED_NETWORKS)

    # 2. Webhook challenge verification
    print("\n2. Webhook challenge")
    test("valid challenge returns challenge",
         adapter.verify_webhook_challenge("subscribe", "verify_me", "abc123") == "abc123")
    test("wrong token returns None",
         adapter.verify_webhook_challenge("subscribe", "bad_token", "abc123") is None)
    test("wrong mode returns None",
         adapter.verify_webhook_challenge("other", "verify_me", "abc123") is None)

    # 3. Webhook signature verification
    print("\n3. Webhook HMAC verification")
    adapter_nosecret = WhatsAppAlgoVoi(webhook_secret="")
    body = b'{"object":"whatsapp_business_account","entry":[]}'
    test("empty secret returns None",
         adapter_nosecret.verify_webhook(body, make_sig("test_secret", body)) is None)

    sig = make_sig("test_secret", body)
    result = adapter.verify_webhook(body, sig)
    test("valid HMAC returns payload", result is not None)
    test("wrong HMAC returns None", adapter.verify_webhook(body, "sha256=wrong") is None)
    test("no sha256= prefix still works",
         adapter.verify_webhook(body, hmac_mod.new("test_secret".encode(), body, hashlib.sha256).hexdigest()) is not None)

    # 4. Timing-safe comparison
    print("\n4. Timing safety")
    test("uses hmac.compare_digest", "compare_digest" in src)

    # 5. Order message parsing
    print("\n5. Order message parsing")
    order_payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "field": "messages",
                "value": {
                    "messages": [{
                        "type": "order",
                        "from": "447700900001",
                        "order": {
                            "catalog_id": "cat-001",
                            "product_items": [
                                {"product_retailer_id": "SKU-1", "quantity": 2, "item_price": 24.99, "currency": "GBP"},
                                {"product_retailer_id": "SKU-2", "quantity": 1, "item_price": 9.99, "currency": "GBP"},
                            ],
                        },
                    }]
                },
            }]
        }]
    }
    parsed = adapter.parse_order_message(order_payload)
    test("parses from_number", parsed and parsed["from_number"] == "447700900001")
    test("sums product items", parsed and parsed["amount"] == round(2*24.99 + 9.99, 2))
    test("parses currency", parsed and parsed["currency"] == "GBP")
    test("parses catalog_id", parsed and parsed["catalog_id"] == "cat-001")

    # 6. Edge cases
    print("\n6. Edge cases")
    test("empty payload returns None", adapter.parse_order_message({}) is None)
    test("non-order message returns None", adapter.parse_order_message({
        "entry": [{"changes": [{"value": {"messages": [{"type": "text", "from": "1", "text": {"body": "hello"}}]}}]}]
    }) is None)
    test("empty product_items returns None", adapter.parse_order_message({
        "entry": [{"changes": [{"value": {"messages": [{"type": "order", "from": "1", "order": {"product_items": []}}]}}]}]
    }) is None)

    # 7. send_payment_link guards
    print("\n7. send_payment_link guards")
    adapter_no_wa = WhatsAppAlgoVoi(whatsapp_token="", phone_number_id="123")
    test("no whatsapp_token returns False",
         adapter_no_wa.send_payment_link("447700", "https://x/checkout/tok", 50) is False)
    adapter_no_ph = WhatsAppAlgoVoi(whatsapp_token="tok", phone_number_id="")
    test("no phone_number_id returns False",
         adapter_no_ph.send_payment_link("447700", "https://x/checkout/tok", 50) is False)
    test("empty to returns False",
         adapter.send_payment_link("", "https://x/checkout/tok", 50) is False)
    test("empty checkout_url returns False",
         adapter.send_payment_link("447700", "", 50) is False)

    # 8. verify_payment
    print("\n8. Payment verification")
    test("empty token returns False", adapter.verify_payment("") is False)

    # 9. Platform-specific checks
    print("\n9. WhatsApp-specific checks")
    test("GRAPH_API_BASE is v18.0", "v18.0" in GRAPH_API_BASE)
    test("X-Hub-Signature-256 in source", "X-Hub-Signature-256" in src)
    test("hub.verify_token in source", "hub.verify_token" in src)
    test("hub.challenge in source", "hub.challenge" in src)
    test("messaging_product in source", "messaging_product" in src)
    test("cta_url in source", "cta_url" in src)
    test("graph.facebook.com in source", "graph.facebook.com" in src)

    # 10. SSL enforcement
    print("\n10. SSL enforcement")
    test("ssl.create_default_context", "create_default_context" in src)

    # 11. No hardcoded secrets
    print("\n11. No hardcoded secrets")
    test("no real API keys", "algv_" not in src)
    test("no real tenant IDs", "96eb0225" not in src)

    print("\n" + "=" * 50)
    print(f"Results: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
