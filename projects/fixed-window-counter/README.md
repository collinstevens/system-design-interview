# Fixed window counter rate limiter

TypeScript implementation of the algorithm on pages 64–65 of _System Design Interview_, backed by Redis in Docker. The default limit is three requests per clock-aligned second, per client, matching Figure 4-8.

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
mise.exe exec -- bun run --filter fixed-window-counter redis:up
mise.exe exec -- bun run --filter fixed-window-counter demo alice
mise.exe exec -- bun run --filter fixed-window-counter redis:down
```

Use `mise.exe exec --` in PowerShell to bypass the shell wrapper, which can consume the `--` separator.

The demo sends four requests. For a fresh client, if all four arrive in the same second, the first three are allowed and the fourth is rejected. Requests crossing a second boundary use a fresh counter. Repeated runs share the client's current counter; another client ID has its own limit.

The demo builds TypeScript and copies the Lua script to `dist/` before running with Node.js. Use `bun run build` to build separately. Shared linting, formatting, and type-check commands are documented in the [root README](../../README.md#shared-tooling).

Set `REDIS_URL` to use another Redis instance; the default is `redis://localhost:6381`. Docker binds to localhost on port 6381 so this exercise can run alongside the other rate limiters. Persistence is disabled. Stop it with `bun run redis:down`.

## Use

After `bun run build`, use the compiled module from a JavaScript ES module:

```js
import { createClient } from "redis";
import { FixedWindowCounterRateLimiter } from "./dist/rate-limiter.js";

const redis = createClient({ url: "redis://localhost:6381" });
redis.on("error", console.error);
await redis.connect();

const limiter = new FixedWindowCounterRateLimiter(redis, 3, 1_000);
const result = await limiter.check("alice");
console.log(result);

await redis.quit();
```

The constructor accepts the Redis client, a positive integer limit, a positive integer window duration in milliseconds, and an optional key prefix. Instances sharing a prefix must use the same policy; use a distinct prefix for each policy.

`check` returns `allowed`, `requestCount` (including rejected attempts in this window), `remaining` (unused quota, never negative), and `retryAfterMs` (zero when allowed, otherwise the milliseconds until the next window). The caller decides whether to process the request. Redis errors propagate to the caller.

## Algorithm

Time is divided into equal intervals aligned to the Unix epoch. With `windowMs = 60_000`, counters reset on round minutes; with `windowMs = 1_000`, they reset on round seconds. Each window includes its start and excludes its end.

A single atomic Lua script reads Redis server time, resets the client's counter if its stored window start differs from the current window start, and increments the counter. It sets expiration to the next aligned boundary using `windowMs - now % windowMs`. Every attempt increments the counter, and only counts at or below the limit are admitted. Rejected attempts do not move the expiration past that boundary. The first request in a new window starts at one, even if the previous key is still present.

Each active client uses one Redis hash containing the window start and an integer counter, with constant work and storage per client. Inactive counters expire automatically. All callers use Redis time and the atomic script so concurrent requests share a consistent admission decision. This assumes the Redis clock progresses normally and counters are not evicted or lost during a window.

The tradeoff in Figure 4-9 remains: with five requests per minute, five requests just before a minute boundary and five just after it can all pass. Each fixed minute respects its limit, but a rolling minute spanning the boundary can contain ten accepted requests.
