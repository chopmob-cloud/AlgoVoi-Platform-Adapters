import { createTrigger, TriggerStrategy, Property } from '@activepieces/pieces-framework';
import { algovoiAuth, AlgovoiAuth } from '../../index';
import { authHeaders, getApiBase } from '../common';

export const paymentConfirmed = createTrigger({
  name: 'payment_confirmed',
  auth: algovoiAuth,
  displayName: 'Payment Confirmed',
  description: 'Triggers instantly when an AlgoVoi crypto payment is confirmed on-chain.',
  props: {
    network_filter: Property.ShortText({
      displayName: 'Network Filter (optional)',
      description: 'Only trigger for this network (e.g. algorand_mainnet). Leave blank for all networks.',
      required: false,
    }),
  },
  type: TriggerStrategy.WEBHOOK,
  sampleData: {
    event_id:   'evt_sample_001',
    event_type: 'payment.confirmed',
    status:     'paid',
    token:      'abc123',
    amount:     5.0,
    currency:   'USD',
    network:    'algorand_mainnet',
    tx_id:      'ABC123TXID',
    order_id:   'order_001',
    payer:      'ALGO_WALLET_ADDRESS',
    created_at: 1713400000,
  },

  async onEnable(context) {
    const auth = context.auth as AlgovoiAuth;
    const base = getApiBase(auth);

    const resp = await fetch(`${base}/v1/webhooks`, {
      method: 'POST',
      headers: authHeaders(auth),
      body: JSON.stringify({
        url:   context.webhookUrl,
        event: 'payment.confirmed',
      }),
    });

    if (!resp.ok) throw new Error(`Failed to register webhook: ${resp.status}`);
    const data = await resp.json() as Record<string, unknown>;
    await context.store.put('webhook_id', data.id);
  },

  async onDisable(context) {
    const auth = context.auth as AlgovoiAuth;
    const base = getApiBase(auth);
    const webhookId = await context.store.get<string>('webhook_id');

    if (webhookId) {
      await fetch(`${base}/v1/webhooks/${webhookId}`, {
        method:  'DELETE',
        headers: authHeaders(auth),
      });
    }
  },

  async run(context) {
    const payload = context.payload.body as Record<string, unknown>;
    const networkFilter = context.propsValue.network_filter;

    // Filter by network if specified
    if (networkFilter && payload.network && payload.network !== networkFilter) {
      return [];
    }

    return [payload];
  },
});
