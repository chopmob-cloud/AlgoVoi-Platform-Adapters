#!/usr/bin/env node
/**
 * AlgoVoi MCP Server (stdio transport).
 *
 * Exposes 8 tools to any MCP client (Claude Desktop, Claude Code, Cursor,
 * Windsurf, etc.) for creating AlgoVoi payment links, verifying payments,
 * and generating MPP / x402 challenges.
 *
 * Auth comes from env vars — never from tool arguments. See README.
 *
 * Run: `npx @algovoi/mcp-server` (once published) or `node dist/index.js`.
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

import { AlgoVoiClient } from "./client.js";
import {
  createPaymentLink,
  verifyPayment,
  prepareExtensionPayment,
  verifyWebhook,
  listNetworks,
  generateMppChallenge,
  verifyMppReceipt,
  verifyX402Proof,
  TOOL_SCHEMAS,
} from "./tools.js";

// ── env var wiring ────────────────────────────────────────────────────────────

function requireEnv(name: string): string {
  const v = process.env[name];
  if (!v || !v.trim()) {
    process.stderr.write(
      `\n[algovoi-mcp] missing required env var: ${name}\n` +
        `Set ALGOVOI_API_KEY, ALGOVOI_TENANT_ID, and ALGOVOI_PAYOUT_ADDRESS.\n\n`
    );
    process.exit(2);
  }
  return v;
}

const API_KEY = requireEnv("ALGOVOI_API_KEY");
const TENANT_ID = requireEnv("ALGOVOI_TENANT_ID");
const PAYOUT_ADDRESS = requireEnv("ALGOVOI_PAYOUT_ADDRESS");
const API_BASE = process.env.ALGOVOI_API_BASE || "https://api1.ilovechicken.co.uk";
const WEBHOOK_SECRET = process.env.ALGOVOI_WEBHOOK_SECRET;

const client = new AlgoVoiClient({
  apiBase: API_BASE,
  apiKey: API_KEY,
  tenantId: TENANT_ID,
  payoutAddress: PAYOUT_ADDRESS,
});

// ── MCP server ────────────────────────────────────────────────────────────────

const server = new Server(
  {
    name: "algovoi-mcp-server",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: TOOL_SCHEMAS as unknown as Array<{
    name: string;
    description: string;
    inputSchema: unknown;
  }>,
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: rawArgs } = request.params;
  const args = (rawArgs ?? {}) as Record<string, unknown>;

  try {
    const result = await dispatch(name, args);
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(result, null, 2),
        },
      ],
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({ error: message }, null, 2),
        },
      ],
      isError: true,
    };
  }
});

async function dispatch(
  name: string,
  args: Record<string, unknown>
): Promise<unknown> {
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
    default:
      throw new Error(`unknown tool: ${name}`);
  }
}

// ── stdio transport ───────────────────────────────────────────────────────────

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  process.stderr.write(
    `[algovoi-mcp] connected on stdio — ${TOOL_SCHEMAS.length} tools ready, api_base=${API_BASE}\n`
  );
}

main().catch((err) => {
  process.stderr.write(`[algovoi-mcp] fatal: ${err}\n`);
  process.exit(1);
});
