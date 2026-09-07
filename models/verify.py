import argparse
import hashlib
from pathlib import Path

from z3 import get_version_string

import sliding_window_log
import token_bucket
from proof import Proofs


LUA_SOURCES = {
    "projects/token-bucket/src/token-bucket.lua": "c10172a80d54abb942a0557126e49982d3d5eea05cf818ed62f0febd5fd4767e",
    "projects/sliding-window-log/src/sliding-window-log.lua": "e83d519be8daa57aef070cca6c8226a03fa0fe2be1e7b49560c08a9e71b5e8a7",
}


def verify_sources() -> None:
    root = Path(__file__).resolve().parent.parent
    for relative_path, expected in LUA_SOURCES.items():
        source = (root / relative_path).read_text(encoding="utf-8")
        actual = hashlib.sha256(source.encode("utf-8")).hexdigest()
        if actual != expected:
            raise RuntimeError(
                f"{relative_path} changed: review its model and proof obligations before "
                f"updating its source digest to {actual}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Check the rate limiter Z3 models.")
    parser.add_argument("--depth", type=int, default=8, help="sliding window trace bound (default: 8)")
    parser.add_argument("--timeout-ms", type=int, default=10_000, help="timeout per solver query")
    args = parser.parse_args()
    if args.depth < 2 or args.timeout_ms < 1:
        parser.error("depth must be at least 2 and timeout-ms must be positive")
    verify_sources()
    print(f"Z3 {get_version_string()}; exact integer models; sliding trace depth {args.depth}", flush=True)
    proofs = Proofs(args.timeout_ms)
    token_bucket.verify(proofs)
    sliding_window_log.verify(proofs, args.depth)
    print(f"\n{proofs.proven} obligations proved; {proofs.witnesses} expected witnesses found.")


if __name__ == "__main__":
    main()
