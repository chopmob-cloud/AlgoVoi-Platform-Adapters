"""
MPP Adapter — Integration test against live AlgoVoi x402 endpoint.

Tests:
1. No credentials -> 402 with WWW-Authenticate challenge
2. Invalid credentials -> 402 with error
3. Challenge format validation
4. Empty webhook secret rejection
"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from mpp import MppGate, MppResult

PASS = 0
FAIL = 0

def test(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} — {detail}")


def main():
    global PASS, FAIL

    gate = MppGate(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        resource_id="premium-content",
        amount_microunits=1000000,
        networks=["algorand_mainnet", "voi_mainnet"],
        realm="Test API",
        payout_address="GHSRL2SAY247LWE7HLUGEYKH...",
    )

    print("MPP Adapter — Integration Tests")
    print("=" * 50)

    # Test 1: No credentials -> requires payment
    print("\n1. No credentials")
    result = gate.check({})
    test("requires_payment is True", result.requires_payment)
    test("challenge exists", result.challenge is not None)
    if result.challenge:
        headers = result.challenge.as_402_headers()
        test("WWW-Authenticate header present", "WWW-Authenticate" in headers)
        test("X-Payment-Required header present", "X-Payment-Required" in headers)

        www_auth = headers.get("WWW-Authenticate", "")
        test("WWW-Authenticate starts with 'Payment'", www_auth.startswith("Payment"))
        test("contains realm", "realm=" in www_auth)
        test("contains challenge", "challenge=" in www_auth)

    # Test 2: Invalid base64 credential -> requires payment
    print("\n2. Invalid credential encoding")
    result = gate.check({"Authorization": "Payment not-valid-base64!!!"})
    test("requires_payment is True", result.requires_payment)
    test("error mentions encoding", result.error is not None and "encoding" in result.error.lower(),
         f"error={result.error}")

    # Test 3: Valid base64 but missing txId
    print("\n3. Missing txId in credential")
    import base64
    empty_cred = base64.b64encode(json.dumps({"network": "algorand-mainnet"}).encode()).decode()
    result = gate.check({"Authorization": f"Payment {empty_cred}"})
    test("requires_payment is True", result.requires_payment)
    test("error mentions txId", result.error is not None and "txid" in (result.error or "").lower(),
         f"error={result.error}")

    # Test 4: Valid credential but fake tx_id -> verification fails
    print("\n4. Fake tx_id -> verification fails")
    fake_cred = base64.b64encode(json.dumps({
        "network": "algorand-mainnet",
        "payload": {"txId": "FAKETXID123", "payer": "TESTADDR"},
    }).encode()).decode()
    result = gate.check({"Authorization": f"Payment {fake_cred}"})
    test("requires_payment is True", result.requires_payment)
    test("error mentions verification", result.error is not None and "verification" in (result.error or "").lower(),
         f"error={result.error}")

    # Test 5: X-Payment header works too
    print("\n5. X-Payment header (alternative)")
    result = gate.check({"X-Payment": empty_cred})
    test("requires_payment is True (missing txId)", result.requires_payment)

    # Test 6: tx_id length guard
    print("\n6. tx_id length guard (>200 chars)")
    long_cred = base64.b64encode(json.dumps({
        "network": "algorand-mainnet",
        "payload": {"txId": "A" * 201, "payer": "TESTADDR"},
    }).encode()).decode()
    result = gate.check({"Authorization": f"Payment {long_cred}"})
    test("requires_payment is True", result.requires_payment)

    # Test 7: Challenge has correct networks
    print("\n7. Challenge network configuration")
    result = gate.check({})
    if result.challenge:
        accepts = result.challenge.accepts
        test("2 networks in accepts", len(accepts) == 2, f"got {len(accepts)}")
        networks = [a["network"] for a in accepts]
        test("algorand-mainnet in accepts", "algorand-mainnet" in networks)
        test("voi-mainnet in accepts", "voi-mainnet" in networks)
        test("asset_id 31566704 for algorand", any(a["asset"] == "31566704" for a in accepts))
        test("asset_id 302190 for voi", any(a["asset"] == "302190" for a in accepts))

    # Test 8: WSGI guard
    print("\n8. WSGI guard")
    wsgi_result = gate.wsgi_guard({"HTTP_AUTHORIZATION": "Bearer invalid"})
    test("WSGI returns 402 tuple", wsgi_result is not None and wsgi_result[0] == "402 Payment Required")

    # Summary
    print("\n" + "=" * 50)
    print(f"Results: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
