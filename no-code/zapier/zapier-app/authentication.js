'use strict';

const API_BASE = 'https://api1.ilovechicken.co.uk';

// Test the connection by hitting a lightweight endpoint.
// A 401/403 = bad creds; 200 or 404 = creds are valid.
const testAuth = async (z, bundle) => {
  const response = await z.request({
    url: `${API_BASE}/v1/verify`,
    method: 'GET',
    headers: {
      Authorization: `Bearer ${bundle.authData.api_key}`,
      'X-Tenant-Id': bundle.authData.tenant_id,
    },
    params: { token: '_auth_test_' },
    throwForStatus: false,
  });
  // 404 = token not found (auth valid), 401/403 = bad creds
  if (response.status === 401 || response.status === 403) {
    throw new z.errors.Error('Invalid API key or Tenant ID. Check your AlgoVoi credentials.', 'AuthenticationError', response.status);
  }
  return response.json || { ok: true };
};

const authentication = {
  type: 'custom',
  test: testAuth,
  fields: [
    {
      key: 'api_key',
      label: 'API Key',
      required: true,
      type: 'password',
      helpText:
        'Your AlgoVoi API key (starts with `algv_`). Find it at **app.algovoi.com → Settings → API Keys**.',
    },
    {
      key: 'tenant_id',
      label: 'Tenant ID',
      required: true,
      type: 'string',
      helpText: 'Your AlgoVoi tenant UUID. Find it at **app.algovoi.com → Settings**.',
    },
    {
      key: 'payout_algorand',
      label: 'Payout Address — Algorand',
      required: false,
      type: 'string',
      helpText: 'Algorand wallet address for ALGO / USDC payouts (58-char base32).',
    },
    {
      key: 'payout_voi',
      label: 'Payout Address — VOI',
      required: false,
      type: 'string',
      helpText: 'VOI wallet address for VOI / aUSDC payouts.',
    },
    {
      key: 'payout_hedera',
      label: 'Payout Address — Hedera',
      required: false,
      type: 'string',
      helpText: 'Hedera account ID for HBAR / USDC payouts (e.g. `0.0.123456`).',
    },
    {
      key: 'payout_stellar',
      label: 'Payout Address — Stellar',
      required: false,
      type: 'string',
      helpText: 'Stellar public key for XLM / USDC payouts (starts with `G`).',
    },
    {
      key: 'webhook_secret',
      label: 'Webhook Secret',
      required: false,
      type: 'password',
      helpText:
        'AlgoVoi webhook signing secret for HMAC-SHA256 signature verification. ' +
        'Found in **AlgoVoi Dashboard → Settings → Webhooks**.',
    },
  ],
  connectionLabel: 'Tenant {{bundle.authData.tenant_id}}',
};

module.exports = authentication;
