import { readFileSync } from "node:fs";
import { Result, Schema } from "effect";
import type { RedisClientType } from "redis";

const slidingWindowCounterScript = readFileSync(
  new URL("./sliding-window-counter.lua", import.meta.url),
  "utf8",
);

export const RateLimitResult = Schema.Struct({
  allowed: Schema.Boolean,
  estimatedRequestCount: Schema.Natural,
  remaining: Schema.Natural,
});

export type RateLimitResult = typeof RateLimitResult.Type;

const RateLimitReply = Schema.Tuple([
  Schema.BooleanFromBit.annotate({ title: "allowed" }),
  Schema.Natural.annotate({ title: "estimatedRequestCount" }),
]);

const decodeRateLimitReply = Schema.decodeUnknownResult(RateLimitReply, {
  onExcessProperty: "error",
});

export class SlidingWindowCounterRateLimiter {
  constructor(
    private readonly redis: RedisClientType,
    private readonly limit = 7,
    private readonly windowMs = 60_000,
    private readonly keyPrefix = "rate-limit:sliding-window-counter",
  ) {
    if (!Number.isSafeInteger(limit) || limit < 1) {
      throw new RangeError("limit must be a positive safe integer");
    }
    if (!Number.isSafeInteger(windowMs) || windowMs < 1 || windowMs > Number.MAX_SAFE_INTEGER / 2) {
      throw new RangeError(
        "windowMs must be a positive safe integer at most Number.MAX_SAFE_INTEGER / 2",
      );
    }
    if (!keyPrefix) {
      throw new TypeError("keyPrefix must not be empty");
    }
  }

  async check(clientId: string): Promise<RateLimitResult> {
    if (!clientId) {
      throw new TypeError("clientId must not be empty");
    }

    const result = await this.redis.eval(slidingWindowCounterScript, {
      keys: [`${this.keyPrefix}:${clientId}`],
      arguments: [String(this.windowMs), String(this.limit)],
    });

    const [allowed, estimatedRequestCount] = Result.getOrThrowWith(
      decodeRateLimitReply(result),
      (cause) => new Error("Unexpected rate limiter response from Redis", { cause }),
    );
    return {
      allowed,
      estimatedRequestCount,
      remaining: Math.max(0, this.limit - estimatedRequestCount),
    };
  }
}
