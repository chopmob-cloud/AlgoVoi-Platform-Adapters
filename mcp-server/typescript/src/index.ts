#!/usr/bin/env node
/**
 * AlgoVoi MCP Server (stdio transport).
 *
 * Exposes up to 8 tools to any MCP client (Claude Desktop, Claude Code,
 * Cursor, Windsurf) for creating AlgoVoi payment links, verifying payments,
 * and generating MPP / x402 challenges.
 *
 * Runtime pipeline per tool call::
 *
 *     raw args  →  schemas.parseX   (strict; extra=forbid)
 *              →  tool function     (business logic)
 *              →  redact.scrub      (strip secrets, truncate strings)
 *              →  audit.logCall     (stderr JSON)
 *
 * Env-var auth only.  Tool allow-list via `MCP_ENABLED_TOOLS`.
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

import { AlgoVoiClient } from "./client.js";
import { logCall } from "./audit.js";
import { scrub } from "./redact.js";
import { PARSERS, ValidationError } from "./schemas.js";
import {
  createPaymentLink,
  verifyPayment,
  prepareExtensionPayment,
  verifyWebhook,
  listNetworks,
  generateMppChallenge,
  verifyMppReceipt,
  verifyX402Proof,
  generateX402Challenge,
  generateAp2Mandate,
  verifyAp2Payment,
  TOOL_SCHEMAS,
} from "./tools.js";

// ── env var wiring ────────────────────────────────────────────────────────────

function requireEnv(name: string): string {
  const v = process.env[name];
  if (!v || !v.trim()) {
    process.stderr.write(
      `\n[algovoi-mcp] missing required env var: ${name}\n` +
        `Set ALGOVOI_API_KEY, ALGOVOI_TENANT_ID, and at least one payout address.\n\n`
    );
    process.exit(2);
  }
  return v;
}

function optionalEnv(name: string): string | undefined {
  const v = process.env[name];
  return v && v.trim() ? v.trim() : undefined;
}

const API_KEY      = requireEnv("ALGOVOI_API_KEY");
const TENANT_ID    = requireEnv("ALGOVOI_TENANT_ID");
const API_BASE     = process.env.ALGOVOI_API_BASE || "https://api1.ilovechicken.co.uk";
const WEBHOOK_SECRET = process.env.ALGOVOI_WEBHOOK_SECRET;

// Per-chain payout addresses. Per-chain vars take priority; ALGOVOI_PAYOUT_ADDRESS
// acts as a universal fallback for any chain not individually configured.
const PAYOUT_FALLBACK = optionalEnv("ALGOVOI_PAYOUT_ADDRESS");
const PAYOUT_ADDRESSES: Record<string, string> = {};
const CHAIN_ENV: [string, string][] = [
  ["algorand_mainnet", "ALGOVOI_PAYOUT_ALGORAND"],
  ["voi_mainnet",      "ALGOVOI_PAYOUT_VOI"],
  ["hedera_mainnet",   "ALGOVOI_PAYOUT_HEDERA"],
  ["stellar_mainnet",  "ALGOVOI_PAYOUT_STELLAR"],
];
for (const [key, envVar] of CHAIN_ENV) {
  const v = optionalEnv(envVar) ?? PAYOUT_FALLBACK;
  if (v) PAYOUT_ADDRESSES[key] = v;
}
if (Object.keys(PAYOUT_ADDRESSES).length === 0) {
  process.stderr.write(
    "\n[algovoi-mcp] no payout address configured.\n" +
    "Set ALGOVOI_PAYOUT_ALGORAND, ALGOVOI_PAYOUT_VOI, ALGOVOI_PAYOUT_HEDERA,\n" +
    "ALGOVOI_PAYOUT_STELLAR (or ALGOVOI_PAYOUT_ADDRESS as a universal fallback).\n\n"
  );
  process.exit(2);
}

function parseEnabledTools(raw: string | undefined): Set<string> | null {
  if (!raw || !raw.trim()) return null;
  const known  = new Set<string>(TOOL_SCHEMAS.map((t) => t.name));
  const listed = raw.split(",").map((s) => s.trim()).filter(Boolean);
  const valid  = listed.filter((n) => known.has(n));
  const bad    = listed.filter((n) => !known.has(n));
  if (bad.length > 0) {
    process.stderr.write(
      `[algovoi-mcp] warning: MCP_ENABLED_TOOLS contains unknown tools: ${JSON.stringify(bad)} — ignoring\n`
    );
  }
  return new Set(valid);
}

const ENABLED_TOOLS = parseEnabledTools(process.env.MCP_ENABLED_TOOLS);

const client = new AlgoVoiClient({
  apiBase:         API_BASE,
  apiKey:          API_KEY,
  tenantId:        TENANT_ID,
  payoutAddresses: PAYOUT_ADDRESSES,
});

// ── MCP server ────────────────────────────────────────────────────────────────

const server = new Server(
  { name: "algovoi-mcp-server", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

const visibleSchemas = ENABLED_TOOLS
  ? TOOL_SCHEMAS.filter((t) => ENABLED_TOOLS.has(t.name))
  : TOOL_SCHEMAS;

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: visibleSchemas as unknown as Array<{
    name: string;
    description: string;
    inputSchema: unknown;
  }>,
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: rawArgs } = request.params;
  const args = (rawArgs ?? {}) as Record<string, unknown>;

  if (ENABLED_TOOLS && !ENABLED_TOOLS.has(name)) {
    logCall({ tool_name: name, args, status: "rejected", duration_ms: 0, error_code: "ToolDisabled" });
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(
            { error: `tool '${name}' is not enabled (MCP_ENABLED_TOOLS)` },
            null,
            2
          ),
        },
      ],
      isError: true,
    };
  }

  const start = performance.now();
  try {
    const result = scrub(await dispatch(name, args));
    logCall({ tool_name: name, args, status: "ok", duration_ms: performance.now() - start });
    return {
      content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
    };
  } catch (err) {
    const isValidation = err instanceof ValidationError;
    const duration     = performance.now() - start;
    const message      = err instanceof Error ? err.message : String(err);
    logCall({
      tool_name:   name,
      args,
      status:      isValidation ? "rejected" : "error",
      duration_ms: duration,
      error_code:  isValidation ? "ValidationError" : (err instanceof Error ? err.name : "Error"),
    });
    return {
      content: [
        { type: "text", text: JSON.stringify({ error: message }, null, 2) },
      ],
      isError: true,
    };
  }
});

async function dispatch(
  name: string,
  rawArgs: Record<string, unknown>
): Promise<unknown> {
  const parser = PARSERS[name as keyof typeof PARSERS];
  if (!parser) {
    throw new Error(`unknown tool: ${name}`);
  }
  const args = parser(rawArgs);
  switch (name) {
    case "create_payment_link":
      return createPaymentLink(client, args as any);
    case "verify_payment":
      return verifyPayment(client, args as any);
    case "prepare_extension_payment":
      return prepareExtensionPayment(client, args as any);
    case "verify_webhook":
      return verifyWebhook(WEBHOOK_SECRET, args as any);
    case "list_networks":
      return listNetworks();
    case "generate_mpp_challenge":
      return generateMppChallenge(client, args as any);
    case "verify_mpp_receipt":
      return verifyMppReceipt(client, args as any);
    case "verify_x402_proof":
      return verifyX402Proof(client, args as any);
    case "generate_x402_challenge":
      return generateX402Challenge(client, args as any);
    case "generate_ap2_mandate":
      return generateAp2Mandate(client, args as any);
    case "verify_ap2_payment":
      return verifyAp2Payment(client, args as any);
    default:
      throw new Error(`unknown tool: ${name}`);
  }
}

// ── stdio transport ───────────────────────────────────────────────────────────

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  process.stderr.write(
    `[algovoi-mcp] connected on stdio — ${visibleSchemas.length} tools ready, ` +
      `webhook_secret=${WEBHOOK_SECRET ? "set" : "unset"}\n`
  );
}

main().catch((err) => {
  process.stderr.write(`[algovoi-mcp] fatal: ${err}\n`);
  process.exit(1);
});
