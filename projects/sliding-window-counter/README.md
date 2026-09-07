# Sliding window counter rate limiter

TypeScript implementation of the weighted counter algorithm on pages 67–69 of _System Design Interview_, backed by Redis in Docker. The default limit is seven requests per approximate rolling minute, per client, matching the text accompanying Figure 4-11.

## Run

Requires mise and Docker with Compose. From the repository root, run `mise install` and `mise exec -- bun install --frozen-lockfile` to install the pinned tools and workspace dependencies.

Run these commands from this directory with mise activated:

```sh
bun run redis:up
bun run check
bun run demo alice
```

Alternatively, from the repository root in PowerShell:

```powershell
mise.exe exec -- bun run --filter sliding-window-counter redis:up
mise.exe exec -- bun run --filter sliding-window-counter demo alice
mise.exe exec -- bun run --filter sliding-window-counter redis:down
```

Use `mise.exe exec --` in PowerShell to bypass the shell wrapper, which can consume the `--` separator.

The demo sends eight requests. For a fresh client, if all arrive in the same minute, the first seven are allowed and the eighth is rejected. Running it again reuses that client's current and previous counters. Use another client ID for a separate limit; capacity gradually recovers during the following minute.

The demo builds TypeScript and copies the Lua script to `dist/` before running with Node.js. Use `bun run build` to build separately. Shared linting, formatting, and type-check commands are documented in the [root README](../../README.md#shared-tooling).

Set `REDIS_URL` to use another Redis instance; the default is `redis://localhost:6383`. Docker binds to localhost on port 6383 and has persistence disabled. Stop it with `bun run redis:down`.

## Use

After `bun run build`, use the compiled module from a JavaScript ES module:

```js
import { createClient } from "redis";
import { SlidingWindowCounterRateLimiter } from "./dist/rate-limiter.js";

const redis = createClient({ url: "redis://localhost:6383" });
redis.on("error", console.error);
await redis.connect();

const limiter = new SlidingWindowCounterRateLimiter(redis, 7, 60_000);
console.log(await limiter.check("alice"));

await redis.quit();
```

The constructor accepts the Redis client, limit, window duration in milliseconds, and an optional key prefix. The limit must be a positive safe integer. The window must be a positive safe integer at most `Number.MAX_SAFE_INTEGER / 2`, leaving room for two-window expiration arithmetic. Instances sharing a prefix must use the same policy; use a distinct prefix for each policy.

`check` returns `allowed`, `estimatedRequestCount` (the rounded estimate after this attempt), and `remaining` (unused estimated capacity, never negative). The caller decides whether to process the request. Redis errors propagate to the caller.

## Algorithm

Each client has a Redis hash containing the current window start and two counts of accepted requests. Windows align to the Unix epoch. At the next boundary, the current count becomes the previous count and a fresh current count starts at zero. After skipping at least one whole intervening window, both counts reset.

The estimate weights the previous window by the fraction still overlapping the rolling window:

```text
overlap = (windowMs - elapsedInCurrentWindowMs) / windowMs
estimate = floor(currentCount + previousCount * overlap)
allowed = estimate < limit
```

As in the book's example, the estimate rounds down. An allowed request increments the current counter and the returned estimate by one; rejected attempts leave both counters unchanged. For five previous requests and three current requests at 30% through the minute, the estimate is `floor(3 + 5 * 0.7) = 6`. With a limit of seven, one more request is accepted, returning an estimate of seven. Another at the same time is rejected.

A single atomic Lua script reads Redis server time, rotates the counters, makes the decision, and saves state. This keeps concurrent callers consistent. State expires at the end of the following fixed window, when its current count can no longer contribute. Expiring at the current boundary would discard history too early.

Each active client uses constant storage and each decision takes constant work. This smooths the fixed window boundary burst, but the estimate assumes requests were evenly distributed in the previous window. It can overcount or undercount actual rolling traffic, and rounding down admits fractional headroom. It does not guarantee an exact rolling-window maximum. Calculations use Lua floating-point arithmetic. The implementation assumes the Redis clock progresses normally and state is not evicted or lost while relevant.
