import type { ICredentialType, INodeProperties } from 'n8n-workflow';

export class AlgoVoiApi implements ICredentialType {
	name = 'algoVoiApi';
	displayName = 'AlgoVoi API';
	documentationUrl =
		'https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters/tree/master/no-code/n8n';
	icon = 'file:algovoi.svg' as const;

	properties: INodeProperties[] = [
		{
			displayName: 'API Key',
			name: 'apiKey',
			type: 'string',
			typeOptions: { password: true },
			default: '',
			required: true,
			description: 'AlgoVoi API key (starts with algv_). Find it at app.algovoi.com → Settings → API Keys.',
		},
		{
			displayName: 'Tenant ID',
			name: 'tenantId',
			type: 'string',
			default: '',
			required: true,
			description: 'AlgoVoi tenant UUID. Find it at app.algovoi.com → Settings.',
		},
		{
			displayName: 'Payout Address — Algorand',
			name: 'payoutAlgorand',
			type: 'string',
			default: '',
			description: 'Algorand wallet address for ALGO / USDC payouts (58-char base32).',
		},
		{
			displayName: 'Payout Address — VOI',
			name: 'payoutVoi',
			type: 'string',
			default: '',
			description: 'VOI wallet address for VOI / aUSDC payouts.',
		},
		{
			displayName: 'Payout Address — Hedera',
			name: 'payoutHedera',
			type: 'string',
			default: '',
			description: 'Hedera account ID for HBAR / USDC payouts (e.g. 0.0.123456).',
		},
		{
			displayName: 'Payout Address — Stellar',
			name: 'payoutStellar',
			type: 'string',
			default: '',
			description: 'Stellar public key for XLM / USDC payouts (starts with G).',
		},
		{
			displayName: 'Webhook Secret',
			name: 'webhookSecret',
			type: 'string',
			typeOptions: { password: true },
			default: '',
			description:
				'AlgoVoi webhook signing secret for HMAC-SHA256 signature verification. ' +
				'Found in AlgoVoi Dashboard → Settings → Webhooks.',
		},
		{
			displayName: 'API Base URL',
			name: 'apiBase',
			type: 'string',
			default: 'https://api1.ilovechicken.co.uk',
			description: 'AlgoVoi API base URL. Leave as default unless instructed otherwise.',
		},
	];
}
