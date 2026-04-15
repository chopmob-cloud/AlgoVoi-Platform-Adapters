const CHAIN_TO_NETWORK = {
  ALGO: 'algorand_mainnet',
  VOI:  'voi_mainnet',
  XLM:  'stellar_mainnet',
  HBAR: 'hedera_mainnet',
};

function cors() {
  return {
    'Access-Control-Allow-Origin':  '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };
}

export async function onRequestPost(context) {
  const { chain, amount, currency } = await context.request.json();

  const network = CHAIN_TO_NETWORK[chain?.toUpperCase()];
  if (!network) {
    return Response.json({ error: `Unsupported chain: ${chain}` }, { status: 400, headers: cors() });
  }

  const gatewayUrl = context.env.GATEWAY_URL    ?? 'https://api1.ilovechicken.co.uk';
  const apiKey     = context.env.GATEWAY_API_KEY;
  const tenantId   = context.env.GATEWAY_TENANT_ID;

  if (!apiKey || !tenantId) {
    return Response.json({ error: 'Demo service not configured.' }, { status: 503, headers: cors() });
  }

  const res = await fetch(`${gatewayUrl}/v1/payment-links`, {
    method: 'POST',
    headers: {
      'Content-Type':  'application/json',
      'Authorization': `Bearer ${apiKey}`,
      'X-Tenant-Id':   tenantId,
    },
    body: JSON.stringify({
      amount:             parseFloat(amount),
      currency:           (currency || 'USD').toUpperCase(),
      label:              `${chain} demo payment`,
      preferred_network:  network,
      expires_in_seconds: 1800,
    }),
  });

  if (!res.ok) {
    let errMsg;
    try {
      const errJson = await res.json();
      errMsg = errJson.detail || errJson.message || errJson.error || `Server error ${res.status}`;
    } catch {
      errMsg = `Server error ${res.status}`;
    }
    return Response.json({ error: errMsg }, { status: res.status, headers: cors() });
  }

  const { checkout_url } = await res.json();
  return Response.json({ checkout_url }, { headers: cors() });
}

export async function onRequestOptions() {
  return new Response(null, { headers: cors() });
}
