"""A/B harness for the worked-example trace pipeline (WORKED_EXAMPLE_REASONING_SPEC.md §17).

Runs each supported deterministic adapter end-to-end and reports the metrics that decide promotion:
whether it shipped (Stage-4/4b pass), card count (conciseness), and where it failed if it didn't. With a
real OPENAI_API_KEY it exercises the live prose-only formatter; offline it reports the deterministic
stages (Stage 0/1/2 + structural gate) and that formatting deferred.

    python -m scripts.trace_pipeline_ab            # all five adapters
    python -m scripts.trace_pipeline_ab kruskal    # one
"""
from __future__ import annotations

import sys
import time

from app.services.examples import trace_pipeline as tp
from app.services.examples.trace_adapters import ADAPTERS
from app.services.examples.trace_contract import structural_invariants, validate_fidelity, validate_prose


def run(slug: str) -> dict:
    adapter = ADAPTERS[slug]
    t0 = time.time()
    trace = tp.select_instance(adapter, seed=int(t0) % 100000)
    if trace is None:
        return {"slug": slug, "stage": "select", "ok": False}
    struct = structural_invariants(trace, adapter)
    if struct:
        return {"slug": slug, "stage": "structural", "ok": False, "errors": struct[:2]}
    raw = tp.default_format_fn(tp.build_format_payload(trace))     # live formatter; None offline
    if raw is None:
        return {"slug": slug, "stage": "format", "ok": None, "steps": len(trace.steps),
                "note": "no formatter (offline) — deterministic stages passed"}
    cards = tp._normalize_and_attach(raw, trace)
    if cards is None:
        return {"slug": slug, "stage": "normalize", "ok": False, "steps": len(trace.steps)}
    fid = validate_fidelity(cards, trace, adapter)
    prose = validate_prose(cards, trace, adapter)
    return {"slug": slug, "stage": "done", "ok": fid.ok and not prose, "cards": len(cards),
            "steps": len(trace.steps), "secs": round(time.time() - t0, 2),
            "fidelity": fid.code, "prose_violations": len(prose)}


def main() -> None:
    slugs = sys.argv[1:] or list(ADAPTERS)
    print(f"{'adapter':14} {'ok':>5} {'cards':>6} {'stage':>10}  notes")
    for slug in slugs:
        r = run(slug)
        print(f"{slug:14} {str(r.get('ok')):>5} {str(r.get('cards', '-')):>6} {r['stage']:>10}  "
              f"{r.get('note') or r.get('errors') or r.get('fidelity') or ''}")


if __name__ == "__main__":
    main()
