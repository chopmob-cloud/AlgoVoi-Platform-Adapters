/**
 * GET /auth/callback
 * Shopify redirects here after merchant approves the app.
 * Exchanges the code for a permanent access token, stores merchant credentials,
 * registers the orders/create webhook with AlgoVoi.
 */

const SHOPIFY_CLIENT_ID     = 'YOUR_SHOPIFY_CLIENT_ID';
const ALGOVOI_GATEWAY       = 'https://api1.ilovechicken.co.uk';

export async function onRequestGet(context) {
  const { searchParams } = new URL(context.request.url);
  const shop  = searchParams.get('shop');
  const code  = searchParams.get('code');
  const state = searchParams.get('state');

  if (!shop || !code) {
    return new Response('Missing shop or code', { status: 400 });
  }

  // Exchange code for access token
  const tokenRes = await fetch(`https://${shop}/admin/oauth/access_token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      client_id:     SHOPIFY_CLIENT_ID,
      client_secret: context.env.SHOPIFY_CLIENT_SECRET,
      code,
    }),
  });

  if (!tokenRes.ok) {
    const errBody = await tokenRes.text();
    return new Response(`Failed to get access token: HTTP ${tokenRes.status} — ${errBody}`, { status: 500 });
  }

  const { access_token } = await tokenRes.json();

  // Load existing merchant data if any (preserve AlgoVoi credentials)
  const existing = await context.env.MERCHANTS.get(shop, 'json') || {};
  await context.env.MERCHANTS.put(shop, JSON.stringify({
    ...existing,
    shop,
    access_token,
    connected_at: new Date().toISOString(),
  }));

  // Redirect to settings page
  return Response.redirect(`https://worker.algovoi.co.uk/?shop=${shop}&installed=1`, 302);
}
