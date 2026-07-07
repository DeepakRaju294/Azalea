"""Shadow-log aggregator — turns the Q23/Q24 shadow reports into the per-family violation rate that authorizes
`on_enforced`.

A family earns `on_enforced` when its shadow violation rate is ~0 (Q23 §14 / Q24 §5): either the content is
already clean, or it was made clean after the flagged claims were fixed. This module reads the shadow reports
(returned by `free_text/shadow.py` and `trace_teaching/shadow.py`, one JSON object per line in their JSONL sinks)
and produces a per-domain breakdown + an enforce-ready verdict, so the flip is a measured decision, not a guess.

A "violation" is a span/field the validator would NOT ship as-is:
- free-text: a claim whose disposition is delete / withhold_field / withhold_card.
- trace-teaching: a field whose decision is withhold / retry.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

FREE_TEXT = "free_text"
TRACE_TEACHING = "trace_teaching"


@dataclass
class DomainShadow:
    domain: str
    units: int = 0                              # spans (free-text) + fields (trace) evaluated
    violations: int = 0                         # units that would not ship as-is
    by_reason: Dict[str, int] = field(default_factory=dict)   # failure kind → count
    free_text_units: int = 0
    trace_units: int = 0

    @property
    def violation_rate(self) -> float:
        return (self.violations / self.units) if self.units else 0.0

    def _bump(self, reason: str, n: int = 1) -> None:
        if n:
            self.by_reason[reason] = self.by_reason.get(reason, 0) + n


@dataclass
class ShadowReport:
    domains: Dict[str, DomainShadow] = field(default_factory=dict)

    def _domain(self, name: str) -> DomainShadow:
        return self.domains.setdefault(name, DomainShadow(domain=name))

    def enforce_ready(self, domain: str, *, threshold: float = 0.0) -> bool:
        """A domain is enforce-ready when it has been measured and its violation rate ≤ threshold."""
        d = self.domains.get(domain)
        return d is not None and d.units > 0 and d.violation_rate <= threshold

    def render(self) -> str:
        lines = ["domain            units  violations  rate    top reasons"]
        for name in sorted(self.domains):
            d = self.domains[name]
            top = ", ".join(f"{k}={v}" for k, v in sorted(d.by_reason.items(), key=lambda kv: -kv[1])[:3])
            lines.append(f"{name:<16}  {d.units:>5}  {d.violations:>10}  {d.violation_rate:>5.1%}   {top}")
        return "\n".join(lines)


_FREE_TEXT_VIOLATION_ACTIONS = {"delete", "withhold_field", "withhold_card"}
_TRACE_VIOLATION_DECISIONS = {"withhold", "retry"}


def add_free_text_report(report: ShadowReport, record: dict) -> None:
    domain = str(record.get("domain") or "unknown")
    d = report._domain(domain)
    for fr in record.get("fields", []) or []:
        for claim in fr.get("claims", []) or []:
            d.units += 1
            d.free_text_units += 1
            action = str(claim.get("action") or "")
            if action in _FREE_TEXT_VIOLATION_ACTIONS:
                d.violations += 1
                # attribute to the most specific failure reason available
                stage = claim.get("transformation_failure_stage")
                l4 = claim.get("l4")
                if stage:
                    d._bump(f"l2:{stage}")
                elif claim.get("l2_verdict") == "refuted":
                    d._bump("l2:refuted")
                elif l4 in ("unsupported", "unavailable", "refuted"):
                    d._bump(f"l4:{l4}")
                elif claim.get("l1") == "fail":
                    d._bump("l1:out_of_scope")
                elif claim.get("l3") == "fail":
                    d._bump("l3:sibling")
                else:
                    d._bump(f"action:{action}")


def add_trace_teaching_report(report: ShadowReport, record: dict) -> None:
    domain = str(record.get("domain") or "unknown")
    d = report._domain(domain)
    for fr in record.get("fields", []) or []:
        d.units += 1
        d.trace_units += 1
        decision = str(fr.get("decision") or "")
        if decision in _TRACE_VIOLATION_DECISIONS:
            d.violations += 1
            failures = fr.get("failures") or []
            if failures:
                for chk in failures:
                    d._bump(f"trace:{chk}")
            else:
                d._bump(f"trace:{decision}")


def aggregate(reports: Iterable[Tuple[str, dict]]) -> ShadowReport:
    """Aggregate (kind, report) pairs where kind ∈ {free_text, trace_teaching}."""
    out = ShadowReport()
    for kind, record in reports:
        if kind == FREE_TEXT:
            add_free_text_report(out, record)
        elif kind == TRACE_TEACHING:
            add_trace_teaching_report(out, record)
    return out


def load_reports(path: str) -> List[dict]:
    """Read a JSONL shadow sink into a list of report dicts (skips blank/broken lines)."""
    out: List[dict] = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        return []
    return out


def aggregate_files(*, free_text_path: Optional[str] = None,
                    trace_teaching_path: Optional[str] = None) -> ShadowReport:
    """Aggregate the two production JSONL sinks into one report."""
    pairs: List[Tuple[str, dict]] = []
    if free_text_path:
        pairs.extend((FREE_TEXT, r) for r in load_reports(free_text_path))
    if trace_teaching_path:
        pairs.extend((TRACE_TEACHING, r) for r in load_reports(trace_teaching_path))
    return aggregate(pairs)


def _main(argv: Optional[List[str]] = None) -> int:
    """CLI: aggregate the production shadow sinks and print the per-family violation-rate table.

    Usage: python -m app.services.shadow_metrics [--free-text PATH] [--trace PATH] [--threshold 0.0] [--enforce DOMAIN]
    """
    import argparse
    import os

    p = argparse.ArgumentParser(description="Summarize Q23/Q24 shadow logs into a violation-rate report.")
    p.add_argument("--free-text", default=os.path.join("logs", "free_text_shadow.jsonl"))
    p.add_argument("--trace", default=os.path.join("logs", "trace_teaching_shadow.jsonl"))
    p.add_argument("--threshold", type=float, default=0.0)
    p.add_argument("--enforce", default=None, help="print an enforce-ready verdict for this domain")
    args = p.parse_args(argv)

    report = aggregate_files(free_text_path=args.free_text, trace_teaching_path=args.trace)
    if not report.domains:
        print("no shadow data found (run generation with a family enrolled in shadow_validate first)")
        return 0
    print(report.render())
    if args.enforce:
        ready = report.enforce_ready(args.enforce, threshold=args.threshold)
        print(f"\nenforce-ready[{args.enforce}] @ threshold {args.threshold:.1%}: {ready}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
