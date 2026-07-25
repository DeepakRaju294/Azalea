"""Emit the offline Milestone A compiler/equivalence report."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.examples.runtime_binding.convergence import build_live_offline_convergence_report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("reports/t6_convergence_offline_v1.json"))
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--candidates-per-seed", type=int, default=8)
    args = parser.parse_args()
    report = build_live_offline_convergence_report(
        seeds=tuple(range(args.seeds)),
        candidates_per_seed=args.candidates_per_seed,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report.to_json(indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
