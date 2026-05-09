package algovoi

// Tier 2 — Standing-Authority Recurring Payments
//
// Tier 2 is "customer signs ONCE, AlgoVoi auto-pulls per cycle".
// Tier 1 (hosted/extension checkout) is "customer clicks pay on every
// invoice".
//
// The merchant lifecycle:
//
//   1. Tenant creates a Tier 1 subscription (POST /v1/subscriptions —
//      out of scope of this adapter; use the dashboard or call the API
//      directly).
//   2. Tenant calls CreateRecurringAuthority — gateway returns
//      `customer_signing_payload`, a chain-specific template.
//   3. Tenant's frontend hands the template to the customer's wallet
//      (Pera / Defly / MetaMask / Phantom / HashPack / Freighter / etc.)
//      which constructs + signs the on-chain authorisation.
//   4. Once the on-chain transaction lands, tenant calls
//      ConfirmAuthority(authorityID, onChainAddress, ...) to transition
//      the row to status='active'.
//   5. AlgoVoi's cycle reaper auto-pulls per cap_period_seconds. Each
//      pull emits subscription.charged / subscription.payment_failed
//      webhooks the tenant handles via VerifyWebhook + IsRecurringEvent.
//   6. To stop: RevokeAuthority — gateway constructs the revocation
//      transaction. To pause/resume without on-chain action: Pause/Resume.
//
// Wire formats are locked at *_v1 — see Recurr/<chain>/README.md for
// per-chain wallet-side flows.

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
)

// ---------------------------------------------------------------------------
// Tier 2 constants
// ---------------------------------------------------------------------------

// MaxRecurringBodyBytes caps the size of recurring API responses. List
// responses are bounded by gateway's limit=200; defence-in-depth.
const MaxRecurringBodyBytes = 16 * 1024

// MaxUUIDLen guards URL-path parameters against pathological lengths.
const MaxUUIDLen = 36

// recurringNetworks enumerates every chain that has a real Tier 2
// provider (Sprints 1-5 in content/recurring_payments_tier2_design.md):
// 7 mainnets + 7 testnets.
var recurringNetworks = map[string]bool{
	"algorand_mainnet": true, "algorand_testnet": true,
	"voi_mainnet": true, "voi_testnet": true,
	"base_mainnet": true, "base_sepolia": true,
	"tempo_mainnet": true, "tempo_testnet": true,
	"solana_mainnet": true, "solana_devnet": true,
	"hedera_mainnet": true, "hedera_testnet": true,
	"stellar_mainnet": true, "stellar_testnet": true,
}

// recurringEventTypes enumerates the Tier 2 webhook events emitted in
// addition to Tier 1's payment.* events.
var recurringEventTypes = map[string]bool{
	"recurring.authority_created":   true,
	"recurring.authority_activated": true,
	"recurring.authority_paused":    true,
	"recurring.authority_resumed":   true,
	"recurring.authority_revoked":   true,
	"recurring.authority_expired":   true,
	"subscription.charged":          true,
	"subscription.payment_failed":   true,
}

// IsRecurringNetwork reports whether `network` is a Tier 2 chain id.
func IsRecurringNetwork(network string) bool { return recurringNetworks[network] }

// RecurringEventTypes returns a sorted list of Tier 2 webhook event types.
func RecurringEventTypes() []string {
	out := make([]string, 0, len(recurringEventTypes))
	for k := range recurringEventTypes {
		out = append(out, k)
	}
	return out
}

// ---------------------------------------------------------------------------
// Tier 2 request / response types
// ---------------------------------------------------------------------------

// AuthorityCreateRequest is the input to CreateRecurringAuthority.
type AuthorityCreateRequest struct {
	SubscriptionID        string                 `json:"subscription_id"`
	Chain                 string                 `json:"chain"`
	CustomerWalletAddress string                 `json:"customer_wallet_address"`
	CapAmountMinor        int64                  `json:"cap_amount_minor"`
	CapPeriodSeconds      int64                  `json:"cap_period_seconds"`
	PerCycleAmountMinor   int64                  `json:"per_cycle_amount_minor"`
	Asset                 string                 `json:"asset,omitempty"` // defaults to "USDC"
	Metadata              map[string]interface{} `json:"metadata,omitempty"`
}

// Authority is the server-recorded standing-authority row.
type Authority struct {
	ID                    string                 `json:"id"`
	TenantID              string                 `json:"tenant_id"`
	SubscriptionID        string                 `json:"subscription_id"`
	Chain                 string                 `json:"chain"`
	CustomerWalletAddress string                 `json:"customer_wallet_address"`
	CapAmountMinor        int64                  `json:"cap_amount_minor"`
	CapPeriodSeconds      int64                  `json:"cap_period_seconds"`
	PerCycleAmountMinor   int64                  `json:"per_cycle_amount_minor"`
	Asset                 string                 `json:"asset"`
	Status                string                 `json:"status"`
	OnChainAddress        string                 `json:"on_chain_address,omitempty"`
	CapRemainingMinor     int64                  `json:"cap_remaining_minor"`
	CyclesPulled          int                    `json:"cycles_pulled"`
	CyclesFailed          int                    `json:"cycles_failed"`
	CreatedAt             string                 `json:"created_at"`
	ActivatedAt           string                 `json:"activated_at,omitempty"`
	RevokedAt             string                 `json:"revoked_at,omitempty"`
	LastError             string                 `json:"last_error,omitempty"`
	Metadata              map[string]interface{} `json:"metadata,omitempty"`
}

// AuthorityCreateResponse is what CreateRecurringAuthority returns.
//
// CustomerSigningPayload is intentionally untyped (`map[string]interface{}`)
// because its structure is chain-specific — the caller hands it to the
// per-chain wallet UI without inspecting it. See Recurr/<chain>/README.md
// in this repository for the per-chain shape.
type AuthorityCreateResponse struct {
	Authority              Authority              `json:"authority"`
	CustomerSigningPayload map[string]interface{} `json:"customer_signing_payload"`
	AuthorisationURL       string                 `json:"authorisation_url,omitempty"`
}

// ---------------------------------------------------------------------------
// CreateRecurringAuthority
// ---------------------------------------------------------------------------

// CreateRecurringAuthority creates a Tier 2 standing authority for an
// existing subscription. The returned response.CustomerSigningPayload
// is the chain-specific template the customer's wallet signs.
//
// `req.Asset` defaults to "USDC" if empty.
//
// Validation rules enforced locally before the round-trip:
//   - chain must be a known Tier 2 network (use IsRecurringNetwork)
//   - cap_amount_minor and per_cycle_amount_minor must be positive
//   - cap_period_seconds must be >= 86400 (1 day)
//   - per_cycle_amount_minor must be <= cap_amount_minor
//
// Stellar uses 7-decimal precision for USDC; every other chain uses 6.
// Pass amounts in chain-native atomic units (120 USDC = 120_000_000 on
// most chains, 1_200_000_000 on Stellar).
func (c *Client) CreateRecurringAuthority(req AuthorityCreateRequest) (*AuthorityCreateResponse, error) {
	if !recurringNetworks[req.Chain] {
		return nil, fmt.Errorf("algovoi: unsupported recurring chain %q", req.Chain)
	}
	if req.SubscriptionID == "" || len(req.SubscriptionID) > MaxUUIDLen {
		return nil, fmt.Errorf("algovoi: invalid subscription_id")
	}
	if req.CustomerWalletAddress == "" {
		return nil, fmt.Errorf("algovoi: customer_wallet_address required")
	}
	if len(req.CustomerWalletAddress) > 128 {
		return nil, fmt.Errorf("algovoi: customer_wallet_address too long (max 128 chars)")
	}
	if req.CapAmountMinor <= 0 || req.PerCycleAmountMinor <= 0 || req.CapPeriodSeconds <= 0 {
		return nil, fmt.Errorf("algovoi: amounts and period must be positive")
	}
	if req.CapPeriodSeconds < 86400 {
		return nil, fmt.Errorf("algovoi: cap_period_seconds must be >= 86400 (1 day)")
	}
	if req.PerCycleAmountMinor > req.CapAmountMinor {
		return nil, fmt.Errorf("algovoi: per_cycle_amount_minor cannot exceed cap_amount_minor")
	}

	// Default asset
	if req.Asset == "" {
		req.Asset = "USDC"
	}

	body, err := c.recurringPost("/v1/recurring/authorities", req)
	if err != nil {
		return nil, err
	}
	var resp AuthorityCreateResponse
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, fmt.Errorf("algovoi: invalid create-authority response: %w", err)
	}
	return &resp, nil
}

// ---------------------------------------------------------------------------
// GetAuthority / ListAuthorities
// ---------------------------------------------------------------------------

// GetAuthority fetches a recurring authority by id.
func (c *Client) GetAuthority(authorityID string) (*Authority, error) {
	if authorityID == "" || len(authorityID) > MaxUUIDLen {
		return nil, fmt.Errorf("algovoi: invalid authority_id")
	}
	body, err := c.recurringGet("/v1/recurring/authorities/" + url.PathEscape(authorityID))
	if err != nil {
		return nil, err
	}
	var a Authority
	if err := json.Unmarshal(body, &a); err != nil {
		return nil, fmt.Errorf("algovoi: invalid get-authority response: %w", err)
	}
	return &a, nil
}

// ListAuthoritiesOptions filters the ListAuthorities query.
type ListAuthoritiesOptions struct {
	SubscriptionID string // optional
	Status         string // optional: pending / active / paused / revoking / revoked / expired
	Limit          int    // default 50, max 200
	Offset         int    // default 0
}

// ListAuthorities lists recurring authorities for this tenant.
func (c *Client) ListAuthorities(opts ListAuthoritiesOptions) ([]Authority, error) {
	if opts.Limit == 0 {
		opts.Limit = 50
	}
	if opts.Limit < 1 || opts.Limit > 200 || opts.Offset < 0 {
		return nil, fmt.Errorf("algovoi: invalid limit/offset")
	}

	q := url.Values{}
	q.Set("limit", strconv.Itoa(opts.Limit))
	q.Set("offset", strconv.Itoa(opts.Offset))
	if opts.SubscriptionID != "" {
		if len(opts.SubscriptionID) > MaxUUIDLen {
			return nil, fmt.Errorf("algovoi: invalid subscription_id")
		}
		q.Set("subscription_id", opts.SubscriptionID)
	}
	if opts.Status != "" {
		if len(opts.Status) > 32 || !isAlnumUnderscore(opts.Status) {
			return nil, fmt.Errorf("algovoi: invalid status filter")
		}
		q.Set("status", opts.Status)
	}

	body, err := c.recurringGet("/v1/recurring/authorities?" + q.Encode())
	if err != nil {
		return nil, err
	}
	var list []Authority
	if err := json.Unmarshal(body, &list); err != nil {
		return nil, fmt.Errorf("algovoi: invalid list-authorities response: %w", err)
	}
	return list, nil
}

// ---------------------------------------------------------------------------
// ConfirmAuthority — mark active after on-chain landing
// ---------------------------------------------------------------------------

// ConfirmAuthorityRequest carries the on-chain handle and optional
// first cycle due-at.
type ConfirmAuthorityRequest struct {
	OnChainAddress  string `json:"on_chain_address"`
	FirstCycleDueAt string `json:"first_cycle_due_at,omitempty"`
}

// ConfirmAuthority marks a pending authority active. on-chain-address
// format depends on the chain:
//
//	Algorand / VOI : "app:<application_id>"
//	EVM            : "0x<tx_hash>"
//	Solana         : "<base58 tx signature>"
//	Hedera         : "<account_id>@<seconds>.<nanos>" (Hedera tx id)
//	Stellar        : "<64-char hex tx hash>"
//
// Most tenants don't need to call this — the AlgoVoi widget does it
// automatically. Surfaced here for self-hosted wallet UIs.
func (c *Client) ConfirmAuthority(authorityID string, req ConfirmAuthorityRequest) (*Authority, error) {
	if authorityID == "" || len(authorityID) > MaxUUIDLen {
		return nil, fmt.Errorf("algovoi: invalid authority_id")
	}
	if req.OnChainAddress == "" || len(req.OnChainAddress) > 200 {
		return nil, fmt.Errorf("algovoi: invalid on_chain_address")
	}
	if req.FirstCycleDueAt != "" && len(req.FirstCycleDueAt) > 64 {
		return nil, fmt.Errorf("algovoi: invalid first_cycle_due_at")
	}

	path := "/v1/recurring/authorities/" + url.PathEscape(authorityID) + "/confirm"
	body, err := c.recurringPost(path, req)
	if err != nil {
		return nil, err
	}
	var a Authority
	if err := json.Unmarshal(body, &a); err != nil {
		return nil, fmt.Errorf("algovoi: invalid confirm-authority response: %w", err)
	}
	return &a, nil
}

// ---------------------------------------------------------------------------
// RevokeAuthority / PauseAuthority / ResumeAuthority
// ---------------------------------------------------------------------------

// RevokeAuthority revokes an active authority. Gateway constructs the
// chain-specific revocation transaction; the customer's wallet signs it.
// Authority transitions to status='revoking' until on-chain landing,
// then 'revoked'.
func (c *Client) RevokeAuthority(authorityID string) (*Authority, error) {
	if authorityID == "" || len(authorityID) > MaxUUIDLen {
		return nil, fmt.Errorf("algovoi: invalid authority_id")
	}
	path := "/v1/recurring/authorities/" + url.PathEscape(authorityID) + "/revoke"
	body, err := c.recurringPost(path, struct{}{})
	if err != nil {
		return nil, err
	}
	var a Authority
	if err := json.Unmarshal(body, &a); err != nil {
		return nil, fmt.Errorf("algovoi: invalid revoke-authority response: %w", err)
	}
	return &a, nil
}

// PauseAuthority pauses an active authority — no on-chain action.
// Stops cycle pulls until ResumeAuthority is called.
func (c *Client) PauseAuthority(authorityID string) (*Authority, error) {
	if authorityID == "" || len(authorityID) > MaxUUIDLen {
		return nil, fmt.Errorf("algovoi: invalid authority_id")
	}
	path := "/v1/recurring/authorities/" + url.PathEscape(authorityID) + "/pause"
	body, err := c.recurringPost(path, struct{}{})
	if err != nil {
		return nil, err
	}
	var a Authority
	if err := json.Unmarshal(body, &a); err != nil {
		return nil, fmt.Errorf("algovoi: invalid pause-authority response: %w", err)
	}
	return &a, nil
}

// ResumeAuthorityRequest carries an optional next-cycle due-at.
type ResumeAuthorityRequest struct {
	NextCycleDueAt string `json:"next_cycle_due_at,omitempty"`
}

// ResumeAuthority resumes a paused authority. Pass NextCycleDueAt to
// delay the first post-resume pull; otherwise pulls resume immediately
// on the existing schedule.
func (c *Client) ResumeAuthority(authorityID string, req ResumeAuthorityRequest) (*Authority, error) {
	if authorityID == "" || len(authorityID) > MaxUUIDLen {
		return nil, fmt.Errorf("algovoi: invalid authority_id")
	}
	if req.NextCycleDueAt != "" && len(req.NextCycleDueAt) > 64 {
		return nil, fmt.Errorf("algovoi: invalid next_cycle_due_at")
	}
	path := "/v1/recurring/authorities/" + url.PathEscape(authorityID) + "/resume"
	body, err := c.recurringPost(path, req)
	if err != nil {
		return nil, err
	}
	var a Authority
	if err := json.Unmarshal(body, &a); err != nil {
		return nil, fmt.Errorf("algovoi: invalid resume-authority response: %w", err)
	}
	return &a, nil
}

// ---------------------------------------------------------------------------
// ManualPull — tenant-initiated catch-up / proration
// ---------------------------------------------------------------------------

// PullRequest carries a manual pull. Most pulls fire automatically via
// the cycle reaper; only use this for proration or dunning catch-ups.
type PullRequest struct {
	AuthorityID    string `json:"authority_id"`
	AmountMinor    int64  `json:"amount_minor"`
	IdempotencyKey string `json:"idempotency_key,omitempty"`
}

// ManualPull triggers a one-off pull. AmountMinor must be <=
// per_cycle_amount_minor of the authority. Returns the updated
// authority row.
func (c *Client) ManualPull(req PullRequest) (*Authority, error) {
	if req.AuthorityID == "" || len(req.AuthorityID) > MaxUUIDLen {
		return nil, fmt.Errorf("algovoi: invalid authority_id")
	}
	if req.AmountMinor <= 0 {
		return nil, fmt.Errorf("algovoi: amount_minor must be positive")
	}
	if req.IdempotencyKey != "" && len(req.IdempotencyKey) > 128 {
		return nil, fmt.Errorf("algovoi: idempotency_key too long")
	}
	body, err := c.recurringPost("/v1/recurring/pulls", req)
	if err != nil {
		return nil, err
	}
	var a Authority
	if err := json.Unmarshal(body, &a); err != nil {
		return nil, fmt.Errorf("algovoi: invalid manual-pull response: %w", err)
	}
	return &a, nil
}

// ---------------------------------------------------------------------------
// Webhook helper
// ---------------------------------------------------------------------------

// IsRecurringEvent reports whether the parsed webhook payload is a Tier 2
// event (subscription.charged, recurring.authority_*, etc.).
//
// Use this to fork your handler:
//
//	payload, err := av.VerifyWebhook(body, sig)
//	if err != nil { http.Error(w, "Unauthorized", 401); return }
//	if algovoi.IsRecurringEvent(payload) {
//	    handleRecurring(payload)   // subscription.charged, etc.
//	} else {
//	    handleOneShot(payload)     // payment.succeeded, etc.
//	}
func IsRecurringEvent(payload map[string]interface{}) bool {
	if payload == nil {
		return false
	}
	for _, key := range [...]string{"event_type", "type"} {
		if v, ok := payload[key]; ok {
			if s, ok := v.(string); ok && recurringEventTypes[s] {
				return true
			}
		}
	}
	return false
}

// ---------------------------------------------------------------------------
// Internal — HTTP helpers (mirror algovoi.go's post() pattern)
// ---------------------------------------------------------------------------

// recurringPost POSTs JSON to a recurring endpoint with auth + size cap.
func (c *Client) recurringPost(path string, body interface{}) ([]byte, error) {
	rawURL := c.APIBase + path
	if !isHTTPS(rawURL) {
		return nil, fmt.Errorf("algovoi: refusing to POST authenticated request over plaintext")
	}
	payload, err := json.Marshal(body)
	if err != nil {
		return nil, err
	}
	req, err := http.NewRequest("POST", rawURL, bytes.NewReader(payload))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+c.APIKey)
	req.Header.Set("X-Tenant-Id", c.TenantID)
	return c.doRecurring(req)
}

// recurringGet GETs a recurring endpoint with auth + size cap.
func (c *Client) recurringGet(path string) ([]byte, error) {
	rawURL := c.APIBase + path
	if !isHTTPS(rawURL) {
		return nil, fmt.Errorf("algovoi: refusing to GET authenticated request over plaintext")
	}
	req, err := http.NewRequest("GET", rawURL, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+c.APIKey)
	req.Header.Set("X-Tenant-Id", c.TenantID)
	return c.doRecurring(req)
}

// doRecurring runs the request and reads up to MaxRecurringBodyBytes.
// Returns an error on non-2xx with the response body in the message
// (truncated to 1 KB to keep error logs sane).
func (c *Client) doRecurring(req *http.Request) ([]byte, error) {
	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(io.LimitReader(resp.Body, int64(MaxRecurringBodyBytes)+1))
	if err != nil {
		return nil, err
	}
	if int64(len(body)) > int64(MaxRecurringBodyBytes) {
		return nil, fmt.Errorf("algovoi: response exceeds %d bytes", MaxRecurringBodyBytes)
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		// Truncate body in error to keep log lines small
		snippet := string(body)
		if len(snippet) > 1024 {
			snippet = snippet[:1024] + "..."
		}
		return nil, fmt.Errorf("algovoi: HTTP %d: %s", resp.StatusCode, snippet)
	}
	return body, nil
}

// isAlnumUnderscore reports whether s contains only [A-Za-z0-9_].
// Used for status filter sanity-check before query-string encoding.
func isAlnumUnderscore(s string) bool {
	for _, r := range s {
		if !((r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') ||
			(r >= '0' && r <= '9') || r == '_') {
			return false
		}
	}
	return s != ""
}
