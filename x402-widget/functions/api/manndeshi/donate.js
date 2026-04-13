/**
 * POST /api/manndeshi/donate
 *
 * Creates a $2.75 USDC (Algorand) AlgoVoi payment link for the
 * Manndeshi Foundation donation widget.
 *
 * Env vars (set via wrangler secret put):
 *   GATEWAY_URL        — AlgoVoi API base (default: https://api1.ilovechicken.co.uk)
 *   GATEWAY_API_KEY    — AlgoVoi Bearer token
 *   GATEWAY_TENANT_ID  — AlgoVoi tenant UUID
 */

const DONATION_AMOUNT   = 2.75;
const DONATION_CURRENCY = 'USD';
const DONATION_NETWORK  = 'algorand_mainnet';
const DONATION_LABEL    = 'manndeshi | Manndeshi Foundation $2.75 USDC donation';
const EXPIRES_SECONDS   = 3600; // 1 hour

export async function onRequestPost(context) {
  const gatewayUrl = context.env.GATEWAY_URL    ?? 'https://api1.ilovechicken.co.uk';
  const apiKey     = context.env.GATEWAY_API_KEY;
  const tenantId   = context.env.GATEWAY_TENANT_ID;

  if (!apiKey || !tenantId) {
    return Response.json(
      { error: 'Donation service not configured.' },
      { status: 503, headers: cors() }
    );
  }

  const res = await fetch(`${gatewayUrl}/v1/payment-links`, {
    method:  'POST',
    headers: {
      'Content-Type':  'application/json',
      'Authorization': `Bearer ${apiKey}`,
      'X-Tenant-Id':   tenantId,
    },
    body: JSON.stringify({
      amount:             DONATION_AMOUNT,
      currency:           DONATION_CURRENCY,
      label:              DONATION_LABEL,
      preferred_network:  DONATION_NETWORK,
      expires_in_seconds: EXPIRES_SECONDS,
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    console.error('AlgoVoi payment-links error:', res.status, err);
    return Response.json(
      { error: 'Could not create payment link. Please try again.' },
      { status: 502, headers: cors() }
    );
  }

  const { checkout_url } = await res.json();

  return Response.json(
    { checkout_url },
    { headers: cors() }
  );
}

export async function onRequestOptions() {
  return new Response(null, { headers: cors() });
}

function cors() {
  return {
    'Access-Control-Allow-Origin':  '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };
}
