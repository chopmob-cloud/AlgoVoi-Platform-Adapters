/**
 * x402 Widget — Demo Endpoint
 * ───────────────────────────
 * Cloudflare Pages Function that proxies widget payment requests using
 * server-side credentials from environment variables. The browser sends
 * NO credentials — they're sourced from CF Pages secrets.
 *
 * This is the recommended pattern for production deployments. See ./pay.js
 * for the alternative where the browser supplies its own credentials.
 *
 * Required CF Pages env vars:
 *   GATEWAY_API_KEY   — algv_ or algvw_ key
 *   GATEWAY_TENANT_ID — tenant UUID
 * Optional:
 *   GATEWAY_URL — defaults to https://api1.ilovechicken.co.uk
 */

const CHAIN_TO_NETWORK = {
  ALGO:  'algorand_mainnet',
  VOI:   'voi_mainnet',
  HBAR:  'hedera_mainnet',
  XLM:   'stellar_mainnet',
  BASE:  'base_mainnet',
  SOL:   'solana_mainnet',
  TEMPO: 'tempo_mainnet',
};

const DEFAULT_GATEWAY_URL = 'https://api1.ilovechicken.co.uk';
const REQUEST_TIMEOUT_MS  = 30_000;
const MAX_BODY_BYTES      = 4 * 1024;
const LINK_TTL_SECONDS    = 1800;

const CORS_HEADERS = {
  'Access-Control-Allow-Origin':  '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Access-Control-Max-Age':       '86400',
};

const json = (body, status = 200) =>
  Response.json(body, { status, headers: CORS_HEADERS });

export async function onRequestOptions() {
  return new Response(null, { headers: CORS_HEADERS });
}

export async function onRequestPost(context) {
  // 1. Parse + size-check the request body
  let body;
  try {
    const raw = await context.request.text();
    if (raw.length > MAX_BODY_BYTES) {
      return json({ error: 'Request body too large' }, 413);
    }
    body = JSON.parse(raw);
  } catch {
    return json({ error: 'Invalid JSON body' }, 400);
  }

  // 2. Validate inputs
  const { chain, amount, currency } = body;

  const network = CHAIN_TO_NETWORK[chain?.toUpperCase?.()];
  if (!network) {
    return json({ error: `Unsupported chain: ${chain}` }, 400);
  }

  const amountNum = parseFloat(amount);
  if (!Number.isFinite(amountNum) || amountNum <= 0) {
    return json({ error: 'Amount must be a positive number' }, 400);
  }

  // 3. Pull credentials from env
  const apiKey     = context.env.GATEWAY_API_KEY;
  const tenantId   = context.env.GATEWAY_TENANT_ID;
  const gatewayUrl = context.env.GATEWAY_URL ?? DEFAULT_GATEWAY_URL;

  if (!apiKey || !tenantId) {
    return json({ error: 'Demo service not configured.' }, 503);
  }

  // 4. Call the gateway with a timeout
  const origin = context.request.headers.get('origin') || '';
  const ctrl   = new AbortController();
  const timer  = setTimeout(() => ctrl.abort(), REQUEST_TIMEOUT_MS);

  let res;
  try {
    res = await fetch(`${gatewayUrl}/v1/payment-links`, {
      method: 'POST',
      signal: ctrl.signal,
      headers: {
        'Content-Type':  'application/json',
        'Authorization': `Bearer ${apiKey}`,
        'X-Tenant-Id':   tenantId,
        ...(origin && { 'X-Widget-Origin': origin }),
      },
      body: JSON.stringify({
        amount:             amountNum,
        currency:           (currency || 'USD').toUpperCase(),
        label:              `${chain.toUpperCase()} demo payment`,
        preferred_network:  network,
        expires_in_seconds: LINK_TTL_SECONDS,
      }),
    });
  } catch (err) {
    if (err.name === 'AbortError') {
      return json({ error: 'Gateway request timed out' }, 504);
    }
    return json({ error: 'Gateway unreachable' }, 502);
  } finally {
    clearTimeout(timer);
  }

  // 5. Surface gateway errors with a clean message
  if (!res.ok) {
    let errMsg = `Server error ${res.status}`;
    try {
      const errJson = await res.json();
      errMsg = errJson.detail || errJson.message || errJson.error || errMsg;
    } catch {
      // Gateway didn't return JSON — keep the generic message
    }
    return json({ error: errMsg }, res.status);
  }

  // 6. Pass the checkout URL back to the widget
  let payload;
  try {
    payload = await res.json();
  } catch {
    return json({ error: 'Gateway returned invalid response' }, 502);
  }

  if (!payload.checkout_url) {
    return json({ error: 'Gateway response missing checkout_url' }, 502);
  }

  return json({ checkout_url: payload.checkout_url });
}
