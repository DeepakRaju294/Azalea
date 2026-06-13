"""Handoff to the visual system (EXAMPLE_SYSTEM_SPEC.md §4.5).

Pure mapping from a CanonicalFixture onto the visual system's CanonicalExample, plus
the lens-aware visual resolution. `apply_fixture_to_lesson` (the lesson-mutating
adapter, Step E) lands in Phase 3; these pure functions are needed already so a
fixture can be validated against the real V2 pipeline.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from app.core.example_applications import APPLICATION_PROFILES
from app.core.example_fixtures import CanonicalFixture
from app.core.example_ontology import EXAMPLE_TYPE_TO_DEFAULT_VISUAL

_log = logging.getLogger(__name__)

# Bump when the apply output improves (richer prose, supporting diagram, ...);
# cached lessons stamped with an older version are re-enriched on read.
APPLY_VERSION = 16

Visual = tuple[str, str]

_ACRONYMS = {"dfs": "DFS", "bfs": "BFS"}


def _app_title(application: str) -> str:
    return _ACRONYMS.get(application, application.replace("_", " ").title())

# The visual ontology's taxonomy mode vs the visual_v2 pipeline's profile-mode key.
_PIPELINE_MODE: dict[str, str] = {
    "code_execution_trace": "code_execution",
    "substitution": "formula_substitution",
}


def pipeline_mode(ontology_mode: str) -> str:
    """Translate an ontology mode name to the visual_v2 pipeline profile-mode key."""
    return _PIPELINE_MODE.get(ontology_mode, ontology_mode)


def resolve_visual(fixture: CanonicalFixture) -> Visual:
    """The authoritative (base_type, mode) for this fixture's lens (spec §4.5 Step A):
    fixture override ▸ the profile's lens-appropriate visual ▸ the type default."""
    if fixture.visual_override is not None:
        return fixture.visual_override
    profile = APPLICATION_PROFILES.get(fixture.application)
    if profile is not None:
        if profile.code_example_type == fixture.example_type and profile.code_visual is not None:
            return profile.code_visual
        if profile.example_type == fixture.example_type:
            return profile.default_visual
    return EXAMPLE_TYPE_TO_DEFAULT_VISUAL[fixture.example_type]


def _algorithm_for(fixture: CanonicalFixture) -> Optional[str]:
    profile = APPLICATION_PROFILES.get(fixture.application)
    if profile is None:
        return None
    if profile.code_example_type == fixture.example_type:
        return profile.code_algorithm
    return profile.algorithm


def fixture_to_canonical_example(fixture: CanonicalFixture) -> dict[str, Any]:
    """Field map → visual_v2 CanonicalExample (spec §4.5 Step A). The mode is the
    pipeline mode; the ontology pair (resolve_visual) is what the VisualValidator checks."""
    base_type, ontology_mode = resolve_visual(fixture)
    example: dict[str, Any] = {
        "example_id": fixture.fixture_id,
        "domain_object": fixture.example_type,
        "base_type": base_type,
        "mode": pipeline_mode(ontology_mode),
        "algorithm": _algorithm_for(fixture),
        "input": dict(fixture.input),
        "base_structure": dict(fixture.base_structure),
        "expected_output": fixture.expected_output,
        "learner_goal": fixture.learner_goal,
    }
    if fixture.code is not None:
        example["code"] = fixture.code
        example["entry_function"] = fixture.entry_function
    # Projected (T2) node_link fixture (PROJECTOR_SYSTEM_SPEC §7): override the mode to
    # graph_projection and carry the contract so the pipeline takes the projector route.
    if fixture.graph_projection is not None:
        example["mode"] = "graph_projection"
        example["base_type"] = "node_link_diagram"
        example["graph_projection"] = dict(fixture.graph_projection)
    return example


# ---------------------------------------------------------------------------
# Step E — the one generic adapter (spec §4.5). Replaces the three ad-hoc adapters
# once it proves out (Phase 7). Flag-gated, failure-safe. No LLM yet — the step
# cards carry deterministic placeholder prose; Phase 4 swaps in validated ProseSlots.
# ---------------------------------------------------------------------------


def _milestone_frame_indices(result: dict[str, Any], fixture: CanonicalFixture) -> list[int]:
    """Which frames become cards. Code lens: each pre-loop setup line, then the LAST
    frame of every loop iteration — the branch line that acted (low/high update or
    return), so the highlight sits on the line in use, not the `while`. Concept
    simulators are already one-frame-per-step."""
    frames = result.get("frames") or []
    if fixture.example_type == "code_execution_trace" and fixture.code:
        from app.services.visual_v2.code_lesson_integration import (
            _loop_line_numbers,
            _milestone_frame_indices as _code_milestones,
        )
        loop_lines = _loop_line_numbers(fixture.code)
        # The branch-frame scheme assumes ONE driving loop (binary search's while).
        # Nested loops (BFS's while+for) and recursion read better as accumulator
        # milestones — one card per value the output gains (the fallback below).
        if len(loop_lines) == 1:
            def _hl(i: int) -> Any:
                lines = (frames[i].get("state_after") or {}).get("highlight_lines") or []
                return lines[0] if lines else None

            arrivals = [i for i in range(len(frames)) if _hl(i) in loop_lines]
            if arrivals:
                # Pre-loop frames are folded into one synced "Set Up the Range" card
                # (_code_setup_card); milestones are the loop iterations only — one
                # card per probe (the branch frame), plus the final return.
                iterations = [arrivals[k + 1] - 1 for k in range(len(arrivals) - 1)]
                final = [len(frames) - 1] if len(frames) - 1 > arrivals[-1] else []
                milestones = sorted(set(iterations + final))
                if len(milestones) >= 2:
                    return milestones
        return _code_milestones(frames, loop_lines)
    return list(range(len(frames)))


def _frame_points_for_code(
    frames: list[dict[str, Any]], milestones: list[int], loop_lines: frozenset, points_per: list[list[str]]
) -> list[list[int]]:
    """Per-bullet frame indices for code-lens cards, so the highlight (and variables
    panel) advance with each bullet: while-arrival → mid line → compare line →
    branch/return line. Setup cards keep one frame for all bullets."""
    def _hl(i: int) -> Any:
        lines = (frames[i].get("state_after") or {}).get("highlight_lines") or []
        return lines[0] if lines else None

    arrivals = [i for i in range(len(frames)) if _hl(i) in loop_lines]
    first_arrival = arrivals[0] if arrivals else len(frames)
    out: list[list[int]] = []
    for fi, points in zip(milestones, points_per):
        n_points = max(1, len(points))
        if fi <= first_arrival:
            out.append([fi] * n_points)     # setup: one frame for the whole card
            continue
        priors = [a for a in arrivals if a < fi]
        w = priors[-1] if priors else fi    # this iteration's while-arrival
        seq = [min(w + k, fi) for k in range(n_points - 1)] + [fi]
        out.append(seq[:n_points])
    return out


def _code_setup_card(model: dict[str, Any], fixture: CanonicalFixture) -> Optional[dict[str, Any]]:
    """One synced 'Set Up the Range' card covering every pre-loop init line. Each
    bullet highlights ITS line and shows the resulting variable, via synthetic
    after-execution frames (highlight from line L + variables after line L ran) —
    fixing the off-by-one where 'low = 0' lit the `high` line. Appends the synthetic
    frames to the model; returns the card (or None if there are no pre-loop lines)."""
    frames = model.get("frames") or []
    if not frames:
        return None
    from app.services.visual_v2.code_lesson_integration import _loop_line_numbers
    loop_lines = _loop_line_numbers(fixture.code or "")

    def hl(i: int) -> Any:
        return ((frames[i].get("state") or {}).get("highlight_lines") or [None])[0]

    def vars_at(i: int) -> dict:
        # The compiled model stores variables as [{name, value}] (frontend contract).
        raw = (frames[i].get("state") or {}).get("variables")
        if isinstance(raw, list):
            return {str(d.get("name")): d.get("value") for d in raw if isinstance(d, dict)}
        return raw if isinstance(raw, dict) else {}

    n = len(frames)
    first_loop = next((i for i in range(n) if hl(i) in loop_lines), n)
    if first_loop <= 0:
        return None

    base = len(frames)
    bullets: list[str] = []
    per_point: list[int] = []
    # The function parameters are already bound at entry — seed prev_keys with them
    # so only genuinely NEW variables (low, high, ...) are detected per line.
    prev_keys: set[str] = {k for k in vars_at(0) if k != "arr"}
    for i in range(first_loop):
        line = hl(i)
        after = vars_at(i + 1) if i + 1 < n else vars_at(i)   # state AFTER this line ran
        new = [k for k in after if k not in prev_keys and k != "arr"]
        prev_keys = {k for k in after if k != "arr"}
        if not new:
            continue
        k = new[0]
        role = ("the left end of the search range" if k == "low"
                else "the right end — the index of the last element" if k == "high" else "initialised")
        bullets.append(f"Line {line}: {k} = {after[k]} — {role}.")
        # Synthetic frame: this line highlighted + the variables AFTER it ran.
        st = dict(frames[i].get("state") or {})
        src = (frames[i + 1].get("state") if i + 1 < n else frames[i].get("state")) or {}
        for vk in ("variables", "call_stack", "output"):
            if vk in src:
                st[vk] = src[vk]
        frames.append({"index": base + len(per_point), "state": st, "highlights": {},
                       "annotations": [], "selectable_elements": [], "transitions": []})
        per_point.append(base + len(per_point))

    if not bullets:
        return None
    v = vars_at(first_loop)
    bullets.append(
        f"Line {hl(first_loop)}: the loop begins, checking low ({v.get('low')}) <= high "
        f"({v.get('high')}) — the range now spans the whole array."
    )
    per_point.append(first_loop)
    model_id = model["id"]
    return {
        "id": f"v2-ex-{model_id}-setup-range",
        "blueprint_key": "worked_example",
        "card_type": "worked_example",
        "title": f"{_app_title(fixture.application)}: Set Up the Range",
        "points": bullets,
        "body": [],
        "main_concept": fixture.learner_goal or "Initialise the search range.",
        "visual_type": model["base_type"],
        "visual_v2_ref": {"visual_model_id": model_id, "frame_index": per_point[0],
                          "frame_index_per_point": per_point, "source": "v2_example_ontology"},
        "metadata": {"code_setup_range": True},
        "estimated_seconds": 30,
    }


def _build_step_cards(
    model: dict[str, Any], milestones: list[int], points_per: list[list[str]], fixture: CanonicalFixture,
    frame_points: list[list[int]] | None = None,
) -> list[dict[str, Any]]:
    model_id = model["id"]
    cards: list[dict[str, Any]] = []
    for n, fi in enumerate(milestones):
        points = points_per[n] if n < len(points_per) and points_per[n] else [f"Step {n + 1} of the worked example."]
        ref: dict[str, Any] = {"visual_model_id": model_id, "frame_index": fi, "source": "v2_example_ontology"}
        if frame_points is not None and n < len(frame_points):
            ref["frame_index_per_point"] = frame_points[n]
        cards.append({
            "id": f"v2-ex-{model_id}-{n + 1}",
            "blueprint_key": "worked_example",
            "card_type": "worked_example",
            "title": f"{_app_title(fixture.application)}: Step {n + 1}",
            "points": points,
            "body": [],
            "main_concept": fixture.learner_goal or f"Step {n + 1} of the worked example.",
            "visual_type": model["base_type"],
            "visual_v2_ref": ref,
            "estimated_seconds": 30,
        })
    return cards


def _setup_bullets(fixture: CanonicalFixture) -> list[str]:
    """The problem statement for a worked example's mandatory setup card."""
    if fixture.setup_bullets:
        return list(fixture.setup_bullets)
    base = fixture.base_structure
    if fixture.example_type == "code_execution_trace":
        if "array" in fixture.input and "target" in fixture.input:
            arr = list(fixture.input.get("array") or [])
            target = fixture.input.get("target")
            return [
                f"The problem: find the INDEX of the target value {target} in a sorted array of {len(arr)} values.",
                "We solve it with binary search: repeatedly halve the range [low, high] until the target is found.",
                "Watch the code run line by line — the variables panel tracks low, high, and mid as they change.",
            ]
        return [
            f"The problem: {fixture.learner_goal}" if fixture.learner_goal else "Run the program on a concrete input.",
            "Watch the code run line by line — the variables panel tracks the state as it changes.",
        ]
    if fixture.example_type == "node_link_trace":
        nodes = list(base.get("nodes") or [])
        edges = list(base.get("edges") or [])
        start = fixture.input.get("start")
        return [
            f"The structure: a graph with {len(nodes)} nodes ({', '.join(str(n) for n in nodes)}) joined by {len(edges)} edges.",
            f"We start the traversal from node {start}.",
            fixture.learner_goal,
        ]
    if fixture.example_type == "grid_table_trace":
        rows, cols = base.get("rows"), base.get("cols")
        return [
            f"The problem: count the distinct paths from the top-left to the bottom-right of a {rows} x {cols} grid.",
            "Moves allowed: only right or only down.",
            "Each cell will store how many paths reach it.",
        ]
    return [fixture.learner_goal] if fixture.learner_goal else []


def _ensure_setup_card(cards: list[dict[str, Any]], model: dict[str, Any], fixture: CanonicalFixture) -> None:
    """Every worked example opens with a mandatory setup card stating the problem
    (with the starting visual), so Step 1 is an actual solving action. Mutates
    `cards` in place."""
    if not cards:
        return
    if fixture.example_type == "sequence_state_trace":
        # The first slot already narrates the setup state (frame 0) — promote it.
        cards[0]["title"] = "Worked Example Setup"
        cards[0].setdefault("metadata", {})["worked_example_setup"] = True
        for n, card in enumerate(cards[1:], start=1):
            card["title"] = f"{_app_title(fixture.application)}: Step {n}"
        return
    setup = {
        "id": f"v2-ex-{model['id']}-setup",
        "blueprint_key": "worked_example",
        "card_type": "worked_example",
        "title": "Worked Example Setup",
        "points": [b for b in _setup_bullets(fixture) if b],
        "body": [],
        "main_concept": fixture.learner_goal or "The problem this worked example solves.",
        "visual_type": model["base_type"],
        "visual_v2_ref": {"visual_model_id": model["id"], "frame_index": 0, "source": "v2_example_ontology"},
        "metadata": {"worked_example_setup": True},
        "estimated_seconds": 25,
    }
    cards.insert(0, setup)


def _build_walkthrough_cards(fixture: CanonicalFixture) -> list[dict[str, Any]]:
    """One card per code line from the fixture's VERIFIED code + line_explanations —
    every line gets its own explanation, growing reveal, highlight on the new line
    (the spec §6 code_walkthrough slot, same card shape the frontend already renders)."""
    if not fixture.code or not fixture.line_explanations:
        return []
    lines = [ln for ln in fixture.code.splitlines() if ln.strip()]
    if len(lines) != len(fixture.line_explanations):
        _log.warning("examples: %s line_explanations (%d) != code lines (%d); skipping walkthrough",
                     fixture.fixture_id, len(fixture.line_explanations), len(lines))
        return []
    # The displayed cumulative code is sliced from the ORIGINAL code (which keeps
    # its blank-line separation between functions): show everything up to and
    # including the n-th non-blank line; the highlight is that line's real number.
    original_lines = (fixture.code or "").splitlines()
    nonblank_positions = [i for i, ln in enumerate(original_lines) if ln.strip()]  # 0-based

    total = len(lines)
    cards: list[dict[str, Any]] = []
    for n, (title, explanation) in enumerate(fixture.line_explanations, start=1):
        cut = nonblank_positions[n - 1]
        cumulative, highlight = "\n".join(original_lines[: cut + 1]), cut + 1
        cards.append({
            "id": f"v2-cw-{fixture.fixture_id}-{n}",
            "blueprint_key": "code_walkthrough",
            "card_type": "code_walkthrough",
            "title": f"Code Walkthrough: {title}",
            "points": [explanation],
            "body": [],
            "main_concept": explanation,
            "code_snippet": cumulative,
            "code_language": "python",
            "visual_type": "code_trace",
            "highlight_lines_per_step": [[highlight, highlight]],
            "continuation_group_id": f"v2-cw-{fixture.fixture_id}",
            "continuation_index": n,
            "continuation_total": total,
            "continuation_reason": "one_code_line_per_card",
            "continues_from_previous": n > 1,
            "estimated_seconds": 20,
        })
    return cards


def _swap_walkthrough_cards(lesson_json: dict[str, Any], fixture: CanonicalFixture) -> None:
    """Replace the lesson's code_walkthrough run with the fixture-driven one (the
    LLM's walkthrough code is unverified and often broken). No-op without
    line_explanations or for non-code lenses."""
    new_cards = _build_walkthrough_cards(fixture)
    if not new_cards:
        return
    cards = list(lesson_json.get("lesson_cards") or [])
    rebuilt: list[dict[str, Any]] = []
    inserted = False
    for card in cards:
        if str(card.get("blueprint_key") or card.get("card_type") or "").lower() == "code_walkthrough":
            if not inserted:
                rebuilt.extend(new_cards)
                inserted = True
            continue
        rebuilt.append(card)
    if not inserted:
        # No walkthrough slot in the legacy lesson — insert before the worked example.
        idx = next((j for j, c in enumerate(rebuilt)
                    if str(c.get("blueprint_key") or "").lower() == "worked_example"), len(rebuilt))
        rebuilt[idx:idx] = new_cards
    lesson_json["lesson_cards"] = rebuilt


def _fallback(reason: str, topic_id: str, application: Optional[str] = None) -> bool:
    from app.services.examples.metrics import GLOBAL as METRICS

    _log.info("examples: falling back to legacy for topic %s (%s)", topic_id, reason)
    METRICS.record_fallback(reason, application)
    return False


def _apply_edge_case(lesson_json: dict[str, Any], declared: Any, model_id: str, seed: Optional[object] = None) -> None:
    """One VERIFIED edge-case card (spec §5.2 role `edge_case`) — e.g. the target is
    absent and the bounds cross. Replaces the lesson's LLM edge_case cards for
    fixture-covered topics (one verified beats several unverified). Failure-safe."""
    try:
        from app.services.examples.declaration import pick_fixture
        from app.services.visual_v2.pipeline import run_for_registered

        fx = pick_fixture(declared, "edge_case", seed=seed)
        if fx is None or fx.example_type != "sequence_state_trace":
            return
        example = fixture_to_canonical_example(fx)
        result = run_for_registered(example, model_id=f"{model_id}_edge")
        if result.get("status") != "validated":
            return
        model = result["model"]
        frames = result.get("frames") or []
        mids = [f["state_after"].get("mid") for f in frames if f["state_after"].get("mid") is not None]
        target = fx.input.get("target")
        card = {
            "id": f"v2-edge-{model['id']}",
            "blueprint_key": "edge_case",
            "card_type": "edge_case",
            "title": "Edge Case: Target Not in the Array",
            "points": [
                f"What happens when we search the same kind of array for {target} — a value that is NOT there?",
                f"The probes halve the range exactly as before: mid {' -> '.join(str(m) for m in mids)}; every comparison narrows the range.",
                "After the final probe the bounds cross — low ends up GREATER than high, so the range is empty.",
                "An empty range is the proof of absence: binary search returns -1.",
            ],
            "body": [],
            "main_concept": fx.learner_goal,
            "visual_type": model["base_type"],
            "visual_v2_ref": {"visual_model_id": model["id"], "frame_index": len(model["frames"]) - 1,
                              "source": "v2_example_ontology"},
            "estimated_seconds": 30,
        }
        models = lesson_json.setdefault("visual_models", [])
        models[:] = [m for m in models if m.get("id") != model["id"]]
        models.append(model)

        cards = list(lesson_json.get("lesson_cards") or [])
        rebuilt, inserted = [], False
        for c in cards:
            if str(c.get("blueprint_key") or c.get("card_type") or "").lower() == "edge_case":
                if not inserted:
                    rebuilt.append(card)
                    inserted = True
                continue
            rebuilt.append(c)
        if not inserted:
            last_we = max((i for i, c in enumerate(rebuilt)
                           if str(c.get("blueprint_key") or "").lower() == "worked_example"), default=-1)
            rebuilt.insert(last_we + 1 if last_we >= 0 else len(rebuilt), card)
        lesson_json["lesson_cards"] = rebuilt
    except Exception as exc:  # noqa: BLE001 — the edge card is additive polish
        _log.warning("examples: edge-case apply failed: %s", exc)


def _apply_practice(lesson_json: dict[str, Any], declared: Any, model_id: str, seed: Optional[object] = None) -> None:
    """An isomorphic practice question (spec §7.2): same reasoning shape as the
    worked example, different values, with a deterministic answer. Inserted at the
    start of the practice run. Failure-safe."""
    try:
        from app.services.examples.declaration import pick_fixture

        fx = pick_fixture(declared, "practice", seed=seed)
        if fx is None or fx.example_type != "sequence_state_trace":
            return
        array = list(fx.base_structure.get("array") or [])
        target = fx.input.get("target")
        answer = fx.expected_output
        first_mid = (len(array) - 1) // 2
        choices = []
        for cand in (str(first_mid), str(answer), str(len(array) - 1), "-1"):
            if cand not in choices:
                choices.append(cand)
        q_text = (
            f"Try it yourself: run binary search on {array} to find {target}. "
            f"Which INDEX does it return?"
        )
        # Idempotent on re-apply: refresh the existing question/card in place.
        questions = lesson_json.setdefault("practice_questions", [])
        q_id = f"q-v2-{model_id}"
        existing_q = next((i for i, q in enumerate(questions) if q.get("id") == q_id), None)
        q_index = existing_q if existing_q is not None else len(questions)
        if existing_q is not None:
            questions.pop(existing_q)
        questions.insert(q_index, {
            "id": q_id,
            "question_type": "multiple_choice",
            "question_text": q_text,
            "correct_answer": str(answer),
            "expected_answer": str(answer),
            "explanation": (
                f"Trace it like the worked example: start with the full range and halve it each probe — "
                f"the target {target} sits at index {answer}."
            ),
            "choices": choices,
            "options": choices,
            "skill_target": "", "concept_tested": "", "related_section": "", "why_this_matters": "",
            "difficulty": "standard", "given": [], "starter_code": "", "language": "",
            "test_cases": [], "visual_feedback_plan": {}, "edge_cases_tested": [],
            "misconceptions_tested": [], "metadata": {}, "rubric": {},
        })

        cards = [c for c in (lesson_json.get("lesson_cards") or [])
                 if c.get("id") != f"v2-practice-{model_id}"]
        existing_practice = next((i for i, c in enumerate(cards)
                                  if str(c.get("blueprint_key") or "").lower() == "practice"), None)
        card_type = (cards[existing_practice].get("card_type") if existing_practice is not None else None) or "quick_practice"
        card = {
            "id": f"v2-practice-{model_id}",
            "blueprint_key": "practice",
            "card_type": card_type,
            "title": "Practice: Trace It Yourself",
            "points": [q_text],
            "body": [],
            "main_concept": fx.learner_goal,
            "practice_question_index": q_index,
            "estimated_seconds": 45,
        }
        insert_at = existing_practice if existing_practice is not None else len(cards)
        cards.insert(insert_at, card)
        lesson_json["lesson_cards"] = cards
    except Exception as exc:  # noqa: BLE001 — the practice card is additive polish
        _log.warning("examples: practice apply failed: %s", exc)


def validate_and_order_cards(lesson_json: dict[str, Any], topic: dict[str, Any]) -> None:
    """CardValidator (spec §5.3 #5), as a repairing gate at the END of enrichment:
    the final card set contains only the topic type's blueprint keys, in blueprint
    order (background → … → worked_example → edge_case → … → practice). Cards of
    the same key keep their relative order. Never empties a lesson. Failure-safe."""
    try:
        from app.core.course_blueprints import get_topic_blueprint, normalize_topic_type_key

        cards = lesson_json.get("lesson_cards")
        if not isinstance(cards, list) or not cards:
            return
        topic_type = normalize_topic_type_key(topic.get("topic_type"))
        blueprint = get_topic_blueprint(topic_type)
        sequence = list(blueprint.get("default_card_sequence") or [])
        allowed: set[str] = set(sequence)
        for key in ("optional_cards", "continuation_card_sequence", "continuation_optional_cards"):
            allowed |= set(blueprint.get(key) or [])
        if not allowed:
            return

        def _key(card: dict[str, Any]) -> str:
            return str(card.get("blueprint_key") or card.get("card_type") or "").lower()

        kept = [c for c in cards if _key(c) in allowed]
        if not kept:
            return  # never empty the lesson
        order = {key: i for i, key in enumerate(sequence)}
        fallback_rank = len(sequence)
        reordered = sorted(kept, key=lambda c: order.get(_key(c), fallback_rank))  # stable
        if reordered != cards:
            dropped = len(cards) - len(kept)
            _log.info(
                "examples: CardValidator repaired lesson (topic_type=%s, dropped=%d, reordered=%s)",
                topic_type, dropped, [_key(c) for c in reordered],
            )
            lesson_json["lesson_cards"] = reordered
    except Exception as exc:  # noqa: BLE001 — the gate must never break a lesson
        _log.warning("examples: CardValidator failed: %s", exc)


def ensure_worked_example_setup(lesson_json: dict[str, Any], topic: dict[str, Any]) -> None:
    """Deterministic guarantee: every worked example opens with a setup card (the
    problem being solved), REGARDLESS of which path produced the lesson — fixture,
    legacy bridge, or raw LLM. Reuses the proven generation-time pass; recognises
    existing setups (incl. ours) so it never duplicates."""
    try:
        cards = lesson_json.get("lesson_cards")
        if not isinstance(cards, list) or not cards:
            return
        from app.services.lean_lesson_generator import _ensure_generic_worked_example_setup_cards

        _ensure_generic_worked_example_setup_cards(cards)
    except Exception as exc:  # noqa: BLE001 — a missing setup must not break the lesson
        _log.warning("examples: ensure_worked_example_setup failed: %s", exc)


def _remove_stale_apply(lesson_json: dict[str, Any]) -> None:
    """Strip a previous example-ontology apply from a lesson whose topic no longer
    declares an example (e.g. a study-path intro that was wrongly given a worked
    example before the blueprint gate existed). Restores the blueprint card set."""
    metadata = lesson_json.get("metadata") or {}
    applied = metadata.get("visual_v2_example_ontology") if isinstance(metadata, dict) else None
    if not isinstance(applied, dict):
        return
    model_id = str(applied.get("model_id") or "")
    lesson_json["lesson_cards"] = [
        card for card in (lesson_json.get("lesson_cards") or [])
        if not (
            (card.get("visual_v2_ref") or {}).get("source") == "v2_example_ontology"
            or str(card.get("id") or "").startswith(("v2-cw-", "v2-practice-", "v2-edge-"))
        )
    ]
    lesson_json["visual_models"] = [
        m for m in (lesson_json.get("visual_models") or [])
        if m.get("id") not in (model_id, f"{model_id}_diagram", f"{model_id}_edge")
    ]
    metadata.pop("visual_v2_example_ontology", None)
    _log.info("examples: removed stale apply (model %s) from lesson", model_id)


def _attach_supporting_diagram(
    lesson_json: dict[str, Any],
    cards: list[dict[str, Any]],
    milestones: list[int],
    result: dict[str, Any],
    fixture: CanonicalFixture,
    model_id: str,
) -> None:
    """For a code-lens fixture whose application also has a CONCEPT simulator (e.g.
    binary_search code → the array/pointer view), attach the concept model as a
    supporting diagram and point each step card at the aligned frame (the spec's
    `supporting_visuals`). Setup cards → frame 0; k-th loop iteration → probe k;
    the final card → the last frame. Failure-safe: any problem just skips the diagram."""
    profile = APPLICATION_PROFILES.get(fixture.application)
    if fixture.example_type != "code_execution_trace":
        return
    # binary_search keeps its rich registered-simulator range diagram. EVERY other code
    # fixture infers the diagram (graph → node_link, array → indexed_sequence) from the
    # code's OWN trace (PROJECTOR §6.4 INV-DUAL-SLOT), the same builder the fallback uses.
    if not (profile is not None and profile.algorithm is not None and "array" in fixture.input):
        try:
            from app.services.examples.code_diagram import attach_diagram_to_cards, build_diagram_from_trace

            trace_steps = (result.get("trace") or {}).get("steps") or []
            diagram = build_diagram_from_trace(trace_steps, model_id=f"{model_id}_diagram")
            attach_diagram_to_cards(lesson_json, cards, result.get("frames") or [], diagram, source="v2_example_ontology")
        except Exception as exc:  # noqa: BLE001 — additive
            _log.warning("examples: code-diagram failed for %s: %s", fixture.fixture_id, exc)
        return
    try:
        from app.services.visual_v2.pipeline import run_for_registered

        base_type, mode = profile.default_visual
        concept_example = {
            "example_id": f"{fixture.fixture_id}_diagram",
            "domain_object": profile.example_type,
            "base_type": base_type,
            "mode": pipeline_mode(mode),
            "algorithm": profile.algorithm,
            "input": {k: v for k, v in fixture.input.items() if k != "array"},
            "base_structure": {"array": list(fixture.input["array"])},
            "learner_goal": fixture.learner_goal,
        }
        concept = run_for_registered(concept_example, model_id=f"{model_id}_diagram")
        if concept.get("status") != "validated":
            return
        diagram = concept["model"]
        n_frames = len(diagram.get("frames") or [])
        if not n_frames:
            return

        frames = result.get("frames") or []

        def _mid_at(fi: int) -> Any:
            return ((frames[fi].get("state_after") or {}).get("variables") or {}).get("mid")

        models = lesson_json.setdefault("visual_models", [])
        models[:] = [m for m in models if m.get("id") != diagram["id"]]
        models.append(diagram)

        # Each change of `mid` between milestones is one completed probe; concept
        # frame k shows probe k (frame 0 = the full starting range). The setup card
        # (not milestone-aligned) shows the full starting range.
        # Setup cards (problem statement + range init) show the full starting range
        # (frame 0); only the iteration step cards zip with the probe milestones.
        def _is_setup(c: dict[str, Any]) -> bool:
            meta = c.get("metadata") or {}
            return bool(meta.get("worked_example_setup") or meta.get("code_setup_range"))

        step_cards = [c for c in cards if not _is_setup(c)]
        for card in cards:
            if _is_setup(card):
                card["diagram_v2_ref"] = {
                    "visual_model_id": diagram["id"], "frame_index": 0, "source": "v2_example_ontology",
                }
        iteration = 0
        prev_mid: Any = None
        for card, fi in zip(step_cards, milestones):
            mid = _mid_at(fi)
            if mid is not None and mid != prev_mid:
                iteration += 1
                prev_mid = mid
            card["diagram_v2_ref"] = {
                "visual_model_id": diagram["id"],
                "frame_index": min(iteration, n_frames - 1),
                "source": "v2_example_ontology",
            }
    except Exception as exc:  # noqa: BLE001 — the diagram is optional polish
        _log.warning("examples: supporting diagram failed for %s: %s", fixture.fixture_id, exc)


def apply_fixture_to_lesson(lesson_json: dict[str, Any], topic: dict[str, Any], card_role: str = "worked_example") -> bool:
    """Declare → select fixture → run the V2 pipeline → swap the worked-example cards.
    Returns True iff applied (lesson_json mutated). Flag-gated + failure-safe."""
    from app.services.examples.declaration import declare_example, pick_fixture
    from app.services.visual_v2.flags import is_v2_enabled
    from app.services.visual_v2.pipeline import run_for_registered

    if not isinstance(lesson_json, dict):
        return False
    topic_id = str(topic.get("id") or "topic")
    started = time.perf_counter()

    declared = declare_example(topic, card_role)
    if declared is None:
        _remove_stale_apply(lesson_json)   # undo any pre-gate apply (e.g. on an intro)
        return _fallback("no_application_match", topic_id)
    fixture = pick_fixture(declared, card_role, seed=topic_id)
    if fixture is None:
        return _fallback("no_fixture_for_role", topic_id, declared.application)

    base_type, _mode = resolve_visual(fixture)
    if not is_v2_enabled(pipeline_mode(_mode), declared.application):
        return _fallback("feature_flag_disabled", topic_id, declared.application)

    example = fixture_to_canonical_example(fixture)
    model_id = f"v2_{declared.application}_{topic_id}"
    try:
        result = run_for_registered(example, model_id=model_id, topic_id=topic_id)
    except Exception as exc:  # noqa: BLE001 — never break the lesson
        _log.warning("examples: pipeline raised for %s: %s", fixture.fixture_id, exc)
        return _fallback("visual_pipeline_failed", topic_id, declared.application)
    if result.get("status") != "validated":
        return _fallback(f"visual_pipeline_failed:{result.get('stage')}", topic_id, declared.application)

    model = result["model"]
    from app.services.visual_v2.code_lesson_integration import cap_milestones
    milestones = cap_milestones(_milestone_frame_indices(result, fixture))
    if not milestones:
        return _fallback("visual_pipeline_failed:no_milestones", topic_id, declared.application)
    # Delta-focused, trace-grounded prose per milestone (deterministic; spec §4.1).
    from app.services.examples.prose_slot import build_prose_slots, fill_slots
    points_per = fill_slots(build_prose_slots(result, milestones, fixture))
    frame_points = None
    if fixture.example_type == "code_execution_trace" and fixture.code:
        from app.services.visual_v2.code_lesson_integration import _loop_line_numbers
        loop_lines = _loop_line_numbers(fixture.code)
        if len(loop_lines) == 1:  # per-bullet frames only for the single-loop scheme
            frame_points = _frame_points_for_code(result.get("frames") or [], milestones, loop_lines, points_per)
    cards = _build_step_cards(model, milestones, points_per, fixture, frame_points)
    if fixture.example_type == "code_execution_trace" and fixture.code:
        setup_range = _code_setup_card(model, fixture)
        if setup_range is not None:
            cards.insert(0, setup_range)
            step_n = 1
            for c in cards:
                if (c.get("metadata") or {}).get("code_setup_range"):
                    continue
                c["title"] = f"{_app_title(fixture.application)}: Step {step_n}"
                step_n += 1
    _ensure_setup_card(cards, model, fixture)   # mandatory problem-statement setup

    # Carry the projector's semantic event_id onto each projected card's ref (the
    # cross-spec join key for dual-slot sync + feedback; §4 step 5, §6.4, §11).
    projection = result.get("projection")
    if projection is not None and getattr(projection, "deltas", None):
        event_ids = [d.get("event_id") for d in projection.deltas]
        for card in cards:
            ref = card.get("visual_v2_ref")
            if isinstance(ref, dict) and isinstance(ref.get("frame_index"), int) and 0 <= ref["frame_index"] < len(event_ids) and event_ids[ref["frame_index"]]:
                ref["event_id"] = event_ids[ref["frame_index"]]

    models = lesson_json.setdefault("visual_models", [])
    models[:] = [m for m in models if m.get("id") != model_id]
    models.append(model)

    # Code-lens extras: the concept diagram toggle + the verified line-by-line
    # code walkthrough (replaces the LLM's unverified walkthrough code).
    _attach_supporting_diagram(lesson_json, cards, milestones, result, fixture, model_id)
    _swap_walkthrough_cards(lesson_json, fixture)

    # Role fixtures (spec §5.2/§7.2): a verified edge-case card + an isomorphic
    # practice question, when the application has fixtures for those roles.
    _apply_edge_case(lesson_json, declared, model_id, seed=topic_id)
    _apply_practice(lesson_json, declared, model_id, seed=topic_id)

    existing = list(lesson_json.get("lesson_cards") or [])
    rebuilt: list[dict[str, Any]] = []
    inserted = False
    for card in existing:
        if str(card.get("blueprint_key") or card.get("card_type") or "").lower() == "worked_example":
            if not inserted:
                rebuilt.extend(cards)
                inserted = True
            continue
        rebuilt.append(card)
    if not inserted:
        idx = next((j for j, c in enumerate(rebuilt) if str(c.get("blueprint_key") or "").lower() == "practice"), len(rebuilt))
        rebuilt[idx:idx] = cards
    lesson_json["lesson_cards"] = rebuilt
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    lesson_json.setdefault("metadata", {})["visual_v2_example_ontology"] = {
        "version": APPLY_VERSION,
        "fixture_id": fixture.fixture_id, "application": declared.application,
        "resolved_example_type": declared.resolved_example_type, "pattern": declared.pattern,
        "fixture_source": fixture.source, "variant": fixture.variant, "model_id": model_id,
        "steps": len(cards), "total_frames": len(result.get("frames") or []),
        "time_to_apply_ms": round(elapsed_ms, 1),
    }
    from app.services.examples.metrics import GLOBAL as METRICS
    METRICS.record_applied(
        application=declared.application,
        resolved_example_type=declared.resolved_example_type,
        pattern=declared.pattern,
        fixture_id=fixture.fixture_id,
        fixture_source=fixture.source,
        variant=fixture.variant,
        raw_frame_count=len(result.get("frames") or []),
        milestone_count=len(milestones),
        elapsed_ms=elapsed_ms,
    )
    return True
