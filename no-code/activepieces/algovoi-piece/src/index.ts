import { createPiece, PieceAuth } from '@activepieces/pieces-framework';
import { createPaymentLink } from './lib/actions/create-payment-link';
import { verifyPayment } from './lib/actions/verify-payment';
import { listNetworks } from './lib/actions/list-networks';
import { paymentConfirmed } from './lib/triggers/payment-confirmed';

export const algovoiAuth = PieceAuth.CustomAuth({
  description: `
**AlgoVoi** lets you accept crypto payments on Algorand, VOI, Hedera, and Stellar.

Get your API key and Tenant ID from [dash.algovoi.co.uk](https://dash.algovoi.co.uk) → Settings.

**Tip:** Point the API Base URL at \`https://cloud.algovoi.co.uk\` to have AlgoVoi Cloud manage payouts centrally — no Tenant ID or payout addresses needed. For direct API access use \`https://api1.ilovechicken.co.uk\` with all fields filled.
  `,
  props: {
    api_key: PieceAuth.SecretText({
      displayName: 'API Key',
      description: 'Your AlgoVoi API key (starts with algv_). Found in dash.algovoi.co.uk → Settings.',
      required: true,
    }),
    tenant_id: PieceAuth.ShortText({
      displayName: 'Tenant ID',
      description: 'Your AlgoVoi tenant UUID. Found in dash.algovoi.co.uk → Settings.',
      required: true,
    }),
    payout_algorand: PieceAuth.ShortText({
      displayName: 'Payout Address — Algorand',
      description: 'Algorand wallet address for USDC / ALGO payouts (58-char base32). Required for Algorand payments.',
      required: false,
    }),
    payout_voi: PieceAuth.ShortText({
      displayName: 'Payout Address — VOI',
      description: 'VOI wallet address for aUSDC / VOI payouts.',
      required: false,
    }),
    payout_hedera: PieceAuth.ShortText({
      displayName: 'Payout Address — Hedera',
      description: 'Hedera account ID for USDC / HBAR payouts (e.g. 0.0.123456).',
      required: false,
    }),
    payout_stellar: PieceAuth.ShortText({
      displayName: 'Payout Address — Stellar',
      description: 'Stellar public key for USDC / XLM payouts (starts with G).',
      required: false,
    }),
    webhook_secret: PieceAuth.SecretText({
      displayName: 'Webhook Secret',
      description: 'AlgoVoi webhook signing secret for HMAC-SHA256 verification. Found in Settings → Webhooks.',
      required: false,
    }),
    api_base: PieceAuth.ShortText({
      displayName: 'API Base URL',
      description: 'AlgoVoi API base URL. Leave blank for default (https://api1.ilovechicken.co.uk).',
      required: false,
    }),
  },
  validate: async ({ auth }) => {
    const base = (auth.api_base || 'https://api1.ilovechicken.co.uk').replace(/\/$/, '');
    try {
      const resp = await fetch(`${base}/v1/networks`, {
        headers: {
          Authorization: `Bearer ${auth.api_key}`,
          'X-Tenant-Id': auth.tenant_id,
        },
      });
      if (resp.status === 401) return { valid: false, error: 'Invalid API key or Tenant ID.' };
      if (!resp.ok) return { valid: false, error: `AlgoVoi API returned ${resp.status}.` };
      return { valid: true };
    } catch {
      return { valid: false, error: 'Could not reach AlgoVoi API. Check the API Base URL.' };
    }
  },
});

export const algovoi = createPiece({
  displayName: 'AlgoVoi',
  auth: algovoiAuth,
  minimumSupportedRelease: '0.20.0',
  logoUrl: 'https://raw.githubusercontent.com/chopmob-cloud/AlgoVoi-Platform-Adapters/master/assets/algovoi-logo.png',
  authors: ['algovoi'],
  actions: [createPaymentLink, verifyPayment, listNetworks],
  triggers: [paymentConfirmed],
});
