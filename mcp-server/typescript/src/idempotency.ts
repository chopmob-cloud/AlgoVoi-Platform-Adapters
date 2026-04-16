/**
 * In-memory TTL cache for idempotency keys.
 *
 * Per-process / per-session for the stdio server — matches the §6.4
 * ALGOVOI_MCP.md requirement to dedupe payment-creation retries within a
 * short window.  Opportunistic sweep when the cache grows past 1 000 entries.
 */

const DEFAULT_TTL_MS = 24 * 60 * 60 * 1000;
const MAX_ENTRIES = 1_000;

interface Entry<T> {
  expiry: number;
  value: T;
}

export class IdempotencyCache<T = unknown> {
  private readonly ttlMs: number;
  private readonly store: Map<string, Entry<T>> = new Map();

  constructor(ttlMs: number = DEFAULT_TTL_MS) {
    this.ttlMs = ttlMs;
  }

  get(key: string): T | undefined {
    const entry = this.store.get(key);
    if (!entry) return undefined;
    if (Date.now() > entry.expiry) {
      this.store.delete(key);
      return undefined;
    }
    return entry.value;
  }

  set(key: string, value: T): void {
    this.store.set(key, { expiry: Date.now() + this.ttlMs, value });
    if (this.store.size > MAX_ENTRIES) {
      this.sweep();
    }
  }

  private sweep(): void {
    const now = Date.now();
    for (const [k, entry] of this.store) {
      if (now > entry.expiry) this.store.delete(k);
    }
  }

  get size(): number {
    return this.store.size;
  }
}
