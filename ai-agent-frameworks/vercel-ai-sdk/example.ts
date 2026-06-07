/**
 * AlgoVoi Vercel AI SDK Adapter — usage examples
 * =================================================
 *
 * Covers:
 *   1. Next.js App Router — non-streaming handler
 *   2. Next.js App Router — streaming handler
 *   3. Express server
 *   4. Payment tool in generateText() with tools
 *   5. Anthropic / Google / Groq providers
 *   6. x402 and AP2 protocols
 */

// ── 1. Next.js App Router — non-streaming ─────────────────────────────────────
// app/api/chat/route.ts

import { openai } from "@ai-sdk/openai";
import { AlgoVoiVercelAI } from "./vercel_ai_algovoi";

const gate = new AlgoVoiVercelAI({
  algovoiKey:       process.env.ALGOVOI_KEY!,
  tenantId:         process.env.TENANT_ID!,
  payoutAddress:    process.env.PAYOUT_ADDRESS!,
  protocol:         "mpp",
  network:          "algorand-mainnet",
  amountMicrounits: 10_000,           // 0.01 USDC per call
  model:            openai("gpt-4o"),
});

export async function POST(req: Request): Promise<Response> {
  return gate.nextHandler(req);
}

// ── 2. Next.js App Router — streaming ─────────────────────────────────────────
// app/api/chat/stream/route.ts

export async function POSTStream(req: Request): Promise<Response> {
  const body = await req.json() as { messages: unknown[] };

  const result = await gate.check(req.headers, body);
  if (result.requiresPayment) return result.as402Response();

  const stream = gate.streamText(body.messages as Parameters<typeof gate.streamText>[0]);
  return stream.toDataStreamResponse();   // Vercel AI SDK streaming response
}

// ── 3. Express server ─────────────────────────────────────────────────────────

import express, { Request as ExpressReq, Response as ExpressResp } from "express";

const app = express();
app.use(express.json({ limit: "1mb" }));

const expressGate = new AlgoVoiVercelAI({
  algovoiKey:       process.env.ALGOVOI_KEY!,
  tenantId:         process.env.TENANT_ID!,
  payoutAddress:    process.env.PAYOUT_ADDRESS!,
  protocol:         "mpp",
  network:          "algorand-mainnet",
  amountMicrounits: 10_000,
  model:            openai("gpt-4o"),
});

app.post("/ai/chat", async (req: ExpressReq, res: ExpressResp) => {
  const result = await expressGate.check(req.headers as Record<string, string>, req.body);
  if (result.requiresPayment) {
    const r = result.as402Response();
    const body = await r.json();
    res.status(402).set(Object.fromEntries(result.challengeHeaders)).json(body);
    return;
  }
  const content = await expressGate.generateText(req.body.messages);
  res.json({ content });
});

// ── 4. Payment tool in generateText() ─────────────────────────────────────────

const toolGate = new AlgoVoiVercelAI({
  algovoiKey:    process.env.ALGOVOI_KEY!,
  tenantId:      process.env.TENANT_ID!,
  payoutAddress: process.env.PAYOUT_ADDRESS!,
  protocol:      "mpp",
  network:       "algorand-mainnet",
});

const premiumKbTool = toolGate.asTool(
  async (query: string) => {
    // Replace with your actual premium content lookup
    return `Premium knowledge base answer to: ${query}`;
  },
  {
    toolName:        "premium_kb",
    toolDescription: "Access the premium knowledge base. Provide your query and a payment proof.",
  }
);

// Use with generateText + tools
async function chatWithPremiumKb(userMessage: string) {
  const model = openai("gpt-4o");
  const { generateText } = await import("ai");

  const result = await generateText({
    model,
    tools: { premium_kb: premiumKbTool },
    messages: [{ role: "user", content: userMessage }],
  });

  return result.text;
}

// ── 5. Anthropic / Google / Groq providers ─────────────────────────────────────

import { anthropic } from "@ai-sdk/anthropic";
import { google } from "@ai-sdk/google";
import { createOpenAI } from "@ai-sdk/openai";

// Anthropic Claude
const claudeGate = new AlgoVoiVercelAI({
  algovoiKey:    process.env.ALGOVOI_KEY!,
  tenantId:      process.env.TENANT_ID!,
  payoutAddress: process.env.PAYOUT_ADDRESS!,
  protocol:      "ap2",
  network:       "voi-mainnet",
  model:         anthropic("claude-opus-4-5"),
});

// Google Gemini
const geminiGate = new AlgoVoiVercelAI({
  algovoiKey:    process.env.ALGOVOI_KEY!,
  tenantId:      process.env.TENANT_ID!,
  payoutAddress: process.env.PAYOUT_ADDRESS!,
  protocol:      "x402",
  network:       "hedera-mainnet",
  model:         google("gemini-2.0-flash"),
});

// Groq (via OpenAI-compatible provider)
const groq = createOpenAI({
  baseURL: "https://api.groq.com/openai/v1",
  apiKey:  process.env.GROQ_API_KEY,
});
const groqGate = new AlgoVoiVercelAI({
  algovoiKey:    process.env.ALGOVOI_KEY!,
  tenantId:      process.env.TENANT_ID!,
  payoutAddress: process.env.PAYOUT_ADDRESS!,
  protocol:      "mpp",
  network:       "stellar-mainnet",
  model:         groq("llama-3.1-70b-versatile"),
});

// ── 6. x402 and AP2 protocols ─────────────────────────────────────────────────

// x402 — Hedera
const x402Gate = new AlgoVoiVercelAI({
  algovoiKey:       process.env.ALGOVOI_KEY!,
  tenantId:         process.env.TENANT_ID!,
  payoutAddress:    process.env.HEDERA_PAYOUT_ADDRESS!,
  protocol:         "x402",
  network:          "hedera-mainnet",
  amountMicrounits: 5_000,
  model:            openai("gpt-4o-mini"),
});

// AP2 — Algorand
const ap2Gate = new AlgoVoiVercelAI({
  algovoiKey:       process.env.ALGOVOI_KEY!,
  tenantId:         process.env.TENANT_ID!,
  payoutAddress:    process.env.PAYOUT_ADDRESS!,
  protocol:         "ap2",
  network:          "algorand-mainnet",
  amountMicrounits: 10_000,
  ap2ExpiresSec:    900,             // 15-minute CartMandate TTL
  model:            openai("gpt-4o"),
});

// AP2 Next.js handler — reads body for ap2_mandate field
export async function POSTAp2(req: Request): Promise<Response> {
  const body = await req.json() as { messages: unknown[]; ap2_mandate?: unknown };
  const result = await ap2Gate.check(req.headers, body);
  if (result.requiresPayment) return result.as402Response();
  const content = await ap2Gate.generateText(body.messages as Parameters<typeof ap2Gate.generateText>[0]);
  return Response.json({ content });
}

export { app, chatWithPremiumKb };
