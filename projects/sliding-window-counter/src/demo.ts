import { createClient } from "redis";
import { SlidingWindowCounterRateLimiter } from "./rate-limiter.js";

const clientId = process.argv[2] ?? "demo-user";
const redis = createClient({
  url: process.env.REDIS_URL ?? "redis://localhost:6383",
  socket: { reconnectStrategy: false, connectTimeout: 5_000 },
});
redis.on("error", (error: Error) => console.error("Redis error:", error.message));

try {
  await redis.connect();
  const limiter = new SlidingWindowCounterRateLimiter(redis);
  for (let request = 1; request <= 8; request++) {
    console.log({ clientId, request, ...(await limiter.check(clientId)) });
  }
} finally {
  if (redis.isOpen) {
    await redis.quit();
  }
}
