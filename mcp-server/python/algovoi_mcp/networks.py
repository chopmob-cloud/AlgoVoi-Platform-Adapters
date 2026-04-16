"""Network and asset constants for the AlgoVoi MCP server."""

NETWORKS = (
    "algorand_mainnet",
    "voi_mainnet",
    "hedera_mainnet",
    "stellar_mainnet",
)

PROTOCOLS = ("mpp", "ap2", "x402")

NETWORK_INFO = {
    "algorand_mainnet": {
        "label": "Algorand",
        "asset": "USDC",
        "asset_id": "31566704",
        "decimals": 6,
        "caip2": "algorand:mainnet",
        "description": "Circle-issued USDC on Algorand (ASA 31566704).",
    },
    "voi_mainnet": {
        "label": "VOI",
        "asset": "aUSDC",
        "asset_id": "302190",
        "decimals": 6,
        "caip2": "voi:mainnet",
        "description": "Aramid-bridged USDC on VOI (ARC-200 302190).",
    },
    "hedera_mainnet": {
        "label": "Hedera",
        "asset": "USDC",
        "asset_id": "0.0.456858",
        "decimals": 6,
        "caip2": "hedera:mainnet",
        "description": "Circle-issued USDC on Hedera (HTS 0.0.456858).",
    },
    "stellar_mainnet": {
        "label": "Stellar",
        "asset": "USDC",
        "asset_id": "USDC:GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN",
        "decimals": 7,
        "caip2": "stellar:pubnet",
        "description": "Circle-issued USDC on Stellar (trust line required).",
    },
}

CAIP2 = {k: v["caip2"] for k, v in NETWORK_INFO.items()}
