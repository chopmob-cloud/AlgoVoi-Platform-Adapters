import type {
	IDataObject,
	IExecuteFunctions,
	INodeExecutionData,
	INodeType,
	INodeTypeDescription,
} from 'n8n-workflow';
import { NodeConnectionType, NodeOperationError } from 'n8n-workflow';

// ── Constants ──────────────────────────────────────────────────────────────────

const NETWORK_OPTIONS = [
	{ name: 'Algorand — USDC',         value: 'algorand_mainnet' },
	{ name: 'VOI — aUSDC',             value: 'voi_mainnet' },
	{ name: 'Hedera — USDC',           value: 'hedera_mainnet' },
	{ name: 'Stellar — USDC',          value: 'stellar_mainnet' },
	{ name: 'Algorand — ALGO (native)', value: 'algorand_mainnet_algo' },
	{ name: 'VOI — VOI (native)',       value: 'voi_mainnet_voi' },
	{ name: 'Hedera — HBAR (native)',   value: 'hedera_mainnet_hbar' },
	{ name: 'Stellar — XLM (native)',   value: 'stellar_mainnet_xlm' },
	{ name: 'Algorand Testnet — USDC',  value: 'algorand_testnet' },
	{ name: 'VOI Testnet — aUSDC',      value: 'voi_testnet' },
	{ name: 'Hedera Testnet — USDC',    value: 'hedera_testnet' },
	{ name: 'Stellar Testnet — USDC',   value: 'stellar_testnet' },
];

const NETWORK_INFO: Record<string, { label: string; asset: string; assetId: string | null; decimals: number }> = {
	algorand_mainnet:      { label: 'Algorand',         asset: 'USDC',  assetId: '31566704',    decimals: 6 },
	voi_mainnet:           { label: 'VOI',              asset: 'aUSDC', assetId: '302190',      decimals: 6 },
	hedera_mainnet:        { label: 'Hedera',           asset: 'USDC',  assetId: '0.0.456858',  decimals: 6 },
	stellar_mainnet:       { label: 'Stellar',          asset: 'USDC',  assetId: 'USDC:GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN', decimals: 7 },
	algorand_mainnet_algo: { label: 'Algorand',         asset: 'ALGO',  assetId: null,          decimals: 6 },
	voi_mainnet_voi:       { label: 'VOI',              asset: 'VOI',   assetId: null,          decimals: 6 },
	hedera_mainnet_hbar:   { label: 'Hedera',           asset: 'HBAR',  assetId: null,          decimals: 8 },
	stellar_mainnet_xlm:   { label: 'Stellar',          asset: 'XLM',   assetId: null,          decimals: 7 },
	algorand_testnet:      { label: 'Algorand Testnet', asset: 'USDC',  assetId: '10458941',    decimals: 6 },
	voi_testnet:           { label: 'VOI Testnet',      asset: 'aUSDC', assetId: null,          decimals: 6 },
	hedera_testnet:        { label: 'Hedera Testnet',   asset: 'USDC',  assetId: '0.0.4279119', decimals: 6 },
	stellar_testnet:       { label: 'Stellar Testnet',  asset: 'USDC',  assetId: 'USDC:GBBD47IF6LWK7P7MDEVSCWR7DPUWV3NY3DTQEVFL4NAT4AQH3ZLLFLA5', decimals: 7 },
	algorand_testnet_algo: { label: 'Algorand Testnet', asset: 'ALGO',  assetId: null,          decimals: 6 },
	voi_testnet_voi:       { label: 'VOI Testnet',      asset: 'VOI',   assetId: null,          decimals: 6 },
	hedera_testnet_hbar:   { label: 'Hedera Testnet',   asset: 'HBAR',  assetId: null,          decimals: 8 },
	stellar_testnet_xlm:   { label: 'Stellar Testnet',  asset: 'XLM',   assetId: null,          decimals: 7 },
};

// ── Node definition ────────────────────────────────────────────────────────────

export class AlgoVoi implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'AlgoVoi',
		name: 'algoVoi',
		icon: 'file:algovoi.svg',
		group: ['finance'],
		version: 1,
		subtitle: '={{$parameter["operation"]}}',
		description:
			'Accept crypto payments on Algorand, VOI, Hedera & Stellar. ' +
			'Create checkout links, verify payments, and generate MPP/x402/AP2 challenges.',
		defaults: { name: 'AlgoVoi' },
		inputs: [NodeConnectionType.Main],
		outputs: [NodeConnectionType.Main],
		credentials: [{ name: 'algoVoiApi', required: true }],
		requestDefaults: {
			headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
		},
		properties: [
			// ── Operation selector ───────────────────────────────────────────────
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				options: [
					{ name: 'Create Payment Link',       value: 'createPaymentLink',      description: 'Create a hosted AlgoVoi checkout URL' },
					{ name: 'Verify Payment',            value: 'verifyPayment',          description: 'Check whether a checkout token has been paid' },
					{ name: 'List Networks',             value: 'listNetworks',           description: 'List all 16 supported networks and assets' },
					{ name: 'Generate MPP Challenge',    value: 'generateMppChallenge',   description: 'Build an MPP WWW-Authenticate 402 challenge header' },
					{ name: 'Generate x402 Challenge',   value: 'generateX402Challenge',  description: 'Build an x402 X-Payment-Required challenge header' },
					{ name: 'Generate AP2 Mandate',      value: 'generateAp2Mandate',     description: 'Build an AP2 CartMandate / PaymentMandate' },
					{ name: 'Verify Webhook Signature',  value: 'verifyWebhookSignature', description: 'Validate an AlgoVoi HMAC-SHA256 webhook signature' },
				],
				default: 'createPaymentLink',
			},

			// ── createPaymentLink fields ─────────────────────────────────────────
			{
				displayName: 'Amount (USD)',
				name: 'amount',
				type: 'number',
				required: true,
				displayOptions: { show: { operation: ['createPaymentLink'] } },
				default: 1.0,
				description: 'Payment amount in USD. AlgoVoi converts to the correct crypto amount on checkout.',
			},
			{
				displayName: 'Label',
				name: 'label',
				type: 'string',
				required: true,
				displayOptions: { show: { operation: ['createPaymentLink'] } },
				default: '',
				description: 'Description shown to the customer on the checkout page.',
			},
			{
				displayName: 'Network',
				name: 'network',
				type: 'options',
				required: false,
				displayOptions: { show: { operation: ['createPaymentLink', 'generateMppChallenge', 'generateX402Challenge', 'generateAp2Mandate'] } },
				options: NETWORK_OPTIONS,
				default: 'algorand_mainnet',
				description: 'Blockchain / asset the customer should pay on.',
			},
			{
				displayName: 'Currency',
				name: 'currency',
				type: 'string',
				required: false,
				displayOptions: { show: { operation: ['createPaymentLink'] } },
				default: 'USD',
				description: 'Fiat base currency (3-letter code).',
			},
			{
				displayName: 'Redirect URL',
				name: 'redirectUrl',
				type: 'string',
				required: false,
				displayOptions: { show: { operation: ['createPaymentLink'] } },
				default: '',
				description: 'HTTPS URL to redirect the customer after a successful payment.',
			},

			// ── verifyPayment fields ─────────────────────────────────────────────
			{
				displayName: 'Checkout Token',
				name: 'token',
				type: 'string',
				required: true,
				displayOptions: { show: { operation: ['verifyPayment'] } },
				default: '',
				description: 'Checkout token from a previous Create Payment Link operation or AlgoVoi webhook.',
			},

			// ── challenge / mandate shared fields ────────────────────────────────
			{
				displayName: 'Resource ID',
				name: 'resourceId',
				type: 'string',
				required: true,
				displayOptions: { show: { operation: ['generateMppChallenge', 'generateX402Challenge', 'generateAp2Mandate'] } },
				default: '',
				description: 'Unique identifier for the protected resource (e.g. /api/premium).',
			},
			{
				displayName: 'Amount (microunits)',
				name: 'amountMicrounits',
				type: 'number',
				required: true,
				displayOptions: { show: { operation: ['generateMppChallenge', 'generateX402Challenge', 'generateAp2Mandate'] } },
				default: 1000000,
				description: 'Payment amount in asset microunits (e.g. 1000000 = 1 USDC with 6 decimals).',
			},
			{
				displayName: 'Expires In (seconds)',
				name: 'expiresInSeconds',
				type: 'number',
				required: false,
				displayOptions: { show: { operation: ['generateMppChallenge', 'generateX402Challenge', 'generateAp2Mandate'] } },
				default: 300,
				description: 'How long the challenge is valid for (1–86400 seconds).',
			},

			// ── verifyWebhookSignature fields ────────────────────────────────────
			{
				displayName: 'Raw Webhook Body',
				name: 'rawBody',
				type: 'string',
				required: true,
				displayOptions: { show: { operation: ['verifyWebhookSignature'] } },
				default: '',
				description: 'Raw string body received from AlgoVoi (before JSON parsing).',
			},
			{
				displayName: 'X-AlgoVoi-Signature Header',
				name: 'signature',
				type: 'string',
				required: true,
				displayOptions: { show: { operation: ['verifyWebhookSignature'] } },
				default: '',
				description: 'Value of the X-AlgoVoi-Signature header from the incoming webhook.',
			},
		],
	};

	// ── Execute ────────────────────────────────────────────────────────────────

	async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
		const items      = this.getInputData();
		const returnData: INodeExecutionData[] = [];

		const credentials = await this.getCredentials('algoVoiApi');
		const apiKey      = credentials.apiKey as string;
		const tenantId    = credentials.tenantId as string;
		const apiBase     = ((credentials.apiBase as string) || 'https://api1.ilovechicken.co.uk').replace(/\/$/, '');
		const payoutMap: Record<string, string> = {
			algorand_mainnet: (credentials.payoutAlgorand as string) || '',
			voi_mainnet:      (credentials.payoutVoi      as string) || '',
			hedera_mainnet:   (credentials.payoutHedera   as string) || '',
			stellar_mainnet:  (credentials.payoutStellar  as string) || '',
		};
		const webhookSecret = (credentials.webhookSecret as string) || '';

		const authHeaders: IDataObject = {
			Authorization: `Bearer ${apiKey}`,
			'X-Tenant-Id':  tenantId,
		};

		// Helper: resolve payout address for a given network
		const payoutFor = (network: string): string => {
			const base = network.replace(/_(algo|voi|hbar|xlm)$/, '');
			return payoutMap[network] || payoutMap[base] || Object.values(payoutMap).find(Boolean) || '';
		};

		for (let i = 0; i < items.length; i++) {
			const operation = this.getNodeParameter('operation', i) as string;
			let result: IDataObject = {};

			try {
				// ── 1. createPaymentLink ──────────────────────────────────────────
				if (operation === 'createPaymentLink') {
					const amount      = this.getNodeParameter('amount', i)      as number;
					const label       = this.getNodeParameter('label', i)       as string;
					const network     = this.getNodeParameter('network', i)     as string;
					const currency    = this.getNodeParameter('currency', i)    as string;
					const redirectUrl = this.getNodeParameter('redirectUrl', i) as string;

					const body: IDataObject = {
						amount:            Math.round(amount * 100) / 100,
						currency:          currency.toUpperCase(),
						label:             label.slice(0, 200),
						preferred_network: network,
					};
					if (redirectUrl) {
						body.redirect_url       = redirectUrl;
						body.expires_in_seconds = 3600;
					}

					const resp = await this.helpers.httpRequest({
						method:  'POST',
						url:     `${apiBase}/v1/payment-links`,
						headers: authHeaders,
						body,
						json:    true,
					});

					if (!resp.checkout_url) throw new Error('AlgoVoi API did not return checkout_url');

					const tokenMatch = (resp.checkout_url as string).match(/\/checkout\/([A-Za-z0-9_-]+)$/);
					result = {
						checkout_url:      resp.checkout_url,
						token:             tokenMatch ? tokenMatch[1] : '',
						amount,
						currency:          currency.toUpperCase(),
						network,
						amount_microunits: resp.amount_microunits || 0,
					};
				}

				// ── 2. verifyPayment ──────────────────────────────────────────────
				else if (operation === 'verifyPayment') {
					const token = this.getNodeParameter('token', i) as string;

					const resp = await this.helpers.httpRequest({
						method:  'GET',
						url:     `${apiBase}/checkout/${encodeURIComponent(token)}/status`,
						headers: {},
						json:    true,
					});

					const status = String(resp.status || 'unknown');
					result = {
						token,
						paid:   ['paid', 'completed', 'confirmed'].includes(status),
						status,
					};
				}

				// ── 3. listNetworks ───────────────────────────────────────────────
				else if (operation === 'listNetworks') {
					const networks = Object.entries(NETWORK_INFO).map(([id, info]) => ({
						id,
						label:    info.label,
						asset:    info.asset,
						asset_id: info.assetId,
						decimals: info.decimals,
					}));
					result = { networks, count: networks.length };
				}

				// ── 4. generateMppChallenge ───────────────────────────────────────
				else if (operation === 'generateMppChallenge') {
					const resourceId       = this.getNodeParameter('resourceId', i)       as string;
					const amountMicrounits = this.getNodeParameter('amountMicrounits', i) as number;
					const network          = this.getNodeParameter('network', i)          as string;
					const expiresIn        = Math.max(1, Math.min(this.getNodeParameter('expiresInSeconds', i) as number, 86400));

					const expiresAt = Math.floor(Date.now() / 1000) + expiresIn;
					const payout    = payoutFor(network);
					const netInfo   = NETWORK_INFO[network] || {};
					const asset     = netInfo.assetId || netInfo.asset || '';

					const challenge =
						`AlgoVoi realm="${resourceId}",` +
						`network="${network}",` +
						`receiver="${payout}",` +
						`amount="${amountMicrounits}",` +
						`asset="${asset}",` +
						`expires="${expiresAt}"`;

					result = {
						protocol:          'mpp',
						header_name:       'WWW-Authenticate',
						header_value:      challenge,
						resource_id:       resourceId,
						amount_microunits: amountMicrounits,
						network,
						expires_at:        expiresAt,
					};
				}

				// ── 5. generateX402Challenge ──────────────────────────────────────
				else if (operation === 'generateX402Challenge') {
					const resourceId       = this.getNodeParameter('resourceId', i)       as string;
					const amountMicrounits = this.getNodeParameter('amountMicrounits', i) as number;
					const network          = this.getNodeParameter('network', i)          as string;
					const expiresIn        = Math.max(1, Math.min(this.getNodeParameter('expiresInSeconds', i) as number, 86400));

					const expiresAt  = Math.floor(Date.now() / 1000) + expiresIn;
					const payout     = payoutFor(network);
					const netInfo    = NETWORK_INFO[network] || {};
					const mandateId  = Buffer.from(`${resourceId}:${Date.now()}`).toString('hex').slice(0, 16);

					const payloadObj = {
						version:  1,
						scheme:   'exact',
						network,
						resource: resourceId,
						receiver: payout,
						amount:   String(amountMicrounits),
						asset:    netInfo.assetId || netInfo.asset || '',
						expires:  expiresAt,
						mandate:  mandateId,
					};
					const encoded = Buffer.from(JSON.stringify(payloadObj)).toString('base64');

					result = {
						protocol:    'x402',
						header_name: 'X-Payment-Required',
						header_value: encoded,
						mandate_id:  mandateId,
						network,
						expires_at:  expiresAt,
					};
				}

				// ── 6. generateAp2Mandate ─────────────────────────────────────────
				else if (operation === 'generateAp2Mandate') {
					const resourceId       = this.getNodeParameter('resourceId', i)       as string;
					const amountMicrounits = this.getNodeParameter('amountMicrounits', i) as number;
					const network          = this.getNodeParameter('network', i)          as string;
					const expiresIn        = Math.max(1, Math.min(this.getNodeParameter('expiresInSeconds', i) as number, 86400));

					const expiresAt = Math.floor(Date.now() / 1000) + expiresIn;
					const payout    = payoutFor(network);
					const netInfo   = NETWORK_INFO[network] || {};
					const mandateId = Buffer.from(`${resourceId}:${Date.now()}`).toString('hex').slice(0, 16);

					const mandateObj = {
						version:    '0.1',
						mandate_id: mandateId,
						resource:   resourceId,
						network,
						receiver:   payout,
						amount:     String(amountMicrounits),
						asset:      netInfo.assetId || netInfo.asset || '',
						expires:    expiresAt,
					};
					const mandateB64 = Buffer.from(JSON.stringify(mandateObj)).toString('base64');

					result = {
						protocol:    'ap2',
						mandate_id:  mandateId,
						mandate_b64: mandateB64,
						network,
						expires_at:  expiresAt,
					};
				}

				// ── 7. verifyWebhookSignature ─────────────────────────────────────
				else if (operation === 'verifyWebhookSignature') {
					const rawBody   = this.getNodeParameter('rawBody', i)   as string;
					const signature = this.getNodeParameter('signature', i) as string;

					if (!webhookSecret) {
						throw new NodeOperationError(this.getNode(), 'webhookSecret is not configured in credentials', { itemIndex: i });
					}

					const crypto = await import('crypto');
					const expected = crypto
						.createHmac('sha256', webhookSecret)
						.update(rawBody, 'utf8')
						.digest('hex');

					const valid = crypto.timingSafeEqual(
						Buffer.from(expected, 'hex'),
						Buffer.from(signature.length === expected.length ? signature : expected, 'hex'),
					);

					if (!valid) {
						result = { valid: false, error: 'Signature mismatch', payload: null };
					} else {
						try {
							result = { valid: true, payload: JSON.parse(rawBody) as IDataObject };
						} catch {
							result = { valid: false, error: 'Invalid JSON body', payload: null };
						}
					}
				}

			} catch (error) {
				if (this.continueOnFail()) {
					returnData.push({ json: { error: (error as Error).message }, pairedItem: { item: i } });
					continue;
				}
				throw error;
			}

			returnData.push({ json: result, pairedItem: { item: i } });
		}

		return [returnData];
	}
}
