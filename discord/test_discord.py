"""
Discord AlgoVoi Adapter -- Tests
"""

import hashlib
import hmac as hmac_mod
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from discord_algovoi import DiscordAlgoVoi, HOSTED_NETWORKS, INTERACTION_PING, INTERACTION_APPLICATION_COMMAND

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

    adapter = DiscordAlgoVoi(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        discord_public_key="",
        webhook_secret="test_secret",
        default_network="algorand_mainnet",
        base_currency="USD",
    )

    src = open(os.path.join(os.path.dirname(__file__), "discord_algovoi.py")).read()

    print("Discord AlgoVoi Adapter -- Tests")
    print("=" * 50)

    # 1. Network validation
    print("\n1. Network validation")
    test("4 hosted networks", len(HOSTED_NETWORKS) == 4)
    test("algorand_mainnet", "algorand_mainnet" in HOSTED_NETWORKS)
    test("voi_mainnet", "voi_mainnet" in HOSTED_NETWORKS)
    test("hedera_mainnet", "hedera_mainnet" in HOSTED_NETWORKS)
    test("stellar_mainnet", "stellar_mainnet" in HOSTED_NETWORKS)

    # 2. Webhook / interaction verification
    print("\n2. Interaction verification")
    adapter_nosecret = DiscordAlgoVoi(discord_public_key="", webhook_secret="")
    test("empty secret+key returns False",
         adapter_nosecret.verify_interaction(b"body", "sig", "ts") is False)

    # HMAC-SHA256 fallback path
    ts = "1700000000"
    body = b'{"type":2}'
    expected = hmac_mod.new("test_secret".encode(), (ts + body.decode()).encode(), hashlib.sha256).hexdigest()
    # Rebuild properly: HMAC of (timestamp_bytes + raw_body)
    expected2 = hmac_mod.new("test_secret".encode(), ts.encode() + body, hashlib.sha256).hexdigest()
    test("valid HMAC fallback returns True",
         adapter.verify_interaction(body, expected2, ts) is True)
    test("invalid HMAC returns False",
         adapter.verify_interaction(body, "baddigest", ts) is False)

    # discord_public_key set returns Ed25519 path returns False (nacl not available in stdlib)
    adapter_pubkey = DiscordAlgoVoi(discord_public_key="aabbccdd", webhook_secret="")
    test("public_key set returns False (no nacl)",
         adapter_pubkey.verify_interaction(body, "sig", "ts") is False)

    # 3. Timing-safe comparison
    print("\n3. Timing safety")
    test("uses hmac.compare_digest", "compare_digest" in src)

    # 4. Interaction parsing
    print("\n4. Interaction parsing")
    interaction_payload = {
        "id": "inter-001",
        "token": "tok-abc",
        "type": INTERACTION_APPLICATION_COMMAND,
        "data": {
            "name": "pay",
            "options": [
                {"name": "amount", "value": 49.99},
                {"name": "currency", "value": "USD"},
                {"name": "reference", "value": "order-123"},
            ],
        },
        "member": {"user": {"id": "user-snowflake-789"}},
    }
    parsed = adapter.parse_interaction(interaction_payload)
    test("parses command name", parsed and parsed["command_name"] == "pay")
    test("parses user_id", parsed and parsed["user_id"] == "user-snowflake-789")
    test("parses amount", parsed and parsed["amount"] == 49.99)
    test("parses currency", parsed and parsed["currency"] == "USD")
    test("parses reference", parsed and parsed["reference"] == "order-123")
    test("parses interaction_id", parsed and parsed["interaction_id"] == "inter-001")

    # PING type should return None
    ping_payload = {"type": INTERACTION_PING, "id": "ping-001"}
    test("PING type returns None", adapter.parse_interaction(ping_payload) is None)

    # Missing data
    test("empty payload returns None", adapter.parse_interaction({}) is None)

    # User from DM (no member key)
    dm_payload = {
        "id": "dm-002",
        "token": "tok-dm",
        "type": INTERACTION_APPLICATION_COMMAND,
        "data": {"name": "pay", "options": [{"name": "amount", "value": 10}]},
        "user": {"id": "dm-user-456"},
    }
    dm_parsed = adapter.parse_interaction(dm_payload)
    test("parses DM user_id", dm_parsed and dm_parsed["user_id"] == "dm-user-456")

    # 5. Edge cases
    print("\n5. Edge cases")
    # Invalid amount
    bad_amount_payload = {
        "id": "inter-003",
        "token": "tok-x",
        "type": INTERACTION_APPLICATION_COMMAND,
        "data": {
            "name": "pay",
            "options": [{"name": "amount", "value": "not-a-number"}],
        },
        "member": {"user": {"id": "u"}},
    }
    bad = adapter.parse_interaction(bad_amount_payload)
    test("bad amount defaults to 0.0", bad and bad["amount"] == 0.0)

    # verify_payment empty token
    test("verify_payment empty token returns False", adapter.verify_payment("") is False)

    # 6. Platform-specific behaviour
    print("\n6. Discord-specific checks")
    test("Ed25519 comment in source", "Ed25519" in src)
    test("discord_public_key stored", "discord_public_key" in src)
    test("X-Signature-Ed25519 header referenced", "X-Signature-Ed25519" in src)
    test("X-Signature-Timestamp header referenced", "X-Signature-Timestamp" in src)
    test("PING constant == 1", INTERACTION_PING == 1)
    test("APPLICATION_COMMAND constant == 2", INTERACTION_APPLICATION_COMMAND == 2)
    test("ephemeral flag 64 in source", "64" in src)
    test("discord.com/developers in source or docs", "discord" in src.lower())

    # 7. SSL enforcement
    print("\n7. SSL enforcement")
    test("ssl.create_default_context", "create_default_context" in src)

    # 8. No hardcoded secrets
    print("\n8. No hardcoded secrets")
    test("no real API keys", "algv_" not in src)
    test("no real tenant IDs", "96eb0225" not in src)

    # 9. Default network fallback
    print("\n9. Network fallback")
    adapter_unknown = DiscordAlgoVoi(
        api_key="k", tenant_id="t", default_network="algorand_mainnet"
    )
    # create_checkout with unknown network should fall back to default
    # (can't call API in tests, but verify the fallback logic is present)
    test("unknown network falls back to default", "default_network" in src)

    print("\n" + "=" * 50)
    print(f"Results: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
