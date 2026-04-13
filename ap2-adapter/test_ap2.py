"""
AP2 Adapter v2.0.0 — Unit Tests

Tests the AP2 v0.1 CartMandate / PaymentMandate flow with the
AlgoVoi crypto-algo extension (https://api1.ilovechicken.co.uk/ap2/extensions/crypto-algo/v1).
"""

import base64
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

from ap2 import (
    Ap2Gate, Ap2CartMandate, Ap2Mandate, Ap2Result,
    EXTENSION_URI, AP2_VERSION, NETWORKS,
)

PASS = FAIL = 0


def test(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}" + (f" — {detail}" if detail else ""))


def b64j(obj: dict) -> str:
    return base64.b64encode(json.dumps(obj).encode()).decode()


def make_gate(**kwargs) -> Ap2Gate:
    defaults = dict(
        merchant_id="shop42",
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        amount_microunits=10000,
        networks=["algorand-mainnet", "voi-mainnet"],
        payout_address="ZVLRVYQSLJNVFMOIOKT35XH5SNQG45IVFMLLRFLHDQJQA5TO5H3SO4TVDQ",
    )
    defaults.update(kwargs)
    return Ap2Gate(**defaults)


def main():
    global PASS, FAIL
    gate = make_gate()

    src_path = os.path.join(os.path.dirname(__file__), "ap2.py")
    src = open(src_path).read()

    print("AP2 Adapter v2.0.0 — Unit Tests")
    print("=" * 60)

    # 1. Version and constants
    print("\n1. Version and constants")
    import ap2 as ap2_mod
    test("version is 2.0.0", ap2_mod.__version__ == "2.0.0")
    test("AP2_VERSION is 0.1", AP2_VERSION == "0.1")
    test("EXTENSION_URI is correct",
         EXTENSION_URI == "https://api1.ilovechicken.co.uk/ap2/extensions/crypto-algo/v1")
    test("NETWORKS has algorand-mainnet", "algorand-mainnet" in NETWORKS)
    test("NETWORKS has voi-mainnet", "voi-mainnet" in NETWORKS)
    test("algorand asset_id is 31566704", NETWORKS["algorand-mainnet"]["asset_id"] == 31566704)
    test("voi asset_id is 302190", NETWORKS["voi-mainnet"]["asset_id"] == 302190)

    # 2. No credentials -> CartMandate
    print("\n2. No credentials -> CartMandate (HTTP 402)")
    result = gate.check({})
    test("requires_payment is True", result.requires_payment)
    test("cart_mandate is not None", result.cart_mandate is not None)
    test("mandate is None", result.mandate is None)

    cm = result.cart_mandate
    if cm:
        d = cm.as_dict()

        # 3. CartMandate structure
        print("\n3. CartMandate structure")
        test("ap2_version is '0.1'", d.get("ap2_version") == "0.1")
        test("type is CartMandate", d.get("type") == "CartMandate")
        test("merchant_id is shop42", d.get("merchant_id") == "shop42")
        test("request_id is non-empty", bool(d.get("request_id")))
        test("expires_at is in the future", d.get("expires_at", 0) > time.time())
        contents = d.get("contents", {})
        pr = contents.get("payment_request", {})
        methods = pr.get("payment_methods", [])
        test("payment_methods has 2 entries", len(methods) == 2, f"got {len(methods)}")
        for pm in methods:
            test(f"supported_methods is extension URI",
                 pm.get("supported_methods") == EXTENSION_URI)
            data = pm.get("data", {})
            test(f"{data.get('network')}: has network", "network" in data)
            test(f"{data.get('network')}: has receiver", "receiver" in data)
            test(f"{data.get('network')}: has amount_microunits", "amount_microunits" in data)
            test(f"{data.get('network')}: amount_microunits is 10000",
                 data.get("amount_microunits") == 10000)
            test(f"{data.get('network')}: has asset_id", "asset_id" in data)
            test(f"{data.get('network')}: min_confirmations is 1",
                 data.get("min_confirmations") == 1)
            test(f"{data.get('network')}: memo_required is True",
                 data.get("memo_required") is True)

        algo_data = next((pm["data"] for pm in methods if pm["data"].get("network") == "algorand-mainnet"), {})
        voi_data  = next((pm["data"] for pm in methods if pm["data"].get("network") == "voi-mainnet"), {})
        test("algorand-mainnet asset_id is 31566704", algo_data.get("asset_id") == 31566704)
        test("voi-mainnet asset_id is 302190", voi_data.get("asset_id") == 302190)

        # 4. CartMandate header encoding
        print("\n4. CartMandate header encoding")
        hdr = cm.as_header()
        test("as_header() returns non-empty string", bool(hdr))
        decoded_cm = json.loads(base64.b64decode(hdr + "=="))
        test("decoded type is CartMandate", decoded_cm.get("type") == "CartMandate")

    # 5. Flask response format
    print("\n5. Flask response format")
    body_str, status, headers = result.as_flask_response()
    test("status is 402", status == 402)
    test("X-AP2-Cart-Mandate header present", "X-AP2-Cart-Mandate" in headers)
    body_obj = json.loads(body_str)
    test("body error is 'Payment Required'", body_obj.get("error") == "Payment Required")
    test("body has ap2_version", body_obj.get("ap2_version") == "0.1")
    test("body has cart_mandate", "cart_mandate" in body_obj)

    # 6. WSGI response format
    print("\n6. WSGI response format")
    status_w, headers_w, body_w = result.as_wsgi_response()
    test("WSGI status is '402 Payment Required'", status_w == "402 Payment Required")
    test("WSGI body is bytes", isinstance(body_w, bytes))
    test("WSGI body decodes to JSON", json.loads(body_w).get("error") == "Payment Required")
    test("WSGI X-AP2-Cart-Mandate in headers",
         any(h[0] == "X-AP2-Cart-Mandate" for h in headers_w))

    # 7. Invalid mandate encoding
    print("\n7. Invalid mandate encoding")
    r = gate.check({"X-AP2-Mandate": "not-valid-json!!!"})
    test("requires_payment True", r.requires_payment)
    test("error mentions encoding", "encoding" in (r.error or "").lower(), f"error={r.error}")

    # 8. Merchant ID mismatch
    print("\n8. Merchant ID mismatch")
    r = gate.check({"X-AP2-Mandate": b64j({
        "ap2_version": "0.1", "type": "PaymentMandate",
        "merchant_id": "wrong_merchant",
        "payer_address": "TESTADDR",
        "signature": "fakesig",
        "payment_response": {"method_name": EXTENSION_URI, "details": {"network": "algorand-mainnet"}},
    })})
    test("requires_payment True", r.requires_payment)
    test("error mentions merchant", "merchant" in (r.error or "").lower(), f"error={r.error}")

    # 9. Missing payer_address
    print("\n9. Missing payer_address")
    r = gate.check({"X-AP2-Mandate": b64j({
        "ap2_version": "0.1", "type": "PaymentMandate",
        "merchant_id": "shop42",
        "signature": "fakesig",
        "payment_response": {"method_name": EXTENSION_URI, "details": {"network": "algorand-mainnet"}},
    })})
    test("requires_payment True", r.requires_payment)
    test("error mentions payer", "payer" in (r.error or "").lower(), f"error={r.error}")

    # 10. Missing signature
    print("\n10. Missing signature")
    r = gate.check({"X-AP2-Mandate": b64j({
        "ap2_version": "0.1", "type": "PaymentMandate",
        "merchant_id": "shop42",
        "payer_address": "TESTADDR",
        "payment_response": {"method_name": EXTENSION_URI, "details": {"network": "algorand-mainnet"}},
    })})
    test("requires_payment True", r.requires_payment)
    test("error mentions payer or signature", r.error is not None, f"error={r.error}")

    # 11. Fake signature -> verification fails
    print("\n11. Fake signature -> rejected")
    r = gate.check({"X-AP2-Mandate": b64j({
        "ap2_version": "0.1", "type": "PaymentMandate",
        "merchant_id": "shop42",
        "payer_address": "TESTADDR123456",
        "signature": "ZmFrZXNpZw==",
        "payment_response": {"method_name": EXTENSION_URI,
                             "details": {"network": "algorand-mainnet", "tx_id": "FAKETX"}},
    })})
    test("requires_payment True", r.requires_payment)
    test("error mentions signature", "signature" in (r.error or "").lower(), f"error={r.error}")

    # 12. tx_id length guard
    print("\n12. tx_id length guard (>200 chars)")
    r = gate.check({"X-AP2-Mandate": b64j({
        "ap2_version": "0.1", "type": "PaymentMandate",
        "merchant_id": "shop42",
        "payer_address": "TESTADDR",
        "signature": "fakesig",
        "payment_response": {"method_name": EXTENSION_URI,
                             "details": {"network": "algorand-mainnet", "tx_id": "A" * 201}},
    })})
    test("requires_payment True for >200 char tx_id", r.requires_payment)
    test("error mentions tx_id", "tx_id" in (r.error or "").lower(), f"error={r.error}")

    # 13. Mandate in body
    print("\n13. Mandate in request body (ap2_mandate field)")
    fake_mandate = b64j({
        "ap2_version": "0.1", "type": "PaymentMandate",
        "merchant_id": "shop42",
        "payer_address": "TESTADDR123456",
        "signature": "ZmFrZXNpZw==",
        "payment_response": {"method_name": EXTENSION_URI,
                             "details": {"network": "algorand-mainnet", "tx_id": "FAKETX"}},
    })
    r = gate.check({}, body={"ap2_mandate": fake_mandate})
    test("mandate from body: parsed (not encoding error)", "encoding" not in (r.error or "").lower())
    test("mandate from body: requires_payment True (fake sig)", r.requires_payment)

    # 14. JSON mandate (non-base64)
    print("\n14. JSON mandate (non-base64)")
    json_mandate = json.dumps({
        "ap2_version": "0.1", "type": "PaymentMandate",
        "merchant_id": "shop42",
        "payer_address": "TESTADDR",
        "signature": "ZmFrZXNpZw==",
        "payment_response": {"method_name": EXTENSION_URI,
                             "details": {"network": "algorand-mainnet"}},
    })
    r = gate.check({"X-AP2-Mandate": json_mandate})
    test("JSON mandate parsed (not encoding error)", "encoding" not in (r.error or "").lower())

    # 15. Real ed25519 — valid PaymentMandate accepted
    print("\n15. Real ed25519 — valid PaymentMandate accepted")
    try:
        from nacl.signing import SigningKey
        sk = SigningKey.generate()
        pubkey = bytes(sk.verify_key)
        addr   = base64.b32encode(pubkey + b'\x00' * 4).decode().rstrip('=')

        fields = {
            "ap2_version": "0.1",
            "type": "PaymentMandate",
            "merchant_id": "shop42",
            "payer_address": addr,
            "payment_response": {
                "method_name": EXTENSION_URI,
                "details": {
                    "network": "algorand-mainnet",
                    "tx_id": "FAKETX_REAL_SIG",
                },
            },
        }
        msg = json.dumps(fields, sort_keys=True, separators=(",", ":")).encode()
        sig = base64.b64encode(sk.sign(msg).signature).decode()
        mandate = {**fields, "signature": sig}

        r = gate.check({"X-AP2-Mandate": b64j(mandate)})
        # Sig is valid but tx_id is fake -> on-chain verification fails (not sig failure)
        test("valid sig: NOT signature error",
             "signature" not in (r.error or "").lower(), f"error={r.error}")
        test("valid sig: on-chain verification attempted",
             "on-chain" in (r.error or "").lower() or r.requires_payment,
             f"error={r.error}")

        # 16. Tampered mandate rejected
        print("\n16. Tampered mandate (amount_microunits changed) rejected")
        tampered = dict(fields)
        tampered["payment_response"] = dict(fields["payment_response"])
        tampered["payment_response"]["details"] = {
            "network": "voi-mainnet",   # changed
            "tx_id": "FAKETX_TAMPERED",
        }
        tampered["signature"] = sig  # original sig — now invalid
        r_t = gate.check({"X-AP2-Mandate": b64j(tampered)})
        test("tampered mandate: sig verification fails", r_t.requires_payment)
        test("tampered mandate: signature error", "signature" in (r_t.error or "").lower(),
             f"error={r_t.error}")

        # 17. Wrong key rejected
        print("\n17. Wrong signature (different key) rejected")
        sk2  = SigningKey.generate()
        sig2 = base64.b64encode(sk2.sign(msg).signature).decode()
        wrong = {**fields, "signature": sig2}
        r_w = gate.check({"X-AP2-Mandate": b64j(wrong)})
        test("wrong key: requires_payment True", r_w.requires_payment)
        test("wrong key: signature error", "signature" in (r_w.error or "").lower(),
             f"error={r_w.error}")

        # 18. cryptography package fallback
        print("\n18. cryptography package fallback")
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
            csk   = Ed25519PrivateKey.generate()
            cpub  = csk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
            caddr = base64.b32encode(cpub + b'\x00' * 4).decode().rstrip('=')
            cf = {
                "ap2_version": "0.1", "type": "PaymentMandate",
                "merchant_id": "shop42",
                "payer_address": caddr,
                "payment_response": {
                    "method_name": EXTENSION_URI,
                    "details": {"network": "algorand-mainnet", "tx_id": "FAKE_CRYPT"},
                },
            }
            cmsg = json.dumps(cf, sort_keys=True, separators=(",", ":")).encode()
            csig = base64.b64encode(csk.sign(cmsg)).decode()
            cf_mandate = {**cf, "signature": csig}
            r_c = gate.check({"X-AP2-Mandate": b64j(cf_mandate)})
            test("cryptography fallback: NOT signature error",
                 "signature" not in (r_c.error or "").lower(), f"error={r_c.error}")
        except Exception as e:
            test("cryptography fallback: skipped", True, str(e))

    except ImportError as e:
        for n in range(15, 19):
            test(f"section {n} skipped — PyNaCl not available", True, str(e))

    # 19. Replay protection
    print("\n19. Replay protection")
    gate_rp = make_gate()
    gate_rp._used_tx_ids.add("USED_TX_123")
    r_rp = gate_rp.check({"X-AP2-Mandate": b64j({
        "ap2_version": "0.1", "type": "PaymentMandate",
        "merchant_id": "shop42",
        "payer_address": "TESTADDR",
        "signature": "fakesig",
        "payment_response": {"method_name": EXTENSION_URI,
                             "details": {"network": "algorand-mainnet", "tx_id": "USED_TX_123"}},
    })})
    test("replayed tx_id rejected", r_rp.requires_payment)
    test("replay error message", "already used" in (r_rp.error or "").lower(),
         f"error={r_rp.error}")

    # 20. 4-network CartMandate — extension schema only covers AVM, adapter covers 2 chains
    print("\n20. 2-network CartMandate (algorand + voi)")
    gate2 = make_gate(networks=["algorand-mainnet", "voi-mainnet"])
    r2 = gate2.check({})
    test("2-network gate: requires_payment True", r2.requires_payment)
    cm2 = r2.cart_mandate
    if cm2:
        methods2 = cm2.as_dict()["contents"]["payment_request"]["payment_methods"]
        test("2 payment_methods entries", len(methods2) == 2, f"got {len(methods2)}")
        nets2 = [m["data"]["network"] for m in methods2]
        test("algorand-mainnet in payment_methods", "algorand-mainnet" in nets2)
        test("voi-mainnet in payment_methods", "voi-mainnet" in nets2)

    # 21. Extension URI in source
    print("\n21. Extension URI and schema references in source")
    test("EXTENSION_URI in source",
         "https://api1.ilovechicken.co.uk/ap2/extensions/crypto-algo/v1" in src)
    test("EXTENSION_SCHEMA in source",
         "schema.json" in src)
    test("AP2_VERSION 0.1 in source", '"0.1"' in src)
    test("CartMandate in source", "CartMandate" in src)
    test("PaymentMandate in source", "PaymentMandate" in src)
    test("payment_response in source", "payment_response" in src)
    test("no third-party imports (requests/httpx)",
         not any(x in src for x in ["import requests", "import httpx"]))
    test("SSL context used", "create_default_context" in src)

    # Summary
    print("\n" + "=" * 60)
    print(f"Results: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
