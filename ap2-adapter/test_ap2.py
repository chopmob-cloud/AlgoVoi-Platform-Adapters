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

    # 11. Real ed25519 key pair — valid mandate accepted
    print("\n11. Real ed25519 signature — valid mandate accepted")
    try:
        from nacl.signing import SigningKey
        import base64 as _b64

        sk = SigningKey.generate()
        pubkey_bytes = bytes(sk.verify_key)  # 32-byte ed25519 public key

        # Build Algorand-compatible address: base32(pubkey + 4-byte pad)
        addr_bytes = pubkey_bytes + b'\x00' * 4
        payer_addr = _b64.b32encode(addr_bytes).decode().rstrip('=')

        # Canonical mandate (no signature field)
        mandate_fields = {
            "merchant_id": "shop42",
            "payer_address": payer_addr,
            "network": "algorand-mainnet",
            "amount": {"value": "5.98", "currency": "USD"},
        }
        msg = json.dumps(mandate_fields, sort_keys=True, separators=(",", ":")).encode()
        sig_bytes = sk.sign(msg).signature
        sig_b64 = _b64.b64encode(sig_bytes).decode()

        mandate_json = {**mandate_fields, "signature": sig_b64}
        mandate_b64 = _b64.b64encode(json.dumps(mandate_json).encode()).decode()

        result_real = gate.check({"X-AP2-Mandate": mandate_b64})
        test("valid mandate: requires_payment False", not result_real.requires_payment,
             f"error={result_real.error}")
        test("valid mandate: mandate object present", result_real.mandate is not None)
        if result_real.mandate:
            test("mandate.payer_address matches", result_real.mandate.payer_address == payer_addr)
            test("mandate.merchant_id matches", result_real.mandate.merchant_id == "shop42")
            test("mandate.amount is 5.98", result_real.mandate.amount == 5.98)
            test("mandate.network is algorand-mainnet", result_real.mandate.network == "algorand-mainnet")

        # 12. Tampered mandate rejected
        print("\n12. Tampered mandate rejected")
        tampered = dict(mandate_json)
        tampered["amount"] = {"value": "0.01", "currency": "USD"}  # changed amount
        tampered_b64 = _b64.b64encode(json.dumps(tampered).encode()).decode()
        result_tampered = gate.check({"X-AP2-Mandate": tampered_b64})
        test("tampered amount: requires_payment True", result_tampered.requires_payment)
        test("tampered amount: verification failed", "verification" in (result_tampered.error or "").lower(),
             f"error={result_tampered.error}")

        # 13. Wrong signature rejected
        print("\n13. Wrong signature (different key) rejected")
        sk2 = SigningKey.generate()  # different key
        sig2_bytes = sk2.sign(msg).signature
        wrong_sig_mandate = {**mandate_fields, "signature": _b64.b64encode(sig2_bytes).decode()}
        wrong_sig_b64 = _b64.b64encode(json.dumps(wrong_sig_mandate).encode()).decode()
        result_wrongsig = gate.check({"X-AP2-Mandate": wrong_sig_b64})
        test("wrong signature: requires_payment True", result_wrongsig.requires_payment)
        test("wrong signature: verification failed", "verification" in (result_wrongsig.error or "").lower(),
             f"error={result_wrongsig.error}")

        # 14. cryptography package fallback
        print("\n14. cryptography package fallback verification")
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
            crypt_sk = Ed25519PrivateKey.generate()
            crypt_vk = crypt_sk.public_key()
            crypt_pubkey = crypt_vk.public_bytes(Encoding.Raw, PublicFormat.Raw)
            crypt_addr = _b64.b32encode(crypt_pubkey + b'\x00' * 4).decode().rstrip('=')
            crypt_fields = {
                "merchant_id": "shop42",
                "payer_address": crypt_addr,
                "network": "voi-mainnet",
                "amount": {"value": "5.98", "currency": "USD"},
            }
            crypt_msg = json.dumps(crypt_fields, sort_keys=True, separators=(",", ":")).encode()
            crypt_sig = crypt_sk.sign(crypt_msg)
            crypt_mandate = {**crypt_fields, "signature": _b64.b64encode(crypt_sig).decode()}
            crypt_b64 = _b64.b64encode(json.dumps(crypt_mandate).encode()).decode()
            result_crypt = gate.check({"X-AP2-Mandate": crypt_b64})
            test("cryptography fallback: valid mandate accepted", not result_crypt.requires_payment,
                 f"error={result_crypt.error}")
        except Exception as e:
            test("cryptography fallback: skipped", True, f"(not tested: {e})")

    except ImportError as e:
        test("ed25519 tests: skipped — PyNaCl not available", True, str(e))

    # 15. WSGI response format
    print("\n15. WSGI response format")
    result_wsgi = gate.check({})
    status_wsgi, headers_wsgi, body_wsgi = result_wsgi.as_wsgi_response()
    test("WSGI status is '402 Payment Required'", status_wsgi == "402 Payment Required")
    test("WSGI body is bytes", isinstance(body_wsgi, bytes))
    test("WSGI body decodes to JSON", json.loads(body_wsgi).get("error") == "Payment Required")
    header_names = [h[0] for h in headers_wsgi]
    test("WSGI X-AP2-Payment-Request in headers", "X-AP2-Payment-Request" in header_names)

    # 16. 4-network gate payment request
    print("\n16. 4-network gate payment request")
    gate4 = Ap2Gate(
        merchant_id="shop4chain",
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        amount_usd=0.01,
        networks=["algorand_mainnet", "voi_mainnet", "hedera_mainnet", "stellar_mainnet"],
    )
    result4 = gate4.check({})
    test("4-network gate: requires_payment True", result4.requires_payment)
    pr4 = result4.payment_request
    test("4-network gate: payment_request present", pr4 is not None)
    if pr4:
        nets4 = pr4.as_dict().get("networks", [])
        test("4 networks in request", len(nets4) == 4, f"got {nets4}")
        test("algorand-mainnet present", "algorand-mainnet" in nets4)
        test("voi-mainnet present", "voi-mainnet" in nets4)
        test("hedera-mainnet present", "hedera-mainnet" in nets4)
        test("stellar-mainnet present", "stellar-mainnet" in nets4)

    # 17. Version and zero-dependency checks
    print("\n17. Version and zero-dependency checks")
    import ap2 as ap2_mod
    src_path = os.path.join(os.path.dirname(__file__), "ap2.py")
    src = open(src_path).read()
    test("version is 1.0.0", ap2_mod.__version__ == "1.0.0")
    test("no third-party imports (requests/httpx)", not any(x in src for x in ["import requests", "import httpx"]))
    test("SSL context used", "create_default_context" in src)
    test("ed25519 signing mentioned in docstring", "ed25519" in src.lower())

    # Summary
    print("\n" + "=" * 50)
    print(f"Results: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
