"""Card-content charters — CARD_CONTENT_CHARTER_SPEC.md (v5).

PRESCRIPTIVE cross-topic overlap control: each card declares the content SLOTS it renders; a per-path,
CARD-AWARE resolver assigns each owned slot a SINGLE owning card, and non-owners get an exclude directive.
The prompt builder concatenates the resolver's prose — it never interprets slots (spec §8 / MUST-NOT).

Phase 1 = the `background` family only is INJECTED (gated by AZALEA_CARD_CHARTERS); the charter table also
carries the `expresses` of the competing card types so ownership RESOLUTION is correct (a definition card must
be able to out-own a background's DEFINE_GLOBAL fallback — spec A16).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

# --- slots (§2) -------------------------------------------------------------------------------------------
SLOTS: tuple[str, ...] = (
    "ORIENT", "MOTIVATE", "INTUIT", "DEFINE_GLOBAL", "DEFINE_LOCAL", "STRUCTURE", "PRECONDITION",
    "PROCEDURE_OVERVIEW", "PROCEDURE", "DERIVE", "INSTANCE", "EDGE", "COMMON_ERROR", "CHECK",
    "PRACTICE", "COMPARE", "APPLY",
)
UNIVERSAL_SLOTS: frozenset[str] = frozenset({"DEFINE_LOCAL"})          # never owned / never excluded
_OWNED_SLOTS: tuple[str, ...] = tuple(s for s in SLOTS if s not in UNIVERSAL_SLOTS)


@dataclass(frozen=True)
class TopicRole:
    topic_type: str
    owns: tuple[str, ...]
    priority: int


@dataclass(frozen=True)
class CardCharter:
    topic_type: str                 # "*" = topic-agnostic default
    card_type: str
    family: str                     # stable rollout key; card-type aliases share one family
    job: str
    expresses: tuple[str, ...] = ()
    fallback_expresses: tuple[str, ...] = ()
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    scope_note: str = ""
    handoff: str = ""


@dataclass(frozen=True)
class SlotDirective:
    include: str
    exclude_template: str           # .format(owner=<friendly label>)


@dataclass(frozen=True)
class SlotOwner:
    topic_order: int
    topic_type: str
    card_type: str
    tier: int                       # 1 role-owner · 2 expresses · 3 fallback
    friendly_label: str = ""


@dataclass(frozen=True)
class TopicPlan:
    topic_key: str                  # stable id (e.g. topic.id)
    topic_type: str
    order_index: int


@dataclass(frozen=True)
class ResolvedCardCharter:
    topic_type: str
    card_type: str
    job: str
    include_slots: tuple[str, ...]
    exclude_slots: tuple[str, ...]
    include_directives: tuple[str, ...]
    exclude_directives: tuple[str, ...]
    scope_note: str
    handoff: str


# --- topic-type ownership (§4) ----------------------------------------------------------------------------
_PROC = ("PROCEDURE_OVERVIEW", "PROCEDURE")
TOPIC_ROLES: dict[str, TopicRole] = {
    "study_path_introduction": TopicRole("study_path_introduction", ("ORIENT",), 10),
    "concept_intuition": TopicRole("concept_intuition", ("INTUIT", "MOTIVATE"), 30),
    "terminology_components": TopicRole("terminology_components", ("DEFINE_GLOBAL", "STRUCTURE"), 40),
    "math_formula_method": TopicRole("math_formula_method", (*_PROC, "DERIVE", "INSTANCE", "EDGE",
                                     "COMMON_ERROR", "CHECK", "PRECONDITION", "PRACTICE"), 60),
    "process_walkthrough": TopicRole("process_walkthrough", (*_PROC, "INSTANCE", "EDGE", "COMMON_ERROR",
                                     "CHECK", "PRECONDITION", "PRACTICE"), 60),
    "algorithm_walkthrough": TopicRole("algorithm_walkthrough", (*_PROC, "INSTANCE", "EDGE",
                                       "PRECONDITION", "CHECK"), 60),
    "data_structure_operation": TopicRole("data_structure_operation", ("STRUCTURE", *_PROC, "INSTANCE",
                                          "PRECONDITION"), 55),
    "coding_implementation": TopicRole("coding_implementation", (*_PROC, "INSTANCE", "COMMON_ERROR",
                                       "CHECK", "PRACTICE"), 65),
    "proof_reasoning": TopicRole("proof_reasoning", ("DERIVE", "PROCEDURE", "CHECK"), 60),
    "science_mechanism": TopicRole("science_mechanism", ("INTUIT", *_PROC, "INSTANCE", "PRECONDITION"), 60),
    "compare_distinguish": TopicRole("compare_distinguish", ("COMPARE",), 50),
    "problem_solving_application": TopicRole("problem_solving_application", ("APPLY", "PRACTICE",
                                            "COMMON_ERROR", "CHECK"), 70),
}
_ZERO_ROLE = TopicRole("", (), 0)


def _role_owns(topic_type: str, slot: str) -> bool:
    return slot in TOPIC_ROLES.get(topic_type, _ZERO_ROLE).owns


_FRIENDLY_LABELS: dict[str, str] = {
    "study_path_introduction": "the intro topic",
    "concept_intuition": "the intuition topic",
    "terminology_components": "the glossary topic",
    "math_formula_method": "the method topic",
    "process_walkthrough": "the process topic",
    "algorithm_walkthrough": "the walkthrough topic",
    "coding_implementation": "the implementation topic",
    "problem_solving_application": "the application topic",
}


def _friendly(topic_type: str) -> str:
    return _FRIENDLY_LABELS.get(topic_type, f"the {topic_type.replace('_', ' ')} topic")


# --- slot directives (§5 prose the resolver emits) --------------------------------------------------------
SLOT_DIRECTIVES: dict[str, SlotDirective] = {
    "ORIENT": SlotDirective("State what the learner will be able to do by the end and why it matters.",
                            "Do NOT restate path-level goals — {owner} covers them."),
    "MOTIVATE": SlotDirective("Say when and why you would reach for this.",
                              "Do NOT motivate why/when this matters — {owner} covers it."),
    "INTUIT": SlotDirective("Give the one-sentence mental model — the intuition for what this is.",
                            "Do NOT explain the intuition or re-answer \"what is this\" — {owner} covers it."),
    "DEFINE_GLOBAL": SlotDirective("Define, in full, every term the path uses.",
                                   "Do NOT formally define terms — {owner} is the glossary; reference it."),
    "DEFINE_LOCAL": SlotDirective("You MAY name a term you use in one clause "
                                  "(e.g. \"where b is the linear coefficient\") — do not expand it into a full definition.",
                                  ""),
    "STRUCTURE": SlotDirective("Lay out the inputs, outputs, parts, and notation.",
                               "Do NOT enumerate the anatomy/parts — {owner} covers it."),
    "PRECONDITION": SlotDirective("State when the method applies and its input assumptions/constraints.",
                                  "Do NOT state preconditions — {owner} covers them."),
    "PROCEDURE_OVERVIEW": SlotDirective("Name the method/approach in one breath — the shape, not the steps.",
                                        "Do NOT even summarize the approach — {owner} covers it."),
    "PROCEDURE": SlotDirective("Give the full ordered method / steps.",
                               "Do NOT teach the full procedure — {owner} covers it."),
    "DERIVE": SlotDirective("Justify why the method works.",
                            "Do NOT justify why it works — {owner} covers it."),
    "INSTANCE": SlotDirective("Show one fully worked instance.",
                              "Do NOT add a worked example — {owner} covers worked instances."),
    "EDGE": SlotDirective("Cover the degenerate / boundary cases, treated correctly.",
                          "Do NOT cover edge cases — {owner} owns them."),
    "COMMON_ERROR": SlotDirective("Call out the mistake learners commonly make here and how to avoid it.",
                                  "Do NOT list common mistakes — {owner} covers them."),
    "CHECK": SlotDirective("Show how to verify the result.",
                           "Do NOT show how to verify — {owner} covers it."),
    "PRACTICE": SlotDirective("Give a problem to attempt, within the taught scope, distinct from any earlier practice.",
                              "Do NOT add practice — {owner} covers it."),
    "COMPARE": SlotDirective("Contrast with the alternatives.",
                             "Do NOT compare alternatives — {owner} covers it."),
    "APPLY": SlotDirective("Apply the method to a real problem.",
                           "Do NOT add an application — {owner} covers it."),
}


# --- the charter table (§6) -------------------------------------------------------------------------------
# INJECTED family (Phase 1): background. Non-injected rows carry `expresses` only so RESOLUTION is correct.
_METHOD_BG = ("PROCEDURE_OVERVIEW", "STRUCTURE")
_METHOD_BG_FALLBACK = ("INTUIT", "MOTIVATE", "DEFINE_GLOBAL")
_BG_SCOPE = "Name the method and goal only; do not teach the full procedure or a glossary."

CARD_CHARTERS: dict[tuple[str, str], CardCharter] = {
    ("study_path_introduction", "background"): CardCharter(
        "study_path_introduction", "background", "background",
        job="Orient the path: what you'll be able to do, and why it matters.", expresses=("ORIENT",)),
    ("concept_intuition", "background"): CardCharter(
        "concept_intuition", "background", "background",
        job="Give the mental model and when you'd reach for this.", expresses=("INTUIT", "MOTIVATE")),
    ("math_formula_method", "background"): CardCharter(
        "math_formula_method", "background", "background",
        job="Name the method, its inputs/output, and the goal.",
        expresses=_METHOD_BG, fallback_expresses=_METHOD_BG_FALLBACK, scope_note=_BG_SCOPE),
    ("process_walkthrough", "background"): CardCharter(
        "process_walkthrough", "background", "background",
        job="Name the process, its inputs/output, and the goal.",
        expresses=_METHOD_BG, fallback_expresses=_METHOD_BG_FALLBACK, scope_note=_BG_SCOPE),
    ("algorithm_walkthrough", "background"): CardCharter(
        "algorithm_walkthrough", "background", "background",
        job="The problem it solves and the high-level approach.",
        expresses=("PROCEDURE_OVERVIEW",), fallback_expresses=("INTUIT", "MOTIVATE"), scope_note=_BG_SCOPE),
    ("coding_implementation", "background"): CardCharter(
        "coding_implementation", "background", "background",
        job="The problem the code solves and the approach.",
        expresses=("PROCEDURE_OVERVIEW",), fallback_expresses=("MOTIVATE",), scope_note=_BG_SCOPE),
}

# Topic-agnostic defaults for the COMPETING card types — ownership data only (their families aren't injected
# in Phase 1, but the resolver needs their `expresses` so e.g. a definition card out-owns a bg's DEFINE_GLOBAL).
CARD_CHARTER_DEFAULTS: dict[str, CardCharter] = {
    "components_terms": CardCharter("*", "components_terms", "definition",
        job="Define the terms this path uses.", expresses=("DEFINE_GLOBAL", "STRUCTURE")),
    "formula_breakdown": CardCharter("*", "formula_breakdown", "method_process",
        job="The formula/method and why it works.", expresses=("PROCEDURE", "DERIVE", "PRECONDITION")),
    "method_process": CardCharter("*", "method_process", "method_process",
        job="The ordered method / steps.", expresses=("PROCEDURE", "PRECONDITION")),
    "formula": CardCharter("*", "formula", "method_process",
        job="The formula that drives the method.", expresses=("PROCEDURE",)),
    "worked_example": CardCharter("*", "worked_example", "worked_example",
        job="One fully worked instance.", expresses=("INSTANCE",)),
    "edge_case": CardCharter("*", "edge_case", "edge_case",
        job="The degenerate / boundary cases.", expresses=("EDGE",)),
    "practice": CardCharter("*", "practice", "practice",
        job="A problem to attempt within the taught scope.", expresses=("PRACTICE",)),
    "roadmap": CardCharter("*", "roadmap", "roadmap",
        job="Preview the path's topics.", expresses=("ORIENT",)),
    "summary": CardCharter("*", "summary", "summary",
        job="Compress what was taught; introduce nothing new.",
        scope_note="Compress what was taught; introduce nothing new."),
    "review": CardCharter("*", "review", "summary",
        job="Compress what was taught; introduce nothing new.",
        scope_note="Compress what was taught; introduce nothing new."),
    "takeaway": CardCharter("*", "takeaway", "summary",
        job="Compress what was taught; introduce nothing new.",
        scope_note="Compress what was taught; introduce nothing new."),
}


def charter_for(topic_type: str, card_type: str) -> CardCharter | None:
    """(topic_type, card_type) cell → card_type default → None (spec §3)."""
    return CARD_CHARTERS.get((topic_type, card_type)) or CARD_CHARTER_DEFAULTS.get(card_type)


# --- rollout (§12) ----------------------------------------------------------------------------------------
_FLAG = "AZALEA_CARD_CHARTERS"


def active_charter_families() -> frozenset[str]:
    """The active families from AZALEA_CARD_CHARTERS (comma-separated; `all` = every family; unset/empty = off)."""
    raw = str(os.getenv(_FLAG, "")).strip().lower()
    if not raw:
        return frozenset()
    if raw == "all":
        return frozenset({"all"})
    return frozenset(f.strip() for f in raw.split(",") if f.strip())


def _family_active(family: str, active: frozenset[str]) -> bool:
    return "all" in active or family in active


# --- resolution (§5) --------------------------------------------------------------------------------------
def _best(records: list[tuple[TopicPlan, str, int]]) -> tuple[TopicPlan, str, int]:
    # highest priority, ties earliest order_index, then earliest card-plan index
    return min(records, key=lambda r: (-TOPIC_ROLES.get(r[0].topic_type, _ZERO_ROLE).priority,
                                       r[0].order_index, r[2]))


def resolve_ownership(topics: list[TopicPlan],
                      card_plans_by_topic: dict[str, list[str]]) -> dict[str, SlotOwner]:
    """Assign each owned slot a single owning (topic, card) by precedence tiers (§5). CARD-AWARE — a topic
    qualifies only if it has a planned card whose charter can render the slot."""
    owners: dict[str, SlotOwner] = {}
    for slot in _OWNED_SLOTS:
        express: list[tuple[TopicPlan, str, int]] = []
        fallback: list[tuple[TopicPlan, str, int]] = []
        for t in topics:
            for idx, ct in enumerate(card_plans_by_topic.get(t.topic_key, ()) or ()):
                ch = charter_for(t.topic_type, ct)
                if ch is None:
                    continue
                if slot in ch.expresses:
                    express.append((t, ct, idx))
                elif slot in ch.fallback_expresses:
                    fallback.append((t, ct, idx))
        role_express = [r for r in express if _role_owns(r[0].topic_type, slot)]
        role_fallback = [r for r in fallback if _role_owns(r[0].topic_type, slot)]
        pick, tier = None, 0
        if role_express:
            pick, tier = _best(role_express), 1
        elif role_fallback:
            pick, tier = _best(role_fallback), 1
        elif express:
            pick, tier = _best(express), 2
        elif fallback:
            pick, tier = _best(fallback), 3
        if pick is not None:
            t, ct, _ = pick
            owners[slot] = SlotOwner(t.order_index, t.topic_type, ct, tier, _friendly(t.topic_type))
    return owners


def resolve_card(charter: CardCharter, ownership: dict[str, SlotOwner],
                 this_topic: TopicPlan, this_card_type: str) -> ResolvedCardCharter:
    """Turn a charter + ownership into human-readable directives for exactly THIS card (§5). Slots this card
    owns → include; expressed slots a sibling owns → exclude; fallback slots owned elsewhere / unresolved → omit."""
    include_slots: list[str] = []
    exclude_slots: list[str] = []
    inc: list[str] = []
    exc: list[str] = []
    seen: set[str] = set()
    for slot in (*charter.expresses, *charter.fallback_expresses):
        if slot in seen:
            continue
        seen.add(slot)
        owner = ownership.get(slot)
        if owner is None:
            continue                                            # genuinely uncarried (§5) → omit
        if (owner.topic_type == this_topic.topic_type and owner.card_type == this_card_type
                and owner.topic_order == this_topic.order_index):
            include_slots.append(slot)                          # this card owns it (incl. a fired fallback)
            inc.append(SLOT_DIRECTIVES[slot].include)
        else:
            exclude_slots.append(slot)                          # a sibling owns it → tell this card NOT to render it
            exc.append(SLOT_DIRECTIVES[slot].exclude_template.format(owner=owner.friendly_label))
    inc.append(SLOT_DIRECTIVES["DEFINE_LOCAL"].include)          # universal allowance, always
    return ResolvedCardCharter(
        this_topic.topic_type, this_card_type, charter.job,
        tuple(include_slots), tuple(exclude_slots), tuple(inc), tuple(exc),
        charter.scope_note, charter.handoff)


def resolve_card_for(this_topic: TopicPlan, card_type: str,
                     ownership: dict[str, SlotOwner]) -> ResolvedCardCharter | None:
    """Convenience: look up the charter and resolve it, or None if the card is ungoverned or its family is off."""
    charter = charter_for(this_topic.topic_type, card_type)
    if charter is None or not _family_active(charter.family, active_charter_families()):
        return None
    return resolve_card(charter, ownership, this_topic, card_type)


# §12: report the active set at import so the feature can't silently no-op (unlike the dark flags).
try:
    _active = active_charter_families()
    if _active:
        logging.getLogger(__name__).info("card_charters active families: %s", sorted(_active))
except Exception:  # noqa: BLE001
    pass
