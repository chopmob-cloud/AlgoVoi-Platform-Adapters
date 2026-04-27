/**
 * /api/x402/session?shop=X&order_id=Y
 *
 * GET  → Returns HTTP 402 with X-Payment-Details header (x402 protocol).
 *         The AlgoVoi browser extension intercepts this and handles payment.
 *         Falls back gracefully — non-extension users see manual buttons.
 *
 * POST → Receives X-Payment header with tx proof from extension.
 *         Verifies tx on-chain, marks Shopify order as paid, returns order_status_url.
 *
 * OPTIONS → CORS preflight for extension cross-origin requests.
 */

const SHOPIFY_API_VERSION = '2024-01';
const APP_BASE            = 'https://worker.algovoi.co.uk';

// Algorand mainnet USDC asset ID
const ALGO_USDC_ASSET_ID = 31566704;

// Public indexers — no API key needed
const ALGO_INDEXER = 'https://mainnet-idx.algonode.cloud';
const VOI_INDEXER  = 'https://mainnet-idx.voi.nodly.io';

const CORS_HEADERS = {
  'Access-Control-Allow-Origin':   '*',
  'Access-Control-Allow-Methods':  'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers':  'Content-Type, X-Payment',
  'Access-Control-Expose-Headers': 'X-Payment-Details',
};

// ─── Helpers ────────────────────────────────────────────────────────────────

async function hmacHex(secret, message) {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    'raw', enc.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false, ['sign']
  );
  const buf = await crypto.subtle.sign('HMAC', key, enc.encode(message));
  return Array.from(new Uint8Array(buf))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
}

function json(body, status = 200, extra = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...CORS_HEADERS, ...extra },
  });
}

/**
 * Verify an Algorand/Voi asset transfer transaction via public indexer.
 * Returns true only if the tx:
 *   - Exists and is confirmed
 *   - Sent the correct asset to the merchant's receiving address
 *   - Amount >= expected (in base units, e.g. microUSDC)
 */
async function verifyTx({ txId, network, expectedAddress, expectedAssetId, expectedAmountBase }) {
  const indexer = network === 'voi' ? VOI_INDEXER : ALGO_INDEXER;
  try {
    const res = await fetch(`${indexer}/v2/transactions/${txId}`);
    if (!res.ok) return { ok: false, reason: `Indexer returned ${res.status}` };

    const { transaction } = await res.json();
    const axfer = transaction?.['asset-transfer-transaction'];

    if (!axfer) return { ok: false, reason: 'Not an asset transfer transaction' };

    if (axfer['asset-id'] !== expectedAssetId) {
      return { ok: false, reason: `Wrong asset: got ${axfer['asset-id']}, want ${expectedAssetId}` };
    }
    if (axfer.receiver !== expectedAddress) {
      return { ok: false, reason: `Wrong receiver: got ${axfer.receiver}` };
    }
    if (axfer.amount < expectedAmountBase) {
      return { ok: false, reason: `Underpayment: got ${axfer.amount}, need ${expectedAmountBase}` };
    }

    return { ok: true };
  } catch (e) {
    return { ok: false, reason: `Indexer error: ${e.message}` };
  }
}

const MARK_AS_PAID = `
  mutation orderMarkAsPaid($input: OrderMarkAsPaidInput!) {
    orderMarkAsPaid(input: $input) {
      order { id displayFinancialStatus }
      userErrors { field message }
    }
  }
`;

// ─── GET — return 402 with payment details ───────────────────────────────────

export async function onRequestGet(context) {
  const { searchParams } = new URL(context.request.url);
  const shop    = searchParams.get('shop');
  const orderId = searchParams.get('order_id');
  const chain   = (searchParams.get('chain') || 'algo').toLowerCase(); // algo | voi

  if (!shop || !orderId) {
    return json({ error: 'Missing shop or order_id' }, 400);
  }

  const merchant = await context.env.MERCHANTS.get(shop, 'json');
  if (!merchant?.access_token) {
    return json({ error: 'Merchant not configured' }, 404);
  }
  if (!merchant?.receiving_address) {
    return json({ error: 'Merchant receiving address not configured' }, 404);
  }

  // Fetch order amount from Shopify
  const orderRes = await fetch(
    `https://${shop}/admin/api/${SHOPIFY_API_VERSION}/orders/${orderId}.json?fields=total_price,currency,name,order_status_url`,
    { headers: { 'X-Shopify-Access-Token': merchant.access_token } }
  );
  if (!orderRes.ok) {
    return json({ error: 'Order not found' }, 404);
  }
  const { order } = await orderRes.json();

  // Amount in microUSDC (6 decimal places)
  const displayAmount  = parseFloat(order.total_price);
  const amountBase     = Math.round(displayAmount * 1_000_000);

  // Resolve asset ID: merchant can override per-chain in their config
  const assetId = chain === 'voi'
    ? (merchant.voi_usdc_asset_id ?? parseInt(context.env.VOI_USDC_ASSET_ID ?? '0'))
    : (merchant.algo_usdc_asset_id ?? ALGO_USDC_ASSET_ID);

  const network = chain === 'voi' ? 'voi-mainnet' : 'algorand-mainnet';

  // Pre-sign the callback so POST handler can verify without a second secret lookup
  const sig = await hmacHex(context.env.SHOPIFY_CLIENT_SECRET, `${shop}:${orderId}`);

  const paymentDetails = {
    version:           '1',
    scheme:            'exact',
    network,
    maxAmountRequired: String(amountBase),
    resource:          `${APP_BASE}/api/x402/session?shop=${encodeURIComponent(shop)}&order_id=${encodeURIComponent(orderId)}&chain=${chain}`,
    description:       `Order ${order.name || orderId} · ${shop.replace('.myshopify.com', '')}`,
    mimeType:          'application/json',
    payTo: [
      {
        scheme:            'exact',
        network,
        asset:             String(assetId),
        address:           merchant.receiving_address,
        maxAmountRequired: String(amountBase),
      },
    ],
    // Extra fields passed through by the extension in X-Payment header
    extra: {
      shop,
      order_id:         orderId,
      chain,
      sig,                      // ← extension echoes this back in POST body
      display_amount:   String(displayAmount),
      currency:         order.currency,
      order_status_url: order.order_status_url,
    },
  };

  return new Response(
    JSON.stringify({ error: 'Payment required', paymentDetails }),
    {
      status: 402,
      headers: {
        'Content-Type':      'application/json',
        'X-Payment-Details': JSON.stringify(paymentDetails),
        ...CORS_HEADERS,
      },
    }
  );
}

// ─── POST — receive payment proof, verify, mark order paid ──────────────────

export async function onRequestPost(context) {
  const { searchParams } = new URL(context.request.url);
  const shop    = searchParams.get('shop');
  const orderId = searchParams.get('order_id');
  const chain   = (searchParams.get('chain') || 'algo').toLowerCase();

  if (!shop || !orderId) {
    return json({ error: 'Missing shop or order_id' }, 400);
  }

  // Parse X-Payment header sent by the extension
  const xPaymentHeader = context.request.headers.get('X-Payment');
  if (!xPaymentHeader) {
    return json({ error: 'X-Payment header required' }, 402);
  }

  let xPayment;
  try { xPayment = JSON.parse(xPaymentHeader); } catch {
    return json({ error: 'Invalid X-Payment JSON' }, 400);
  }

  // Verify the HMAC sig that was embedded in paymentDetails.extra
  const sig         = xPayment?.extra?.sig ?? xPayment?.sig;
  const expected    = await hmacHex(context.env.SHOPIFY_CLIENT_SECRET, `${shop}:${orderId}`);
  if (!sig || sig !== expected) {
    return json({ error: 'Invalid payment signature' }, 403);
  }

  // Get tx proof
  const txId = xPayment?.txId ?? xPayment?.transaction_id ?? xPayment?.tx_id;
  if (!txId) {
    return json({ error: 'Missing transaction ID in X-Payment' }, 400);
  }

  const merchant = await context.env.MERCHANTS.get(shop, 'json');
  if (!merchant?.access_token || !merchant?.receiving_address) {
    return json({ error: 'Merchant not configured' }, 404);
  }

  // Fetch order to get the expected amount
  const orderRes = await fetch(
    `https://${shop}/admin/api/${SHOPIFY_API_VERSION}/orders/${orderId}.json?fields=total_price,currency,financial_status,order_status_url`,
    { headers: { 'X-Shopify-Access-Token': merchant.access_token } }
  );
  if (!orderRes.ok) return json({ error: 'Order not found' }, 404);
  const { order } = await orderRes.json();

  // Don't double-mark
  if (order.financial_status === 'paid') {
    return json({ success: true, already_paid: true, order_status_url: order.order_status_url });
  }

  const amountBase = Math.round(parseFloat(order.total_price) * 1_000_000);
  const assetId    = chain === 'voi'
    ? (merchant.voi_usdc_asset_id ?? parseInt(context.env.VOI_USDC_ASSET_ID ?? '0'))
    : (merchant.algo_usdc_asset_id ?? ALGO_USDC_ASSET_ID);

  // ── Verify transaction on-chain ────────────────────────────────────────────
  const verification = await verifyTx({
    txId,
    network:            chain,
    expectedAddress:    merchant.receiving_address,
    expectedAssetId:    assetId,
    expectedAmountBase: amountBase,
  });

  if (!verification.ok) {
    console.error(`x402 tx verification failed: ${verification.reason} txId=${txId}`);
    return json({ error: `Payment verification failed: ${verification.reason}` }, 402);
  }

  // ── Mark Shopify order as paid ─────────────────────────────────────────────
  const gqlRes = await fetch(
    `https://${shop}/admin/api/${SHOPIFY_API_VERSION}/graphql.json`,
    {
      method:  'POST',
      headers: {
        'Content-Type':          'application/json',
        'X-Shopify-Access-Token': merchant.access_token,
      },
      body: JSON.stringify({
        query:     MARK_AS_PAID,
        variables: { input: { id: `gid://shopify/Order/${orderId}` } },
      }),
    }
  );

  const gqlData   = await gqlRes.json();
  const userErrors = gqlData?.data?.orderMarkAsPaid?.userErrors ?? [];
  if (userErrors.length > 0) {
    console.error('orderMarkAsPaid userErrors', JSON.stringify(userErrors));
    return json({ error: userErrors[0].message }, 422);
  }

  console.log(`x402 payment verified and order ${orderId} marked paid. txId=${txId}`);

  return json({
    success:          true,
    txId,
    order_status_url: order.order_status_url,
  });
}

// ─── OPTIONS — CORS preflight ────────────────────────────────────────────────

export async function onRequestOptions() {
  return new Response(null, { status: 204, headers: CORS_HEADERS });
}
