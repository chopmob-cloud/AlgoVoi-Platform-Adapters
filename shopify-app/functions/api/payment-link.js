/**
 * GET /api/payment-link?shop=mystore.myshopify.com&order_id=12345
 * Returns payment links for all supported chains.
 */

const ALGOVOI_API = 'https://api1.ilovechicken.co.uk';

const CHAINS = [
  { key: 'ALGO',  label: 'Pay with USDC (Algorand)', network: 'algorand_mainnet' },
  { key: 'VOI',   label: 'Pay with aUSDC (Voi)',     network: 'voi_mainnet'      },
  { key: 'HBAR',  label: 'Pay with USDC (Hedera)',   network: 'hedera_mainnet'   },
  { key: 'XLM',   label: 'Pay with USDC (Stellar)',  network: 'stellar_mainnet'  },
  { key: 'BASE',  label: 'Pay with USDC (Base)',     network: 'base_mainnet'     },
  { key: 'SOL',   label: 'Pay with USDC (Solana)',   network: 'solana_mainnet'   },
  { key: 'TEMPO', label: 'Pay with USDCe (Tempo)',   network: 'tempo_mainnet'    },
];

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

function json(data, status = 200) {
  return Response.json(data, { status, headers: CORS });
}

export async function onRequestOptions() {
  return new Response(null, { status: 204, headers: CORS });
}

export async function onRequestGet(context) {
  const { searchParams } = new URL(context.request.url);
  const shop    = searchParams.get('shop');
  const orderId = searchParams.get('order_id');

  if (!shop || !orderId) {
    return json({ error: 'Missing shop or order_id' }, 400);
  }

  const merchant = await context.env.MERCHANTS.get(shop, 'json');
  if (!merchant?.access_token || !merchant?.api_key || !merchant?.tenant_id) {
    return json({ error: 'Merchant not configured' }, 404);
  }

  // Fetch order details from Shopify
  const orderRes = await fetch(
    `https://${shop}/admin/api/2024-01/orders/${orderId}.json`,
    { headers: { 'X-Shopify-Access-Token': merchant.access_token }, signal: AbortSignal.timeout(10000) }
  );
  if (!orderRes.ok) {
    return json({ error: 'Order not found' }, 404);
  }

  const { order } = await orderRes.json();
  const amount   = parseFloat(order.total_price);
  const currency = order.currency || 'GBP';

  // Create a payment link for each chain in parallel
  const results = await Promise.all(
    CHAINS.map(async ({ key, label, network }) => {
      try {
        const res = await fetch(`${ALGOVOI_API}/v1/payment-links`, {
          method: 'POST',
          headers: {
            'Content-Type':  'application/json',
            'Authorization': `Bearer ${merchant.api_key}`,
            'X-Tenant-Id':   merchant.tenant_id,
          },
          body: JSON.stringify({
            amount,
            currency,
            label:              `Order ${order.name} — ${key}`,
            preferred_network:  network,
            expires_in_seconds: 1800,
            metadata: { order_id: String(orderId), shop },
          }),
          signal: AbortSignal.timeout(10000),
        });
        if (!res.ok) {
          const errText = await res.text();
          return { key, label, error: true, detail: errText };
        }
        const link = await res.json();
        return { key, label, checkout_url: link.checkout_url };
      } catch (_) {
        return { key, label, error: true };
      }
    })
  );

  return json({ order_name: order.name, chains: results });
}
