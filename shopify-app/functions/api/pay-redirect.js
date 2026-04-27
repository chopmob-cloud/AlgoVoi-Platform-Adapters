/**
 * GET /api/pay-redirect?shop=X&order_id=Y&chain=ALGO
 * Generates a single payment link for the given chain and redirects to it.
 * Sets redirect_url on the payment link so AlgoVoi redirects the buyer back
 * to /api/order-paid after payment, where we mark the Shopify order as paid.
 */

const ALGOVOI_API   = 'https://api1.ilovechicken.co.uk';
const APP_BASE      = 'https://worker.algovoi.co.uk';

const CHAIN_TO_NETWORK = {
  ALGO:  'algorand_mainnet',
  VOI:   'voi_mainnet',
  HBAR:  'hedera_mainnet',
  XLM:   'stellar_mainnet',
  BASE:  'base_mainnet',
  SOL:   'solana_mainnet',
  TEMPO: 'tempo_mainnet',
};

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

async function hmacHex(secret, message) {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    'raw', enc.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false, ['sign']
  );
  const buf = await crypto.subtle.sign('HMAC', key, enc.encode(message));
  return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('');
}

export async function onRequestOptions() {
  return new Response(null, { status: 204, headers: CORS });
}

export async function onRequestGet(context) {
  const { searchParams } = new URL(context.request.url);
  const shop    = searchParams.get('shop');
  const orderId = searchParams.get('order_id');
  const chain   = (searchParams.get('chain') || 'ALGO').toUpperCase();

  const network = CHAIN_TO_NETWORK[chain];
  if (!shop || !orderId || !network) {
    return new Response('Missing or invalid parameters', { status: 400 });
  }

  const merchant = await context.env.MERCHANTS.get(shop, 'json');
  if (!merchant?.access_token || !merchant?.api_key || !merchant?.tenant_id) {
    return new Response('Merchant not configured', { status: 404 });
  }

  // Use amount/currency passed directly from the extension when available —
  // avoids a round-trip to the Shopify REST API, cutting latency roughly in half.
  let amount   = parseFloat(searchParams.get('amount') || '0');
  let currency = (searchParams.get('currency') || '').toUpperCase();
  let orderName = `#${orderId}`;

  if (!amount || !currency) {
    // Fallback: fetch from Shopify (only needed if extension didn't supply them)
    const orderRes = await fetch(
      `https://${shop}/admin/api/2024-01/orders/${orderId}.json?fields=total_price,currency,name`,
      { headers: { 'X-Shopify-Access-Token': merchant.access_token } }
    );
    if (!orderRes.ok) {
      return new Response('Order not found', { status: 404 });
    }
    const { order } = await orderRes.json();
    amount    = parseFloat(order.total_price);
    currency  = order.currency || 'GBP';
    orderName = order.name || orderName;
  }

  // Build signed redirect URL so order-paid.js can verify it came from AlgoVoi
  const sigPayload  = `${shop}:${orderId}`;
  const sig         = await hmacHex(context.env.SHOPIFY_CLIENT_SECRET, sigPayload);
  const redirectUrl = `${APP_BASE}/api/order-paid?shop=${encodeURIComponent(shop)}&order_id=${encodeURIComponent(orderId)}&sig=${sig}`;

  // Create payment link
  const linkRes = await fetch(`${ALGOVOI_API}/v1/payment-links`, {
    method: 'POST',
    headers: {
      'Content-Type':  'application/json',
      'Authorization': `Bearer ${merchant.api_key}`,
      'X-Tenant-Id':   merchant.tenant_id,
    },
    body: JSON.stringify({
      amount,
      currency,
      label:              `Order ${orderName} — ${chain}`,
      preferred_network:  network,
      expires_in_seconds: 1800,
      redirect_url:       redirectUrl,
    }),
  });

  if (!linkRes.ok) {
    return new Response('Failed to create payment link', { status: 502 });
  }

  const { checkout_url } = await linkRes.json();
  return Response.redirect(checkout_url, 302);
}
