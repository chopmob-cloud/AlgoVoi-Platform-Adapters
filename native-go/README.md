# Native Go — AlgoVoi Payment Adapter

Zero-dependency Go library for integrating AlgoVoi payments (hosted checkout, in-page wallet, and webhook verification) into any Go HTTP server using only the standard library.

Full integration guide: [native-go — see root README](https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `algovoi.go` | Client library — hosted checkout, extension payment, webhook HMAC verification |
| `recurring.go` | Tier 2 — standing-authority recurring payments (8 lifecycle methods + helpers) |
| `example_test.go` | Runnable usage examples as Go test functions |

---

## Quick start — Tier 1 (one-shot payment)

```go
av := algovoi.New(
    "https://api1.ilovechicken.co.uk",
    "algv_YOUR_API_KEY",
    "YOUR_TENANT_ID",
    "YOUR_WEBHOOK_SECRET",
)

http.HandleFunc("/pay-hosted", func(w http.ResponseWriter, r *http.Request) {
    link, err := av.CreatePaymentLink(algovoi.PaymentLinkRequest{
        Amount:   9.99,
        Currency: "USD",
        OrderRef: r.FormValue("order_ref"),
    })
    http.Redirect(w, r, link.URL, http.StatusSeeOther)
})
```

---

## Quick start — Tier 2 (recurring / standing authority)

Tier 2 is "customer signs once, AlgoVoi auto-pulls per cycle". Requires an
existing subscription UUID (create one via the dashboard or `POST /v1/subscriptions`).

```go
// 1. Create a standing authority for a monthly $10 subscription.
resp, err := av.CreateRecurringAuthority(algovoi.AuthorityCreateRequest{
    SubscriptionID:        "YOUR_SUBSCRIPTION_UUID",
    Chain:                 "algorand_mainnet",          // or any of the 7 chains
    CustomerWalletAddress: "CUSTOMER_ALGO_ADDRESS",
    CapAmountMinor:        120_000_000,                 // $120 cap (6 decimals)
    CapPeriodSeconds:      365 * 86400,                 // 1-year window
    PerCycleAmountMinor:   10_000_000,                  // $10/month per pull
    Asset:                 "USDC",
})
// resp.CustomerSigningPayload — hand to the customer's wallet UI

// 2. After on-chain landing, confirm (AlgoVoi's hosted widget does this for you):
auth, err := av.ConfirmAuthority(resp.Authority.ID, algovoi.ConfirmAuthorityRequest{
    OnChainAddress: "app:12345678",  // Algorand app ID; format varies by chain
})

// 3. Inspect, pause, resume, or revoke:
auth, err = av.GetAuthority(authorityID)
auth, err = av.PauseAuthority(authorityID)
auth, err = av.ResumeAuthority(authorityID, "")
auth, err = av.RevokeAuthority(authorityID)  // on-chain revocation

// 4. Handle webhooks:
payload, err := av.VerifyWebhook(rawBody, sigHeader)
if algovoi.IsRecurringEvent(payload) {
    eventType := payload["event_type"].(string)
    // "subscription.charged", "subscription.payment_failed",
    // "recurring.authority_activated", etc.
}
```

Stellar uses 7-decimal USDC precision (`1_200_000_000` = 120 USDC).
All other chains use 6 decimals.

See [`Recurr/merchant-examples/go.go`](../Recurr/merchant-examples/go.go)
for a full runnable example and
[`Recurr/README.md`](../Recurr/README.md) for the chain matrix.

---

Licensed under the [Business Source License 1.1](../LICENSE).
