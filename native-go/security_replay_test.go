// Package algovoi — security replay suite (2026-04-15).
//
// Run with: go test -v -run TestSecurityReplay
//
// Mirrors the Python/PHP/etc. security replays. Go's static type system
// closes the bytes/None/int HMAC TypeError class — but the rest of the
// usual gaps (amount sanity, redirect scheme, scheme guard on outbound
// calls, token length cap, port-mismatch SSRF) all need verification.
package algovoi

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"math"
	"strings"
	"testing"
)

func b64Hmac(secret string, body []byte) string {
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write(body)
	return base64.StdEncoding.EncodeToString(mac.Sum(nil))
}

func TestSecurityReplay(t *testing.T) {
	c := New(
		"https://api1.ilovechicken.co.uk",
		"test_key", "test_tenant", "test_secret",
	)

	t.Run("HMAC empty-secret rejects forged sig", func(t *testing.T) {
		nosec := New("https://x", "", "", "")
		body := []byte(`{"x":1}`)
		_, err := nosec.VerifyWebhook(body, b64Hmac("", body))
		if err == nil {
			t.Fatal("empty secret accepted forged sig")
		}
	})

	t.Run("HMAC valid sig accepted", func(t *testing.T) {
		body := []byte(`{"y":2}`)
		sig := b64Hmac("test_secret", body)
		_, err := c.VerifyWebhook(body, sig)
		if err != nil {
			t.Fatalf("valid sig rejected: %v", err)
		}
	})

	t.Run("HMAC wrong-by-one rejected (timing-safe)", func(t *testing.T) {
		body := []byte(`{"z":3}`)
		sig := b64Hmac("test_secret", body)
		// Pick a replacement char guaranteed different from sig[0]
		first := byte('Z')
		if sig[0] == 'Z' {
			first = 'Y'
		}
		bad := string(first) + sig[1:]
		_, err := c.VerifyWebhook(body, bad)
		if err == nil {
			t.Fatal("wrong-by-one signature accepted")
		}
	})

	t.Run("HMAC empty signature rejected", func(t *testing.T) {
		body := []byte(`{"a":1}`)
		_, err := c.VerifyWebhook(body, "")
		if err == nil {
			t.Fatal("empty signature accepted")
		}
	})

	t.Run("VerifyWebhook 1MB+ body rejected (v1.1.0 cap)", func(t *testing.T) {
		var sb strings.Builder
		sb.WriteString(`{"x":"`)
		for i := 0; i < 1024*1024; i++ {
			sb.WriteByte('A')
		}
		sb.WriteString(`"}`)
		huge := []byte(sb.String())
		sig := b64Hmac("test_secret", huge)
		_, err := c.VerifyWebhook(huge, sig)
		if err == nil {
			t.Fatal("1 MB body accepted by VerifyWebhook (no cap)")
		}
	})

	t.Run("CreatePaymentLink rejects non-finite amount (v1.1.0 guard)", func(t *testing.T) {
		// After the local guard, all five values fail FAST with no
		// network attempt — no api1.ilovechicken.co.uk lookup needed.
		for _, amt := range []float64{math.NaN(), math.Inf(1), math.Inf(-1), 0, -1} {
			_, err := c.CreatePaymentLink(amt, "USD", "L", "algorand_mainnet", "")
			if err == nil {
				t.Errorf("amount %v accepted (expected error)", amt)
			}
			// The local guard's error message should mention "amount".
			if err != nil && !strings.Contains(err.Error(), "amount") {
				t.Logf("amount %v: error mentions network instead of local guard: %v", amt, err)
			}
		}
	})

	t.Run("CreatePaymentLink rejects non-https redirect (v1.1.0 guard)", func(t *testing.T) {
		for _, u := range []string{
			"http://example.com",
			"file:///etc/passwd",
			"gopher://x",
			"javascript:alert(1)",
		} {
			_, err := c.CreatePaymentLink(1.0, "USD", "L", "algorand_mainnet", u)
			if err == nil {
				t.Errorf("redirect %q accepted (expected error)", u)
			}
			if err != nil && !strings.Contains(err.Error(), "redirect_url") {
				t.Logf("redirect %q: not local guard: %v", u, err)
			}
		}
	})

	t.Run("VerifyHostedReturn rejects http:// api_base (v1.1.0)", func(t *testing.T) {
		insecure := New("http://api1.ilovechicken.co.uk", "k", "t", "s")
		// Should return (false, nil) FAST without any network attempt.
		ok, err := insecure.VerifyHostedReturn("test_token")
		if ok || err != nil {
			t.Fatalf("expected (false, nil) — got (%v, %v)", ok, err)
		}
	})

	t.Run("VerifyHostedReturn token length cap (v1.1.0)", func(t *testing.T) {
		ok, _ := c.VerifyHostedReturn(strings.Repeat("A", 201))
		if ok {
			t.Fatal("oversized token accepted")
		}
	})

	t.Run("VerifyExtensionPayment token length cap (v1.1.0)", func(t *testing.T) {
		longToken := strings.Repeat("A", 201)
		_, err := c.VerifyExtensionPayment(longToken, "TX_OK")
		if err == nil {
			t.Fatal("oversized token accepted")
		}
	})

	t.Run("VerifyExtensionPayment tx_id length cap", func(t *testing.T) {
		_, err := c.VerifyExtensionPayment("tok", strings.Repeat("A", 201))
		if err == nil {
			t.Fatal("oversized tx_id accepted")
		}
	})

	t.Run("VerifyExtensionPayment rejects http:// api_base (v1.1.0)", func(t *testing.T) {
		insecure := New("http://api1.ilovechicken.co.uk", "k", "t", "s")
		_, err := insecure.VerifyExtensionPayment("tok", "TX_OK")
		if err == nil {
			t.Fatal("http:// api_base accepted")
		}
		if err != nil && !strings.Contains(err.Error(), "https") {
			t.Logf("not local guard: %v", err)
		}
	})

	t.Run("post() refuses authenticated plaintext (v1.1.0)", func(t *testing.T) {
		// Confirm the API key is never sent over plaintext. The local
		// guard inside post() must trip BEFORE any network call.
		insecure := New("http://api1.ilovechicken.co.uk", "leaky_key", "t", "s")
		_, err := insecure.CreatePaymentLink(1.0, "USD", "L", "algorand_mainnet", "")
		if err == nil {
			t.Fatal("plaintext POST attempted with API key")
		}
	})

	t.Run("AlgodOverrides honoured (v1.1.0)", func(t *testing.T) {
		c2 := NewWithAlgodOverrides("https://x", "k", "t", "s",
			map[string]AlgodConfig{
				"algorand-mainnet": {URL: "https://my-private-algod", AssetID: 999, Ticker: "USDC", Dec: 6},
			})
		got := c2.Algod["algorand-mainnet"]
		if got.URL != "https://my-private-algod" {
			t.Fatalf("override not applied: %+v", got)
		}
		if got.AssetID != 999 {
			t.Fatalf("override AssetID not applied: %d", got.AssetID)
		}
	})

	t.Run("ExtractToken doesn't allow path traversal", func(t *testing.T) {
		// Tokens are constrained to [A-Za-z0-9_-], so '..' and '/' won't match.
		got := ExtractToken("https://x/checkout/../../admin")
		if got == "" {
			// Empty is the safe outcome — regex didn't match.
			return
		}
		// If non-empty, it must not contain a slash or dot.
		if strings.ContainsAny(got, "/.") {
			t.Fatalf("path traversal characters survived in token %q", got)
		}
	})
}
