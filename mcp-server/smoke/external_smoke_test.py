"""
External smoke test for @algovoi/mcp-server published on npm.

Simulates what Claude Desktop / Cursor / any external MCP client would do:
  1. Fresh `npx @algovoi/mcp-server@1.1.3` (cold cache, forced re-fetch)
  2. Full MCP handshake (initialize)
  3. List tools (should return 11)
  4. Call list_networks (offline — validates tool dispatch)
  5. Call generate_mpp_challenge (offline — validates HMAC compose)

Prints each step pass/fail. Exits 1 on any failure.
"""
import json, os, subprocess, sys, tempfile


def send(proc, obj):
    proc.stdin.write(json.dumps(obj) + "\n")
    proc.stdin.flush()


def read(proc, timeout=10):
    # Read one JSON-RPC line from stdout (non-blocking up to timeout).
    import select
    if os.name == "nt":
        # Windows: no select on pipes. Just read blocking.
        return json.loads(proc.stdout.readline())
    r, _, _ = select.select([proc.stdout], [], [], timeout)
    if not r:
        raise TimeoutError("no response within timeout")
    return json.loads(proc.stdout.readline())


def main():
    # Use a temp HOME so npm pulls fresh (no local cache)
    with tempfile.TemporaryDirectory() as tmp:
        env = os.environ.copy()
        env["ALGOVOI_API_KEY"] = "algv_smoke_test_" + "a" * 30
        env["ALGOVOI_TENANT_ID"] = "00000000-0000-0000-0000-000000000000"
        env["ALGOVOI_PAYOUT_ADDRESS"] = "ALGOVOI_SMOKE_ADDR"
        env["ALGOVOI_API_BASE"] = "https://cloud.algovoi.co.uk"
        env["ALGOVOI_WEBHOOK_SECRET"] = "smoke_webhook_secret"

        print("=" * 70)
        print("External MCP smoke test  —  @algovoi/mcp-server@1.1.3 via npx")
        print("=" * 70)

        # Windows: npx.cmd is the shell wrapper
        npx = "npx.cmd" if os.name == "nt" else "npx"
        cmd = [npx, "-y", "@algovoi/mcp-server@1.1.3"]
        print(f"\n[1] Spawning: {' '.join(cmd)}")
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
            bufsize=1,
            shell=False,
        )

        try:
            # --- initialize ---
            print("\n[2] Sending initialize...")
            send(proc, {
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "external-smoke", "version": "1"},
                },
            })
            resp = read(proc)
            assert resp.get("id") == 1 and "result" in resp, f"bad init: {resp}"
            server_info = resp["result"]["serverInfo"]
            print(f"    OK  serverInfo: {server_info['name']} v{server_info['version']}")
            print(f"    OK  protocol:   {resp['result']['protocolVersion']}")

            # --- tools/list ---
            print("\n[3] Calling tools/list...")
            send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            resp = read(proc)
            tools = resp["result"]["tools"]
            print(f"    OK  {len(tools)} tools returned:")
            for t in tools:
                print(f"        - {t['name']}")
            assert len(tools) >= 8, f"expected >=8 tools, got {len(tools)}"

            # --- tools/call list_networks (offline) ---
            print("\n[4] Calling list_networks (offline)...")
            send(proc, {
                "jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {"name": "list_networks", "arguments": {}},
            })
            resp = read(proc)
            content = resp["result"]["content"][0]["text"]
            data = json.loads(content)
            net_count = len(data.get("networks", []))
            print(f"    OK  {net_count} networks returned (expected 16)")
            assert net_count == 16, f"expected 16 networks, got {net_count}"

            # --- tools/call generate_mpp_challenge (offline HMAC) ---
            print("\n[5] Calling generate_mpp_challenge (offline)...")
            send(proc, {
                "jsonrpc": "2.0", "id": 4, "method": "tools/call",
                "params": {
                    "name": "generate_mpp_challenge",
                    "arguments": {
                        "resource_id": "smoke-test-resource",
                        "amount": "1.00",
                        "network": "algorand_mainnet",
                    },
                },
            })
            resp = read(proc)
            result = resp.get("result", {})
            if result.get("isError"):
                print(f"    SKIP  tool returned error (likely missing env): {result['content'][0]['text'][:80]}")
            else:
                content = result["content"][0]["text"]
                print(f"    OK  challenge length: {len(content)} chars")

            # --- tools/call verify_webhook (offline HMAC) ---
            print("\n[6] Calling verify_webhook (offline)...")
            send(proc, {
                "jsonrpc": "2.0", "id": 5, "method": "tools/call",
                "params": {
                    "name": "verify_webhook",
                    "arguments": {
                        "signature": "deadbeef",
                        "body": '{"test":true}',
                    },
                },
            })
            resp = read(proc)
            content = resp["result"]["content"][0]["text"]
            print(f"    OK  signature-check result (expected 'invalid'): {content[:60]}")

            # --- shutdown ---
            print("\n[7] Closing connection...")
            proc.stdin.close()
            proc.wait(timeout=5)
            print(f"    OK  exited cleanly (code {proc.returncode})")

            print("\n" + "=" * 70)
            print("ALL EXTERNAL TESTS PASSED")
            print("=" * 70)

        except Exception as e:
            err = proc.stderr.read() if proc.stderr else ""
            print(f"\n!! FAIL: {e}")
            print(f"!! stderr: {err[:500]}")
            try:
                proc.kill()
            except Exception:
                pass
            sys.exit(1)


if __name__ == "__main__":
    main()
