"""Run the isolated Milestone A shadow evidence cohort.

Historical mode replays persisted production topic identities through the normal router without changing the
database. Controlled mode selects structurally diverse eligible FormulaSpecs through that same router.
Neither mode calls an LLM or writes learner content.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.examples.runtime_binding.compiler import compile_formula_spec
from app.services.examples.runtime_binding.shadow import summarize_shadow_events
from app.services.examples.trace_pipeline import route_adapter, select_instance
from app.services.examples.trace_adapters.families.formula_specs import ALL_SPECS


def _run_historical() -> int:
    from app.db.database import SessionLocal
    import app.db.base  # noqa: F401 - registers models before querying
    from app.models.topic import Topic

    count = 0
    database = SessionLocal()
    try:
        for topic in database.query(Topic).order_by(Topic.created_at, Topic.id).all():
            adapter = route_adapter({
                "id": str(topic.id),
                "title": topic.title,
                "topic_type": topic.course_type or "",
            })
            if adapter is None or getattr(adapter, "_formula_spec", None) is None:
                continue
            seed = int(hashlib.md5(str(topic.id).encode()).hexdigest(), 16) % 1_000_000
            if select_instance(adapter, seed=seed) is not None:
                count += 1
    finally:
        database.close()
    return count


def _controlled_adapters(limit: int = 10):
    selected = []
    seen = set()
    for spec in ALL_SPECS:
        if not spec.register or compile_formula_spec(spec).status != "compiled":
            continue
        adapter = route_adapter({
            "id": f"milestone-a-{spec.slug}",
            "title": spec.title,
            "topic_type": "problem_solving_application",
        })
        routed = getattr(getattr(adapter, "_formula_spec", None), "slug", None)
        if routed != spec.slug or routed in seen:
            continue
        selected.append(adapter)
        seen.add(routed)
        if len(selected) >= limit:
            break
    if len(selected) < limit:
        raise RuntimeError(f"only {len(selected)} eligible FormulaSpecs route by their reviewed title")
    return selected


def _run_controlled(per_slug: int = 10) -> int:
    count = 0
    for adapter in _controlled_adapters():
        for seed in range(per_slug):
            if select_instance(adapter, seed=seed) is None:
                raise RuntimeError(f"controlled trace selection failed: {adapter.slug}, seed {seed}")
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("logs/t6_substrate_shadow.jsonl"),
    )
    parser.add_argument("--keep-existing", action="store_true")
    args = parser.parse_args()
    if args.output.exists() and not args.keep_existing:
        args.output.unlink()
    os.environ["AZALEA_T6_SUBSTRATE_SHADOW"] = "observe"
    os.environ["AZALEA_T6_SUBSTRATE_SHADOW_SAMPLE_RATE"] = "1"
    os.environ["AZALEA_T6_SUBSTRATE_SHADOW_PATH"] = str(args.output)

    os.environ["AZALEA_T6_SUBSTRATE_SHADOW_SOURCE"] = "historical_topic_replay"
    historical = _run_historical()
    os.environ["AZALEA_T6_SUBSTRATE_SHADOW_SOURCE"] = "controlled_router_validation"
    controlled = _run_controlled()
    summary = summarize_shadow_events(args.output)
    print({"historical": historical, "controlled": controlled, "summary": summary})


if __name__ == "__main__":
    main()
