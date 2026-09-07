from dataclasses import dataclass

from z3 import And, ArithRef, BoolRef, If, Implies, Ints

from proof import Proofs


@dataclass(frozen=True)
class BucketResult:
    tokens: ArithRef
    last_refill_ms: ArithRef
    allowed: BoolRef
    retry_after_ms: ArithRef
    refill_count: ArithRef


def step(
    capacity: ArithRef,
    refill_tokens: ArithRef,
    interval_ms: ArithRef,
    now: ArithRef,
    tokens: ArithRef,
    last_refill_ms: ArithRef,
) -> BucketResult:
    elapsed_ms = If(now >= last_refill_ms, now - last_refill_ms, 0)
    refill_count = elapsed_ms / interval_ms
    replenished = tokens + refill_count * refill_tokens
    available = If(
        refill_count > 0,
        If(replenished < capacity, replenished, capacity),
        tokens,
    )
    last_refill_ms = If(
        refill_count > 0, now - elapsed_ms % interval_ms, last_refill_ms
    )
    allowed = available >= 1
    return BucketResult(
        tokens=If(allowed, available - 1, available),
        last_refill_ms=last_refill_ms,
        allowed=allowed,
        retry_after_ms=If(allowed, 0, interval_ms - (now - last_refill_ms)),
        refill_count=refill_count,
    )


def verify(proofs: Proofs) -> None:
    capacity, refill, interval, now, tokens, last = Ints(
        "tb_capacity tb_refill tb_interval tb_now tb_tokens tb_last"
    )
    config = [capacity > 0, refill > 0, interval > 0, now >= 0]
    valid = [*config, tokens >= 0, tokens <= capacity, last >= 0]
    forward = [*valid, now >= last]
    result = step(capacity, refill, interval, now, tokens, last)
    initial = step(capacity, refill, interval, now, capacity, now)

    proofs.prove(
        "token bucket: first request starts full and consumes one token",
        config,
        And(
            initial.allowed,
            initial.tokens == capacity - 1,
            initial.last_refill_ms == now,
            initial.retry_after_ms == 0,
        ),
    )
    proofs.prove(
        "token bucket: token bounds are inductive, even with clock rollback",
        valid,
        And(result.tokens >= 0, result.tokens <= capacity, result.last_refill_ms >= last),
    )
    proofs.prove(
        "token bucket: allowance requires an existing token or a completed refill",
        valid,
        result.allowed == And(capacity > 0, (tokens > 0) | (now - last >= interval)),
    )
    proofs.prove(
        "token bucket: refill schedule advances only by whole intervals",
        forward,
        And(
            result.last_refill_ms == last + result.refill_count * interval,
            result.last_refill_ms <= now,
            now - result.last_refill_ms < interval,
        ),
    )
    start, completed = Ints("tb_start tb_completed")
    proofs.prove(
        "token bucket: cumulative refill count stays anchored to the first request",
        [*forward, start >= 0, completed >= 0, last == start + completed * interval],
        completed + result.refill_count == (now - start) / interval,
    )
    proofs.prove(
        "token bucket: rejection preserves the empty bucket and refill schedule",
        valid,
        Implies(
            ~result.allowed,
            And(result.tokens == 0, tokens == 0, result.last_refill_ms == last),
        ),
    )
    proofs.prove(
        "token bucket: retry is zero on acceptance, otherwise within one interval",
        forward,
        And(
            Implies(result.allowed, result.retry_after_ms == 0),
            Implies(
                ~result.allowed,
                And(result.retry_after_ms > 0, result.retry_after_ms <= interval),
            ),
        ),
    )

    wait = Ints("tb_wait")[0]
    early = step(
        capacity, refill, interval, now + wait, result.tokens, result.last_refill_ms
    )
    retry = step(
        capacity,
        refill,
        interval,
        now + result.retry_after_ms,
        result.tokens,
        result.last_refill_ms,
    )
    proofs.prove(
        "token bucket: retry is the earliest successful retry without competing requests",
        [*valid, ~result.allowed, wait >= 0, wait < result.retry_after_ms],
        And(~early.allowed, retry.allowed),
    )

    spent, issued = Ints("tb_spent tb_issued")
    proofs.prove(
        "token bucket: cumulative token budget is inductive",
        [
            *valid,
            spent >= 0,
            issued >= 0,
            tokens + spent <= capacity + issued,
        ],
        result.tokens + spent + If(result.allowed, 1, 0)
        <= capacity + issued + result.refill_count * refill,
    )
    proofs.prove(
        "token bucket: a saturated refill discards excess tokens",
        [*forward, result.refill_count > 0, tokens + result.refill_count * refill >= capacity],
        And(result.allowed, result.tokens == capacity - 1),
    )

    proofs.witness(
        "token bucket: clock rollback can make retry longer than one interval",
        [*valid, now < last, ~result.allowed, result.retry_after_ms > interval],
        {
            "capacity": capacity,
            "refill": refill,
            "interval": interval,
            "tokens": tokens,
            "last": last,
            "now": now,
            "retry": result.retry_after_ms,
        },
    )
