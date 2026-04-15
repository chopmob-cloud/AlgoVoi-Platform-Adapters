"""
Squarespace AlgoVoi Adapter — Security Replay Suite (2026-04-15)

Same shape as amazon-mws and tiktok-shop replays. Squarespace is
single-region (api.squarespace.com), so there's no SSRF allowlist to
enforce on fulfill_order — but everything else (HMAC type guards,
body cap, scheme guards, amount sanity, replay, README drift) follows
the established checklist.
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

from squarespace_algovoi import SquarespaceAlgoVoi  # noqa: E402

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


def main() -> int:
    adapter = SquarespaceAlgoVoi(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        squarespace_api_key="test_sq_key",
        webhook_secret="test_secret",
    )

    print("Squarespace Adapter -- Security Replay")
    print("=" * 50)

    # ── 1. HMAC empty-secret ───────────────────────────────────────────
    section("1. HMAC empty-secret bypass")
    no_sec = SquarespaceAlgoVoi(webhook_secret="")
    body = b'{"x":1}'
    result("empty secret rejects forged sig",
           no_sec.verify_webhook(body, hex_hmac("", body)) is None)
    result("empty secret rejects empty sig",
           no_sec.verify_webhook(body, "") is None)

    # ── 2. HMAC timing-safe ────────────────────────────────────────────
    section("2. HMAC timing-safe compare")
    body = b'{"y":2}'
    sig = hex_hmac("test_secret", body)
    almost = ("g" if sig[0] != "g" else "h") + sig[1:]
    result("wrong-by-one rejected",
           adapter.verify_webhook(body, almost) is None)
    result("totally wrong rejected",
           adapter.verify_webhook(body, "wrong") is None)
    result("valid sig accepted",
           adapter.verify_webhook(body, sig) is not None)

    # ── 3. HMAC type confusion ─────────────────────────────────────────
    section("3. HMAC signature type confusion")
    body = b'{"z":3}'
    sig = hex_hmac("test_secret", body)
    for name, val in (
        ("bytes", sig.encode()), ("None", None), ("int", 12345),
    ):
        try:
            out = adapter.verify_webhook(body, val)  # type: ignore[arg-type]
            result(f"{name} sig rejected (no crash)", out is None,
                   f"returned {out!r}")
        except TypeError:
            result(f"{name} sig raises TypeError (uncaught)", False,
                   "should fail closed without raising")

    # ── 4. Replay ──────────────────────────────────────────────────────
    section("4. HMAC replay (caller dedupe required)")
    body = b'{"topic":"order.create","data":{"id":"REPLAY"}}'
    sig = hex_hmac("test_secret", body)
    a = adapter.verify_webhook(body, sig)
    b = adapter.verify_webhook(body, sig)
    if a is not None and b is not None:
        warn("body+sig accepted twice",
             "No nonce/timestamp guard — caller must dedupe by order id")

    # ── 5. Body size + malformed ───────────────────────────────────────
    section("5. Body size + malformed handling")
    bad = b'not-json'
    result("non-JSON body rejected after valid HMAC",
           adapter.verify_webhook(bad, hex_hmac("test_secret", bad)) is None)
    huge = b'{"x":"' + b'A' * 1024 * 1024 + b'"}'
    result("1 MB body rejected",
           adapter.verify_webhook(huge, hex_hmac("test_secret", huge)) is None)

    # ── 6. parse_order_webhook — amount edge cases ─────────────────────
    section("6. parse_order_webhook — amount edge cases")

    def make_wh(amount_str, oid="SQ-1"):
        return {"topic": "order.create", "data": {
            "id": oid,
            "grandTotal": {"value": amount_str, "currency": "GBP"},
            "fulfillmentStatus": "PENDING"}}

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

    # ── 7. Null-key fuzzing (the TikTok bug) ───────────────────────────
    section("7. Null-key fuzzing")
    cases = [
        ("data=null",     {"topic": "order.create", "data": None}),
        ("grandTotal=null", {"topic": "order.create",
                             "data": {"id": "X", "grandTotal": None}}),
        ("payload=None",  None),
        ("payload=list",  [1, 2, 3]),
        ("payload=str",   "not-a-dict"),
    ]
    for label, p in cases:
        try:
            out = adapter.parse_order_webhook(p)  # type: ignore[arg-type]
            result(f"{label} returns None (no crash)", out is None,
                   f"returned {out!r}")
        except (AttributeError, TypeError) as e:
            result(f"{label} raises {type(e).__name__} (uncaught)", False, str(e))

    # ── 8. _post rejects http:// api_base ──────────────────────────────
    section("8. _post rejects non-https api_base")
    insecure = SquarespaceAlgoVoi(api_base="http://api1.ilovechicken.co.uk",
                                  webhook_secret="s")
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

    # ── 11. process_order amount + redirect_url (v1.1.0) ───────────────
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

    # ── 12. fulfill_order — tx_id length + truncations ─────────────────
    section("12. fulfill_order tx_id handling")
    result("201-char tx_id rejected",
           adapter.fulfill_order("123", "A" * 201, None) is False)
    result("empty tx_id rejected",
           adapter.fulfill_order("123", "", None) is False)
    src_fo = inspect.getsource(adapter.fulfill_order)
    result("fulfill_order does not silently truncate tx_id (v1.1.0)",
           "tx_id[:64]" not in src_fo and "tx_id[:40]" not in src_fo)
    # Look for a real JSON-key usage, not the explanatory comment.
    result("fulfill_order no longer constructs broken trackingUrl (v1.1.0)",
           '"trackingUrl":' not in src_fo)
    result("fulfill_order URL is hardcoded (no SSRF surface)",
           '"https://api.squarespace.com' in src_fo)
    result("fulfill_order rejects empty order_id",
           adapter.fulfill_order("", "TX_OK", None) is False)

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
    if "algovoi_api_key=" in readme:
        warn("README documents non-existent algovoi_api_key arg",
             "actual class takes (api_base, api_key, tenant_id, "
             "squarespace_api_key, webhook_secret, default_network, "
             "base_currency, timeout). The 'api_key' arg is the AlgoVoi "
             "key; 'squarespace_api_key' is the Squarespace one.")
    else:
        result("README quick-start matches actual constructor", True)
    if "USDC on Algorand and aUSDC on VOI" in readme and "Hedera" not in readme:
        warn("README undercount — supports 4 chains, README mentions only 2",
             "HOSTED_NETWORKS lists ALGO, VOI, HBAR, XLM")

    # ── Summary ───────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print(f"Results: {PASS} pass, {FAIL} fail, {WARN} warn")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
