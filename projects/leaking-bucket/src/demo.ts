import { setTimeout } from "node:timers/promises";
import { createClient } from "redis";
import { LeakingBucketRateLimiter } from "./rate-limiter.js";

const clientId = process.argv[2] ?? "demo-user";
const redis = createClient({
  url: process.env.REDIS_URL ?? "redis://localhost:6382",
  socket: { reconnectStrategy: false, connectTimeout: 5_000 },
});
redis.on("error", (error: Error) => console.error("Redis error:", error.message));

try {
  await redis.connect();
  const limiter = new LeakingBucketRateLimiter(redis);
  for (let request = 1; request <= 5; request++) {
    console.log({ clientId, request, ...(await limiter.enqueue(clientId, `request-${request}`)) });
  }

  while (true) {
    const result = await limiter.dequeue(clientId);
    if (result.request !== null) {
      console.log({ clientId, processedAt: new Date().toISOString(), ...result });
    }
    if (result.queueSize === 0) {
      break;
    }
    await setTimeout(result.retryAfterMs);
  }
} finally {
  if (redis.isOpen) {
    await redis.quit();
  }
}
