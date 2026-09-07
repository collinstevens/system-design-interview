from dataclasses import dataclass

from z3 import And, ArithRef, BoolRef, BoolVal, Distinct, If, Int, Ints, IntVal, Sum

from proof import Proofs


@dataclass(frozen=True)
class Entry:
    member: ArithRef
    timestamp: ArithRef
    present: BoolRef


@dataclass(frozen=True)
class LogResult:
    entries: tuple[Entry, ...]
    expires_at: ArithRef
    count: ArithRef
    allowed: BoolRef


def step(
    entries: tuple[Entry, ...],
    expires_at: ArithRef,
    window_ms: ArithRef,
    limit: ArithRef,
    now: ArithRef,
    member: ArithRef,
) -> LogResult:
    retained = tuple(
        Entry(
            entry.member,
            entry.timestamp,
            And(
                entry.present,
                now < expires_at,
                entry.timestamp >= now - window_ms,
                entry.member != member,
            ),
        )
        for entry in entries
    )
    entries = (*retained, Entry(member, now, BoolVal(True)))
    count = Sum([If(entry.present, 1, 0) for entry in entries])
    return LogResult(entries, now + window_ms + 1, count, count <= limit)


def trace(
    times: list[ArithRef], members: list[ArithRef], window: ArithRef, limit: ArithRef
) -> list[LogResult]:
    entries = ()
    expires_at = IntVal(0)
    results = []
    for now, member in zip(times, members, strict=True):
        result = step(entries, expires_at, window, limit, now, member)
        results.append(result)
        entries, expires_at = result.entries, result.expires_at
    return results


def attempts_in_window(times: list[ArithRef], now: ArithRef, window: ArithRef) -> ArithRef:
    return Sum([If(And(time >= now - window, time <= now), 1, 0) for time in times])


def verify(proofs: Proofs, depth: int) -> None:
    window, limit, now, last, timestamp = Ints("sw_window sw_limit sw_now sw_last sw_timestamp")
    config = [window > 0, limit > 0]
    retained = timestamp >= now - window
    proofs.prove(
        "sliding window: pruning retains exactly the closed window under monotonic time",
        [*config, timestamp >= 0, now >= timestamp],
        retained == And(timestamp >= now - window, timestamp <= now),
    )
    boundary = step(
        (Entry(IntVal(0), now - window, BoolVal(True)),),
        now + 1,
        window,
        limit,
        now,
        IntVal(1),
    )
    older = step(
        (Entry(IntVal(0), now - window - 1, BoolVal(True)),),
        now + 1,
        window,
        limit,
        now,
        IntVal(1),
    )
    proofs.prove(
        "sliding window: the lower endpoint survives and one millisecond older is removed",
        [*config, now >= window + 1],
        And(boundary.count == 2, older.count == 1),
    )
    proofs.prove(
        "sliding window: expiration cannot discard an attempt still in the closed window",
        [*config, timestamp >= 0, timestamp <= last, now >= last + window + 1],
        timestamp < now - window,
    )
    initial = step((), IntVal(0), window, limit, now, IntVal(0))
    proofs.prove(
        "sliding window: first request establishes the acceptance bound",
        [*config, now >= 0],
        And(initial.allowed, initial.count == 1, initial.count <= limit),
    )
    old_accepted, live_accepted, live_count = Ints("sw_old_accepted sw_live_accepted sw_live_count")
    admitted = live_count + 1 <= limit
    next_accepted = live_accepted + If(admitted, 1, 0)
    proofs.prove(
        "sliding window: at most limit accepted requests per window is inductive",
        [
            *config,
            old_accepted >= 0,
            old_accepted <= limit,
            live_accepted >= 0,
            live_accepted <= old_accepted,
            live_count >= live_accepted,
        ],
        And(next_accepted <= limit, next_accepted <= live_count + 1),
    )

    times = [Int(f"sw_time_{i}") for i in range(depth)]
    members = [Int(f"sw_member_{i}") for i in range(depth)]
    assumptions = [
        *config,
        times[0] >= 0,
        Distinct(*members),
        *(later >= earlier for earlier, later in zip(times, times[1:])),
    ]
    results = trace(times, members, window, limit)
    properties = []
    for i, result in enumerate(results):
        expected_count = attempts_in_window(times[: i + 1], times[i], window)
        accepted_count = Sum(
            [
                If(And(results[j].allowed, times[j] >= times[i] - window), 1, 0)
                for j in range(i + 1)
            ]
        )
        properties.extend(
            [
                result.count == expected_count,
                result.allowed == (expected_count <= limit),
                accepted_count <= limit,
            ]
        )
    proofs.prove(
        f"sliding window: exact attempt counts, decisions and safety through {depth} requests",
        assumptions,
        And(*properties),
    )

    first, second, third = Ints("sw_first sw_second sw_third")
    unique_members = [IntVal(i) for i in range(3)]
    times = [first, second, third]
    results = trace(times, unique_members, window, limit)
    proofs.witness(
        "sliding window: a rejected attempt prolongs rejection after the accepted one ages out",
        [
            window > 0,
            limit == 1,
            first == 0,
            second > first,
            third > second,
            results[0].allowed,
            ~results[1].allowed,
            ~results[2].allowed,
            first < third - window,
        ],
        {"window": window, "first": first, "second": second, "third": third},
    )
    collisions = trace([first, second], [IntVal(0), IntVal(0)], window, limit)
    proofs.witness(
        "sliding window: reusing a member can exceed the request limit",
        [
            *config,
            limit == 1,
            first == 0,
            second == first,
            collisions[0].allowed,
            collisions[1].allowed,
        ],
        {"window": window, "first": first, "second": second, "stored_count": collisions[1].count},
    )
    rollback_times = [first, first, second, third]
    rollback = trace(rollback_times, [IntVal(i) for i in range(4)], window, limit)
    proofs.witness(
        "sliding window: clock rollback can revisit a window whose history was discarded",
        [
            *config,
            limit == 2,
            first == 0,
            second > first + window,
            third == first,
            *(result.allowed for result in rollback),
            attempts_in_window(rollback_times, third, window) > limit,
        ],
        {
            "window": window,
            "limit": limit,
            "first_two_requests": first,
            "third_request": second,
            "fourth_request": third,
            "stored_count": rollback[-1].count,
        },
    )
