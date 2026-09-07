# Rate limiter Z3 models

Executable Python models of [token-bucket.lua](../projects/token-bucket/src/token-bucket.lua) and [sliding-window-log.lua](../projects/sliding-window-log/src/sliding-window-log.lua), using the official [Z3 Python bindings](https://github.com/Z3Prover/z3#z3-bindings). Redis and Docker are not required.

These are handwritten mathematical models, not an automatic verification of Lua execution. They establish the properties below under explicit assumptions. The runner checks SHA-256 digests of both Lua files, normalizing line endings, so a changed script requires reviewing the corresponding model before rerunning the proofs. A matching digest prevents unnoticed source drift; it does not establish equivalence between Lua and Python.

## Run

From the repository root in PowerShell:

```powershell
mise.exe exec -- python -m venv .venv
.venv/Scripts/python.exe -m pip install -r models/requirements.txt
.venv/Scripts/python.exe models/verify.py
```

On macOS or Linux:

```sh
mise exec -- python -m venv .venv
.venv/bin/python -m pip install -r models/requirements.txt
.venv/bin/python models/verify.py
```

Python is already pinned in `mise.toml`; run `mise install` first if needed. The virtual environment keeps the proof dependency separate from the application dependencies.

The default run proves 16 obligations and finds four expected witnesses. Each `PROVED` result means Z3 found the negation of that property unsatisfiable for every input satisfying its assumptions. Assumptions are checked for satisfiability first to prevent vacuous proofs. Each `WITNESS` is a satisfiable example illustrating a deliberate behavior or a failed guarantee when an assumption is removed.

An unexpected counterexample, inconsistent assumptions, solver timeout, or `unknown` result causes a nonzero exit. Queries have a ten-second timeout each. Increase the sliding-window history bound or timeout when exploring:

```powershell
.venv/Scripts/python.exe models/verify.py --depth 12 --timeout-ms 30000
```

The Python model files are independent of the TypeScript build, lint, and formatting commands. The verification runner is their executable check.

## Assumptions and scope

- Each call is one atomic Redis script execution for one client. Concurrent calls are represented by their serialized execution order. Configuration is fixed for that client's key.
- Capacity, refill size, interval, limit, and window are positive integers. Timestamps are nonnegative integer milliseconds. The models use unbounded Z3 integers and exact integer arithmetic.
- Lua uses floating-point numbers. These proofs assume its arithmetic agrees with the integer model, including division followed by `floor`, remainder, and serialization. They do not prove that agreement across every constructor-accepted safe integer; safe integer inputs alone do not establish exact intermediate arithmetic or division. Floating-point rounding, Redis integer limits, resource exhaustion, command failures, and response decoding are outside the proofs.
- Buckets start absent or in a valid state: both hash fields exist, tokens are between zero and capacity, and the last refill time is nonnegative. Other writers, partial hashes, configuration changes, deletion, eviction, and data loss are excluded. An intentional reset starts a new history.
- Sliding logs start empty. Members are unique per attempt in the main proofs, matching the TypeScript caller's intended UUID behavior. The model assumes uniqueness rather than proving UUID collision freedom.
- The main rolling-window and refill-schedule guarantees assume nondecreasing server timestamps. Equal timestamps are allowed. Clock rollback is explored separately; token bounds, token accounting, and rejection preservation do not require monotonic time.

## Token bucket

[token_bucket.py](token_bucket.py) translates the Lua arithmetic and branches directly. `step` takes symbolic configuration, time, token count, and last refill time. Its result contains the stored state and the reply, plus the refill count for accounting. The initialization obligation supplies `capacity` and `now`, corresponding to the Lua defaults for a missing hash.

| Lua operation                         | Model                                                                   |
| ------------------------------------- | ----------------------------------------------------------------------- |
| Clamp elapsed time to zero            | `If(now >= last_refill_ms, now - last_refill_ms, 0)`                    |
| `floor(elapsedMs / refillIntervalMs)` | Z3 integer division with nonnegative elapsed time and positive interval |
| Refill and cap at capacity            | Conditional addition and minimum, only for completed intervals          |
| Carry partial intervals forward       | `now - elapsed_ms % interval_ms`                                        |
| Consume a token or reject             | Symbolic `allowed`, resulting tokens, and retry delay                   |
| Persist the hash                      | Return the token count and last refill time as the next state           |

The obligations establish initialization, preservation of valid state, the admission condition, whole-interval schedule advancement, the schedule's alignment with the first request, rejection without postponing refills, retry bounds, the earliest successful retry without competing requests, cumulative token accounting, and saturation at capacity.

The accounting invariant uses two ghost counters that are not stored in Redis: `spent` counts accepted requests and `issued` counts tokens offered by completed refills, including tokens discarded at capacity:

```text
tokens + spent <= capacity + issued
```

Initialization establishes this inequality with zero spent and issued tokens. Each transition preserves it after adding one to `spent` when allowed and `refill_count * refill_tokens` to `issued`. Together with the schedule obligations, this gives, for any number of calls with nondecreasing time:

```text
accepted_since_start <= capacity + refill_tokens * floor((now - start) / interval)
```

This is a batched token bucket. It can admit bursts around refill boundaries; the formula is anchored to the first request, not an arbitrary rolling window. The state and accounting arguments are inductive, with no request-count bound.

## Sliding window log

[sliding_window_log.py](sliding_window_log.py) models each sorted-set entry with a member, timestamp, and symbolic presence flag. A transition expires eligible state, removes scores strictly below `now - window`, replaces an existing entry with the same member as `ZADD` would, inserts the attempt, counts members, refreshes expiration, and admits only when the count is at most the limit. Insertion happens even for a rejected attempt.

The model uses eager expiration at `last_attempt + window + 1`. The expiration obligation proves that every entry is already strictly outside the window at that time. Later physical deletion therefore gives the same decisions after pruning under nondecreasing time. The extra millisecond preserves the inclusive lower endpoint. See Redis's [score-range removal](https://redis.io/docs/latest/commands/zremrangebyscore/) and [millisecond expiration](https://redis.io/docs/latest/commands/pexpire/) semantics.

Two complementary arguments cover the window:

1. **Induction without a history bound.** Advancing time and pruning can only reduce the number of accepted requests still in the window. Call that number `live_accepted`; it cannot exceed the total `live_count` of retained attempts. An accepted insertion requires `live_count + 1 <= limit`, so it preserves `live_accepted + 1 <= limit`. A rejected insertion leaves the accepted count unchanged. The initialization, pruning, expiration, and cardinality obligations establish this argument. The link from entry membership to cardinality is a mathematical abstraction, not a mechanically proved refinement of arbitrary Redis sorted sets.
2. **Bounded execution of the entry model.** For every prefix of up to eight requests by default, Z3 compares the stored count and decision against an independent count of all attempts in `[now - window, now]`, and checks the number of accepted attempts in that window. Times, positive configuration values, and distinct members are symbolic. This includes simultaneous arrivals, exact endpoints, rejected attempts, and idle expiration. Only the number of requests is bounded. Increasing `--depth` extends this check; it does not turn it into an unbounded equivalence proof.

## Witnesses

The runner asks Z3 to construct these examples. Concrete values can vary between solver versions.

| Behavior                                                 | Example in milliseconds                                                                                                                                                                                               |
| -------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Token retry can exceed one interval after clock rollback | Empty bucket, interval `1`, last refill `1`, now `0`: reject with retry `2`. The elapsed-time clamp prevents an early refill.                                                                                         |
| Rejected attempts prolong sliding-window rejection       | Limit `1`, window `1`, attempts at `0`, `1`, `2`: accept, reject, reject. At `2`, the accepted attempt is gone but the rejected attempt at `1` still counts.                                                          |
| Reusing a sorted-set member undercounts requests         | Limit `1`, two attempts at `0` using the same member: both accepted, stored count stays `1`.                                                                                                                          |
| Clock rollback can invalidate a rolling-window guarantee | Limit `2`, window `1`, unique attempts at `0`, `0`, `2`, `0`: all accepted. After pruning the first two attempts at time `2`, rollback to `0` admits another request, making three accepted attempts timestamped `0`. |

The last two witnesses explain why unique members and nondecreasing time are assumptions. They are not failures of the model runner. The Lua implementations are unchanged.
