import { readFileSync } from "node:fs";
import { Result, Schema } from "effect";
import type { RedisClientType } from "redis";

const enqueueScript = readFileSync(new URL("./enqueue.lua", import.meta.url), "utf8");
const dequeueScript = readFileSync(new URL("./dequeue.lua", import.meta.url), "utf8");

export const EnqueueResult = Schema.Struct({
  allowed: Schema.Boolean,
  queueSize: Schema.Natural,
  remaining: Schema.Natural,
});

export type EnqueueResult = typeof EnqueueResult.Type;

export const DequeueResult = Schema.Struct({
  request: Schema.NullOr(Schema.String),
  queueSize: Schema.Natural,
  retryAfterMs: Schema.Natural,
});

export type DequeueResult = typeof DequeueResult.Type;

const EnqueueReply = Schema.Tuple([
  Schema.BooleanFromBit.annotate({ title: "allowed" }),
  Schema.Natural.annotate({ title: "queueSize" }),
]);

const DequeueReply = Schema.Tuple([
  Schema.NullOr(Schema.String).annotate({ title: "request" }),
  Schema.Natural.annotate({ title: "queueSize" }),
  Schema.Natural.annotate({ title: "retryAfterMs" }),
]);

const decodeEnqueueReply = Schema.decodeUnknownResult(EnqueueReply, {
  onExcessProperty: "error",
});
const decodeDequeueReply = Schema.decodeUnknownResult(DequeueReply, {
  onExcessProperty: "error",
});

export class LeakingBucketRateLimiter {
  constructor(
    private readonly redis: RedisClientType,
    private readonly capacity = 4,
    private readonly leakIntervalMs = 1_000,
    private readonly keyPrefix = "rate-limit:leaking-bucket",
  ) {
    if (!Number.isSafeInteger(capacity) || capacity < 1) {
      throw new RangeError("capacity must be a positive safe integer");
    }
    if (
      !Number.isSafeInteger(leakIntervalMs) ||
      leakIntervalMs < 1 ||
      leakIntervalMs > Number.MAX_SAFE_INTEGER / 2
    ) {
      throw new RangeError(
        "leakIntervalMs must be a positive safe integer at most Number.MAX_SAFE_INTEGER / 2",
      );
    }
    if (!keyPrefix) {
      throw new TypeError("keyPrefix must not be empty");
    }
  }

  async enqueue(clientId: string, request: string): Promise<EnqueueResult> {
    if (!request) {
      throw new TypeError("request must not be empty");
    }

    const result = await this.redis.eval(enqueueScript, {
      keys: this.keys(clientId),
      arguments: [String(this.capacity), String(this.leakIntervalMs), request],
    });

    const [allowed, queueSize] = Result.getOrThrowWith(
      decodeEnqueueReply(result),
      (cause) => new Error("Unexpected enqueue response from Redis", { cause }),
    );
    return { allowed, queueSize, remaining: Math.max(0, this.capacity - queueSize) };
  }

  async dequeue(clientId: string): Promise<DequeueResult> {
    const result = await this.redis.eval(dequeueScript, {
      keys: this.keys(clientId),
      arguments: [String(this.leakIntervalMs)],
    });

    const [request, queueSize, retryAfterMs] = Result.getOrThrowWith(
      decodeDequeueReply(result),
      (cause) => new Error("Unexpected dequeue response from Redis", { cause }),
    );
    return { request, queueSize, retryAfterMs };
  }

  private keys(clientId: string): string[] {
    if (!clientId) {
      throw new TypeError("clientId must not be empty");
    }
    return [`${this.keyPrefix}:${clientId}:queue`, `${this.keyPrefix}:${clientId}:next-drain`];
  }
}
