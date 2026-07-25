"""Emit the deterministic Milestone A T6 inventory as JSON."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.examples.runtime_binding.inventory import inventory_live_catalog


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional JSON output path; stdout when omitted.")
    args = parser.parse_args()
    payload = inventory_live_catalog().to_json(indent=2) + "\n"
    if args.output is None:
        print(payload, end="")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload, encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
