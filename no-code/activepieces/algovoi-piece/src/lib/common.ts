export const NETWORK_OPTIONS = [
  { label: 'Algorand — USDC',          value: 'algorand_mainnet' },
  { label: 'VOI — aUSDC',              value: 'voi_mainnet' },
  { label: 'Hedera — USDC',            value: 'hedera_mainnet' },
  { label: 'Stellar — USDC',           value: 'stellar_mainnet' },
  { label: 'Algorand — ALGO (native)', value: 'algorand_mainnet_algo' },
  { label: 'VOI — VOI (native)',       value: 'voi_mainnet_voi' },
  { label: 'Hedera — HBAR (native)',   value: 'hedera_mainnet_hbar' },
  { label: 'Stellar — XLM (native)',   value: 'stellar_mainnet_xlm' },
  { label: 'Algorand Testnet — USDC',  value: 'algorand_testnet' },
  { label: 'VOI Testnet — aUSDC',      value: 'voi_testnet' },
  { label: 'Hedera Testnet — USDC',    value: 'hedera_testnet' },
  { label: 'Stellar Testnet — USDC',   value: 'stellar_testnet' },
];

export type AlgovoiAuth = {
  api_key: string;
  tenant_id: string;
  payout_algorand?: string;
  payout_voi?: string;
  payout_hedera?: string;
  payout_stellar?: string;
  webhook_secret?: string;
  api_base?: string;
};

export function getApiBase(auth: AlgovoiAuth): string {
  return (auth.api_base || 'https://api1.ilovechicken.co.uk').replace(/\/$/, '');
}

export function authHeaders(auth: AlgovoiAuth): Record<string, string> {
  return {
    Authorization: `Bearer ${auth.api_key}`,
    'X-Tenant-Id': auth.tenant_id,
    'Content-Type': 'application/json',
  };
}

export async function algovoiFetch(
  auth: AlgovoiAuth,
  path: string,
  options: { method?: string; body?: unknown } = {},
): Promise<unknown> {
  const base = getApiBase(auth);
  const resp = await fetch(`${base}${path}`, {
    method: options.method || 'GET',
    headers: authHeaders(auth),
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  const text = await resp.text();
  let data: unknown;
  try { data = JSON.parse(text); } catch { data = { raw: text }; }

  if (!resp.ok) {
    const msg = typeof data === 'object' && data !== null && 'error' in data
      ? String((data as Record<string, unknown>).error)
      : `AlgoVoi API error ${resp.status}`;
    throw new Error(msg);
  }

  return data;
}
