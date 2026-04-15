/**
 * x402 Widget — Pay Endpoint
 * ──────────────────────────
 * Cloudflare Pages Function that proxies widget payment requests to the
 * AlgoVoi gateway. The browser supplies tenant-id + api-key in the body
 * (typically an origin-restricted `algvw_` widget key).
 *
 * For server-side credential storage instead of client-supplied keys,
 * see ./demo.js as a template — same shape, env-sourced credentials.
 *
 * The browser's Origin header is forwarded as X-Widget-Origin so the
 * gateway can enforce domain allowlisting on `algvw_` keys.
 */

const CHAIN_TO_NETWORK = {
  ALGO: 'algorand_mainnet',
  VOI:  'voi_mainnet',
  XLM:  'stellar_mainnet',
  HBAR: 'hedera_mainnet',
};

const GATEWAY_URL        = 'https://api1.ilovechicken.co.uk';
const REQUEST_TIMEOUT_MS = 30_000;
const MAX_BODY_BYTES     = 4 * 1024;   // payment requests are tiny — reject obvious abuse
const LINK_TTL_SECONDS   = 1800;       // 30 min — matches gateway default

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
  const { chain, amount, currency, tenantId, apiKey } = body;

  if (!tenantId || typeof tenantId !== 'string') {
    return json({ error: 'Missing tenant-id' }, 400);
  }
  if (!apiKey || typeof apiKey !== 'string' ||
      !(apiKey.startsWith('algv_') || apiKey.startsWith('algvw_'))) {
    return json(
      { error: 'Missing or invalid api-key (expected algv_ or algvw_ prefix)' },
      400,
    );
  }

  const network = CHAIN_TO_NETWORK[chain?.toUpperCase?.()];
  if (!network) {
    return json({ error: `Unsupported chain: ${chain}` }, 400);
  }

  const amountNum = parseFloat(amount);
  if (!Number.isFinite(amountNum) || amountNum <= 0) {
    return json({ error: 'Amount must be a positive number' }, 400);
  }

  // 3. Call the gateway with a timeout
  const origin = context.request.headers.get('origin') || '';
  const ctrl   = new AbortController();
  const timer  = setTimeout(() => ctrl.abort(), REQUEST_TIMEOUT_MS);

  let res;
  try {
    res = await fetch(`${GATEWAY_URL}/v1/payment-links`, {
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
        label:              `${chain.toUpperCase()} payment`,
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

  // 4. Surface gateway errors with a clean, user-friendly message
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

  // 5. Pass the checkout URL back to the widget
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
