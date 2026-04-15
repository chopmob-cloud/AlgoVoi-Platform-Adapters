# AlgoVoi x402 Payment Widget

A drop-in Web Component for accepting crypto payments on any website. One `<script>` tag, one HTML element — no framework, no npm, no backend code required.

Supports **Algorand (USDC)**, **VOI (aUSDC)**, **Hedera (USDC)**, and **Stellar (USDC)**.

Live demo: [worker.ilovechicken.co.uk](https://worker.ilovechicken.co.uk)

---

## Quick start

```html
<script type="module" src="https://worker.ilovechicken.co.uk/widget.js"></script>
<algovoi-x402
  amount="29.99"
  currency="USD"
  chains="ALGO,VOI,XLM,HBAR"
  tenant-id="YOUR_TENANT_ID"
  api-key="algv_YOUR_API_KEY">
</algovoi-x402>
```

That's it. The widget renders chain buttons, creates a payment link via the AlgoVoi API, and gives the customer a hosted checkout URL.

---

## Attributes

| Attribute   | Required | Default                                                   | Description                                               |
|-------------|----------|-----------------------------------------------------------|-----------------------------------------------------------|
| `amount`    | Yes      | —                                                         | Payment amount (e.g. `"29.99"`)                           |
| `currency`  | No       | `USD`                                                     | ISO 4217 currency code                                    |
| `chains`    | Yes      | —                                                         | Comma-separated chain codes: `ALGO`, `VOI`, `XLM`, `HBAR` |
| `tenant-id` | *        | —                                                         | Your AlgoVoi tenant UUID                                  |
| `api-key`   | *        | —                                                         | Your AlgoVoi API key (`algv_` or `algvw_`)                |
| `api-url`   | No       | `https://worker.ilovechicken.co.uk/api/x402/pay`         | Override to point at your own backend proxy               |

\* Required when using the default `/api/x402/pay` endpoint. Omit both when using `api-url` with a backend that supplies credentials server-side.

---

## How it works

```
Customer clicks a chain button (e.g. "Algorand")
        ↓
Widget POSTs { chain, amount, currency } to api-url
        ↓
Cloudflare Function proxies to POST /v1/payment-links on api1.ilovechicken.co.uk
        ↓
AlgoVoi returns a checkout_url
        ↓
Widget opens the hosted checkout in a new tab
        ↓
Customer pays on-chain → order confirmed via webhook
```

---

## Widget states

| State     | What the user sees                                              |
|-----------|-----------------------------------------------------------------|
| `idle`    | Chain selection buttons                                         |
| `loading` | Spinner while the payment link is being created                 |
| `ready`   | Checkout link + chain buttons (re-select any chain to regenerate) |
| `done`    | Confirmation message (triggered when the checkout tab closes)   |
| `error`   | Error banner + chain buttons to retry                           |

---

## Securing your credentials

When you embed `tenant-id` and `api-key` directly in HTML, **anyone can read them** via browser DevTools. An attacker could create spam checkout links against your quota. Two production-safe approaches are available:

---

### Option A — Origin-restricted widget key (recommended for static sites)

Use an `algvw_` prefixed key from the AlgoVoi dashboard. These keys are **domain-locked**: the gateway rejects requests that don't originate from your registered domain(s). The widget automatically forwards the browser's `Origin` header via `X-Widget-Origin` so the gateway can enforce this check server-side.

```html
<!-- The key only works from your registered domain — safe to publish in HTML -->
<script type="module" src="https://worker.ilovechicken.co.uk/widget.js"></script>
<algovoi-x402
  amount="29.99"
  currency="USD"
  chains="ALGO,VOI,XLM,HBAR"
  tenant-id="YOUR_TENANT_ID"
  api-key="algvw_YOUR_WIDGET_KEY">
</algovoi-x402>
```

**Trade-off:** credentials are visible in source but can only be used from your registered domain. Suitable for most static sites, Webflow, Framer, Squarespace, etc.

---

### Option B — Server-side proxy via `api-url` (recommended for production)

Point `api-url` at your own backend endpoint. Your backend holds the credentials in environment variables — nothing is ever sent to the browser.

```html
<!-- No credentials in HTML at all -->
<script type="module" src="https://worker.ilovechicken.co.uk/widget.js"></script>
<algovoi-x402
  amount="29.99"
  currency="USD"
  chains="ALGO,VOI,XLM,HBAR"
  api-url="/api/create-payment">
</algovoi-x402>
```

The widget POSTs `{ chain, amount, currency }` to whatever URL you set. Your endpoint then calls the AlgoVoi gateway and returns `{ checkout_url }`.

#### Cloudflare Pages Function

```js
// functions/api/create-payment.js
const CHAIN_MAP = {
  ALGO: 'algorand_mainnet', VOI: 'voi_mainnet',
  XLM:  'stellar_mainnet',  HBAR: 'hedera_mainnet',
};

export async function onRequestPost(context) {
  const { chain, amount, currency } = await context.request.json();
  const res = await fetch('https://api1.ilovechicken.co.uk/v1/payment-links', {
    method: 'POST',
    headers: {
      'Content-Type':  'application/json',
      'Authorization': `Bearer ${context.env.ALGOVOI_API_KEY}`,
      'X-Tenant-Id':   context.env.ALGOVOI_TENANT_ID,
    },
    body: JSON.stringify({
      amount:             parseFloat(amount),
      currency:           (currency || 'USD').toUpperCase(),
      label:              `${chain} payment`,
      preferred_network:  CHAIN_MAP[chain?.toUpperCase()],
      expires_in_seconds: 1800,
    }),
  });
  const { checkout_url } = await res.json();
  return Response.json({ checkout_url });
}

export async function onRequestOptions() {
  return new Response(null, {
    headers: { 'Access-Control-Allow-Origin': '*',
               'Access-Control-Allow-Methods': 'POST, OPTIONS',
               'Access-Control-Allow-Headers': 'Content-Type' },
  });
}
```

Set secrets with Wrangler:
```bash
wrangler secret put ALGOVOI_API_KEY
wrangler secret put ALGOVOI_TENANT_ID
```

#### Next.js / Vercel

```js
// app/api/create-payment/route.js
const CHAIN_MAP = {
  ALGO: 'algorand_mainnet', VOI: 'voi_mainnet',
  XLM:  'stellar_mainnet',  HBAR: 'hedera_mainnet',
};

export async function POST(req) {
  const { chain, amount, currency } = await req.json();
  const res = await fetch('https://api1.ilovechicken.co.uk/v1/payment-links', {
    method: 'POST',
    headers: {
      'Content-Type':  'application/json',
      'Authorization': `Bearer ${process.env.ALGOVOI_API_KEY}`,
      'X-Tenant-Id':   process.env.ALGOVOI_TENANT_ID,
    },
    body: JSON.stringify({
      amount:             parseFloat(amount),
      currency:           (currency || 'USD').toUpperCase(),
      label:              `${chain} payment`,
      preferred_network:  CHAIN_MAP[chain?.toUpperCase()],
      expires_in_seconds: 1800,
    }),
  });
  return Response.json(await res.json());
}
```

Add to `.env.local`:
```
ALGOVOI_API_KEY=algv_YOUR_KEY
ALGOVOI_TENANT_ID=YOUR_TENANT_UUID
```

#### Express

```js
// routes/create-payment.js
const CHAIN_MAP = {
  ALGO: 'algorand_mainnet', VOI: 'voi_mainnet',
  XLM:  'stellar_mainnet',  HBAR: 'hedera_mainnet',
};

app.post('/api/create-payment', async (req, res) => {
  const { chain, amount, currency } = req.body;
  const response = await fetch('https://api1.ilovechicken.co.uk/v1/payment-links', {
    method: 'POST',
    headers: {
      'Content-Type':  'application/json',
      'Authorization': `Bearer ${process.env.ALGOVOI_API_KEY}`,
      'X-Tenant-Id':   process.env.ALGOVOI_TENANT_ID,
    },
    body: JSON.stringify({
      amount:             parseFloat(amount),
      currency:           (currency || 'USD').toUpperCase(),
      label:              `${chain} payment`,
      preferred_network:  CHAIN_MAP[chain?.toUpperCase()],
      expires_in_seconds: 1800,
    }),
  });
  res.json(await response.json());
});
```

---

### Comparison

| Approach | Credentials in HTML? | Works on static sites? | Setup effort |
|----------|---------------------|------------------------|--------------|
| Direct embed (`algv_` key) | Yes — visible in source | Yes | None |
| Origin-restricted (`algvw_` key) | Yes — but domain-locked | Yes | Register domain in dashboard |
| Server-side proxy (`api-url`) | No — never reaches browser | Requires a backend | Low |

---

## Two built-in proxy endpoints

This widget repo ships two Cloudflare Functions:

| Endpoint | Auth | Use case |
|----------|------|----------|
| `POST /api/x402/pay` | Client-supplied `tenant-id` + `api-key` | Production — merchant passes their own credentials |
| `POST /api/x402/demo` | Server-side env secrets | Demo/testing — no credentials in HTML |

Both endpoints forward the browser's `Origin` header as `X-Widget-Origin` to the gateway, enabling domain allowlisting on `algvw_` keys.

---

## Deployment

The widget runs on **Cloudflare Pages** with **Pages Functions** as the backend proxy.

### Deploy your own instance

1. Clone this directory
2. Set Cloudflare environment secrets:
   ```bash
   wrangler secret put GATEWAY_API_KEY
   wrangler secret put GATEWAY_TENANT_ID
   ```
3. Deploy:
   ```bash
   wrangler pages deploy .
   ```

### Files

| File | Purpose |
|------|---------|
| `widget.js` | Web Component — renders chain buttons and handles the full payment flow |
| `index.html` | Demo page — uses the demo endpoint, no credentials needed |
| `functions/api/x402/pay.js` | CF Function — proxies with client-supplied credentials + Origin forwarding |
| `functions/api/x402/demo.js` | CF Function — proxies with server-side env secrets |
| `wrangler.toml` | Cloudflare Pages configuration |
| `make_widget_gif.py` | Generates the embed demo GIF |

---

## CORS

Both endpoints return `Access-Control-Allow-Origin: *` — the widget is embeddable from any origin.

---

## Supported networks

| Code | Network | Asset |
|------|---------|-------|
| `ALGO` | Algorand Mainnet | USDC |
| `VOI` | VOI Mainnet | aUSDC |
| `XLM` | Stellar Mainnet | USDC |
| `HBAR` | Hedera Mainnet | USDC |

---

## Live instance

The reference deployment is at `https://worker.ilovechicken.co.uk`:

- Demo page: `https://worker.ilovechicken.co.uk`
- Widget JS: `https://worker.ilovechicken.co.uk/widget.js`
- Demo endpoint: `POST https://worker.ilovechicken.co.uk/api/x402/demo`
- Pay endpoint: `POST https://worker.ilovechicken.co.uk/api/x402/pay`

Source: [github.com/chopmob-cloud/AlgoVoi-Platform-Adapters](https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters)
