/**
 * Structured audit logging for every tool invocation (stderr only — stdout
 * is reserved for the MCP JSON-RPC frames).
 *
 * Implements §10 of ALGOVOI_MCP.md.  Raw arguments are hashed, never logged.
 */

import { createHash, randomBytes } from "node:crypto";

function hashArgs(args: unknown): string {
  let payload: string;
  try {
    payload = JSON.stringify(args, Object.keys(args ?? {}).sort());
  } catch {
    payload = String(args);
  }
  return createHash("sha256").update(payload).digest("hex").slice(0, 16);
}

export interface AuditEntry {
  tool_name: string;
  args: unknown;
  status: "ok" | "error" | "rejected";
  duration_ms: number;
  error_code?: string;
}

export function logCall(entry: AuditEntry): void {
  const record: Record<string, unknown> = {
    timestamp:   new Date().toISOString(),
    trace_id:    randomBytes(8).toString("hex"),
    tool_name:   entry.tool_name,
    args_hash:   hashArgs(entry.args),
    status:      entry.status,
    duration_ms: Math.round(entry.duration_ms * 100) / 100,
  };
  if (entry.error_code) record.error_code = entry.error_code;
  try {
    process.stderr.write(JSON.stringify(record) + "\n");
  } catch {
    // Never let audit log failures break a tool call.
  }
}
