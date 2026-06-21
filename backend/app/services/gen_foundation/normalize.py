"""Deterministic normalization (spec §9.2 step 1 — lossless mechanical fixes).

Real model output drifts from the strict contract in mechanical ways that are safe to
repair WITHOUT a model call: enum synonyms, a `state_relevance` that disagrees with the
`state_delta`, a free-form delta that can be re-expressed as ops against the schema,
derivable `explanation_mode`, and junk `code_refs`. Running this before validation turns
"reject + repair-call" into "fix deterministically", which is the cheap path the spec
prefers. Anything NOT losslessly fixable is left for validation/audit to flag.
"""
from __future__ import annotations

from typing import Any, Optional

from .cards import is_coding_card
from .trace import MAX_WORK_LINES_PER_CARD

_RELEVANCE_SYNONYMS = {
    "dynamic": "stateful", "mutable": "stateful", "changing": "stateful", "evolving": "stateful",
    "fixed": "static", "constant": "static", "stable": "static", "immutable": "static",
    "na": "none", "n/a": "none", "": "none", "irrelevant": "none",
}

_LIST_OPS = {"append", "push", "pop", "remove", "clear"}


def _has_ops(delta: Any) -> bool:
    return isinstance(delta, dict) and isinstance(delta.get("ops"), list) and bool(delta["ops"])


def _freeform_to_ops(delta: dict[str, Any], paths: list[str]) -> Optional[dict[str, Any]]:
    """Salvage a ``{key: value}`` delta into ``{"ops":[{set ...}]}`` for keys that are
    declared schema paths. Returns None if nothing maps (then the delta is dropped)."""
    ops = []
    for key, value in delta.items():
        if key in paths:
            ops.append({"op": "set", "path": key, "value": value})
    return {"ops": ops} if ops else None


def _op_valid(op: Any, schema) -> bool:
    """A delta op is keepable only if its path is declared and its kind fits the op
    (so the §7 derivation can't raise). Mismatched/undeclared ops are dropped."""
    if schema is None or not isinstance(op, dict):
        return False
    name, path = op.get("op"), op.get("path")
    if path not in getattr(schema, "paths", {}):
        return False
    kind = schema.paths[path]
    if name == "add":
        return kind == "number"
    if name in _LIST_OPS:
        return kind == "list"
    if name == "move":
        src = op.get("source")
        return kind == "list" and src in schema.paths and schema.paths[src] == "list"
    return name == "set"  # set works on any declared path


def _derive_title(card: dict[str, Any], index: int) -> str:
    """A short, human title from the card's goal (the model frequently omits `title`, which was the
    dominant cause of fallback-to-legacy). Falls back to a step label."""
    goal = str(card.get("goal") or "").strip().rstrip(".")
    if goal:
        words = goal.split()
        short = " ".join(words[:8])
        return short[:1].upper() + short[1:] if short else f"Step {index + 1}"
    return f"Step {index + 1}"


def normalize_card(card: dict[str, Any], paths: list[str], schema=None, index: int = 0) -> dict[str, Any]:
    if not isinstance(card, dict):
        return card

    # title is required for rendering; the model often omits it -> derive from the goal
    if not str(card.get("title") or "").strip():
        card["title"] = _derive_title(card, index)

    # derive explanation_mode for coding cards
    if card.get("how") and not card.get("explanation_mode"):
        card["explanation_mode"] = "implementation_how"

    # state_relevance: synonyms -> canonical
    sr = str(card.get("state_relevance") or "").strip().lower()
    sr = _RELEVANCE_SYNONYMS.get(sr, sr)

    delta = card.get("state_delta")
    # free-form delta ({path: value}) -> ops form where keys are declared paths
    if isinstance(delta, dict) and "ops" not in delta:
        delta = _freeform_to_ops(delta, paths)
        card["state_delta"] = delta
    # drop ops the schema can't resolve (wrong kind / undeclared path) so derivation can't raise
    if _has_ops(delta) and schema is not None:
        kept = [op for op in delta["ops"] if _op_valid(op, schema)]
        delta = {"ops": kept} if kept else None
        card["state_delta"] = delta

    # reconcile relevance with the delta: real ops -> stateful; otherwise no mutable state
    if _has_ops(delta):
        sr = "stateful"
    else:
        if sr == "stateful":
            sr = "static"  # claimed stateful but no usable delta
        card["state_delta"] = None
    if sr not in ("stateful", "static", "none"):
        sr = "none"
    card["state_relevance"] = sr

    # cap work lines deterministically: merge any overflow into the last kept line (§5.2)
    work = card.get("work")
    if isinstance(work, list) and len(work) > MAX_WORK_LINES_PER_CARD:
        head = [str(w) for w in work[: MAX_WORK_LINES_PER_CARD - 1]]
        tail = "; ".join(str(w) for w in work[MAX_WORK_LINES_PER_CARD - 1:])
        card["work"] = head + [tail]

    # code_refs: keep only positive ints; drop the field if nothing valid remains
    refs = card.get("code_refs")
    if isinstance(refs, list):
        clean = [r for r in refs if isinstance(r, int) and not isinstance(r, bool) and r > 0]
        if clean:
            card["code_refs"] = clean
        else:
            card.pop("code_refs", None)
    elif refs is not None:
        card.pop("code_refs", None)

    # a coding card must not also carry `reasoning` (and vice-versa) — prefer the role's field
    if is_coding_card(card) and "reasoning" in card:
        card.pop("reasoning", None)

    return card


def normalize_artifact(artifact: dict[str, Any], state_schema: Optional[str]) -> dict[str, Any]:
    if not isinstance(artifact, dict):
        return artifact
    schema = None
    paths: list[str] = []
    if state_schema:
        try:
            from .state import get_schema
            schema = get_schema(state_schema)
            paths = sorted(schema.paths)
        except Exception:
            schema = None
    cards = artifact.get("cards")
    if isinstance(cards, list):
        normed = [normalize_card(c, paths, schema, i) for i, c in enumerate(cards)]
        # Drop cards with no concrete `work` — a worked example is concrete steps, not
        # definitional/intro cards (§3). Keep the originals if that would empty the example.
        stepful = [c for c in normed if isinstance(c, dict) and isinstance(c.get("work"), list) and c["work"]]
        artifact["cards"] = stepful or normed
        # Sanitize the state chain: fold deltas over the initial state and DROP any that can't
        # resolve at runtime (e.g. 'remove' a value not present), containing the bad delta to its
        # card (§7) instead of failing the whole worked example -> legacy fallback.
        if schema is not None:
            from .state import InvalidStateDeltaError, apply_delta
            init = artifact.get("initial_resolved_state")
            current = dict(init) if isinstance(init, dict) else {}
            for c in artifact["cards"]:
                delta = c.get("state_delta") if isinstance(c, dict) else None
                if not isinstance(delta, dict):
                    continue
                try:
                    current = apply_delta(current, delta, schema)
                except InvalidStateDeltaError:
                    c["state_delta"] = None
                    if c.get("state_relevance") == "stateful":
                        c["state_relevance"] = "static"
    return artifact
