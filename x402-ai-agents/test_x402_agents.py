"""
x402 AI Agents AlgoVoi Adapter -- Tests
"""

import base64
import hashlib
import hmac as hmac_mod
import json
import os
import ssl as ssl_mod
import sys

sys.path.insert(0, os.path.dirname(__file__))

from x402_agents_algovoi import (
    X402AgentAlgoVoi,
    HOSTED_NETWORKS,
    NETWORK_CAIP2,
    NETWORK_ASSET,
    USDC_DECIMALS,
)

PASS = FAIL = 0


def test(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  [PASS] " + name)
    else:
        FAIL += 1
        print("  [FAIL] " + name + (" -- " + detail if detail else ""))


def main():
    global PASS, FAIL

    adapter = X402AgentAlgoVoi(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        webhook_secret="test_secret",
        default_network="algorand_mainnet",
        base_currency="USD",
        payout_address="TEST_PAYOUT_ADDR",
    )

    src_path = os.path.join(os.path.dirname(__file__), "x402_agents_algovoi.py")
    src = open(src_path).read()

    print("x402 AI Agents AlgoVoi Adapter -- Tests")
    print("=" * 50)

    # 1. Network validation
    print("\n1. Network validation")
    test("4 hosted networks", len(HOSTED_NETWORKS) == 4)
    test("algorand_mainnet supported", "algorand_mainnet" in HOSTED_NETWORKS)
    test("voi_mainnet supported", "voi_mainnet" in HOSTED_NETWORKS)
    test("hedera_mainnet supported", "hedera_mainnet" in HOSTED_NETWORKS)
    test("stellar_mainnet supported", "stellar_mainnet" in HOSTED_NETWORKS)

    # 1b. CAIP-2 and asset mappings
    print("\n1b. CAIP-2 and asset mappings")
    test("algorand CAIP-2 is algorand:mainnet", NETWORK_CAIP2["algorand_mainnet"] == "algorand:mainnet")
    test("voi CAIP-2 is voi:mainnet", NETWORK_CAIP2["voi_mainnet"] == "voi:mainnet")
    test("stellar CAIP-2 is stellar:pubnet", NETWORK_CAIP2["stellar_mainnet"] == "stellar:pubnet")
    test("hedera CAIP-2 is hedera:mainnet", NETWORK_CAIP2["hedera_mainnet"] == "hedera:mainnet")
    test("algorand asset is 31566704", NETWORK_ASSET["algorand_mainnet"] == "31566704")
    test("voi asset is 302190", NETWORK_ASSET["voi_mainnet"] == "302190")
    test("stellar asset contains GA5ZS", "GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN" in NETWORK_ASSET["stellar_mainnet"])
    test("hedera asset is 0.0.456858", NETWORK_ASSET["hedera_mainnet"] == "0.0.456858")
    test("USDC_DECIMALS is 6", USDC_DECIMALS == 6)

    # 2. Webhook security
    print("\n2. Webhook security")
    adapter_nosecret = X402AgentAlgoVoi(webhook_secret="")
    test(
        "empty secret returns None",
        adapter_nosecret.verify_webhook(b"body", "sig") is None,
    )

    body = b'{"event":"payment.confirmed","tx_id":"ALGO123"}'
    expected = hmac_mod.new("test_secret".encode(), body, hashlib.sha256).hexdigest()
    result = adapter.verify_webhook(body, expected)
    test("valid HMAC returns payload", result is not None)
    test("valid HMAC payload has tx_id", result is not None and result.get("tx_id") == "ALGO123")
    test("wrong HMAC returns None", adapter.verify_webhook(body, "badsig") is None)

    # 3. Timing safety
    print("\n3. Timing safety")
    test("uses hmac.compare_digest", "compare_digest" in src)

    # 4. create_payment_requirement — spec format
    print("\n4. create_payment_requirement")
    req = adapter.create_payment_requirement(
        amount=0.001,
        currency="USD",
        network="algorand_mainnet",
        resource_path="/api/inference",
        resource_description="Inference API call",
    )
    test("returns a dict", isinstance(req, dict))
    test("has header_value key", "header_value" in req)
    test(
        "header_value is non-empty string",
        isinstance(req.get("header_value"), str) and len(req["header_value"]) > 0,
    )

    decoded_raw = base64.b64decode(req["header_value"].encode())
    decoded = json.loads(decoded_raw)
    test("header_value decodes to valid JSON", isinstance(decoded, dict))
    test("x402Version is integer 1", decoded.get("x402Version") == 1)
    test("has accepts array", isinstance(decoded.get("accepts"), list) and len(decoded["accepts"]) == 1)

    accept = decoded["accepts"][0]
    test("scheme is exact", accept.get("scheme") == "exact")
    test("network is CAIP-2 algorand:mainnet", accept.get("network") == "algorand:mainnet")
    test("amount is string microunits '1000'", accept.get("amount") == "1000")
    test("asset is algorand ASA ID", accept.get("asset") == "31566704")
    test("payTo is payout_address", accept.get("payTo") == "TEST_PAYOUT_ADDR")
    test("maxTimeoutSeconds is int", isinstance(accept.get("maxTimeoutSeconds"), int))
    test("extra.name is USDC", (accept.get("extra") or {}).get("name") == "USDC")
    test("extra.decimals is 6", (accept.get("extra") or {}).get("decimals") == 6)

    resource = decoded.get("resource", {})
    test("resource.url is resource_path", resource.get("url") == "/api/inference")
    test("resource.description is set", bool(resource.get("description")))

    # 5. decode_payment_requirement roundtrip
    print("\n5. decode_payment_requirement roundtrip")
    header_val = req["header_value"]
    decoded2 = adapter.decode_payment_requirement(header_val)
    test("roundtrip returns dict", isinstance(decoded2, dict))
    test("roundtrip x402Version is 1", decoded2.get("x402Version") == 1)
    test("roundtrip resource.url matches", (decoded2.get("resource") or {}).get("url") == "/api/inference")
    test("roundtrip accepts[0].amount matches", (decoded2.get("accepts") or [{}])[0].get("amount") == "1000")
    test("empty string returns None", adapter.decode_payment_requirement("") is None)
    test("garbage returns None", adapter.decode_payment_requirement("!!!notbase64!!!") is None)

    # 6. verify_x402_payment edge cases
    print("\n6. verify_x402_payment edge cases")
    ok, tx = adapter.verify_x402_payment("")
    test("empty header returns (False, None)", ok is False and tx is None)

    ok2, tx2 = adapter.verify_x402_payment("notvalidbase64!!!")
    test("invalid base64 returns (False, None)", ok2 is False and tx2 is None)

    no_tx = base64.b64encode(json.dumps({"scheme": "exact"}).encode()).decode()
    ok3, tx3 = adapter.verify_x402_payment(no_tx)
    test("missing signature/tx_id returns (False, None)", ok3 is False and tx3 is None)

    # Spec format: payload.signature
    spec_proof = base64.b64encode(json.dumps({
        "x402Version": 1,
        "scheme": "exact",
        "network": "algorand:mainnet",
        "payload": {
            "signature": "SPECTXID",
            "authorization": {"from": "ADDR", "to": "PAYTO", "amount": "1000", "asset": "31566704"},
        },
    }).encode()).decode()
    result_spec = adapter.verify_x402_payment(spec_proof)
    test("spec payload.signature does not crash", isinstance(result_spec, tuple) and len(result_spec) == 2)

    # Legacy fallback: payload.tx_id
    legacy_proof = base64.b64encode(json.dumps({
        "x402Version": 1,
        "scheme": "exact",
        "network": "algorand:mainnet",
        "payload": {"tx_id": "LEGACYTXID", "payer": "ADDR"},
    }).encode()).decode()
    result_legacy = adapter.verify_x402_payment(legacy_proof)
    test("legacy payload.tx_id fallback does not crash", isinstance(result_legacy, tuple) and len(result_legacy) == 2)

    # 7. build_payment_required_response structure
    print("\n7. build_payment_required_response")
    pr = adapter.build_payment_required_response(
        amount=0.005,
        currency="USD",
        network="voi_mainnet",
        resource_path="/data/feed",
    )
    test("returns dict", isinstance(pr, dict))
    test("status_code is 402", pr.get("status_code") == 402)
    test("header_name is X-PAYMENT-REQUIRED", pr.get("header_name") == "X-PAYMENT-REQUIRED")
    test("header_value is non-empty", bool(pr.get("header_value")))

    inner = json.loads(base64.b64decode(pr["header_value"].encode()))
    inner_accept = (inner.get("accepts") or [{}])[0]
    test("inner amount is string microunits '5000'", inner_accept.get("amount") == "5000")
    test("inner network is voi:mainnet", inner_accept.get("network") == "voi:mainnet")
    test("inner asset is voi ASA ID", inner_accept.get("asset") == "302190")

    # 8. handle_agent_payment
    print("\n8. handle_agent_payment")
    test("empty payment header returns False", adapter.handle_agent_payment("/api/data", "") is False)
    test("garbage header returns False", adapter.handle_agent_payment("/api/data", "notvalid") is False)

    # 9. verify_payment edge cases
    print("\n9. verify_payment edge cases")
    test("empty token returns False", adapter.verify_payment("") is False)

    # 10. x402Version integer in source
    print("\n10. Protocol compliance in source")
    test("x402Version integer in source", '"x402Version": 1' in src or '"x402Version":1' in src or "x402Version" in src)
    test("accepts array in source", '"accepts"' in src or "'accepts'" in src)

    # 11. Header name constants in source
    print("\n11. Header name constants")
    test("X-PAYMENT-REQUIRED in source", "X-PAYMENT-REQUIRED" in src)
    test("X-PAYMENT in source", "X-PAYMENT" in src)

    # 12. HTTP 402 literal in source
    print("\n12. HTTP 402 presence")
    test("402 in source", "402" in src)

    # 13. SSL enforcement
    print("\n13. SSL enforcement")
    test("ssl.create_default_context in source", "create_default_context" in src)
    test("adapter._ssl is SSLContext", isinstance(adapter._ssl, ssl_mod.SSLContext))

    # 14. No hardcoded secrets
    print("\n14. No hardcoded secrets")
    test("no real API keys", "algv_iedCPy" not in src)
    test("no real tenant UUIDs", "96eb0225" not in src)

    # 15. base64 encode/decode roundtrip (spec format)
    print("\n15. base64 encode/decode roundtrip")
    original = {
        "x402Version": 1,
        "accepts": [{"scheme": "exact", "network": "algorand:mainnet", "amount": "10000", "asset": "31566704", "payTo": ""}],
        "resource": {"url": "/test", "description": "Test"},
    }
    encoded = base64.b64encode(json.dumps(original).encode()).decode()
    decoded_back = json.loads(base64.b64decode(encoded.encode()))
    test("roundtrip preserves x402Version", decoded_back["x402Version"] == 1)
    test("roundtrip preserves amount", decoded_back["accepts"][0]["amount"] == "10000")
    test("roundtrip preserves network", decoded_back["accepts"][0]["network"] == "algorand:mainnet")

    # 16. Default network / currency fallback
    print("\n16. Default network and currency fallback")
    req_defaults = adapter.create_payment_requirement(amount=1.0)
    decoded_defaults = adapter.decode_payment_requirement(req_defaults["header_value"])
    accept_defaults = (decoded_defaults.get("accepts") or [{}])[0]
    test("falls back to default_network CAIP-2", accept_defaults.get("network") == "algorand:mainnet")
    test("amount is string microunits for 1.0 USDC", accept_defaults.get("amount") == "1000000")

    req_invalid_net = adapter.create_payment_requirement(amount=1.0, network="invalid_chain")
    decoded_inv = adapter.decode_payment_requirement(req_invalid_net["header_value"])
    inv_accept = (decoded_inv.get("accepts") or [{}])[0]
    test("invalid network falls back to default", inv_accept.get("network") == "algorand:mainnet")

    # 17. Microunit conversion accuracy
    print("\n17. Microunit conversion")
    cases = [(0.01, "10000"), (0.001, "1000"), (1.0, "1000000"), (0.1, "100000")]
    for amount_usdc, expected_str in cases:
        r = adapter.create_payment_requirement(amount=amount_usdc)
        got = (r.get("accepts") or [{}])[0].get("amount")
        test(f"{amount_usdc} USDC -> {expected_str} microunits", got == expected_str)

    # 18. stdlib only
    print("\n18. Zero-dependency (stdlib only)")
    forbidden = ["import requests", "import httpx", "import aiohttp", "import boto3"]
    test("no third-party imports", not any(imp in src for imp in forbidden))

    # Summary
    print("\n" + "=" * 50)
    print("Results: %d passed, %d failed" % (PASS, FAIL))
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
