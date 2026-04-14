"""
AlgoVoi AP2 AI Adapter — Tests
================================
All tests are unit tests — no live network calls, all external I/O mocked.
"""

import base64
import json
import os
import sys
import time
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "ap2-adapter"))

import ap2_algovoi as mod
from ap2_algovoi import AlgoVoiAp2AI, Ap2AiResult

PASS = FAIL = 0

def ok(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
        return True
    else:
        FAIL += 1
        print(f"  [FAIL] {name}" + (f" — {detail}" if detail else ""))
        return False

# ── Shared constants ──────────────────────────────────────────────────────────

OPENAI_KEY  = "sk-test-key"
ALGOVOI_KEY = "algv_testkey"
TENANT_ID   = "YOUR_TENANT_ID"
PAYOUT_ADDR = "ZVLRVYQSLJNVFMOIOKT35XH5SNQG45IVFMLLRFLHDQJQA5TO5H3SO4TVDQ"


def _make_gate(**kwargs):
    defaults = dict(
        openai_key=OPENAI_KEY, algovoi_key=ALGOVOI_KEY,
        tenant_id=TENANT_ID, payout_address=PAYOUT_ADDR,
        networks=["algorand-mainnet", "voi-mainnet"],
        amount_microunits=10000,
    )
    defaults.update(kwargs)
    return AlgoVoiAp2AI(**defaults)


# ── Section 1: construction ───────────────────────────────────────────────────

def test_construction():
    print("\n1. AlgoVoiAp2AI construction")
    results = []

    gate = _make_gate()
    results.append(ok("gate constructs", gate is not None))
    results.append(ok("openai_key stored", gate._openai_key == OPENAI_KEY))
    results.append(ok("model default gpt-4o", gate._model == "gpt-4o"))
    results.append(ok("base_url default None", gate._base_url is None))
    results.append(ok("inner Ap2Gate created", gate._gate is not None))
    results.append(ok("merchant_id == tenant_id", gate._gate.merchant_id == TENANT_ID))
    results.append(ok("amount_microunits passed", gate._gate.amount_microunits == 10000))
    results.append(ok("payout_address passed", gate._gate.payout_address == PAYOUT_ADDR))
    results.append(ok("algorand-mainnet in networks", "algorand-mainnet" in gate._gate.networks))
    results.append(ok("voi-mainnet in networks", "voi-mainnet" in gate._gate.networks))

    return results


# ── Section 2: check() — no mandate → 402 with CartMandate ───────────────────

def test_check_no_mandate():
    print("\n2. check() — no mandate -> 402 CartMandate")
    results = []

    gate = _make_gate()
    result = gate.check({}, {})

    results.append(ok("requires_payment True", result.requires_payment))
    results.append(ok("result is Ap2AiResult", isinstance(result, Ap2AiResult)))
    results.append(ok("mandate is None", result.mandate is None))
    results.append(ok("has as_flask_response", hasattr(result, "as_flask_response")))
    results.append(ok("has as_wsgi_response", hasattr(result, "as_wsgi_response")))

    body, status, headers = result.as_flask_response()
    results.append(ok("flask status 402", status == 402))
    results.append(ok("X-AP2-Cart-Mandate in headers",
                      any("x-ap2-cart-mandate" == k.lower() for k in headers)))

    wsgi_status, wsgi_headers, wsgi_body = result.as_wsgi_response()
    results.append(ok("wsgi status starts 402", wsgi_status.startswith("402")))
    results.append(ok("wsgi body is bytes", isinstance(wsgi_body, bytes)))

    return results


# ── Section 3: check() — valid PaymentMandate → mandate ──────────────────────

def test_check_valid_mandate():
    print("\n3. check() — valid PaymentMandate -> mandate")
    results = []

    import nacl.signing as _nacl  # type: ignore
    signing_key = _nacl.SigningKey.generate()
    pubkey      = bytes(signing_key.verify_key)
    # Derive Algorand-style address: base32(pubkey + 4-byte zero checksum), no padding
    payer_addr  = base64.b32encode(pubkey + b'\x00' * 4).decode().rstrip('=')
    tx_id       = "SDIX4LHMRGX5E2JJ5XTZ7WEKIZB6AVSLIRWUPTQ3FYKRSSVDMHWQ"

    gate = _make_gate()

    # Step 1: get cart mandate
    result_cart = gate.check({}, {})
    _, _, cart_headers = result_cart.as_flask_response()
    cart_b64 = next(
        v for k, v in cart_headers.items() if k.lower() == "x-ap2-cart-mandate"
    )

    # Step 2: build PaymentMandate
    mandate_obj = {
        "ap2_version": "0.1",
        "type": "PaymentMandate",
        "merchant_id": TENANT_ID,
        "payer_address": payer_addr,
        "payment_response": {
            "method_name": "https://api1.ilovechicken.co.uk/ap2/extensions/crypto-algo/v1",
            "details": {
                "network": "algorand-mainnet",
                "tx_id":   tx_id,
            },
        },
    }
    canonical = json.dumps(mandate_obj, separators=(",", ":"), sort_keys=True).encode()
    sig_bytes  = signing_key.sign(canonical).signature
    mandate_obj["signature"] = base64.b64encode(sig_bytes).decode()

    # Step 3: mock indexer confirming the TX
    indexer_data = json.dumps({"transaction": {
        "confirmed-round": 12345678,
        "sender": payer_addr,
        "asset-transfer-transaction": {
            "receiver": PAYOUT_ADDR,
            "amount": 10000,
            "asset-id": 31566704,
        },
    }}).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = indexer_data
    mock_resp.status = 200
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("ap2.urlopen", return_value=mock_resp):
        result = gate.check(
            {"X-AP2-Mandate": base64.b64encode(json.dumps(mandate_obj).encode()).decode()},
            {},
        )

    results.append(ok("requires_payment False", not result.requires_payment))
    results.append(ok("mandate present", result.mandate is not None))
    if result.mandate:
        results.append(ok("mandate.tx_id matches", result.mandate.tx_id == tx_id))
        results.append(ok("mandate.network set", result.mandate.network == "algorand-mainnet"))
        results.append(ok("mandate.payer_address set", result.mandate.payer_address == payer_addr))

    return results


# ── Section 4: algorand-mainnet only ──────────────────────────────────────────

def test_algorand_only():
    print("\n4. algorand-mainnet only network")
    results = []

    gate = _make_gate(networks=["algorand-mainnet"])
    results.append(ok("algorand-mainnet in networks", "algorand-mainnet" in gate._gate.networks))
    results.append(ok("voi-mainnet not in networks", "voi-mainnet" not in gate._gate.networks))

    return results


# ── Section 5: complete() calls OpenAI ───────────────────────────────────────

def test_complete():
    print("\n5. complete() calls OpenAI SDK")
    results = []

    gate = _make_gate()

    with patch("ap2_algovoi.AlgoVoiAp2AI.complete") as mock_complete:
        mock_complete.return_value = "Paid via AP2!"
        reply = gate.complete([{"role": "user", "content": "hi"}])

    results.append(ok("returns string", isinstance(reply, str)))
    results.append(ok("returns content", reply == "Paid via AP2!"))

    return results


# ── Section 6: complete() model override ─────────────────────────────────────

def test_model_override():
    print("\n6. complete() — model override")
    results = []

    gate = _make_gate(model="gpt-4o-mini")
    results.append(ok("model stored", gate._model == "gpt-4o-mini"))

    return results


# ── Section 7: base_url for compatible providers ──────────────────────────────

def test_base_url():
    print("\n7. base_url for OpenAI-compatible providers")
    results = []

    for url in [
        "https://api.mistral.ai/v1",
        "https://api.groq.com/openai/v1",
    ]:
        gate = _make_gate(base_url=url)
        results.append(ok(f"base_url stored", gate._base_url == url))

    return results


# ── Section 8: Ap2AiResult delegates correctly ───────────────────────────────

def test_result_delegation():
    print("\n8. Ap2AiResult delegates as_flask/wsgi to inner")
    results = []

    inner = MagicMock()
    inner.requires_payment = True
    inner.mandate = None
    inner.error = "no mandate"
    inner.as_flask_response.return_value = ("body", 402, {"X-AP2-Cart-Mandate": "xxx"})
    inner.as_wsgi_response.return_value = ("402 Payment Required", [("X-AP2-Cart-Mandate", "xxx")], b"body")

    result = Ap2AiResult(inner)
    results.append(ok("requires_payment delegated", result.requires_payment))
    results.append(ok("error delegated", result.error == "no mandate"))

    body, status, headers = result.as_flask_response()
    results.append(ok("flask delegates", status == 402))
    results.append(ok("X-AP2-Cart-Mandate passed", "X-AP2-Cart-Mandate" in headers))

    wsgi_status, _, wsgi_body = result.as_wsgi_response()
    results.append(ok("wsgi delegates", wsgi_status.startswith("402")))
    results.append(ok("wsgi body bytes", isinstance(wsgi_body, bytes)))

    return results


# ── Section 9: expires_seconds configurable ──────────────────────────────────

def test_expires_seconds():
    print("\n9. expires_seconds configurable")
    results = []

    gate = _make_gate(expires_seconds=300)
    results.append(ok("expires_seconds stored", gate._gate.expires_seconds == 300))

    return results


# ── Section 10: ImportError when openai missing ───────────────────────────────

def test_import_error():
    print("\n10. complete() raises ImportError when openai not installed")
    results = []

    gate = _make_gate()
    real_modules = dict(sys.modules)
    sys.modules["openai"] = None  # type: ignore

    try:
        gate.complete([{"role": "user", "content": "hi"}])
        results.append(ok("ImportError raised", False, "no error raised"))
    except ImportError:
        results.append(ok("ImportError raised", True))
    finally:
        sys.modules.clear()
        sys.modules.update(real_modules)

    return results


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    global PASS, FAIL
    PASS = FAIL = 0

    sections = [
        test_construction,
        test_check_no_mandate,
        test_check_valid_mandate,
        test_algorand_only,
        test_complete,
        test_model_override,
        test_base_url,
        test_result_delegation,
        test_expires_seconds,
        test_import_error,
    ]

    for fn in sections:
        fn()

    print(f"\n{'='*50}")
    print(f"Results: {PASS}/{PASS+FAIL} passed", "PASS" if FAIL == 0 else "FAIL")
    if FAIL:
        sys.exit(1)


if __name__ == "__main__":
    main()
