'use strict';

const API_BASE = 'https://api1.ilovechicken.co.uk';

const SUPPORTED_NETWORKS = [
  { value: 'algorand_mainnet',      label: 'Algorand — USDC',          sample: 'algorand_mainnet' },
  { value: 'voi_mainnet',           label: 'VOI — aUSDC',              sample: 'voi_mainnet' },
  { value: 'hedera_mainnet',        label: 'Hedera — USDC',            sample: 'hedera_mainnet' },
  { value: 'stellar_mainnet',       label: 'Stellar — USDC',           sample: 'stellar_mainnet' },
  { value: 'algorand_mainnet_algo', label: 'Algorand — ALGO (native)', sample: 'algorand_mainnet_algo' },
  { value: 'voi_mainnet_voi',       label: 'VOI — VOI (native)',        sample: 'voi_mainnet_voi' },
  { value: 'hedera_mainnet_hbar',   label: 'Hedera — HBAR (native)',   sample: 'hedera_mainnet_hbar' },
  { value: 'stellar_mainnet_xlm',   label: 'Stellar — XLM (native)',   sample: 'stellar_mainnet_xlm' },
  { value: 'algorand_testnet',      label: 'Algorand Testnet — USDC',  sample: 'algorand_testnet' },
  { value: 'voi_testnet',           label: 'VOI Testnet — aUSDC',      sample: 'voi_testnet' },
  { value: 'hedera_testnet',        label: 'Hedera Testnet — USDC',    sample: 'hedera_testnet' },
  { value: 'stellar_testnet',       label: 'Stellar Testnet — USDC',   sample: 'stellar_testnet' },
];

const perform = async (z, bundle) => {
  const body = {
    amount:            parseFloat(bundle.inputData.amount),
    currency:          (bundle.inputData.currency || 'USD').toUpperCase(),
    label:             bundle.inputData.label,
    preferred_network: bundle.inputData.network || 'algorand_mainnet',
  };

  if (bundle.inputData.redirect_url) {
    body.redirect_url       = bundle.inputData.redirect_url;
    body.expires_in_seconds = 3600;
  }

  const response = await z.request({
    url: `${API_BASE}/v1/payment-links`,
    method: 'POST',
    headers: {
      Authorization: `Bearer ${bundle.authData.api_key}`,
      'X-Tenant-Id': bundle.authData.tenant_id,
    },
    body,
  });

  const data = response.data;
  // Extract token from checkout URL
  const tokenMatch = (data.checkout_url || '').match(/\/checkout\/([A-Za-z0-9_-]+)$/);
  const token = tokenMatch ? tokenMatch[1] : '';

  return {
    checkout_url:      data.checkout_url,
    token,
    amount:            body.amount,
    currency:          body.currency,
    network:           body.preferred_network,
    amount_microunits: data.amount_microunits || 0,
  };
};

module.exports = {
  key: 'create_payment_link',
  noun: 'Payment Link',

  display: {
    label: 'Create Payment Link',
    description:
      'Creates a hosted AlgoVoi checkout link. Share it via email, SMS, or social media — ' +
      'the customer pays with their crypto wallet, no account required.',
  },

  operation: {
    perform,
    inputFields: [
      {
        key:      'amount',
        label:    'Amount (USD)',
        type:     'number',
        required: true,
        helpText: 'Payment amount in USD (e.g. `5.00`). AlgoVoi converts to the correct crypto amount.',
      },
      {
        key:      'label',
        label:    'Payment Label',
        type:     'string',
        required: true,
        helpText: 'Description shown to the customer on the checkout page (e.g. "Premium access — 1 month").',
      },
      {
        key:         'network',
        label:       'Preferred Network',
        type:        'string',
        required:    false,
        default:     'algorand_mainnet',
        choices:     SUPPORTED_NETWORKS,
        helpText:    'Which blockchain / asset the customer should pay on.',
      },
      {
        key:      'currency',
        label:    'Base Currency',
        type:     'string',
        required: false,
        default:  'USD',
        helpText: 'Fiat currency for the amount (3-letter code). Default: USD.',
      },
      {
        key:      'redirect_url',
        label:    'Redirect URL (after payment)',
        type:     'string',
        required: false,
        helpText: 'HTTPS URL to redirect the customer to after a successful payment.',
      },
    ],

    sample: {
      checkout_url:      'https://pay.algovoi.com/c/abc123',
      token:             'abc123',
      amount:            5.0,
      currency:          'USD',
      network:           'algorand_mainnet',
      amount_microunits: 5000000,
    },

    outputFields: [
      { key: 'checkout_url',      label: 'Checkout URL' },
      { key: 'token',             label: 'Checkout Token' },
      { key: 'amount',            label: 'Amount (USD)',      type: 'number' },
      { key: 'currency',          label: 'Currency' },
      { key: 'network',           label: 'Network' },
      { key: 'amount_microunits', label: 'Amount (microunits)', type: 'integer' },
    ],
  },
};
