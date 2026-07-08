"""Regenerate ADAPTER_CATALOG.md — the full running list of every adapter, grouped by type.

The manifest (app/services/examples/trace_adapters/manifest.py::MANIFEST) is the source of truth; this dumps it to
the repo-root ADAPTER_CATALOG.md so the list never drifts. Run after adding adapters:

    OPENAI_API_KEY=dummy python gen_adapter_catalog.py     # from backend/
"""
from __future__ import annotations

import os
from collections import defaultdict

from app.services.examples.trace_adapters import manifest as M

_FAMILY_A = ["T1", "T2", "T3", "T4", "T5", "T9a", "T9b", "T11", "T12"]
_FAMILY_B = ["T6", "T7", "T8a", "T8b", "T10", "T13", "T14", "T15", "T16"]
_ENGINE = {"T6": "formula_engine", "T7": "rewrite_engine", "T8a": "construct_engine",
           "T8b": "derivation_engine", "T10": "stateful_engine", "T13": "induction_engine",
           "T14": "table_engine", "T15": "rowreduce_engine", "T16": "numerical_engine"}


def render() -> str:
    by_type: dict[str, list] = defaultdict(list)
    for slug, entry in M.MANIFEST.items():
        by_type[entry.get("type")].append((slug, entry.get("family", ""), bool(entry.get("coding", False))))

    grammar = M.ADAPTER_TYPES
    gaps = M.manifest_gaps()
    lines = [
        "# Adapter Catalog — the full running list", "",
        "> **Auto-generated from `app/services/examples/trace_adapters/manifest.py::MANIFEST` (the source of",
        "> truth)** by `backend/gen_adapter_catalog.py`. Regenerate after adding adapters. Companion to",
        "> `ADAPTER_TAXONOMY_SPEC.md` (which defines the *types*); this lists every *adapter*, grouped by type.",
        "> Each row is `slug · family · trace|coding` (`coding` = also has a deterministic coding walkthrough;",
        "> `trace` = ships its walkthrough from the verified trace).", "",
        f"**{len(M.MANIFEST)} adapters · {len(grammar)} types · manifest_gaps() = "
        + (("GAPS: " + ", ".join(gaps)) if gaps else "CLEAN") + "**", "",
    ]

    def section(title: str, types: list[str]) -> None:
        lines.extend([f"## {title}", ""])
        for t in types:
            rows = sorted(by_type.get(t, []))
            backing = f" · engine `{_ENGINE[t]}`" if t in _ENGINE else " · hand-coded"
            lines.extend([f"### {t} — `{grammar.get(t)}` ({len(rows)}){backing}", ""])
            lines.extend(f"- `{slug}` · {fam} · {'coding' if coding else 'trace'}" for slug, fam, coding in rows)
            lines.append("")

    section("Family A — algorithmic execution traces (hand-coded)", _FAMILY_A)
    section("Family B — declarative generators (one-file data specs on live engines)", _FAMILY_B)
    return "\n".join(lines) + "\n"


def main() -> None:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(repo_root, "ADAPTER_CATALOG.md")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(render())
    print(f"wrote {out} ({len(M.MANIFEST)} adapters)")


if __name__ == "__main__":
    main()
