/**
 * GET /auth/install?shop=mystore.myshopify.com
 * Starts the Shopify OAuth flow.
 */

const SHOPIFY_CLIENT_ID = 'YOUR_SHOPIFY_CLIENT_ID';
const SCOPES            = 'read_orders,write_orders';
const REDIRECT_URI      = 'https://worker.algovoi.co.uk/auth/callback';

export async function onRequestGet(context) {
  const { searchParams } = new URL(context.request.url);
  const shop = searchParams.get('shop');

  if (!shop || !shop.endsWith('.myshopify.com')) {
    return new Response('Invalid shop domain', { status: 400 });
  }

  const state = crypto.randomUUID();
  const installUrl = `https://${shop}/admin/oauth/authorize?client_id=${SHOPIFY_CLIENT_ID}&scope=${SCOPES}&redirect_uri=${encodeURIComponent(REDIRECT_URI)}&state=${state}&grant_options[]=per-user`;

  return Response.redirect(installUrl, 302);
}
