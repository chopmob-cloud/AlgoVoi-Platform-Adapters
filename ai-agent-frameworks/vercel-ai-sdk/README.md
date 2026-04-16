# Vercel AI SDK Adapter for AlgoVoi

Payment-gate any Vercel AI SDK model call or tool using x402, MPP, or AP2 — paid in USDC on Algorand, VOI, Hedera, or Stellar.

**v1.0.0 — TypeScript-native, provider-agnostic. Works with OpenAI, Anthropic, Google, Groq, Ollama, and any `@ai-sdk/*` provider. Designed for Next.js App Router, Express, and Vercel Edge Functions.**

https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## How it works

```
Client sends request
        |
        v
AlgoVoiVercelAI.check() — no payment proof
        |
        v
HTTP 402 + protocol challenge header
  x402:  X-PAYMENT-REQUIRED (spec v1, base64 JSON)
  MPP:   WWW-Authenticate: Payment (IETF draft)
  AP2:   X-AP2-Cart-Mandate (crypto-algo extension)
        |
        v
Client pays on-chain (Algorand / VOI / Hedera / Stellar)
Client re-sends with proof in header
        |
        v
AlgoVoiVercelAI.check() — proof verified directly via public
blockchain indexers (no central API dependency)
        |
        v
gate.generateText(messages)   → model reply string
gate.streamText(messages)     → StreamTextResult (pipe to client)
        |
        v
HTTP 200 — response returned
```

### Tool mode

```
LLM selects AlgoVoiPaymentTool via function calling
        |
        v
tool.execute({ query: "...", paymentProof: "<base64>" })
  → challenge JSON if proof absent/invalid
  → resourceFn(query) result if payment verified
```

---

## Files

| File | Description |
|------|-------------|
| `vercel_ai_algovoi.ts` | Adapter — `AlgoVoiVercelAI`, `VercelAIResult` |
| `test_vercel_ai_algovoi.test.ts` | Unit tests (all mocked, no live calls) — 79/79 |
| `smoke_test_vercel_ai.ts` | Two-phase smoke test (challenge render + real on-chain verification) |
| `example.ts` | Next.js App Router, streaming, Express, tool, multi-provider examples |
| `package.json` | Dev dependencies (vitest, tsx, typescript) |
| `tsconfig.json` | TypeScript compiler config |
| `README.md` | This file |

---

## Supported chains

| Network key | Asset | Asset ID |
|-------------|-------|----------|
| `algorand-mainnet` | USDC | ASA 31566704 |
| `voi-mainnet` | aUSDC | ARC200 302190 |
| `hedera-mainnet` | USDC | HTS 0.0.456858 |
| `stellar-mainnet` | USDC | Circle |

## Supported protocols

| Key | Spec |
|-----|------|
| `x402` | x402 spec v1 — `X-PAYMENT-REQUIRED` / `X-PAYMENT` |
| `mpp` | IETF draft-ryan-httpauth-payment — `WWW-Authenticate: Payment` |
| `ap2` | AP2 v0.1 + AlgoVoi crypto-algo extension |

---

## Quick start

```bash
npm install ai zod @ai-sdk/openai
```

```typescript
import { openai } from "@ai-sdk/openai";
import { AlgoVoiVercelAI } from "./vercel_ai_algovoi";

const gate = new AlgoVoiVercelAI({
  algovoiKey:       "algv_...",
  tenantId:         "your-tenant-uuid",
  payoutAddress:    "YOUR_ALGORAND_ADDRESS",
  protocol:         "mpp",              // "mpp" | "x402" | "ap2"
  network:          "algorand-mainnet",
  amountMicrounits: 10_000,             // 0.01 USDC per call
  model:            openai("gpt-4o"),
});
```

### Next.js App Router — non-streaming

```typescript
// app/api/chat/route.ts
export async function POST(req: Request) {
  return gate.nextHandler(req);   // check() → generateText() → 200 or 402
}
```

### Next.js App Router — streaming

```typescript
// app/api/chat/stream/route.ts
export async function POST(req: Request) {
  const body = await req.json();
  const result = await gate.check(req.headers, body);
  if (result.requiresPayment) return result.as402Response();

  const stream = gate.streamText(body.messages);
  return stream.toDataStreamResponse();   // Vercel AI SDK streaming
}
```

### Manual check + complete

```typescript
const result = await gate.check(dict(request.headers), body);
if (result.requiresPayment) {
  return result.as402Response();   // 402 + challenge header
}
const content = await gate.generateText(body.messages);
```

### Payment tool (for LLM function calling)

```typescript
const premiumTool = gate.asTool(
  async (query) => myPremiumHandler(query),
  { toolName: "premium_kb", toolDescription: "Access premium knowledge base." }
);

// Use with any Vercel AI SDK generateText call
const { generateText } = await import("ai");
await generateText({
  model: openai("gpt-4o"),
  tools: { premium_kb: premiumTool },
  messages: [{ role: "user", content: "..." }],
});
```

---

## Constructor parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `algovoiKey` | `string` | required | `algv_...` API key |
| `tenantId` | `string` | required | AlgoVoi tenant UUID |
| `payoutAddress` | `string` | required | On-chain payout address |
| `protocol` | `string` | `"mpp"` | Payment protocol |
| `network` | `string` | `"algorand-mainnet"` | Blockchain network |
| `amountMicrounits` | `number` | `10000` | Amount in micro-USDC (10000 = $0.01) |
| `model` | `LanguageModel` | `undefined` | Vercel AI SDK model (required for `generateText`/`streamText`) |
| `resourceId` | `string` | `"ai-function"` | AlgoVoi resource identifier |
| `realm` | `string` | `"API Access"` | MPP realm string |
| `challengeTtl` | `number` | `300` | MPP challenge TTL in seconds |
| `ap2ExpiresSec` | `number` | `600` | AP2 CartMandate TTL in seconds |

---

## Method reference

### `check(headers[, body])` → `Promise<VercelAIResult>`

Verify payment proof from request headers.

```typescript
const result = await gate.check(req.headers, body);
result.requiresPayment     // true → return 402; false → proceed
result.error               // human-readable rejection reason
result.challengeHeaders    // Record<string, string> with 402 headers
result.as402Response()     // Web API Response (status 402)
```

Accepts `Headers` (Web API) or `Record<string, string>`. Header names are case-normalised internally.

### `generateText(messages)` → `Promise<string>`

Run an OpenAI-format message list through the configured model via `ai.generateText`.

```typescript
const reply = await gate.generateText([
  { role: "system",    content: "Be concise." },
  { role: "user",      content: "What is AlgoVoi?" },
]);
```

Throws if no `model` was set in the constructor.

### `streamText(messages)` → `StreamTextResult`

Stream through the configured model via `ai.streamText`. Returns the raw result — call `.toDataStreamResponse()` for Next.js streaming.

```typescript
const stream = gate.streamText(messages);
return stream.toDataStreamResponse();
```

Throws if no `model` was set in the constructor.

### `asTool(resourceFn[, opts])` → Vercel AI SDK `tool`

Return a Vercel AI SDK `tool()` compatible object. The tool accepts `query` and `paymentProof` parameters.

```typescript
const t = gate.asTool(
  (query) => myHandler(query),
  { toolName: "premium_kb", toolDescription: "..." }
);
// Use in generateText({ tools: { premium_kb: t } })
```

### `nextHandler(req)` → `Promise<Response>`

One-call Next.js App Router handler: `check()` → `generateText()`.

```typescript
export const POST = (req: Request) => gate.nextHandler(req);
```

For streaming, use `check()` + `streamText()` manually.

---

## Supported Vercel AI SDK providers

Pass any provider model to the `model` constructor parameter.

| Provider | Install | Model example |
|----------|---------|---------------|
| OpenAI | `npm i @ai-sdk/openai` | `openai("gpt-4o")` |
| Anthropic | `npm i @ai-sdk/anthropic` | `anthropic("claude-opus-4-5")` |
| Google | `npm i @ai-sdk/google` | `google("gemini-2.0-flash")` |
| Groq | `npm i @ai-sdk/groq` | `groq("llama-3.1-70b-versatile")` |
| Mistral | `npm i @ai-sdk/mistral` | `mistral("mistral-large-latest")` |
| Cohere | `npm i @ai-sdk/cohere` | `cohere("command-r-plus")` |
| Ollama | `npm i ollama-ai-provider` | `ollama("llama3")` |
| Azure OpenAI | `npm i @ai-sdk/azure` | `azure("gpt-4o")` |
| Any OpenAI-compatible | `npm i @ai-sdk/openai` | `createOpenAI({ baseURL: "..." })("model")` |

---

## Edge Function compatibility

`vercel_ai_algovoi.ts` uses `node:crypto` for MPP HMAC challenge generation. This requires the **Node.js runtime** in Vercel. For Edge Functions, use `x402` or `ap2` protocol, or configure `runtime = "nodejs"` in your route:

```typescript
export const runtime = "nodejs";   // in Next.js App Router route
```

All network verification calls use the standard `fetch()` API and work on both runtimes.

---

## Smoke test

```bash
# Phase 1 — no live API needed:
npx tsx smoke_test_vercel_ai.ts --phase 1

# Phase 2 — live on-chain verification:
ALGOVOI_KEY=algv_... TENANT_ID=... PAYOUT_ADDRESS=... OPENAI_KEY=sk-... \
  npx tsx smoke_test_vercel_ai.ts --phase 2
```

---

## Requirements

- Node.js ≥ 18 (for native `fetch` and `Buffer`)
- `ai` ≥ 4.0.0 (peer dependency)
- `zod` ≥ 3.0.0 (peer dependency)
- A `@ai-sdk/*` provider package for `generateText` / `streamText`

---

Licensed under the [Business Source License 1.1](../../LICENSE).
