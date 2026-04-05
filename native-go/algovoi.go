// Package algovoi provides a zero-dependency Go client for the AlgoVoi payment platform.
//
// Supports:
//   - Hosted checkout (Algorand, VOI, Hedera) — redirect to AlgoVoi payment page
//   - Extension payment (Algorand, VOI) — in-page wallet flow via algosdk
//   - Webhook verification with HMAC
//   - SSRF protection on checkout URL fetches
//   - Cancel-bypass prevention on hosted return
//
// No third-party dependencies — uses only the Go standard library.
//
// Version: 1.0.0
package algovoi

import (
	"bytes"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"html"
	"io"
	"net/http"
	"net/url"
	"regexp"
	"strings"
	"time"
)

// AlgodConfig holds node configuration for a specific chain.
type AlgodConfig struct {
	URL     string
	AssetID int
	Ticker  string
	Dec     int
}

var algodConfigs = map[string]AlgodConfig{
	"algorand-mainnet": {URL: "https://mainnet-api.algonode.cloud", AssetID: 31566704, Ticker: "USDC", Dec: 6},
	"voi-mainnet":      {URL: "https://mainnet-api.voi.nodely.io", AssetID: 302190, Ticker: "aUSDC", Dec: 6},
}

var hostedNetworks = map[string]bool{
	"algorand_mainnet": true,
	"voi_mainnet":      true,
	"hedera_mainnet":   true,
	"stellar_mainnet":  true,
}
var extNetworks = map[string]bool{"algorand_mainnet": true, "voi_mainnet": true}

var tokenRegex = regexp.MustCompile(`/checkout/([A-Za-z0-9_-]+)$`)
var addrRegex = regexp.MustCompile(`<div[^>]+id=["']addr["'][^>]*>([A-Z2-7]{58})<`)
var memoRegex = regexp.MustCompile(`<div[^>]+id=["']memo["'][^>]*>(algovoi:[^<]+)<`)

// Client is the AlgoVoi payment adapter.
type Client struct {
	APIBase       string
	APIKey        string
	TenantID      string
	WebhookSecret string
	HTTPClient    *http.Client
}

// New creates a new AlgoVoi client with sensible defaults.
func New(apiBase, apiKey, tenantID, webhookSecret string) *Client {
	return &Client{
		APIBase:       strings.TrimRight(apiBase, "/"),
		APIKey:        apiKey,
		TenantID:      tenantID,
		WebhookSecret: webhookSecret,
		HTTPClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

// ── Payment Link ────────────────────────────────────────────────────────

// PaymentLinkResponse is the API response from creating a payment link.
type PaymentLinkResponse struct {
	CheckoutURL      string `json:"checkout_url"`
	ID               string `json:"id"`
	Chain            string `json:"chain"`
	AmountMicrounits int    `json:"amount_microunits"`
	AssetID          int    `json:"asset_id"`
}

// CreatePaymentLink creates a payment link via the AlgoVoi API.
func (c *Client) CreatePaymentLink(amount float64, currency, label, network, redirectURL string) (*PaymentLinkResponse, error) {
	payload := map[string]interface{}{
		"amount":            amount,
		"currency":          strings.ToUpper(currency),
		"label":             label,
		"preferred_network": network,
	}
	if redirectURL != "" {
		payload["redirect_url"] = redirectURL
		payload["expires_in_seconds"] = 3600
	}

	body, err := c.post(c.APIBase+"/v1/payment-links", payload, true)
	if err != nil {
		return nil, err
	}

	var resp PaymentLinkResponse
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, fmt.Errorf("algovoi: invalid response: %w", err)
	}
	if resp.CheckoutURL == "" {
		return nil, fmt.Errorf("algovoi: empty checkout_url in response")
	}
	return &resp, nil
}

// ExtractToken extracts the short token from a checkout URL.
func ExtractToken(checkoutURL string) string {
	m := tokenRegex.FindStringSubmatch(checkoutURL)
	if len(m) < 2 {
		return ""
	}
	return m[1]
}

// ── Hosted Checkout ─────────────────────────────────────────────────────

// HostedResult contains the data from a hosted checkout initiation.
type HostedResult struct {
	CheckoutURL      string
	Token            string
	Chain            string
	AmountMicrounits int
}

// HostedCheckout starts a hosted checkout. Returns the redirect URL and token.
func (c *Client) HostedCheckout(amount float64, currency, label, network, redirectURL string) (*HostedResult, error) {
	if !hostedNetworks[network] {
		network = "algorand_mainnet"
	}

	link, err := c.CreatePaymentLink(amount, currency, label, network, redirectURL)
	if err != nil {
		return nil, err
	}

	return &HostedResult{
		CheckoutURL:      link.CheckoutURL,
		Token:            ExtractToken(link.CheckoutURL),
		Chain:            link.Chain,
		AmountMicrounits: link.AmountMicrounits,
	}, nil
}

// VerifyHostedReturn checks whether a hosted checkout was actually paid.
// Call this when the customer returns from the hosted checkout page.
//
// CRITICAL: Without this check, a customer can cancel payment and still
// appear to have paid (cancel-bypass vulnerability).
func (c *Client) VerifyHostedReturn(token string) (bool, error) {
	if token == "" {
		return false, nil
	}

	req, err := http.NewRequest("GET", c.APIBase+"/checkout/"+url.PathEscape(token), nil)
	if err != nil {
		return false, err
	}

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return false, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return false, nil
	}

	body, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return false, err
	}

	var data struct {
		Status string `json:"status"`
	}
	if err := json.Unmarshal(body, &data); err != nil {
		return false, nil
	}

	switch data.Status {
	case "paid", "completed", "confirmed":
		return true, nil
	default:
		return false, nil
	}
}

// ── Extension Payment ───────────────────────────────────────────────────

// ExtensionData contains all variables needed to render the JS payment UI.
type ExtensionData struct {
	Token         string
	Receiver      string
	Memo          string
	AmountMU      int
	AssetID       int
	AlgodURL      string
	Ticker        string
	AmountDisplay string
	Chain         string
	CheckoutURL   string
}

// ExtensionCheckout prepares data for the in-page wallet payment flow.
func (c *Client) ExtensionCheckout(amount float64, currency, label, network string) (*ExtensionData, error) {
	if !extNetworks[network] {
		network = "algorand_mainnet"
	}

	link, err := c.CreatePaymentLink(amount, currency, label, network, "")
	if err != nil {
		return nil, err
	}

	chain := link.Chain
	if chain == "" {
		chain = "algorand-mainnet"
	}
	amountMU := link.AmountMicrounits
	algod, ok := algodConfigs[chain]
	if !ok {
		algod = algodConfigs["algorand-mainnet"]
	}

	scraped, err := c.scrapeCheckout(link.CheckoutURL)
	if err != nil {
		return nil, err
	}

	token := ExtractToken(link.CheckoutURL)
	divisor := 1.0
	for i := 0; i < algod.Dec; i++ {
		divisor *= 10
	}

	return &ExtensionData{
		Token:         token,
		Receiver:      scraped.Receiver,
		Memo:          scraped.Memo,
		AmountMU:      amountMU,
		AssetID:       algod.AssetID,
		AlgodURL:      algod.URL,
		Ticker:        algod.Ticker,
		AmountDisplay: fmt.Sprintf("%.2f", float64(amountMU)/divisor),
		Chain:         chain,
		CheckoutURL:   link.CheckoutURL,
	}, nil
}

// VerifyExtensionPayment verifies an extension payment transaction with the AlgoVoi API.
func (c *Client) VerifyExtensionPayment(token, txID string) (map[string]interface{}, error) {
	if token == "" || txID == "" || len(txID) > 200 {
		return map[string]interface{}{"error": "Invalid parameters"}, fmt.Errorf("invalid parameters")
	}

	verifyURL := c.APIBase + "/checkout/" + url.PathEscape(token) + "/verify"
	body, err := c.postRaw(verifyURL, map[string]interface{}{"tx_id": txID})
	if err != nil {
		return nil, err
	}

	var result map[string]interface{}
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, err
	}
	return result, nil
}

// ── Webhook ─────────────────────────────────────────────────────────────

// VerifyWebhook verifies and parses an incoming webhook request.
// Returns nil if the secret is empty or the signature is invalid.
func (c *Client) VerifyWebhook(rawBody []byte, signature string) (map[string]interface{}, error) {
	if c.WebhookSecret == "" {
		return nil, fmt.Errorf("webhook secret not configured")
	}

	mac := hmac.New(sha256.New, []byte(c.WebhookSecret))
	mac.Write(rawBody)
	expected := base64.StdEncoding.EncodeToString(mac.Sum(nil))

	if !hmac.Equal([]byte(expected), []byte(signature)) {
		return nil, fmt.Errorf("invalid signature")
	}

	var payload map[string]interface{}
	if err := json.Unmarshal(rawBody, &payload); err != nil {
		return nil, fmt.Errorf("invalid JSON: %w", err)
	}
	return payload, nil
}

// ── HTTP Handler Helpers ────────────────────────────────────────────────

// WebhookHandler returns an http.HandlerFunc that verifies and processes webhooks.
// The callback receives the parsed payload on success.
func (c *Client) WebhookHandler(callback func(payload map[string]interface{})) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}

		body, err := io.ReadAll(io.LimitReader(r.Body, 1<<20))
		if err != nil {
			http.Error(w, "Bad request", http.StatusBadRequest)
			return
		}

		signature := r.Header.Get("X-AlgoVoi-Signature")
		payload, err := c.VerifyWebhook(body, signature)
		if err != nil {
			http.Error(w, "Unauthorized", http.StatusUnauthorized)
			return
		}

		callback(payload)
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"ok":true}`))
	}
}

// ── HTML Helpers ────────────────────────────────────────────────────────

// ChainInfo represents a chain option for the selector.
type ChainInfo struct {
	Value  string
	Label  string
	Ticker string
	Colour string
}

// RenderChainSelector renders chain selector radio buttons as HTML.
// mode should be "hosted" (4 chains: Algorand, VOI, Hedera, Stellar) or
// "extension" (2 chains: Algorand, VOI — the AlgoVoi browser extension signs
// those two; Hedera/Stellar buyers use hosted checkout with their own wallet).
func RenderChainSelector(fieldName, mode string) string {
	chains := []ChainInfo{
		{Value: "algorand_mainnet", Label: "Algorand", Ticker: "USDC", Colour: "#3b82f6"},
		{Value: "voi_mainnet", Label: "VOI", Ticker: "aUSDC", Colour: "#8b5cf6"},
	}
	if mode == "hosted" {
		chains = append(chains, ChainInfo{Value: "hedera_mainnet", Label: "Hedera", Ticker: "USDC", Colour: "#00a9a5"})
		chains = append(chains, ChainInfo{Value: "stellar_mainnet", Label: "Stellar", Ticker: "USDC", Colour: "#7C63D0"})
	}

	var sb strings.Builder
	sb.WriteString(`<div style="margin:.5rem 0;font-size:12px;color:#6b7280;font-weight:600;text-transform:uppercase;letter-spacing:.04em;">Select network</div>`)
	sb.WriteString(`<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:.5rem;">`)
	for i, c := range chains {
		checked := ""
		if i == 0 {
			checked = " checked"
		}
		sb.WriteString(fmt.Sprintf(
			`<label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:13px;">`+
				`<input type="radio" name="%s" value="%s"%s style="accent-color:%s;">`+
				` %s &mdash; %s</label>`,
			html.EscapeString(fieldName), html.EscapeString(c.Value), checked, c.Colour,
			html.EscapeString(c.Label), html.EscapeString(c.Ticker),
		))
	}
	sb.WriteString(`</div>`)
	return sb.String()
}

// IsValidHostedNetwork returns true if the network is valid for hosted checkout.
func IsValidHostedNetwork(network string) bool { return hostedNetworks[network] }

// IsValidExtNetwork returns true if the network is valid for extension payment.
func IsValidExtNetwork(network string) bool { return extNetworks[network] }

// ── Internal ────────────────────────────────────────────────────────────

func (c *Client) post(url string, data map[string]interface{}, auth bool) ([]byte, error) {
	payload, err := json.Marshal(data)
	if err != nil {
		return nil, err
	}

	req, err := http.NewRequest("POST", url, bytes.NewReader(payload))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	if auth {
		req.Header.Set("Authorization", "Bearer "+c.APIKey)
		req.Header.Set("X-Tenant-Id", c.TenantID)
	}

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return nil, err
	}

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, fmt.Errorf("algovoi: HTTP %d: %s", resp.StatusCode, string(body))
	}
	return body, nil
}

func (c *Client) postRaw(rawURL string, data map[string]interface{}) ([]byte, error) {
	payload, err := json.Marshal(data)
	if err != nil {
		return nil, err
	}

	req, err := http.NewRequest("POST", rawURL, bytes.NewReader(payload))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	return io.ReadAll(io.LimitReader(resp.Body, 1<<20))
}

type scrapeResult struct {
	Receiver string
	Memo     string
}

func (c *Client) scrapeCheckout(checkoutURL string) (*scrapeResult, error) {
	// SSRF guard: host must match API base
	apiHost := mustParseHost(c.APIBase)
	checkoutHost := mustParseHost(checkoutURL)
	if apiHost == "" || checkoutHost != apiHost {
		return nil, fmt.Errorf("algovoi: checkout URL host mismatch (SSRF blocked)")
	}

	client := &http.Client{Timeout: 15 * time.Second}
	resp, err := client.Get(checkoutURL)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return nil, err
	}
	htmlStr := string(body)

	var receiver, memo string
	if m := addrRegex.FindStringSubmatch(htmlStr); len(m) >= 2 {
		receiver = m[1]
	}
	if m := memoRegex.FindStringSubmatch(htmlStr); len(m) >= 2 {
		memo = strings.TrimSpace(m[1])
	}

	if receiver == "" || memo == "" {
		return nil, fmt.Errorf("algovoi: could not extract receiver/memo from checkout page")
	}
	return &scrapeResult{Receiver: receiver, Memo: memo}, nil
}

func mustParseHost(rawURL string) string {
	u, err := url.Parse(rawURL)
	if err != nil {
		return ""
	}
	return u.Hostname()
}
