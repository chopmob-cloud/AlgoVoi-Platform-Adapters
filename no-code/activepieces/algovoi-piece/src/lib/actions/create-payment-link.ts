import { createAction, Property } from '@activepieces/pieces-framework';
import { algovoiAuth, AlgovoiAuth } from '../../index';
import { NETWORK_OPTIONS, algovoiFetch } from '../common';

export const createPaymentLink = createAction({
  name: 'create_payment_link',
  auth: algovoiAuth,
  displayName: 'Create Payment Link',
  description: 'Creates a hosted AlgoVoi checkout URL. Share it with a customer — they pay with their crypto wallet.',
  props: {
    amount: Property.Number({
      displayName: 'Amount (USD)',
      description: 'Payment amount in USD (e.g. 5.00).',
      required: true,
    }),
    label: Property.ShortText({
      displayName: 'Payment Label',
      description: 'Description shown to the customer (e.g. "Premium access — 1 month").',
      required: true,
    }),
    network: Property.StaticDropdown({
      displayName: 'Network',
      description: 'Blockchain / asset the customer should pay on.',
      required: false,
      defaultValue: 'algorand_mainnet',
      options: { options: NETWORK_OPTIONS },
    }),
    currency: Property.ShortText({
      displayName: 'Base Currency',
      description: 'Fiat currency for the amount (3-letter code, default USD).',
      required: false,
      defaultValue: 'USD',
    }),
    redirect_url: Property.ShortText({
      displayName: 'Redirect URL',
      description: 'HTTPS URL to send the customer to after successful payment.',
      required: false,
    }),
  },

  async run(context) {
    const auth = context.auth as AlgovoiAuth;
    const { amount, label, network, currency, redirect_url } = context.propsValue;

    const body: Record<string, unknown> = {
      amount:            Math.round((amount ?? 0) * 100) / 100,
      currency:          (currency || 'USD').toUpperCase(),
      label:             (label || '').slice(0, 200),
      preferred_network: network || 'algorand_mainnet',
    };
    if (redirect_url) body.redirect_url = redirect_url;

    const resp = await algovoiFetch(auth, '/v1/payment-links', { method: 'POST', body }) as Record<string, unknown>;

    const url = String(resp.checkout_url || '');
    const tokenMatch = url.match(/\/checkout\/([A-Za-z0-9_-]+)$/);

    return {
      checkout_url:      url,
      token:             tokenMatch ? tokenMatch[1] : '',
      amount,
      currency:          (currency || 'USD').toUpperCase(),
      network:           network || 'algorand_mainnet',
      amount_microunits: resp.amount_microunits ?? 0,
    };
  },
});
