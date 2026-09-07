import { readFileSync } from "node:fs";
import { Result, Schema } from "effect";
import type { RedisClientType } from "redis";

const fixedWindowCounterScript = readFileSync(
  new URL("./fixed-window-counter.lua", import.meta.url),
  "utf8",
);

export const RateLimitResult = Schema.Struct({
  allowed: Schema.Boolean,
  requestCount: Schema.Int.check(Schema.isGreaterThan(0)),
  remaining: Schema.Natural,
  retryAfterMs: Schema.Natural,
});

export type RateLimitResult = typeof RateLimitResult.Type;

const RateLimitReply = Schema.Tuple([
  Schema.BooleanFromBit.annotate({ title: "allowed" }),
  Schema.Int.check(Schema.isGreaterThan(0)).annotate({ title: "requestCount" }),
  Schema.Natural.annotate({ title: "retryAfterMs" }),
]);

const decodeRateLimitReply = Schema.decodeUnknownResult(RateLimitReply, {
  onExcessProperty: "error",
});

export class FixedWindowCounterRateLimiter {
  constructor(
    private readonly redis: RedisClientType,
    private readonly limit = 3,
    private readonly windowMs = 1_000,
    private readonly keyPrefix = "rate-limit:fixed-window-counter",
  ) {
    if (!Number.isSafeInteger(limit) || limit < 1) {
      throw new RangeError("limit must be a positive safe integer");
    }
    if (!Number.isSafeInteger(windowMs) || windowMs < 1) {
      throw new RangeError("windowMs must be a positive safe integer");
    }
    if (!keyPrefix) {
      throw new TypeError("keyPrefix must not be empty");
    }
  }

  async check(clientId: string): Promise<RateLimitResult> {
    if (!clientId) {
      throw new TypeError("clientId must not be empty");
    }

    const result = await this.redis.eval(fixedWindowCounterScript, {
      keys: [`${this.keyPrefix}:${clientId}`],
      arguments: [String(this.windowMs), String(this.limit)],
    });

    const [allowed, requestCount, retryAfterMs] = Result.getOrThrowWith(
      decodeRateLimitReply(result),
      (cause) => new Error("Unexpected rate limiter response from Redis", { cause }),
    );
    return {
      allowed,
      requestCount,
      remaining: Math.max(0, this.limit - requestCount),
      retryAfterMs,
    };
  }
}
