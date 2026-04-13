const CHAIN_TO_NETWORK = {
  ALGO: 'algorand_mainnet',
  VOI:  'voi_mainnet',
  XLM:  'stellar_mainnet',
  HBAR: 'hedera_mainnet',
};

const GATEWAY_URL = 'https://api1.ilovechicken.co.uk';

function cors() {
  return {
    'Access-Control-Allow-Origin':  '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };
}

export async function onRequestPost(context) {
  const { chain, amount, currency, tenantId, apiKey } = await context.request.json();

  if (!tenantId || !apiKey) {
    return Response.json({ error: 'Missing tenant-id or api-key' }, { status: 400, headers: cors() });
  }

  const network = CHAIN_TO_NETWORK[chain?.toUpperCase()];
  if (!network) {
    return Response.json({ error: `Unsupported chain: ${chain}` }, { status: 400, headers: cors() });
  }

  const res = await fetch(`${GATEWAY_URL}/v1/payment-links`, {
    method: 'POST',
    headers: {
      'Content-Type':  'application/json',
      'Authorization': `Bearer ${apiKey}`,
      'X-Tenant-Id':   tenantId,
    },
    body: JSON.stringify({
      amount:             parseFloat(amount),
      currency:           (currency || 'USD').toUpperCase(),
      label:              `${chain} payment`,
      preferred_network:  network,
      expires_in_seconds: 1800,
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    return Response.json({ error: err }, { status: res.status, headers: cors() });
  }

  const { checkout_url } = await res.json();
  return Response.json({ checkout_url }, { headers: cors() });
}

export async function onRequestOptions() {
  return new Response(null, { headers: cors() });
}
