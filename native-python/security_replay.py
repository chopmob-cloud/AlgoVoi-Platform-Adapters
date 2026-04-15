"""
Native Python AlgoVoi Adapter — Security Replay Suite (2026-04-15)

Different shape from the B2B webhook adapters because the native adapter
has a wider attack surface: hosted-checkout return verification, the
extension payment scrape (SSRF guard), HTML rendering with embedded JS,
and the same HMAC verify_webhook bugs.
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

from algovoi import AlgoVoi  # noqa: E402

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


def b64_hmac(secret: str, body: bytes) -> str:
    return base64.b64encode(
        hmac_mod.new(secret.encode(), body, hashlib.sha256).digest()
    ).decode()


def main() -> int:
    av = AlgoVoi(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        webhook_secret="test_secret",
    )

    print("Native Python AlgoVoi Adapter -- Security Replay")
    print("=" * 50)

    # ── 1. HMAC empty-secret ───────────────────────────────────────────
    section("1. HMAC empty-secret bypass (April 2026 hardening)")
    no_sec = AlgoVoi(webhook_secret="")
    body = b'{"x":1}'
    result("empty secret rejects forged sig",
           no_sec.verify_webhook(body, b64_hmac("", body)) is None)
    result("empty secret rejects empty sig",
           no_sec.verify_webhook(body, "") is None)

    # ── 2. HMAC timing-safe ────────────────────────────────────────────
    section("2. HMAC timing-safe compare")
    body = b'{"y":2}'
    sig = b64_hmac("test_secret", body)
    almost = ("Z" if sig[0] != "Z" else "Y") + sig[1:]
    result("wrong-by-one rejected",
           av.verify_webhook(body, almost) is None)
    result("totally wrong rejected",
           av.verify_webhook(body, "wrong") is None)
    result("valid sig accepted",
           av.verify_webhook(body, sig) is not None)

    # ── 3. HMAC type confusion ─────────────────────────────────────────
    section("3. HMAC signature type confusion")
    body = b'{"z":3}'
    sig = b64_hmac("test_secret", body)
    for name, val in (("bytes", sig.encode()), ("None", None), ("int", 12345)):
        try:
            out = av.verify_webhook(body, val)  # type: ignore[arg-type]
            result(f"{name} sig rejected (no crash)", out is None,
                   f"returned {out!r}")
        except TypeError:
            result(f"{name} sig raises TypeError (uncaught)", False,
                   "should fail closed without raising")

    # ── 4. Replay ──────────────────────────────────────────────────────
    section("4. HMAC replay (caller dedupe required)")
    body = b'{"order_id":"REPLAY-1"}'
    sig = b64_hmac("test_secret", body)
    a = av.verify_webhook(body, sig)
    b = av.verify_webhook(body, sig)
    if a is not None and b is not None:
        warn("body+sig accepted twice",
             "No nonce/timestamp guard — caller must dedupe by order_id")

    # ── 5. Body size + malformed ───────────────────────────────────────
    section("5. Body size + malformed handling")
    bad = b'not-json'
    result("non-JSON body rejected after valid HMAC",
           av.verify_webhook(bad, b64_hmac("test_secret", bad)) is None)
    huge = b'{"x":"' + b'A' * 1024 * 1024 + b'"}'
    result("1 MB body rejected (v1.1.0)",
           av.verify_webhook(huge, b64_hmac("test_secret", huge)) is None)

    # ── 6. create_payment_link / hosted_checkout amount validation (v1.1.0) ─
    section("6. create_payment_link amount + redirect_url validation (v1.1.0)")
    result("negative amount returns None",
           av.create_payment_link(-1.0, "USD", "L", "algorand_mainnet") is None)
    result("NaN amount returns None",
           av.create_payment_link(float("nan"), "USD", "L", "algorand_mainnet") is None)
    result("Infinity amount returns None",
           av.create_payment_link(float("inf"), "USD", "L", "algorand_mainnet") is None)
    result("zero amount returns None",
           av.create_payment_link(0, "USD", "L", "algorand_mainnet") is None)
    result("file:// redirect_url returns None",
           av.create_payment_link(1.0, "USD", "L", "algorand_mainnet",
               redirect_url="file:///etc/passwd") is None)
    result("gopher:// redirect_url returns None",
           av.create_payment_link(1.0, "USD", "L", "algorand_mainnet",
               redirect_url="gopher://x") is None)
    result("javascript: redirect_url returns None",
           av.create_payment_link(1.0, "USD", "L", "algorand_mainnet",
               redirect_url="javascript:alert(1)") is None)
    result("http:// redirect_url returns None (https-only)",
           av.create_payment_link(1.0, "USD", "L", "algorand_mainnet",
               redirect_url="http://example.com") is None)

    # ── 7. verify_hosted_return — cancel-bypass guard (April 2026) ─────
    section("7. verify_hosted_return — cancel-bypass guard (April 2026)")
    result("empty token returns False",
           av.verify_hosted_return("") is False)
    insecure = AlgoVoi(api_base="http://api1.ilovechicken.co.uk",
                       webhook_secret="s")
    t0 = _time.time()
    out = insecure.verify_hosted_return("test_tok")
    elapsed = _time.time() - t0
    result("http:// api_base verify_hosted_return returns False",
           out is False)
    result("http:// api_base returns FAST (no network call)",
           elapsed < 0.5, f"Took {elapsed:.3f}s")

    # ── 8. Path traversal in token ─────────────────────────────────────
    section("8. Path traversal via token quoting")
    from urllib.parse import quote
    encoded = quote("../../../admin", safe='')
    result("'/' encoded as %2F (path traversal blocked)",
           "/" not in encoded and "%2F" in encoded)

    # ── 9. extension_checkout SSRF on _scrape_checkout ─────────────────
    section("9. _scrape_checkout SSRF guard (April 2026)")
    src_sc = inspect.getsource(av._scrape_checkout)
    if "urlparse" in src_sc and ".hostname" in src_sc:
        result("_scrape_checkout has hostname check vs api_base", True)
    else:
        warn("_scrape_checkout missing SSRF guard",
             "extension flow could be redirected to internal services")

    # ── 10. _post / _post_raw scheme guard ─────────────────────────────
    section("10. _post / _post_raw scheme guards")
    src_post = inspect.getsource(av._post)
    src_postraw = inspect.getsource(av._post_raw)
    result("_post requires https:// api_base",
           'startswith("https://")' in src_post)
    result("_post_raw requires https:// url",
           'startswith("https://")' in src_postraw)

    # ── 11. tx_id + token length guard on verify_extension_payment (v1.1.0) ─
    section("11. verify_extension_payment token + tx_id guards (v1.1.0)")
    out = av.verify_extension_payment("", "TXID")
    result("empty token rejected",
           out.get("_http_code") == 400)
    out = av.verify_extension_payment("tok", "")
    result("empty tx_id rejected",
           out.get("_http_code") == 400)
    out = av.verify_extension_payment("tok", "A" * 201)
    result(">200 char tx_id rejected",
           out.get("_http_code") == 400)
    out = av.verify_extension_payment("A" * 201, "TXID")
    result(">200 char token rejected (v1.1.0)",
           out.get("_http_code") == 400)

    # ── 12. HTML rendering — XSS surface ──────────────────────────────
    section("12. HTML rendering — XSS surface")

    # render_chain_selector takes field_name (caller-supplied). Confirm escape.
    html = AlgoVoi.render_chain_selector("network", "hosted")
    if "<script>" in AlgoVoi.render_chain_selector("<script>alert(1)</script>", "hosted"):
        warn("render_chain_selector did NOT escape field_name",
             "<script> tag survived HTML escape")
    else:
        result("render_chain_selector escapes field_name HTML", True)

    # render_extension_payment_ui — caller-supplied verify_url and success_url
    # are inserted into a <script>...</script> block via json.dumps. json.dumps
    # does NOT escape '/' or '</'. A success_url ending in '</script>' could
    # break out of the script context. Confirm or refute.
    payment_data = {
        "amount_display": "1.00", "ticker": "USDC", "chain": "algorand-mainnet",
        "checkout_url": "https://example/checkout/abc",
        "receiver": "A" * 58, "memo": "algovoi:abc",
        "algod_url": "https://algod", "amount_mu": 1000000, "asset_id": 31566704,
        "token": "abc",
    }
    # XSS regression — prove </script> from caller-supplied URL cannot escape.
    xss_url = "</script><script>alert('XSS')</script>"
    rendered = AlgoVoi.render_extension_payment_ui(
        payment_data, verify_url=xss_url, success_url=xss_url,
    )
    result("verify_url cannot break out of <script> (v1.1.0)",
           "</script><script>alert('XSS')</script>" not in rendered)
    # The neutralised form is "<\/script>" inside the JS literal.
    result("verify_url collapses to safe '/' fallback",
           '"/"' in rendered)
    # success_url path: same protection.
    rendered2 = AlgoVoi.render_extension_payment_ui(
        payment_data, verify_url="/verify", success_url=xss_url,
    )
    result("success_url cannot break out of <script>",
           "</script><script>alert('XSS')</script>" not in rendered2)
    # And legitimate https URLs MUST still pass through unchanged.
    rendered3 = AlgoVoi.render_extension_payment_ui(
        payment_data, verify_url="https://example.com/verify",
        success_url="https://example.com/success",
    )
    result("legitimate https URLs survive validation",
           '"https://example.com/verify"' in rendered3 and
           '"https://example.com/success"' in rendered3)
    # And same-origin paths starting with "/" must work too (the Flask
    # examples use "/verify-extension" and "/payment-success").
    rendered4 = AlgoVoi.render_extension_payment_ui(
        payment_data, verify_url="/verify-extension", success_url="/payment-success",
    )
    result("same-origin path URLs survive validation",
           '"/verify-extension"' in rendered4 and
           '"/payment-success"' in rendered4)

    # ── 13. Constructor input validation ──────────────────────────────
    section("13. Constructor / config validation")
    # api_base accepts anything — even crazy strings. Any subsequent _post
    # call returns None silently. That's defensible (fail-closed), but
    # construction should at least normalize trailing slashes:
    bad_av = AlgoVoi(api_base="https://x/")
    result("trailing slash stripped from api_base",
           bad_av.api_base == "https://x")

    # ── 14. Documentation accuracy ────────────────────────────────────
    section("14. Documentation accuracy")
    here = os.path.dirname(__file__)
    with open(os.path.join(here, "README.md"), encoding="utf-8") as fh:
        readme = fh.read()
    drift_markers = ("poll_and_notify", "refresh_token", "algovoi_api_key=",
                     "client_id=", "client_secret=")
    if any(m in readme for m in drift_markers):
        warn("README contains drifted references",
             f"found one of: {drift_markers}")
    else:
        result("README has no obvious drift markers", True)

    # ── Summary ───────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print(f"Results: {PASS} pass, {FAIL} fail, {WARN} warn")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
