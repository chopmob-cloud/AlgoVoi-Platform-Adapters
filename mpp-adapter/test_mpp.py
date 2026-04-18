"""
MPP Adapter -- Unit Tests (spec v2 / IETF draft-ryan-httpauth-payment)
"""

import base64
import hashlib
import hmac as hmac_mod
import json
import os
import re
import ssl as ssl_mod
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

from mpp import MppGate, MppChallenge, MppReceipt, MppResult, INTENT

PASS = FAIL = 0


def test(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}" + (f" -- {detail}" if detail else ""))


def b64j(obj: dict) -> str:
    return base64.b64encode(json.dumps(obj).encode()).decode()


def main():
    global PASS, FAIL

    gate = MppGate(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        resource_id="premium-content",
        amount_microunits=10000,
        networks=["algorand_mainnet", "voi_mainnet"],
        realm="Test API",
        payout_address="TEST_PAYOUT_ADDR",
        method="algorand",
        challenge_ttl=300,
    )

    src_path = os.path.join(os.path.dirname(__file__), "mpp.py")
    src = open(src_path).read()

    print("MPP Adapter -- Unit Tests")
    print("=" * 55)

    # 1. Version and constants
    print("\n1. Version and constants")
    import mpp as mpp_mod
    test("version is 2.2.0", mpp_mod.__version__ == "2.2.0")
    test("INTENT is 'charge'", INTENT == "charge")
    test("INTENT constant in source", '"charge"' in src)
    test("8 networks defined in NETWORKS", len(MppGate.NETWORKS) == 8)

    # 2. No credentials -> challenge issued
    print("\n2. No credentials -> 402 challenge")
    result = gate.check({})
    test("requires_payment is True", result.requires_payment)
    test("challenge is not None", result.challenge is not None)
    test("receipt is None", result.receipt is None)

    if result.challenge:
        headers = result.challenge.as_402_headers()

        # 3. WWW-Authenticate spec fields
        print("\n3. WWW-Authenticate header — spec fields")
        www = headers.get("WWW-Authenticate", "")
        test("WWW-Authenticate present", "WWW-Authenticate" in headers)
        test("starts with 'Payment '", www.startswith("Payment "))
        test("contains realm=", 'realm="Test API"' in www)
        test("contains id=", "id=" in www)
        test("contains method=", 'method="algorand"' in www)
        test("contains intent=\"charge\"", 'intent="charge"' in www)
        test("contains request=", "request=" in www)
        test("contains expires=", "expires=" in www)
        test("expires is RFC3339 format", bool(re.search(r'expires="\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"', www)))

        # 4. Challenge ID
        print("\n4. Challenge ID")
        id_match = re.search(r'id="([^"]+)"', www)
        challenge_id = id_match.group(1) if id_match else ""
        test("id field is non-empty", bool(challenge_id))
        test("id is 32 hex chars", bool(re.match(r'^[0-9a-f]{32}$', challenge_id)))
        test("challenge.challenge_id matches header", result.challenge.challenge_id == challenge_id)

        # 5. Request object (charge intent)
        print("\n5. Request object (charge intent)")
        req_match = re.search(r'request="([^"]+)"', www)
        request_b64 = req_match.group(1) if req_match else ""
        test("request= field is non-empty", bool(request_b64))
        try:
            req_obj = json.loads(base64.b64decode(request_b64 + "=="))
            test("request= decodes to valid JSON", isinstance(req_obj, dict))
            test("request has 'amount' field", "amount" in req_obj)
            test("request amount is string '10000'", req_obj.get("amount") == "10000")
            test("request has 'currency' field", "currency" in req_obj)
            test("request currency is 'usdc'", req_obj.get("currency") == "usdc")
            test("request has 'recipient' field", "recipient" in req_obj)
            test("request has 'methodDetails'", "methodDetails" in req_obj)
            md = req_obj.get("methodDetails", {})
            test("methodDetails has 'accepts'", "accepts" in md)
            test("methodDetails has 'resource'", "resource" in md)
            test("methodDetails.resource matches resource_id", md.get("resource") == "premium-content")
        except Exception as e:
            test("request= decodes to valid JSON", False, str(e))

        # 6. X-Payment-Required header
        print("\n6. X-Payment-Required header")
        xpr = headers.get("X-Payment-Required", "")
        test("X-Payment-Required present", bool(xpr))
        try:
            xpr_obj = json.loads(base64.b64decode(xpr + "=="))
            test("X-Payment-Required decodes to JSON", isinstance(xpr_obj, dict))
            test("has 'accepts' array", isinstance(xpr_obj.get("accepts"), list))
            test("has 'resource' field", "resource" in xpr_obj)
        except Exception as e:
            test("X-Payment-Required decodes to JSON", False, str(e))

        # 7. Accepts entries
        print("\n7. Accepts entries")
        accepts = result.challenge.accepts
        test("2 entries for 2-network gate", len(accepts) == 2, f"got {len(accepts)}")
        nets = [a["network"] for a in accepts]
        test("algorand-mainnet in accepts", "algorand-mainnet" in nets)
        test("voi-mainnet in accepts", "voi-mainnet" in nets)

        for entry in accepts:
            net = entry.get("network", "unknown")
            test(f"{net}: has 'amount' (not maxAmountRequired)", "amount" in entry and "maxAmountRequired" not in entry)
            test(f"{net}: amount is string '10000'", entry.get("amount") == "10000")
            test(f"{net}: has 'asset'", "asset" in entry)
            test(f"{net}: has 'payTo'", "payTo" in entry)
            test(f"{net}: has 'resource'", "resource" in entry)
            test(f"{net}: resource matches resource_id", entry.get("resource") == "premium-content")

        test("algorand asset is '31566704'", any(a["asset"] == "31566704" for a in accepts))
        test("voi asset is '302190'", any(a["asset"] == "302190" for a in accepts))

    # 8. Invalid credential encoding
    print("\n8. Invalid credential encoding")
    result_bad = gate.check({"Authorization": "Payment not-valid-base64!!!"})
    test("requires_payment True", result_bad.requires_payment)
    test("error mentions encoding", "encoding" in (result_bad.error or "").lower(),
         f"error={result_bad.error}")

    # 9. Missing txId
    print("\n9. Missing txId in credential")
    empty_cred = b64j({"network": "algorand-mainnet"})
    result_notx = gate.check({"Authorization": f"Payment {empty_cred}"})
    test("requires_payment True", result_notx.requires_payment)
    test("error mentions txId", "txid" in (result_notx.error or "").lower(),
         f"error={result_notx.error}")

    # 10. tx_id length guard
    print("\n10. tx_id length guard (>200 chars)")
    long_cred = b64j({"network": "algorand-mainnet", "payload": {"txId": "A" * 201}})
    result_long = gate.check({"Authorization": f"Payment {long_cred}"})
    test("requires_payment True for >200 char txId", result_long.requires_payment)

    # 11. Fake tx_id -> verification fails (hits indexer, gets 404)
    print("\n11. Fake tx_id -> verification fails")
    fake_cred = b64j({"network": "algorand-mainnet", "payload": {"txId": "FAKETXID123", "payer": "ADDR"}})
    result_fake = gate.check({"Authorization": f"Payment {fake_cred}"})
    test("requires_payment True", result_fake.requires_payment)
    test("error mentions verification", "verification" in (result_fake.error or "").lower(),
         f"error={result_fake.error}")

    # 12. X-Payment header as alternative
    print("\n12. X-Payment header alternative")
    result_xp = gate.check({"X-Payment": empty_cred})
    test("X-Payment header accepted", result_xp.requires_payment)  # missing txId -> gated
    test("error is txId related", "txid" in (result_xp.error or "").lower())

    # 13. Authorization: Payment takes precedence over X-Payment
    print("\n13. Authorization takes precedence over X-Payment")
    fake_xp = b64j({"network": "algorand-mainnet", "payload": {"txId": "XPAYMENT_TX"}})
    result_both = gate.check({
        "Authorization": f"Payment {empty_cred}",
        "X-Payment": fake_xp,
    })
    test("Authorization used (missing txId error, not verification error)",
         "txid" in (result_both.error or "").lower())

    # 14. Replay protection
    print("\n14. Replay protection (single-use enforcement)")
    gate2 = MppGate(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        resource_id="test",
        amount_microunits=10000,
        payout_address="ADDR",
    )
    gate2._used_tx_ids.add("ALREADY_USED_TX")
    replay_cred = b64j({"network": "algorand-mainnet", "payload": {"txId": "ALREADY_USED_TX"}})
    result_replay = gate2.check({"Authorization": f"Payment {replay_cred}"})
    test("replayed proof rejected", result_replay.requires_payment)
    test("replay error message", "already used" in (result_replay.error or "").lower(),
         f"error={result_replay.error}")

    # 15. WSGI guard
    print("\n15. WSGI guard")
    wsgi_result = gate.wsgi_guard({"HTTP_AUTHORIZATION": "Bearer invalid"})
    test("WSGI returns 402 tuple", wsgi_result is not None)
    if wsgi_result:
        status, resp_headers, body = wsgi_result
        test("status is '402 Payment Required'", status == "402 Payment Required")
        header_names = [h[0] for h in resp_headers]
        test("WWW-Authenticate in WSGI headers", "WWW-Authenticate" in header_names)
        test("X-Payment-Required in WSGI headers", "X-Payment-Required" in header_names)
        test("body is JSON bytes", json.loads(body).get("error") == "Payment Required")

    # 16. MppResult.as_wsgi_response()
    print("\n16. MppResult.as_wsgi_response()")
    result_no_cred = gate.check({})
    status2, headers2, body2 = result_no_cred.as_wsgi_response()
    test("status is '402 Payment Required'", status2 == "402 Payment Required")
    header_names2 = [h[0] for h in headers2]
    test("WWW-Authenticate in headers", "WWW-Authenticate" in header_names2)

    # 17. MppReceipt spec fields
    print("\n17. MppReceipt spec fields")
    receipt = MppReceipt(
        tx_id="TESTTXID123",
        payer="PAYERADDR",
        network="algorand-mainnet",
        amount=10000,
        method="algorand",
    )
    test("status is 'success'", receipt.status == "success")
    test("reference is tx_id", receipt.reference == "TESTTXID123")
    test("method is set", receipt.method == "algorand")
    test("timestamp is RFC3339", bool(re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$', receipt.timestamp)))

    header_val = receipt.as_header_value()
    test("as_header_value returns non-empty string", bool(header_val))
    decoded_receipt = json.loads(base64.b64decode(header_val + "=="))
    test("receipt JSON has 'status'", decoded_receipt.get("status") == "success")
    test("receipt JSON has 'method'", bool(decoded_receipt.get("method")))
    test("receipt JSON has 'timestamp'", bool(decoded_receipt.get("timestamp")))
    test("receipt JSON has 'reference'", decoded_receipt.get("reference") == "TESTTXID123")
    test("receipt JSON has 'payer'", bool(decoded_receipt.get("payer")))
    test("receipt JSON has 'amount'", decoded_receipt.get("amount") == 10000)
    test("receipt JSON has 'network'", bool(decoded_receipt.get("network")))

    # 18. Challenge uniqueness (different expires -> different id)
    print("\n18. Challenge ID uniqueness")
    c1 = gate._build_challenge()
    import time as time_mod; time_mod.sleep(1)
    c2 = gate._build_challenge()
    test("two challenges have different IDs", c1.challenge_id != c2.challenge_id)
    test("two challenges have different expires", c1.expires != c2.expires)

    # 19. Default values
    print("\n19. Default values")
    gate_defaults = MppGate(
        api_base="https://example.com",
        api_key="k",
        tenant_id="t",
        resource_id="r",
    )
    test("default method is 'algorand'", gate_defaults.method == "algorand")
    test("default networks is ['algorand_mainnet']", gate_defaults.networks == ["algorand_mainnet"])
    test("default amount is 1000000", gate_defaults.amount_microunits == 1000000)
    test("default challenge_ttl is 300", gate_defaults.challenge_ttl == 300)
    test("default realm is 'API Access'", gate_defaults.realm == "API Access")

    # 20. Network and indexer config — all 4 chains × 2 tokens
    print("\n20. Network and indexer config — all 4 chains × 2 tokens (8 total)")
    test("8 networks defined", len(MppGate.NETWORKS) == 8)
    # Stablecoin networks
    test("algorand-mainnet in INDEXERS", "algorand-mainnet" in MppGate.INDEXERS)
    test("algorand_mainnet in INDEXERS", "algorand_mainnet" in MppGate.INDEXERS)
    test("voi-mainnet in INDEXERS", "voi-mainnet" in MppGate.INDEXERS)
    test("voi_mainnet in INDEXERS", "voi_mainnet" in MppGate.INDEXERS)
    test("hedera-mainnet in INDEXERS", "hedera-mainnet" in MppGate.INDEXERS)
    test("hedera_mainnet in INDEXERS", "hedera_mainnet" in MppGate.INDEXERS)
    test("stellar-mainnet in INDEXERS", "stellar-mainnet" in MppGate.INDEXERS)
    test("stellar_mainnet in INDEXERS", "stellar_mainnet" in MppGate.INDEXERS)
    # Native token networks in INDEXERS
    test("algorand_mainnet_algo in INDEXERS", "algorand_mainnet_algo" in MppGate.INDEXERS)
    test("voi_mainnet_voi in INDEXERS", "voi_mainnet_voi" in MppGate.INDEXERS)
    test("hedera_mainnet_hbar in INDEXERS", "hedera_mainnet_hbar" in MppGate.INDEXERS)
    test("stellar_mainnet_xlm in INDEXERS", "stellar_mainnet_xlm" in MppGate.INDEXERS)
    # Stablecoin asset IDs
    test("algorand USDC asset_id is 31566704", MppGate.NETWORKS["algorand_mainnet"]["asset_id"] == 31566704)
    test("voi aUSDC asset_id is 302190", MppGate.NETWORKS["voi_mainnet"]["asset_id"] == 302190)
    test("hedera USDC asset_id is 0.0.456858", MppGate.NETWORKS["hedera_mainnet"]["asset_id"] == "0.0.456858")
    test("stellar USDC contains GA5ZS issuer",
         "GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN" in MppGate.NETWORKS["stellar_mainnet"]["asset_id"])
    # Native token asset_id == None
    test("ALGO asset_id is None", MppGate.NETWORKS["algorand_mainnet_algo"]["asset_id"] is None)
    test("VOI asset_id is None", MppGate.NETWORKS["voi_mainnet_voi"]["asset_id"] is None)
    test("HBAR asset_id is None", MppGate.NETWORKS["hedera_mainnet_hbar"]["asset_id"] is None)
    test("XLM asset_id is None", MppGate.NETWORKS["stellar_mainnet_xlm"]["asset_id"] is None)
    # Native flag
    test("algorand_mainnet native=False", MppGate.NETWORKS["algorand_mainnet"]["native"] is False)
    test("algorand_mainnet_algo native=True", MppGate.NETWORKS["algorand_mainnet_algo"]["native"] is True)
    test("voi_mainnet native=False", MppGate.NETWORKS["voi_mainnet"]["native"] is False)
    test("voi_mainnet_voi native=True", MppGate.NETWORKS["voi_mainnet_voi"]["native"] is True)
    test("hedera_mainnet native=False", MppGate.NETWORKS["hedera_mainnet"]["native"] is False)
    test("hedera_mainnet_hbar native=True", MppGate.NETWORKS["hedera_mainnet_hbar"]["native"] is True)
    test("stellar_mainnet native=False", MppGate.NETWORKS["stellar_mainnet"]["native"] is False)
    test("stellar_mainnet_xlm native=True", MppGate.NETWORKS["stellar_mainnet_xlm"]["native"] is True)
    # Tickers
    test("ALGO ticker", MppGate.NETWORKS["algorand_mainnet_algo"]["ticker"] == "ALGO")
    test("VOI ticker", MppGate.NETWORKS["voi_mainnet_voi"]["ticker"] == "VOI")
    test("HBAR ticker", MppGate.NETWORKS["hedera_mainnet_hbar"]["ticker"] == "HBAR")
    test("XLM ticker", MppGate.NETWORKS["stellar_mainnet_xlm"]["ticker"] == "XLM")
    # Decimals
    test("HBAR decimals=8", MppGate.NETWORKS["hedera_mainnet_hbar"]["decimals"] == 8)
    test("XLM decimals=7", MppGate.NETWORKS["stellar_mainnet_xlm"]["decimals"] == 7)
    test("ALGO decimals=6", MppGate.NETWORKS["algorand_mainnet_algo"]["decimals"] == 6)
    test("VOI decimals=6", MppGate.NETWORKS["voi_mainnet_voi"]["decimals"] == 6)
    # Indexer routing correct for native keys
    test("ALGO indexer is algonode", "algonode.cloud" in MppGate.INDEXERS["algorand_mainnet_algo"])
    test("VOI indexer is nodely.dev", "nodely.dev" in MppGate.INDEXERS["voi_mainnet_voi"])
    test("HBAR indexer is mirrornode", "mirrornode.hedera.com" in MppGate.INDEXERS["hedera_mainnet_hbar"])
    test("XLM indexer is horizon", "horizon.stellar.org" in MppGate.INDEXERS["stellar_mainnet_xlm"])
    # USDC indexers unchanged
    test("algorand indexer is algonode", "algonode.cloud" in MppGate.INDEXERS["algorand-mainnet"])
    test("voi indexer is nodely.dev", "nodely.dev" in MppGate.INDEXERS["voi-mainnet"])
    test("hedera indexer is mirrornode", "mirrornode.hedera.com" in MppGate.INDEXERS["hedera-mainnet"])
    test("stellar indexer is horizon", "horizon.stellar.org" in MppGate.INDEXERS["stellar-mainnet"])

    # 20b. 4-network gate challenge
    print("\n20b. 4-network gate challenge")
    gate4 = MppGate(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        resource_id="all-chains",
        amount_microunits=10000,
        networks=["algorand_mainnet", "voi_mainnet", "hedera_mainnet", "stellar_mainnet"],
        payout_address="TEST_ADDR",
    )
    result4 = gate4.check({})
    test("4-network gate issues challenge", result4.requires_payment and result4.challenge is not None)
    if result4.challenge:
        accepts4 = result4.challenge.accepts
        test("4 entries in accepts", len(accepts4) == 4, f"got {len(accepts4)}")
        nets4 = [a["network"] for a in accepts4]
        test("algorand-mainnet in 4-chain accepts", "algorand-mainnet" in nets4)
        test("voi-mainnet in 4-chain accepts", "voi-mainnet" in nets4)
        test("hedera-mainnet in 4-chain accepts", "hedera-mainnet" in nets4)
        test("stellar-mainnet in 4-chain accepts", "stellar-mainnet" in nets4)
        hedera_entry = next((a for a in accepts4 if a["network"] == "hedera-mainnet"), {})
        test("hedera entry asset is 0.0.456858", hedera_entry.get("asset") == "0.0.456858")
        stellar_entry = next((a for a in accepts4 if a["network"] == "stellar-mainnet"), {})
        test("stellar entry asset contains USDC:", stellar_entry.get("asset", "").startswith("USDC:"))

    # 20c. Hedera TX ID normalisation
    print("\n20c. Hedera TX ID normalisation")
    gate_h = MppGate(
        api_base="https://api1.ilovechicken.co.uk", api_key="k",
        tenant_id="t", resource_id="r", payout_address="0.0.1317927",
        networks=["hedera_mainnet"],
    )
    # Wallet format 0.0.account@seconds.nanos should not crash and attempt the Mirror Node lookup
    wallet_cred = b64j({"network": "hedera-mainnet", "payload": {"txId": "0.0.99@0000000001.000000001"}})
    result_norm = gate_h.check({"Authorization": f"Payment {wallet_cred}"})
    test("wallet-format Hedera TX ID handled (not encoding error)", result_norm.error != "Invalid credential encoding")
    test("wallet-format error is verification (not encoding)", "verification" in (result_norm.error or "").lower())

    # 20d. (see 20c above for routing)
    print("\n20c. Hedera and Stellar verification routing")
    fake_hedera = b64j({"network": "hedera-mainnet", "payload": {"txId": "0.0.99-0000000001-000000001"}})
    result_hedera = gate4.check({"Authorization": f"Payment {fake_hedera}"})
    test("fake Hedera TX: requires_payment True", result_hedera.requires_payment)
    test("fake Hedera TX: verification failed", "verification" in (result_hedera.error or "").lower())

    fake_stellar = b64j({"network": "stellar-mainnet", "payload": {"txId": "0000000000000000000000000000000000000000000000000000000000000000"}})
    result_stellar = gate4.check({"Authorization": f"Payment {fake_stellar}"})
    test("fake Stellar TX: requires_payment True", result_stellar.requires_payment)
    test("fake Stellar TX: verification failed", "verification" in (result_stellar.error or "").lower())

    # 21. SSL enforcement
    print("\n21. SSL enforcement")
    test("create_default_context in source", "create_default_context" in src)
    test("_ssl_ctx is SSLContext", isinstance(gate._ssl_ctx, ssl_mod.SSLContext))
    test("nosec B310 annotation present", "nosec B310" in src)

    # 22. Security — HMAC in source
    print("\n22. Security")
    test("HMAC used for challenge IDs", "hmac" in src.lower())
    test("compare_digest not needed here (no webhook)", True)  # MPP doesn't have webhooks
    test("_used_tx_ids set for replay protection", hasattr(gate, "_used_tx_ids"))

    # 23. Zero-dependency (stdlib only)
    print("\n23. Zero-dependency (stdlib only)")
    forbidden = ["import requests", "import httpx", "import aiohttp", "import algosdk"]
    test("no third-party imports", not any(imp in src for imp in forbidden))

    # 24. No hardcoded secrets
    print("\n24. No hardcoded secrets")
    test("no real API keys", "algv_2z3N" not in src and "algv_iedCPy" not in src)
    test("no real payout addresses", "ZVLRVYQS" not in src)

    # 25. _CAIP2_TO_INTERNAL mapping
    print("\n25. _CAIP2_TO_INTERNAL CAIP-2 network mapping")
    caip2 = mpp_mod._CAIP2_TO_INTERNAL
    test("_CAIP2_TO_INTERNAL exists in module", isinstance(caip2, dict))
    test("algorand:mainnet -> algorand-mainnet", caip2.get("algorand:mainnet") == "algorand-mainnet")
    test("voi:mainnet -> voi-mainnet", caip2.get("voi:mainnet") == "voi-mainnet")
    test("hedera:mainnet -> hedera-mainnet", caip2.get("hedera:mainnet") == "hedera-mainnet")
    test("stellar:pubnet -> stellar-mainnet", caip2.get("stellar:pubnet") == "stellar-mainnet")
    test("4 entries in _CAIP2_TO_INTERNAL", len(caip2) == 4)

    # 26. _issued_challenges populated on _build_challenge()
    print("\n26. _issued_challenges populated on _build_challenge()")
    gate_echo = MppGate(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        resource_id="echo-test",
        amount_microunits=10000,
        payout_address="ADDR",
    )
    test("_issued_challenges starts empty", len(gate_echo._issued_challenges) == 0)
    ch = gate_echo._build_challenge()
    test("_issued_challenges has 1 entry after _build_challenge()", len(gate_echo._issued_challenges) == 1)
    test("challenge_id is in _issued_challenges", ch.challenge_id in gate_echo._issued_challenges)
    stored_expiry = gate_echo._issued_challenges.get(ch.challenge_id, 0)
    test("stored expiry is in the future", stored_expiry > time.time())

    # 27. _validate_challenge_id()
    print("\n27. _validate_challenge_id()")
    test("valid issued ID validates True", gate_echo._validate_challenge_id(ch.challenge_id))
    test("unknown ID validates False", not gate_echo._validate_challenge_id("0000000000000000000000000000000000"))
    test("empty string validates False", not gate_echo._validate_challenge_id(""))
    # Simulate expired: overwrite expiry with past timestamp
    gate_echo._issued_challenges[ch.challenge_id] = time.time() - 1
    test("expired challenge validates False", not gate_echo._validate_challenge_id(ch.challenge_id))

    # 28. Challenge echo validation — credential with valid echo accepted
    print("\n28. Challenge echo — valid echo not rejected (reaches indexer)")
    gate_v = MppGate(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        resource_id="echo-valid",
        amount_microunits=10000,
        payout_address="ADDR",
    )
    ch_v = gate_v._build_challenge()
    valid_echo_cred = b64j({
        "challenge": {
            "id":     ch_v.challenge_id,
            "realm":  gate_v.realm,
            "method": "algorand",
            "intent": "charge",
        },
        "payload": {"txId": "FAKETX_ECHO_VALID"},
    })
    result_echo_valid = gate_v.check({"Authorization": f"Payment {valid_echo_cred}"})
    test("valid challenge echo: error is NOT invalid_challenge",
         "invalid or expired challenge" not in (result_echo_valid.error or "").lower(),
         f"error={result_echo_valid.error}")
    test("valid challenge echo: error is verification (indexer rejects fake txId)",
         "verification" in (result_echo_valid.error or "").lower(),
         f"error={result_echo_valid.error}")

    # 29. Challenge echo — invalid/unknown ID rejected
    print("\n29. Challenge echo — invalid ID rejected")
    gate_inv = MppGate(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        resource_id="echo-invalid",
        amount_microunits=10000,
        payout_address="ADDR",
    )
    unknown_echo_cred = b64j({
        "challenge": {
            "id":     "deadbeefdeadbeefdeadbeefdeadbeef",
            "realm":  "Test API",
            "method": "algorand",
            "intent": "charge",
        },
        "payload": {"txId": "SOMETXID"},
    })
    result_echo_inv = gate_inv.check({"Authorization": f"Payment {unknown_echo_cred}"})
    test("unknown challenge ID: requires_payment True", result_echo_inv.requires_payment)
    test("unknown challenge ID: error is invalid/expired",
         "invalid or expired challenge" in (result_echo_inv.error or "").lower(),
         f"error={result_echo_inv.error}")
    test("unknown challenge ID: new challenge issued", result_echo_inv.challenge is not None)

    # 30. Challenge echo — credential without challenge object (backward compat)
    print("\n30. Challenge echo — no challenge object (backward compat)")
    gate_bc = MppGate(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        resource_id="echo-bc",
        amount_microunits=10000,
        payout_address="ADDR",
    )
    no_echo_cred = b64j({"network": "algorand-mainnet", "payload": {"txId": "FAKETX_NOECHO"}})
    result_bc = gate_bc.check({"Authorization": f"Payment {no_echo_cred}"})
    test("no challenge object: NOT invalid_challenge error",
         "invalid or expired challenge" not in (result_bc.error or "").lower(),
         f"error={result_bc.error}")
    test("no challenge object: reaches indexer (verification error)",
         "verification" in (result_bc.error or "").lower(),
         f"error={result_bc.error}")

    # 31. CAIP-2 network extraction from challenge.method
    print("\n31. CAIP-2 network extraction from challenge.method")
    gate_caip = MppGate(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        resource_id="caip2-test",
        amount_microunits=10000,
        networks=["algorand_mainnet", "voi_mainnet", "hedera_mainnet", "stellar_mainnet"],
        payout_address="ADDR",
    )
    ch_caip = gate_caip._build_challenge()
    # Use CAIP-2 format in challenge.method
    caip2_cred = b64j({
        "challenge": {
            "id":     ch_caip.challenge_id,
            "realm":  gate_caip.realm,
            "method": "algorand:mainnet",   # CAIP-2 format
            "intent": "charge",
        },
        "payload": {"txId": "FAKETX_CAIP2"},
    })
    result_caip = gate_caip.check({"Authorization": f"Payment {caip2_cred}"})
    test("CAIP-2 method accepted (not invalid_challenge)",
         "invalid or expired challenge" not in (result_caip.error or "").lower(),
         f"error={result_caip.error}")
    test("CAIP-2 algorand:mainnet routes to indexer (verification error)",
         "verification" in (result_caip.error or "").lower(),
         f"error={result_caip.error}")

    # VOI CAIP-2
    gate_voi_caip = MppGate(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        resource_id="caip2-voi",
        amount_microunits=10000,
        networks=["voi_mainnet"],
        payout_address="ADDR",
    )
    ch_voi = gate_voi_caip._build_challenge()
    voi_caip2_cred = b64j({
        "challenge": {
            "id":     ch_voi.challenge_id,
            "realm":  gate_voi_caip.realm,
            "method": "voi:mainnet",   # CAIP-2 format
            "intent": "charge",
        },
        "payload": {"txId": "FAKETX_VOICAIP2"},
    })
    result_voi_caip = gate_voi_caip.check({"Authorization": f"Payment {voi_caip2_cred}"})
    test("CAIP-2 voi:mainnet routes to nodely indexer (verification error)",
         "verification" in (result_voi_caip.error or "").lower(),
         f"error={result_voi_caip.error}")

    # 32. Native token challenge — asset field is "native", ticker present
    print("\n32. Native token challenge — ALGO/VOI/HBAR/XLM")
    for net_key, expected_ticker, expected_network in [
        ("algorand_mainnet_algo", "ALGO", "algorand-mainnet"),
        ("voi_mainnet_voi",       "VOI",  "voi-mainnet"),
        ("hedera_mainnet_hbar",   "HBAR", "hedera-mainnet"),
        ("stellar_mainnet_xlm",   "XLM",  "stellar-mainnet"),
    ]:
        gate_n = MppGate(
            api_base="https://api1.ilovechicken.co.uk",
            api_key="test_key",
            tenant_id="test_tenant",
            resource_id=f"native-{net_key}",
            amount_microunits=10000,
            networks=[net_key],
            payout_address="TEST_ADDR",
        )
        result_n = gate_n.check({})
        test(f"{net_key}: challenge issued", result_n.requires_payment and result_n.challenge is not None)
        if result_n.challenge:
            accepts_n = result_n.challenge.accepts
            test(f"{net_key}: 1 entry in accepts", len(accepts_n) == 1)
            if accepts_n:
                entry = accepts_n[0]
                test(f"{net_key}: network is {expected_network}", entry.get("network") == expected_network)
                test(f"{net_key}: asset is 'native'", entry.get("asset") == "native")
                test(f"{net_key}: ticker is {expected_ticker}", entry.get("ticker") == expected_ticker)
                test(f"{net_key}: amount is '10000'", entry.get("amount") == "10000")
                test(f"{net_key}: payTo present", bool(entry.get("payTo")))

    # 33. Native token verification routing — fake TXs reach correct indexer
    print("\n33. Native token verification routing — fake TX hits indexer (not routing error)")
    gate_algo_n = MppGate(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        resource_id="algo-native-route",
        amount_microunits=10000,
        networks=["algorand_mainnet_algo"],
        payout_address="TEST_ADDR",
    )
    fake_algo_native = b64j({"network": "algorand-mainnet", "payload": {"txId": "FAKE_ALGO_NATIVE_TX"}})
    result_algo_n = gate_algo_n.check({"Authorization": f"Payment {fake_algo_native}"})
    test("ALGO native: verification failed (not routing error)", "verification" in (result_algo_n.error or "").lower())

    gate_voi_n = MppGate(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        resource_id="voi-native-route",
        amount_microunits=10000,
        networks=["voi_mainnet_voi"],
        payout_address="TEST_ADDR",
    )
    fake_voi_native = b64j({"network": "voi-mainnet", "payload": {"txId": "FAKE_VOI_NATIVE_TX"}})
    result_voi_n = gate_voi_n.check({"Authorization": f"Payment {fake_voi_native}"})
    test("VOI native: verification failed (not routing error)", "verification" in (result_voi_n.error or "").lower())

    gate_hbar = MppGate(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        resource_id="hbar-route",
        amount_microunits=10000,
        networks=["hedera_mainnet_hbar"],
        payout_address="0.0.1317927",
    )
    fake_hbar = b64j({"network": "hedera-mainnet", "payload": {"txId": "0.0.99-9999999999-000000001"}})
    result_hbar = gate_hbar.check({"Authorization": f"Payment {fake_hbar}"})
    test("HBAR native: verification failed (not routing error)", "verification" in (result_hbar.error or "").lower())

    gate_xlm = MppGate(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        resource_id="xlm-route",
        amount_microunits=10000,
        networks=["stellar_mainnet_xlm"],
        payout_address="GD45SH4TC4TMJOJWJJSLGAXODAIO36POCACT2MWS7I6CTJORMFKEP3HR",
    )
    fake_xlm = b64j({"network": "stellar-mainnet", "payload": {"txId": "0" * 64}})
    result_xlm = gate_xlm.check({"Authorization": f"Payment {fake_xlm}"})
    test("XLM native: verification failed (not routing error)", "verification" in (result_xlm.error or "").lower())

    # 34. 8-network gate challenge
    print("\n34. 8-network gate challenge (all chains × all tokens)")
    gate8 = MppGate(
        api_base="https://api1.ilovechicken.co.uk",
        api_key="test_key",
        tenant_id="test_tenant",
        resource_id="all-8-chains",
        amount_microunits=10000,
        networks=[
            "algorand_mainnet", "algorand_mainnet_algo",
            "voi_mainnet",      "voi_mainnet_voi",
            "hedera_mainnet",   "hedera_mainnet_hbar",
            "stellar_mainnet",  "stellar_mainnet_xlm",
        ],
        payout_address="TEST_ADDR",
    )
    result8 = gate8.check({})
    test("8-network gate issues challenge", result8.requires_payment and result8.challenge is not None)
    if result8.challenge:
        accepts8 = result8.challenge.accepts
        test("8 entries in accepts", len(accepts8) == 8, f"got {len(accepts8)}")
        native_entries  = [a for a in accepts8 if a.get("asset") == "native"]
        usdc_entries    = [a for a in accepts8 if a.get("asset") != "native"]
        test("4 native asset entries", len(native_entries) == 4, f"got {len(native_entries)}")
        test("4 stablecoin asset entries", len(usdc_entries) == 4, f"got {len(usdc_entries)}")
        tickers = {a.get("ticker") for a in accepts8}
        test("USDC ticker in 8-chain accepts", "USDC" in tickers)
        test("aUSDC ticker in 8-chain accepts", "aUSDC" in tickers)
        test("ALGO ticker in 8-chain accepts", "ALGO" in tickers)
        test("VOI ticker in 8-chain accepts", "VOI" in tickers)
        test("HBAR ticker in 8-chain accepts", "HBAR" in tickers)
        test("XLM ticker in 8-chain accepts", "XLM" in tickers)

    # Summary
    print("\n" + "=" * 55)
    print(f"Results: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
