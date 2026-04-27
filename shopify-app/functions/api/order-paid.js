/**
 * GET /api/order-paid?shop=X&order_id=Y&sig=Z
 *
 * AlgoVoi redirects the buyer here after payment is verified.
 * We verify the HMAC sig (computed in pay-redirect.js using SHOPIFY_CLIENT_SECRET),
 * then call Shopify's orderMarkAsPaid GraphQL mutation to mark the order as paid.
 * Finally we redirect the buyer to the Shopify order status page.
 */

const SHOPIFY_API_VERSION = '2024-01';

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

const MARK_AS_PAID = `
  mutation orderMarkAsPaid($input: OrderMarkAsPaidInput!) {
    orderMarkAsPaid(input: $input) {
      order { id displayFinancialStatus }
      userErrors { field message }
    }
  }
`;

export async function onRequestGet(context) {
  const { searchParams } = new URL(context.request.url);
  const shop    = searchParams.get('shop');
  const orderId = searchParams.get('order_id');
  const sig     = searchParams.get('sig');

  if (!shop || !orderId || !sig) {
    return new Response('Missing parameters', { status: 400 });
  }

  // Verify HMAC signature
  const expected = await hmacHex(context.env.SHOPIFY_CLIENT_SECRET, `${shop}:${orderId}`);
  if (expected !== sig) {
    return new Response('Invalid signature', { status: 403 });
  }

  const merchant = await context.env.MERCHANTS.get(shop, 'json');
  if (!merchant?.access_token) {
    return new Response('Merchant not configured', { status: 404 });
  }

  // Mark order as paid via Shopify GraphQL Admin API
  const gid = `gid://shopify/Order/${orderId}`;
  const gqlUrl = `https://${shop}/admin/api/${SHOPIFY_API_VERSION}/graphql.json`;
  const headers = {
    'Content-Type': 'application/json',
    'X-Shopify-Access-Token': merchant.access_token,
  };

  // Fetch order status URL and mark as paid in parallel
  const [orderRes, paidRes] = await Promise.allSettled([
    fetch(
      `https://${shop}/admin/api/${SHOPIFY_API_VERSION}/orders/${orderId}.json?fields=order_status_url`,
      { headers: { 'X-Shopify-Access-Token': merchant.access_token } }
    ),
    fetch(gqlUrl, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        query: MARK_AS_PAID,
        variables: { input: { id: gid } },
      }),
    }),
  ]);

  // Log any errors from the mark-as-paid call (best-effort — don't block redirect)
  if (paidRes.status === 'fulfilled' && paidRes.value.ok) {
    const data = await paidRes.value.json().catch(() => null);
    const errors = data?.data?.orderMarkAsPaid?.userErrors ?? [];
    if (errors.length > 0) {
      console.error('orderMarkAsPaid userErrors', JSON.stringify(errors));
    }
  } else if (paidRes.status === 'rejected') {
    console.error('order-paid: Shopify API error', paidRes.reason);
  }

  // Redirect buyer to order status page, falling back to store homepage
  let redirectTo = `https://${shop}`;
  if (orderRes.status === 'fulfilled' && orderRes.value.ok) {
    const body = await orderRes.value.json().catch(() => null);
    if (body?.order?.order_status_url) {
      redirectTo = body.order.order_status_url;
    }
  }

  return Response.redirect(redirectTo, 302);
}
