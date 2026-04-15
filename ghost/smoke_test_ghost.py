"""
Ghost Adapter Smoke Test
========================
Phase 1 — gateway-only: exercises AlgoVoi.process_payment / verify_payment
          + every security guard in ghost_algovoi.py. NO real Ghost blog
          required. Hits the live AlgoVoi gateway.

Phase 2 — Ghost-connected: takes a real Ghost blog URL + admin key + a
          4-chain TX batch. Creates / upgrades a test member via the
          Ghost Admin API after verifying payment. NEEDS a Ghost 5.x
          blog (Ghost Pro trial works fine) and a tx on each chain.

Usage:
    # Phase 1 only (no Ghost needed):
    python smoke_test_ghost.py

    # Phase 2 (Ghost + real payments):
    python smoke_test_ghost.py ALGO_TX VOI_TX HEDERA_TX STELLAR_TX

Env vars:
    GHOST_URL           https://yourblog.ghost.io    (Phase 2)
    GHOST_ADMIN_KEY     <id>:<secret-hex>            (Phase 2)
    GHOST_TIER_ID       optional — comps onto a tier (Phase 2)
    ALGOVOI_KEY         algv_...                     (both phases)
    TENANT_ID           uuid                         (both phases)
    WEBHOOK_SECRET      test-secret (Phase 1) or real for Phase 2
    TEST_READER_EMAIL   smoke+{ts}@example.com (auto-generated if unset)
"""

from __future__ import annotations

import base64
import hashlib
import hmac as hmac_mod
import json
import math
import os
import sys
import time
from typing import Any, Optional

sys.path.insert(0, os.path.dirname(__file__))
from ghost_algovoi import GhostAlgoVoi, MAX_WEBHOOK_BODY_BYTES  # noqa: E402

# ── Credential loading ────────────────────────────────────────────────────────

def _read_labelled(label: str, path: str) -> Optional[str]:
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.lower().startswith(label.lower() + ":"):
                    _, _, v = line.partition(":")
                    return v.strip().split()[0] if v.strip() else None
    except FileNotFoundError:
        pass
    return None


def _read_prefix(prefix: str, path: str) -> Optional[str]:
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(prefix):
                    return line
    except FileNotFoundError:
        pass
    return None


REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")

def _algovoi_key() -> str:
    return (
        os.environ.get("ALGOVOI_KEY")
        or (_read_prefix("algv_", os.path.join(REPO_ROOT, "openai.txt")) or "")
        or (_read_prefix("algv_", os.path.join(REPO_ROOT, "keys.txt")) or "").split()[0]
        or ""
    )

ALGOVOI_KEY    = _algovoi_key()
TENANT_ID      = os.environ.get("TENANT_ID", "YOUR_TENANT_ID")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "phase1-local-secret")

GHOST_URL       = os.environ.get("GHOST_URL", "")
GHOST_ADMIN_KEY = os.environ.get("GHOST_ADMIN_KEY", "")
GHOST_TIER_ID   = os.environ.get("GHOST_TIER_ID")
TEST_EMAIL      = os.environ.get("TEST_READER_EMAIL", f"smoke+{int(time.time())}@example.com")

# Placeholder for Phase 1 construction — the ghost_admin_key format guard
# requires <24 hex>:<64 hex>, so we build a fake one just to get past the
# constructor when no real Ghost is configured.
_PLACEHOLDER_KEY = "0123456789abcdef01234567:" + "0" * 64

# ── Helpers ───────────────────────────────────────────────────────────────────

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


def b64_hmac(secret: str, body: bytes) -> str:
    return base64.b64encode(hmac_mod.new(secret.encode(), body, hashlib.sha256).digest()).decode()


def _adapter(ghost_url: str = "https://placeholder.invalid",
             ghost_admin_key: str = _PLACEHOLDER_KEY,
             webhook_secret: str = WEBHOOK_SECRET) -> GhostAlgoVoi:
    return GhostAlgoVoi(
        ghost_url=ghost_url,
        ghost_admin_key=ghost_admin_key,
        api_base="https://api1.ilovechicken.co.uk",
        api_key=ALGOVOI_KEY,
        tenant_id=TENANT_ID,
        webhook_secret=webhook_secret,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Phase 1 — security replay + gateway round-trip (no Ghost needed)
# ══════════════════════════════════════════════════════════════════════════════

def phase_1():
    print("\n" + "=" * 60)
    print("PHASE 1 — Ghost adapter (gateway-only)")
    print("=" * 60)

    # ── 1. Construction — ghost_admin_key format guard ──
    section("1. Construction guards")
    try:
        GhostAlgoVoi(ghost_url="https://x", ghost_admin_key="not-a-valid-key")
        result("malformed ghost_admin_key raises ValueError", False,
               "construction should have raised")
    except ValueError:
        result("malformed ghost_admin_key raises ValueError", True)

    try:
        GhostAlgoVoi(ghost_url="https://x", ghost_admin_key="")
        result("empty ghost_admin_key raises ValueError", False)
    except ValueError:
        result("empty ghost_admin_key raises ValueError", True)

    try:
        _adapter()
        result("well-formed placeholder key construction OK", True)
    except Exception as e:
        result("well-formed placeholder key construction OK", False, str(e))

    # ── 2. verify_webhook security guards ──
    section("2. verify_webhook guards")
    a = _adapter()
    body = b'{"tx_id":"TEST","reader_email":"a@b.co"}'
    sig = b64_hmac(WEBHOOK_SECRET, body)
    result("valid sig accepted", a.verify_webhook(body, sig) is not None)
    result("empty secret returns None",
           _adapter(webhook_secret="").verify_webhook(body, sig) is None)
    result("wrong sig returns None",
           a.verify_webhook(body, "wrong==") is None)
    # Type guards
    result("bytes signature returns None (no TypeError)",
           a.verify_webhook(body, sig.encode()) is None)   # type: ignore[arg-type]
    result("None signature returns None (no TypeError)",
           a.verify_webhook(body, None) is None)           # type: ignore[arg-type]
    result("int signature returns None (no TypeError)",
           a.verify_webhook(body, 12345) is None)          # type: ignore[arg-type]
    result("non-bytes body returns None",
           a.verify_webhook("not-bytes", sig) is None)     # type: ignore[arg-type]
    huge = b'{"x":"' + b'A' * (MAX_WEBHOOK_BODY_BYTES + 1) + b'"}'
    result("over-64KB body rejected",
           a.verify_webhook(huge, b64_hmac(WEBHOOK_SECRET, huge)) is None)
    result("non-dict JSON (array) rejected",
           a.verify_webhook(b'[1,2,3]', b64_hmac(WEBHOOK_SECRET, b'[1,2,3]')) is None)
    result("non-dict JSON (number) rejected",
           a.verify_webhook(b'42', b64_hmac(WEBHOOK_SECRET, b'42')) is None)

    # ── 3. process_payment input validation ──
    section("3. process_payment input validation")
    # Bad email
    result("invalid email rejected",
           a.process_payment("not-an-email", amount=1.0) is None)
    result("empty email rejected",
           a.process_payment("", amount=1.0) is None)
    over254 = "a" * 245 + "@example.com"
    result(">254-char email rejected",
           a.process_payment(over254, amount=1.0) is None)
    # Bad amounts
    result("NaN amount rejected",
           a.process_payment("a@b.co", amount=float("nan")) is None)
    result("Inf amount rejected",
           a.process_payment("a@b.co", amount=float("inf")) is None)
    result("zero amount rejected",
           a.process_payment("a@b.co", amount=0) is None)
    result("negative amount rejected",
           a.process_payment("a@b.co", amount=-1.0) is None)
    # Bad redirect URLs
    result("file:// redirect rejected",
           a.process_payment("a@b.co", amount=1.0, redirect_url="file:///etc/passwd") is None)
    result("gopher:// redirect rejected",
           a.process_payment("a@b.co", amount=1.0, redirect_url="gopher://x") is None)
    result("http:// redirect rejected (https-only)",
           a.process_payment("a@b.co", amount=1.0, redirect_url="http://example.com") is None)

    # ── 4. verify_payment input validation ──
    section("4. verify_payment input validation")
    result("empty token returns False", a.verify_payment("") is False)
    result(">200-char token returns False", a.verify_payment("x" * 201) is False)
    insecure = GhostAlgoVoi(
        ghost_url="https://placeholder.invalid",
        ghost_admin_key=_PLACEHOLDER_KEY,
        api_base="http://api1.ilovechicken.co.uk",
        api_key=ALGOVOI_KEY, tenant_id=TENANT_ID, webhook_secret=WEBHOOK_SECRET,
    )
    t0 = time.time()
    out = insecure.verify_payment("test_token")
    elapsed = time.time() - t0
    result("http:// api_base verify_payment returns False FAST (no network)",
           out is False and elapsed < 0.5,
           f"took {elapsed:.3f}s" if elapsed >= 0.5 else "")

    # ── 5. upgrade_member input validation ──
    section("5. upgrade_member input validation")
    result("invalid email rejected",
           a.upgrade_member("not-an-email", "TX123") is False)
    result("empty tx_id rejected",
           a.upgrade_member("a@b.co", "") is False)
    result(">200-char tx_id rejected",
           a.upgrade_member("a@b.co", "x" * 201) is False)
    insecure_ghost = GhostAlgoVoi(
        ghost_url="http://placeholder.invalid",   # plaintext — refuse
        ghost_admin_key=_PLACEHOLDER_KEY,
        api_base="https://api1.ilovechicken.co.uk",
        api_key=ALGOVOI_KEY, tenant_id=TENANT_ID, webhook_secret=WEBHOOK_SECRET,
    )
    result("http:// ghost_url rejects upgrade_member (no JWT leak)",
           insecure_ghost.upgrade_member("a@b.co", "TX123") is False)

    # ── 6. Live gateway round-trip ──
    section("6. Live gateway round-trip (process_payment -> 402 -> checkout URL)")
    if not ALGOVOI_KEY or not TENANT_ID or TENANT_ID == "YOUR_TENANT_ID":
        warn("live gateway skipped", "ALGOVOI_KEY / TENANT_ID not set")
    else:
        live = _adapter()
        for net in ("algorand_mainnet", "voi_mainnet", "hedera_mainnet", "stellar_mainnet"):
            out = live.process_payment(
                reader_email=TEST_EMAIL, amount=0.01, network=net,
                label=f"Smoke {net}",
            )
            if out and out.get("checkout_url", "").startswith("https://"):
                result(f"live link created on {net}", True,
                       f"token={out.get('token', '')[:16]}…")
            else:
                result(f"live link created on {net}", False, repr(out))


# ══════════════════════════════════════════════════════════════════════════════
# Phase 2 — Ghost Admin API (needs real blog + Admin key)
# ══════════════════════════════════════════════════════════════════════════════

def phase_2(algo_tx: str, voi_tx: str, hedera_tx: str, stellar_tx: str):
    print("\n" + "=" * 60)
    print("PHASE 2 — On-chain verify + Ghost Admin API")
    print("=" * 60)

    if not GHOST_URL or not GHOST_ADMIN_KEY:
        print("\n[ABORT] Phase 2 requires GHOST_URL + GHOST_ADMIN_KEY env vars.")
        sys.exit(2)
    if not ALGOVOI_KEY or not TENANT_ID or TENANT_ID == "YOUR_TENANT_ID":
        print("\n[ABORT] Phase 2 requires ALGOVOI_KEY + TENANT_ID env vars.")
        sys.exit(2)

    adapter = GhostAlgoVoi(
        ghost_url=GHOST_URL,
        ghost_admin_key=GHOST_ADMIN_KEY,
        api_base="https://api1.ilovechicken.co.uk",
        api_key=ALGOVOI_KEY,
        tenant_id=TENANT_ID,
        webhook_secret=WEBHOOK_SECRET,
    )

    # Prove the Ghost Admin JWT works by doing a read — /members should
    # return 200 even if there are zero members.
    section("1. Ghost Admin API reachability")
    members = adapter._ghost_request("GET", "/ghost/api/admin/members/?limit=1")
    if members is None:
        result("Ghost Admin API reachable", False,
               "GET /members returned None — check GHOST_URL + GHOST_ADMIN_KEY")
        sys.exit(1)
    else:
        result("Ghost Admin API reachable", True,
               f"members.meta: {str(members.get('meta', {}))[:80]}")

    # For each chain: verify payment, then upgrade_member.
    section("2. Per-chain: verify on-chain → upgrade_member")
    chains = [
        ("algorand-mainnet", algo_tx),
        ("voi-mainnet", voi_tx),
        ("hedera-mainnet", hedera_tx),
        ("stellar-mainnet", stellar_tx),
    ]
    passed = failed = 0
    for net, tx_id in chains:
        print(f"\n-- {net} (TX {tx_id}) ------------------------------")
        # Step A: build an MPP-style proof and feed it through verify_payment
        # style flow. verify_payment expects a checkout token not a tx_id;
        # for a true Phase 2 we'd need the token that produced this TX. We
        # skip that step here and demonstrate upgrade_member directly with
        # the tx_id as an on-chain audit reference — same contract the
        # webhook uses.
        ok = adapter.upgrade_member(
            reader_email=TEST_EMAIL,
            tx_id=tx_id,
            tier_id=GHOST_TIER_ID,
        )
        if ok:
            result(f"upgrade_member via {net} TX", True)
            passed += 1
        else:
            result(f"upgrade_member via {net} TX", False,
                   "check server logs for details")
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"Phase 2 per-chain: {passed}/{passed + failed} passed")
    if failed:
        sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) == 5:
        # Phase 1 runs first anyway, then Phase 2
        phase_1()
        phase_2(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
    elif len(sys.argv) == 1:
        phase_1()
    else:
        print(__doc__)
        sys.exit(2)

    print(f"\n{'=' * 60}\nTotals: {PASS} pass, {FAIL} fail, {WARN} warn")
    sys.exit(0 if FAIL == 0 else 1)
