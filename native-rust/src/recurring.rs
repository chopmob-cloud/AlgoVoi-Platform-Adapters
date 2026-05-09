//! Tier 2 — Standing-Authority Recurring Payments
//!
//! Tier 2 is "customer signs ONCE, AlgoVoi auto-pulls per cycle".
//! Tier 1 (hosted/extension checkout) is "customer clicks pay on every
//! invoice".
//!
//! ## Lifecycle
//!
//! 1. Tenant creates a Tier 1 subscription (POST /v1/subscriptions —
//!    out of scope of this adapter).
//! 2. Tenant calls [`Client::create_recurring_authority`] — gateway
//!    returns `customer_signing_payload`, a chain-specific template.
//! 3. Tenant's frontend hands the template to the customer's wallet
//!    (Pera / Defly / MetaMask / Phantom / HashPack / Freighter / etc.)
//!    which constructs + signs the on-chain authorisation.
//! 4. Once on-chain, tenant calls [`Client::confirm_authority`].
//! 5. AlgoVoi's cycle reaper auto-pulls per `cap_period_seconds`. Each
//!    pull emits `subscription.charged` / `subscription.payment_failed`
//!    webhooks the tenant handles via `verify_webhook` +
//!    [`is_recurring_event`].
//! 6. To stop: [`Client::revoke_authority`] (on-chain), or
//!    [`Client::pause_authority`] / [`Client::resume_authority`]
//!    (off-chain).
//!
//! Wire formats are locked at `*_v1` — see `Recurr/<chain>/README.md`
//! in this repository for per-chain wallet-side flows.

use std::collections::BTreeMap;

use crate::{is_https, json_escape, url_encode, Client, Error, HttpClient};

// ---------------------------------------------------------------------------
// Tier 2 constants
// ---------------------------------------------------------------------------

/// Cap on recurring API response bodies. List responses are bounded by
/// gateway's `limit=200`; defence-in-depth.
pub const MAX_RECURRING_BODY_BYTES: usize = 16 * 1024;

/// Standard UUID string length.
pub const MAX_UUID_LEN: usize = 36;

/// Every Tier 2 chain id (7 mainnets + 7 testnets) — matches the
/// `RECURRING_NETWORKS` set in native-python / native-go / native-php.
pub const RECURRING_NETWORKS: &[&str] = &[
    "algorand_mainnet", "algorand_testnet",
    "voi_mainnet",      "voi_testnet",
    "base_mainnet",     "base_sepolia",
    "tempo_mainnet",    "tempo_testnet",
    "solana_mainnet",   "solana_devnet",
    "hedera_mainnet",   "hedera_testnet",
    "stellar_mainnet",  "stellar_testnet",
];

/// Tier 2 webhook event types (in addition to Tier 1's `payment.*`).
pub const RECURRING_EVENT_TYPES: &[&str] = &[
    "recurring.authority_created",
    "recurring.authority_activated",
    "recurring.authority_paused",
    "recurring.authority_resumed",
    "recurring.authority_revoked",
    "recurring.authority_expired",
    "subscription.charged",
    "subscription.payment_failed",
];

/// Test whether `network` is one of the 14 supported Tier 2 chain ids.
pub fn is_recurring_network(network: &str) -> bool {
    RECURRING_NETWORKS.iter().any(|&n| n == network)
}

/// Test whether the parsed webhook event-type string is a Tier 2 event.
///
/// Pass the value of the `event_type` (or `type`) field from the parsed
/// webhook payload. Returns true for `subscription.charged`,
/// `recurring.authority_revoked`, etc.
pub fn is_recurring_event(event_type: &str) -> bool {
    RECURRING_EVENT_TYPES.iter().any(|&e| e == event_type)
}

// ---------------------------------------------------------------------------
// Request / response types
// ---------------------------------------------------------------------------

/// Input for [`Client::create_recurring_authority`].
///
/// Stellar uses 7-decimal precision for USDC; every other chain uses 6.
/// Pass `cap_amount_minor` in chain-native atomic units.
#[derive(Debug, Clone)]
pub struct AuthorityCreateRequest {
    pub subscription_id: String,
    pub chain: String,
    pub customer_wallet_address: String,
    pub cap_amount_minor: i64,
    pub cap_period_seconds: i64,
    pub per_cycle_amount_minor: i64,
    /// Defaults to "USDC" if empty.
    pub asset: String,
    /// Free-form tenant metadata, forwarded on every webhook event.
    /// Empty map if no metadata. Values are JSON-encoded as strings.
    pub metadata: BTreeMap<String, String>,
}

/// Server-recorded standing-authority row.
#[derive(Debug, Clone, Default)]
pub struct Authority {
    pub id: String,
    pub tenant_id: String,
    pub subscription_id: String,
    pub chain: String,
    pub customer_wallet_address: String,
    pub cap_amount_minor: i64,
    pub cap_period_seconds: i64,
    pub per_cycle_amount_minor: i64,
    pub asset: String,
    pub status: String,
    pub on_chain_address: String,
    pub cap_remaining_minor: i64,
    pub cycles_pulled: i64,
    pub cycles_failed: i64,
    pub created_at: String,
    pub activated_at: String,
    pub revoked_at: String,
    pub last_error: String,
}

/// Response from [`Client::create_recurring_authority`].
///
/// `customer_signing_payload` is the raw JSON object string carrying the
/// chain-specific signing template. We don't attempt to parse it — its
/// shape varies per chain (see `Recurr/<chain>/README.md`). Hand it to
/// your frontend wallet UI as-is.
#[derive(Debug, Clone)]
pub struct AuthorityCreateResponse {
    pub authority: Authority,
    /// Raw JSON object — chain-specific. Pass through to the wallet UI.
    pub customer_signing_payload_json: String,
    pub authorisation_url: String,
}

/// Filters for [`Client::list_authorities`].
#[derive(Debug, Clone, Default)]
pub struct ListAuthoritiesOptions {
    pub subscription_id: Option<String>,
    /// One of: pending / active / paused / revoking / revoked / expired.
    pub status: Option<String>,
    /// Default 50 (when 0). Max 200.
    pub limit: u32,
    pub offset: u32,
}

/// Body for [`Client::confirm_authority`].
#[derive(Debug, Clone)]
pub struct ConfirmAuthorityRequest {
    /// Chain-native handle. Format depends on the chain:
    ///   Algorand / VOI : `app:<application_id>`
    ///   EVM            : `0x<tx_hash>`
    ///   Solana         : `<base58 tx signature>`
    ///   Hedera         : `<account_id>@<seconds>.<nanos>`
    ///   Stellar        : `<64-char hex tx hash>`
    pub on_chain_address: String,
    /// Optional ISO-8601 first-cycle due-at; gateway computes one if empty.
    pub first_cycle_due_at: String,
}

/// Body for [`Client::manual_pull`].
#[derive(Debug, Clone)]
pub struct PullRequest {
    pub authority_id: String,
    /// Pull amount in atomic units. Must be <= per_cycle_amount_minor.
    pub amount_minor: i64,
    /// Optional client-supplied key for retry safety.
    pub idempotency_key: String,
}

// ---------------------------------------------------------------------------
// Small JSON helpers (no serde)
// ---------------------------------------------------------------------------

/// Extract a quoted string value for a top-level JSON key. Returns ""
/// if not found. Mirrors the existing `extract_json_string` helper but
/// is repeated here so this module is self-contained.
fn extract_string(json: &str, key: &str) -> String {
    let pattern = format!("\"{}\":", key);
    if let Some(pos) = json.find(&pattern) {
        let rest = &json[pos + pattern.len()..];
        let rest = rest.trim_start();
        if let Some(after_quote) = rest.strip_prefix('"') {
            // Find the next unescaped closing quote
            let mut escaped = false;
            for (i, ch) in after_quote.char_indices() {
                if escaped {
                    escaped = false;
                    continue;
                }
                if ch == '\\' {
                    escaped = true;
                    continue;
                }
                if ch == '"' {
                    return after_quote[..i].to_string();
                }
            }
        }
    }
    String::new()
}

/// Extract an integer value for a top-level JSON key. Returns 0 if not
/// found or not a valid integer.
fn extract_i64(json: &str, key: &str) -> i64 {
    let pattern = format!("\"{}\":", key);
    if let Some(pos) = json.find(&pattern) {
        let rest = &json[pos + pattern.len()..];
        let rest = rest.trim_start();
        // Read while sign-digit
        let mut end = 0;
        for (i, ch) in rest.char_indices() {
            if i == 0 && (ch == '-' || ch == '+') {
                end = i + 1;
                continue;
            }
            if ch.is_ascii_digit() {
                end = i + 1;
                continue;
            }
            break;
        }
        if end > 0 {
            return rest[..end].parse().unwrap_or(0);
        }
    }
    0
}

/// Extract a top-level JSON object substring — finds `"key": {...}` and
/// returns the matching `{...}` substring including braces. Returns ""
/// if not found. Naive but handles nested objects via brace counting.
fn extract_object(json: &str, key: &str) -> String {
    let pattern = format!("\"{}\":", key);
    if let Some(pos) = json.find(&pattern) {
        let rest = &json[pos + pattern.len()..];
        let rest = rest.trim_start();
        if !rest.starts_with('{') {
            return String::new();
        }
        let mut depth = 0i32;
        let mut in_string = false;
        let mut escaped = false;
        for (i, ch) in rest.char_indices() {
            if escaped {
                escaped = false;
                continue;
            }
            if ch == '\\' {
                escaped = true;
                continue;
            }
            if ch == '"' {
                in_string = !in_string;
                continue;
            }
            if in_string {
                continue;
            }
            if ch == '{' {
                depth += 1;
            } else if ch == '}' {
                depth -= 1;
                if depth == 0 {
                    return rest[..=i].to_string();
                }
            }
        }
    }
    String::new()
}

/// Parse one Authority JSON object. Used for both single-row endpoints
/// (`get/confirm/revoke/pause/resume/pull`) and the list endpoint
/// (called per element).
pub(crate) fn parse_authority(json: &str) -> Authority {
    Authority {
        id: extract_string(json, "id"),
        tenant_id: extract_string(json, "tenant_id"),
        subscription_id: extract_string(json, "subscription_id"),
        chain: extract_string(json, "chain"),
        customer_wallet_address: extract_string(json, "customer_wallet_address"),
        cap_amount_minor: extract_i64(json, "cap_amount_minor"),
        cap_period_seconds: extract_i64(json, "cap_period_seconds"),
        per_cycle_amount_minor: extract_i64(json, "per_cycle_amount_minor"),
        asset: extract_string(json, "asset"),
        status: extract_string(json, "status"),
        on_chain_address: extract_string(json, "on_chain_address"),
        cap_remaining_minor: extract_i64(json, "cap_remaining_minor"),
        cycles_pulled: extract_i64(json, "cycles_pulled"),
        cycles_failed: extract_i64(json, "cycles_failed"),
        created_at: extract_string(json, "created_at"),
        activated_at: extract_string(json, "activated_at"),
        revoked_at: extract_string(json, "revoked_at"),
        last_error: extract_string(json, "last_error"),
    }
}

/// Parse a JSON array of Authority objects. Naive — splits on top-level
/// `},{` boundaries respecting string + brace depth. Returns empty Vec
/// if the input isn't a JSON array.
fn parse_authority_array(json: &str) -> Vec<Authority> {
    let trimmed = json.trim();
    if !trimmed.starts_with('[') || !trimmed.ends_with(']') {
        return Vec::new();
    }
    let inner = &trimmed[1..trimmed.len() - 1];
    let mut results = Vec::new();
    let mut depth = 0i32;
    let mut in_string = false;
    let mut escaped = false;
    let mut start: Option<usize> = None;
    for (i, ch) in inner.char_indices() {
        if escaped {
            escaped = false;
            continue;
        }
        if ch == '\\' {
            escaped = true;
            continue;
        }
        if ch == '"' {
            in_string = !in_string;
            continue;
        }
        if in_string {
            continue;
        }
        if ch == '{' {
            if depth == 0 {
                start = Some(i);
            }
            depth += 1;
        } else if ch == '}' {
            depth -= 1;
            if depth == 0 {
                if let Some(s) = start {
                    results.push(parse_authority(&inner[s..=i]));
                }
                start = None;
            }
        }
    }
    results
}

fn parse_create_response(json: &str) -> AuthorityCreateResponse {
    let auth_obj = extract_object(json, "authority");
    AuthorityCreateResponse {
        authority: parse_authority(&auth_obj),
        customer_signing_payload_json: extract_object(json, "customer_signing_payload"),
        authorisation_url: extract_string(json, "authorisation_url"),
    }
}

// ---------------------------------------------------------------------------
// JSON encoding for requests
// ---------------------------------------------------------------------------

fn encode_create_request(req: &AuthorityCreateRequest) -> String {
    let asset_upper = if req.asset.is_empty() {
        "USDC".to_string()
    } else {
        req.asset.to_uppercase()
    };
    let mut s = String::from("{");
    s.push_str(&format!(
        "\"subscription_id\":\"{}\",\
         \"chain\":\"{}\",\
         \"customer_wallet_address\":\"{}\",\
         \"cap_amount_minor\":{},\
         \"cap_period_seconds\":{},\
         \"per_cycle_amount_minor\":{},\
         \"asset\":\"{}\"",
        json_escape(&req.subscription_id),
        json_escape(&req.chain),
        json_escape(&req.customer_wallet_address),
        req.cap_amount_minor,
        req.cap_period_seconds,
        req.per_cycle_amount_minor,
        json_escape(&asset_upper),
    ));
    if !req.metadata.is_empty() {
        s.push_str(",\"metadata\":{");
        let mut first = true;
        for (k, v) in &req.metadata {
            if !first {
                s.push(',');
            }
            first = false;
            s.push_str(&format!("\"{}\":\"{}\"", json_escape(k), json_escape(v)));
        }
        s.push('}');
    }
    s.push('}');
    s
}

fn encode_confirm_request(req: &ConfirmAuthorityRequest) -> String {
    if req.first_cycle_due_at.is_empty() {
        format!(
            "{{\"on_chain_address\":\"{}\"}}",
            json_escape(&req.on_chain_address)
        )
    } else {
        format!(
            "{{\"on_chain_address\":\"{}\",\"first_cycle_due_at\":\"{}\"}}",
            json_escape(&req.on_chain_address),
            json_escape(&req.first_cycle_due_at),
        )
    }
}

fn encode_resume_request(next_cycle_due_at: &str) -> String {
    if next_cycle_due_at.is_empty() {
        "{}".into()
    } else {
        format!(
            "{{\"next_cycle_due_at\":\"{}\"}}",
            json_escape(next_cycle_due_at)
        )
    }
}

fn encode_pull_request(req: &PullRequest) -> String {
    let mut s = format!(
        "{{\"authority_id\":\"{}\",\"amount_minor\":{}",
        json_escape(&req.authority_id),
        req.amount_minor,
    );
    if !req.idempotency_key.is_empty() {
        s.push_str(&format!(
            ",\"idempotency_key\":\"{}\"",
            json_escape(&req.idempotency_key)
        ));
    }
    s.push('}');
    s
}

// ---------------------------------------------------------------------------
// Authenticated-status-aware authorisation header
// ---------------------------------------------------------------------------

fn auth_headers<'a>(api_key: &'a str, tenant_id: &'a str) -> [(String, String); 2] {
    [
        ("Authorization".into(), format!("Bearer {api_key}")),
        ("X-Tenant-Id".into(), tenant_id.into()),
    ]
}

/// Run an HttpClient request that returns `Authority`. Used by the four
/// post-only authority endpoints (revoke / pause / resume / confirm).
fn post_for_authority(
    http: &dyn HttpClient,
    api_base: &str,
    api_key: &str,
    tenant_id: &str,
    path: &str,
    body: &str,
) -> Result<Authority, Error> {
    if !is_https(api_base) {
        return Err(Error::InvalidInput("api_base must use https scheme".into()));
    }
    let url = format!("{}{}", api_base.trim_end_matches('/'), path);
    let owned = auth_headers(api_key, tenant_id);
    let headers: Vec<(&str, &str)> = vec![
        ("Content-Type", "application/json"),
        (owned[0].0.as_str(), owned[0].1.as_str()),
        (owned[1].0.as_str(), owned[1].1.as_str()),
    ];
    let resp = http.post(&url, body, &headers)?;
    if resp.status < 200 || resp.status >= 300 {
        return Err(Error::Http(format!("HTTP {}: {}", resp.status, resp.body)));
    }
    if resp.body.len() > MAX_RECURRING_BODY_BYTES {
        return Err(Error::InvalidResponse(format!(
            "response exceeds {MAX_RECURRING_BODY_BYTES} bytes"
        )));
    }
    Ok(parse_authority(&resp.body))
}

// ---------------------------------------------------------------------------
// Client API
// ---------------------------------------------------------------------------

impl Client {
    fn api_base(&self) -> &str {
        &self.config().api_base
    }
    fn api_key(&self) -> &str {
        &self.config().api_key
    }
    fn tenant_id(&self) -> &str {
        &self.config().tenant_id
    }

    /// Create a Tier 2 standing authority for an existing subscription.
    pub fn create_recurring_authority(
        &self,
        http: &dyn HttpClient,
        req: &AuthorityCreateRequest,
    ) -> Result<AuthorityCreateResponse, Error> {
        if !is_recurring_network(&req.chain) {
            return Err(Error::InvalidInput(format!(
                "unsupported recurring chain: {}",
                req.chain
            )));
        }
        if req.subscription_id.is_empty() || req.subscription_id.len() > MAX_UUID_LEN {
            return Err(Error::InvalidInput("invalid subscription_id".into()));
        }
        if req.customer_wallet_address.is_empty() {
            return Err(Error::InvalidInput("customer_wallet_address required".into()));
        }
        if req.customer_wallet_address.len() > 128 {
            return Err(Error::InvalidInput("customer_wallet_address too long (max 128 chars)".into()));
        }
        if req.cap_amount_minor <= 0 || req.cap_period_seconds <= 0 || req.per_cycle_amount_minor <= 0 {
            return Err(Error::InvalidInput("amounts and period must be positive".into()));
        }
        if req.cap_period_seconds < 86400 {
            return Err(Error::InvalidInput(
                "cap_period_seconds must be >= 86400 (1 day)".into(),
            ));
        }
        if req.per_cycle_amount_minor > req.cap_amount_minor {
            return Err(Error::InvalidInput(
                "per_cycle_amount_minor cannot exceed cap_amount_minor".into(),
            ));
        }
        if !is_https(self.api_base()) {
            return Err(Error::InvalidInput("api_base must use https scheme".into()));
        }

        let url = format!(
            "{}/v1/recurring/authorities",
            self.api_base().trim_end_matches('/')
        );
        let body = encode_create_request(req);
        let owned = auth_headers(self.api_key(), self.tenant_id());
        let resp = http.post(
            &url,
            &body,
            &[
                ("Content-Type", "application/json"),
                (owned[0].0.as_str(), owned[0].1.as_str()),
                (owned[1].0.as_str(), owned[1].1.as_str()),
            ],
        )?;
        if resp.status < 200 || resp.status >= 300 {
            return Err(Error::Http(format!("HTTP {}: {}", resp.status, resp.body)));
        }
        if resp.body.len() > MAX_RECURRING_BODY_BYTES {
            return Err(Error::InvalidResponse(format!(
                "response exceeds {MAX_RECURRING_BODY_BYTES} bytes"
            )));
        }
        Ok(parse_create_response(&resp.body))
    }

    /// Fetch the current state of a recurring authority by id.
    pub fn get_authority(
        &self,
        http: &dyn HttpClient,
        authority_id: &str,
    ) -> Result<Authority, Error> {
        if authority_id.is_empty() || authority_id.len() > MAX_UUID_LEN {
            return Err(Error::InvalidInput("invalid authority_id".into()));
        }
        if !is_https(self.api_base()) {
            return Err(Error::InvalidInput("api_base must use https scheme".into()));
        }
        let url = format!(
            "{}/v1/recurring/authorities/{}",
            self.api_base().trim_end_matches('/'),
            url_encode(authority_id),
        );
        let resp = http.get(&url)?;
        if resp.status < 200 || resp.status >= 300 {
            return Err(Error::Http(format!("HTTP {}: {}", resp.status, resp.body)));
        }
        if resp.body.len() > MAX_RECURRING_BODY_BYTES {
            return Err(Error::InvalidResponse(format!(
                "response exceeds {MAX_RECURRING_BODY_BYTES} bytes"
            )));
        }
        Ok(parse_authority(&resp.body))
    }

    /// List recurring authorities for this tenant.
    pub fn list_authorities(
        &self,
        http: &dyn HttpClient,
        opts: &ListAuthoritiesOptions,
    ) -> Result<Vec<Authority>, Error> {
        let limit = if opts.limit == 0 { 50 } else { opts.limit };
        if limit < 1 || limit > 200 {
            return Err(Error::InvalidInput("limit must be 1..=200".into()));
        }
        if !is_https(self.api_base()) {
            return Err(Error::InvalidInput("api_base must use https scheme".into()));
        }

        let mut path = format!("/v1/recurring/authorities?limit={}&offset={}", limit, opts.offset);
        if let Some(ref sid) = opts.subscription_id {
            if sid.len() > MAX_UUID_LEN {
                return Err(Error::InvalidInput("invalid subscription_id".into()));
            }
            path.push_str(&format!("&subscription_id={}", url_encode(sid)));
        }
        if let Some(ref status) = opts.status {
            if status.len() > 32 || !status.chars().all(|c| c.is_ascii_alphanumeric() || c == '_') {
                return Err(Error::InvalidInput("invalid status filter".into()));
            }
            path.push_str(&format!("&status={}", url_encode(status)));
        }

        let url = format!("{}{}", self.api_base().trim_end_matches('/'), path);
        let resp = http.get(&url)?;
        if resp.status < 200 || resp.status >= 300 {
            return Err(Error::Http(format!("HTTP {}: {}", resp.status, resp.body)));
        }
        if resp.body.len() > MAX_RECURRING_BODY_BYTES {
            return Err(Error::InvalidResponse(format!(
                "response exceeds {MAX_RECURRING_BODY_BYTES} bytes"
            )));
        }
        Ok(parse_authority_array(&resp.body))
    }

    /// Mark a pending authority active after on-chain landing.
    ///
    /// Most tenants don't need to call this — the AlgoVoi widget does it.
    /// Surfaced here for self-hosted wallet UIs.
    pub fn confirm_authority(
        &self,
        http: &dyn HttpClient,
        authority_id: &str,
        req: &ConfirmAuthorityRequest,
    ) -> Result<Authority, Error> {
        if authority_id.is_empty() || authority_id.len() > MAX_UUID_LEN {
            return Err(Error::InvalidInput("invalid authority_id".into()));
        }
        if req.on_chain_address.is_empty() || req.on_chain_address.len() > 200 {
            return Err(Error::InvalidInput("invalid on_chain_address".into()));
        }
        if !req.first_cycle_due_at.is_empty() && req.first_cycle_due_at.len() > 64 {
            return Err(Error::InvalidInput("invalid first_cycle_due_at".into()));
        }
        let path = format!(
            "/v1/recurring/authorities/{}/confirm",
            url_encode(authority_id)
        );
        let body = encode_confirm_request(req);
        post_for_authority(http, self.api_base(), self.api_key(), self.tenant_id(), &path, &body)
    }

    /// Revoke an active authority. Gateway constructs the chain-specific
    /// revocation transaction; the customer's wallet signs it. Authority
    /// transitions to `revoking` until on-chain landing, then `revoked`.
    pub fn revoke_authority(
        &self,
        http: &dyn HttpClient,
        authority_id: &str,
    ) -> Result<Authority, Error> {
        if authority_id.is_empty() || authority_id.len() > MAX_UUID_LEN {
            return Err(Error::InvalidInput("invalid authority_id".into()));
        }
        let path = format!(
            "/v1/recurring/authorities/{}/revoke",
            url_encode(authority_id)
        );
        post_for_authority(http, self.api_base(), self.api_key(), self.tenant_id(), &path, "{}")
    }

    /// Pause an active authority — no on-chain action. Stops cycle pulls
    /// until `resume_authority` is called.
    pub fn pause_authority(
        &self,
        http: &dyn HttpClient,
        authority_id: &str,
    ) -> Result<Authority, Error> {
        if authority_id.is_empty() || authority_id.len() > MAX_UUID_LEN {
            return Err(Error::InvalidInput("invalid authority_id".into()));
        }
        let path = format!(
            "/v1/recurring/authorities/{}/pause",
            url_encode(authority_id)
        );
        post_for_authority(http, self.api_base(), self.api_key(), self.tenant_id(), &path, "{}")
    }

    /// Resume a paused authority. Pass non-empty `next_cycle_due_at` to
    /// delay the first post-resume pull; otherwise pulls resume on the
    /// existing schedule.
    pub fn resume_authority(
        &self,
        http: &dyn HttpClient,
        authority_id: &str,
        next_cycle_due_at: &str,
    ) -> Result<Authority, Error> {
        if authority_id.is_empty() || authority_id.len() > MAX_UUID_LEN {
            return Err(Error::InvalidInput("invalid authority_id".into()));
        }
        if !next_cycle_due_at.is_empty() && next_cycle_due_at.len() > 64 {
            return Err(Error::InvalidInput("invalid next_cycle_due_at".into()));
        }
        let path = format!(
            "/v1/recurring/authorities/{}/resume",
            url_encode(authority_id)
        );
        let body = encode_resume_request(next_cycle_due_at);
        post_for_authority(http, self.api_base(), self.api_key(), self.tenant_id(), &path, &body)
    }

    /// Manually trigger a pull (e.g. catch-up after dunning, prorated
    /// mid-cycle billing). Most pulls fire automatically via the cycle
    /// reaper.
    pub fn manual_pull(
        &self,
        http: &dyn HttpClient,
        req: &PullRequest,
    ) -> Result<Authority, Error> {
        if req.authority_id.is_empty() || req.authority_id.len() > MAX_UUID_LEN {
            return Err(Error::InvalidInput("invalid authority_id".into()));
        }
        if req.amount_minor <= 0 {
            return Err(Error::InvalidInput("amount_minor must be positive".into()));
        }
        if !req.idempotency_key.is_empty() && req.idempotency_key.len() > 128 {
            return Err(Error::InvalidInput("idempotency_key too long".into()));
        }
        let body = encode_pull_request(req);
        post_for_authority(http, self.api_base(), self.api_key(), self.tenant_id(), "/v1/recurring/pulls", &body)
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{Config, HttpResponse};
    use std::cell::RefCell;

    // -----------------------------------------------------------------------
    // Constants + helpers
    // -----------------------------------------------------------------------

    #[test]
    fn recurring_networks_has_14_entries() {
        assert_eq!(RECURRING_NETWORKS.len(), 14);
    }

    #[test]
    fn is_recurring_network_classifies_correctly() {
        assert!(is_recurring_network("algorand_mainnet"));
        assert!(is_recurring_network("base_mainnet"));
        assert!(is_recurring_network("solana_devnet"));
        assert!(is_recurring_network("stellar_testnet"));
        assert!(!is_recurring_network("ethereum_mainnet"));
        assert!(!is_recurring_network("polygon_mainnet"));
        assert!(!is_recurring_network(""));
    }

    #[test]
    fn recurring_event_types_has_8_entries() {
        assert_eq!(RECURRING_EVENT_TYPES.len(), 8);
    }

    #[test]
    fn is_recurring_event_classifies_correctly() {
        assert!(is_recurring_event("subscription.charged"));
        assert!(is_recurring_event("subscription.payment_failed"));
        assert!(is_recurring_event("recurring.authority_revoked"));
        assert!(!is_recurring_event("payment.succeeded"));
        assert!(!is_recurring_event(""));
    }

    // -----------------------------------------------------------------------
    // JSON helpers
    // -----------------------------------------------------------------------

    #[test]
    fn extract_string_basic() {
        assert_eq!(extract_string(r#"{"k":"v"}"#, "k"), "v");
        assert_eq!(extract_string(r#"{"a":"x","b":"y"}"#, "b"), "y");
        assert_eq!(extract_string(r#"{"k":null}"#, "k"), "");
        assert_eq!(extract_string(r#"{}"#, "k"), "");
    }

    #[test]
    fn extract_i64_basic() {
        assert_eq!(extract_i64(r#"{"n":42}"#, "n"), 42);
        assert_eq!(extract_i64(r#"{"n":-7}"#, "n"), -7);
        assert_eq!(extract_i64(r#"{"a":"x","n":120000000}"#, "n"), 120_000_000);
        assert_eq!(extract_i64(r#"{"k":"v"}"#, "missing"), 0);
    }

    #[test]
    fn extract_object_basic() {
        let s = r#"{"authority":{"id":"a1","status":"pending"},"other":"x"}"#;
        let inner = extract_object(s, "authority");
        assert_eq!(inner, r#"{"id":"a1","status":"pending"}"#);
    }

    #[test]
    fn extract_object_handles_nested_braces() {
        let s = r#"{"payload":{"actions":[{"id":"approve"}],"v":1}}"#;
        let inner = extract_object(s, "payload");
        assert_eq!(inner, r#"{"actions":[{"id":"approve"}],"v":1}"#);
    }

    #[test]
    fn parse_authority_extracts_fields() {
        let json = r#"{
            "id": "auth-uuid",
            "tenant_id": "t-uuid",
            "subscription_id": "sub-uuid",
            "chain": "algorand_mainnet",
            "customer_wallet_address": "X",
            "cap_amount_minor": 120000000,
            "cap_period_seconds": 31536000,
            "per_cycle_amount_minor": 10000000,
            "asset": "USDC",
            "status": "pending",
            "cap_remaining_minor": 120000000,
            "cycles_pulled": 0,
            "cycles_failed": 0,
            "created_at": "2026-05-07T00:00:00Z"
        }"#;
        let a = parse_authority(json);
        assert_eq!(a.id, "auth-uuid");
        assert_eq!(a.chain, "algorand_mainnet");
        assert_eq!(a.cap_amount_minor, 120_000_000);
        assert_eq!(a.cap_remaining_minor, 120_000_000);
        assert_eq!(a.cycles_pulled, 0);
        assert_eq!(a.status, "pending");
    }

    #[test]
    fn parse_authority_array_handles_empty_and_one_and_many() {
        assert_eq!(parse_authority_array("[]").len(), 0);
        let one = r#"[{"id":"a1","status":"active"}]"#;
        let v = parse_authority_array(one);
        assert_eq!(v.len(), 1);
        assert_eq!(v[0].id, "a1");
        let two = r#"[{"id":"a1","status":"active"},{"id":"a2","status":"paused"}]"#;
        let v = parse_authority_array(two);
        assert_eq!(v.len(), 2);
        assert_eq!(v[1].id, "a2");
    }

    // -----------------------------------------------------------------------
    // Mock HTTP client + round-trip tests
    // -----------------------------------------------------------------------

    struct MockHttp {
        captured: RefCell<Vec<(String, String, String)>>, // (method, url, body)
        response: HttpResponse,
    }

    impl MockHttp {
        fn new(status: u16, body: &str) -> Self {
            Self {
                captured: RefCell::new(Vec::new()),
                response: HttpResponse {
                    status,
                    body: body.into(),
                },
            }
        }
        fn last(&self) -> Option<(String, String, String)> {
            self.captured.borrow().last().cloned()
        }
    }

    impl HttpClient for MockHttp {
        fn get(&self, url: &str) -> Result<HttpResponse, Error> {
            self.captured
                .borrow_mut()
                .push(("GET".into(), url.into(), String::new()));
            Ok(HttpResponse {
                status: self.response.status,
                body: self.response.body.clone(),
            })
        }
        fn post(
            &self,
            url: &str,
            body: &str,
            _headers: &[(&str, &str)],
        ) -> Result<HttpResponse, Error> {
            self.captured
                .borrow_mut()
                .push(("POST".into(), url.into(), body.into()));
            Ok(HttpResponse {
                status: self.response.status,
                body: self.response.body.clone(),
            })
        }
    }

    fn make_client() -> Client {
        Client::new(Config {
            api_base: "https://api.example.com".into(),
            api_key: "algv_k".into(),
            tenant_id: "t-uuid".into(),
            webhook_secret: "ws".into(),
        })
    }

    fn make_request() -> AuthorityCreateRequest {
        AuthorityCreateRequest {
            subscription_id: "sub-uuid".into(),
            chain: "algorand_mainnet".into(),
            customer_wallet_address: "X".into(),
            cap_amount_minor: 120_000_000,
            cap_period_seconds: 365 * 86400,
            per_cycle_amount_minor: 10_000_000,
            asset: String::new(),
            metadata: BTreeMap::new(),
        }
    }

    // -----------------------------------------------------------------------
    // Input validation — must short-circuit BEFORE the wire
    // -----------------------------------------------------------------------

    #[test]
    fn create_rejects_unsupported_chain() {
        let c = make_client();
        let http = MockHttp::new(200, "{}");
        let mut req = make_request();
        req.chain = "ethereum_mainnet".into();
        let result = c.create_recurring_authority(&http, &req);
        assert!(result.is_err());
        assert!(http.captured.borrow().is_empty(), "no HTTP call should be made");
    }

    #[test]
    fn create_rejects_period_below_one_day() {
        let c = make_client();
        let http = MockHttp::new(200, "{}");
        let mut req = make_request();
        req.cap_period_seconds = 3600;
        assert!(c.create_recurring_authority(&http, &req).is_err());
        assert!(http.captured.borrow().is_empty());
    }

    #[test]
    fn create_rejects_per_cycle_exceeds_cap() {
        let c = make_client();
        let http = MockHttp::new(200, "{}");
        let mut req = make_request();
        req.per_cycle_amount_minor = req.cap_amount_minor + 1;
        assert!(c.create_recurring_authority(&http, &req).is_err());
        assert!(http.captured.borrow().is_empty());
    }

    #[test]
    fn create_rejects_plaintext_http() {
        let mut config = Config {
            api_base: "http://example.com".into(),
            api_key: "k".into(),
            tenant_id: "t".into(),
            webhook_secret: "w".into(),
        };
        let c = Client::new(config.clone());
        let http = MockHttp::new(200, "{}");
        assert!(c.create_recurring_authority(&http, &make_request()).is_err());
        assert!(http.captured.borrow().is_empty());

        config.api_base = "https://example.com".into();
        let _ = Client::new(config);
    }

    #[test]
    fn create_rejects_oversize_wallet_address() {
        let c = make_client();
        let http = MockHttp::new(200, "{}");
        let mut req = make_request();
        req.customer_wallet_address = "A".repeat(129);
        let result = c.create_recurring_authority(&http, &req);
        assert!(result.is_err());
        assert!(http.captured.borrow().is_empty(), "no HTTP call should be made");
    }

    #[test]
    fn create_accepts_wallet_address_at_boundary() {
        // 128 chars is the exact limit — should not be rejected by the adapter
        // (gateway validates the actual address format).
        let c = make_client();
        let http = MockHttp::new(201, CREATE_RESPONSE);
        let mut req = make_request();
        req.customer_wallet_address = "A".repeat(128);
        // Should not return an InvalidInput error (may fail on mock response parse, not on validation)
        let result = c.create_recurring_authority(&http, &req);
        // The mock returns valid JSON, so we expect success here
        assert!(result.is_ok() || matches!(result, Err(Error::InvalidResponse(_))));
        // At minimum, HTTP was called (passed client-side validation)
        assert!(!http.captured.borrow().is_empty());
    }

    #[test]
    fn get_rejects_oversize_id() {
        let c = make_client();
        let http = MockHttp::new(200, "{}");
        let oversize: String = "a".repeat(100);
        assert!(c.get_authority(&http, &oversize).is_err());
        assert!(http.captured.borrow().is_empty());
    }

    #[test]
    fn list_rejects_oversize_limit_and_bad_status() {
        let c = make_client();
        let http = MockHttp::new(200, "[]");
        let opts_high = ListAuthoritiesOptions {
            limit: 500,
            ..Default::default()
        };
        assert!(c.list_authorities(&http, &opts_high).is_err());

        let opts_bad_status = ListAuthoritiesOptions {
            status: Some("bad-status!".into()),
            ..Default::default()
        };
        assert!(c.list_authorities(&http, &opts_bad_status).is_err());

        assert!(http.captured.borrow().is_empty());
    }

    #[test]
    fn manual_pull_rejects_non_positive_amount() {
        let c = make_client();
        let http = MockHttp::new(200, "{}");
        let req = PullRequest {
            authority_id: "a1".into(),
            amount_minor: -1,
            idempotency_key: String::new(),
        };
        assert!(c.manual_pull(&http, &req).is_err());
        assert!(http.captured.borrow().is_empty());
    }

    // -----------------------------------------------------------------------
    // Round-trip — POST / GET hits the right URL with the right body
    // -----------------------------------------------------------------------

    const CREATE_RESPONSE: &str = r#"{
      "authority": {
        "id": "auth-uuid",
        "tenant_id": "t-uuid",
        "subscription_id": "sub-uuid",
        "chain": "algorand_mainnet",
        "customer_wallet_address": "X",
        "cap_amount_minor": 120000000,
        "cap_period_seconds": 31536000,
        "per_cycle_amount_minor": 10000000,
        "asset": "USDC",
        "status": "pending",
        "cap_remaining_minor": 120000000,
        "cycles_pulled": 0,
        "cycles_failed": 0,
        "created_at": "2026-05-07T00:00:00Z"
      },
      "customer_signing_payload": {"version":"algorand_spending_cap_vault_v1","actions":[{"id":"deploy_vault"}]},
      "authorisation_url": ""
    }"#;

    #[test]
    fn create_recurring_authority_round_trip() {
        let c = make_client();
        let http = MockHttp::new(201, CREATE_RESPONSE);
        let resp = c.create_recurring_authority(&http, &make_request()).unwrap();

        assert_eq!(resp.authority.id, "auth-uuid");
        assert_eq!(resp.authority.status, "pending");
        assert_eq!(resp.authority.cap_amount_minor, 120_000_000);
        assert!(resp.customer_signing_payload_json.contains("algorand_spending_cap_vault_v1"));

        let (method, url, body) = http.last().unwrap();
        assert_eq!(method, "POST");
        assert_eq!(url, "https://api.example.com/v1/recurring/authorities");
        // Body has the right chain + atomic units + asset default
        assert!(body.contains("\"chain\":\"algorand_mainnet\""));
        assert!(body.contains("\"cap_amount_minor\":120000000"));
        assert!(body.contains("\"asset\":\"USDC\""));
    }

    #[test]
    fn list_authorities_get_with_query_string() {
        let c = make_client();
        let http = MockHttp::new(
            200,
            r#"[{"id":"a1","status":"active","chain":"base_mainnet","cycles_pulled":3}]"#,
        );
        let opts = ListAuthoritiesOptions {
            status: Some("active".into()),
            limit: 10,
            ..Default::default()
        };
        let list = c.list_authorities(&http, &opts).unwrap();
        assert_eq!(list.len(), 1);
        assert_eq!(list[0].id, "a1");
        assert_eq!(list[0].cycles_pulled, 3);

        let (method, url, body) = http.last().unwrap();
        assert_eq!(method, "GET");
        assert!(url.contains("limit=10"));
        assert!(url.contains("status=active"));
        assert_eq!(body, "");
    }

    #[test]
    fn revoke_authority_round_trip() {
        let c = make_client();
        let http = MockHttp::new(200, r#"{"id":"a1","status":"revoking"}"#);
        let a = c.revoke_authority(&http, "a1").unwrap();
        assert_eq!(a.status, "revoking");

        let (method, url, _body) = http.last().unwrap();
        assert_eq!(method, "POST");
        assert!(url.ends_with("/v1/recurring/authorities/a1/revoke"));
    }

    #[test]
    fn confirm_authority_carries_optional_first_cycle_due_at() {
        let c = make_client();
        let http = MockHttp::new(200, r#"{"id":"a1","status":"active"}"#);
        let req = ConfirmAuthorityRequest {
            on_chain_address: "app:12345".into(),
            first_cycle_due_at: "2026-06-07T00:00:00Z".into(),
        };
        let a = c.confirm_authority(&http, "a1", &req).unwrap();
        assert_eq!(a.status, "active");

        let (_, _, body) = http.last().unwrap();
        assert!(body.contains("\"on_chain_address\":\"app:12345\""));
        assert!(body.contains("\"first_cycle_due_at\":\"2026-06-07T00:00:00Z\""));
    }

    #[test]
    fn non_2xx_returns_error() {
        let c = make_client();
        let http = MockHttp::new(403, r#"{"error":"forbidden"}"#);
        let err = c.get_authority(&http, "a1").unwrap_err();
        assert!(format!("{err}").contains("403"));
    }
}
