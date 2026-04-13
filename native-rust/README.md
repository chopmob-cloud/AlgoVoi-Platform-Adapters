# Native Rust — AlgoVoi Payment Adapter

Zero-dependency Rust library (stdlib only, no crates) for integrating AlgoVoi payments (hosted checkout, in-page wallet, and webhook verification) into any Rust HTTP server.

Full integration guide: [native-rust — see root README](https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `src/lib.rs` | Client library — `Client`, `Config`, hosted checkout, extension payment, webhook HMAC verification |
| `Cargo.toml` | Package manifest (no external dependencies) |

---

## Quick start

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

Licensed under the [Business Source License 1.1](../LICENSE).
