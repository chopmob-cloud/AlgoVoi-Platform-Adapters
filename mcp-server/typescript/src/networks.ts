/**
 * Network and asset constants.
 *
 * NETWORKS uses snake_case keys (the format the AlgoVoi REST API expects).
 * NETWORK_INFO is the rich object each tool returns so the LLM can decide
 * which chain to offer the user.
 */

export const NETWORKS = [
  // ── Mainnet ──────────────────────────────────────────────────────────
  "algorand_mainnet",
  "voi_mainnet",
  "hedera_mainnet",
  "stellar_mainnet",
  "algorand_mainnet_algo",
  "voi_mainnet_voi",
  "hedera_mainnet_hbar",
  "stellar_mainnet_xlm",
  // ── Testnet ──────────────────────────────────────────────────────────
  "algorand_testnet",
  "voi_testnet",
  "hedera_testnet",
  "stellar_testnet",
  "algorand_testnet_algo",
  "voi_testnet_voi",
  "hedera_testnet_hbar",
  "stellar_testnet_xlm",
] as const;

export type Network = (typeof NETWORKS)[number];

export const NETWORK_INFO: Record<
  Network,
  {
    label: string;
    asset: string;
    asset_id: string | null;
    decimals: number;
    caip2: string;
    description: string;
  }
> = {
  algorand_mainnet: {
    label: "Algorand",
    asset: "USDC",
    asset_id: "31566704",
    decimals: 6,
    caip2: "algorand:mainnet",
    description: "Circle-issued USDC on Algorand (ASA 31566704).",
  },
  voi_mainnet: {
    label: "VOI",
    asset: "aUSDC",
    asset_id: "302190",
    decimals: 6,
    caip2: "voi:mainnet",
    description: "Aramid-bridged USDC on VOI (ARC-200 302190).",
  },
  hedera_mainnet: {
    label: "Hedera",
    asset: "USDC",
    asset_id: "0.0.456858",
    decimals: 6,
    caip2: "hedera:mainnet",
    description: "Circle-issued USDC on Hedera (HTS 0.0.456858).",
  },
  stellar_mainnet: {
    label: "Stellar",
    asset: "USDC",
    asset_id: "USDC:GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN",
    decimals: 7,
    caip2: "stellar:pubnet",
    description: "Circle-issued USDC on Stellar (trust line required).",
  },
  algorand_mainnet_algo: {
    label: "Algorand",
    asset: "ALGO",
    asset_id: null,
    decimals: 6,
    caip2: "algorand:mainnet",
    description: "Native ALGO on Algorand (6 decimals, 1 ALGO = 1_000_000 microALGO).",
  },
  voi_mainnet_voi: {
    label: "VOI",
    asset: "VOI",
    asset_id: null,
    decimals: 6,
    caip2: "voi:mainnet",
    description: "Native VOI on VOI network (6 decimals, 1 VOI = 1_000_000 microVOI).",
  },
  hedera_mainnet_hbar: {
    label: "Hedera",
    asset: "HBAR",
    asset_id: null,
    decimals: 8,
    caip2: "hedera:mainnet",
    description: "Native HBAR on Hedera (8 decimals, 1 HBAR = 100_000_000 tinybar).",
  },
  stellar_mainnet_xlm: {
    label: "Stellar",
    asset: "XLM",
    asset_id: null,
    decimals: 7,
    caip2: "stellar:pubnet",
    description: "Native XLM on Stellar (7 decimals, 1 XLM = 10_000_000 stroops).",
  },

  // ── Testnet ─────────────────────────────────────────────────────────────────
  algorand_testnet: {
    label: "Algorand Testnet",
    asset: "USDC",
    asset_id: "10458941",
    decimals: 6,
    caip2: "algorand:testnet",
    description: "Circle USDC on Algorand testnet (ASA 10458941). For development only.",
  },
  voi_testnet: {
    label: "VOI Testnet",
    asset: "aUSDC",
    asset_id: null,
    decimals: 6,
    caip2: "voi:testnet",
    description: "Aramid-bridged USDC on VOI testnet. Asset ID varies — verify before use.",
  },
  hedera_testnet: {
    label: "Hedera Testnet",
    asset: "USDC",
    asset_id: "0.0.4279119",
    decimals: 6,
    caip2: "hedera:testnet",
    description: "Circle USDC on Hedera testnet (HTS 0.0.4279119). For development only.",
  },
  stellar_testnet: {
    label: "Stellar Testnet",
    asset: "USDC",
    asset_id: "USDC:GBBD47IF6LWK7P7MDEVSCWR7DPUWV3NY3DTQEVFL4NAT4AQH3ZLLFLA5",
    decimals: 7,
    caip2: "stellar:testnet",
    description: "Circle USDC on Stellar testnet. For development only.",
  },
  algorand_testnet_algo: {
    label: "Algorand Testnet",
    asset: "ALGO",
    asset_id: null,
    decimals: 6,
    caip2: "algorand:testnet",
    description: "Native ALGO on Algorand testnet (6 decimals). For development only.",
  },
  voi_testnet_voi: {
    label: "VOI Testnet",
    asset: "VOI",
    asset_id: null,
    decimals: 6,
    caip2: "voi:testnet",
    description: "Native VOI on VOI testnet (6 decimals). For development only.",
  },
  hedera_testnet_hbar: {
    label: "Hedera Testnet",
    asset: "HBAR",
    asset_id: null,
    decimals: 8,
    caip2: "hedera:testnet",
    description: "Native HBAR on Hedera testnet (8 decimals). For development only.",
  },
  stellar_testnet_xlm: {
    label: "Stellar Testnet",
    asset: "XLM",
    asset_id: null,
    decimals: 7,
    caip2: "stellar:testnet",
    description: "Native XLM on Stellar testnet (7 decimals). For development only.",
  },
};

export const PROTOCOLS = ["mpp", "ap2", "x402"] as const;
export type Protocol = (typeof PROTOCOLS)[number];
