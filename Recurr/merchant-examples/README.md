# Tier 2 — Merchant-side examples

Working examples of the merchant-side Tier 2 lifecycle (create
authority, confirm, manage, handle webhooks). The merchant flow is
**chain-agnostic** — the same HTTP endpoints work across all 7
supported chains. The only chain-specific detail at the merchant
layer is the `cap_amount_minor` decimals (6 on most chains, 7 on
Stellar).

For wallet-side / customer-signing flows (per chain), see the
sibling per-chain folders:
[`../algorand/`](../algorand/) · [`../voi/`](../voi/) ·
[`../evm/`](../evm/) · [`../solana/`](../solana/) ·
[`../hedera/`](../hedera/) · [`../stellar/`](../stellar/).

---

## Language status

| Language | File | Adapter version | Notes |
|---|---|---|---|
| Python | [`python.py`](python.py) | `native-python/algovoi.py` v1.2.0+ | Full Tier 2 surface — 8 lifecycle methods + `is_recurring_event` helper. **Shipped.** |
| Go | _coming soon_ | `native-go/` | Tracked as the next adapter to ship. Same shape as Python: HTTP wrappers, no chain SDKs. |
| PHP | _coming soon_ | `native-php/` | Tracked. |
| Rust | _coming soon_ | `native-rust/` | Tracked. |

The Go / PHP / Rust adapters already exist for Tier 1 (one-shot
hosted checkout). Adding Tier 2 to each is a mechanical port of the
8 methods in `native-python/algovoi.py`'s Tier 2 section — the
HTTP-shape contract is identical across languages.

---

## Lifecycle (chain-agnostic merchant view)

```
POST /v1/recurring/authorities
  ↓ returns: { authority: {...}, customer_signing_payload: <chain-specific> }
  ↓
[wallet signs the customer_signing_payload — see per-chain folder]
  ↓
POST /v1/recurring/authorities/{id}/confirm
  ↓ marks authority active
  ↓
[AlgoVoi cycle reaper auto-pulls per cap_period_seconds]
  ↓
[your webhook handler receives subscription.charged / .payment_failed]
  ↓
[any time] GET    /v1/recurring/authorities/{id}    inspect state
[any time] POST   /v1/recurring/authorities/{id}/pause / resume
[when done] POST  /v1/recurring/authorities/{id}/revoke
```

`python.py` walks through each step end-to-end with comments.

---

## Why these aren't language-specific

The reason `python.py` is the only file here is that **Tier 2's
merchant side has no chain-specific code**. `create_recurring_authority`
takes a `chain` field, the gateway returns the right
`customer_signing_payload` for that chain, and your wallet UI handles
chain-native signing using the matching per-chain folder.

So a Go merchant adapter would be the same 8 methods translated to
Go's idioms — no chain-specific switches at the Go layer. Same for
PHP and Rust. We'll add `go.go` / `php.php` / `rust.rs` here as the
underlying language adapters extend their Tier 2 surface.

---

## Running `python.py`

```bash
# From this directory:
python python.py

# Or copy native-python/algovoi.py adjacent to python.py and run from anywhere
cp ../../native-python/algovoi.py .
python python.py
```

The default run is a smoke check that lists supported chains + event
types without making network calls. Replace the `api_key` /
`tenant_id` / `webhook_secret` at the top of the file with real values,
then call `example_create_authority(subscription_id, customer_wallet, chain)`
to exercise a real lifecycle.
