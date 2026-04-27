/**
 * POST /webhooks/shopify
 * Receives orders/create from Shopify, verifies HMAC, creates payment link,
 * and updates the Shopify order note + order status page with the pay URL.
 */

const ALGOVOI_API = 'https://api1.ilovechicken.co.uk';
const APP_BASE    = 'https://worker.algovoi.co.uk';

async function hmacSha256Base64(secret, message) {
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    'raw', encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false, ['sign']
  );
  const sig = await crypto.subtle.sign('HMAC', key, encoder.encode(message));
  return btoa(String.fromCharCode(...new Uint8Array(sig)));
}

export async function onRequestPost(context) {
  const shop  = context.request.headers.get('x-shopify-shop-domain');
  const topic = context.request.headers.get('x-shopify-topic');
  const hmac  = context.request.headers.get('x-shopify-hmac-sha256');
  const body  = await context.request.text();

  if (!shop) return new Response('Missing shop header', { status: 400 });

  const merchant = await context.env.MERCHANTS.get(shop, 'json');
  if (!merchant?.tenant_id || !merchant?.api_key) {
    return new Response('Merchant not configured', { status: 404 });
  }

  // Verify Shopify HMAC
  const valid = await hmacSha256Base64(context.env.SHOPIFY_CLIENT_SECRET, body) === hmac;
  if (!valid) {
    return new Response('Invalid signature', { status: 401 });
  }

  const order = JSON.parse(body);
  const orderId = order.id;
  const amount  = parseFloat(order.total_price || '0');
  const currency = order.currency || 'USD';
  const orderName = order.name || `#${order.order_number}`;

  if (!orderId || amount <= 0) {
    return Response.json({ received: true, skipped: 'no amount' });
  }

  // Skip if already paid
  if (order.financial_status === 'paid') {
    return Response.json({ received: true, skipped: 'already paid' });
  }

  // Create an AlgoVoi payment link (default chain — customer chooses on pay page)
  let checkoutUrl = '';
  try {
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
        label: `Shopify ${orderName}`,
        preferred_network: 'algorand_mainnet',
        expires_in_seconds: 1800,
      }),
      signal: AbortSignal.timeout(15000),
    });
    if (linkRes.ok) {
      const linkData = await linkRes.json();
      checkoutUrl = linkData.checkout_url || '';
    }
  } catch (_) {}

  // Build the multi-chain pay page URL (always available even if link creation fails)
  const payPageUrl = `${APP_BASE}/pay?shop=${encodeURIComponent(shop)}&order_id=${encodeURIComponent(orderId)}`;

  // Update the Shopify order: note + order status page note
  if (merchant.access_token) {
    const note = [
      `💰 Pay with Crypto — ${orderName}`,
      '',
      `Choose your chain and pay with USDC:`,
      payPageUrl,
      '',
      checkoutUrl ? `Direct Algorand checkout: ${checkoutUrl}` : '',
      '',
      'Powered by AlgoVoi',
    ].filter(Boolean).join('\n');

    try {
      // Update order note
      await fetch(`https://${shop}/admin/api/2024-01/orders/${orderId}.json`, {
        method: 'PUT',
        headers: {
          'Content-Type':           'application/json',
          'X-Shopify-Access-Token': merchant.access_token,
        },
        body: JSON.stringify({
          order: {
            id: orderId,
            note: note,
            tags: 'algovoi-pending',
          },
        }),
        signal: AbortSignal.timeout(10000),
      });
    } catch (_) {}

    // Also add an order-level metafield with the pay URL (visible on order status page)
    try {
      await fetch(`https://${shop}/admin/api/2024-01/orders/${orderId}/metafields.json`, {
        method: 'POST',
        headers: {
          'Content-Type':           'application/json',
          'X-Shopify-Access-Token': merchant.access_token,
        },
        body: JSON.stringify({
          metafield: {
            namespace: 'algovoi',
            key: 'pay_url',
            value: payPageUrl,
            type: 'single_line_text_field',
          },
        }),
        signal: AbortSignal.timeout(10000),
      });
    } catch (_) {}
  }

  // Forward to AlgoVoi platform webhook (best effort)
  if (merchant.webhook_secret) {
    try {
      const platformHmac = await hmacSha256Base64(merchant.webhook_secret, body);
      await fetch(`${ALGOVOI_API}/webhooks/shopify/${merchant.tenant_id}`, {
        method: 'POST',
        headers: {
          'Content-Type':          'application/json',
          'X-Shopify-Hmac-Sha256': platformHmac,
          'X-Shopify-Shop-Domain': shop,
          'X-Shopify-Topic':       topic,
        },
        body,
        signal: AbortSignal.timeout(10000),
      });
    } catch (_) {}
  }

  return Response.json({
    received: true,
    status: 'awaiting_payment',
    order_id: orderId,
    pay_url: payPageUrl,
    checkout_url: checkoutUrl || undefined,
  });
}
