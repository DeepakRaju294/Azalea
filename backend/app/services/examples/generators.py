"""Tier-2 fixture generators (EXAMPLE_SYSTEM_SPEC §7.1 `generated_deterministic`).

A hand-verified fixture hardcodes only the *input*; the simulator + prose are the
shared template. A generator reuses that template and varies the scenario — so one
binary-search generator yields unlimited verified worked examples (found-late, absent,
practice variants) without hand-authoring each. Every generated fixture still runs
through the real pipeline + validators (verified, never asserted).

Seeded by the topic so similar topics get *stable but varied* scenarios. Flag-gated
(`AZALEA_FIXTURE_GENERATORS`, default OFF) so the hand-verified path is unchanged
until enabled. Adding another algorithm = one generator function + a registry entry.
"""

from __future__ import annotations

import hashlib
import os
import random
from functools import lru_cache
from typing import Callable, Optional

from app.core.example_fixtures import _BINARY_SEARCH_CODE, CanonicalFixture, fixtures_for


def fixture_generators_enabled() -> bool:
    return os.getenv("AZALEA_FIXTURE_GENERATORS", "").strip().lower() in {"1", "true", "all", "on"}


def _rng(*parts: object) -> random.Random:
    return random.Random("|".join(str(p) for p in parts))


def _sorted_array(rng: random.Random, length: int) -> list[int]:
    start = rng.choice([1, 2, 3, 5, 7])
    step = rng.choice([1, 2, 3])
    return [start + i * step for i in range(length)]


def _bs_index(arr: list[int], target: int) -> int:
    return arr.index(target) if target in arr else -1


# The code-lens line explanations are the SAME canonical implementation — reuse the
# hand-verified fixture's so generated code fixtures inherit the verified walkthrough.
def _bs_code_lines() -> tuple[tuple[str, str], ...]:
    for fx in fixtures_for("binary_search"):
        if fx.example_type == "code_execution_trace" and fx.line_explanations:
            return fx.line_explanations
    return ()


def _bs_concept(fid: str, arr: list[int], target: int, tags: tuple[str, ...], min_steps: int) -> CanonicalFixture:
    return CanonicalFixture(
        fixture_id=fid, application="binary_search", example_type="sequence_state_trace",
        pattern="range_halving", base_structure={"array": list(arr)}, input={"target": target},
        expected_output=_bs_index(arr, target), source="generated_deterministic",
        sizing={"min_steps": min_steps}, tags=tags,
        learner_goal=f"Trace binary search finding {target} in a {len(arr)}-element sorted array.",
    )


def _bs_code(fid: str, arr: list[int], target: int, tags: tuple[str, ...], min_steps: int) -> CanonicalFixture:
    return CanonicalFixture(
        fixture_id=fid, application="binary_search", example_type="code_execution_trace",
        pattern="loop_execution", input={"array": list(arr), "target": target},
        expected_output=_bs_index(arr, target), code=_BINARY_SEARCH_CODE, entry_function="binary_search",
        line_explanations=_bs_code_lines(), source="generated_deterministic",
        sizing={"min_steps": min_steps}, tags=tags,
        learner_goal="Step through the binary-search loop on a fresh sorted array.",
    )


def generate_binary_search(seed: object) -> list[CanonicalFixture]:
    """Varied, verified binary-search scenarios from the template (concept + code
    worked examples, an absent edge case, and an isomorphic practice variant)."""
    rng = _rng("binary_search", seed)
    length = rng.choice([13, 15, 17, 19])
    arr = _sorted_array(rng, length)
    found = arr[0]                       # found-late → guarantees many probes
    absent = arr[-1] + rng.choice([3, 5, 7])
    parr = _sorted_array(_rng("bs_practice", seed), rng.choice([13, 15, 17]))
    ptarget = parr[0]                    # also found-late so the practice has >= 3 probes
    s = str(seed)
    return [
        _bs_concept(f"binary_search_gen_concept_{s}", arr, found, ("medium_nontrivial",), 4),
        _bs_code(f"binary_search_gen_code_{s}", arr, found, ("medium_nontrivial",), 4),
        _bs_concept(f"binary_search_gen_absent_{s}", arr, absent, ("edge_case",), 4),
        _bs_concept(f"binary_search_gen_practice_{s}", parr, ptarget, ("isomorphic_variant",), 3),
    ]


# application -> generator(seed) -> [CanonicalFixture]. Add an algorithm here.
GENERATORS: dict[str, Callable[[object], list[CanonicalFixture]]] = {
    "binary_search": generate_binary_search,
}


@lru_cache(maxsize=512)
def _validated(application: str, seed_key: str) -> tuple[CanonicalFixture, ...]:
    """Generate + KEEP ONLY fixtures that validate through the real pipeline (verified,
    never asserted). Memoised per (application, seed)."""
    gen = GENERATORS.get(application)
    if gen is None:
        return ()
    from app.services.examples.handoff import fixture_to_canonical_example
    from app.services.visual_v2.pipeline import run_for_registered

    ok: list[CanonicalFixture] = []
    for fx in gen(seed_key):
        try:
            result = run_for_registered(fixture_to_canonical_example(fx), model_id=f"gen_{fx.fixture_id}")
            if result.get("status") == "validated" and len(result.get("frames") or []) >= int(fx.sizing.get("min_steps", 0)):
                ok.append(fx)
        except Exception:  # noqa: BLE001 — a bad scenario is simply dropped
            continue
    return tuple(ok)


def generated_fixtures(application: str, seed: object) -> list[CanonicalFixture]:
    """Validated generated fixtures for an application + seed, or [] when the flag is
    off or no generator exists. Safe to call unconditionally."""
    if not fixture_generators_enabled() or application not in GENERATORS:
        return []
    seed_key = hashlib.md5(str(seed).encode()).hexdigest()[:12]
    return list(_validated(application, seed_key))
