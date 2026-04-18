'use strict';

const API_BASE = 'https://api1.ilovechicken.co.uk';

// ── REST-hook lifecycle ────────────────────────────────────────────────────────

const subscribeHook = async (z, bundle) => {
  const response = await z.request({
    url: `${API_BASE}/v1/webhooks`,
    method: 'POST',
    headers: {
      Authorization: `Bearer ${bundle.authData.api_key}`,
      'X-Tenant-Id': bundle.authData.tenant_id,
    },
    body: {
      url: bundle.targetUrl,
      event: 'payment.confirmed',
    },
  });
  return response.data;
};

const unsubscribeHook = async (z, bundle) => {
  const hookId = bundle.subscribeData.id;
  if (!hookId) return {};
  const response = await z.request({
    url: `${API_BASE}/v1/webhooks/${hookId}`,
    method: 'DELETE',
    headers: {
      Authorization: `Bearer ${bundle.authData.api_key}`,
      'X-Tenant-Id': bundle.authData.tenant_id,
    },
  });
  return response.data;
};

// ── Incoming webhook processor ─────────────────────────────────────────────────

const processWebhook = (z, bundle) => {
  const payload = bundle.cleanedRequest;
  return [
    {
      id:           payload.event_id || payload.id || String(Date.now()),
      event_type:   payload.event_type || payload.type || 'payment.confirmed',
      status:       payload.status || 'paid',
      token:        payload.token || '',
      amount:       payload.amount || 0,
      currency:     payload.currency || 'USD',
      network:      payload.network || '',
      tx_id:        payload.tx_id || '',
      order_id:     payload.order_id || payload.reference || '',
      payer:        payload.payer || payload.sender || '',
      created_at:   payload.created_at || Math.floor(Date.now() / 1000),
    },
  ];
};

// ── Fallback list (used during Zap testing when no real hook has fired) ────────

const getFallbackList = async (z, bundle) => {
  return [
    {
      id:         'evt_sample_001',
      event_type: 'payment.confirmed',
      status:     'paid',
      token:      'sample_checkout_token',
      amount:     5.0,
      currency:   'USD',
      network:    'algorand_mainnet',
      tx_id:      'SAMPLETXID123456789',
      order_id:   'order_001',
      payer:      'ALGORAND_ADDRESS_HERE',
      created_at: 1713400000,
    },
  ];
};

// ── Module definition ─────────────────────────────────────────────────────────

module.exports = {
  key: 'payment_confirmed',
  noun: 'Payment',

  display: {
    label: 'Payment Confirmed',
    description:
      'Triggers instantly when an AlgoVoi crypto payment is confirmed on-chain. ' +
      'Supports USDC and native tokens on Algorand, VOI, Hedera, and Stellar.',
    important: true,
  },

  operation: {
    type: 'hook',
    performSubscribe:   subscribeHook,
    performUnsubscribe: unsubscribeHook,
    perform:            processWebhook,
    performList:        getFallbackList,

    sample: {
      id:         'evt_sample_001',
      event_type: 'payment.confirmed',
      status:     'paid',
      token:      'abc123token',
      amount:     5.0,
      currency:   'USD',
      network:    'algorand_mainnet',
      tx_id:      'ABC123TXID',
      order_id:   'order_001',
      payer:      'ALGOADDRESS',
      created_at: 1713400000,
    },

    outputFields: [
      { key: 'id',         label: 'Event ID' },
      { key: 'event_type', label: 'Event Type' },
      { key: 'status',     label: 'Payment Status' },
      { key: 'token',      label: 'Checkout Token' },
      { key: 'amount',     label: 'Amount (USD)',          type: 'number' },
      { key: 'currency',   label: 'Currency' },
      { key: 'network',    label: 'Network' },
      { key: 'tx_id',      label: 'Transaction ID' },
      { key: 'order_id',   label: 'Order / Reference ID' },
      { key: 'payer',      label: 'Payer Address' },
      { key: 'created_at', label: 'Timestamp (Unix)',      type: 'integer' },
    ],
  },
};
