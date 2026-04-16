/**
 * Network and asset constants.
 *
 * NETWORKS uses snake_case keys (the format the AlgoVoi REST API expects).
 * NETWORK_INFO is the rich object each tool returns so the LLM can decide
 * which chain to offer the user.
 */

export const NETWORKS = [
  "algorand_mainnet",
  "voi_mainnet",
  "hedera_mainnet",
  "stellar_mainnet",
] as const;

export type Network = (typeof NETWORKS)[number];

export const NETWORK_INFO: Record<
  Network,
  {
    label: string;
    asset: string;
    asset_id: string;
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
};

export const PROTOCOLS = ["mpp", "ap2", "x402"] as const;
export type Protocol = (typeof PROTOCOLS)[number];
