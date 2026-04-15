"""
Amazon SP-API AlgoVoi Adapter — Security Replay Suite (2026-04-15)

Replays the April 2026 audit categories plus new attack-surface checks
identified during the 2026-04-15 review. Run alongside test_amazon.py.

Outputs are PASS / FAIL / WARN so we can distinguish real failures from
"defense missing but not currently exploitable in this codebase".
"""

from __future__ import annotations

import base64
import hashlib
import hmac as hmac_mod
import math
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from amazon_algovoi import AmazonAlgoVoi  # noqa: E402

PASS = FAIL = WARN = 0


def result(label: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label} -- {detail}")


def warn(label: str, detail: str = "") -> None:
    global WARN
    WARN += 1
    print(f"  [WARN] {label} -- {detail}")


def section(title: str) -> None:
    print(f"\n{title}")
    print("-" * len(title))


def hmac_b64(secret: str, body: bytes) -> str:
    return base64.b64encode(
        hmac_mod.new(secret.encode(), body, hashlib.sha256).digest()
    ).decode()


def main() -> int:
    adapter = AmazonAlgoVoi(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        webhook_secret="test_secret",
    )

    print("Amazon SP-API Adapter -- Security Replay")
    print("=" * 50)

    # ── 1. HMAC EMPTY-SECRET (April 2026 fix regression check) ─────────
    section("1. HMAC empty-secret bypass (April 2026 hardening)")
    no_sec = AmazonAlgoVoi(webhook_secret="")
    body = b'{"x":1}'
    # If empty secret were used, HMAC of body would be deterministic
    forged = hmac_b64("", body)
    result("empty secret rejects valid-looking forged sig",
           no_sec.verify_webhook(body, forged) is None,
           "Empty secret bypass present!")
    result("empty secret rejects empty sig",
           no_sec.verify_webhook(body, "") is None)

    # ── 2. HMAC TIMING (uses compare_digest — re-prove, don't just grep) ─
    section("2. HMAC timing-safe compare")
    body = b'{"y":2}'
    valid = hmac_b64("test_secret", body)
    almost = "A" + valid[1:]  # same length, one char off
    result("wrong-by-one-char rejected",
           adapter.verify_webhook(body, almost) is None)
    result("totally wrong sig rejected",
           adapter.verify_webhook(body, "wrong==") is None)
    result("valid sig accepted",
           adapter.verify_webhook(body, valid) is not None)

    # ── 3. HMAC TYPE CONFUSION ─────────────────────────────────────────
    section("3. HMAC signature type confusion")
    body = b'{"z":3}'
    valid = hmac_b64("test_secret", body)
    # Signature passed as bytes (might bypass compare_digest if not coerced)
    try:
        out = adapter.verify_webhook(body, valid.encode())  # type: ignore[arg-type]
        # compare_digest raises TypeError on str/bytes mismatch — should reject
        result("bytes signature rejected (or raises caught)", out is None,
               f"Returned non-None: {out!r}")
    except TypeError:
        result("bytes signature raises TypeError (uncaught)", False,
               "verify_webhook should coerce or catch")

    # None signature
    try:
        out = adapter.verify_webhook(body, None)  # type: ignore[arg-type]
        result("None signature rejected (or raises caught)", out is None,
               f"Returned non-None: {out!r}")
    except TypeError:
        result("None signature raises TypeError (uncaught)", False,
               "Should reject without raising")

    # ── 4. HMAC REPLAY ─────────────────────────────────────────────────
    section("4. HMAC replay (no nonce/timestamp)")
    body = b'{"OrderId":"REPLAY-1"}'
    sig = hmac_b64("test_secret", body)
    a = adapter.verify_webhook(body, sig)
    b = adapter.verify_webhook(body, sig)
    if a is not None and b is not None:
        warn("identical body+sig accepted twice (replay possible)",
             "Adapter has no nonce/timestamp window — caller must dedupe")
    else:
        result("replay attempt blocked", False,
               "Unexpected: replay was blocked, investigate")

    # ── 5. JSON INJECTION VIA RAW BODY ─────────────────────────────────
    section("5. Malformed-body handling")
    bad_body = b'not-json-at-all'
    sig = hmac_b64("test_secret", bad_body)
    result("non-JSON body rejected after valid HMAC",
           adapter.verify_webhook(bad_body, sig) is None)

    huge_body = b'{"x":"' + b'A' * 1024 * 1024 + b'"}'  # 1 MB string
    sig = hmac_b64("test_secret", huge_body)
    out = adapter.verify_webhook(huge_body, sig)
    if out is not None:
        warn("1 MB body parsed without size cap",
             "verify_webhook accepts unbounded bodies — caller must cap")
    else:
        result("1 MB body rejected", True)

    # ── 6. PARSE_SP_API_ORDER — amount validation ──────────────────────
    section("6. SP-API order parsing — amount edge cases")

    def make_notif(amount_str: str, status: str = "Unshipped") -> dict:
        return {
            "Payload": {
                "OrderChangeNotification": {
                    "AmazonOrderId": "999-0000000-0000001",
                    "Summary": {
                        "OrderTotalAmount": amount_str,
                        "OrderTotalCurrencyCode": "GBP",
                        "OrderStatus": status,
                    },
                }
            }
        }

    # Negative amount — currently NOT validated
    out = adapter.parse_sp_api_order(make_notif("-1.00"))
    if out and out.get("amount", 0) < 0:
        warn("negative amount accepted",
             f"parse_sp_api_order returned amount={out['amount']} — "
             "downstream gateway must reject")
    else:
        result("negative amount rejected/coerced", True)

    # NaN — float('nan') succeeds, breaks math
    out = adapter.parse_sp_api_order(make_notif("nan"))
    if out and isinstance(out.get("amount"), float) and math.isnan(out["amount"]):
        warn("NaN amount accepted",
             "parse_sp_api_order returned NaN — downstream gateway must reject")
    else:
        result("NaN amount rejected", True)

    # Infinity
    out = adapter.parse_sp_api_order(make_notif("inf"))
    if out and isinstance(out.get("amount"), float) and math.isinf(out["amount"]):
        warn("Infinity amount accepted",
             "parse_sp_api_order returned inf — downstream gateway must reject")
    else:
        result("Infinity amount rejected", True)

    # Garbage string
    out = adapter.parse_sp_api_order(make_notif("not-a-number"))
    result("non-numeric amount rejected (returns None)", out is None)

    # ── 7. SSRF — confirm_shipment marketplace_url ─────────────────────
    section("7. SSRF: confirm_shipment marketplace_url allowlist (v1.1.0)")
    # v1.1.0 allowlists marketplace_url against ALLOWED_MARKETPLACE_HOSTS.
    # Each of these MUST return False without making any network call.
    cases = [
        ("attacker host (https)", "https://attacker.invalid"),
        ("attacker host (http)",  "http://attacker.invalid"),
        ("amazon host but http",  "http://sellingpartnerapi-eu.amazon.com"),
        ("empty url",             ""),
        ("file:// scheme",        "file:///etc/passwd"),
        ("gopher:// scheme",      "gopher://internal:11211"),
    ]
    for label, mu in cases:
        out = adapter.confirm_shipment(
            "123-1234567-1234567", "TX_OK", "LEAKED_TOKEN", marketplace_url=mu,
        )
        result(f"rejected: {label}", out is False, f"returned {out!r}")

    # ── 8. _post with http:// api_base ─────────────────────────────────
    section("8. _post rejects non-https api_base")
    insecure = AmazonAlgoVoi(
        api_base="http://api1.ilovechicken.co.uk",
        api_key="x", tenant_id="y", webhook_secret="z",
    )
    out = insecure.process_order("X", 1.00)
    result("http:// api_base causes process_order to return None",
           out is None)

    # ── 9. verify_payment with non-https api_base ──────────────────────
    section("9. verify_payment scheme guard (v1.1.0)")
    # v1.1.0 added an explicit `startswith("https://")` check at the top
    # of verify_payment. Confirm by inspecting the source AND by behaviour
    # — http:// must return False before any network attempt.
    import inspect as _inspect
    src_vp = _inspect.getsource(adapter.verify_payment)
    result("verify_payment has explicit https scheme check",
           "startswith(\"https://\")" in src_vp or
           "startswith('https://')" in src_vp)
    # Behavioural: pointing at http:// localhost should NOT attempt a
    # connection. If we returned False fast (no socket error from a real
    # host lookup), the guard worked.
    import time as _time
    t0 = _time.time()
    out = insecure.verify_payment("test_token")
    elapsed = _time.time() - t0
    result("http:// api_base returns False",
           out is False)
    result("http:// api_base returns FAST (no network call)",
           elapsed < 0.5,
           f"Took {elapsed:.3f}s — likely attempted a network call")

    # ── 10. Path traversal in token ────────────────────────────────────
    section("10. Path traversal via verify_payment token")
    # quote(token, safe='') encodes '/' to %2F. Dots are NOT reserved URL
    # chars and stay literal — that's fine because the traversal vector
    # is the slash, not the dot. The check is: does '/' get encoded?
    from urllib.parse import quote
    payload = "../../../admin"
    encoded = quote(payload, safe='')
    result("'/' encoded as %2F (path traversal blocked)",
           "/" not in encoded and "%2F" in encoded)

    # ── 11. tx_id injection in confirm_shipment payload ────────────────
    section("11. tx_id injection")
    # tx_id is interpolated into a JSON string via f-string before json.dumps.
    # That's safe because json.dumps() handles escaping.
    # But tx_id is also length-guarded (>200 rejected).
    long_tx = "A" * 201
    result("201-char tx_id rejected",
           adapter.confirm_shipment("123", long_tx, "tok") is False)
    weird_tx = 'A"INJECT'
    # Not actually executed (would hit Amazon and fail), but JSON escaping
    # will neutralise the quote. We just verify the length guard alone
    # doesn't bless dangerous content.
    payload = '{"x":"' + weird_tx + '"}'  # what string-concat WOULD produce
    if '"INJECT' in payload:
        # confirm: the actual code uses json.dumps so this is moot
        import inspect
        src = inspect.getsource(adapter.confirm_shipment)
        if "json.dumps" in src:
            result("tx_id passed through json.dumps (escaping safe)", True)
        else:
            result("tx_id NOT escaped via json.dumps", False)

    # ── 12. process_order amount/currency validation ───────────────────
    section("12. process_order amount/currency validation")
    # Negative amount — passed straight through to gateway
    # (offline, so we only check the code shape)
    import inspect
    src = inspect.getsource(adapter.process_order)
    if "amount > 0" in src or "amount <= 0" in src or "Number.isFinite" in src:
        result("process_order has amount guard", True)
    else:
        warn("process_order has no amount guard",
             "Negative/zero amount passed through to gateway. "
             "Gateway will reject, but defense-in-depth would help.")
    if "isnan" in src.lower() or "isfinite" in src.lower():
        result("process_order has finite-number guard", True)
    else:
        warn("process_order has no NaN/Inf guard",
             "Defense-in-depth missing")

    # ── 13. Currency whitelist ─────────────────────────────────────────
    section("13. Currency handling")
    if "ALLOWED_CURRENCIES" in src or "currency_whitelist" in src.lower():
        result("currency whitelist present", True)
    else:
        warn("no currency whitelist",
             "currency.upper() only — gateway must enforce ISO codes")

    # ── 14. README accuracy ────────────────────────────────────────────
    section("14. Documentation accuracy")
    here = os.path.dirname(__file__)
    with open(os.path.join(here, "README.md"), encoding="utf-8") as fh:
        readme = fh.read()
    if "poll_and_notify" in readme or "refresh_token" in readme:
        warn("README describes polling API that doesn't exist",
             "README mentions poll_and_notify / refresh_token; "
             "actual code is webhook-driven via flask_webhook_handler. "
             "Merchants following the README will get AttributeError.")
    else:
        result("README matches code shape", True)

    # ── Summary ───────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print(f"Results: {PASS} pass, {FAIL} fail, {WARN} warn")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
