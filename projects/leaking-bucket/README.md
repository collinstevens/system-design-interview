# Leaking bucket rate limiter

TypeScript implementation of the bounded FIFO queue on pages 62–63 of _System Design Interview_, backed by Redis in Docker. Each client can queue four requests by default, and a worker releases one request every second.

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
mise.exe exec -- bun run --filter leaking-bucket redis:up
mise.exe exec -- bun run --filter leaking-bucket demo alice
mise.exe exec -- bun run --filter leaking-bucket redis:down
```

Use `mise.exe exec --` in PowerShell to bypass the shell wrapper, which can consume the `--` separator.

For a fresh client, the demo enqueues five requests: four fit and the fifth is rejected. It then runs a worker that prints the four requests in order, spaced at least one second apart. The first release waits one interval. Another client ID has its own queue and schedule.

The demo builds TypeScript and copies both Lua scripts to `dist/` before running with Node.js. Use `bun run build` to build separately. Shared linting, formatting, and type-check commands are documented in the [root README](../../README.md#shared-tooling).

Set `REDIS_URL` to use another Redis instance; the default is `redis://localhost:6382`. Docker binds to localhost on port 6382 and has persistence disabled. Stop it with `bun run redis:down`.

## Use

After `bun run build`, use the compiled module from a JavaScript ES module:

```js
import { setTimeout } from "node:timers/promises";
import { createClient } from "redis";
import { LeakingBucketRateLimiter } from "./dist/rate-limiter.js";

const redis = createClient({ url: "redis://localhost:6382" });
redis.on("error", console.error);
await redis.connect();

const limiter = new LeakingBucketRateLimiter(redis, 4, 1_000);
console.log(await limiter.enqueue("alice", "send-notification"));

while (true) {
  const result = await limiter.dequeue("alice");
  if (result.request !== null) {
    console.log("Process:", result.request);
  }
  if (result.queueSize === 0) {
    break;
  }
  await setTimeout(result.retryAfterMs);
}

await redis.quit();
```

The constructor accepts the Redis client, queue capacity, milliseconds between releases, and an optional key prefix. Capacity must be a positive safe integer. The interval must be a positive safe integer at most `Number.MAX_SAFE_INTEGER / 2`. Instances sharing a prefix must use the same policy; choose another prefix for a separate policy.

`enqueue(clientId, request)` accepts a nonempty request string and returns `allowed`, `queueSize`, and `remaining` queue slots. An allowed request has entered the queue and waits for a worker. Duplicate strings are separate FIFO entries.

`dequeue(clientId)` returns `request` (a string when released, otherwise `null`), `queueSize`, and `retryAfterMs`. A null request with a nonempty queue means the worker should wait that many milliseconds before trying again. An empty queue returns a zero retry delay; a long-running worker should wait for new work rather than poll in a tight loop. Redis errors propagate to the caller.

## Algorithm

Each client has a Redis list and a timestamp for the next permitted release. One atomic Lua script checks capacity and appends to the tail. When the queue is full, it rejects the new request without modifying the queue or schedule. A second atomic script checks Redis server time and removes at most one request from the head when due. Concurrent producers cannot overfill the queue, and concurrent workers cannot release multiple requests in one interval.

The first enqueue into an idle queue schedules a release one interval later. Each release schedules the next for one interval after its actual release time. A delayed worker resumes at the configured pace; unused intervals do not accumulate a burst allowance. Keeping the release timestamp briefly after the queue empties also prevents an immediate release when it refills.

The worker must call `dequeue` to perform releases; elapsed time alone does not remove queued work. The timestamp expires after its interval, but pending requests do not expire. Redis removes the list when its final item is popped. Work per operation is constant and each client's queue holds at most `capacity` strings, so memory also depends on payload sizes.

This exercise demonstrates queue admission and pacing. Dequeue removes an item before the caller processes it; there is no acknowledgement or retry mechanism for a worker crash. The Docker configuration also loses queued work on restart. The scripts target the standalone Redis instance supplied here and assume its clock progresses normally. Old queued requests can delay newer ones, which is the tradeoff described in the book.
