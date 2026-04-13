# AlgoVoi x402 Payment Widget

A drop-in Web Component for accepting crypto payments on any website. One `<script>` tag, one HTML element — no framework, no npm, no backend code required.

Supports **Algorand (USDC)**, **VOI (aUSDC)**, **Hedera (USDC)**, and **Stellar (USDC)**.

---

## Quick start

```html
<script type="module" src="https://worker.ilovechicken.co.uk/widget.js"></script>
<algovoi-x402
  amount="29.99"
  chains="ALGO,VOI,XLM,HBAR"
  tenant-id="YOUR_TENANT_ID"
  api-key="algv_YOUR_API_KEY">
</algovoi-x402>
```

That's it. The widget renders chain buttons, creates a payment link via the AlgoVoi API, and gives the customer a hosted checkout URL.

---

## Attributes

| Attribute | Required | Description |
|-----------|----------|-------------|
| `amount` | Yes | Payment amount (e.g. `"29.99"`) |
| `chains` | Yes | Comma-separated chain codes: `ALGO`, `VOI`, `XLM`, `HBAR` |
| `tenant-id` | Yes | Your AlgoVoi tenant UUID |
| `api-key` | Yes | Your AlgoVoi API key (starts with `algv_`) |

---

## How it works

```
Customer clicks a chain button (e.g. "ALGO")
        ↓
Widget calls POST /api/x402/pay on the Cloudflare Function
        ↓
Function proxies to POST /v1/payment-links on api1.ilovechicken.co.uk
        ↓
AlgoVoi returns a checkout_url
        ↓
Widget displays a link to the hosted checkout page
        ↓
Customer pays on-chain → order confirmed via webhook
```

---

## Two endpoints

| Endpoint | Auth | Use case |
|----------|------|----------|
| `POST /api/x402/pay` | Client-supplied `tenant-id` + `api-key` | Production — merchant embeds their own credentials |
| `POST /api/x402/demo` | Server-side env secrets | Demo/testing — no credentials exposed to the browser |

---

## Security best practices

### The problem

When you embed `tenant-id` and `api-key` directly in HTML, **anyone can view them** via "View Source" or browser DevTools. An attacker could use your API key to create payment links that settle to your payout address — they can't steal funds, but they can:

- Create spam checkout links using your tenant quota
- Trigger rate limits on your account
- See your tenant ID (not secret, but unnecessary exposure)

### Recommended approaches

#### 1. Server-side proxy (recommended for production)

**Don't expose your API key in HTML.** Instead, create a thin backend endpoint that calls the AlgoVoi API:

```html
<!-- Frontend: no credentials in HTML -->
<script type="module" src="/widget.js"></script>
<algovoi-x402 amount="29.99" chains="ALGO,VOI,XLM,HBAR">
</algovoi-x402>

<script>
  // Override the widget's default endpoint to use YOUR backend
  window.ALGOVOI_PAY_URL = '/api/create-payment';
</script>
```

```python
# Backend (Flask example): credentials stay server-side
@app.route('/api/create-payment', methods=['POST'])
def create_payment():
    data = request.get_json()
    resp = requests.post('https://api1.ilovechicken.co.uk/v1/payment-links',
        headers={
            'Authorization': f'Bearer {os.environ["ALGOVOI_API_KEY"]}',
            'X-Tenant-Id': os.environ['ALGOVOI_TENANT_ID'],
            'Content-Type': 'application/json',
        },
        json={
            'amount': float(data['amount']),
            'currency': 'GBP',
            'label': f'{data["chain"]} payment',
            'preferred_network': CHAIN_MAP[data['chain']],
        }
    )
    return jsonify(resp.json())
```

#### 2. Demo endpoint (recommended for testing)

Use the `/api/x402/demo` endpoint which keeps credentials in Cloudflare environment variables — nothing exposed to the browser:

```html
<script>
  window.ALGOVOI_PAY_URL = 'https://worker.ilovechicken.co.uk/api/x402/demo';
</script>
<script type="module" src="https://worker.ilovechicken.co.uk/widget.js"></script>
<algovoi-x402 amount="0.01" chains="ALGO,VOI">
</algovoi-x402>
```

#### 3. Client-side with restricted key (acceptable for low-risk)

If you must embed credentials in HTML (e.g. static sites with no backend):

- **Use a dedicated API key** with restricted permissions (payment link creation only)
- **Set spending caps** on your tenant to limit abuse
- **Monitor usage** via the AlgoVoi dashboard for unexpected spikes
- **Rotate the key** if you suspect it's been misused
- **Never use your admin key** — only use tenant-scoped API keys (`algv_`)

```html
<!-- Acceptable for low-value, rate-limited use cases -->
<algovoi-x402
  amount="0.99"
  chains="ALGO"
  tenant-id="your-tenant-id"
  api-key="algv_restricted-key-with-caps">
</algovoi-x402>
```

---

## Deployment

The widget runs on **Cloudflare Pages** with **Pages Functions** as the backend proxy.

### Deploy your own instance

1. Clone this directory
2. Set Cloudflare environment secrets:
   ```
   wrangler secret put GATEWAY_API_KEY
   wrangler secret put GATEWAY_TENANT_ID
   ```
3. Deploy:
   ```
   wrangler pages deploy .
   ```

### Files

| File | Purpose |
|------|---------|
| `widget.js` | Web Component — renders chain buttons and handles payment flow |
| `index.html` | Demo page with the widget embedded |
| `functions/api/x402/pay.js` | Cloudflare Function — proxies payment links with client-supplied credentials |
| `functions/api/x402/demo.js` | Cloudflare Function — proxies payment links with server-side env credentials |
| `wrangler.toml` | Cloudflare Pages configuration |

---

## CORS

Both endpoints return `Access-Control-Allow-Origin: *` — the widget is embeddable from any origin.

---

## Live instance

The reference deployment is at `https://worker.ilovechicken.co.uk`:

- Widget JS: `https://worker.ilovechicken.co.uk/widget.js`
- Demo endpoint: `POST https://worker.ilovechicken.co.uk/api/x402/demo`
- Pay endpoint: `POST https://worker.ilovechicken.co.uk/api/x402/pay`
