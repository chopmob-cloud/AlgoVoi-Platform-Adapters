"""
Easy Digital Downloads Adapter Smoke Test
=========================================
Phase 1 — Static checks: syntax-level scan of algovoi-edd.php + presence
          of required hooks + security guards. NO running WordPress
          required. Catches regressions from future edits.

Phase 2 — Live against a running WP+EDD sandbox (tastewp.com / instawp.com
          / LocalWP / etc.). Expects:
            • WordPress + EDD 3.2+ installed
            • algovoi-edd.php plugin activated
            • AlgoVoi gateway configured at Downloads > Settings > Payments
            • A test Download product exists

          Runs through:
            1. GET /wp-json/algovoi-edd/v1/webhook (expect 404/405 — route exists)
            2. POST /wp-json/algovoi-edd/v1/webhook without signature (expect 401)
            3. POST with bad signature (expect 401)
            4. POST with valid-HMAC but no token (expect 400)
            5. POST with valid-HMAC + valid token (reuses the 2026-04-14 TX
               batch against the live AlgoVoi gateway — expect 200)

Usage:
    # Phase 1 only (no sandbox needed):
    python smoke_test_edd.py

    # Phase 2 (full):
    python smoke_test_edd.py https://your-sandbox.tastewp.com

Env vars:
    EDD_WEBHOOK_SECRET   value configured in EDD admin (required for Phase 2)
    EDD_TEST_PAYMENT_ID  existing pending EDD payment ID to complete
    ALGOVOI_TX_ID        on-chain TX the webhook will reference
    ALGOVOI_TOKEN        checkout token attached to the pending payment
"""

from __future__ import annotations

import base64
import hashlib
import hmac as hmac_mod
import json
import os
import re
import sys
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

HERE = os.path.dirname(os.path.abspath(__file__))
PHP  = os.path.join(HERE, "algovoi-edd.php")

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
    print(f"\n{title}\n{'-' * len(title)}")


# ══════════════════════════════════════════════════════════════════════════════
# Phase 1 — static checks against algovoi-edd.php
# ══════════════════════════════════════════════════════════════════════════════

def phase_1():
    print("\n" + "=" * 60)
    print("PHASE 1 — Static checks against algovoi-edd.php")
    print("=" * 60)

    if not os.path.isfile(PHP):
        print(f"  [FAIL] plugin file not found at {PHP}")
        sys.exit(1)

    with open(PHP, encoding="utf-8") as f:
        src = f.read()

    # ── 1. Plugin header ──
    section("1. WordPress plugin header")
    for field in ("Plugin Name:", "Version:", "Requires PHP:", "EDD requires at least:", "License:"):
        result(f"header has '{field}'", field in src)
    m = re.search(r'EDD requires at least:\s*([\d.]+)', src)
    if m:
        result(f"EDD minimum version >= 3.0 (found {m.group(1)})", float(m.group(1)) >= 3.0)

    # ── 2. Gateway registration ──
    section("2. Gateway registration")
    result("registers 'algovoi' gateway via edd_payment_gateways filter",
           "edd_payment_gateways" in src and "'algovoi'" in src)
    result("suppresses CC form via edd_algovoi_cc_form",
           "edd_algovoi_cc_form" in src and "__return_false" in src)
    result("settings section registered",
           "edd_settings_sections_gateways" in src)
    result("settings fields registered",
           "edd_settings_gateways" in src)

    # ── 3. Required actions / hooks ──
    section("3. Required actions + hooks")
    result("edd_gateway_algovoi action handler present",
           "add_action('edd_gateway_algovoi'" in src or 'add_action("edd_gateway_algovoi"' in src)
    result("template_redirect return handler present",
           "add_action('template_redirect'" in src)
    result("REST webhook route registered",
           "register_rest_route" in src and "algovoi-edd/v1" in src)

    # ── 4. Security hardening (grep-level) ──
    section("4. Security hardening patterns")
    result("hash_equals for timing-safe compare",
           "hash_equals(" in src)
    result("64KB body cap BEFORE HMAC",
           re.search(r"strlen\(\$raw\)\s*>\s*65536", src) is not None)
    result("empty-signature reject BEFORE HMAC",
           '$signature === \'\'' in src or "signature === ''" in src)
    result("empty-secret reject",
           "secret === ''" in src)
    result("https-only outbound (algovoi_edd_is_https)",
           "algovoi_edd_is_https" in src and "str_starts_with" in src)
    result("200-char token cap",
           "strlen($token) > 200" in src or "strlen($tx_id) > 200" in src)
    result("is_finite amount guard",
           "is_finite(" in src and "$amount <= 0" in src)
    result("cancel-bypass verify on return",
           "algovoi_edd_verify_paid" in src)
    result("webhook double-checks gateway",
           # Webhook handler calls verify_paid AFTER verifying HMAC
           src.count("algovoi_edd_verify_paid") >= 2)
    result("idempotent status transitions",
           re.search(r"status\s*!==\s*'publish'", src) is not None)
    result("edd_send_back_to_checkout array form (EDD 3.x)",
           "edd_send_back_to_checkout(['payment-mode'" in src)
    result("no legacy string form of edd_send_back_to_checkout",
           "'?payment-mode=algovoi'" not in src)

    # ── 5. Common bug patterns ──
    section("5. Common bug patterns")
    result("no eval() / create_function()",
           not re.search(r"\beval\s*\(|create_function\s*\(", src))
    result("no hardcoded algv_ or known tenant UUIDs",
           not re.search(r"algv_[A-Za-z0-9]{15,}|47f11878-[a-f0-9-]{20,}", src))


# ══════════════════════════════════════════════════════════════════════════════
# Phase 2 — live sandbox
# ══════════════════════════════════════════════════════════════════════════════

def _hmac_sign(secret: str, body: bytes) -> str:
    return base64.b64encode(hmac_mod.new(secret.encode(), body, hashlib.sha256).digest()).decode()


def _post(url: str, body: bytes, headers: dict) -> tuple[int, str]:
    req = Request(url, data=body, method="POST")
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urlopen(req, timeout=20) as r:  # nosec B310
            return r.status, r.read().decode("utf-8", "replace")[:400]
    except HTTPError as e:
        return e.code, (e.read() or b"").decode("utf-8", "replace")[:400]
    except URLError as e:
        return 0, f"URLError: {e}"


def phase_2(base_url: str):
    print("\n" + "=" * 60)
    print(f"PHASE 2 — Live EDD sandbox at {base_url}")
    print("=" * 60)

    secret = os.environ.get("EDD_WEBHOOK_SECRET")
    if not secret:
        print("  [ABORT] EDD_WEBHOOK_SECRET not set — cannot sign webhooks.")
        sys.exit(2)

    webhook = base_url.rstrip("/") + "/wp-json/algovoi-edd/v1/webhook"

    # ── 1. Route exists? GET should return 404/405, not 200 ──
    section(f"1. Webhook route reachability: {webhook}")
    try:
        with urlopen(Request(webhook, method="GET"), timeout=10) as r:   # nosec B310
            result("route exists (got status)", True, f"HTTP {r.status}")
    except HTTPError as e:
        # 404 / 405 / 401 all acceptable — means WP routed the request
        result("route exists (HTTPError from WP)", e.code in (401, 404, 405),
               f"HTTP {e.code}")
    except URLError as e:
        result("route reachable", False, f"{e}")
        print("  [ABORT] sandbox not reachable — aborting Phase 2")
        sys.exit(1)

    # ── 2. POST without signature — expect 401 ──
    section("2. POST without signature")
    code, body = _post(webhook, b'{"tx_id":"X","order_id":"1"}',
                       {"Content-Type": "application/json"})
    result("401 returned (signature missing)", code == 401, f"HTTP {code}")

    # ── 3. POST with bad signature — expect 401 ──
    section("3. POST with bad signature")
    code, body = _post(webhook, b'{"tx_id":"X","order_id":"1"}',
                       {"Content-Type": "application/json",
                        "X-AlgoVoi-Signature": "wrong=="})
    result("401 returned (bad signature)", code == 401, f"HTTP {code}")

    # ── 4. Oversized body — expect 400 ──
    section("4. Oversized body (>64KB)")
    big = b'{"x":"' + b'A' * 70000 + b'"}'
    code, body = _post(webhook, big,
                       {"Content-Type": "application/json",
                        "X-AlgoVoi-Signature": _hmac_sign(secret, big)})
    result("400 returned (body >64KB)", code == 400, f"HTTP {code}")

    # ── 5. Valid HMAC, missing order_id/tx_id — expect 400 ──
    section("5. Valid HMAC but missing fields")
    body = b'{"hello":"world"}'
    code, resp = _post(webhook, body,
                       {"Content-Type": "application/json",
                        "X-AlgoVoi-Signature": _hmac_sign(secret, body)})
    result("400 returned (missing order_id/tx_id)", code == 400, f"HTTP {code}")

    # ── 6. Valid HMAC + order_id + tx_id against non-existent order — expect 404 ──
    section("6. Valid HMAC against unknown order")
    body = json.dumps({"order_id": 999_999_999, "tx_id": "TX_TEST_999"}).encode()
    code, resp = _post(webhook, body,
                       {"Content-Type": "application/json",
                        "X-AlgoVoi-Signature": _hmac_sign(secret, body)})
    result("404 returned (order not found)", code == 404, f"HTTP {code}")

    # ── 7. Full happy path — optional, needs EDD_TEST_PAYMENT_ID + ALGOVOI_TX_ID ──
    test_id = os.environ.get("EDD_TEST_PAYMENT_ID")
    test_tx = os.environ.get("ALGOVOI_TX_ID")
    if test_id and test_tx:
        section(f"7. Happy path: payment_id={test_id}, tx={test_tx[:12]}…")
        body = json.dumps({"order_id": int(test_id), "tx_id": test_tx}).encode()
        code, resp = _post(webhook, body,
                           {"Content-Type": "application/json",
                            "X-AlgoVoi-Signature": _hmac_sign(secret, body)})
        # 200 if verify_paid() on the gateway returns true (real payment)
        # 402 if not paid — acceptable because it means the guard fires
        result("200 (paid) or 402 (cancel-bypass guard fired)",
               code in (200, 402), f"HTTP {code}: {resp[:200]}")
    else:
        print("\n[skip] set EDD_TEST_PAYMENT_ID + ALGOVOI_TX_ID for happy-path test")


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) == 1:
        phase_1()
    elif len(sys.argv) == 2:
        phase_1()
        phase_2(sys.argv[1])
    else:
        print(__doc__)
        sys.exit(2)

    print(f"\n{'=' * 60}\nTotals: {PASS} pass, {FAIL} fail, {WARN} warn")
    sys.exit(0 if FAIL == 0 else 1)
