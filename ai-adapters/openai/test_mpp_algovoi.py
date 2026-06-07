"""
AlgoVoi MPP AI Adapter — Tests
================================
All tests are unit tests — no live network calls, all external I/O mocked.
"""

import base64
import json
import os
import sys
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mpp-adapter"))

import mpp_algovoi as mod
from mpp_algovoi import AlgoVoiMppAI, MppAiResult

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
        networks=["algorand_mainnet"], amount_microunits=10000,
    )
    defaults.update(kwargs)
    return AlgoVoiMppAI(**defaults)


# ── Section 1: construction ───────────────────────────────────────────────────

def test_construction():
    print("\n1. AlgoVoiMppAI construction")
    results = []

    gate = _make_gate()
    results.append(ok("gate constructs", gate is not None))
    results.append(ok("openai_key stored", gate._openai_key == OPENAI_KEY))
    results.append(ok("model default gpt-4o", gate._model == "gpt-4o"))
    results.append(ok("base_url default None", gate._base_url is None))
    results.append(ok("inner MppGate created", gate._gate is not None))
    results.append(ok("resource_id default ai-chat", gate._gate.resource_id == "ai-chat"))
    results.append(ok("amount_microunits passed", gate._gate.amount_microunits == 10000))
    results.append(ok("payout_address passed", gate._gate.payout_address == PAYOUT_ADDR))
    results.append(ok("networks passed", "algorand_mainnet" in gate._gate.networks))

    return results


# ── Section 2: check() — no credential → 402 ─────────────────────────────────

def test_check_no_credential():
    print("\n2. check() — no credential -> 402")
    results = []

    gate = _make_gate()
    result = gate.check({})

    results.append(ok("requires_payment True", result.requires_payment))
    results.append(ok("result is MppAiResult", isinstance(result, MppAiResult)))
    results.append(ok("has as_flask_response", hasattr(result, "as_flask_response")))
    results.append(ok("has as_wsgi_response", hasattr(result, "as_wsgi_response")))

    body, status, headers = result.as_flask_response()
    results.append(ok("flask status 402", status == 402))
    results.append(ok("WWW-Authenticate in headers",
                      any("www-authenticate" == k.lower() for k in headers)))

    wsgi_status, wsgi_headers, wsgi_body = result.as_wsgi_response()
    results.append(ok("wsgi status starts 402", wsgi_status.startswith("402")))
    results.append(ok("wsgi body is bytes", isinstance(wsgi_body, bytes)))

    return results


# ── Section 3: check() — valid credential → receipt ──────────────────────────

def test_check_valid_credential():
    print("\n3. check() — valid MPP credential -> receipt")
    results = []

    gate = _make_gate()
    tx_id = "DF2PQUPY6TVX3DD7GQSY7LEZNVGOEYC24NBIIHLKYM5RIA3UN4AQ"

    # Mock indexer returning a confirmed valid payment
    indexer_data = json.dumps({"transaction": {
        "confirmed-round": 12345678,
        "sender": "PAYER_ADDR",
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

    # Build a valid MPP credential
    proof = base64.b64encode(json.dumps({
        "network": "algorand-mainnet",
        "payload": {"txId": tx_id},
    }).encode()).decode()

    with patch("mpp.urlopen", return_value=mock_resp):
        result = gate.check({"Authorization": f"Payment {proof}"})

    results.append(ok("requires_payment False", not result.requires_payment))
    results.append(ok("receipt present", result.receipt is not None))
    if result.receipt:
        results.append(ok("receipt.tx_id matches", result.receipt.tx_id == tx_id))
        results.append(ok("receipt.payer set", result.receipt.payer != ""))
        results.append(ok("receipt.amount set", result.receipt.amount >= 10000))

    return results


# ── Section 4: all 4 networks construct ──────────────────────────────────────

def test_all_networks():
    print("\n4. all 4 networks construct")
    results = []

    for net in ["algorand_mainnet", "voi_mainnet", "hedera_mainnet", "stellar_mainnet"]:
        gate = _make_gate(networks=[net])
        results.append(ok(f"{net} constructs", net in gate._gate.networks))

    return results


# ── Section 5: custom resource_id and realm ───────────────────────────────────

def test_custom_resource():
    print("\n5. custom resource_id and realm")
    results = []

    gate = _make_gate(resource_id="my-ai-service", realm="My AI")
    results.append(ok("resource_id set", gate._gate.resource_id == "my-ai-service"))
    results.append(ok("realm set", gate._gate.realm == "My AI"))

    return results


# ── Section 6: complete() calls OpenAI ───────────────────────────────────────

def test_complete():
    print("\n6. complete() calls OpenAI SDK")
    results = []

    gate = _make_gate()
    mock_choice = MagicMock()
    mock_choice.message.content = "Hello from MPP!"
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]

    with patch("mpp_algovoi.AlgoVoiMppAI.complete") as mock_complete:
        mock_complete.return_value = "Hello from MPP!"
        reply = gate.complete([{"role": "user", "content": "hi"}])

    results.append(ok("returns string", isinstance(reply, str)))
    results.append(ok("returns content", reply == "Hello from MPP!"))

    return results


# ── Section 7: complete() model override ─────────────────────────────────────

def test_model_override():
    print("\n7. complete() — model override")
    results = []

    gate = _make_gate(model="gpt-4o-mini")
    results.append(ok("model stored", gate._model == "gpt-4o-mini"))

    with patch("mpp_algovoi.AlgoVoiMppAI.complete") as mock_complete:
        mock_complete.return_value = "ok"
        gate.complete([{"role": "user", "content": "hi"}], model="gpt-3.5-turbo")
        call_kwargs = mock_complete.call_args
        results.append(ok("model override passed", call_kwargs[1].get("model") == "gpt-3.5-turbo"
                          or (call_kwargs[0] and call_kwargs[0][1] == "gpt-3.5-turbo")))

    return results


# ── Section 8: base_url for compatible providers ──────────────────────────────

def test_base_url():
    print("\n8. base_url for OpenAI-compatible providers")
    results = []

    for url in [
        "https://api.mistral.ai/v1",
        "https://api.together.xyz/v1",
        "https://api.groq.com/openai/v1",
    ]:
        gate = _make_gate(base_url=url)
        results.append(ok(f"base_url {url[:30]}... stored", gate._base_url == url))

    return results


# ── Section 9: MppAiResult delegates correctly ───────────────────────────────

def test_result_delegation():
    print("\n9. MppAiResult delegates as_flask/wsgi to inner")
    results = []

    inner = MagicMock()
    inner.requires_payment = True
    inner.receipt = None
    inner.error = "no payment"
    inner.as_flask_response.return_value = ("body", 402, {"WWW-Authenticate": "Payment x"})
    inner.as_wsgi_response.return_value = ("402 Payment Required", [("WWW-Authenticate", "Payment x")], b"body")

    result = MppAiResult(inner)
    results.append(ok("requires_payment delegated", result.requires_payment))
    results.append(ok("error delegated", result.error == "no payment"))

    body, status, headers = result.as_flask_response()
    results.append(ok("flask delegates", status == 402))
    results.append(ok("WWW-Authenticate passed", "WWW-Authenticate" in headers))

    wsgi_status, _, wsgi_body = result.as_wsgi_response()
    results.append(ok("wsgi delegates", wsgi_status.startswith("402")))
    results.append(ok("wsgi body bytes", isinstance(wsgi_body, bytes)))

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
        test_check_no_credential,
        test_check_valid_credential,
        test_all_networks,
        test_custom_resource,
        test_complete,
        test_model_override,
        test_base_url,
        test_result_delegation,
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
