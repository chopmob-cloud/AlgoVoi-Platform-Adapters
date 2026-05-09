package algovoi

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// ---------------------------------------------------------------------------
// IsRecurringNetwork / RecurringEventTypes
// ---------------------------------------------------------------------------

func TestIsRecurringNetworkCovers7MainnetsAndTestnets(t *testing.T) {
	wantTrue := []string{
		"algorand_mainnet", "algorand_testnet",
		"voi_mainnet", "voi_testnet",
		"base_mainnet", "base_sepolia",
		"tempo_mainnet", "tempo_testnet",
		"solana_mainnet", "solana_devnet",
		"hedera_mainnet", "hedera_testnet",
		"stellar_mainnet", "stellar_testnet",
	}
	for _, n := range wantTrue {
		if !IsRecurringNetwork(n) {
			t.Errorf("IsRecurringNetwork(%q) = false, want true", n)
		}
	}
	for _, n := range []string{"ethereum_mainnet", "polygon_mainnet", "", "lol"} {
		if IsRecurringNetwork(n) {
			t.Errorf("IsRecurringNetwork(%q) = true, want false", n)
		}
	}
}

func TestRecurringEventTypesContainsAllEight(t *testing.T) {
	got := RecurringEventTypes()
	if len(got) != 8 {
		t.Fatalf("RecurringEventTypes returned %d events, want 8", len(got))
	}
	wanted := []string{
		"recurring.authority_created",
		"recurring.authority_activated",
		"recurring.authority_paused",
		"recurring.authority_resumed",
		"recurring.authority_revoked",
		"recurring.authority_expired",
		"subscription.charged",
		"subscription.payment_failed",
	}
	set := make(map[string]bool)
	for _, e := range got {
		set[e] = true
	}
	for _, w := range wanted {
		if !set[w] {
			t.Errorf("missing event type %q", w)
		}
	}
}

// ---------------------------------------------------------------------------
// IsRecurringEvent
// ---------------------------------------------------------------------------

func TestIsRecurringEvent(t *testing.T) {
	cases := []struct {
		payload map[string]interface{}
		want    bool
	}{
		{map[string]interface{}{"event_type": "subscription.charged"}, true},
		{map[string]interface{}{"event_type": "recurring.authority_revoked"}, true},
		{map[string]interface{}{"type": "subscription.charged"}, true},
		{map[string]interface{}{"event_type": "payment.succeeded"}, false},
		{map[string]interface{}{}, false},
		{nil, false},
		{map[string]interface{}{"event_type": 12345}, false},
	}
	for i, c := range cases {
		if got := IsRecurringEvent(c.payload); got != c.want {
			t.Errorf("case %d: IsRecurringEvent(%v) = %v, want %v", i, c.payload, got, c.want)
		}
	}
}

// ---------------------------------------------------------------------------
// Input validation — no HTTP call should be made on bad inputs
// ---------------------------------------------------------------------------

func TestCreateRecurringAuthorityInputValidation(t *testing.T) {
	// HTTPClient with a transport that flags any HTTP call — these
	// validation cases must short-circuit BEFORE the wire.
	flagged := false
	c := New("https://example.com", "k", "t", "s")
	c.HTTPClient = &http.Client{
		Transport: roundTripFunc(func(*http.Request) (*http.Response, error) {
			flagged = true
			return &http.Response{StatusCode: 200, Body: io.NopCloser(strings.NewReader(`{}`))}, nil
		}),
	}

	cases := []struct {
		name string
		req  AuthorityCreateRequest
	}{
		{"unsupported chain", AuthorityCreateRequest{
			SubscriptionID: "sub", Chain: "ethereum_mainnet",
			CustomerWalletAddress: "abc",
			CapAmountMinor:        100, CapPeriodSeconds: 86400,
			PerCycleAmountMinor: 10,
		}},
		{"empty subscription id", AuthorityCreateRequest{
			Chain: "algorand_mainnet", CustomerWalletAddress: "abc",
			CapAmountMinor:   100,
			CapPeriodSeconds: 86400, PerCycleAmountMinor: 10,
		}},
		{"empty wallet", AuthorityCreateRequest{
			SubscriptionID: "sub", Chain: "algorand_mainnet",
			CapAmountMinor:   100,
			CapPeriodSeconds: 86400, PerCycleAmountMinor: 10,
		}},
		{"zero cap amount", AuthorityCreateRequest{
			SubscriptionID: "sub", Chain: "algorand_mainnet",
			CustomerWalletAddress: "abc",
			CapAmountMinor:        0, CapPeriodSeconds: 86400,
			PerCycleAmountMinor: 10,
		}},
		{"period below 1 day", AuthorityCreateRequest{
			SubscriptionID: "sub", Chain: "algorand_mainnet",
			CustomerWalletAddress: "abc",
			CapAmountMinor:        100, CapPeriodSeconds: 3600,
			PerCycleAmountMinor: 10,
		}},
		{"per-cycle exceeds cap", AuthorityCreateRequest{
			SubscriptionID: "sub", Chain: "base_mainnet",
			CustomerWalletAddress: "0xabc",
			CapAmountMinor:        10, CapPeriodSeconds: 86400 * 30,
			PerCycleAmountMinor: 100,
		}},
		{"wallet address too long", AuthorityCreateRequest{
			SubscriptionID:        "sub",
			Chain:                 "algorand_mainnet",
			CustomerWalletAddress: strings.Repeat("A", 129),
			CapAmountMinor:        100, CapPeriodSeconds: 86400,
			PerCycleAmountMinor: 10,
		}},
	}
	for _, c2 := range cases {
		flagged = false
		_, err := c.CreateRecurringAuthority(c2.req)
		if err == nil {
			t.Errorf("%s: expected error, got nil", c2.name)
		}
		if flagged {
			t.Errorf("%s: validation should short-circuit before HTTP, but HTTPClient was called", c2.name)
		}
	}
}

func TestGetAuthorityInputValidation(t *testing.T) {
	c := New("https://example.com", "k", "t", "s")
	if _, err := c.GetAuthority(""); err == nil {
		t.Errorf("GetAuthority(\"\") should fail")
	}
	if _, err := c.GetAuthority(strings.Repeat("a", 100)); err == nil {
		t.Errorf("GetAuthority(<oversize>) should fail")
	}
}

func TestListAuthoritiesInputValidation(t *testing.T) {
	c := New("https://example.com", "k", "t", "s")
	if _, err := c.ListAuthorities(ListAuthoritiesOptions{Limit: 500}); err == nil {
		t.Errorf("limit=500 should fail")
	}
	if _, err := c.ListAuthorities(ListAuthoritiesOptions{Status: "bad-status!"}); err == nil {
		t.Errorf("invalid status should fail")
	}
	if _, err := c.ListAuthorities(ListAuthoritiesOptions{Offset: -1}); err == nil {
		t.Errorf("negative offset should fail")
	}
}

func TestManualPullInputValidation(t *testing.T) {
	c := New("https://example.com", "k", "t", "s")
	if _, err := c.ManualPull(PullRequest{AmountMinor: 10}); err == nil {
		t.Errorf("missing authority_id should fail")
	}
	if _, err := c.ManualPull(PullRequest{AuthorityID: "id", AmountMinor: -1}); err == nil {
		t.Errorf("negative amount should fail")
	}
}

// ---------------------------------------------------------------------------
// HTTP round-trip — mocked gateway via httptest
// ---------------------------------------------------------------------------

func TestCreateRecurringAuthorityRoundTrip(t *testing.T) {
	srv := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" || r.URL.Path != "/v1/recurring/authorities" {
			t.Errorf("got %s %s, want POST /v1/recurring/authorities", r.Method, r.URL.Path)
		}
		if got := r.Header.Get("Authorization"); got != "Bearer algv_k" {
			t.Errorf("auth header = %q", got)
		}
		if got := r.Header.Get("X-Tenant-Id"); got != "t-uuid" {
			t.Errorf("tenant header = %q", got)
		}
		var body AuthorityCreateRequest
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Fatalf("decode request body: %v", err)
		}
		if body.Chain != "algorand_mainnet" {
			t.Errorf("chain = %q, want algorand_mainnet", body.Chain)
		}
		if body.CapAmountMinor != 120_000_000 {
			t.Errorf("cap_amount_minor = %d, want 120_000_000", body.CapAmountMinor)
		}
		if body.Asset != "USDC" {
			t.Errorf("asset default not applied: %q", body.Asset)
		}

		w.WriteHeader(http.StatusCreated)
		w.Write([]byte(`{
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
		  "customer_signing_payload": {
		    "version": "algorand_spending_cap_vault_v1",
		    "actions": [{"id": "deploy_vault"}]
		  },
		  "authorisation_url": null
		}`))
	}))
	defer srv.Close()

	c := New(srv.URL, "algv_k", "t-uuid", "ws")
	c.HTTPClient = srv.Client() // accept the test server's self-signed cert

	resp, err := c.CreateRecurringAuthority(AuthorityCreateRequest{
		SubscriptionID:        "sub-uuid",
		Chain:                 "algorand_mainnet",
		CustomerWalletAddress: "X",
		CapAmountMinor:        120_000_000,
		CapPeriodSeconds:      365 * 86400,
		PerCycleAmountMinor:   10_000_000,
	})
	if err != nil {
		t.Fatalf("CreateRecurringAuthority: %v", err)
	}
	if resp.Authority.ID != "auth-uuid" {
		t.Errorf("authority.id = %q, want auth-uuid", resp.Authority.ID)
	}
	if resp.Authority.Status != "pending" {
		t.Errorf("authority.status = %q, want pending", resp.Authority.Status)
	}
	if resp.CustomerSigningPayload["version"] != "algorand_spending_cap_vault_v1" {
		t.Errorf("template version not preserved")
	}
}

func TestListAuthoritiesRoundTrip(t *testing.T) {
	srv := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "GET" {
			t.Errorf("got %s, want GET", r.Method)
		}
		q := r.URL.Query()
		if q.Get("limit") != "10" {
			t.Errorf("limit = %q", q.Get("limit"))
		}
		if q.Get("status") != "active" {
			t.Errorf("status = %q", q.Get("status"))
		}
		w.Write([]byte(`[{"id":"a1","status":"active","chain":"base_mainnet","cycles_pulled":3}]`))
	}))
	defer srv.Close()

	c := New(srv.URL, "k", "t", "s")
	c.HTTPClient = srv.Client()

	list, err := c.ListAuthorities(ListAuthoritiesOptions{Status: "active", Limit: 10})
	if err != nil {
		t.Fatalf("ListAuthorities: %v", err)
	}
	if len(list) != 1 || list[0].ID != "a1" || list[0].CyclesPulled != 3 {
		t.Errorf("unexpected list response: %+v", list)
	}
}

func TestRevokeAuthorityRoundTrip(t *testing.T) {
	srv := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" || !strings.HasSuffix(r.URL.Path, "/revoke") {
			t.Errorf("got %s %s", r.Method, r.URL.Path)
		}
		w.Write([]byte(`{"id":"a1","status":"revoking"}`))
	}))
	defer srv.Close()

	c := New(srv.URL, "k", "t", "s")
	c.HTTPClient = srv.Client()

	a, err := c.RevokeAuthority("a1")
	if err != nil {
		t.Fatalf("RevokeAuthority: %v", err)
	}
	if a.Status != "revoking" {
		t.Errorf("status = %q, want revoking", a.Status)
	}
}

func TestNon2xxReturnsError(t *testing.T) {
	srv := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusForbidden)
		w.Write([]byte(`{"error":"forbidden"}`))
	}))
	defer srv.Close()

	c := New(srv.URL, "k", "t", "s")
	c.HTTPClient = srv.Client()

	_, err := c.GetAuthority("auth-uuid")
	if err == nil {
		t.Fatal("expected error on 403, got nil")
	}
	if !strings.Contains(err.Error(), "403") {
		t.Errorf("error should mention 403: %v", err)
	}
}

func TestPlaintextHTTPRefused(t *testing.T) {
	c := New("http://example.com", "k", "t", "s") // http, not https
	if _, err := c.GetAuthority("a1"); err == nil {
		t.Error("plaintext HTTP must be refused")
	}
	if _, err := c.CreateRecurringAuthority(AuthorityCreateRequest{
		SubscriptionID: "sub", Chain: "algorand_mainnet",
		CustomerWalletAddress: "X",
		CapAmountMinor:        100, CapPeriodSeconds: 86400 * 30,
		PerCycleAmountMinor: 10,
	}); err == nil {
		t.Error("plaintext HTTP must be refused (POST)")
	}
}

// roundTripFunc is a tiny http.RoundTripper adapter so we can mock
// transport without spinning up a server.
type roundTripFunc func(req *http.Request) (*http.Response, error)

func (f roundTripFunc) RoundTrip(req *http.Request) (*http.Response, error) { return f(req) }
