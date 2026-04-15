"""
TikTok Shop AlgoVoi Adapter -- Tests
"""

import hashlib
import hmac as hmac_mod
import base64
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from tiktok_algovoi import TikTokAlgoVoi, HOSTED_NETWORKS

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

    adapter = TikTokAlgoVoi(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        webhook_secret="test_algovoi_secret",
        tiktok_app_secret="test_tiktok_secret",
        default_network="algorand_mainnet",
        base_currency="GBP",
    )

    print("TikTok Shop AlgoVoi Adapter -- Tests")
    print("=" * 50)

    # 1. Network validation
    print("\n1. Network validation")
    test("4 hosted networks", len(HOSTED_NETWORKS) == 4)
    test("algorand", "algorand_mainnet" in HOSTED_NETWORKS)
    test("voi", "voi_mainnet" in HOSTED_NETWORKS)
    test("hedera", "hedera_mainnet" in HOSTED_NETWORKS)
    test("stellar", "stellar_mainnet" in HOSTED_NETWORKS)

    # 2. TikTok webhook verification
    print("\n2. TikTok webhook security")
    adapter_nosecret = TikTokAlgoVoi(tiktok_app_secret="")
    test("empty tiktok secret returns None", adapter_nosecret.verify_tiktok_webhook(b"body", "sig") is None)

    body = b'{"type":"ORDER_CREATED","data":{"order_id":"12345"}}'
    expected = hmac_mod.new("test_tiktok_secret".encode(), body, hashlib.sha256).hexdigest()
    result = adapter.verify_tiktok_webhook(body, expected)
    test("valid TikTok HMAC returns payload", result is not None)
    test("wrong TikTok HMAC returns None", adapter.verify_tiktok_webhook(body, "wrong") is None)

    # 3. AlgoVoi webhook verification
    print("\n3. AlgoVoi webhook security")
    adapter_nosecret2 = TikTokAlgoVoi(webhook_secret="")
    test("empty algovoi secret returns None", adapter_nosecret2.verify_algovoi_webhook(b"body", "sig") is None)

    av_body = b'{"order_id":"123","tx_id":"ABC"}'
    av_expected = base64.b64encode(
        hmac_mod.new("test_algovoi_secret".encode(), av_body, hashlib.sha256).digest()
    ).decode()
    result = adapter.verify_algovoi_webhook(av_body, av_expected)
    test("valid AlgoVoi HMAC returns payload", result is not None)
    test("wrong AlgoVoi HMAC returns None", adapter.verify_algovoi_webhook(av_body, "wrong") is None)

    # 4. Timing-safe comparisons
    print("\n4. Timing safety")
    src = open(__file__.replace("test_tiktok.py", "tiktok_algovoi.py")).read()
    test("uses hmac.compare_digest", "compare_digest" in src)

    # 4a. Type guards (v1.1.0 hardening)
    test("tiktok bytes sig returns None (no crash)",
         adapter.verify_tiktok_webhook(body, expected.encode()) is None)
    test("tiktok None sig returns None (no crash)",
         adapter.verify_tiktok_webhook(body, None) is None)
    test("tiktok int sig returns None (no crash)",
         adapter.verify_tiktok_webhook(body, 12345) is None)
    test("algovoi bytes sig returns None (no crash)",
         adapter.verify_algovoi_webhook(av_body, av_expected.encode()) is None)
    test("algovoi None sig returns None (no crash)",
         adapter.verify_algovoi_webhook(av_body, None) is None)
    test("non-bytes body returns None (no crash)",
         adapter.verify_tiktok_webhook("not-bytes", expected) is None)
    test("64 KB+ body rejected (tiktok)",
         adapter.verify_tiktok_webhook(b'{"x":"' + b'A' * 70_000 + b'"}', "x") is None)
    test("64 KB+ body rejected (algovoi)",
         adapter.verify_algovoi_webhook(b'{"x":"' + b'A' * 70_000 + b'"}', "x") is None)

    # 5. Parse order webhook
    print("\n5. Order webhook parsing")
    webhook = {
        "type": "ORDER_CREATED",
        "data": {
            "order_id": "TT-98765",
            "payment": {
                "total_amount": "49.99",
                "currency": "GBP",
            },
            "order_status": "AWAITING_SHIPMENT",
        },
    }
    order = adapter.parse_order_webhook(webhook)
    test("parses order ID", order and order["order_id"] == "TT-98765")
    test("parses amount", order and order["amount"] == 49.99)
    test("parses currency", order and order["currency"] == "GBP")
    test("parses status", order and order["status"] == "AWAITING_SHIPMENT")
    test("parses event type", order and order["event_type"] == "ORDER_CREATED")

    # 6. Status change event
    webhook2 = {
        "type": "ORDER_STATUS_CHANGE",
        "data": {
            "order_id": "TT-11111",
            "payment": {"total_amount": "10.00", "currency": "USD"},
            "order_status": "AWAITING_COLLECTION",
        },
    }
    order2 = adapter.parse_order_webhook(webhook2)
    test("parses status change event", order2 and order2["order_id"] == "TT-11111")

    # 7. Empty/invalid webhooks
    test("empty payload returns None", adapter.parse_order_webhook({}) is None)
    test("unknown event type returns None", adapter.parse_order_webhook({"type": "UNKNOWN", "data": {}}) is None)
    test("legacy '1' event type now rejected (v1.1.0)",
         adapter.parse_order_webhook({"type": "1", "data": {"order_id": "X"}}) is None)

    # 7a. Amount sanity (v1.1.0)
    def _wh(amount, oid="TT-1"):
        return {"type": "ORDER_CREATED", "data": {
            "order_id": oid,
            "payment": {"total_amount": amount, "currency": "GBP"},
            "order_status": "AWAITING_SHIPMENT"}}
    test("negative amount rejected", adapter.parse_order_webhook(_wh("-1.00")) is None)
    test("NaN amount rejected", adapter.parse_order_webhook(_wh("nan")) is None)
    test("Infinity amount rejected", adapter.parse_order_webhook(_wh("inf")) is None)
    test("zero amount rejected", adapter.parse_order_webhook(_wh("0")) is None)
    test("missing payment block returns None",
         adapter.parse_order_webhook({"type": "ORDER_CREATED",
                                      "data": {"order_id": "X"}}) is None)
    # 7a-bis. Null-key fuzzing (v1.1.0 — guard against AttributeError on null fields)
    test("payment=null returns None (no AttributeError)",
         adapter.parse_order_webhook({"type": "ORDER_CREATED",
                                      "data": {"order_id": "X", "payment": None}}) is None)
    test("data=null returns None (no AttributeError)",
         adapter.parse_order_webhook({"type": "ORDER_CREATED", "data": None}) is None)
    test("payment as string returns None (no AttributeError)",
         adapter.parse_order_webhook({"type": "ORDER_CREATED",
                                      "data": {"order_id": "X", "payment": "oops"}}) is None)
    test("payload as None returns None (no crash)",
         adapter.parse_order_webhook(None) is None)
    test("payload as list returns None (no crash)",
         adapter.parse_order_webhook([1, 2, 3]) is None)
    test("nested order.payment=null returns None",
         adapter.parse_order_webhook({"type": "ORDER_CREATED",
                                      "data": {"order": {"order_id": "X", "payment": None}}}) is None)

    # 7b. process_order amount + redirect_url (v1.1.0)
    test("negative amount returns None",
         adapter.process_order("123", -1.00) is None)
    test("NaN amount returns None",
         adapter.process_order("123", float("nan")) is None)
    test("Infinity amount returns None",
         adapter.process_order("123", float("inf")) is None)
    test("zero amount returns None",
         adapter.process_order("123", 0) is None)
    test("file:// redirect_url returns None",
         adapter.process_order("123", 1.00, redirect_url="file:///etc/passwd") is None)
    test("gopher:// redirect_url returns None",
         adapter.process_order("123", 1.00, redirect_url="gopher://x") is None)
    test("http:// redirect_url returns None (https-only)",
         adapter.process_order("123", 1.00, redirect_url="http://example.com/ok") is None)

    # 8. Payment verification
    print("\n6. Payment verification")
    test("empty token returns False", adapter.verify_payment("") == False)
    insecure = TikTokAlgoVoi(api_base="http://api1.ilovechicken.co.uk",
                             webhook_secret="s", tiktok_app_secret="t")
    test("http:// api_base rejects verify_payment",
         insecure.verify_payment("tok") == False)

    # 9. Shipping update — tx_id + SSRF allowlist
    print("\n7. Shipping update")
    test("empty tx_id rejected", adapter.update_shipping("123", "", "token") == False)
    test(">200 char tx_id rejected", adapter.update_shipping("123", "A" * 201, "token") == False)
    test("non-tiktok api_base rejected (SSRF guard)",
         adapter.update_shipping("123", "TX", "token",
             api_base="https://attacker.invalid") == False)
    test("http:// api_base rejected",
         adapter.update_shipping("123", "TX", "token",
             api_base="http://open-api.tiktokglobalshop.com") == False)
    test("file:// api_base rejected",
         adapter.update_shipping("123", "TX", "token",
             api_base="file:///etc/passwd") == False)
    test("empty api_base rejected",
         adapter.update_shipping("123", "TX", "token",
             api_base="") == False)

    # 10. SSL
    print("\n8. SSL enforcement")
    test("ssl.create_default_context", "create_default_context" in src)

    # 11. No secrets
    print("\n9. No hardcoded secrets")
    test("no real API keys", "algv_iedCPy" not in src)
    test("no real tenant IDs", "96eb0225" not in src)

    # Summary
    print("\n" + "=" * 50)
    print(f"Results: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
