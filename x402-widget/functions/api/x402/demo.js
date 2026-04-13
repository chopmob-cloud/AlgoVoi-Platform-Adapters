const CHAIN_TO_NETWORK = {
  ALGO: 'algorand_mainnet',
  VOI:  'voi_mainnet',
  XLM:  'stellar_mainnet',
  HBAR: 'hedera_mainnet',
};

export async function onRequestPost(context) {
  const { chain, amount } = await context.request.json();

  const network = CHAIN_TO_NETWORK[chain?.toUpperCase()];
  if (!network) {
    return Response.json({ error: `Unsupported chain: ${chain}` }, { status: 400 });
  }

  const gatewayUrl = context.env.GATEWAY_URL ?? 'https://api1.ilovechicken.co.uk';
  const apiKey     = context.env.GATEWAY_API_KEY;
  const tenantId   = context.env.GATEWAY_TENANT_ID;

  const res = await fetch(`${gatewayUrl}/v1/payment-links`, {
    method: 'POST',
    headers: {
      'Content-Type':  'application/json',
      'Authorization': `Bearer ${apiKey}`,
      'X-Tenant-Id':   tenantId,
    },
    body: JSON.stringify({
      amount:            parseFloat(amount),
      currency:          'GBP',
      label:             `${chain} payment`,
      preferred_network: network,
      expires_in_seconds: 1800,
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    return Response.json({ error: err }, { status: res.status });
  }

  const { checkout_url } = await res.json();
  return Response.json({ checkout_url }, {
    headers: { 'Access-Control-Allow-Origin': '*' },
  });
}

export async function onRequestOptions() {
  return new Response(null, {
    headers: {
      'Access-Control-Allow-Origin':  '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    },
  });
}
