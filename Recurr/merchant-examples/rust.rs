//! AlgoVoi Tier 2 — Rust merchant-side example.
//!
//! Runnable reference showing the full Tier 2 lifecycle from the
//! merchant's perspective. The wallet-side flow (where the customer
//! actually signs the on-chain authorisation) is documented per chain
//! in `../algorand/`, `../voi/`, `../evm/`, `../solana/`, `../hedera/`,
//! `../stellar/`.
//!
//! Uses the native-rust adapter at `../../native-rust/` (v1.2.0+) — the
//! chain-agnostic merchant HTTP wrapper. Zero external crates required
//! by the adapter itself; this example uses `ureq` only to satisfy the
//! `HttpClient` trait that the adapter accepts (you can swap in
//! `reqwest`, `hyper`, or any other HTTP client by implementing the
//! 2-method trait).
//!
//! ```text
//! # Cargo.toml of your merchant project:
//! [dependencies]
//! algovoi = { path = "../../native-rust" }
//! ureq = "2"   # or reqwest, hyper, isahc, ...
//! ```
//!
//! Build:
//!   cargo run --example rust
//! ```

#![allow(dead_code, unused_imports)]

use std::collections::BTreeMap;

use algovoi::{
    is_recurring_event, is_recurring_network, recurring,
    AuthorityCreateRequest, Client, Config, ConfirmAuthorityRequest, Error,
    HttpClient, HttpResponse, ListAuthoritiesOptions, PullRequest,
    RECURRING_EVENT_TYPES, RECURRING_NETWORKS,
};

// ---------------------------------------------------------------------------
// Step 0 — Plug in your favourite HTTP client.
//
// The native-rust adapter is std-only at the type level — it accepts
// any `&dyn HttpClient`. Below is a sketch using `ureq`, but use
// whatever fits your stack.
// ---------------------------------------------------------------------------

struct UreqHttpClient;

impl HttpClient for UreqHttpClient {
    fn get(&self, url: &str) -> Result<HttpResponse, Error> {
        // let resp = ureq::get(url).call().map_err(|e| Error::Http(e.to_string()))?;
        // Ok(HttpResponse {
        //     status: resp.status(),
        //     body: resp.into_string().unwrap_or_default(),
        // })
        Err(Error::Http("ureq not wired in this stub — implement HttpClient with your HTTP crate".into()))
    }

    fn post(&self, url: &str, json_body: &str, headers: &[(&str, &str)]) -> Result<HttpResponse, Error> {
        // let mut req = ureq::post(url);
        // for (k, v) in headers { req = req.set(k, v); }
        // let resp = req.send_string(json_body).map_err(|e| Error::Http(e.to_string()))?;
        // Ok(HttpResponse {
        //     status: resp.status(),
        //     body: resp.into_string().unwrap_or_default(),
        // })
        Err(Error::Http("ureq not wired in this stub".into()))
    }
}

// ---------------------------------------------------------------------------
// Step 1 — Create a Tier 2 standing authority for an existing subscription
// ---------------------------------------------------------------------------

fn example_create_authority(
    client: &Client,
    http: &dyn HttpClient,
    subscription_id: &str,
    customer_wallet: &str,
    chain: &str,
) -> Result<recurring::AuthorityCreateResponse, Error> {
    if !is_recurring_network(chain) {
        return Err(Error::InvalidInput(format!("unsupported chain: {chain}")));
    }

    // Cap amounts depend on chain decimals.
    // Most chains: 6 decimals. Stellar: 7 decimals.
    let (per_cycle, total_cap) = if chain.starts_with("stellar_") {
        (10 * 10_000_000_i64, 120 * 10_000_000_i64)
    } else {
        (10 * 1_000_000_i64, 120 * 1_000_000_i64)
    };

    let mut metadata = BTreeMap::new();
    metadata.insert("plan".into(), "monthly_pro".into());
    metadata.insert("customer_email".into(), "alice@example.com".into());

    let req = AuthorityCreateRequest {
        subscription_id: subscription_id.into(),
        chain: chain.into(),
        customer_wallet_address: customer_wallet.into(),
        cap_amount_minor: total_cap,
        cap_period_seconds: 365 * 86400,
        per_cycle_amount_minor: per_cycle,
        asset: "USDC".into(),
        metadata,
    };

    let resp = client.create_recurring_authority(http, &req)?;
    println!("[create] authority_id = {}", resp.authority.id);
    println!("[create] status       = {}", resp.authority.status);
    println!(
        "[create] template ver = {}",
        // Embedded chain-specific JSON; print first 80 chars for context
        &resp.customer_signing_payload_json[..resp.customer_signing_payload_json.len().min(80)]
    );

    // Hand `resp.customer_signing_payload_json` to your frontend wallet UI.
    // The per-chain folders in this directory have wallet-side reference code.
    Ok(resp)
}

// ---------------------------------------------------------------------------
// Step 2 — After the customer's wallet signs and on-chain auth lands
// ---------------------------------------------------------------------------

fn example_confirm_authority(
    client: &Client,
    http: &dyn HttpClient,
    authority_id: &str,
    on_chain_handle: &str,
) -> Result<recurring::Authority, Error> {
    let confirmed = client.confirm_authority(
        http,
        authority_id,
        &ConfirmAuthorityRequest {
            on_chain_address: on_chain_handle.into(),
            first_cycle_due_at: String::new(),
        },
    )?;
    println!("[confirm] status = {} (should be 'active')", confirmed.status);
    Ok(confirmed)
}

// ---------------------------------------------------------------------------
// Step 3 — Read state any time
// ---------------------------------------------------------------------------

fn example_inspect(client: &Client, http: &dyn HttpClient, authority_id: &str) {
    match client.get_authority(http, authority_id) {
        Ok(a) => println!(
            "[inspect] status={} cycles={}/{} remaining={}",
            a.status,
            a.cycles_pulled,
            a.cycles_pulled + a.cycles_failed,
            a.cap_remaining_minor,
        ),
        Err(e) => println!("[inspect] error: {e}"),
    }
}

fn example_list_active(client: &Client, http: &dyn HttpClient) {
    let opts = ListAuthoritiesOptions {
        status: Some("active".into()),
        limit: 50,
        ..Default::default()
    };
    match client.list_authorities(http, &opts) {
        Ok(list) => {
            println!("[list] {} active authorities", list.len());
            for a in list {
                println!(
                    "    {}  chain={}  cycles={}",
                    a.id, a.chain, a.cycles_pulled
                );
            }
        }
        Err(e) => println!("[list] error: {e}"),
    }
}

// ---------------------------------------------------------------------------
// Step 4 — Lifecycle controls
// ---------------------------------------------------------------------------

fn example_pause(client: &Client, http: &dyn HttpClient, authority_id: &str) {
    let _ = client.pause_authority(http, authority_id);
}

fn example_resume(client: &Client, http: &dyn HttpClient, authority_id: &str) {
    let _ = client.resume_authority(http, authority_id, "");
}

fn example_revoke(client: &Client, http: &dyn HttpClient, authority_id: &str) {
    match client.revoke_authority(http, authority_id) {
        Ok(a) => println!("[revoke] status = {}", a.status), // 'revoking' → 'revoked'
        Err(e) => println!("[revoke] error: {e}"),
    }
}

fn example_manual_pull(
    client: &Client,
    http: &dyn HttpClient,
    authority_id: &str,
    amount_minor: i64,
) {
    let req = PullRequest {
        authority_id: authority_id.into(),
        amount_minor,
        idempotency_key: format!("manual_{authority_id}_{amount_minor}"),
    };
    match client.manual_pull(http, &req) {
        Ok(a) => println!("[pull] accepted; status = {}", a.status),
        Err(e) => println!("[pull] error: {e}"),
    }
}

// ---------------------------------------------------------------------------
// Step 5 — Webhook handler
//
// Tier 2 emits these event types alongside Tier 1's payment.* events.
// verify_webhook + is_recurring_event let you fork the handler.
// ---------------------------------------------------------------------------

fn example_webhook_handler(
    client: &Client,
    raw_body: &str,
    signature: &str,
) -> Result<(), Error> {
    // Existing Tier 1 webhook verifier — returns the verified raw JSON
    // body as a String (no built-in parser; bring your own).
    let verified_json = client.verify_webhook(raw_body.as_bytes(), signature)?;

    // Extract the event type. The adapter is std-only so you'd typically
    // parse with `serde_json` in production. Below is a stdlib-only
    // string scan for the demo — replace with serde_json::Value when you
    // wire this into a real handler.
    let event_type = naive_event_type(&verified_json);

    if is_recurring_event(&event_type) {
        match event_type.as_str() {
            "subscription.charged" => {
                println!("[webhook] charged: extend customer access");
            }
            "subscription.payment_failed" => {
                println!("[webhook] failed: trigger dunning");
            }
            "recurring.authority_revoked" => {
                println!("[webhook] revoked: cancel subscription");
            }
            "recurring.authority_expired" => {
                println!("[webhook] expired: notify customer to renew");
            }
            other => {
                println!("[webhook] recurring event: {other}");
            }
        }
    } else {
        println!("[webhook] one-shot event");
    }
    Ok(())
}

/// Naive top-level "event_type":"<value>" extractor. Sufficient for
/// dispatch on AlgoVoi's webhook envelopes; for production use
/// serde_json (small, well-trusted, ~80 KB) for cleaner parsing.
fn naive_event_type(json: &str) -> String {
    let pattern = "\"event_type\":\"";
    if let Some(pos) = json.find(pattern) {
        let rest = &json[pos + pattern.len()..];
        if let Some(end) = rest.find('"') {
            return rest[..end].to_string();
        }
    }
    String::new()
}

// ---------------------------------------------------------------------------
// Smoke check — list supported chains + event types
// ---------------------------------------------------------------------------

fn main() {
    let _client = Client::new(Config {
        api_base: "https://api1.ilovechicken.co.uk".into(),
        api_key: "algv_REPLACE_ME".into(),
        tenant_id: "REPLACE_ME_UUID".into(),
        webhook_secret: "whsec_REPLACE_ME".into(),
    });

    println!("Tier 2 chains supported by this adapter:");
    let mut chains: Vec<&&str> = RECURRING_NETWORKS.iter().collect();
    chains.sort();
    for c in chains {
        println!("  - {c}");
    }

    println!("\nTier 2 webhook event types:");
    let mut events: Vec<&&str> = RECURRING_EVENT_TYPES.iter().collect();
    events.sort();
    for e in events {
        println!("  - {e}");
    }

    println!(
        "\nReady to integrate. Replace the api_key / tenant_id / \
         webhook_secret + plug an HttpClient impl into UreqHttpClient \
         (or your preferred crate), then call example_create_authority(...)."
    );
}
