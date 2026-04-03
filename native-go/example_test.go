// Package algovoi — usage examples as runnable test functions.
//
// These demonstrate how to integrate AlgoVoi payments into any Go HTTP server.
// Run with: go test -v -run Example
package algovoi

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
)

// ExampleNew shows how to create a client and set up HTTP handlers.
func ExampleNew() {
	av := New(
		"https://api1.ilovechicken.co.uk",
		"algv_YOUR_API_KEY",
		"YOUR_TENANT_ID",
		"YOUR_WEBHOOK_SECRET",
	)

	// ── Hosted checkout: redirect customer to AlgoVoi ────────────────

	http.HandleFunc("/pay-hosted", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}

		network := r.FormValue("network")
		if !IsValidHostedNetwork(network) {
			network = "algorand_mainnet"
		}

		result, err := av.HostedCheckout(
			9.99, "USD", "Order #123", network,
			"https://yoursite.com/payment-return",
		)
		if err != nil {
			http.Error(w, "Payment could not be initiated: "+err.Error(), http.StatusInternalServerError)
			return
		}

		// Store token in session/DB for verification on return
		// session.Set("algovoi_token", result.Token)

		http.Redirect(w, r, result.CheckoutURL, http.StatusSeeOther)
	})

	// ── Hosted checkout return: verify before marking paid ───────────

	http.HandleFunc("/payment-return", func(w http.ResponseWriter, r *http.Request) {
		// token := session.Get("algovoi_token")
		token := "" // Replace with session lookup

		// CRITICAL: verify payment was actually completed
		paid, _ := av.VerifyHostedReturn(token)
		if paid {
			fmt.Fprint(w, "Payment confirmed!")
			// Mark order as paid in your database
		} else {
			fmt.Fprint(w, "Payment not completed. Order is pending.")
		}
	})

	// ── Extension payment: in-page wallet flow ──────────────────────

	http.HandleFunc("/pay-extension", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}

		network := r.FormValue("network")
		if !IsValidExtNetwork(network) {
			network = "algorand_mainnet"
		}

		data, err := av.ExtensionCheckout(9.99, "USD", "Order #123", network)
		if err != nil {
			http.Error(w, "Payment could not be initiated: "+err.Error(), http.StatusInternalServerError)
			return
		}

		// Store token in session
		// session.Set("algovoi_token", data.Token)

		// Render the payment UI (in production, use a template)
		w.Header().Set("Content-Type", "text/html")
		fmt.Fprintf(w, `<html><body style="background:#0f1117;color:#e2e8f0;">
			<p>Pay %s %s on %s</p>
			<p>To: %s</p>
			<p>Memo: %s</p>
			<p>Use the AlgoVoi browser extension to complete payment.</p>
		</body></html>`,
			data.AmountDisplay, data.Ticker, data.Chain, data.Receiver, data.Memo)
	})

	// ── Extension verify endpoint (called by JS) ────────────────────

	http.HandleFunc("/verify-extension", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}

		// token := session.Get("algovoi_token")
		token := "" // Replace with session lookup

		var input struct {
			TxID string `json:"tx_id"`
		}
		if err := json.NewDecoder(r.Body).Decode(&input); err != nil || input.TxID == "" || len(input.TxID) > 200 {
			http.Error(w, `{"error":"Missing tx_id"}`, http.StatusBadRequest)
			return
		}

		result, err := av.VerifyExtensionPayment(token, input.TxID)
		if err != nil {
			http.Error(w, `{"error":"Verification failed"}`, http.StatusUnprocessableEntity)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(result)
	})

	// ── Webhook handler ─────────────────────────────────────────────

	http.HandleFunc("/webhook", av.WebhookHandler(func(payload map[string]interface{}) {
		orderID, _ := payload["order_id"].(string)
		txID, _ := payload["tx_id"].(string)
		log.Printf("Webhook: order %s paid via tx %s", orderID, txID)
		// Mark order as paid in your database
	}))

	// ── Checkout page with chain selector ────────────────────────────

	http.HandleFunc("/checkout", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/html")
		fmt.Fprintf(w, `<html><body style="background:#0f1117;color:#e2e8f0;font-family:system-ui;max-width:600px;margin:2rem auto;">
			<h2>Checkout — $9.99</h2>
			<h3>Hosted Checkout</h3>
			<form method="POST" action="/pay-hosted">
				%s
				<button type="submit" style="margin-top:1rem;padding:.8rem 2rem;background:#3b82f6;color:#fff;border:none;border-radius:8px;cursor:pointer;">Pay via Hosted Checkout</button>
			</form>
			<hr style="border-color:#2a2d3a;margin:2rem 0;">
			<h3>Extension Payment</h3>
			<form method="POST" action="/pay-extension">
				%s
				<button type="submit" style="margin-top:1rem;padding:.8rem 2rem;background:#8b5cf6;color:#fff;border:none;border-radius:8px;cursor:pointer;">Pay via Extension</button>
			</form>
		</body></html>`,
			RenderChainSelector("network", "hosted"),
			RenderChainSelector("network", "extension"),
		)
	})

	log.Println("Starting server on :8080")
	log.Fatal(http.ListenAndServe(":8080", nil))
}
