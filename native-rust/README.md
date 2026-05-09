# Native Rust — AlgoVoi Payment Adapter

Zero-dependency Rust library (stdlib only, no crates) for integrating AlgoVoi payments (hosted checkout, in-page wallet, and webhook verification) into any Rust HTTP server.

Full integration guide: [native-rust — see root README](https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `src/lib.rs` | Client library — `Client`, `Config`, hosted checkout, extension payment, webhook HMAC verification |
| `src/recurring.rs` | Tier 2 — standing-authority recurring payments (8 lifecycle methods + helpers, no `serde` dep) |
| `Cargo.toml` | Package manifest (no external dependencies) |

---

## Quick start — Tier 1 (one-shot payment)

```rust
use algovoi::{Client, Config};

let client = Client::new(Config {
    api_base: "https://api1.ilovechicken.co.uk".into(),
    api_key: "algv_...".into(),
    tenant_id: "uuid".into(),
    webhook_secret: "secret".into(),
});

let link = client.create_payment_link(9.99, "USD", "ORDER-001")?;
// redirect to link.url
```

---

## Quick start — Tier 2 (recurring / standing authority)

The adapter's `HttpClient` trait is caller-pluggable — bring your own HTTP client
(`ureq`, `reqwest`, `hyper`, etc.) by implementing the 2-method trait.

```rust
use algovoi::recurring::{AuthorityCreateRequest, ConfirmAuthorityRequest, is_recurring_event};
use std::collections::BTreeMap;

// 1. Create a standing authority for a monthly $10 subscription.
let resp = client.create_recurring_authority(&http, &AuthorityCreateRequest {
    subscription_id: "YOUR_SUBSCRIPTION_UUID".into(),
    chain: "algorand_mainnet".into(),   // or any of the 7 chains
    customer_wallet_address: "CUSTOMER_ALGO_ADDRESS".into(),
    cap_amount_minor: 120_000_000,      // $120 cap (6 decimals)
    cap_period_seconds: 365 * 86400,   // 1-year window
    per_cycle_amount_minor: 10_000_000, // $10/month per pull
    asset: String::new(),               // defaults to "USDC"
    metadata: BTreeMap::new(),
})?;
// resp.customer_signing_payload_json — hand to the customer's wallet UI

// 2. After on-chain landing, confirm:
let auth = client.confirm_authority(&http, &resp.authority.id, &ConfirmAuthorityRequest {
    on_chain_address: "app:12345678".into(),  // format varies by chain
    first_cycle_due_at: String::new(),
})?;

// 3. Lifecycle management:
let auth = client.get_authority(&http, &authority_id)?;
let auth = client.pause_authority(&http, &authority_id)?;
let auth = client.resume_authority(&http, &authority_id, "")?;
let auth = client.revoke_authority(&http, &authority_id)?;  // on-chain revocation

// 4. Webhook classification:
let event_type = &payload["event_type"];  // parsed from verified webhook body
if is_recurring_event(event_type) {
    // "subscription.charged", "subscription.payment_failed",
    // "recurring.authority_activated", etc.
}
```

Stellar uses 7-decimal USDC precision (`1_200_000_000` = 120 USDC).
All other chains use 6 decimals.

See [`Recurr/merchant-examples/rust.rs`](../Recurr/merchant-examples/rust.rs)
for a full runnable example and
[`Recurr/README.md`](../Recurr/README.md) for the chain matrix.

---

Licensed under the [Business Source License 1.1](../LICENSE).
