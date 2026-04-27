/**
 * POST /webhooks/gdpr/shop-redact
 *
 * Shopify GDPR mandatory webhook: shop/redact
 * Called 48 hours after a merchant uninstalls the app.
 * Must delete all merchant data associated with the shop.
 */

export async function onRequestPost(context) {
  const body = await context.request.text();
  const hmac = context.request.headers.get('x-shopify-hmac-sha256');

  if (!hmac || !context.env.SHOPIFY_CLIENT_SECRET) {
    return new Response('Unauthorized', { status: 401 });
  }

  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    'raw',
    encoder.encode(context.env.SHOPIFY_CLIENT_SECRET),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );
  const sig = await crypto.subtle.sign('HMAC', key, encoder.encode(body));
  const expected = btoa(String.fromCharCode(...new Uint8Array(sig)));

  if (expected !== hmac) {
    return new Response('Invalid signature', { status: 401 });
  }

  // Parse the shop domain from the request
  let shopDomain = '';
  try {
    const data = JSON.parse(body);
    shopDomain = data.shop_domain || '';
  } catch (_) {}

  // Delete the merchant record from KV
  if (shopDomain && context.env.MERCHANTS) {
    await context.env.MERCHANTS.delete(shopDomain);
    console.log(`GDPR shop/redact: deleted merchant data for ${shopDomain}`);
  }

  return Response.json({ received: true, redacted: true }, { status: 200 });
}
