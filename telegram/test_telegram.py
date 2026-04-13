"""
Telegram AlgoVoi Adapter -- Tests
"""

import hashlib
import hmac as hmac_mod
import json
import sys
import os
import time
sys.path.insert(0, os.path.dirname(__file__))

from telegram_algovoi import TelegramAlgoVoi, HOSTED_NETWORKS, TELEGRAM_API_BASE

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

    adapter = TelegramAlgoVoi(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        bot_token="123456:ABCdef",
        webhook_secret="test_secret",
        default_network="algorand_mainnet",
        base_currency="USD",
    )

    src = open(os.path.join(os.path.dirname(__file__), "telegram_algovoi.py")).read()

    print("Telegram AlgoVoi Adapter -- Tests")
    print("=" * 50)

    # 1. Network validation
    print("\n1. Network validation")
    test("4 hosted networks", len(HOSTED_NETWORKS) == 4)
    test("algorand_mainnet", "algorand_mainnet" in HOSTED_NETWORKS)
    test("voi_mainnet", "voi_mainnet" in HOSTED_NETWORKS)
    test("hedera_mainnet", "hedera_mainnet" in HOSTED_NETWORKS)
    test("stellar_mainnet", "stellar_mainnet" in HOSTED_NETWORKS)

    # 2. Webhook verification
    print("\n2. Webhook verification")
    adapter_nosecret = TelegramAlgoVoi(webhook_secret="")
    test("empty secret returns None", adapter_nosecret.verify_update(b"body", "sig") is None)

    body = b'{"update_id":1,"message":{"chat":{"id":111},"text":"/pay 10 USD"}}'
    # Valid: secret matches header exactly
    result = adapter.verify_update(body, "test_secret")
    test("matching secret returns payload", result is not None)
    test("wrong secret returns None", adapter.verify_update(body, "wrong_secret") is None)
    test("empty signature returns None", adapter.verify_update(body, "") is None)

    # 3. Timing-safe comparison
    print("\n3. Timing safety")
    test("uses hmac.compare_digest", "compare_digest" in src)

    # 4. Message parsing — /pay command
    print("\n4. Message parsing")
    update_pay = {
        "update_id": 100,
        "message": {
            "chat": {"id": 123456},
            "text": "/pay 49.99 GBP",
        },
    }
    parsed = adapter.parse_order_message(update_pay)
    test("parses /pay chat_id", parsed and parsed["chat_id"] == "123456")
    test("parses /pay amount", parsed and parsed["amount"] == 49.99)
    test("parses /pay currency", parsed and parsed["currency"] == "GBP")

    # /pay without currency returns default
    update_no_currency = {
        "update_id": 101,
        "message": {
            "chat": {"id": 789},
            "text": "/pay 25",
        },
    }
    nc = adapter.parse_order_message(update_no_currency)
    test("defaults to base_currency", nc and nc["currency"] == "USD")

    # 5. Callback query parsing
    print("\n5. Callback query parsing")
    update_cb = {
        "callback_query": {
            "message": {"chat": {"id": 555}},
            "data": "pay:99.99:EUR",
        }
    }
    cb = adapter.parse_order_message(update_cb)
    test("parses callback chat_id", cb and cb["chat_id"] == "555")
    test("parses callback amount", cb and cb["amount"] == 99.99)
    test("parses callback currency", cb and cb["currency"] == "EUR")

    # Unknown callback data
    update_cb_unknown = {
        "callback_query": {
            "message": {"chat": {"id": 666}},
            "data": "unknown:stuff",
        }
    }
    test("unknown callback returns None", adapter.parse_order_message(update_cb_unknown) is None)

    # 6. Edge cases
    print("\n6. Edge cases")
    test("empty update returns None", adapter.parse_order_message({}) is None)
    test("non-pay text returns None",
         adapter.parse_order_message({"message": {"chat": {"id": 1}, "text": "/start"}}) is None)
    test("/pay no amount returns None",
         adapter.parse_order_message({"message": {"chat": {"id": 1}, "text": "/pay"}}) is None)

    bad_amount = {"message": {"chat": {"id": 1}, "text": "/pay abc USD"}}
    test("bad amount returns None", adapter.parse_order_message(bad_amount) is None)

    # 7. send_payment_link guards
    print("\n7. send_payment_link guards")
    adapter_notoken = TelegramAlgoVoi(bot_token="")
    test("no bot_token returns False",
         adapter_notoken.send_payment_link("123", "https://x.com/checkout/tok", 10) is False)
    test("empty chat_id returns False",
         adapter.send_payment_link("", "https://x.com/checkout/tok", 10) is False)
    test("empty checkout_url returns False",
         adapter.send_payment_link("123", "", 10) is False)

    # 8. verify_payment
    print("\n8. Payment verification")
    test("empty token returns False", adapter.verify_payment("") is False)

    # 9. Platform-specific checks
    print("\n9. Telegram-specific checks")
    test("TELEGRAM_API_BASE correct", TELEGRAM_API_BASE == "https://api.telegram.org")
    test("sendMessage in source", "sendMessage" in src)
    test("X-Telegram-Bot-Api-Secret-Token in source", "X-Telegram-Bot-Api-Secret-Token" in src)
    test("setWebhook mentioned", "setWebhook" in src)
    test("inline_keyboard in source", "inline_keyboard" in src)
    test("bypass mode mentioned", "bypass" in src.lower())

    # 10. SSL enforcement
    print("\n10. SSL enforcement")
    test("ssl.create_default_context", "create_default_context" in src)

    # 11. No hardcoded secrets
    print("\n11. No hardcoded secrets")
    test("no real API keys", "algv_" not in src)
    test("no real tenant IDs", "96eb0225" not in src)

    # 12. Replay attack prevention
    print("\n12. Replay attack prevention")
    now = int(time.time())
    fresh_ts = str(now - 60)    # 60 seconds ago — fresh
    stale_ts = str(now - 360)   # 360 seconds ago — stale (> 300s default window)
    test("is_replay method exists", callable(getattr(adapter, "is_replay", None)))
    test("fresh timestamp not replay", adapter.is_replay(fresh_ts) is False)
    test("stale timestamp is replay", adapter.is_replay(stale_ts) is True)
    test("unparseable returns False (fail open)", adapter.is_replay("not-a-timestamp") is False)
    test("empty string returns False (fail open)", adapter.is_replay("") is False)
    test("negative epoch returns False", adapter.is_replay("-1") is False)
    test("zero epoch returns False", adapter.is_replay("0") is False)
    # Custom max_age_seconds
    test("60s window: 90s old is stale",
         adapter.is_replay(str(now - 90), max_age_seconds=60) is True)
    test("3600s window: 360s old is fresh",
         adapter.is_replay(stale_ts, max_age_seconds=3600) is False)

    # 13. Replay integration: verify_update() rejects stale message dates
    print("\n13. Replay integration with verify_update")
    # Fresh message — should pass signature AND replay check
    fresh_body = json.dumps({
        "update_id": 200,
        "message": {
            "chat": {"id": 999},
            "text": "/pay 10 USD",
            "date": now - 30,
        },
    }).encode()
    test("verify_update accepts fresh message date",
         adapter.verify_update(fresh_body, "test_secret") is not None)

    # Stale message — valid signature but stale date → should be rejected
    stale_body = json.dumps({
        "update_id": 201,
        "message": {
            "chat": {"id": 999},
            "text": "/pay 10 USD",
            "date": now - 400,  # 400s ago, > default 300s window
        },
    }).encode()
    test("verify_update rejects stale message date (valid secret)",
         adapter.verify_update(stale_body, "test_secret") is None)

    # Missing date — should fail open (update with no message.date is accepted)
    no_date_body = json.dumps({
        "update_id": 202,
        "message": {
            "chat": {"id": 999},
            "text": "/pay 10 USD",
        },
    }).encode()
    test("verify_update accepts missing message date (fail open)",
         adapter.verify_update(no_date_body, "test_secret") is not None)

    # callback_query update — no message.date at the expected path, fail open
    callback_body = json.dumps({
        "update_id": 203,
        "callback_query": {
            "message": {"chat": {"id": 555}},
            "data": "pay:99.99:EUR",
        },
    }).encode()
    test("verify_update accepts callback_query (no message.date, fail open)",
         adapter.verify_update(callback_body, "test_secret") is not None)

    # edited_message with stale date — should reject
    edited_stale_body = json.dumps({
        "update_id": 204,
        "edited_message": {
            "chat": {"id": 999},
            "text": "/pay 10 USD",
            "date": now - 400,
        },
    }).encode()
    test("verify_update rejects stale edited_message date",
         adapter.verify_update(edited_stale_body, "test_secret") is None)

    # Wrong secret + fresh date — still rejected (signature check comes first)
    test("verify_update rejects wrong secret even with fresh date",
         adapter.verify_update(fresh_body, "wrong_secret") is None)

    print("\n" + "=" * 50)
    print(f"Results: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
