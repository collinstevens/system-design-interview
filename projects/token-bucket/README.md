# Token bucket rate limiter

TypeScript implementation of the algorithm on pages 58–62 of _System Design Interview_, backed by Redis in Docker. Each client starts with four tokens and receives four more every minute, up to a capacity of four, matching Figure 4-6.

## Run

Requires mise and Docker with Compose. From the repository root, run `mise install` and `mise exec -- bun install --frozen-lockfile` to install the pinned tools and workspace dependencies.

Run these commands from this directory with mise activated:

```sh
bun run redis:up
bun run demo alice
```

For a fresh client, the demo sends five requests: four are accepted and the fifth is rejected. Running it again uses the same bucket. Wait for the next refill or use another client ID to see accepted requests again.

In PowerShell, prefix commands with `mise.exe exec --` to bypass the activated shell wrapper. From the repository root:

```powershell
mise.exe exec -- bun run --filter token-bucket redis:up
mise.exe exec -- bun run --filter token-bucket demo alice
mise.exe exec -- bun run --filter token-bucket redis:down
```

The demo builds TypeScript and copies the Lua script into `dist/` before running with Node.js. `bun run check` type-checks the project, and `bun run build` builds it separately. See the [shared tooling instructions](../../README.md#shared-tooling) for repository checks.

Set `REDIS_URL` to use another Redis instance; the default is `redis://localhost:6380`. Docker binds to localhost on port 6380 so this project can run alongside the sliding window log project. Persistence is disabled. Stop Redis with `bun run redis:down`.

## Use

After building, import the compiled module from a JavaScript ES module:

```js
import { createClient } from "redis";
import { TokenBucketRateLimiter } from "./dist/rate-limiter.js";

const redis = createClient({ url: "redis://localhost:6380" });
redis.on("error", console.error);
await redis.connect();

const limiter = new TokenBucketRateLimiter(redis, 4, 2, 1_000);
const result = await limiter.check("alice");
console.log(result.allowed, result.remaining, result.retryAfterMs);

await redis.quit();
```

Constructor arguments are the Redis client, capacity, tokens added per refill, refill interval in milliseconds, and an optional key prefix. The example above models Figure 4-4: a capacity of four with two tokens added every second. Capacity, refill tokens, and refill interval must be positive safe integers.

The caller processes a request only when `allowed` is true. `remaining` is the token count after the decision. `retryAfterMs` is zero for an accepted request and the time until the next refill for a rejected request; other requests may consume those tokens first. Redis errors propagate to the caller.

Use client IDs for independent buckets, a shared ID for a global bucket, or distinct prefixes for endpoint policies. All instances sharing a prefix must use the same configuration.

## Algorithm

Each client has a Redis hash containing its token count and last refill time. One atomic Lua script reads Redis server time, adds tokens for completed refill intervals, caps the total at capacity, and consumes one token if available. An empty bucket rejects the request without consuming tokens or postponing the next refill. Concurrent callers share the same atomic decision.

Refills happen in whole batches, matching the photographed example. The interval starts at a client's first request. Refills are calculated when a request arrives, so no background timer is needed. Partial intervals carry forward, and unused tokens survive between refills up to capacity. Excess tokens are discarded.

For Figure 4-6, a request at 0 seconds leaves three tokens; three requests at 5 seconds empty the bucket; a request at 20 seconds is rejected; and the bucket receives four tokens at 60 seconds before processing the next request.

Each check uses constant time and each client uses constant storage. Hashes remain in Redis to preserve each client's refill schedule, so total storage grows with distinct clients. Deleting a client's key resets its bucket to full and starts a new schedule on its next request. This exercise leaves inactive-client cleanup to the caller.

## Formal model

The [Python Z3 model](../../models/README.md#token-bucket) proves token bounds, cumulative accounting, refill timing, and retry behavior under the documented assumptions. It also finds a clock-rollback example. Run it using the [model setup instructions](../../models/README.md#run).
