import { readFileSync } from "node:fs";
import { Result, Schema } from "effect";
import type { RedisClientType } from "redis";

const tokenBucketScript = readFileSync(new URL("./token-bucket.lua", import.meta.url), "utf8");

export const RateLimitResult = Schema.Struct({
  allowed: Schema.Boolean,
  remaining: Schema.Natural,
  retryAfterMs: Schema.Natural,
});

export type RateLimitResult = typeof RateLimitResult.Type;

const RateLimitReply = Schema.Tuple([
  Schema.BooleanFromBit.annotate({ title: "allowed" }),
  Schema.Natural.annotate({ title: "remaining" }),
  Schema.Natural.annotate({ title: "retryAfterMs" }),
]);

const decodeRateLimitReply = Schema.decodeUnknownResult(RateLimitReply, {
  onExcessProperty: "error",
});

export class TokenBucketRateLimiter {
  constructor(
    private readonly redis: RedisClientType,
    private readonly capacity = 4,
    private readonly refillTokens = 4,
    private readonly refillIntervalMs = 60_000,
    private readonly keyPrefix = "rate-limit:token-bucket",
  ) {
    if (!Number.isSafeInteger(capacity) || capacity < 1) {
      throw new RangeError("capacity must be a positive safe integer");
    }
    if (!Number.isSafeInteger(refillTokens) || refillTokens < 1) {
      throw new RangeError("refillTokens must be a positive safe integer");
    }
    if (!Number.isSafeInteger(refillIntervalMs) || refillIntervalMs < 1) {
      throw new RangeError("refillIntervalMs must be a positive safe integer");
    }
    if (!keyPrefix) {
      throw new TypeError("keyPrefix must not be empty");
    }
  }

  async check(clientId: string): Promise<RateLimitResult> {
    if (!clientId) {
      throw new TypeError("clientId must not be empty");
    }

    const result = await this.redis.eval(tokenBucketScript, {
      keys: [`${this.keyPrefix}:${clientId}`],
      arguments: [String(this.capacity), String(this.refillTokens), String(this.refillIntervalMs)],
    });

    const [allowed, remaining, retryAfterMs] = Result.getOrThrowWith(
      decodeRateLimitReply(result),
      (cause) => new Error("Unexpected rate limiter response from Redis", { cause }),
    );
    return { allowed, remaining, retryAfterMs };
  }
}
