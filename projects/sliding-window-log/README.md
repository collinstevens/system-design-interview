# Sliding window log rate limiter

TypeScript implementation of the algorithm on pages 66–67 of _System Design Interview_, backed by Redis in Docker. The default limit is two requests per rolling minute, per client.

## Run

Requires mise and Docker with Compose. Run `mise install` from the repository root to install the pinned tools and enable the Git hooks. Run `mise exec -- bun install --frozen-lockfile` from the repository root to install dependencies for all workspaces. Bun manages dependencies and runs scripts. The TypeScript compiler and Node.js runtime use the versions pinned in the root `mise.toml`.

```sh
bun run redis:up
bun run check
bun run demo alice
```

Run these commands from this directory with mise activated, or prefix each command with `mise exec --`. For a fresh client, the demo sends three requests: the first two are allowed and the third is rejected. Running it again within the window continues counting requests for that client. Use a different client ID for a separate limit, or wait more than a minute after the last attempt.

In PowerShell, use `mise.exe exec --` for that prefix to bypass the shell wrapper, which can consume the `--` separator. This also applies to the root install command above.

The demo compiles TypeScript and copies `src/sliding-window-log.lua` into `dist/` before running it with Node.js. Use `bun run build` to build separately. Use Bun from the repository root to install or update dependencies and keep the root `bun.lock` in sync. Runtime dependency versions come from the root catalog.

Set `REDIS_URL` to use another Redis instance; the default is `redis://localhost:6379`. The Docker instance binds to localhost on port 6379 and has persistence disabled. Stop it with `bun run redis:down`.

## Shared tooling

Linting, formatting, Git hooks, and the TypeScript baseline are configured at the repository root. See the [shared tooling instructions](../../README.md#shared-tooling) for commands and editor setup. Run `bun run check` here to type-check this exercise, or run it from the repository root to check all exercises.

## Use

After `bun run build`, use the compiled module from a JavaScript ES module:

```js
import { createClient } from "redis";
import { SlidingWindowLogRateLimiter } from "./dist/rate-limiter.js";

const redis = createClient();
redis.on("error", console.error);
await redis.connect();

const limiter = new SlidingWindowLogRateLimiter(redis, 2, 60_000);
const result = await limiter.check("alice");
console.log(result.allowed, result.requestCount, result.remaining);

await redis.quit();
```

The caller uses `allowed` to decide whether to process the request. Redis errors propagate to the caller. All instances sharing a key prefix must use the same limit and window; pass a distinct fourth constructor argument to isolate different policies.

## Algorithm

Each client has a Redis sorted set. A single Lua script reads Redis server time, removes timestamps strictly older than the window start, inserts the current attempt, and accepts it only when the resulting count is within the limit. [Redis executes scripts atomically](https://redis.io/docs/latest/develop/programmability/), keeping concurrent decisions consistent.

The window includes both endpoints, `[now - windowMs, now]`, matching the book. UUID members keep requests distinct even when their timestamps match. Inactive logs expire after `windowMs + 1` milliseconds.

Rejected requests stay in the log, as in the pictured algorithm. Repeated rejected attempts can therefore prolong rejection, and memory grows with all attempts in the window rather than only accepted requests. `remaining` describes unused capacity immediately after this attempt.

## Formal model

The [Python Z3 model](../../models/README.md#sliding-window-log) checks inclusive boundaries, safe expiration, attempt counts, and rolling-window admission safety. It includes an inductive cardinality argument, bounded symbolic histories, and witnesses showing why unique members and nondecreasing time matter. Run it using the [model setup instructions](../../models/README.md#run).
