import { createAction, Property } from '@activepieces/pieces-framework';
import { algovoiAuth, AlgovoiAuth } from '../../index';
import { algovoiFetch } from '../common';

export const verifyPayment = createAction({
  name: 'verify_payment',
  auth: algovoiAuth,
  displayName: 'Verify Payment',
  description: 'Checks whether an AlgoVoi checkout token has been paid on-chain.',
  props: {
    token: Property.ShortText({
      displayName: 'Checkout Token',
      description: 'The checkout token from a Create Payment Link action or AlgoVoi webhook payload.',
      required: true,
    }),
  },

  async run(context) {
    const auth = context.auth as AlgovoiAuth;
    const { token } = context.propsValue;

    const resp = await algovoiFetch(
      auth,
      `/checkout/${encodeURIComponent(token ?? '')}/status`,
    ) as Record<string, unknown>;

    const status = String(resp.status || 'unknown');
    return {
      token,
      paid:   ['paid', 'completed', 'confirmed'].includes(status),
      status,
      tx_id:  resp.tx_id ?? null,
      payer:  resp.payer ?? null,
    };
  },
});
