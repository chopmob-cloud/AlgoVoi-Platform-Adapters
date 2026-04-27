/**
 * POST /webhooks/gdpr/customers-redact
 *
 * Shopify GDPR mandatory webhook: customers/redact
 * Called when a store owner requests deletion of customer data.
 *
 * AlgoVoi does NOT store any customer personal data.
 * We only store merchant-level data (shop domain, access token).
 * No action is required for customer redaction.
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

  console.log('GDPR customers/redact received — no customer data to delete');

  return Response.json({ received: true, redacted: true }, { status: 200 });
}
