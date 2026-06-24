"""Aggregate the gen_foundation shadow logs into per-family headline rates (Group 2).

Reads the two JSONL sinks produced once shadow collection is enabled and rolls them into the numbers
that decide the deferred work (Group 3): which families execute reliably, where the model's answers
disagree with execution, which families violate their invariants, and which cards keep failing.

Enable collection (set these in the environment, e.g. backend/.env):

    AZALEA_GEN_FOUNDATION_SHADOW=1            # run the single-pass pipeline in shadow
    AZALEA_GEN_FOUNDATION_EXECUTE=1           # let the executor actually run code (oracle)
    AZALEA_GEN_FOUNDATION_TELEMETRY_PATH=.../shadow_telemetry.jsonl
    AZALEA_CARD_FAILURE_LOG_PATH=.../card_failures.jsonl

Then, after some generation traffic:

    python scripts/aggregate_shadow_telemetry.py shadow_telemetry.jsonl --failures card_failures.jsonl

Pure `aggregate()` so it is unit-testable; the CLI just loads files and prints.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from typing import Any, Optional


def _rate(num: int, den: int) -> Optional[float]:
    return round(num / den, 3) if den else None


def load_jsonl(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # tolerate a partially-written trailing line
    return rows


def aggregate(telemetry: list[dict[str, Any]],
              failures: Optional[list[dict[str, Any]]] = None) -> dict[str, Any]:
    """Roll telemetry + card-failure rows into per-family rates and overall headlines (pure)."""
    families: dict[str, dict[str, Any]] = {}

    def fam_bucket(name: str) -> dict[str, Any]:
        return families.setdefault(name, {
            "n": 0, "blocked": 0, "first_pass_valid": 0,
            "executed": 0, "agree": 0, "agree_checkable": 0, "prop_violations": 0,
            "state_sum": 0.0, "state_n": 0, "skip_reasons": Counter(),
        })

    for r in telemetry:
        b = fam_bucket(str(r.get("topic_family") or "(unknown)"))
        b["n"] += 1
        b["blocked"] += int(bool(r.get("blocked")))
        b["first_pass_valid"] += int(bool(r.get("first_pass_valid")))
        if r.get("executed"):
            b["executed"] += 1
            ag = r.get("final_answer_agreement")
            if ag is not None:
                b["agree_checkable"] += 1
                b["agree"] += int(bool(ag))
            if r.get("property_violations"):
                b["prop_violations"] += 1
            sa = r.get("state_agreement")
            if isinstance(sa, (int, float)):
                b["state_sum"] += sa
                b["state_n"] += 1
        else:
            b["skip_reasons"][str(r.get("execution_skip_reason") or "unknown")] += 1

    per_family: dict[str, Any] = {}
    for name, b in sorted(families.items()):
        per_family[name] = {
            "n": b["n"],
            "executed_rate": _rate(b["executed"], b["n"]),
            "blocked_rate": _rate(b["blocked"], b["n"]),
            "first_pass_valid_rate": _rate(b["first_pass_valid"], b["n"]),
            "answer_agreement_rate": _rate(b["agree"], b["agree_checkable"]),
            "property_violation_rate": _rate(b["prop_violations"], b["executed"]),
            "avg_state_agreement": (round(b["state_sum"] / b["state_n"], 3) if b["state_n"] else None),
            "top_skip_reasons": dict(b["skip_reasons"].most_common(4)),
        }

    # card-failure rollup
    fail_summary: dict[str, Any] = {}
    if failures:
        by_card: dict[str, Counter] = defaultdict(Counter)
        by_family_card: dict[tuple[str, str], Counter] = defaultdict(Counter)
        actions: Counter = Counter()
        for f in failures:
            card = str(f.get("card_key") or "?")
            fam = str(f.get("topic_family") or "(unknown)")
            by_card[card][str(f.get("reason") or "?")] += 1
            by_family_card[(fam, card)][str(f.get("action") or "?")] += 1
            actions[str(f.get("action") or "?")] += 1
        fail_summary = {
            "total": len(failures),
            "by_action": dict(actions),
            "regeneration_recovery_rate": _rate(actions.get("regenerated", 0), len(failures)),
            "reasons_by_card": {c: dict(r) for c, r in by_card.items()},
            "actions_by_family_card": {f"{fam}/{card}": dict(a)
                                       for (fam, card), a in sorted(by_family_card.items())},
        }

    n = len(telemetry)
    executed = sum(1 for r in telemetry if r.get("executed"))
    return {
        "overall": {
            "runs": n,
            "executed_rate": _rate(executed, n),
            "blocked_rate": _rate(sum(1 for r in telemetry if r.get("blocked")), n),
            "families": len(per_family),
        },
        "per_family": per_family,
        "card_failures": fail_summary,
    }


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Aggregate gen_foundation shadow telemetry.")
    ap.add_argument("telemetry", help="path to shadow_telemetry.jsonl")
    ap.add_argument("--failures", help="path to card_failures.jsonl", default=None)
    args = ap.parse_args(argv)

    telemetry = load_jsonl(args.telemetry)
    failures = load_jsonl(args.failures) if args.failures else []
    if not telemetry:
        print("no telemetry rows found — has shadow collection been enabled and run?", file=sys.stderr)
        return 1
    print(json.dumps(aggregate(telemetry, failures), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
