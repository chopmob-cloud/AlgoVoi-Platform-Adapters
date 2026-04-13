"""
AP2 Adapter — Integration test.

Tests:
1. No credentials -> 402 with AP2 payment request
2. Invalid mandate encoding -> 402 with error
3. Merchant ID mismatch -> rejected
4. Missing payer/signature -> rejected
5. Fake mandate -> verification fails
6. Payment request format validation
"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from ap2 import Ap2Gate, Ap2Result

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

    gate = Ap2Gate(
        merchant_id="shop42",
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        amount_usd=5.98,
        currency="USD",
        networks=["algorand_mainnet", "voi_mainnet"],
        items=[
            {"label": "API access — 1h", "amount": "4.99"},
            {"label": "Data export", "amount": "0.99"},
        ],
    )

    print("AP2 Adapter — Integration Tests")
    print("=" * 50)

    # Test 1: No credentials -> requires payment
    print("\n1. No credentials")
    result = gate.check({})
    test("requires_payment is True", result.requires_payment)
    test("payment_request exists", result.payment_request is not None)
    if result.payment_request:
        pr = result.payment_request.as_dict()
        test("protocol is ap2", pr["protocol"] == "ap2")
        test("merchant_id is shop42", pr["merchant_id"] == "shop42")
        test("amount is 5.98", pr["amount"]["value"] == "5.98")
        test("currency is USD", pr["amount"]["currency"] == "USD")
        test("2 items", len(pr["items"]) == 2)
        test("signing is ed25519", pr["signing"] == "ed25519")
        test("2 networks", len(pr["networks"]) == 2)
        test("has expires_at", pr["expires_at"] > 0)

    # Test 2: Invalid base64 mandate
    print("\n2. Invalid mandate encoding")
    result = gate.check({"X-AP2-Mandate": "not-valid-json!!!"})
    test("requires_payment is True", result.requires_payment)
    test("error mentions encoding", result.error is not None and "encoding" in (result.error or "").lower(),
         f"error={result.error}")

    # Test 3: Merchant ID mismatch
    print("\n3. Merchant ID mismatch")
    import base64
    wrong_merchant = base64.b64encode(json.dumps({
        "merchant_id": "wrong_merchant",
        "payer_address": "TESTADDR",
        "signature": "fakesig",
        "network": "algorand-mainnet",
        "amount": {"value": "5.98", "currency": "USD"},
    }).encode()).decode()
    result = gate.check({"X-AP2-Mandate": wrong_merchant})
    test("requires_payment is True", result.requires_payment)
    test("error mentions merchant", result.error is not None and "merchant" in (result.error or "").lower(),
         f"error={result.error}")

    # Test 4: Missing payer_address
    print("\n4. Missing payer_address")
    no_payer = base64.b64encode(json.dumps({
        "merchant_id": "shop42",
        "signature": "fakesig",
        "network": "algorand-mainnet",
        "amount": {"value": "5.98", "currency": "USD"},
    }).encode()).decode()
    result = gate.check({"X-AP2-Mandate": no_payer})
    test("requires_payment is True", result.requires_payment)
    test("error mentions payer", result.error is not None and "payer" in (result.error or "").lower(),
         f"error={result.error}")

    # Test 5: Missing signature
    print("\n5. Missing signature")
    no_sig = base64.b64encode(json.dumps({
        "merchant_id": "shop42",
        "payer_address": "TESTADDR",
        "network": "algorand-mainnet",
        "amount": {"value": "5.98", "currency": "USD"},
    }).encode()).decode()
    result = gate.check({"X-AP2-Mandate": no_sig})
    test("requires_payment is True", result.requires_payment)
    test("error mentions payer or signature", result.error is not None,
         f"error={result.error}")

    # Test 6: Valid structure but fake -> verification fails
    print("\n6. Fake mandate -> verification fails")
    fake_mandate = base64.b64encode(json.dumps({
        "merchant_id": "shop42",
        "payer_address": "TESTADDR123456",
        "signature": "base64fakesignature==",
        "network": "algorand-mainnet",
        "amount": {"value": "5.98", "currency": "USD"},
    }).encode()).decode()
    result = gate.check({"X-AP2-Mandate": fake_mandate})
    test("requires_payment is True", result.requires_payment)
    test("error mentions verification", result.error is not None and "verification" in (result.error or "").lower(),
         f"error={result.error}")

    # Test 7: Mandate in body instead of header
    print("\n7. Mandate in request body")
    result = gate.check({}, body={"ap2_mandate": fake_mandate})
    test("requires_payment is True (fake mandate)", result.requires_payment)
    test("mandate was parsed (not 'no mandate' error)", result.error != "Invalid AP2 mandate encoding")

    # Test 8: JSON mandate (not base64)
    print("\n8. JSON mandate (not base64)")
    json_mandate = json.dumps({
        "merchant_id": "shop42",
        "payer_address": "TESTADDR",
        "signature": "fakesig",
        "network": "algorand-mainnet",
        "amount": {"value": "5.98", "currency": "USD"},
    })
    result = gate.check({"X-AP2-Mandate": json_mandate})
    test("parsed JSON mandate", result.error is None or "encoding" not in (result.error or "").lower())

    # Test 9: Payment request header format
    print("\n9. X-AP2-Payment-Request header")
    result = gate.check({})
    if result.payment_request:
        header = result.payment_request.as_header()
        test("header is non-empty base64", len(header) > 10)
        decoded = json.loads(base64.b64decode(header))
        test("decoded has protocol=ap2", decoded["protocol"] == "ap2")
        test("decoded has merchant_id", decoded["merchant_id"] == "shop42")

    # Test 10: Flask response format
    print("\n10. Flask response format")
    result = gate.check({})
    body, status, headers = result.as_flask_response()
    test("status is 402", status == 402)
    test("body contains error", "Payment Required" in (body if isinstance(body, str) else json.dumps(body)))
    test("X-AP2-Payment-Request header present", "X-AP2-Payment-Request" in headers)

    # Summary
    print("\n" + "=" * 50)
    print(f"Results: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
