import { createAction } from '@activepieces/pieces-framework';
import { algovoiAuth, AlgovoiAuth } from '../../index';
import { algovoiFetch } from '../common';

export const listNetworks = createAction({
  name: 'list_networks',
  auth: algovoiAuth,
  displayName: 'List Networks',
  description: 'Returns all AlgoVoi-supported networks (Algorand, VOI, Hedera, Stellar — mainnet and testnet).',
  props: {},

  async run(context) {
    const auth = context.auth as AlgovoiAuth;
    const resp = await algovoiFetch(auth, '/v1/networks') as Record<string, unknown>;
    return { networks: resp.networks ?? [], count: Array.isArray(resp.networks) ? resp.networks.length : 0 };
  },
});
