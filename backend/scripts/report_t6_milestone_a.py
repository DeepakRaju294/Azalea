"""Generate the consolidated Milestone A report and strict go/no-go decision."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services.examples.runtime_binding.milestone_report import build_milestone_a_report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "backend/reports/t6_milestone_a_v1.json",
    )
    args = parser.parse_args()
    report = build_milestone_a_report(REPO_ROOT)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report.to_json(indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")
    print(f"Decision: {report.decision}")
    for gate in report.gates:
        print(f"{'PASS' if gate.passed else 'BLOCK'} {gate.gate}: {gate.evidence}")


if __name__ == "__main__":
    main()
