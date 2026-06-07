'use strict';

const NETWORKS = [
  { id: 'algorand_mainnet',      label: 'Algorand',         asset: 'USDC',  asset_id: '31566704',    decimals: 6 },
  { id: 'voi_mainnet',           label: 'VOI',              asset: 'aUSDC', asset_id: '302190',      decimals: 6 },
  { id: 'hedera_mainnet',        label: 'Hedera',           asset: 'USDC',  asset_id: '0.0.456858',  decimals: 6 },
  { id: 'stellar_mainnet',       label: 'Stellar',          asset: 'USDC',  asset_id: 'USDC:GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN', decimals: 7 },
  { id: 'algorand_mainnet_algo', label: 'Algorand',         asset: 'ALGO',  asset_id: null,          decimals: 6 },
  { id: 'voi_mainnet_voi',       label: 'VOI',              asset: 'VOI',   asset_id: null,          decimals: 6 },
  { id: 'hedera_mainnet_hbar',   label: 'Hedera',           asset: 'HBAR',  asset_id: null,          decimals: 8 },
  { id: 'stellar_mainnet_xlm',   label: 'Stellar',          asset: 'XLM',   asset_id: null,          decimals: 7 },
  { id: 'algorand_testnet',      label: 'Algorand Testnet', asset: 'USDC',  asset_id: '10458941',    decimals: 6 },
  { id: 'voi_testnet',           label: 'VOI Testnet',      asset: 'aUSDC', asset_id: null,          decimals: 6 },
  { id: 'hedera_testnet',        label: 'Hedera Testnet',   asset: 'USDC',  asset_id: '0.0.4279119', decimals: 6 },
  { id: 'stellar_testnet',       label: 'Stellar Testnet',  asset: 'USDC',  asset_id: 'USDC:GBBD47IF6LWK7P7MDEVSCWR7DPUWV3NY3DTQEVFL4NAT4AQH3ZLLFLA5', decimals: 7 },
  { id: 'algorand_testnet_algo', label: 'Algorand Testnet', asset: 'ALGO',  asset_id: null,          decimals: 6 },
  { id: 'voi_testnet_voi',       label: 'VOI Testnet',      asset: 'VOI',   asset_id: null,          decimals: 6 },
  { id: 'hedera_testnet_hbar',   label: 'Hedera Testnet',   asset: 'HBAR',  asset_id: null,          decimals: 8 },
  { id: 'stellar_testnet_xlm',   label: 'Stellar Testnet',  asset: 'XLM',   asset_id: null,          decimals: 7 },
];

const perform = async (z, bundle) => {
  const filter = (bundle.inputData.filter || '').toLowerCase();
  return filter
    ? NETWORKS.filter(n => n.id.includes(filter) || n.asset.toLowerCase().includes(filter))
    : NETWORKS;
};

module.exports = {
  key: 'list_networks',
  noun: 'Network',

  display: {
    label: 'Find Networks',
    description:
      'Lists all 16 AlgoVoi-supported networks (Algorand, VOI, Hedera, Stellar — ' +
      'mainnet and testnet). Use to populate a dropdown or validate a network ID.',
  },

  operation: {
    perform,
    inputFields: [
      {
        key:      'filter',
        label:    'Filter',
        type:     'string',
        required: false,
        helpText: 'Optional text to filter results (e.g. `algorand`, `USDC`, `testnet`).',
      },
    ],

    sample: {
      id:       'algorand_mainnet',
      label:    'Algorand',
      asset:    'USDC',
      asset_id: '31566704',
      decimals: 6,
    },

    outputFields: [
      { key: 'id',       label: 'Network ID' },
      { key: 'label',    label: 'Chain Name' },
      { key: 'asset',    label: 'Asset Symbol' },
      { key: 'asset_id', label: 'Asset ID (on-chain)' },
      { key: 'decimals', label: 'Decimals', type: 'integer' },
    ],
  },
};
