"""Summarize FormulaSpec production-volume and substrate-shadow telemetry."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.examples.runtime_binding.shadow import summarize_shadow_events


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    print(json.dumps(summarize_shadow_events(args.path), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
