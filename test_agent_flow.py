"""
AI Agent Payment Flow Test
==========================
Spins up a local HTTP server gated by x402, MPP, and AP2 adapters.
Runs a simulated AI agent client through each complete protocol loop:

  1. Agent probes endpoint -> receives 402 with payment details
  2. Agent parses challenge / payment request
  3. Agent creates checkout URL via live AlgoVoi API (x402 flow)
  4. (On-chain payment step shown but not executed -- requires funded wallet)
  5. Agent retries with fake proof -> server rejects (expected)

Usage:
  python test_agent_flow.py <api_key> <tenant_id>
  python test_agent_flow.py  # reads keys.txt if present
"""

import base64
import json
import os
import socket
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "x402-ai-agents"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "mpp-adapter"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "ap2-adapter"))

from x402_agents_algovoi import X402AgentAlgoVoi
from mpp import MppGate
from ap2 import Ap2Gate

# ── Credentials ────────────────────────────────────────────────────────────

def load_creds():
    """Load API key and tenant ID from args or keys.txt."""
    if len(sys.argv) >= 3:
        return sys.argv[1], sys.argv[2]

    keys_path = os.path.join(os.path.dirname(__file__), "keys.txt")
    if os.path.exists(keys_path):
        creds = {}
        for line in open(keys_path):
            line = line.strip()
            if ": " in line:
                k, v = line.split(": ", 1)
                creds[k.strip()] = v.strip()
        # Labels in keys.txt are swapped — algv_ value is the api_key
        raw_a = creds.get("GATEWAY_API_KEY", "")
        raw_b = creds.get("GATEWAY_TENANT_ID", "")
        if raw_a.startswith("algv_"):
            return raw_a, raw_b
        else:
            return raw_b, raw_a
    return "", ""


API_KEY, TENANT_ID = load_creds()
API_BASE = "https://api1.ilovechicken.co.uk"

# ── Adapters ────────────────────────────────────────────────────────────────

x402_adapter = X402AgentAlgoVoi(
    api_base=API_BASE,
    api_key=API_KEY,
    tenant_id=TENANT_ID,
    default_network="algorand_mainnet",
    base_currency="USD",
)

mpp_gate = MppGate(
    api_base=API_BASE,
    api_key=API_KEY,
    tenant_id=TENANT_ID,
    resource_id="flow-test-resource",
    amount_microunits=100,   # 0.0001 USDC — tiny test amount
    networks=["algorand_mainnet", "voi_mainnet"],
    realm="AlgoVoi Flow Test",
    payout_address="PLACEHOLDER_PAYOUT_ADDRESS",
)

ap2_gate = Ap2Gate(
    merchant_id="flow-test-merchant",
    api_base=API_BASE,
    api_key=API_KEY,
    tenant_id=TENANT_ID,
    amount_usd=0.01,
    currency="USD",
    networks=["algorand_mainnet", "voi_mainnet"],
    items=[{"label": "Flow test access", "amount": "0.01"}],
)

# ── Local Test Server ────────────────────────────────────────────────────────

class AgentPaymentHandler(BaseHTTPRequestHandler):
    """Minimal HTTP server exposing /x402/, /mpp/, and /ap2/ gated endpoints."""

    def log_message(self, *_):
        pass  # Suppress default access log

    def _headers_dict(self):
        return {k: v for k, v in self.headers.items()}

    def do_GET(self):
        if self.path == "/x402/resource":
            self._handle_x402()
        elif self.path == "/mpp/resource":
            self._handle_mpp()
        else:
            self._send(200, "text/plain", b"OK - no gating on this path")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw_body) if raw_body else {}
        except json.JSONDecodeError:
            body = {}

        if self.path == "/ap2/resource":
            self._handle_ap2(body)
        else:
            self._send(200, "text/plain", b"OK")

    # ── Route handlers ──────────────────────────────────────────────────

    def _handle_x402(self):
        payment_header = self.headers.get("X-Payment", "")
        if not payment_header:
            pr = x402_adapter.build_payment_required_response(
                amount=0.01,
                currency="USD",
                network="algorand_mainnet",
                resource_path="/x402/resource",
            )
            resp = json.dumps({"error": "Payment Required", "detail": pr}).encode()
            self.send_response(402)
            self.send_header("Content-Type", "application/json")
            self.send_header(pr["header_name"], pr["header_value"])
            self.end_headers()
            self.wfile.write(resp)
            return

        ok, tx_id = x402_adapter.verify_x402_payment(payment_header)
        if not ok:
            self._send(402, "application/json", json.dumps(
                {"error": "Payment verification failed"}
            ).encode())
            return
        self._send(200, "application/json", json.dumps(
            {"data": "Protected content — payment verified", "tx_id": tx_id}
        ).encode())

    def _handle_mpp(self):
        result = mpp_gate.check(self._headers_dict())
        if result.requires_payment:
            body = json.dumps({
                "error": "Payment Required",
                "detail": result.error or "This endpoint requires payment via MPP.",
            }).encode()
            self.send_response(402)
            self.send_header("Content-Type", "application/json")
            if result.challenge:
                for k, v in result.challenge.as_402_headers().items():
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)
            return
        self._send(200, "application/json", json.dumps(
            {"data": "Protected content - MPP payment verified"}
        ).encode())

    def _handle_ap2(self, body):
        result = ap2_gate.check(self._headers_dict(), body)
        if result.requires_payment:
            resp_body, status, resp_headers = result.as_flask_response()
            self.send_response(status)
            for k, v in resp_headers.items():
                self.send_header(k, v)
            self.end_headers()
            payload = resp_body if isinstance(resp_body, bytes) else resp_body.encode()
            self.wfile.write(payload)
            return
        self._send(200, "application/json", json.dumps(
            {"data": "Protected content — AP2 mandate verified"}
        ).encode())

    def _send(self, status, ctype, body):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(body)


def find_free_port():
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


# ── Agent Client Helpers ────────────────────────────────────────────────────

def get(base, path, headers=None):
    req = urllib.request.Request(f"{base}{path}", headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def post(base, path, body=None, headers=None):
    data = json.dumps(body or {}).encode()
    h = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(f"{base}{path}", data=data, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


PASS = FAIL = 0

def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}" + (f" -- {detail}" if detail else ""))


def banner(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


# ── Flow Tests ──────────────────────────────────────────────────────────────

def flow_x402(base):
    banner("x402 Protocol Flow")

    # Step 1: Probe with no payment
    print("\n[Step 1] Agent probes endpoint (no payment)")
    status, headers, body = get(base, "/x402/resource")
    check("Server returns HTTP 402", status == 402, f"got {status}")

    req_header = headers.get("X-PAYMENT-REQUIRED", headers.get("x-payment-required", ""))
    check("X-PAYMENT-REQUIRED header present", bool(req_header))

    # Step 2: Decode the requirement
    print("\n[Step 2] Agent decodes payment requirement")
    decoded = None
    if req_header:
        decoded = x402_adapter.decode_payment_requirement(req_header)
        check("Decodes to valid dict", isinstance(decoded, dict))
        check("Version is x402/1", decoded.get("version") == "x402/1")
        check("Has amount", decoded.get("amount") is not None)
        check("Has currency", bool(decoded.get("currency")))
        check("Has network", bool(decoded.get("network")))
        check("Has resource", bool(decoded.get("resource")))
        check("Has expires_at", isinstance(decoded.get("expires_at"), int))
        print(f"\n  Payment requirement:")
        print(f"    amount:   {decoded.get('amount')} {decoded.get('currency')}")
        print(f"    network:  {decoded.get('network')}")
        print(f"    resource: {decoded.get('resource')}")
        print(f"    asset:    {decoded.get('asset')}")
        print(f"    expires:  {decoded.get('expires_at')} (unix)")

    # Step 3: Create checkout URL via live AlgoVoi API
    print("\n[Step 3] Agent creates checkout URL via AlgoVoi API")
    if API_KEY:
        result = x402_adapter.create_payment_link(
            amount=0.01,
            currency="USD",
            network="algorand_mainnet",
            label="x402 flow test - /x402/resource",
        )
        check("Live API returns checkout_url", result is not None and "checkout_url" in result,
              str(result))
        if result:
            print(f"\n  Checkout URL: {result['checkout_url']}")
            print(f"  Token:        {result.get('token', 'n/a')}")
            print(f"  Chain:        {result.get('chain', 'n/a')}")
            print(f"\n  [Agent would now open the checkout URL, pay,")
            print(f"   and use the TX ID as the X-Payment proof.]")
    else:
        print("  (skipped — no API key)")
        check("Live API checkout URL (skipped)", True)

    # Step 4: Retry with invalid proof -> should be rejected
    print("\n[Step 4] Agent retries with invalid proof (expected rejection)")
    fake_proof = base64.b64encode(json.dumps({
        "x402Version": 1,
        "scheme": "exact",
        "network": "algorand-mainnet",
        "payload": {"tx_id": "FAKETXID00000000", "payer": "AAAAAAAAAAAAAAAA"},
    }).encode()).decode()
    status2, _, body2 = get(base, "/x402/resource", {"X-Payment": fake_proof})
    check("Server rejects invalid proof with 402", status2 == 402, f"got {status2}")
    print(f"  Response: {body2.decode()[:120]}")


def flow_mpp(base):
    banner("MPP Protocol Flow")

    # Step 1: Probe with no Authorization
    print("\n[Step 1] Agent probes endpoint (no payment)")
    status, headers, body = get(base, "/mpp/resource")
    check("Server returns HTTP 402", status == 402, f"got {status}")

    www_auth = headers.get("WWW-Authenticate", headers.get("www-authenticate", ""))
    x_payment = headers.get("X-Payment-Required", headers.get("x-payment-required", ""))
    check("WWW-Authenticate: Payment header present", www_auth.startswith("Payment"),
          f"got: {www_auth[:80]}")
    check("X-Payment-Required header present", bool(x_payment))

    # Step 2: Parse the challenge
    print("\n[Step 2] Agent parses WWW-Authenticate challenge")
    check("WWW-Authenticate starts with 'Payment'", www_auth.startswith("Payment"))
    check("Contains realm=", "realm=" in www_auth)
    check("Contains challenge=", "challenge=" in www_auth)

    # Extract and decode challenge
    challenge_b64 = ""
    for part in www_auth.split(","):
        part = part.strip()
        if part.startswith("challenge="):
            challenge_b64 = part[len("challenge="):].strip().strip('"')
    if challenge_b64:
        try:
            challenge_data = json.loads(base64.b64decode(challenge_b64))
            check("Challenge decodes to dict", isinstance(challenge_data, dict))
            accepts = challenge_data.get("accepts", [])
            check("Challenge has accepts list", isinstance(accepts, list) and len(accepts) > 0)
            if accepts:
                print(f"\n  Challenge payment options:")
                for a in accepts:
                    print(f"    network: {a.get('network')}")
                    print(f"    asset:   {a.get('asset')}")
                    print(f"    amount:  {a.get('amount')} microunits")
                    print(f"    payTo:   {a.get('payTo', '(not set)')}")
                    print()
                print(f"  [Agent would now submit on-chain tx to payTo address,")
                print(f"   then retry with Authorization: Payment <base64-proof>]")
        except Exception as e:
            check("Challenge decodes OK", False, str(e))

    # Step 3: Retry with invalid credential -> rejected
    print("\n[Step 3] Agent retries with fake credential (expected rejection)")
    fake_cred = base64.b64encode(json.dumps({
        "network": "algorand-mainnet",
        "payload": {"txId": "FAKETXID00000000", "payer": "AAAAAAAAAA"},
    }).encode()).decode()
    status2, _, body2 = get(base, "/mpp/resource", {"Authorization": f"Payment {fake_cred}"})
    check("Server rejects fake tx with 402", status2 == 402, f"got {status2}")
    resp_data = json.loads(body2)
    check("Error mentions verification", "verification" in (resp_data.get("error", "") + resp_data.get("detail", "")).lower(),
          str(resp_data))


def flow_ap2(base):
    banner("AP2 Protocol Flow")

    # Step 1: Probe with no mandate
    print("\n[Step 1] Agent probes endpoint (no mandate)")
    status, headers, body = post(base, "/ap2/resource")
    check("Server returns HTTP 402", status == 402, f"got {status}")

    ap2_req_header = headers.get("X-AP2-Payment-Request", headers.get("x-ap2-payment-request", ""))
    check("X-AP2-Payment-Request header present", bool(ap2_req_header))

    # Step 2: Decode the payment request
    print("\n[Step 2] Agent decodes payment request")
    if ap2_req_header:
        try:
            pr_data = json.loads(base64.b64decode(ap2_req_header))
            check("Decodes to dict", isinstance(pr_data, dict))
            check("protocol is ap2", pr_data.get("protocol") == "ap2")
            check("Has merchant_id", bool(pr_data.get("merchant_id")))
            check("Has amount.value", bool(pr_data.get("amount", {}).get("value")))
            check("signing is ed25519", pr_data.get("signing") == "ed25519")
            check("Has networks list", isinstance(pr_data.get("networks"), list))
            check("Has expires_at", isinstance(pr_data.get("expires_at"), int))

            print(f"\n  Payment request:")
            print(f"    merchant:  {pr_data.get('merchant_id')}")
            print(f"    amount:    {pr_data['amount']['value']} {pr_data['amount']['currency']}")
            print(f"    signing:   {pr_data.get('signing')}")
            print(f"    networks:  {', '.join(pr_data.get('networks', []))}")
            print(f"    expires:   {pr_data.get('expires_at')} (unix)")
            print(f"\n  [Agent would now:")
            print(f"   1. Select a network from the list")
            print(f"   2. Sign a mandate with its ed25519 private key:")
            print(f"      merchant_id, payer_address, amount, network -> signature")
            print(f"   3. POST X-AP2-Mandate: base64(JSON mandate) to retry]")
        except Exception as e:
            check("Decodes OK", False, str(e))

    # Step 3: Retry with mandate — wrong merchant (rejected)
    print("\n[Step 3] Retry with wrong merchant_id (expected rejection)")
    bad_mandate = base64.b64encode(json.dumps({
        "merchant_id": "wrong-merchant",
        "payer_address": "TESTADDR",
        "signature": "fakesig",
        "network": "algorand-mainnet",
        "amount": {"value": "0.01", "currency": "USD"},
    }).encode()).decode()
    status2, _, body2 = post(base, "/ap2/resource",
                              headers={"X-AP2-Mandate": bad_mandate})
    check("Wrong merchant rejected with 402", status2 == 402, f"got {status2}")
    resp_data = json.loads(body2)
    check("Error mentions merchant",
          "merchant" in (resp_data.get("error", "") + resp_data.get("detail", "")).lower(),
          str(resp_data))

    # Step 4: Retry with correct merchant but fake sig -> verification fails
    print("\n[Step 4] Correct merchant + fake sig (expected verification failure)")
    fake_mandate = base64.b64encode(json.dumps({
        "merchant_id": "flow-test-merchant",
        "payer_address": "TESTADDR123456",
        "signature": "ZmFrZXNpZw==",   # base64("fakesig")
        "network": "algorand-mainnet",
        "amount": {"value": "0.01", "currency": "USD"},
    }).encode()).decode()
    status3, _, body3 = post(base, "/ap2/resource",
                              headers={"X-AP2-Mandate": fake_mandate})
    check("Fake mandate rejected with 402", status3 == 402, f"got {status3}")
    resp_data3 = json.loads(body3)
    check("Error mentions verification",
          "verification" in (resp_data3.get("error", "") + resp_data3.get("detail", "")).lower(),
          str(resp_data3))


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    global PASS, FAIL

    if not API_KEY:
        print("WARNING: No API key found. Skipping live API calls.")

    port = find_free_port()
    base = f"http://127.0.0.1:{port}"

    server = HTTPServer(("127.0.0.1", port), AgentPaymentHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.1)

    print(f"Local test server: {base}")
    print(f"API base:          {API_BASE}")
    print(f"API key:           {API_KEY[:12]}..." if API_KEY else "API key: (none)")
    print(f"Tenant ID:         {TENANT_ID[:8]}..." if TENANT_ID else "Tenant ID: (none)")

    try:
        flow_x402(base)
        flow_mpp(base)
        flow_ap2(base)
    finally:
        server.shutdown()

    print(f"\n{'=' * 60}")
    print(f"  Flow test results: {PASS} passed, {FAIL} failed")
    print(f"{'=' * 60}\n")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
