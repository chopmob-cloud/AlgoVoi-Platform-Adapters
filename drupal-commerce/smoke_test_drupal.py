"""
Drupal Commerce Adapter Smoke Test
==================================
Phase 1 — Static checks: grep-level scan of the module files for
          required hooks, annotations, DI patterns, and security
          guards. NO running Drupal required.

Phase 2 — Live against a running Drupal 10/11 + Commerce 2/3 sandbox
          (simplytest.me, Lando, DDEV, Pantheon Sandbox, etc.). Expects:
            • Drupal running at BASE_URL
            • Commerce + commerce_payment + commerce_algovoi modules enabled
            • AlgoVoi gateway configured (admin/commerce/config/payment-gateways)

          Exercises:
            1. GET /payment/notify/algovoi/<gateway_id> (route exists?)
            2. POST without signature → expect 401
            3. POST with bad signature → expect 401
            4. Oversized body → expect 400
            5. Valid HMAC, missing fields → expect 400
            6. Valid HMAC, unknown order → expect 404

Usage:
    # Phase 1 only:
    python smoke_test_drupal.py

    # Phase 2:
    python smoke_test_drupal.py https://sandbox.example/ algovoi_offsite

Env vars:
    DRUPAL_WEBHOOK_SECRET   value configured in the Drupal payment gateway
"""

from __future__ import annotations

import base64
import hashlib
import hmac as hmac_mod
import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

HERE = os.path.dirname(os.path.abspath(__file__))

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


def _read(path: str) -> str:
    with open(os.path.join(HERE, path), encoding="utf-8") as f:
        return f.read()


# ══════════════════════════════════════════════════════════════════════════════
# Phase 1 — static checks
# ══════════════════════════════════════════════════════════════════════════════

def phase_1():
    print("\n" + "=" * 60)
    print("PHASE 1 — Static checks against drupal-commerce module")
    print("=" * 60)

    # ── 1. Required files ──
    section("1. Required module files")
    required = [
        "commerce_algovoi.info.yml",
        "commerce_algovoi.routing.yml",
        "src/Plugin/Commerce/PaymentGateway/AlgoVoi.php",
        "src/PluginForm/OffsiteRedirect/PaymentOffsiteForm.php",
        "src/Controller/WebhookController.php",
        "README.md",
    ]
    for p in required:
        result(f"{p} exists", os.path.isfile(os.path.join(HERE, p)))

    # ── 2. info.yml declarations ──
    section("2. commerce_algovoi.info.yml")
    info = _read("commerce_algovoi.info.yml")
    result("type: module",                   "type: module" in info)
    result("core_version_requirement ^10/^11", "^10" in info and "^11" in info)
    result("depends on commerce_payment",    "commerce:commerce_payment" in info)
    result("depends on commerce_order",      "commerce:commerce_order" in info)
    result("version: 1.0.0",                 "version: '1.0.0'" in info or 'version: "1.0.0"' in info)
    result("configure: commerce_payment.payment_gateways",
           "configure: commerce_payment.payment_gateways" in info)

    # ── 3. routing.yml ──
    section("3. commerce_algovoi.routing.yml")
    routing = _read("commerce_algovoi.routing.yml")
    result("webhook route path correct",
           "/payment/notify/algovoi/{commerce_payment_gateway}" in routing)
    result("entity:commerce_payment_gateway parameter converter",
           "type: entity:commerce_payment_gateway" in routing)
    result("no_cache: 'TRUE' on webhook",
           "no_cache: 'TRUE'" in routing)

    # ── 4. Gateway plugin ──
    section("4. AlgoVoi payment gateway plugin")
    gw = _read("src/Plugin/Commerce/PaymentGateway/AlgoVoi.php")
    result("@CommercePaymentGateway annotation present", "@CommercePaymentGateway" in gw)
    result('id = "algovoi_offsite"', 'id = "algovoi_offsite"' in gw)
    result('payment_method_types = {} (correct for offsite crypto gateway)',
           "payment_method_types = {}" in gw)
    result("NO payment_method_types = credit_card (Comet finding)",
           '"credit_card"' not in gw)
    result("extends OffsitePaymentGatewayBase",
           "extends OffsitePaymentGatewayBase" in gw)
    result("DI via create() for http_client",
           'container->get(\'http_client\')' in gw or "container->get(\"http_client\")" in gw)
    result("DI for logger.factory",
           "logger.factory" in gw)
    result("DI for entity_type.manager",
           "entity_type.manager" in gw)
    result("no static \\Drupal::logger",
           "\\Drupal::logger(" not in gw and "Drupal::logger(" not in gw)
    result("no static \\Drupal::entityTypeManager",
           "\\Drupal::entityTypeManager(" not in gw and "Drupal::entityTypeManager(" not in gw)

    # ── 5. Security hardening ──
    section("5. Security hardening")
    result("cancel-bypass guard (onReturn calls verifyCheckoutPaid)",
           "verifyCheckoutPaid" in gw and "onReturn" in gw)
    result("hash_equals timing-safe",            "hash_equals(" in gw)
    result("empty-secret reject",                "webhook_secret" in gw and "empty(" in gw)
    result("body size cap 64KB",                 "65536" in gw or "64 * 1024" in gw or "MAX" in gw)
    result("startsWithHttps guard",              "startsWithHttps" in gw)
    result("200-char token cap",                 "200" in gw and "strlen(" in gw)
    result("amount is_finite + > 0",             "is_finite(" in gw and "<= 0" in gw)

    # ── 6. Redirect form ──
    section("6. PaymentOffsiteForm")
    form = _read("src/PluginForm/OffsiteRedirect/PaymentOffsiteForm.php")
    result("extends BasePaymentOffsiteForm",
           "extends BasePaymentOffsiteForm" in form)
    result("uses REDIRECT_GET (token is already in URL)",
           "REDIRECT_GET" in form)
    result("calls gateway createPaymentLink()",
           "createPaymentLink" in form)

    # ── 7. Webhook controller ──
    section("7. WebhookController")
    wc = _read("src/Controller/WebhookController.php")
    result("extends ControllerBase",            "extends ControllerBase" in wc)
    result("instanceof guard against AlgoVoi plugin class",
           "instanceof" in wc and "AlgoVoi" in wc)
    result("size guard BEFORE HMAC verify",     "65536" in wc or "64 * 1024" in wc)
    result("calls plugin->verifyWebhook",       "verifyWebhook" in wc)
    result("double-check via verifyCheckoutPaid",
           "verifyCheckoutPaid" in wc)
    result("idempotent loadByProperties check", "loadByProperties" in wc)

    # ── 8. No leaks ──
    section("8. No sensitive data")
    all_src = info + routing + gw + form + wc
    result("no hardcoded algv_ keys",
           not re.search(r"algv_[A-Za-z0-9]{15,}", all_src))
    result("no known prod tenant UUID",
           "47f11878-2bf4-4f86" not in all_src)


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


def phase_2(base_url: str, gateway_id: str = "algovoi_offsite"):
    print("\n" + "=" * 60)
    print(f"PHASE 2 — Live Drupal sandbox at {base_url} (gateway={gateway_id})")
    print("=" * 60)

    secret = os.environ.get("DRUPAL_WEBHOOK_SECRET")
    if not secret:
        print("  [ABORT] DRUPAL_WEBHOOK_SECRET not set — cannot sign webhooks.")
        sys.exit(2)

    webhook = f"{base_url.rstrip('/')}/payment/notify/algovoi/{gateway_id}"

    section(f"1. Webhook route reachability: {webhook}")
    try:
        with urlopen(Request(webhook, method="GET"), timeout=10) as r:  # nosec B310
            result("route exists (got status)", True, f"HTTP {r.status}")
    except HTTPError as e:
        # 401 / 404 / 405 all mean Drupal routed the request
        result("route exists (HTTPError from Drupal)",
               e.code in (401, 403, 404, 405),
               f"HTTP {e.code}")
    except URLError as e:
        result("route reachable", False, f"{e}")
        print("  [ABORT] sandbox not reachable — aborting Phase 2")
        sys.exit(1)

    section("2. POST without signature")
    code, body = _post(webhook, b'{"order_id":1,"tx_id":"X"}',
                       {"Content-Type": "application/json"})
    result("401 returned (signature missing)", code == 401, f"HTTP {code}: {body[:120]}")

    section("3. POST with bad signature")
    code, body = _post(webhook, b'{"order_id":1,"tx_id":"X"}',
                       {"Content-Type": "application/json",
                        "X-AlgoVoi-Signature": "wrong=="})
    result("401 returned (bad signature)", code == 401, f"HTTP {code}")

    section("4. Oversized body (>64KB)")
    big = b'{"x":"' + b'A' * 70000 + b'"}'
    code, body = _post(webhook, big,
                       {"Content-Type": "application/json",
                        "X-AlgoVoi-Signature": _hmac_sign(secret, big)})
    result("400 returned (body >64KB)", code == 400, f"HTTP {code}")

    section("5. Valid HMAC but missing order_id/tx_id")
    body = b'{"hello":"world"}'
    code, resp = _post(webhook, body,
                       {"Content-Type": "application/json",
                        "X-AlgoVoi-Signature": _hmac_sign(secret, body)})
    result("400 returned (missing fields)", code == 400, f"HTTP {code}")

    section("6. Valid HMAC against non-existent order")
    body = json.dumps({"order_id": 999_999_999, "tx_id": "TX_TEST_999"}).encode()
    code, resp = _post(webhook, body,
                       {"Content-Type": "application/json",
                        "X-AlgoVoi-Signature": _hmac_sign(secret, body)})
    result("404 returned (order not found)", code == 404, f"HTTP {code}")


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) == 1:
        phase_1()
    elif len(sys.argv) in (2, 3):
        phase_1()
        gateway_id = sys.argv[2] if len(sys.argv) == 3 else "algovoi_offsite"
        phase_2(sys.argv[1], gateway_id)
    else:
        print(__doc__)
        sys.exit(2)

    print(f"\n{'=' * 60}\nTotals: {PASS} pass, {FAIL} fail, {WARN} warn")
    sys.exit(0 if FAIL == 0 else 1)
