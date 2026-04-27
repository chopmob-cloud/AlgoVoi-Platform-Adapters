/**
 * POST /api/connect
 * Merchant submits their AlgoVoi tenant ID + API key.
 * 1. Verifies AlgoVoi credentials
 * 2. Registers Shopify integration on the AlgoVoi platform
 * 3. Registers orders/create webhook with Shopify
 */

const APP_WEBHOOK_URL = 'https://worker.algovoi.co.uk/webhooks/shopify';
const ALGOVOI_API     = 'https://api1.ilovechicken.co.uk';

export async function onRequestPost(context) {
  const { shop, tenantId, apiKey } = await context.request.json();

  if (!shop || !tenantId || !apiKey) {
    return Response.json({ error: 'Missing shop, tenantId or apiKey' }, { status: 400 });
  }

  // Load merchant record (must have been through OAuth first)
  const merchant = await context.env.MERCHANTS.get(shop, 'json');
  if (!merchant?.access_token) {
    return Response.json({ error: 'Shop not installed — complete OAuth first' }, { status: 404 });
  }

  // Verify AlgoVoi credentials work
  const testRes = await fetch(`${ALGOVOI_API}/v1/payment-links`, {
    method: 'POST',
    headers: {
      'Content-Type':  'application/json',
      'Authorization': `Bearer ${apiKey}`,
      'X-Tenant-Id':   tenantId,
    },
    body: JSON.stringify({ amount: 0.01, currency: 'GBP', label: 'connection test', expires_in_seconds: 60 }),
  });

  if (!testRes.ok) {
    return Response.json({ error: 'Invalid AlgoVoi credentials' }, { status: 401 });
  }

  // Register Shopify integration on the AlgoVoi platform
  const adminKey = context.env.ALGOVOI_ADMIN_KEY;
  let webhookSecret = null;

  if (adminKey) {
    const integrationRes = await fetch(`${ALGOVOI_API}/api/integrations/${tenantId}/shopify`, {
      method: 'POST',
      headers: {
        'Content-Type':  'application/json',
        'Authorization': `Bearer ${adminKey}`,
      },
      body: JSON.stringify({
        credentials: {
          shop_domain:   shop,
          access_token:  merchant.access_token,
        },
        shop_identifier:   shop,
        base_currency:     'GBP',
        preferred_network: 'algorand_mainnet',
      }),
    });

    if (integrationRes.ok) {
      const integration = await integrationRes.json();
      webhookSecret = integration.webhook_secret;
    }
  }

  // Register orders/create webhook with Shopify (idempotent — 422 means already exists)
  const whRes = await fetch(`https://${shop}/admin/api/2024-01/webhooks.json`, {
    method: 'POST',
    headers: {
      'Content-Type':           'application/json',
      'X-Shopify-Access-Token': merchant.access_token,
    },
    body: JSON.stringify({
      webhook: {
        topic:   'orders/create',
        address: APP_WEBHOOK_URL,
        format:  'json',
      },
    }),
  });

  const webhookOk = whRes.ok || whRes.status === 422; // 422 = already registered

  // Save merchant credentials
  await context.env.MERCHANTS.put(shop, JSON.stringify({
    ...merchant,
    tenant_id:          tenantId,
    api_key:            apiKey,
    webhook_secret:     webhookSecret,
    webhook_registered: webhookOk,
    updated_at:         new Date().toISOString(),
  }));

  return Response.json({
    ok: true,
    webhook_registered:     webhookOk,
    integration_registered: !!webhookSecret,
    message: 'Connected successfully',
  });
}
