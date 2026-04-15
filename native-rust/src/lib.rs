//! # AlgoVoi Native Rust Payment Adapter
//!
//! Zero-dependency Rust library for the AlgoVoi payment platform.
//! Uses only the standard library — no crates required.
//!
//! ## Supports
//! - Hosted checkout (Algorand, VOI, Hedera) — redirect to AlgoVoi payment page
//! - Extension payment (Algorand, VOI) — in-page wallet flow via algosdk
//! - Webhook verification with HMAC-SHA256
//! - SSRF protection on checkout URL fetches
//! - Cancel-bypass prevention on hosted return
//!
//! ## Note on TLS
//! The stdlib `std::net::TcpStream` does not support TLS natively.
//! In production, pair this with `rustls` or `native-tls`, or use behind
//! a reverse proxy that terminates TLS (nginx, Caddy, etc.).
//! The API methods accept a generic `HttpClient` trait so you can plug in
//! any HTTP implementation.
//!
//! ## Quick start
//! ```rust,no_run
//! use algovoi::{Client, Config};
//!
//! let client = Client::new(Config {
//!     api_base: "https://api1.ilovechicken.co.uk".into(),
//!     api_key: "algv_...".into(),
//!     tenant_id: "uuid".into(),
//!     webhook_secret: "secret".into(),
//! });
//! ```
//!
//! AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
//! Licensed under the Business Source License 1.1 — see LICENSE for details.

use std::collections::HashMap;
use std::fmt;

// ── Constants ───────────────────────────────────────────────────────────

/// Adapter version.
pub const VERSION: &str = "1.1.0";

/// Hard cap on inbound webhook bodies (64 KB — AlgoVoi webhooks are <2 KB).
pub const MAX_WEBHOOK_BODY_BYTES: usize = 64 * 1024;

/// Maximum length for checkout tokens — guard against pathological input.
pub const MAX_TOKEN_LEN: usize = 200;

/// Maximum length for on-chain transaction IDs.
pub const MAX_TX_ID_LEN: usize = 200;

// ── Configuration ───────────────────────────────────────────────────────

/// Client configuration.
#[derive(Debug, Clone)]
pub struct Config {
    pub api_base: String,
    pub api_key: String,
    pub tenant_id: String,
    pub webhook_secret: String,
}

/// Refuse to make any outbound call over plaintext HTTP.
fn is_https(url: &str) -> bool {
    url.starts_with("https://")
}

/// Chain-specific node configuration.
#[derive(Debug, Clone)]
pub struct AlgodConfig {
    pub url: &'static str,
    pub asset_id: u64,
    pub ticker: &'static str,
    pub dec: u32,
}

/// Get the algod config for a given chain identifier.
pub fn algod_config(chain: &str) -> &'static AlgodConfig {
    match chain {
        "voi-mainnet" => &ALGOD_VOI,
        _ => &ALGOD_ALGORAND,
    }
}

static ALGOD_ALGORAND: AlgodConfig = AlgodConfig {
    url: "https://mainnet-api.algonode.cloud",
    asset_id: 31566704,
    ticker: "USDC",
    dec: 6,
};

static ALGOD_VOI: AlgodConfig = AlgodConfig {
    url: "https://mainnet-api.voi.nodely.io",
    asset_id: 302190,
    ticker: "aUSDC",
    dec: 6,
};

// ── Network validation ──────────────────────────────────────────────────

/// Valid networks for hosted checkout.
pub const HOSTED_NETWORKS: &[&str] = &[
    "algorand_mainnet",
    "voi_mainnet",
    "hedera_mainnet",
    "stellar_mainnet",
];

/// Valid networks for extension payment.
pub const EXT_NETWORKS: &[&str] = &["algorand_mainnet", "voi_mainnet"];

/// Check if a network is valid for hosted checkout.
pub fn is_valid_hosted_network(network: &str) -> bool {
    HOSTED_NETWORKS.contains(&network)
}

/// Check if a network is valid for extension payment.
pub fn is_valid_ext_network(network: &str) -> bool {
    EXT_NETWORKS.contains(&network)
}

// ── Error type ──────────────────────────────────────────────────────────

/// Errors returned by the AlgoVoi adapter.
#[derive(Debug)]
pub enum Error {
    /// HTTP or network error.
    Http(String),
    /// Invalid or missing data in API response.
    InvalidResponse(String),
    /// SSRF attempt blocked.
    SsrfBlocked,
    /// Webhook verification failed.
    WebhookInvalid(String),
    /// Invalid input parameters.
    InvalidInput(String),
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Error::Http(msg) => write!(f, "HTTP error: {msg}"),
            Error::InvalidResponse(msg) => write!(f, "Invalid response: {msg}"),
            Error::SsrfBlocked => write!(f, "SSRF blocked: checkout URL host mismatch"),
            Error::WebhookInvalid(msg) => write!(f, "Webhook invalid: {msg}"),
            Error::InvalidInput(msg) => write!(f, "Invalid input: {msg}"),
        }
    }
}

impl std::error::Error for Error {}

// ── HTTP abstraction ────────────────────────────────────────────────────

/// HTTP response from the adapter's HTTP client.
#[derive(Debug)]
pub struct HttpResponse {
    pub status: u16,
    pub body: String,
}

/// Trait for HTTP clients. Implement this to plug in your preferred HTTP library.
///
/// The stdlib doesn't include TLS support, so in production you'll want to
/// implement this with `reqwest`, `ureq`, `hyper`, or similar.
pub trait HttpClient {
    /// Send a GET request.
    fn get(&self, url: &str) -> Result<HttpResponse, Error>;

    /// Send a POST request with JSON body and optional auth headers.
    fn post(&self, url: &str, json_body: &str, headers: &[(&str, &str)]) -> Result<HttpResponse, Error>;
}

// ── Payment Link ────────────────────────────────────────────────────────

/// Response from creating a payment link.
#[derive(Debug, Clone)]
pub struct PaymentLink {
    pub checkout_url: String,
    pub id: String,
    pub chain: String,
    pub amount_microunits: u64,
    pub asset_id: u64,
}

/// Result of a hosted checkout initiation.
#[derive(Debug, Clone)]
pub struct HostedResult {
    pub checkout_url: String,
    pub token: String,
    pub chain: String,
    pub amount_microunits: u64,
}

/// All data needed to render the extension payment JS UI.
#[derive(Debug, Clone)]
pub struct ExtensionData {
    pub token: String,
    pub receiver: String,
    pub memo: String,
    pub amount_mu: u64,
    pub asset_id: u64,
    pub algod_url: String,
    pub ticker: String,
    pub amount_display: String,
    pub chain: String,
    pub checkout_url: String,
}

// ── Client ──────────────────────────────────────────────────────────────

/// The AlgoVoi payment adapter client.
#[derive(Debug, Clone)]
pub struct Client {
    config: Config,
}

impl Client {
    /// Create a new client.
    pub fn new(config: Config) -> Self {
        Self { config }
    }

    /// Create a payment link via the AlgoVoi API.
    pub fn create_payment_link(
        &self,
        http: &dyn HttpClient,
        amount: f64,
        currency: &str,
        label: &str,
        network: &str,
        redirect_url: Option<&str>,
    ) -> Result<PaymentLink, Error> {
        // Defence-in-depth: reject obviously bad amounts before the
        // gateway call. NaN / Inf / non-positive values would either
        // produce invalid JSON (NaN, inf) or silently flow through to
        // the gateway. Fail closed locally.
        if !amount.is_finite() || amount <= 0.0 {
            return Err(Error::InvalidInput(
                "amount must be a positive finite number".into(),
            ));
        }
        // Refuse to send the API key over plaintext HTTP. This is the
        // highest-impact scheme guard — Authorization: Bearer +
        // X-Tenant-Id are sent on every payment-link creation.
        if !is_https(&self.config.api_base) {
            return Err(Error::InvalidInput(
                "api_base must use https scheme".into(),
            ));
        }
        // Validate redirect_url scheme — only https is allowed. Blocks
        // SSRF schemes (file://, gopher://, javascript:) and prevents
        // checkout tokens from travelling over plaintext.
        if let Some(rurl) = redirect_url {
            if !rurl.starts_with("https://") {
                return Err(Error::InvalidInput(
                    "redirect_url must be an https URL".into(),
                ));
            }
            // Quick host check: an https URL must have something after
            // "https://" and before the next "/".
            let host = rurl.trim_start_matches("https://")
                .split('/').next().unwrap_or("");
            if host.is_empty() {
                return Err(Error::InvalidInput(
                    "redirect_url must include a host".into(),
                ));
            }
        }

        let mut payload = format!(
            r#"{{"amount":{},"currency":"{}","label":"{}","preferred_network":"{}""#,
            round2(amount),
            currency.to_uppercase(),
            json_escape(label),
            json_escape(network),
        );
        if let Some(rurl) = redirect_url {
            payload.push_str(&format!(
                r#","redirect_url":"{}","expires_in_seconds":3600"#,
                json_escape(rurl)
            ));
        }
        payload.push('}');

        let url = format!("{}/v1/payment-links", self.config.api_base.trim_end_matches('/'));
        let resp = http.post(
            &url,
            &payload,
            &[
                ("Content-Type", "application/json"),
                ("Authorization", &format!("Bearer {}", self.config.api_key)),
                ("X-Tenant-Id", &self.config.tenant_id),
            ],
        )?;

        if resp.status < 200 || resp.status >= 300 {
            return Err(Error::Http(format!("HTTP {}: {}", resp.status, resp.body)));
        }

        parse_payment_link(&resp.body)
    }

    /// Start a hosted checkout. Returns the redirect URL and token.
    pub fn hosted_checkout(
        &self,
        http: &dyn HttpClient,
        amount: f64,
        currency: &str,
        label: &str,
        network: &str,
        redirect_url: &str,
    ) -> Result<HostedResult, Error> {
        let net = if is_valid_hosted_network(network) { network } else { "algorand_mainnet" };
        let link = self.create_payment_link(http, amount, currency, label, net, Some(redirect_url))?;
        Ok(HostedResult {
            token: extract_token(&link.checkout_url),
            checkout_url: link.checkout_url,
            chain: link.chain,
            amount_microunits: link.amount_microunits,
        })
    }

    /// Verify that a hosted checkout was actually paid.
    ///
    /// **CRITICAL:** Without this check, a customer can cancel payment
    /// and still appear to have paid (cancel-bypass vulnerability).
    pub fn verify_hosted_return(&self, http: &dyn HttpClient, token: &str) -> Result<bool, Error> {
        if token.is_empty() {
            return Ok(false);
        }
        if token.len() > MAX_TOKEN_LEN {
            return Ok(false);
        }
        // Refuse to send the checkout token over plaintext HTTP.
        if !is_https(&self.config.api_base) {
            return Ok(false);
        }

        let url = format!(
            "{}/checkout/{}",
            self.config.api_base.trim_end_matches('/'),
            url_encode(token),
        );

        let resp = http.get(&url)?;
        if resp.status != 200 {
            return Ok(false);
        }

        let status = extract_json_string(&resp.body, "status");
        Ok(matches!(status.as_str(), "paid" | "completed" | "confirmed"))
    }

    /// Prepare data for the extension (in-page) wallet payment flow.
    pub fn extension_checkout(
        &self,
        http: &dyn HttpClient,
        amount: f64,
        currency: &str,
        label: &str,
        network: &str,
    ) -> Result<ExtensionData, Error> {
        let net = if is_valid_ext_network(network) { network } else { "algorand_mainnet" };
        let link = self.create_payment_link(http, amount, currency, label, net, None)?;

        let chain = if link.chain.is_empty() { "algorand-mainnet" } else { &link.chain };
        let algod = algod_config(chain);

        let scraped = self.scrape_checkout(http, &link.checkout_url)?;
        let token = extract_token(&link.checkout_url);
        let divisor = 10f64.powi(algod.dec as i32);

        Ok(ExtensionData {
            token,
            receiver: scraped.0,
            memo: scraped.1,
            amount_mu: link.amount_microunits,
            asset_id: algod.asset_id,
            algod_url: algod.url.to_string(),
            ticker: algod.ticker.to_string(),
            amount_display: format!("{:.2}", link.amount_microunits as f64 / divisor),
            chain: chain.to_string(),
            checkout_url: link.checkout_url,
        })
    }

    /// Verify an extension payment transaction with the AlgoVoi API.
    pub fn verify_extension_payment(
        &self,
        http: &dyn HttpClient,
        token: &str,
        tx_id: &str,
    ) -> Result<HashMap<String, serde_value::Value>, Error> {
        // Length-cap BOTH inputs — token was previously only checked
        // for emptiness, allowing arbitrary-length payloads to be
        // URL-encoded into the request path.
        if token.is_empty() || tx_id.is_empty()
                || token.len() > MAX_TOKEN_LEN
                || tx_id.len() > MAX_TX_ID_LEN {
            return Err(Error::InvalidInput("invalid token or tx_id".into()));
        }
        // Refuse to send the checkout token over plaintext HTTP.
        if !is_https(&self.config.api_base) {
            return Err(Error::InvalidInput(
                "api_base must use https scheme".into(),
            ));
        }

        let url = format!(
            "{}/checkout/{}/verify",
            self.config.api_base.trim_end_matches('/'),
            url_encode(token),
        );
        let body = format!(r#"{{"tx_id":"{}"}}"#, json_escape(tx_id));
        let resp = http.post(&url, &body, &[("Content-Type", "application/json")])?;

        // Return raw JSON as a string map for flexibility
        let mut result = HashMap::new();
        result.insert("_body".into(), serde_value::Value::String(resp.body));
        result.insert("_status".into(), serde_value::Value::U16(resp.status));
        Ok(result)
    }

    /// Verify and parse an incoming webhook request.
    ///
    /// Returns the body as `String` on success, or `Error::WebhookInvalid`
    /// on any failure (empty secret, empty signature, oversized body,
    /// signature mismatch). The body is NOT JSON-parsed — caller is
    /// expected to plug in their preferred JSON deserialiser.
    ///
    /// **SECURITY NOTE — replay protection:** This method does NOT
    /// dedupe replays. The HMAC carries no timestamp; callers MUST
    /// track processed identifiers in their persistence layer.
    pub fn verify_webhook(&self, raw_body: &[u8], signature: &str) -> Result<String, Error> {
        if self.config.webhook_secret.is_empty() {
            return Err(Error::WebhookInvalid("webhook secret not configured".into()));
        }
        if signature.is_empty() {
            return Err(Error::WebhookInvalid("empty signature".into()));
        }
        if raw_body.len() > MAX_WEBHOOK_BODY_BYTES {
            return Err(Error::WebhookInvalid(format!(
                "body exceeds {} bytes",
                MAX_WEBHOOK_BODY_BYTES
            )));
        }

        let expected = hmac_sha256_b64(self.config.webhook_secret.as_bytes(), raw_body);
        if !constant_time_eq(expected.as_bytes(), signature.as_bytes()) {
            return Err(Error::WebhookInvalid("invalid signature".into()));
        }

        Ok(String::from_utf8_lossy(raw_body).to_string())
    }

    // ── Internal ────────────────────────────────────────────────────────

    fn scrape_checkout(&self, http: &dyn HttpClient, checkout_url: &str) -> Result<(String, String), Error> {
        // Refuse to scrape over plaintext.
        if !is_https(checkout_url) {
            return Err(Error::SsrfBlocked);
        }
        // SSRF guard: host AND port must match api_base. Comparing
        // hostnames only lets a different port on the same hostname
        // slip through.
        let api_origin = parse_host_port(&self.config.api_base);
        let checkout_origin = parse_host_port(checkout_url);
        if api_origin.is_empty() || checkout_origin != api_origin {
            return Err(Error::SsrfBlocked);
        }

        let resp = http.get(checkout_url)?;
        let html = &resp.body;

        let receiver = extract_regex(html, r#"<div[^>]+id=["']addr["'][^>]*>([A-Z2-7]{58})<"#)
            .ok_or_else(|| Error::InvalidResponse("receiver not found".into()))?;
        let memo = extract_regex(html, r#"<div[^>]+id=["']memo["'][^>]*>(algovoi:[^<]+)<"#)
            .map(|s| s.trim().to_string())
            .ok_or_else(|| Error::InvalidResponse("memo not found".into()))?;

        Ok((receiver, memo))
    }
}

// ── HTML Helpers ────────────────────────────────────────────────────────

/// Render chain selector radio buttons as HTML.
///
/// `mode` should be `"hosted"` (4 chains: Algorand, VOI, Hedera, Stellar) or
/// `"extension"` (2 chains: Algorand, VOI — the AlgoVoi browser extension signs
/// those two, while Hedera/Stellar buyers use hosted checkout with their own
/// wallet such as HashPack, Freighter, or LOBSTR).
pub fn render_chain_selector(field_name: &str, mode: &str) -> String {
    let mut chains = vec![
        ("algorand_mainnet", "Algorand", "USDC", "#3b82f6"),
        ("voi_mainnet", "VOI", "aUSDC", "#8b5cf6"),
    ];
    if mode == "hosted" {
        chains.push(("hedera_mainnet", "Hedera", "USDC", "#00a9a5"));
        chains.push(("stellar_mainnet", "Stellar", "USDC", "#7C63D0"));
    }

    let mut html = String::from(
        r#"<div style="margin:.5rem 0;font-size:12px;color:#6b7280;font-weight:600;text-transform:uppercase;letter-spacing:.04em;">Select network</div>"#,
    );
    html.push_str(r#"<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:.5rem;">"#);

    for (i, (value, label, ticker, colour)) in chains.iter().enumerate() {
        let checked = if i == 0 { " checked" } else { "" };
        html.push_str(&format!(
            r#"<label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:13px;"><input type="radio" name="{}" value="{}"{} style="accent-color:{};"> {} &mdash; {}</label>"#,
            html_escape(field_name), html_escape(value), checked, colour,
            html_escape(label), html_escape(ticker),
        ));
    }
    html.push_str("</div>");
    html
}

// ── Pure-stdlib crypto ──────────────────────────────────────────────────

/// HMAC-SHA256, base64-encoded. Uses only stdlib.
fn hmac_sha256_b64(key: &[u8], message: &[u8]) -> String {
    // HMAC: H((K' ^ opad) || H((K' ^ ipad) || message))
    const BLOCK_SIZE: usize = 64;

    let mut k = [0u8; BLOCK_SIZE];
    if key.len() > BLOCK_SIZE {
        let hash = sha256(key);
        k[..32].copy_from_slice(&hash);
    } else {
        k[..key.len()].copy_from_slice(key);
    }

    let mut ipad = [0x36u8; BLOCK_SIZE];
    let mut opad = [0x5cu8; BLOCK_SIZE];
    for i in 0..BLOCK_SIZE {
        ipad[i] ^= k[i];
        opad[i] ^= k[i];
    }

    // inner hash: H(ipad || message)
    let mut inner_input = Vec::with_capacity(BLOCK_SIZE + message.len());
    inner_input.extend_from_slice(&ipad);
    inner_input.extend_from_slice(message);
    let inner_hash = sha256(&inner_input);

    // outer hash: H(opad || inner_hash)
    let mut outer_input = Vec::with_capacity(BLOCK_SIZE + 32);
    outer_input.extend_from_slice(&opad);
    outer_input.extend_from_slice(&inner_hash);
    let result = sha256(&outer_input);

    base64_encode(&result)
}

/// SHA-256 — pure Rust implementation using only stdlib.
fn sha256(data: &[u8]) -> [u8; 32] {
    const K: [u32; 64] = [
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
        0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
        0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
        0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
        0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
        0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
        0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
    ];

    let mut h: [u32; 8] = [
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
        0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
    ];

    // Pre-processing: pad message
    let bit_len = (data.len() as u64) * 8;
    let mut msg = data.to_vec();
    msg.push(0x80);
    while (msg.len() % 64) != 56 {
        msg.push(0);
    }
    msg.extend_from_slice(&bit_len.to_be_bytes());

    // Process each 512-bit block
    for chunk in msg.chunks(64) {
        let mut w = [0u32; 64];
        for i in 0..16 {
            w[i] = u32::from_be_bytes([chunk[4 * i], chunk[4 * i + 1], chunk[4 * i + 2], chunk[4 * i + 3]]);
        }
        for i in 16..64 {
            let s0 = w[i - 15].rotate_right(7) ^ w[i - 15].rotate_right(18) ^ (w[i - 15] >> 3);
            let s1 = w[i - 2].rotate_right(17) ^ w[i - 2].rotate_right(19) ^ (w[i - 2] >> 10);
            w[i] = w[i - 16].wrapping_add(s0).wrapping_add(w[i - 7]).wrapping_add(s1);
        }

        let [mut a, mut b, mut c, mut d, mut e, mut f, mut g, mut hh] = h;

        for i in 0..64 {
            let s1 = e.rotate_right(6) ^ e.rotate_right(11) ^ e.rotate_right(25);
            let ch = (e & f) ^ ((!e) & g);
            let t1 = hh.wrapping_add(s1).wrapping_add(ch).wrapping_add(K[i]).wrapping_add(w[i]);
            let s0 = a.rotate_right(2) ^ a.rotate_right(13) ^ a.rotate_right(22);
            let maj = (a & b) ^ (a & c) ^ (b & c);
            let t2 = s0.wrapping_add(maj);
            hh = g; g = f; f = e; e = d.wrapping_add(t1);
            d = c; c = b; b = a; a = t1.wrapping_add(t2);
        }

        h[0] = h[0].wrapping_add(a); h[1] = h[1].wrapping_add(b);
        h[2] = h[2].wrapping_add(c); h[3] = h[3].wrapping_add(d);
        h[4] = h[4].wrapping_add(e); h[5] = h[5].wrapping_add(f);
        h[6] = h[6].wrapping_add(g); h[7] = h[7].wrapping_add(hh);
    }

    let mut result = [0u8; 32];
    for (i, val) in h.iter().enumerate() {
        result[4 * i..4 * i + 4].copy_from_slice(&val.to_be_bytes());
    }
    result
}

/// Base64 encode (standard alphabet, with padding).
fn base64_encode(data: &[u8]) -> String {
    const CHARS: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut result = String::with_capacity((data.len() + 2) / 3 * 4);
    for chunk in data.chunks(3) {
        let b0 = chunk[0] as u32;
        let b1 = if chunk.len() > 1 { chunk[1] as u32 } else { 0 };
        let b2 = if chunk.len() > 2 { chunk[2] as u32 } else { 0 };
        let n = (b0 << 16) | (b1 << 8) | b2;
        result.push(CHARS[((n >> 18) & 0x3f) as usize] as char);
        result.push(CHARS[((n >> 12) & 0x3f) as usize] as char);
        if chunk.len() > 1 { result.push(CHARS[((n >> 6) & 0x3f) as usize] as char); } else { result.push('='); }
        if chunk.len() > 2 { result.push(CHARS[(n & 0x3f) as usize] as char); } else { result.push('='); }
    }
    result
}

/// Constant-time byte comparison.
fn constant_time_eq(a: &[u8], b: &[u8]) -> bool {
    if a.len() != b.len() {
        return false;
    }
    let mut diff = 0u8;
    for (x, y) in a.iter().zip(b.iter()) {
        diff |= x ^ y;
    }
    diff == 0
}

// ── String helpers ──────────────────────────────────────────────────────

fn round2(v: f64) -> f64 {
    (v * 100.0).round() / 100.0
}

fn json_escape(s: &str) -> String {
    // RFC 8259 §7 — escape ALL of U+0000..U+001F, plus '"' and '\'.
    let mut out = String::with_capacity(s.len());
    for c in s.chars() {
        match c {
            '\\' => out.push_str("\\\\"),
            '"' => out.push_str("\\\""),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\x08' => out.push_str("\\b"),
            '\x0c' => out.push_str("\\f"),
            // Remaining control chars use the \u00XX form.
            c if (c as u32) < 0x20 => {
                out.push_str(&format!("\\u{:04x}", c as u32));
            }
            c => out.push(c),
        }
    }
    out
}

/// HTML-escape user-controlled text. Local implementation so the crate
/// stays zero-dependency. The previous version called `html::escape`
/// which referenced a non-existent module and broke the build.
fn html_escape(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for c in s.chars() {
        match c {
            '&' => out.push_str("&amp;"),
            '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"),
            '"' => out.push_str("&quot;"),
            '\'' => out.push_str("&#39;"),
            _ => out.push(c),
        }
    }
    out
}

fn url_encode(s: &str) -> String {
    let mut result = String::new();
    for b in s.bytes() {
        match b {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => {
                result.push(b as char);
            }
            _ => {
                result.push_str(&format!("%{:02X}", b));
            }
        }
    }
    result
}

fn parse_host(url: &str) -> String {
    // Simple host extraction without external URL parser
    let after_scheme = url.split("://").nth(1).unwrap_or("");
    let host_port = after_scheme.split('/').next().unwrap_or("");
    let host = host_port.split(':').next().unwrap_or("");
    host.to_lowercase()
}

/// Returns "host:port" (or "host" if port is implicit) so the SSRF guard
/// rejects same-host different-port traffic too.
fn parse_host_port(url: &str) -> String {
    let after_scheme = url.split("://").nth(1).unwrap_or("");
    after_scheme.split('/').next().unwrap_or("").to_lowercase()
}

fn extract_token(checkout_url: &str) -> String {
    if let Some(pos) = checkout_url.rfind("/checkout/") {
        let token = &checkout_url[pos + 10..];
        if !token.is_empty() && token.chars().all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_') {
            return token.to_string();
        }
    }
    String::new()
}

fn extract_json_string(json: &str, key: &str) -> String {
    let pattern = format!(r#""{}":"#, key);
    if let Some(pos) = json.find(&pattern) {
        let rest = &json[pos + pattern.len()..];
        if rest.starts_with('"') {
            if let Some(end) = rest[1..].find('"') {
                return rest[1..=end].to_string();
            }
        }
    }
    String::new()
}

fn extract_regex(html: &str, _pattern: &str) -> Option<String> {
    // Simplified regex-free extraction for the two known patterns
    if _pattern.contains("addr") {
        // Look for <div...id="addr"...>ALGO_ADDRESS<
        if let Some(pos) = html.find("id=\"addr\"") .or_else(|| html.find("id='addr'")) {
            let rest = &html[pos..];
            if let Some(gt) = rest.find('>') {
                let after = &rest[gt + 1..];
                if after.len() >= 58 {
                    let candidate = &after[..58];
                    if candidate.chars().all(|c| c.is_ascii_uppercase() || c == '2' || c == '3' || c == '4' || c == '5' || c == '6' || c == '7') {
                        return Some(candidate.to_string());
                    }
                }
            }
        }
    } else if _pattern.contains("memo") {
        // Look for <div...id="memo"...>algovoi:...<
        if let Some(pos) = html.find("id=\"memo\"").or_else(|| html.find("id='memo'")) {
            let rest = &html[pos..];
            if let Some(gt) = rest.find('>') {
                let after = &rest[gt + 1..];
                if after.starts_with("algovoi:") {
                    if let Some(end) = after.find('<') {
                        return Some(after[..end].trim().to_string());
                    }
                }
            }
        }
    }
    None
}

fn parse_payment_link(json: &str) -> Result<PaymentLink, Error> {
    Ok(PaymentLink {
        checkout_url: extract_json_string(json, "checkout_url"),
        id: extract_json_string(json, "id"),
        chain: extract_json_string(json, "chain"),
        amount_microunits: extract_json_string(json, "amount_microunits")
            .parse()
            .unwrap_or(0),
        asset_id: extract_json_string(json, "asset_id")
            .parse()
            .unwrap_or(0),
    })
}

// ── Serde-free value type ───────────────────────────────────────────────

/// Minimal value type for webhook payloads (avoids serde dependency).
pub mod serde_value {
    #[derive(Debug, Clone)]
    pub enum Value {
        String(String),
        U16(u16),
    }
}

// ── Tests ───────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sha256_empty() {
        let hash = sha256(b"");
        let hex: String = hash.iter().map(|b| format!("{:02x}", b)).collect();
        assert_eq!(hex, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
    }

    #[test]
    fn test_sha256_hello() {
        let hash = sha256(b"hello");
        let hex: String = hash.iter().map(|b| format!("{:02x}", b)).collect();
        assert_eq!(hex, "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824");
    }

    #[test]
    fn test_hmac_sha256() {
        let result = hmac_sha256_b64(b"secret", b"message");
        assert_eq!(result, "i19IcCmVwVmMVz2x4hhmqbgl1KeU0WnXBgoDYFeWNgs=");
    }

    #[test]
    fn test_constant_time_eq() {
        assert!(constant_time_eq(b"abc", b"abc"));
        assert!(!constant_time_eq(b"abc", b"abd"));
        assert!(!constant_time_eq(b"abc", b"ab"));
    }

    #[test]
    fn test_extract_token() {
        assert_eq!(extract_token("https://api.example.com/checkout/abc-123_XYZ"), "abc-123_XYZ");
        assert_eq!(extract_token("https://api.example.com/other/path"), "");
    }

    #[test]
    fn test_parse_host() {
        assert_eq!(parse_host("https://api.example.com/path"), "api.example.com");
        assert_eq!(parse_host("https://api.example.com:8080/path"), "api.example.com");
    }

    #[test]
    fn test_network_validation() {
        assert!(is_valid_hosted_network("algorand_mainnet"));
        assert!(is_valid_hosted_network("hedera_mainnet"));
        assert!(is_valid_hosted_network("stellar_mainnet"));
        assert!(!is_valid_hosted_network("invalid"));
        assert!(is_valid_ext_network("voi_mainnet"));
        assert!(!is_valid_ext_network("hedera_mainnet"));
        assert!(!is_valid_ext_network("stellar_mainnet"));
    }

    #[test]
    fn test_base64_encode() {
        assert_eq!(base64_encode(b"hello"), "aGVsbG8=");
        assert_eq!(base64_encode(b""), "");
        assert_eq!(base64_encode(b"a"), "YQ==");
    }

    #[test]
    fn test_webhook_empty_secret_rejected() {
        let client = Client::new(Config {
            api_base: "https://api.example.com".into(),
            api_key: String::new(),
            tenant_id: String::new(),
            webhook_secret: String::new(),
        });
        assert!(client.verify_webhook(b"body", "sig").is_err());
    }

    #[test]
    fn test_render_chain_selector() {
        let html = render_chain_selector("network", "hosted");
        assert!(html.contains("algorand_mainnet"));
        assert!(html.contains("voi_mainnet"));
        assert!(html.contains("hedera_mainnet"));
        assert!(html.contains("stellar_mainnet"));

        let html2 = render_chain_selector("network", "extension");
        assert!(html2.contains("algorand_mainnet"));
        assert!(html2.contains("voi_mainnet"));
        assert!(!html2.contains("hedera_mainnet"));
        assert!(!html2.contains("stellar_mainnet"));
    }

    // ── v1.1.0 hardening regression tests ──────────────────────────────

    /// Stub HttpClient that returns success for any request without
    /// touching the network. Only used by tests that should NEVER reach
    /// it because of a local guard.
    struct UnreachableClient;
    impl HttpClient for UnreachableClient {
        fn get(&self, _url: &str) -> Result<HttpResponse, Error> {
            panic!("guard failed — UnreachableClient::get reached")
        }
        fn post(&self, _url: &str, _body: &str, _h: &[(&str, &str)]) -> Result<HttpResponse, Error> {
            panic!("guard failed — UnreachableClient::post reached")
        }
    }

    fn fresh_client(api_base: &str) -> Client {
        Client::new(Config {
            api_base: api_base.into(),
            api_key: "k".into(),
            tenant_id: "t".into(),
            webhook_secret: "test_secret".into(),
        })
    }

    #[test]
    fn html_escape_compiles_and_works() {
        // Regression — previous version called the non-existent `html::escape`.
        assert_eq!(html_escape("<script>"), "&lt;script&gt;");
        assert_eq!(html_escape("a&b"), "a&amp;b");
        assert_eq!(html_escape("\"x\""), "&quot;x&quot;");
        assert_eq!(html_escape("'x'"), "&#39;x&#39;");
    }

    #[test]
    fn render_chain_selector_escapes_field_name() {
        let h = render_chain_selector("<script>alert(1)</script>", "hosted");
        assert!(!h.contains("<script>alert(1)</script>"));
        assert!(h.contains("&lt;script&gt;"));
    }

    #[test]
    fn webhook_rejects_empty_signature() {
        let c = fresh_client("https://x");
        assert!(c.verify_webhook(b"body", "").is_err());
    }

    #[test]
    fn webhook_rejects_oversized_body() {
        let c = fresh_client("https://x");
        let huge = vec![b'A'; MAX_WEBHOOK_BODY_BYTES + 1];
        assert!(c.verify_webhook(&huge, "anysig").is_err());
    }

    #[test]
    fn create_payment_link_rejects_non_finite_amount() {
        let c = fresh_client("https://x");
        let http = UnreachableClient;
        // Local guard MUST trip — UnreachableClient panics if reached.
        for amt in [f64::NAN, f64::INFINITY, f64::NEG_INFINITY, 0.0, -1.0] {
            let r = c.create_payment_link(&http, amt, "USD", "L", "algorand_mainnet", None);
            assert!(matches!(r, Err(Error::InvalidInput(_))),
                "amount {} not rejected locally", amt);
        }
    }

    #[test]
    fn create_payment_link_rejects_non_https_redirect() {
        let c = fresh_client("https://x");
        let http = UnreachableClient;
        for u in ["http://x.test", "file:///etc/passwd", "javascript:alert(1)", "gopher://x"] {
            let r = c.create_payment_link(&http, 1.0, "USD", "L", "algorand_mainnet", Some(u));
            assert!(matches!(r, Err(Error::InvalidInput(_))),
                "redirect {} not rejected locally", u);
        }
    }

    #[test]
    fn create_payment_link_refuses_plaintext_api_base() {
        let c = fresh_client("http://insecure");
        let http = UnreachableClient;
        let r = c.create_payment_link(&http, 1.0, "USD", "L", "algorand_mainnet", None);
        assert!(matches!(r, Err(Error::InvalidInput(_))));
    }

    #[test]
    fn verify_hosted_return_refuses_plaintext_api_base() {
        let c = fresh_client("http://insecure");
        let http = UnreachableClient;
        // Returns Ok(false) without touching the network.
        assert_eq!(c.verify_hosted_return(&http, "tok").unwrap(), false);
    }

    #[test]
    fn verify_hosted_return_token_length_cap() {
        let c = fresh_client("https://x");
        let http = UnreachableClient;
        let long = "A".repeat(MAX_TOKEN_LEN + 1);
        assert_eq!(c.verify_hosted_return(&http, &long).unwrap(), false);
    }

    #[test]
    fn verify_extension_payment_token_length_cap() {
        let c = fresh_client("https://x");
        let http = UnreachableClient;
        let long = "A".repeat(MAX_TOKEN_LEN + 1);
        assert!(c.verify_extension_payment(&http, &long, "TX_OK").is_err());
    }

    #[test]
    fn verify_extension_payment_refuses_plaintext() {
        let c = fresh_client("http://insecure");
        let http = UnreachableClient;
        assert!(c.verify_extension_payment(&http, "tok", "TX_OK").is_err());
    }

    #[test]
    fn parse_host_port_includes_port() {
        assert_eq!(parse_host_port("https://api.example.com/p"), "api.example.com");
        assert_eq!(parse_host_port("https://api.example.com:9999/p"), "api.example.com:9999");
        assert!(parse_host_port("api.example.com:9999/p").is_empty(),
            "missing scheme should produce empty origin");
    }

    #[test]
    fn json_escape_handles_control_chars() {
        // RFC 8259 §7 — control chars must be escaped.
        let out = json_escape("\x01\x02\x08\x0b");
        assert!(out.contains("\\u0001"));
        assert!(out.contains("\\u0002"));
        assert!(out.contains("\\b"));        // 0x08
        assert!(out.contains("\\u000b"));    // 0x0b (vertical tab)
    }
}
