from collections.abc import Mapping, Sequence

from z3 import BoolRef, ExprRef, Not, Solver, sat, unsat


class Proofs:
    def __init__(self, timeout_ms: int = 10_000):
        self.timeout_ms = timeout_ms
        self.proven = 0
        self.witnesses = 0

    def solver(self, assumptions: Sequence[BoolRef]) -> Solver:
        solver = Solver()
        solver.set(timeout=self.timeout_ms)
        solver.add(*assumptions)
        return solver

    def prove(
        self, name: str, assumptions: Sequence[BoolRef], property: BoolRef
    ) -> None:
        solver = self.solver(assumptions)
        feasible = solver.check()
        if feasible != sat:
            detail = solver.reason_unknown() if feasible != unsat else "inconsistent assumptions"
            raise RuntimeError(f"{name}: cannot establish feasibility: {detail}")
        solver.add(Not(property))
        result = solver.check()
        if result == sat:
            raise RuntimeError(f"{name}: counterexample\n{solver.model()}")
        if result != unsat:
            raise RuntimeError(f"{name}: unknown: {solver.reason_unknown()}")
        self.proven += 1
        print(f"PROVED {name}", flush=True)

    def witness(
        self,
        name: str,
        constraints: Sequence[BoolRef],
        values: Mapping[str, ExprRef],
    ) -> None:
        solver = self.solver(constraints)
        result = solver.check()
        if result != sat:
            detail = solver.reason_unknown() if result != unsat else "no witness exists"
            raise RuntimeError(f"{name}: {detail}")
        model = solver.model()
        assignments = ", ".join(
            f"{label}={model.eval(value, model_completion=True)}"
            for label, value in values.items()
        )
        self.witnesses += 1
        print(f"WITNESS {name}: {assignments}", flush=True)
