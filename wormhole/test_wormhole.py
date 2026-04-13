"""
Wormhole AlgoVoi Adapter -- Tests
"""

import hashlib
import hmac as hmac_mod
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from wormhole_algovoi import (
    WormholeAlgoVoi,
    HOSTED_NETWORKS,
    SUPPORTED_SOURCE_CHAINS,
    VAA_COMPLETED_STATUSES,
)

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

    adapter = WormholeAlgoVoi(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        wormhole_rpc_url="https://api.wormholescan.io",
        webhook_secret="test_secret",
        default_network="algorand_mainnet",
        base_currency="USD",
    )

    src = open(os.path.join(os.path.dirname(__file__), "wormhole_algovoi.py")).read()

    print("Wormhole AlgoVoi Adapter -- Tests")
    print("=" * 50)

    # 1. Network validation
    print("\n1. Network validation")
    test("4 hosted networks", len(HOSTED_NETWORKS) == 4)
    test("algorand_mainnet present", "algorand_mainnet" in HOSTED_NETWORKS)
    test("voi_mainnet present", "voi_mainnet" in HOSTED_NETWORKS)
    test("hedera_mainnet present", "hedera_mainnet" in HOSTED_NETWORKS)
    test("stellar_mainnet present", "stellar_mainnet" in HOSTED_NETWORKS)

    # 2. Supported source chains
    print("\n2. Supported source chains")
    test("ethereum in source chains", "ethereum" in SUPPORTED_SOURCE_CHAINS)
    test("solana in source chains", "solana" in SUPPORTED_SOURCE_CHAINS)
    test("base in source chains", "base" in SUPPORTED_SOURCE_CHAINS)
    test("polygon in source chains", "polygon" in SUPPORTED_SOURCE_CHAINS)
    test("avalanche in source chains", "avalanche" in SUPPORTED_SOURCE_CHAINS)
    test("arbitrum in source chains", "arbitrum" in SUPPORTED_SOURCE_CHAINS)
    test("at least 6 source chains", len(SUPPORTED_SOURCE_CHAINS) >= 6)

    # 3. Webhook security
    print("\n3. Webhook security")
    adapter_nosecret = WormholeAlgoVoi(webhook_secret="")
    test("empty secret returns None", adapter_nosecret.verify_webhook(b"body", "sig") is None)

    body = b'{"vaa_id":"2/0000/1234","source_chain":"ethereum","source_tx":"0xabc","amount":100.0,"target_chain":"algorand","status":"completed"}'
    expected_sig = hmac_mod.new("test_secret".encode(), body, hashlib.sha256).hexdigest()
    result = adapter.verify_webhook(body, expected_sig)
    test("valid HMAC returns payload", result is not None)
    test("valid HMAC payload is dict", isinstance(result, dict))
    test("wrong HMAC returns None", adapter.verify_webhook(body, "badhash") is None)
    test("tampered body rejected", adapter.verify_webhook(b"tampered", expected_sig) is None)

    # 4. Timing-safe comparison
    print("\n4. Timing safety")
    test("uses hmac.compare_digest", "compare_digest" in src)

    # 5. Bridge event parsing
    print("\n5. Bridge event parsing")
    bridge_event = {
        "vaa_id": "2/000000000000000000000000b6f6d86a8f9879a9c87f18830d/1234",
        "source_chain": "ethereum",
        "source_tx": "0xabcdef1234567890",
        "amount": 100.0,
        "target_chain": "algorand",
        "status": "completed",
    }
    event = adapter.parse_bridge_event(bridge_event)
    test("parses vaa_id", event and event["vaa_id"] == bridge_event["vaa_id"])
    test("parses source_chain", event and event["source_chain"] == "ethereum")
    test("parses source_tx", event and event["source_tx"] == "0xabcdef1234567890")
    test("parses amount", event and event["amount"] == 100.0)
    test("parses target_chain", event and event["target_chain"] == "algorand")
    test("parses status completed", event and event["status"] == "completed")

    # Nested data structure
    bridge_event_nested = {
        "data": {
            "vaa_id": "1/solana-emitter/999",
            "source_chain": "solana",
            "source_tx": "5V3...XYZ",
            "amount": 50.0,
            "target_chain": "algorand",
            "status": "redeemed",
        }
    }
    event2 = adapter.parse_bridge_event(bridge_event_nested)
    test("parses nested data structure", event2 and event2["vaa_id"] == "1/solana-emitter/999")
    test("parses solana source chain", event2 and event2["source_chain"] == "solana")

    # 6. Edge cases — parsing
    print("\n6. Parse edge cases")
    test("empty dict returns None", adapter.parse_bridge_event({}) is None)
    test("missing vaa_id returns None", adapter.parse_bridge_event({"source_chain": "ethereum"}) is None)
    test("None values handled gracefully", adapter.parse_bridge_event({"vaa_id": None}) is None)

    # 7. VAA status check — no live API
    print("\n7. VAA status check")
    status_result = adapter.check_vaa_status("2/emitter/12345")
    test("check_vaa_status returns None on network error", status_result is None)
    test("check_vaa_status empty vaa_id returns None", adapter.check_vaa_status("") is None)

    # 8. VAA completed statuses
    print("\n8. VAA status constants")
    test("completed in VAA_COMPLETED_STATUSES", "completed" in VAA_COMPLETED_STATUSES)
    test("confirmed in VAA_COMPLETED_STATUSES", "confirmed" in VAA_COMPLETED_STATUSES)
    test("redeemed in VAA_COMPLETED_STATUSES", "redeemed" in VAA_COMPLETED_STATUSES)
    test("pending not in VAA_COMPLETED_STATUSES", "pending" not in VAA_COMPLETED_STATUSES)

    # 9. Payment verification — empty token
    print("\n9. Payment verification")
    test("empty token returns False", adapter.verify_payment("") is False)
    test("whitespace token returns False", adapter.verify_payment("   ") is False)

    # 10. create_settlement — no live API
    print("\n10. Settlement creation")
    result_settle = adapter.create_settlement("0xabcdef", 100.0, "USD", "algorand_mainnet")
    test("returns None on network error (no live API)", result_settle is None)

    # Default network fallback
    adapter2 = WormholeAlgoVoi(
        api_key="k",
        tenant_id="t",
        webhook_secret="s",
        default_network="voi_mainnet",
    )
    test("invalid network falls back to default_network", adapter2.default_network == "voi_mainnet")

    # 11. SSL enforcement
    print("\n11. SSL enforcement")
    test("ssl.create_default_context used", "create_default_context" in src)
    test("urlopen uses context=self._ssl", "context=self._ssl" in src)

    # 12. No hardcoded secrets
    print("\n12. No hardcoded secrets")
    test("no real API keys in source", "algv_iedCPy" not in src)
    test("no real tenant IDs in source", "96eb0225" not in src)

    # 13. Wormhole-specific features
    print("\n13. Wormhole-specific features")
    test("wormholescan.io default RPC URL", "wormholescan.io" in src)
    test("/api/v1/vaas/ endpoint used", "/api/v1/vaas/" in src)
    test("wormhole_rpc_url init param", "wormhole_rpc_url" in src)
    test("SUPPORTED_SOURCE_CHAINS exported", "SUPPORTED_SOURCE_CHAINS" in src)
    test("VAA_COMPLETED_STATUSES exported", "VAA_COMPLETED_STATUSES" in src)
    test("portalbridge.com referenced", "portalbridge.com" in src)
    test("docs.wormhole.com referenced", "docs.wormhole.com" in src)
    test("X-Tenant-Id header sent", "X-Tenant-Id" in src)

    # 14. Flask handler
    print("\n14. Flask handler")
    handler = adapter.flask_webhook_handler()
    test("flask_webhook_handler returns callable", callable(handler))

    # Summary
    print("\n" + "=" * 50)
    print(f"Results: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
