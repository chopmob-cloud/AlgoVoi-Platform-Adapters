/**
 * POST /webhooks/gdpr/customers-data-request
 *
 * Shopify GDPR mandatory webhook: customers/data_request
 * Called when a customer requests their data under GDPR.
 *
 * AlgoVoi does NOT store any customer personal data (no names, emails,
 * addresses, or payment details). We only store the shop domain and
 * merchant access token. Therefore, there is no customer data to return.
 */

export async function onRequestPost(context) {
  const body = await context.request.text();
  const hmac = context.request.headers.get('x-shopify-hmac-sha256');

  // Verify webhook authenticity
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

  // AlgoVoi stores no customer PII — acknowledge the request
  console.log('GDPR customers/data_request received — no customer data stored');

  return Response.json({ received: true, customer_data: null }, { status: 200 });
}
