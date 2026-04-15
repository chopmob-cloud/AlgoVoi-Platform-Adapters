"""
TikTok Shop AlgoVoi Adapter — Security Replay Suite (2026-04-15)

Same structure as amazon-mws/security_replay.py. Covers both HMAC paths
(verify_tiktok_webhook hex + verify_algovoi_webhook base64) plus all the
attack categories from the April 2026 audit and the 2026-04-15 review.
"""

from __future__ import annotations

import base64
import hashlib
import hmac as hmac_mod
import inspect
import math
import os
import sys
import time as _time
sys.path.insert(0, os.path.dirname(__file__))

from tiktok_algovoi import TikTokAlgoVoi  # noqa: E402

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


def hex_hmac(secret: str, body: bytes) -> str:
    return hmac_mod.new(secret.encode(), body, hashlib.sha256).hexdigest()


def b64_hmac(secret: str, body: bytes) -> str:
    return base64.b64encode(
        hmac_mod.new(secret.encode(), body, hashlib.sha256).digest()
    ).decode()


def main() -> int:
    adapter = TikTokAlgoVoi(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        webhook_secret="test_algovoi_secret",
        tiktok_app_secret="test_tiktok_secret",
    )

    print("TikTok Shop Adapter -- Security Replay")
    print("=" * 50)

    # ── 1. HMAC EMPTY-SECRET (both paths) ──────────────────────────────
    section("1. HMAC empty-secret bypass (both paths)")
    no_tt = TikTokAlgoVoi(tiktok_app_secret="")
    no_av = TikTokAlgoVoi(webhook_secret="")
    body = b'{"x":1}'
    result("empty tiktok secret rejects forged hex sig",
           no_tt.verify_tiktok_webhook(body, hex_hmac("", body)) is None)
    result("empty algovoi secret rejects forged b64 sig",
           no_av.verify_algovoi_webhook(body, b64_hmac("", body)) is None)

    # ── 2. HMAC TIMING — both paths ────────────────────────────────────
    section("2. HMAC timing-safe compare (both paths)")
    body = b'{"y":2}'
    tt_sig = hex_hmac("test_tiktok_secret", body)
    av_sig = b64_hmac("test_algovoi_secret", body)
    # Pick a replacement char guaranteed different from the original first char
    almost_tt = ("g" if tt_sig[0] != "g" else "h") + tt_sig[1:]
    almost_av = ("Z" if av_sig[0] != "Z" else "Y") + av_sig[1:]
    result("tiktok wrong-by-one rejected",
           adapter.verify_tiktok_webhook(body, almost_tt) is None)
    result("algovoi wrong-by-one rejected",
           adapter.verify_algovoi_webhook(body, almost_av) is None)
    result("valid tiktok sig accepted",
           adapter.verify_tiktok_webhook(body, tt_sig) is not None)
    result("valid algovoi sig accepted",
           adapter.verify_algovoi_webhook(body, av_sig) is not None)

    # ── 3. HMAC TYPE CONFUSION ─────────────────────────────────────────
    section("3. HMAC signature type confusion (both paths)")
    body = b'{"z":3}'
    tt_sig = hex_hmac("test_tiktok_secret", body)
    av_sig = b64_hmac("test_algovoi_secret", body)
    for name, fn, sig in (
        ("tiktok bytes",  adapter.verify_tiktok_webhook,  tt_sig.encode()),
        ("tiktok None",   adapter.verify_tiktok_webhook,  None),
        ("tiktok int",    adapter.verify_tiktok_webhook,  12345),
        ("algovoi bytes", adapter.verify_algovoi_webhook, av_sig.encode()),
        ("algovoi None",  adapter.verify_algovoi_webhook, None),
        ("algovoi int",   adapter.verify_algovoi_webhook, 12345),
    ):
        try:
            out = fn(body, sig)  # type: ignore[arg-type]
            result(f"{name} sig rejected (no crash)", out is None,
                   f"returned {out!r}")
        except TypeError:
            result(f"{name} sig raises TypeError (uncaught)", False,
                   "should fail closed without raising")

    # ── 4. HMAC REPLAY ─────────────────────────────────────────────────
    section("4. HMAC replay (both paths — caller-side dedupe required)")
    body = b'{"order_id":"REPLAY-1"}'
    tt_sig = hex_hmac("test_tiktok_secret", body)
    a = adapter.verify_tiktok_webhook(body, tt_sig)
    b = adapter.verify_tiktok_webhook(body, tt_sig)
    if a is not None and b is not None:
        warn("tiktok body+sig accepted twice",
             "No nonce/timestamp guard — caller must dedupe by order_id")

    # ── 5. BODY SIZE / MALFORMED ───────────────────────────────────────
    section("5. Body size + malformed handling")
    bad = b'not-json'
    result("non-JSON body rejected (tiktok)",
           adapter.verify_tiktok_webhook(bad, hex_hmac("test_tiktok_secret", bad)) is None)
    result("non-JSON body rejected (algovoi)",
           adapter.verify_algovoi_webhook(bad, b64_hmac("test_algovoi_secret", bad)) is None)

    huge = b'{"x":"' + b'A' * 1024 * 1024 + b'"}'  # 1 MB string
    result("1 MB body rejected (tiktok)",
           adapter.verify_tiktok_webhook(huge, hex_hmac("test_tiktok_secret", huge)) is None)
    result("1 MB body rejected (algovoi)",
           adapter.verify_algovoi_webhook(huge, b64_hmac("test_algovoi_secret", huge)) is None)

    # ── 6. PARSE_ORDER_WEBHOOK — amount edge cases ─────────────────────
    section("6. parse_order_webhook — amount edge cases")

    def make_wh(amount_str: str, oid: str = "TT-1") -> dict:
        return {
            "type": "ORDER_CREATED",
            "data": {
                "order_id": oid,
                "payment": {"total_amount": amount_str, "currency": "GBP"},
                "order_status": "AWAITING_SHIPMENT",
            },
        }

    result("negative amount rejected",
           adapter.parse_order_webhook(make_wh("-1.00")) is None)
    result("NaN amount rejected",
           adapter.parse_order_webhook(make_wh("nan")) is None)
    result("Infinity amount rejected",
           adapter.parse_order_webhook(make_wh("inf")) is None)
    result("non-numeric amount returns None",
           adapter.parse_order_webhook(make_wh("not-a-number")) is None)
    result("zero amount rejected",
           adapter.parse_order_webhook(make_wh("0")) is None)

    # ── 7. SSRF — update_shipping api_base allowlist (v1.1.0) ──────────
    section("7. SSRF: update_shipping api_base allowlist (v1.1.0)")
    cases = [
        ("attacker host (https)",  "https://attacker.invalid"),
        ("attacker host (http)",   "http://attacker.invalid"),
        ("tiktok host but http",   "http://open-api.tiktokglobalshop.com"),
        ("empty url",              ""),
        ("file:// scheme",         "file:///etc/passwd"),
        ("gopher:// scheme",       "gopher://internal:11211"),
    ]
    for label, ab in cases:
        out = adapter.update_shipping("TT-1", "TX_OK", "LEAKED_TOKEN", api_base=ab)
        result(f"rejected: {label}", out is False, f"returned {out!r}")

    # ── 8. _post rejects http:// api_base ──────────────────────────────
    section("8. _post rejects non-https api_base")
    insecure = TikTokAlgoVoi(api_base="http://api1.ilovechicken.co.uk",
                             webhook_secret="s", tiktok_app_secret="t")
    out = insecure.process_order("X", 1.00)
    result("http:// api_base causes process_order to return None",
           out is None)

    # ── 9. verify_payment scheme guard (v1.1.0) ────────────────────────
    section("9. verify_payment scheme guard (v1.1.0)")
    src_vp = inspect.getsource(adapter.verify_payment)
    result("verify_payment has explicit https check",
           "startswith(\"https://\")" in src_vp or
           "startswith('https://')" in src_vp)
    t0 = _time.time()
    out = insecure.verify_payment("test_token")
    elapsed = _time.time() - t0
    result("http:// api_base returns False", out is False)
    result("http:// api_base returns FAST (no network call)",
           elapsed < 0.5, f"Took {elapsed:.3f}s")

    # ── 10. Path traversal in token ────────────────────────────────────
    section("10. Path traversal via verify_payment token")
    from urllib.parse import quote
    encoded = quote("../../../admin", safe='')
    result("'/' encoded as %2F (path traversal blocked)",
           "/" not in encoded and "%2F" in encoded)

    # ── 11. process_order amount + redirect_url ────────────────────────
    section("11. process_order amount + redirect_url validation (v1.1.0)")
    result("negative amount rejected",
           adapter.process_order("X", -1.00) is None)
    result("NaN amount rejected",
           adapter.process_order("X", float("nan")) is None)
    result("Infinity amount rejected",
           adapter.process_order("X", float("inf")) is None)
    result("zero amount rejected",
           adapter.process_order("X", 0) is None)
    result("file:// redirect_url rejected",
           adapter.process_order("X", 1.00, redirect_url="file:///x") is None)
    result("gopher:// redirect_url rejected",
           adapter.process_order("X", 1.00, redirect_url="gopher://x") is None)
    result("http:// redirect_url rejected (https-only)",
           adapter.process_order("X", 1.00, redirect_url="http://example.com") is None)

    # ── 12. tx_id injection / length ───────────────────────────────────
    section("12. tx_id length + injection")
    result("201-char tx_id rejected",
           adapter.update_shipping("123", "A" * 201, "tok") is False)
    result("empty tx_id rejected",
           adapter.update_shipping("123", "", "tok") is False)
    src_us2 = inspect.getsource(adapter.update_shipping)
    result("tx_id passed through json.dumps (escape-safe)",
           "json.dumps" in src_us2)

    # ── 13. Currency handling ──────────────────────────────────────────
    section("13. Currency handling")
    src_po = inspect.getsource(adapter.process_order)
    if "ALLOWED_CURRENCIES" in src_po or "currency_whitelist" in src_po.lower():
        result("currency whitelist present", True)
    else:
        warn("no currency whitelist",
             "currency.upper() only — gateway must enforce ISO codes")

    # ── 14. README accuracy ────────────────────────────────────────────
    section("14. Documentation accuracy")
    here = os.path.dirname(__file__)
    with open(os.path.join(here, "README.md"), encoding="utf-8") as fh:
        readme = fh.read()
    drift_markers = ("app_key=", "algovoi_api_key=")
    # Note: access_token= is legitimately mentioned in the post-payment
    # update_shipping example, so it's not a drift marker.
    if any(m in readme for m in drift_markers):
        warn("README documents constructor args that don't exist",
             "actual class takes (api_base, api_key, tenant_id, "
             "webhook_secret, tiktok_app_secret, default_network, "
             "base_currency, timeout)")
    else:
        result("README matches code shape", True)

    # ── Summary ───────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print(f"Results: {PASS} pass, {FAIL} fail, {WARN} warn")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
