# Native Go — AlgoVoi Payment Adapter

Zero-dependency Go library for integrating AlgoVoi payments (hosted checkout, in-page wallet, and webhook verification) into any Go HTTP server using only the standard library.

Full integration guide: [native-go — see root README](https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `algovoi.go` | Client library — hosted checkout, extension payment, webhook HMAC verification |
| `example_test.go` | Runnable usage examples as Go test functions |

---

## Quick start

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

Licensed under the [Business Source License 1.1](../LICENSE).
