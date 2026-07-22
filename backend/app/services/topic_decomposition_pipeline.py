"""Topic-decomposition generation orchestration (TOPIC_DECOMPOSITION_SPEC.md, the flagged live path).

generate_decomposed_topics(chunks, goal, feedback) does the single-call generation, then runs the pure
deterministic core (normalize -> append coding follow-ups -> validate) and ADAPTS the result into the
legacy topic-dict shape the existing lesson pipeline already consumes — so turning the flag on changes
how topics are *decided* without changing anything downstream. The model call is injectable so the
whole orchestration is unit-testable without an API call.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Callable, Optional

from app.core.topic_decomposition import (
    canonical_action, normalize_subject_key, resolve_topic_type,
)
from app.core.topic_decomposition_appender import IMPLEMENTATION_FOLLOW_UP, append_coding_follow_ups
from app.core.topic_decomposition_validator import OverlapResolver, validate_topic_decomposition
from app.core.decision_trace import (
    record_path_decision, record_topic_decision, take_path_trace, take_topic_trace,
)
from app.prompts.topic_decomposition_prompt import (
    REQUIREMENTS_SYSTEM_PROMPT, SYSTEM_PROMPT, build_decomposition_prompt, build_goal_requirements_prompt,
)

_log = logging.getLogger(__name__)

# model_fn: ({"system","user"}) -> parsed {"path_plan", "topics"} (or raw str the pipeline json-loads).
ModelFn = Callable[[dict[str, str]], Any]


def _default_model_fn(payload: dict[str, str]) -> dict[str, Any]:
    from app.services.llm_client import generate_topic_decomposition
    return generate_topic_decomposition(system_prompt=payload["system"], user_prompt=payload["user"])


def _default_resolver() -> Optional[OverlapResolver]:
    """The bounded LLM overlap resolver, only when AZALEA_TOPIC_OVERLAP_RESOLVER is enabled (it costs an
    extra call per genuinely ambiguous pair). Off -> validator flags-and-keeps ambiguous pairs."""
    if os.getenv("AZALEA_TOPIC_OVERLAP_RESOLVER", "") in ("", "0"):
        return None
    from app.services.llm_client import resolve_topic_overlap
    return resolve_topic_overlap


def _coerce(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return raw if isinstance(raw, dict) else {}


# Pedagogical-ASPECT words: a phrase containing one describes how a topic teaches (examples, practice,
# outputs, definitions), never an external concept — such phrases must not be promoted to prerequisites.
_ASPECT_PHRASE_TOKENS = frozenset({
    "example", "examples", "practice", "problem", "problems", "exercise", "exercises",
    "output", "outputs", "characteristic", "characteristics", "definition", "definitions",
    "implementation", "implementations", "basics", "overview", "case", "cases",
    "application", "applications", "illustration", "illustrations", "visual", "visuals",
})

# Tokens that mark a topic as comparison/evaluation CONTENT rather than an algorithm to trace — such a topic
# must never be typed code-able (the appender would manufacture an "Implementing <analysis>" follow-up).
_ANALYSIS_FRAMING_TOKENS = frozenset({
    "evaluating", "evaluate", "evaluation", "comparing", "compare", "comparison", "complexity",
    "analysis", "analyzing", "choosing", "tradeoffs", "tradeoff",
})


def _normalize_topic(t: dict[str, Any]) -> dict[str, Any]:
    """Format-normalize the model's fields (subject_key, primary_action, topic_type) before validation."""
    t = dict(t)
    t["subject_key"] = normalize_subject_key(t.get("subject_key"))
    if t.get("primary_action"):
        t["primary_action"] = canonical_action(t["primary_action"]) or t["primary_action"]
    if not t.get("topic_type") and t.get("content_role"):
        t["topic_type"] = resolve_topic_type(t["content_role"])
    # ROLE/TYPE upgrade: a topic whose declared role maps to a substantive lesson shape but was typed
    # concept_intuition gets the 4-card overview blueprint — no process card, no worked-example slot, not
    # WE-centric (live: 'Flow Types', role=mechanism, typed concept_intuition, shipped 4 thin cards with no
    # mechanism explanation). Upgrade ONLY out of concept_intuition and only to the role's canonical type;
    # a deliberate concept lesson (role foundation) is untouched.
    role = str(t.get("content_role") or "").strip().lower()
    if role and str(t.get("topic_type") or "") == "concept_intuition":
        canonical_tt = resolve_topic_type(role)
        if canonical_tt and canonical_tt not in ("concept_intuition", "study_path_introduction"):
            _log.info("topic normalize: upgraded %r from concept_intuition to %s (content_role=%s)",
                      t.get("title"), canonical_tt, role)
            record_topic_decision(t, "normalize.type_upgrade", f"topic_type -> {canonical_tt}",
                                  "concept_intuition under-blueprints a substantive role: no process card, "
                                  "no worked-example slot, not WE-centric", content_role=role,
                                  from_type="concept_intuition")
            t["topic_type"] = canonical_tt
    # ANALYSIS-framed "walkthroughs": 'Evaluating Traversal Complexity' typed algorithm_walkthrough is not an
    # algorithm — it is comparison/analysis content, and leaving the type triggers the coding-follow-up policy
    # (live: a synthesized 'Implementing Evaluating Traversal Complexity' topic). Retype to compare_distinguish
    # BEFORE the appender runs so no follow-up is ever manufactured for it.
    if str(t.get("topic_type") or "") in ("algorithm_walkthrough", "data_structure_operation"):
        toks = set(re.findall(r"[a-z0-9]+", str(t.get("title") or "").lower()))
        toks |= {w for w in str(t.get("subject_key") or "").split("_") if w}
        if toks & _ANALYSIS_FRAMING_TOKENS:
            _log.info("topic normalize: %r is analysis-framed, retyped %s -> compare_distinguish",
                      t.get("title"), t.get("topic_type"))
            record_topic_decision(t, "normalize.analysis_retype", "topic_type -> compare_distinguish",
                                  "title/subject reads as comparison or complexity ANALYSIS, not an "
                                  "algorithm to trace — leaving it code-able would let the follow-up "
                                  "appender manufacture an 'Implementing <analysis>' topic",
                                  from_type=t.get("topic_type"),
                                  matched_tokens=sorted(toks & _ANALYSIS_FRAMING_TOKENS))
            t["topic_type"] = "compare_distinguish"
            t["content_role"] = "comparison"
    return t


def _subject_phrase(subject_key: str) -> str:
    return (subject_key or "").replace("_", " ").strip().title() or "the algorithm"


def _cross_topic_foundations(teaching_topics: list[dict[str, Any]], goal: str | None) -> list[str]:
    """A concept named in the in_scope of ≥2 teaching topics but TAUGHT by none (matches no topic's
    subject/title) is a shared assumed foundation — a prerequisite the LLM often forgets to declare. E.g. on a
    Bayes path both 'Law of Total Probability' and 'Bayes Theorem' list 'conditional probability' in_scope, yet
    no topic teaches it → it is a prerequisite, not a key term. Deterministic backstop to the LLM's
    path_plan.assumed_prerequisites. Excludes anything the goal names (that stays in-scope/taught)."""
    def _norm(s: str) -> str:
        return re.sub(r"[^a-z0-9 ]+", "", str(s or "").replace("_", " ").lower()).strip()

    subjects = {_norm(t.get("subject_key")) for t in teaching_topics} | {_norm(t.get("title")) for t in teaching_topics}
    subjects.discard("")
    counts: dict[str, tuple[str, int]] = {}   # norm -> (display, topic_count)
    for t in teaching_topics:
        for concept in {_norm(c): str(c).strip() for c in (t.get("in_scope") or [])}.items():
            norm, display = concept
            if not norm or norm in subjects:
                continue
            disp, n = counts.get(norm, (display, 0))
            counts[norm] = (disp, n + 1)
    out: list[str] = []
    for norm, (display, n) in counts.items():
        # A shared scope item is only a FOUNDATION when it names a CONCEPT. Pedagogical-aspect phrases the
        # model copy-pastes across siblings ("examples of performed traversals", "output characteristics",
        # "practice problems for traversal implementation" — live junk prereqs) describe the topics
        # themselves, not an external concept a learner could study first.
        if set(norm.split()) & _ASPECT_PHRASE_TOKENS:
            continue
        if (n >= 2 and not _goal_names_topic({"title": display, "subject_key": display}, goal)
                and not _is_circular_prereq(display, goal)):
            out.append(display)
    return out


# Prepositions/conjunctions that never legitimately OPEN an educational topic title, so a title starting with
# one is a malformed LLM fragment (e.g. "With Ohm's Law", a truncation of "Calculating With Ohm's Law").
# Deliberately EXCLUDES "for"/"in"/"on" — those DO start real titles ("For Loops", "In-place Sorting").
_LEADING_TITLE_JUNK = frozenset({"with", "of", "by", "to", "from", "at", "and", "or"})


_GOAL_MATCH_GLUE = frozenset({"the", "a", "an", "of", "and", "or", "for", "to", "in", "on", "with", "by", "as"})


def _goal_names_topic(topic: dict[str, Any], goal: str | None) -> bool:
    """True when the learner's goal explicitly names this concept (so it belongs IN scope as a taught topic, not
    demoted to an external prerequisite). Matches when the concept's distinctive title/subject words all appear
    in the goal — e.g. goal '…law of total probability' names the 'Law of Total Probability' topic."""
    goal_words = set(re.findall(r"[a-z]+", str(goal or "").lower()))
    if not goal_words:
        return False
    for field in ("subject_key", "title"):
        raw = str(topic.get(field) or "").replace("_", " ").lower()
        terms = {w for w in re.findall(r"[a-z]+", raw) if len(w) >= 3 and w not in _GOAL_MATCH_GLUE}
        if terms and terms <= goal_words:
            return True
    return False


# Generic wrapper words that carry no subject identity in a prerequisite name ("Combinatorial PRINCIPLES",
# "counting BASICS"). Stripped before deciding whether a prereq is just the goal subject in disguise.
_GENERIC_PREREQ_WORDS = frozenset({
    "principle", "principles", "basic", "basics", "fundamental", "fundamentals", "foundation", "foundations",
    "essential", "essentials", "concept", "concepts", "idea", "ideas", "theory", "introduction", "intro",
    "overview", "notation", "method", "methods", "technique", "techniques", "skill", "skills", "analysis",
})


# Generic structure-anatomy words: parts every tree/graph/list already has. In a prereq name they add no
# outside subject ("node traversal" is just "traversal"); a name that is ONLY anatomy ("trees") names a real
# structure and is kept.
_STRUCTURAL_ANATOMY_WORDS = frozenset({
    "node", "nodes", "element", "elements", "item", "items", "tree", "trees", "vertex", "vertices"})


def _prereq_word(w: str) -> str:
    """Light singularization for prereq identity ('trees'≈'tree'; never 'class'→'clas')."""
    if len(w) >= 4 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _prereq_key(name: str) -> str:
    """Shape-blind prereq identity: slug/display/case/plural forms of one concept share a key
    ('binary_search_tree' == 'Binary Search Trees')."""
    return " ".join(_prereq_word(w) for w in re.findall(r"[a-z0-9]+", str(name or "").lower()))


# Trailing qualifiers that weaken a prereq name ("Graph theory basics" reads like a blog post; "Graph theory"
# reads like the textbook chapter the card is pointing at). Stripped from DISPLAY only, repeatedly, never
# below one word.
_PREREQ_TAIL_QUALIFIERS = frozenset({
    "basics", "basic", "fundamentals", "fundamental", "essentials", "foundations", "introduction", "intro",
    "primer", "101", "overview", "concepts", "principles"})


def _strip_generic_prereq_tail(name: str) -> str:
    words = str(name or "").strip().split()
    while len(words) > 1 and words[-1].lower().strip(".,") in _PREREQ_TAIL_QUALIFIERS:
        words.pop()
    return " ".join(words)


_PREREQ_LEAD_GLUE = frozenset({"to", "of", "the", "a", "an", "and", "in", "on", "for", "with"})


def _prereq_display(name: str) -> str:
    s = str(name or "").strip()
    s = s.replace("_", " ").strip() if "_" in s else s
    # leading glue reads malformed on the card and in the link ("to Fluid Dynamics" — live defect)
    words = s.split()
    while len(words) > 1 and words[0].lower() in _PREREQ_LEAD_GLUE:
        words.pop(0)
    s = " ".join(words)
    return _strip_generic_prereq_tail(s) or s


def _drop_prereq_chain_redundancy(names: list[str]) -> list[str]:
    """The prereq card offers earlier-textbook-unit refreshers. A prereq that is itself a prerequisite OF
    another listed prereq is redundant — refreshing the advanced one covers it ('binary trees' beside 'binary
    search trees'; 'probability' beside 'conditional probability'). Detected as a PROPER word-subset on the
    singularized key words; the broader/simpler entry (the subset) is dropped, the advanced one kept."""
    key_words = {n: frozenset(_prereq_key(n).split()) for n in names}
    kept = []
    for n in names:
        kw = key_words[n]
        if kw and any(kw < key_words[m] for m in names if m != n):
            continue
        kept.append(n)
    return kept


def _is_circular_prereq(name: str, goal: str | None) -> bool:
    """True when a proposed prerequisite is really THE GOAL SUBJECT wrapped in generic words — e.g. goal
    'learn combinatorial analysis' with prereq 'Combinatorial Principles'. Such a prereq is CIRCULAR (its
    open_study_path link would open a path teaching the very subject the learner asked for) and the concepts
    it hides are this path's own first topics. After dropping generic wrapper words, if every remaining
    distinctive word appears in the goal (light stemming so 'combinatorics'≈'combinatorial'), it's circular.
    A prereq from a DIFFERENT subject ('basic probability', 'binary search trees') keeps a distinctive word
    the goal lacks and passes."""
    # A prereq that IS a comparison/analysis of multiple techniques is circular by construction, regardless
    # of whether its distinctive words happen to overlap the goal's own wording: a genuine external
    # prerequisite names ONE prior concept, never a meta-level comparison — comparing this path's own
    # techniques is a SYNTHESIS of what the path teaches (often its own compare_distinguish topic), not
    # something learned beforehand. Live: goal 'bst traversal' with prereq 'comparison with other traversal
    # methods' — no word overlaps the goal directly ("comparison"/"other"/"methods" all pass the ordinary
    # goal-word check below), so it read as "a prereq from a different subject" and survived, telling the
    # learner to already be able to "describe at least three tree traversal techniques" before starting the
    # very path that teaches them — while the path ALSO had its own real 'Comparing Tree Traversal Orders'
    # topic the prereq never matched (differently phrased, missed by the exact-title taught-topic guard).
    if re.search(r"\b(comparison|compare|comparing|contrast|contrasting)\b", str(name or "").lower()):
        return True
    goal_words = set(re.findall(r"[a-z]+", str(goal or "").lower()))
    if not goal_words:
        return False

    def _in_goal(w: str) -> bool:
        if w in goal_words:
            return True
        # light stem: shared 6+ char prefix ("combinatorics" ~ "combinatorial")
        return any(len(w) >= 6 and len(g) >= 6 and (g.startswith(w[:6]) or w.startswith(g[:6]))
                   for g in goal_words)

    words = [w for w in re.findall(r"[a-z]+", str(name or "").lower())
             if len(w) >= 3 and w not in _GOAL_MATCH_GLUE and w not in _GENERIC_PREREQ_WORDS]
    # All generic ("basics", "fundamentals") → names no outside subject at all → circular/useless as a prereq.
    if not words:
        return True
    # Structural-anatomy words are not a DIFFERENT subject — they are the generic parts of the structure the
    # goal already implies. Live failure: prereq "node traversal" on a "bst traversal" goal survived because
    # "node" is not a goal word, then told the learner to already "explain and implement pre/in/post-order
    # traversal" — the exact content of the path. Stripping anatomy words makes it {traversal} ⊆ goal →
    # circular. A prereq naming ONLY a structure ("trees") stays: that is a legitimate structural prereq.
    core = [w for w in words if w not in _STRUCTURAL_ANATOMY_WORDS]
    if not core:
        return False
    return all(_in_goal(w) for w in core)


# Broad whole-DISCIPLINE names that make poor prerequisites: they restate an entire field rather than the
# specific concept the goal actually needs, and their sub-concepts usually appear as their OWN, tighter prereqs
# (live failure: a z-score path listed BOTH 'Statistics' and 'mean and median', where Statistics' own
# "what to learn" was mean/median/mode — pure redundancy). Dropped only when a more specific prereq remains.
_UMBRELLA_FIELDS = frozenset({
    "statistics", "mathematics", "math", "maths", "programming", "coding", "computer science",
    "computing", "data science", "science", "engineering", "arithmetic",
    # whole-subfield umbrellas (live: 'fluid mechanics' beside the specific 'Viscosity' + 'Reynolds Number' —
    # the umbrella vaguely restates what its specific siblings already cover)
    "fluid mechanics", "fluid dynamics", "physics", "chemistry", "accounting", "finance", "economics",
    # CS umbrellas (live: 'Data Structures' beside the specific 'Recursion' on a bst-traversal path — the
    # learner needs binary search trees, not the whole field)
    "data structures", "algorithms", "software engineering",
})


def _drop_umbrella_prereqs(prereqs: list[str]) -> list[str]:
    """Remove a broad umbrella-discipline prerequisite ('Statistics', 'Mathematics') when at least one more
    specific prerequisite remains — the specific one is what the learner actually needs, and the umbrella just
    duplicates it vaguely. If EVERY prereq is an umbrella (nothing more specific), keep exactly ONE: two
    whole-discipline names are near-synonyms by construction (live: 'fluid dynamics' AND 'Fluid Mechanics'
    listed side by side — different words, so no lexical dedup could see them; both umbrellas)."""
    specific = [p for p in prereqs if _norm_title(p) not in _UMBRELLA_FIELDS]
    if specific and len(specific) < len(prereqs):
        dropped = [p for p in prereqs if _norm_title(p) in _UMBRELLA_FIELDS]
        _log.info("topic_decomposition: dropped umbrella-field prereq(s) %s (kept specific: %s)", dropped, specific)
        return specific
    if not specific and len(prereqs) > 1:
        _log.info("topic_decomposition: multiple umbrella-only prereqs %s -> kept first", prereqs)
        return prereqs[:1]
    return prereqs


def _norm_title(t: str) -> str:
    """Lowercase alnum words of a title, minus glue, for equality/containment checks."""
    return " ".join(w for w in re.findall(r"[a-z0-9]+", str(t or "").lower())
                    if w not in _GOAL_MATCH_GLUE)


# Role verbs for renaming a topic whose bare title collides with the path/goal or another topic. An
# application/synthesis topic BECOMES "Applying <X>"; a review/practice one "Practicing <X>".
_SYNTHESIS_ROLES = {"application": "Applying", "problem_solving_application": "Applying",
                    "synthesis": "Applying", "review": "Reviewing", "practice": "Practicing"}


def _disambiguate_topic_titles(ordered: list[dict[str, Any]], goal: str | None) -> None:
    """Deterministic decomposition validation (naming): a TEACHING topic must not carry the same title as the
    whole path/goal ('Combinatorial Analysis' topic on a Combinatorial-Analysis path) nor duplicate an earlier
    topic's title — both read as 'why is this here?' to a learner. Rename the offender by its ROLE ('Applying
    Combinatorial Analysis' for an application/synthesis topic), else prefix a clarifier. Mutates in place."""
    goal_words = set(_norm_title(goal).split())
    seen: dict[str, int] = {}
    teaching_seen = 0
    for t in ordered:
        if _is_opener(t):
            continue
        title = str(t.get("title") or "").strip()
        words = set(_norm_title(title).split())
        if not words:
            teaching_seen += 1
            continue
        role = str(t.get("content_role") or "").lower()
        ttype = str(t.get("topic_type") or "").lower()
        verb = _SYNTHESIS_ROLES.get(role) or _SYNTHESIS_ROLES.get(ttype)
        # Title IS the whole path subject (all its words in the goal, a substantial >=2-word subject) AND it is a
        # LATE synthesis/application topic — real teaching topics already precede it, so a topic re-titled the
        # whole subject is a redundant synthesis, not the primary lesson. (A single-concept path whose one topic
        # legitimately IS the subject — 'Bayes Theorem' — is left alone: teaching_seen is 0 there.)
        collides_goal = bool(verb) and len(words) >= 2 and words <= goal_words and teaching_seen >= 2
        collides_prev = " ".join(sorted(words)) in seen
        if collides_goal or collides_prev:
            if verb and not title.lower().startswith(verb.lower()):
                t["title"] = f"{verb} {title}"
            elif collides_prev and not title.lower().startswith(("more on", "further")):
                t["title"] = f"More on {title}"
            _log.info("topic_decomposition: disambiguated colliding title %r -> %r "
                      "(goal=%s prev=%s)", title, t.get("title"), collides_goal, collides_prev)
            record_topic_decision(
                t, "title.disambiguated", f"title -> {t.get('title')!r}",
                ("title restated the whole goal subject as a LATE synthesis/application topic — real "
                 "teaching topics already precede it" if collides_goal
                 else "title collided with an earlier topic's title after normalization"),
                original_title=title)
        seen[" ".join(sorted(_norm_title(str(t.get("title") or "")).split()))] = 1
        teaching_seen += 1


# Generic words that, appended to a topic title, do NOT change its subject — so 'X' and 'X Mechanisms' are the
# same lesson. A REAL distinguishing word (e.g. 'Trees' in 'Binary Search Trees') is deliberately NOT here, so
# only filler-only title differences collapse.
_GENERIC_TOPIC_FILLER = frozenset({
    "mechanisms", "mechanism", "overview", "fundamentals", "fundamental", "basics", "basic", "concepts",
    "concept", "process", "processes", "explained", "introduction", "intro", "techniques", "technique",
    "methods", "method", "essentials", "principles", "principle", "walkthrough", "guide", "review",
    "understanding", "working", "details", "detail", "deep", "dive", "explainer", "primer", "explanation",
    "insights", "insight",
    # synonyms for "the thing itself" that the model uses to split ONE concept into look-alike topics
    "algorithms", "algorithm", "strategies", "strategy", "approaches", "approach", "models", "model",
    "systems", "operations", "operation", "steps", "phases", "phase",
})

# Titles that merely re-orient to the goal ("Introduction to X", "Overview of X") — when collapsing a pair, the
# NON-intro topic is the substantive keeper.
_INTRO_TITLE_WORDS = frozenset({"introduction", "intro", "overview", "understanding"})


def _significant_title_words(topic: dict[str, Any]) -> set[str]:
    """Distinctive title words (>=3 chars, minus generic prereq glue) for near-duplicate detection."""
    return {w for w in _norm_title(topic.get("title")).split()
            if len(w) >= 3 and w not in _GENERIC_PREREQ_WORDS}


def _merge_topic_scope(keep: dict[str, Any], drop: dict[str, Any]) -> None:
    """Fold drop's in_scope into keep (dedup, order-preserving) so a collapse loses no content."""
    scope = list(keep.get("in_scope") or [])
    seen = {str(s).lower() for s in scope}
    for s in (drop.get("in_scope") or []):
        if str(s).lower() not in seen:
            scope.append(s)
            seen.add(str(s).lower())
    keep["in_scope"] = scope


def _keeper_score(topic: dict[str, Any]) -> tuple[int, int]:
    """Higher = better keeper when collapsing a duplicate pair: a SUBSTANTIVE topic beats an 'Introduction to X'
    re-orientation, and richer scope beats thin scope. Uses the RAW title (the intro words are stripped from the
    'significant' set, so they must be read off the full title here)."""
    raw = set(_norm_title(topic.get("title")).split())
    not_intro = 0 if (raw & _INTRO_TITLE_WORDS) else 1
    return (not_intro, len(topic.get("in_scope") or []))


def _collapse_near_duplicate_topics(topics_out: list[dict[str, Any]]) -> set:
    """Two TEACHING topics whose titles share a substantial core and differ ONLY by GENERIC words ('TCP
    Congestion Control Algorithms' vs '… Mechanisms', or '… ' vs '… Overview') are the same lesson split by
    synonyms — the learner reads it two/three times. Collapse them: keep the more substantive one (§_keeper_score),
    merge the other's in_scope, drop it. Matches ACROSS topic types (the model splits one concept into a
    concept_intuition + a science_mechanism + a process_walkthrough), EXCEPT a genuine teach-then-code pair (X +
    Implementing X) — that stays two. A real distinguishing word ('Binary Search' vs 'Binary Search Trees') keeps
    them separate, since 'trees' is not generic. Mutates topics_out."""
    teaching = [t for t in topics_out if not _is_opener(t)]
    remove_ids: set = set()
    for i, a in enumerate(teaching):
        if id(a) in remove_ids:
            continue
        for b in teaching[i + 1:]:
            if id(b) in remove_ids or id(a) in remove_ids:
                continue
            types = {str(a.get("topic_type")), str(b.get("topic_type"))}
            if "coding_implementation" in types:
                continue                                    # teach-then-code is a legit complementary pair
            aw, bw = _significant_title_words(a), _significant_title_words(b)
            if not aw or not bw:
                continue
            shared, diff = aw & bw, aw ^ bw                 # symmetric difference: the words that differ
            if len(shared) < 2 or not diff <= _GENERIC_TOPIC_FILLER:
                continue                                    # need a real shared subject; all differences generic
            keep, drop = (a, b) if _keeper_score(a) >= _keeper_score(b) else (b, a)
            _merge_topic_scope(keep, drop)
            remove_ids.add(id(drop))
            _log.info("topic_decomposition: collapsed near-duplicate %r into %r (synonym-only title diff)",
                      drop.get("title"), keep.get("title"))
            record_topic_decision(
                keep, "dedup.near_duplicate_merged", f"absorbed {drop.get('title')!r}",
                "titles shared a substantial subject and differed only by generic filler words "
                "('Mechanisms' / 'Overview' / ...) — the same lesson split by synonyms; the more "
                "substantive topic kept, the other's scope merged in and it was dropped",
                dropped_topic_type=drop.get("topic_type"), shared_words=sorted(shared))
    if remove_ids:
        topics_out[:] = [t for t in topics_out if id(t) not in remove_ids]
    return remove_ids


def _goal_significant_words(goal: str | None) -> set[str]:
    """The goal's distinctive subject words (>=3 chars, minus goal preamble + generic glue)."""
    return {w for w in _norm_title(goal).split()
            if len(w) >= 3 and w not in _GENERIC_PREREQ_WORDS and w not in _INTRO_FILLER}


def _is_goal_umbrella_subject(subject_key: str, gw: set[str]) -> bool:
    """True when a topic's subject IS the goal itself — word-set equality, acronym-aware: one goal word may
    be the initialism of a contiguous run of subject words ('binary_search_tree_traversal' vs goal
    {'bst','traversal'})."""
    words = [w for w in str(subject_key or "").replace("_", " ").split() if w]
    if not words or not gw:
        return False
    if set(words) == gw:
        return True
    for g in gw:
        n = len(g)
        for i in range(len(words) - n + 1):
            if "".join(w[0] for w in words[i:i + n]) == g:
                if set(words[:i] + words[i + n:]) == (gw - {g}):
                    return True
    return False


def _drop_umbrella_coding_topics(topics_out: list[dict[str, Any]], goal: str | None) -> list[str]:
    """Drop a coding_implementation whose subject is the GOAL ITSELF when the path already has >=2 more
    specific implementations (live failure: the model emitted 'Implementing BST Traversal' alongside the
    per-traversal 'Implementing Inorder/Postorder/Preorder Traversal' — the umbrella re-implements what the
    members already cover). Never drops the only implementation. Mutates topics_out; returns dropped titles."""
    gw = _goal_significant_words(goal)
    if not gw:
        return []
    coding = [t for t in topics_out
              if str(t.get("topic_type") or t.get("course_type") or "").strip() == "coding_implementation"]
    umbrellas = [t for t in coding
                 if _is_goal_umbrella_subject(str(t.get("subject_key") or t.get("title") or ""), gw)]
    if not umbrellas or len(coding) - len(umbrellas) < 2:
        return []
    drop_ids = {id(t) for t in umbrellas}
    dropped = [str(t.get("title") or "") for t in umbrellas]
    topics_out[:] = [t for t in topics_out if id(t) not in drop_ids]
    _log.info("topic_decomposition: dropped umbrella goal-subject coding topic(s): %s", dropped)
    return dropped


def _title_initialism(title: str) -> tuple[str, list[str]]:
    """(initialism, significant-ordered-words) of a topic title — 'Binary Search Tree' -> ('bst',
    ['binary','search','tree']). Order-preserving, filler-free, so the initialism matches how learners
    abbreviate the phrase."""
    words = [w for w in _norm_title(title).split() if len(w) >= 3 and w not in _GENERIC_TOPIC_FILLER]
    return "".join(w[0] for w in words), words


def _demote_parent_of_goal_topics(topics_out: list[dict[str, Any]], goal: str | None) -> list[str]:
    """Demote a teaching topic that teaches a STRICT PARENT of the goal to a prerequisite. Two signals:

    1. SUBSET: the topic's significant title words are a proper subset of the goal's, AND the goal adds >=2
       substantive (non-generic) words beyond it — the topic covers the broad parent ('TCP Overview' -> {tcp})
       while the goal is a specific aspect ('tcp congestion control'). The '>=2 substantive' guard protects a
       goal that merely appends a generic qualifier ('gradient descent' under 'gradient descent optimization').
    2. ACRONYM EXPANSION (live failure: a full 'Binary Search Tree' walkthrough on a 'bst traversal' path,
       overlapping the BST prerequisite): the topic's title is the multiword EXPANSION of an acronym the goal
       uses (initialism 'bst' ∈ goal words) and the goal adds >=1 substantive word beyond the acronym. Guard:
       NO other teaching topic shares that acronym subject — on a 'bfs traversal' goal, 'Breadth-First Search'
       IS the subject its siblings implement, never a demotable parent.

    Removes the topic, returns its concept name for the intro's prereq list (structured prereqs — so the
    grounded prereq card + open_study_path link replace the redundant topic; prereqs and taught topics must
    never overlap). Never demotes a goal-matching topic nor the last teaching topic. Mutates topics_out."""
    gw = _goal_significant_words(goal)
    if len(gw) < 2:                                          # single-word/vague goal -> no reliable signal
        return []
    teaching = [t for t in topics_out if not _is_opener(t)]
    demoted, remove_ids = [], set()
    for t in teaching:
        # Strip generic filler BEFORE the subset test — 'TCP Mechanisms' is still the parent 'TCP' (live
        # evasion: the filler word 'mechanisms' broke the subset relation, so the parent topic survived).
        tw = {w for w in _significant_title_words(t) if w not in _GENERIC_TOPIC_FILLER}
        subset_parent = (len(gw) >= 3 and bool(tw) and tw < gw
                         and len({w for w in (gw - tw) if w not in _GENERIC_TOPIC_FILLER}) >= 2)
        acronym_parent = False
        if not subset_parent:
            initialism, words = _title_initialism(str(t.get("title") or ""))
            if (len(words) >= 2 and initialism in gw
                    and {w for w in gw if w != initialism and w not in _GENERIC_TOPIC_FILLER}):
                acronym_parent = not any(
                    initialism in _norm_title(str(o.get("title") or "")).split()
                    or _title_initialism(str(o.get("title") or ""))[0] == initialism
                    for o in teaching if id(o) != id(t))
        # 3. UMBRELLA DISCIPLINE (live: a 'Fluid Dynamics Fundamentals' topic taught on a 'fluid turbulence'
        #    path, while the prereq card independently named the same discipline — prereq/topic overlap from
        #    the learner's view): a topic whose filler-stripped title IS a whole-discipline umbrella, on a
        #    goal that is a more specific aspect of it, is foundation material → prereq, never a lesson.
        umbrella_parent = False
        if not (subset_parent or acronym_parent):
            stripped = [w for w in _norm_title(str(t.get("title") or "")).split()
                        if w not in _GENERIC_TOPIC_FILLER]
            phrase = " ".join(stripped)
            if phrase in _UMBRELLA_FIELDS:
                umbrella_parent = bool({w for w in gw
                                        if w not in set(stripped) and w not in _GENERIC_TOPIC_FILLER})
        if not (subset_parent or acronym_parent or umbrella_parent):
            continue
        # Drop filler AND glue when building the prereq name: _norm_title("to") returns "" (glue-stripped),
        # and "" is not in the filler set — so "Introduction to Fluid Dynamics" once demoted to the malformed
        # prereq "to Fluid Dynamics" whose link read "Understand the basics of to Fluid Dynamics" (live).
        # A word whose normalization is EMPTY is glue and must go too.
        name = " ".join(w for w in str(t.get("title") or "").split()
                        if _norm_title(w) and _norm_title(w) not in _GENERIC_TOPIC_FILLER).strip()
        demoted.append(name or str(t.get("title") or "").strip())
        remove_ids.add(id(t))
        # A demoted subject takes its own coding follow-up with it — 'Binary Search Tree' becoming a prereq
        # must not leave a dangling 'Implementing Binary Search Tree' behind (the learner is ASSUMED to have
        # the concept; its implementation is equally out of scope).
        t_words = {w for w in _norm_title(str(t.get("title") or "")).split()
                   if w not in _GENERIC_TOPIC_FILLER}
        for o in teaching:
            if id(o) in remove_ids:
                continue
            if str(o.get("topic_type") or o.get("course_type") or "").strip() != "coding_implementation":
                continue
            o_words = {w for w in _norm_title(str(o.get("title") or "")).split()
                       if w not in _GENERIC_TOPIC_FILLER and w != "implementing"}
            if o_words == t_words:
                remove_ids.add(id(o))
                demoted_impl = str(o.get("title") or "")
                _log.info("topic_decomposition: dropping companion implementation of demoted prereq: %r",
                          demoted_impl)
    if remove_ids and len(remove_ids) < len(teaching):       # never demote every teaching topic
        topics_out[:] = [t for t in topics_out if id(t) not in remove_ids]
        _log.info("topic_decomposition: demoted parent-of-goal topic(s) to prerequisites: %s", demoted)
        return demoted
    return []


def _topic_teaches_prereq(topic: dict[str, Any], prereq_names: list[str]) -> bool:
    """True when a topic teaches a concept the path also declared an external PREREQUISITE — i.e. the topic's
    title/subject fully contains a declared prereq's significant words ('Implementing Graph Representation'
    teaches the declared 'Graph Representation' prereq)."""
    tw: set[str] = set()
    for field in ("title", "subject_key"):
        tw |= set(_norm_title(topic.get(field)).split())
    for name in prereq_names:
        pw = {w for w in _norm_title(name).split() if len(w) >= 3}
        if pw and pw <= tw:
            return True
    return False


def _fold_prereq_topics(topics_out: list[dict[str, Any]], prereq_names: list[str], goal: str | None) -> list[str]:
    """A concept is EITHER an external prerequisite OR a taught topic — never both. When the LLM declares a
    concept as a prerequisite AND also emits a standalone topic for it ('Graph Representation' prereq + the
    'Implementing Graph Representation' topic on a Dijkstra path), the learner is assumed to have it, so keep the
    PREREQUISITE (external, linked) and REMOVE the redundant topic. Never removes a goal-named topic (in scope)
    nor the last teaching topic. Mutates topics_out in place; returns the removed titles."""
    if not prereq_names:
        return []
    teaching = [t for t in topics_out if not _is_opener(t)]
    remove_ids, removed = set(), []
    for t in teaching:
        if _goal_names_topic(t, goal):
            continue                                    # the goal names it → it stays a taught topic
        if str(t.get("basis") or "") == "goal_requirement":
            continue                                    # a curriculum REQUIREMENT is in-path by definition —
                                                        # a prereq declaration can never fold it away
        if _topic_teaches_prereq(t, prereq_names):
            remove_ids.add(id(t))
            removed.append(str(t.get("title") or ""))
    if remove_ids and len(remove_ids) < len(teaching):  # never fold away every teaching topic
        topics_out[:] = [t for t in topics_out if id(t) not in remove_ids]
        _log.info("topic_decomposition: folded %d prereq-duplicate topic(s) into prereqs: %s", len(removed), removed)
        return removed
    return []


def _repair_topic_title(title: str, subject_key: str) -> str:
    """Repair a title that begins with a dangling preposition/conjunction (an LLM decomposition artifact) by
    stripping the leading run; if that empties it, fall back to the subject phrase. A clean title is unchanged."""
    tokens = str(title or "").split()
    j = 0
    while j < len(tokens) and tokens[j].lower().strip(",.:;") in _LEADING_TITLE_JUNK:
        j += 1
    if j == 0:
        return title
    rest = tokens[j:]
    if not rest:
        return _subject_phrase(subject_key)
    repaired = " ".join(rest)
    return repaired[0].upper() + repaired[1:]


def _to_legacy(topic: dict[str, Any], title_by_id: dict[str, str], fallback_order: int) -> dict[str, Any]:
    """Adapt one decomposed topic into the legacy topic dict the lesson pipeline consumes, carrying the
    planning fields (incl. relationship_to_parent — the Part C signal) for downstream use/audit."""
    edges = topic.get("topic_relationships") or []
    rel = next((str(e.get("relationship")) for e in edges
                if isinstance(e, dict) and e.get("relationship") == IMPLEMENTATION_FOLLOW_UP), None)
    prereq_titles = [title_by_id.get(str(e.get("parent_topic_id")))
                     for e in edges if isinstance(e, dict)]
    prereq_titles = [p for p in prereq_titles if p]

    subject = str(topic.get("subject_key") or "")
    title = str(topic.get("title") or "").strip()
    if not title:  # synthesized follow-ups have no LLM title
        title = (f"Implementing {_subject_phrase(subject)}"
                 if canonical_action(topic.get("primary_action")) == "implement"
                 else _subject_phrase(subject))
    title = _repair_topic_title(title, subject)
    topic_type = str(topic.get("topic_type") or resolve_topic_type(topic.get("content_role")) or "concept_intuition")

    modifiers = list(topic.get("modifiers") or [])
    if rel == IMPLEMENTATION_FOLLOW_UP and IMPLEMENTATION_FOLLOW_UP not in modifiers:
        modifiers.append(IMPLEMENTATION_FOLLOW_UP)

    _incoming_meta = topic.get("decomposition_metadata")
    _carried_meta: dict[str, Any] = {}
    if isinstance(_incoming_meta, dict):
        # carry the intro's structured prereq maps (gloss = what it is; requirement = what you must know
        # about it for this path) so the lean generator can render the two-line prereq bullets.
        for _k in ("assumed_prerequisite_glosses", "assumed_prerequisite_requirements"):
            if _incoming_meta.get(_k):
                _carried_meta[_k] = _incoming_meta[_k]

    return {
        "title": title[:255],
        "purpose": str(topic.get("purpose") or topic.get("primary_capability") or
                       f"Reach the capability: {topic.get('primary_capability') or title}."),
        "learner_outcome": str(topic.get("learner_outcome") or topic.get("primary_capability") or title),
        "unit_title": str(topic.get("unit_title") or "Core Concepts")[:255],
        "topic_type": topic_type,
        "course_type": topic_type,
        "secondary_course_types": [],
        "prerequisite_topics": ", ".join(prereq_titles),
        "assumed_prerequisites": list(topic.get("assumed_prerequisites") or []),
        "source_refs": ", ".join(str(s) for s in (topic.get("source_refs") or [])),
        "in_scope": list(topic.get("in_scope") or []),
        "out_of_scope": list(topic.get("out_of_scope") or []),
        "practice_target": str(topic.get("practice_target") or ""),
        "practice_format": str(topic.get("practice_format") or ""),
        "estimated_minutes": int(topic.get("estimated_minutes") or 10),
        "order_index": int(topic.get("order_index") or fallback_order),
        "modifiers": modifiers,
        # carried planning fields (Part C signal + audit)
        "subject_key": subject,
        "capability_id": str(topic.get("capability_id") or ""),
        "primary_action": str(topic.get("primary_action") or ""),
        "content_role": str(topic.get("content_role") or ""),
        "practice_evidence_type": str(topic.get("practice_evidence_type") or ""),
        "expected_output": str(topic.get("expected_output") or ""),
        "basis": str(topic.get("basis") or "goal"),
        "policy_reason": topic.get("policy_reason"),
        "relationship_to_parent": rel,
        # persisted audit blob (TOPIC_DECOMPOSITION_SPEC.md step 8)
        "decomposition_metadata": {
            "schema_version": 1,
            "subject_key": subject,
            "capability_id": str(topic.get("capability_id") or ""),
            "primary_action": str(topic.get("primary_action") or ""),
            "content_role": str(topic.get("content_role") or ""),
            "practice_evidence_type": str(topic.get("practice_evidence_type") or ""),
            "expected_output": str(topic.get("expected_output") or ""),
            "basis": str(topic.get("basis") or "goal"),
            "policy_reason": topic.get("policy_reason"),
            "relationship_to_parent": rel,
            # carry the intro's structured prereq glosses (name->one-line "what it is") so the lean generator
            # can render "name — gloss" bullets and thread the gloss into the open_study_path popup.
            **_carried_meta,
            # requirements-first audit trail (intro only): what the curriculum call demanded + how each
            # requirement was owned (declared/semantic/False) — without this, a collapse like "one topic
            # claimed everything" is undiagnosable from the persisted path.
            **({"goal_requirements": topic.get("goal_requirements")}
               if topic.get("goal_requirements") else {}),
            # decision trace (this module + topic_generator.py's later certification pass append to the
            # SAME list — take_topic_trace here just moves what accumulated up to this point).
            "decision_trace": take_topic_trace(topic),
            # path-level decisions (opener only) — everything above and outside any single topic's story.
            **({"path_decision_trace": topic.get("path_decision_trace")}
               if topic.get("path_decision_trace") else {}),
        },
    }


def _is_opener(topic: dict[str, Any]) -> bool:
    return (str(topic.get("topic_type") or "") == "study_path_introduction"
            or str(topic.get("content_role") or "").lower() == "orientation")


# capability_ids / subjects a GENUINE orientation topic uses — anything else means the LLM loaded a real
# concept into the intro slot.
_GENERIC_INTRO_IDS = frozenset({"orientation", "study_path_intro", "study_path_introduction",
                                "synth_intro", "overview", "introduction"})


def _is_conflated_intro(topic: dict[str, Any]) -> bool:
    """True when an 'orientation'/study_path_introduction topic is actually a mislabeled CONCEPT — it carries
    a concrete subject + a teaching deliverable (expected_output + a real practice evidence type). The LLM
    sometimes titles the intro after the first concept (e.g. an intro 'Law of Total Probability' that then
    never teaches it), which starves that concept of a worked example and hides that there is no real intro."""
    if not _is_opener(topic):
        return False
    cap = str(topic.get("capability_id") or "").lower()
    subj = str(topic.get("subject_key") or "").lower()
    generic = (not cap) or cap in _GENERIC_INTRO_IDS or subj in _GENERIC_INTRO_IDS
    has_deliverable = (bool(str(topic.get("expected_output") or "").strip())
                       and str(topic.get("practice_evidence_type") or "").strip() not in ("", "none"))
    return (not generic) and has_deliverable


# Leading goal-preamble words stripped when deriving the intro title ("I want to learn about X" -> "X").
_INTRO_FILLER = frozenset({
    "i", "want", "wanna", "would", "like", "wish", "need", "hope", "aim", "trying", "try", "to",
    "learn", "learning", "understand", "understanding", "study", "studying", "know", "knowing",
    "master", "mastering", "explore", "exploring", "review", "reviewing", "about", "more", "get",
})
_TITLE_SMALL_WORDS = frozenset({"and", "or", "of", "the", "a", "an", "to", "for", "in", "on", "with", "by"})


def _intro_title(goal: str | None) -> str:
    """A clean, presentable intro title from a messy goal ('wANT TO LEARN ABOUT bayes...' ->
    'Introduction to Bayes Theorem ...'). Strips leading preamble words and normalizes wild casing."""
    tokens = re.findall(r"[A-Za-z0-9'+#/-]+", str(goal or ""))
    i = 0
    while i < len(tokens) and tokens[i].lower() in _INTRO_FILLER:
        i += 1
    core = tokens[i:]
    if not core:
        return "Introduction & Key Terms"
    titled = " ".join(w.lower() if (j and w.lower() in _TITLE_SMALL_WORDS) else w.capitalize()
                      for j, w in enumerate(core))
    return f"Introduction to {titled}"[:255]


def _path_assumed_prereqs(path_plan: dict[str, Any]) -> tuple[list[str], dict[str, str], dict[str, str]]:
    """Parse path_plan.assumed_prerequisites — the LLM's STRUCTURED external-prerequisite list — into an
    ordered list of clean concept names, a name->gloss map (WHAT IT IS, the one-line refresher), and a
    name->required_knowledge map (what the learner must know about it to follow THIS path). This is the
    source of truth for the intro's prerequisites card and the prerequisite links, replacing prose
    extraction. Tolerates plain strings or {name, gloss, required_knowledge} dicts; dedupes
    case-insensitively; caps at 4 (prereqs are FEW by contract — a flooded list means the model ignored
    the constraint, and the leading entries are the ones it considered most essential)."""
    names: list[str] = []
    glosses: dict[str, str] = {}
    requirements: dict[str, str] = {}
    seen: set[str] = set()
    for item in (path_plan.get("assumed_prerequisites") or []):
        if isinstance(item, str):
            name, gloss, req = item.strip(), "", ""
        elif isinstance(item, dict):
            name = str(item.get("name") or item.get("concept") or item.get("title") or "").strip()
            gloss = str(item.get("gloss") or item.get("description") or "").strip()
            req = str(item.get("required_knowledge") or item.get("requirement") or "").strip()
        else:
            continue
        name = name.strip().strip(".").strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        names.append(name)
        if gloss:
            glosses[name] = gloss
        if req:
            requirements[name] = req
        if len(names) >= 4:
            break
    return names, glosses, requirements


def _synthesize_intro_topic(goal: str | None) -> dict[str, Any]:
    """A lightweight orientation opener (study_path_introduction). Its cards — background, prerequisites
    (named, not taught), shared terms, roadmap — are generated downstream from the blueprint + siblings;
    here we only mint the topic shell so a multi-topic path never starts cold when the LLM omits an intro."""
    return {
        "topic_id": "synth_intro",
        "capability_id": "orientation",
        "title": _intro_title(goal),
        "subject_key": normalize_subject_key(str(goal or "")) or "overview",
        "primary_action": "understand",
        "content_role": "orientation",
        "topic_type": "study_path_introduction",
        "practice_target": "", "practice_format": "", "practice_evidence_type": "", "expected_output": "",
        "in_scope": [], "out_of_scope": [],
        "basis": "goal",
        "estimated_minutes": 8,
        "purpose": ("Orient the learner: frame the area, name the assumed prerequisites (without teaching "
                    "them), define the shared terms, and preview the topics ahead."),
        "topic_relationships": [],
        "provenance": {"synthesized": True, "reason": "intro_guarantee"},
    }


def _goal_requirements(goal: str | None, chunks_text: str, fn: ModelFn, feedback: str | None = None
                       ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    """The REQUIREMENTS-FIRST call (curriculum-authority design): decide WHAT the path must cover BEFORE any
    topic exists, in a dedicated frame. Returns (requirements, assumed_prerequisites) — the curriculum call
    also owns the EXTERNAL prerequisites (what the course assumes vs teaches is one curriculum decision; the
    decomposition model dropped assumed_prerequisites on 4 of 5 live regens once requirements landed).
    Requirements are injected into the decomposition prompt as authoritative and checked deterministically
    afterward (an unowned core requirement flows into the B.4.1 coverage repair). Kill switch:
    AZALEA_GOAL_REQUIREMENTS=0. Best-effort — a failed call means decomposition proceeds exactly as before.

    PLAN PERSISTENCE (scope-plan #3, app/services/goal_plan_cache.py): a fresh, no-feedback call for a goal
    already cached reuses that curriculum instead of re-rolling — the requirements call is the single
    biggest driver of topic-count variance across identical goals. `feedback` present means the learner is
    actively asking for something different than what shipped, so it BYPASSES the cache read (a stale
    curriculum must never override explicit intent) but a successful call still WRITES the cache — a
    feedback-informed result is the improved canonical curriculum going forward, not a one-off.

    Third return value is the SOURCE, for the caller's decision trace: "disabled" | "cache_hit" |
    "fresh_call" | "fresh_call_feedback" | "empty" | "failed"."""
    if os.getenv("AZALEA_GOAL_REQUIREMENTS", "") == "0":
        return [], [], "disabled"
    has_feedback = bool(feedback and feedback.strip())
    if not has_feedback:
        from app.services.goal_plan_cache import lookup_cached_plan, record_cache_hit
        cached = lookup_cached_plan(goal)
        if cached is not None:
            record_cache_hit(goal)
            _log.info("goal requirements: reused cached curriculum for goal %r (%d requirements)",
                      goal, len(cached["requirements"]))
            return cached["requirements"], cached["assumed_prerequisites"], "cache_hit"
    try:
        payload = {"system": REQUIREMENTS_SYSTEM_PROMPT,
                   "user": build_goal_requirements_prompt(goal, chunks_text)}
        parsed = _coerce(fn(payload))
        reqs: list[dict[str, Any]] = []
        for i, r in enumerate(parsed.get("requirements") or []):
            if not isinstance(r, dict):
                continue
            statement = " ".join(str(r.get("statement") or "").split()).strip()
            if not statement:
                continue
            rid = str(r.get("requirement_id") or "").strip() or f"R{i + 1}"
            kind = str(r.get("kind") or "core").strip().lower()
            reqs.append({"requirement_id": rid,
                         "name": " ".join(str(r.get("name") or "").split()).strip(),
                         "statement": statement,
                         "kind": kind if kind in ("core", "supporting") else "core"})
        prereqs: list[dict[str, Any]] = []
        for p in (parsed.get("assumed_prerequisites") or []):
            if isinstance(p, dict) and str(p.get("name") or "").strip():
                prereqs.append({"name": str(p["name"]).strip(),
                                "gloss": str(p.get("gloss") or "").strip(),
                                "required_knowledge": str(p.get("required_knowledge") or "").strip()})
        reqs, prereqs = reqs[:8], prereqs[:3]
        if reqs:
            _log.info("goal requirements: %d requirements for goal %r: %s (prereqs: %s)", len(reqs), goal,
                      [r["requirement_id"] for r in reqs], [p["name"] for p in prereqs])
            from app.services.goal_plan_cache import store_plan
            store_plan(goal, reqs, prereqs)
        return reqs, prereqs, ("fresh_call_feedback" if has_feedback else "fresh_call") if reqs else "empty"
    except Exception:  # noqa: BLE001 — requirements are additive; never block decomposition
        _log.info("goal requirements call failed for goal %r — decomposing without requirements", goal)
        return [], [], "failed"


_REQ_STOPWORDS = frozenset({
    "the", "a", "an", "of", "in", "on", "to", "and", "or", "for", "with", "from", "into", "across",
    "between", "before", "after", "it", "its", "their", "how", "what", "why", "when", "such", "as",
    "is", "are", "be", "can", "may", "removes", "remove", "them",
    # requirement-statement verbs — they describe the ASK, not the content
    "describe", "explain", "distinguish", "identify", "connect", "understand", "define", "apply",
})


def _req_tokens(text: str) -> set[str]:
    """Content tokens for semantic requirement/scope matching: lowercase alnum words minus stopwords, with a
    crude plural strip so 'transfers'/'eddies' meet 'transfer'/'eddy' forms from the other side."""
    out: set[str] = set()
    for w in re.findall(r"[a-z0-9]+", str(text or "").lower()):
        if w in _REQ_STOPWORDS or len(w) < 3:
            continue
        for suf in ("ies", "es", "s"):
            if w.endswith(suf) and len(w) - len(suf) >= 3:
                w = w[: -len(suf)] + ("y" if suf == "ies" else "")
                break
        out.add(w)
    return out


def _requirement_covered_by_topics(req: dict[str, Any], raw_topics: list[dict[str, Any]]) -> bool:
    """SEMANTIC ownership: a requirement is covered when a topic's title + scope actually carries its content.
    Used two ways: as the fallback when the model forgot the requirement ID (live: 'Energy Transfer in
    Turbulent Flows' fully covered the energy-cascade requirement, but ID-only checking synthesized a
    duplicate on top of it), and as VERIFICATION of a declared covers_requirements claim (live: the model
    claimed everything on one topic and the path collapsed — a declaration is a signal, not proof).
    Deterministic token overlap — ≥3 shared content tokens, or near-full containment of a short requirement.

    KNOWN LIMITATION (documented, not fixed — the fix attempted here regressed the family-survey system and
    was reverted): a topic whose OWN distinctive identity is short (e.g. 'Reynolds Number' -> {reynold,
    number}) can miss coverage of a longer, differently-phrased requirement by one token (live: 'explain key
    quantities such as Reynolds number and their physical significance in characterizing turbulence' shared
    only {reynold, number} with the 'Reynolds Number' topic — one token short of the ≥3 threshold — so a
    duplicate 'Governing quantities of turbulence' topic was synthesized on top of it). A symmetric
    'topic's own short title fully contained in the requirement' rule was tried and reverted: 'order'/
    'traversal' are GENERIC family vocabulary once a distinguishing prefix like 'in'/'pre' is stripped by
    the <4-char token filter, so the same rule let 'In-Order Traversal' falsely claim coverage of the
    'Pre-order traversal' requirement — and unlike the Reynolds case, sibling family members may not even be
    assembled yet at this point in the pipeline, so an in-list uniqueness check is not a reliable guard.
    Fixing the Reynolds-class miss needs real semantic matching (a concept-contract layer), not a token
    heuristic broad enough to also catch it safely."""
    rt = _req_tokens(f"{req.get('name') or ''} {req.get('statement') or ''}")
    if not rt:
        return False
    for t in raw_topics:
        tt = _req_tokens(" ".join([str(t.get("title") or ""), str(t.get("subject_key") or ""),
                                   *[str(s) for s in (t.get("in_scope") or [])]]))
        overlap = rt & tt
        if len(overlap) >= 3 or (len(rt) <= 3 and len(overlap) >= 2):
            return True
    return False


def _enforce_requirement_coverage(path_plan: dict[str, Any], raw_topics: list[dict[str, Any]],
                                  requirements: list[dict[str, Any]]) -> None:
    """Deterministic requirement-coverage check (the anti-self-referential validator): a core requirement no
    topic claims via covers_requirements becomes a REQUIRED standalone capability in the path plan, so the
    existing B.4.1 coverage repair synthesizes a topic for it. Mutates path_plan in place; also records the
    requirements + ownership for telemetry/audit."""
    if not requirements:
        return
    declared: dict[str, list[dict[str, Any]]] = {}
    for t in raw_topics:
        for rid in (t.get("covers_requirements") or []):
            declared.setdefault(str(rid).strip(), []).append(t)
    caps = path_plan.setdefault("required_capabilities", [])
    cap_ids = {str(c.get("capability_id")) for c in caps if isinstance(c, dict)}
    unowned: list[str] = []
    for r in requirements:
        rid = r["requirement_id"]
        declaring = declared.get(rid) or []
        if declaring and _requirement_covered_by_topics(r, declaring):
            r["owned"] = "declared"
            for dt in declaring:
                record_topic_decision(dt, "requirement.claim_verified", f"owns {rid}",
                                      "declared this requirement via covers_requirements, and its own "
                                      "title/scope semantically carries the requirement's content",
                                      requirement=r.get("name") or rid)
        elif _requirement_covered_by_topics(r, raw_topics):
            # covers the forgot-the-ID case AND the declared-but-by-the-wrong-topic case — some topic's
            # scope genuinely carries the content, so never synthesize a duplicate on top of it
            r["owned"] = "semantic"
            _log.info("goal requirements: %s covered semantically by an existing topic's scope", rid)
        else:
            if declaring:
                _log.info("goal requirements: %s DECLARED by %r but the topic's scope does not carry it — "
                          "treating as unowned (a declaration is a signal, not proof)",
                          rid, str(declaring[0].get("title") or "?"))
                for dt in declaring:
                    record_topic_decision(dt, "requirement.claim_rejected", f"claim of {rid} not honored",
                                          "declared this requirement via covers_requirements, but its "
                                          "own title/scope does not semantically carry the content — a "
                                          "declaration is a signal, not proof, so the requirement is "
                                          "still treated as unowned", requirement=r.get("name") or rid)
            r["owned"] = False
        if r["owned"] or r.get("kind") != "core":
            continue
        unowned.append(rid)
        cid = f"goal_req_{rid.lower()}"
        if cid in cap_ids:
            continue
        subject_source = r.get("name") or r["statement"]
        # Content-role inference: a quantitative requirement ("physical meaning of the Reynolds number")
        # synthesized as concept_intuition gets a 4-card overview blueprint, is NOT worked-example-centric,
        # and can never claim its own adapter (live: the Reynolds example drifted to Energy Cascade while
        # the synthesized Reynolds topic shipped with no formula and no example). Infer from the statement.
        rt = _req_tokens(f"{r.get('name') or ''} {r['statement']}")
        if rt & {"number", "law", "equation", "formula", "ratio", "coefficient", "criterion",
                 "calculate", "compute", "quantity"}:
            role = "calculation"
        elif rt & {"mechanism", "process", "cascade", "transfer", "cause", "effect", "dynamic",
                   "interaction", "dissipation"}:
            role = "mechanism"
        else:
            role = "concept_intuition"
        caps.append({
            "capability_id": cid,
            "subject_key": normalize_subject_key(subject_source),
            "primary_capability": (r.get("name") or r["statement"])[:120],
            "description": r["statement"],
            "content_role": role,
            "ownership_mode": "standalone",
            "owner_topic_id": None,
            "prerequisite_capability_ids": [],
            "satisfies_end_actions": [],
            "basis": "goal_requirement",
            "policy_reason": "unowned_goal_requirement",
        })
    path_plan["goal_requirements"] = requirements
    owned_by = {"declared": [], "semantic": [], False: []}
    for r in requirements:
        owned_by.setdefault(r["owned"], []).append(r["requirement_id"])
    record_path_decision(
        path_plan, "requirement.coverage_check",
        f"{len(owned_by['declared'])} declared+verified, {len(owned_by['semantic'])} semantic, "
        f"{len(owned_by[False])} unowned",
        "every requirement's covers_requirements claim is checked against the declaring topic's actual "
        "scope (not trusted at face value); an unowned CORE requirement becomes a required capability so "
        "the B.4.1 coverage repair synthesizes a topic for it",
        declared=owned_by["declared"] or None, semantic=owned_by["semantic"] or None,
        unowned=owned_by[False] or None)
    if unowned:
        _log.info("goal requirements: %s unowned by any topic — appended as required capabilities "
                  "(coverage repair will synthesize topics)", unowned)


def _retry_thin_plan(parsed: dict[str, Any], raw_topics: list[dict[str, Any]], goal: str | None,
                     chunks_text: str, feedback: str | None, fn: ModelFn,
                     goal_requirements: list[dict[str, Any]] | None = None,
                     ) -> tuple[dict[str, Any], list[dict[str, Any]], Optional[str]]:
    """One bounded re-ask when the model returned a SINGLE teaching topic that itself claims several distinct
    content commitments — the signature of an undecomposed area goal (live: 'fluid turbulence' came back as one
    concept_intuition topic whose in_scope listed characteristics + causes + laminar-vs-turbulent; regens of the
    same goal shrank 3 → 2 → 1 topics). A single-topic plan whose topic carries 0-1 commitments is a legitimate
    narrow-technique goal and is NEVER retried. The retry is accepted only when it comes back strictly richer;
    otherwise the original plan stands. Costs at most one extra decomposition call, only on thin plans.

    Third return value is the retry OUTCOME for the caller's decision trace: None (not attempted — the plan
    wasn't thin), "expanded" (adopted a richer plan), "stayed_thin" (retried, model still returned one
    topic), or "failed" (the retry call itself raised)."""
    teaching = [t for t in raw_topics
                if str(t.get("topic_type") or "") != "study_path_introduction"]
    if len(teaching) != 1 or len(list(teaching[0].get("in_scope") or [])) < 2:
        return parsed, raw_topics, None
    t = teaching[0]
    commitments = "; ".join(str(s) for s in (t.get("in_scope") or []))
    thin_note = (
        "YOUR PREVIOUS PLAN WAS TOO THIN: it had a single teaching topic "
        f"({str(t.get('title') or t.get('subject_key') or 'the topic')!r}) that itself claims several distinct "
        f"content commitments ({commitments}). A goal naming an AREA or PHENOMENON must be DECOMPOSED: each "
        "commitment a course would teach as its own unit — a mechanism, a governing quantity or criterion, a "
        "regime comparison, a model or method — becomes its OWN topic with its own in_scope. Return a single "
        "teaching topic ONLY if the goal is genuinely one narrow technique with one deliverable. Regenerate "
        "the complete plan now."
    )
    combined = f"{feedback.strip()}\n\n{thin_note}" if feedback and feedback.strip() else thin_note
    try:
        payload = {"system": SYSTEM_PROMPT,
                   "user": build_decomposition_prompt(goal=goal, chunks_text=chunks_text, feedback=combined,
                                                      goal_requirements=goal_requirements)}
        parsed2 = _coerce(fn(payload))
        raw2 = [x for x in (parsed2.get("topics") or []) if isinstance(x, dict)]
        teaching2 = [x for x in raw2 if str(x.get("topic_type") or "") != "study_path_introduction"]
        if len(teaching2) > 1:
            _log.info("thin-plan retry: expanded %d -> %d teaching topics for goal %r",
                      len(teaching), len(teaching2), goal)
            return parsed2, raw2, "expanded"
        _log.info("thin-plan retry: model kept a single teaching topic for goal %r — accepting original", goal)
    except Exception:  # noqa: BLE001 — the retry is best-effort; the original plan is always usable
        _log.info("thin-plan retry failed for goal %r — accepting original plan", goal)
        return parsed, raw_topics, "failed"
    return parsed, raw_topics, "stayed_thin"


def generate_decomposed_topics(
    goal: str | None,
    chunks_text: str,
    feedback: str | None = None,
    *,
    model_fn: Optional[ModelFn] = None,
    resolve_overlap: Optional[OverlapResolver] = None,
    coding_follow_ups: bool = True,
) -> list[dict[str, Any]]:
    """Single-call decompose -> append coding follow-ups -> validate -> adapt to legacy topics.
    Returns [] when the model produced nothing usable (caller falls back to the legacy generator).
    `coding_follow_ups=False` (non-coding domains) skips the 'Implementing X' follow-up append."""
    fn = model_fn or _default_model_fn
    # REQUIREMENTS FIRST (curriculum authority): decide WHAT must be covered before any topic exists, then
    # decompose AGAINST those requirements. Best-effort: [] keeps the old single-call behavior exactly.
    requirements, req_prereqs, _req_source = _goal_requirements(goal, chunks_text, fn, feedback=feedback)
    payload = {"system": SYSTEM_PROMPT,
               "user": build_decomposition_prompt(goal=goal, chunks_text=chunks_text, feedback=feedback,
                                                  goal_requirements=requirements)}
    parsed = _coerce(fn(payload))
    raw_topics = [t for t in (parsed.get("topics") or []) if isinstance(t, dict)]
    if not raw_topics:
        return []
    _topics_before_retry = len(raw_topics)
    parsed, raw_topics, _retry_outcome = _retry_thin_plan(parsed, raw_topics, goal, chunks_text, feedback, fn,
                                                           goal_requirements=requirements)

    path_plan = parsed.get("path_plan") if isinstance(parsed.get("path_plan"), dict) else {}
    path_plan.setdefault("required_capabilities", [])
    path_plan.setdefault("end_capability_actions", [])

    # Curriculum-call outcome, recorded now that path_plan exists to hold it (the call itself ran before).
    _req_source_reason = {
        "cache_hit": "a PRIOR generation's curriculum for this same goal was reused instead of re-rolling "
            "the requirements call — the single biggest source of topic-count variance across identical "
            "goals (scope-plan #3, app/services/goal_plan_cache.py)",
        "fresh_call": "a dedicated call decides WHAT the path must cover before any topic exists — no "
            "cached curriculum existed for this goal, so a fresh call ran and its result was cached",
        "fresh_call_feedback": "the learner supplied regeneration feedback, which bypasses any cached "
            "curriculum (explicit intent must never be overridden by a stale plan) — the fresh, feedback-"
            "informed result becomes the new cached curriculum for this goal going forward",
        "disabled": "AZALEA_GOAL_REQUIREMENTS=0 — decomposition proceeds exactly as it did before requirements-first",
        "empty": "the call ran but produced no usable requirements (empty/malformed response)",
        "failed": "the call raised — decomposition proceeds without curriculum requirements",
    }.get(_req_source, "a dedicated call decides WHAT the path must cover before any topic exists")
    record_path_decision(
        path_plan, "curriculum.requirements_call",
        f"{len(requirements)} requirement(s), {len(req_prereqs)} external prerequisite(s) [{_req_source}]"
        if requirements else f"no requirements produced [{_req_source}]",
        _req_source_reason,
        requirement_ids=[r["requirement_id"] for r in requirements] or None,
        prerequisite_names=[p["name"] for p in req_prereqs] or None)
    if _retry_outcome is not None:
        record_path_decision(
            path_plan, "curriculum.thin_plan_retry", _retry_outcome,
            "the pre-retry plan had a single teaching topic claiming multiple distinct content "
            "commitments — an undecomposed area goal — so the model was re-asked once with those "
            "commitments named; a richer result is adopted only if it strictly expanded",
            raw_topics_before=_topics_before_retry, raw_topics_after=len(raw_topics))

    # Deterministic requirement coverage: an unowned CORE requirement becomes a required capability, so the
    # validator's B.4.1 coverage repair synthesizes a topic for it — the validator now checks the plan against
    # requirements decided BEFORE the topics, not against the topic list's own claims.
    _enforce_requirement_coverage(path_plan, raw_topics, requirements)
    # Prereq authority fallback: when the decomposition dropped assumed_prerequisites (live: 4 of 5 regens
    # since requirements landed), the CURRICULUM call's prerequisites stand in — same structured shape
    # (name/gloss/required_knowledge), same downstream filters (circular/umbrella/taught-overlap all apply).
    if req_prereqs and not (path_plan.get("assumed_prerequisites") or []):
        path_plan["assumed_prerequisites"] = req_prereqs
        _log.info("goal requirements: decomposition emitted no assumed_prerequisites — using the "
                  "curriculum call's: %s", [p["name"] for p in req_prereqs])
        record_path_decision(path_plan, "curriculum.prereq_fallback",
                             f"used the curriculum call's {len(req_prereqs)} prerequisite(s)",
                             "the decomposition call dropped assumed_prerequisites entirely — the "
                             "curriculum call's own list stands in rather than shipping the path with no "
                             "named prerequisites")

    topics = [_normalize_topic(t) for t in raw_topics]
    path_plan, topics = append_coding_follow_ups(path_plan, topics, enabled=coding_follow_ups)
    resolver = resolve_overlap if resolve_overlap is not None else _default_resolver()
    result = validate_topic_decomposition(path_plan, topics, goal or "", resolve_overlap=resolver)
    if not result.ok:
        _log.info("topic_decomposition: validator flagged %d issues: %s",
                  len(result.actions), [a.detail for a in result.actions if a.outcome == "FLAG"][:5])

    # Intro guarantee — a multi-topic path ALWAYS opens with a lightweight orientation topic. The LLM
    # does not reliably emit one (and the validator stays pure), so synthesize it here when missing;
    # order_index 0 puts it ahead of the validated topics before the renumber below.
    topics_out = list(result.topics)
    # SYNTHESIZED-VS-REAL DUPLICATE: B.4.1 coverage repair (validate_topic_decomposition, just above)
    # synthesizes a standalone topic from a requirement's own text whenever the requirement's token-overlap
    # coverage check fails against every existing topic — including a REAL, non-foundation topic the model
    # itself authored, when that topic's own identity is short relative to the requirement's longer phrasing
    # (the SAME documented _requirement_covered_by_topics limitation as the foundation-fold guard below, just
    # without a foundation tag involved). Live: the model wrote a genuine 'Explaining the Reynolds Number'
    # topic (verified adapter, real formula, real worked example) that shares only {reynolds, number} with
    # R2's longer phrasing — one token short of >=3 — so B.4.1 ALSO synthesized 'Governing quantities of
    # turbulence' on top of it: two topics teaching the identical concept, the synthesized one carrying an
    # INCORRECT formula (missing density entirely) with no verified adapter behind it. Prefer the real,
    # richer topic — drop the synthesized twin (topic-vs-topic comparison, not a broadened general heuristic,
    # for the same regression-avoidance reason as the foundation-fold guard).
    def _topic_identity_tokens(t: dict[str, Any]) -> set[str]:
        # Deliberately EXCLUDES title: a title is often narrative/descriptive prose that picks up the
        # path's own domain-wide vocabulary in passing (live regression caught by
        # test_declared_claim_without_content_is_not_ownership: 'Energy Transfer in Turbulent Flows' is
        # not ABOUT flow regimes, but its title's incidental "Turbulent Flows" matched a synthesized 'Flow
        # regimes' topic well enough to look redundant). subject_key (the topic's deliberate canonical
        # identity) and in_scope (its deliberate content commitment — for a synthesized topic, this IS the
        # source requirement's full statement) are the intentional signals; title is not.
        return _req_tokens(" ".join([str(t.get("subject_key") or ""),
                                     *[str(x) for x in (t.get("in_scope") or [])]]))

    # A word repeated across MULTIPLE core requirements is FAMILY vocabulary, not evidence two specific
    # topics are the same concept (live regression: 'In-order traversal' / 'Pre-order traversal' both say
    # "order"/"traversal"/"algorithm" — every family-survey member would falsely match every other member's
    # synthesized sibling on those words alone). Excluded from the overlap count below.
    _requirement_word_counts: dict[str, int] = {}
    for r in requirements:
        for w in _req_tokens(f"{r.get('name') or ''} {r.get('statement') or ''}"):
            _requirement_word_counts[w] = _requirement_word_counts.get(w, 0) + 1
    _cross_requirement_generic = {w for w, c in _requirement_word_counts.items() if c > 1}

    _synthesized = [t for t in topics_out if str(t.get("basis") or "") == "goal_requirement"]
    if _synthesized:
        _synthesized_ids = {id(t) for t in _synthesized}
        # A foundation-role topic must NEVER be treated as the "real topic to keep" here — the guard below
        # (CORE-REQUIREMENT SHIELD / adapter-identity fold) already decides whether a foundation topic wins
        # over a synthesized sibling, in the OPPOSITE direction (drop the foundation topic, keep the
        # synthesized one). Comparing against foundation topics here would race that logic and could drop
        # the synthesized topic first, leaving only a foundation topic that then gets folded into a
        # misleading "go learn this elsewhere" prerequisite with nothing left actually teaching it.
        _non_synthesized = [t for t in topics_out if id(t) not in _synthesized_ids
                            and str(t.get("content_role") or "").lower() != "foundation"]
        # >=2 tokens, not the general >=3: both sides of THIS comparison are typically short, concrete topic
        # identities (not open-ended requirement phrasing), so 2 shared distinctive tokens (e.g. {reynold,
        # number}) is reliable signal here — deliberately NOT reusing _requirement_covered_by_topics's >=3
        # threshold, which requires the SHORT side to be <=3 tokens total; a synthesized topic's in_scope
        # embeds the requirement's full (long) statement, so neither side alone was ever short enough to
        # trigger that function's own short-topic exception.
        _redundant_synthesized = [
            s for s in _synthesized
            if any(len((_topic_identity_tokens(s) & _topic_identity_tokens(r)) - _cross_requirement_generic)
                   >= 2 for r in _non_synthesized)
        ]
        if _redundant_synthesized:
            drop_ids = {id(t) for t in _redundant_synthesized}
            topics_out = [t for t in topics_out if id(t) not in drop_ids]
            record_path_decision(
                path_plan, "topics.synthesized_dropped_redundant_with_real_topic",
                f"dropped {[str(t.get('title')) for t in _redundant_synthesized]}",
                "B.4.1 coverage repair synthesized these because the requirement's token-overlap coverage "
                "check missed an existing REAL topic that already teaches the identical concept (the same "
                "short-identity limitation as the foundation-fold guard, here without a foundation tag) — "
                "the real topic is richer (may carry a verified adapter/formula) and preferred over the "
                "generic synthesized stub, so the duplicate is dropped rather than shipping both")
    # De-conflate: an 'orientation' topic the LLM actually loaded with a concrete concept is a mislabeled
    # teaching topic — restore its teaching type so the concept is TAUGHT (worked example + adapter), which
    # also frees the intro slot so a real generic orientation topic is synthesized below.
    opener_seen = False
    for t in topics_out:
        if _is_conflated_intro(t):
            t["topic_type"] = "math_formula_method"       # domain gate remaps for non-math paths
            t["content_role"] = "calculation"
            _log.info("topic_decomposition: de-conflated mislabeled intro %r -> teaching topic", t.get("title"))
            record_topic_decision(t, "opener.deconflated", "topic_type -> math_formula_method (teaching)",
                                  "tagged as an orientation opener but loaded with a concrete concept — "
                                  "restored to a taught type so the concept gets a worked example and an "
                                  "adapter, and the real intro slot is freed")
        elif _is_opener(t):
            if not opener_seen:
                opener_seen = True
                if str(t.get("topic_type") or "") != "study_path_introduction":
                    # A GENUINE orientation opener mistyped as a teaching type (live: 'Understanding
                    # Depreciation' as concept_intuition) consumes the intro slot while carrying a blueprint
                    # with NO prerequisites card and NO roadmap. Retype it to the real intro.
                    t["topic_type"] = "study_path_introduction"
                    _log.info("topic_decomposition: retyped orientation opener %r -> study_path_introduction",
                              t.get("title"))
                    record_topic_decision(t, "opener.retyped", "topic_type -> study_path_introduction",
                                          "genuinely orientation-role content mistyped as a teaching type — "
                                          "would otherwise carry a blueprint with no prerequisites card and "
                                          "no roadmap")
                # An opener titled with a whole-DISCIPLINE umbrella orients the WRONG subject (live: a
                # 'fluid turbulence' path opened with an intro titled 'Fluid Dynamics' whose background card
                # was 'Why Fluid Dynamics Matters'). The intro's title is the GOAL's, not the parent field's.
                stripped_title = " ".join(w for w in _norm_title(str(t.get("title") or "")).split()
                                          if w not in _GENERIC_TOPIC_FILLER)
                if stripped_title in _UMBRELLA_FIELDS:
                    new_title = _intro_title(goal)
                    _log.info("topic_decomposition: retitled umbrella-named intro %r -> %r",
                              t.get("title"), new_title)
                    record_topic_decision(t, "opener.retitled", f"title -> {new_title!r}",
                                          "the opener was titled after the whole parent DISCIPLINE, so the "
                                          "path appeared to orient the wrong subject — retitled from the goal",
                                          old_title=t.get("title"))
                    t["title"] = new_title
            else:
                # ONE path, ONE orientation: a SECOND orientation-role topic is a mislabeled teaching topic
                # by construction (live: 'Characteristics of Turbulent Flow' also role=orientation — both got
                # intro blueprints, so the learner saw TWO prerequisites cards and TWO roadmaps, and real
                # teaching content was trapped in a blueprint that cannot hold a worked example).
                t["topic_type"] = "math_formula_method"   # domain gate remaps for non-math paths
                t["content_role"] = "calculation"
                _log.info("topic_decomposition: retyped EXTRA orientation topic %r -> teaching topic",
                          t.get("title"))
                record_topic_decision(t, "opener.extra_retyped", "topic_type -> math_formula_method (teaching)",
                                      "a path has exactly ONE orientation topic; this was a second one, so "
                                      "it was a mislabeled teaching topic trapped in a blueprint with no "
                                      "worked-example slot")

    # Prerequisites are NAMED, not taught: a `foundation`-role topic is a building block the learner is
    # assumed to have. When the path also has a real (non-foundation) concept topic, drop the foundation
    # topics and carry them as ASSUMED PREREQUISITES on the intro — mentioned in its prerequisites card,
    # never a standalone teaching topic. If EVERY teaching topic is foundation, keep them (the goal IS that
    # foundation).
    def _role(t: dict[str, Any]) -> str:
        return str(t.get("content_role") or "").lower()

    # A concept the GOAL explicitly names is IN scope — it must stay a taught topic, never be demoted to an
    # external prerequisite (§3.1 rule 1). E.g. goal "…and law of total probability" → Law of Total Probability
    # is a topic, not a prereq link. Same for a CIRCULAR foundation whose title is just the goal subject in
    # generic wrapping ("Combinatorial Principles" on a combinatorial-analysis path) — folding it would turn
    # the path's own first units into a self-referencing prereq link (live failure: the path collapsed to
    # Binomial+Applications with everything else "assumed"). Both stay taught.
    # ADAPTER-IDENTITY GUARD: the model's own content_role tag is not the last word — a topic it tagged
    # "foundation" can still be the EXACT concept a kept real-concept topic's verified worked example is
    # about (live: the model tagged 'Reynolds Number' foundation, then 'Flow Regimes' got the Reynolds
    # adapter and taught the full formula/worked-example/interpretation — so the intro told the learner to
    # go learn Reynolds number on a SEPARATE path first, then the very next topic taught it from scratch).
    # A foundation topic whose title routes to the SAME adapter as a kept topic is not external background;
    # it is content this path is about to teach — exclude it from folding (the same-adapter dedup pass
    # downstream then collapses it as a genuine duplicate, same as any other same-adapter pair).
    def _adapter_slug(t: dict[str, Any]) -> str | None:
        try:
            from app.services.examples.trace_pipeline import route_adapter
            a = route_adapter({"title": str(t.get("title") or ""),
                               "subject_key": str(t.get("subject_key") or ""),
                               "topic_type": str(t.get("topic_type") or "")})
            return getattr(a, "slug", None)
        except Exception:  # noqa: BLE001 — routing must never break decomposition
            return None

    foundations = [t for t in topics_out
                   if not _is_opener(t) and _role(t) == "foundation" and not _goal_names_topic(t, goal)
                   and not _is_circular_prereq(str(t.get("title") or t.get("subject_key") or ""), goal)]
    real_concepts = [t for t in topics_out if not _is_opener(t) and _role(t) != "foundation"]
    real_concept_adapters = {s for s in (_adapter_slug(t) for t in real_concepts) if s}
    _redundant_by_adapter = [t for t in foundations if _adapter_slug(t) in real_concept_adapters]
    if _redundant_by_adapter:
        # DROP entirely — neither folded to an external prereq NOR kept as its own topic. Concept identity is
        # intentionally adapter-INDEPENDENT (a broad topic must never be renamed after one narrow formula), so
        # this survives as a separate topic with no title/token overlap with its sibling and never gets caught
        # by the later same-adapter/near-duplicate dedup passes (concept_intuition isn't WE-centric) — verified
        # empirically. Its content is fully subsumed by the sibling's adapter-grounded worked example.
        drop_ids = {id(t) for t in _redundant_by_adapter}
        topics_out = [t for t in topics_out if id(t) not in drop_ids]
        foundations = [t for t in foundations if t not in _redundant_by_adapter]
        record_path_decision(
            path_plan, "topics.foundation_dropped_redundant_with_adapter",
            f"dropped {[str(t.get('title')) for t in _redundant_by_adapter]}",
            "the model tagged these content_role=foundation, but they route to the SAME adapter as a kept "
            "teaching topic — that topic's worked example already teaches this exact concept in full "
            "(formula, calculation, interpretation), so this is neither external prerequisite material "
            "(it would tell the learner to 'go learn X first' right before X is taught from scratch) nor "
            "a needed standalone topic — dropped rather than folded or kept")
    # REDUNDANT-WITH-SYNTHESIZED-COVERAGE: validate_topic_decomposition's B.4.1 repair (which ran BEFORE this
    # fold) synthesizes a standalone topic straight from a core requirement's own text whenever nothing in the
    # model's plan covers it — including a foundation topic whose identity is too SHORT to pass the coverage
    # check's token-overlap threshold (documented limitation on _requirement_covered_by_topics: 'Understanding
    # Reynolds Number' shares only {reynolds, number} with R2's longer phrasing, one token short of ≥3). The
    # requirement then looks "unowned", B.4.1 synthesizes 'Governing quantities of turbulence' to cover it, and
    # the CORE-REQUIREMENT SHIELD below sees R2 already covered by that SURVIVOR — so it never protects the
    # foundation topic either. Net result: the same concept both gets folded into "go learn this externally"
    # AND taught fresh by the synthesized sibling (live: exactly this Reynolds-number pair). Catch it directly
    # — topic vs topic, not the general topic-vs-requirement heuristic that regressed family surveys when
    # broadened — by checking each foundation topic's own (short) identity against each synthesized topic's
    # full identity (which embeds the requirement's full text as its in_scope, so the overlap is reliable).
    _synthesized_survivor_ids = {id(t) for t in foundations}
    _synthesized_survivors = [t for t in topics_out
                              if id(t) not in _synthesized_survivor_ids
                              and str(t.get("basis") or "") == "goal_requirement"]
    if _synthesized_survivors:
        _redundant_by_synthesis = [
            f for f in foundations
            if _requirement_covered_by_topics(
                {"name": f.get("title"), "statement": f.get("subject_key") or ""}, _synthesized_survivors)
        ]
        if _redundant_by_synthesis:
            drop_ids = {id(t) for t in _redundant_by_synthesis}
            topics_out = [t for t in topics_out if id(t) not in drop_ids]
            foundations = [t for t in foundations if id(t) not in drop_ids]
            record_path_decision(
                path_plan, "topics.foundation_dropped_redundant_with_synthesized_coverage",
                f"dropped {[str(t.get('title')) for t in _redundant_by_synthesis]}",
                "the model tagged these content_role=foundation, but a required-capability coverage-repair "
                "topic was synthesized for the exact same concept (the requirement's own text this topic "
                "was built from overlaps this foundation topic's identity) — folding it as an EXTERNAL "
                "prerequisite while a synthesized sibling teaches the same concept in the path would tell "
                "the learner to go learn it elsewhere right before teaching it fresh; dropped rather than "
                "folded or kept, since the synthesized topic already owns it")
    # CORE-REQUIREMENT SHIELD: the requirement-coverage check ran BEFORE this fold, over the FULL topic list
    # (foundation candidates included) — if a foundation topic was what made a CORE requirement "covered",
    # folding it away silently UN-covers that requirement with nothing left watching for it (live: the model
    # tagged 'Flow Types' and 'Reynolds Number' foundation; the coverage check marked R1 'Flow regimes' and
    # R2 'Governing quantities of turbulence' — both CORE — as covered BY THOSE topics; the fold then removed
    # both, and the intro told the learner they were prerequisites to learn ELSEWHERE, on a path whose only
    # two surviving topics never taught what Reynolds number even is). A requirement is only "covered"
    # relative to the topics that actually SURVIVE, not the topics the model happened to propose.
    _core_reqs = [r for r in (path_plan.get("goal_requirements") or []) if r.get("kind") == "core"]
    if _core_reqs and foundations:
        _survivor_ids = {id(t) for t in topics_out} - {id(t) for t in foundations}
        _survivors = [t for t in topics_out if id(t) in _survivor_ids]
        _load_bearing = [
            f for f in foundations
            if any(_requirement_covered_by_topics(r, [f]) and not _requirement_covered_by_topics(r, _survivors)
                   for r in _core_reqs)
        ]
        if _load_bearing:
            _keep_ids = {id(t) for t in _load_bearing}
            foundations = [t for t in foundations if id(t) not in _keep_ids]
            record_path_decision(
                path_plan, "topics.foundation_kept_core_requirement",
                f"kept {[str(t.get('title')) for t in _load_bearing]} — not folded",
                "the model tagged these content_role=foundation, but removing them would leave a CORE "
                "curriculum requirement with no remaining topic that teaches it — kept as taught topics "
                "rather than demoted to unaught, misleading prerequisites")

    dropped_prereqs: list[str] = []
    if foundations and real_concepts:
        dropped_prereqs = [str(t.get("title") or _subject_phrase(str(t.get("subject_key") or ""))).strip()
                           for t in foundations]
        drop_ids = {id(t) for t in foundations}
        topics_out = [t for t in topics_out if id(t) not in drop_ids]
        _log.info("topic_decomposition: folded %d prerequisite topic(s) into the intro: %s",
                  len(dropped_prereqs), dropped_prereqs)
        record_path_decision(path_plan, "topics.foundation_folded", f"removed {dropped_prereqs}",
                             "role=foundation topics are building blocks the learner is assumed to have, "
                             "not the goal itself — dropped as taught topics and carried as named (not "
                             "taught) prerequisites on the intro instead")

    non_intro = [t for t in topics_out if not _is_opener(t)]
    has_opener = any(_is_opener(t) for t in topics_out)
    # Synthesize an intro for a multi-topic path — OR whenever we folded prerequisites that need a home.
    # (A genuinely single-technique path is intentionally left lean, no intro padding — see the fixture tests.)
    # Single-topic paths get an intro too (product decision, live failure: a 'straight line depreciation'
    # path certified down to ONE topic and shipped with no orientation, no prereq card, no roadmap).
    if not has_opener and non_intro:
        intro = _synthesize_intro_topic(goal)
        intro["order_index"] = 0
        topics_out = [intro, *topics_out]
        _log.info("topic_decomposition: synthesized orientation intro (LLM emitted none)")
        record_path_decision(path_plan, "intro.synthesized", "inserted a generic orientation topic",
                             "the model emitted no study_path_introduction and this is a multi-topic (or "
                             "prereq-carrying) path — every such path opens with an intro by product "
                             "decision", title=intro.get("title"))

    # Requirements-first audit trail: persist the curriculum call's requirements + per-requirement ownership
    # on the opener's metadata, so a collapsed path is diagnosable from the DB (live: a one-topic path where
    # the model claimed every requirement — nothing recorded what was demanded vs owned).
    if path_plan.get("goal_requirements"):
        opener = next((t for t in topics_out if _is_opener(t)), None)
        if opener is not None:
            opener["goal_requirements"] = path_plan["goal_requirements"]

    # The intro's prerequisites are the SINGLE structured source of truth for its prerequisites card and the
    # prereq links: the LLM's explicit path_plan.assumed_prerequisites (clean concept names + glosses) plus
    # any foundation topics we folded above. No prose parsing — these names are canonical by construction.
    # Exclude any prereq the GOAL itself names (that concept is in-scope, taught, not an external prereq).
    llm_prereqs, prereq_glosses, prereq_requirements = _path_assumed_prereqs(path_plan)
    _prereqs_from_model = list(llm_prereqs)
    # Drop a declared prereq the goal names (in scope, taught) or one that is circular (goal subject in generic
    # wrapping) — those must stay taught topics, never external links.
    llm_prereqs = [p for p in llm_prereqs
                   if not _goal_names_topic({"title": p, "subject_key": p}, goal)
                   and not _is_circular_prereq(p, goal)]
    _dropped_goal_or_circular = [p for p in _prereqs_from_model if p not in llm_prereqs]
    # Drop a broad umbrella-discipline prereq ('Statistics') when a more specific one remains ('mean and
    # median') — the umbrella just vaguely restates the specific concept, which is the redundancy learners notice.
    _before_umbrella = list(llm_prereqs)
    llm_prereqs = _drop_umbrella_prereqs(llm_prereqs)
    if _dropped_goal_or_circular or _before_umbrella != llm_prereqs:
        record_path_decision(
            path_plan, "prerequisites.model_list_filtered", f"kept {llm_prereqs}",
            "dropped any prereq the goal itself names or that is circular with a taught topic, then "
            "collapsed umbrella-discipline duplicates down to the more specific prereq",
            model_proposed=_prereqs_from_model,
            dropped_goal_or_circular=_dropped_goal_or_circular or None,
            dropped_umbrella=[p for p in _before_umbrella if p not in llm_prereqs] or None)
    # A concept is EITHER an external prerequisite OR a topic this path teaches — never both. When the LLM
    # declares a concept as a prereq AND also emits a standalone topic for it (live failure: 'Graph
    # Representation' prereq + the 'Implementing Graph Representation' topic on a Dijkstra path), the learner is
    # ASSUMED to have it — so keep the PREREQUISITE (external, linked) and fold away the redundant topic, rather
    # than padding a Dijkstra path with a full graph-representation lesson. Recompute `teaching` afterward.
    _folded_prereq_topics = _fold_prereq_topics(topics_out, llm_prereqs, goal)
    if _folded_prereq_topics:
        record_path_decision(path_plan, "topics.folded_into_prerequisite",
                             f"removed taught topic(s) {_folded_prereq_topics}",
                             "the LLM declared the same concept BOTH as an external prerequisite and as "
                             "its own taught topic — the learner is assumed to have it, so the "
                             "prerequisite (external, linked) wins and the redundant topic is dropped")
    # A teaching topic whose subject is a STRICT PARENT of the goal ('TCP Overview' on a 'TCP congestion control'
    # path) teaches FOUNDATION material, not the goal — demote it to a prerequisite so the path isn't front-loaded
    # with the very basics the learner is assumed to have (and the goal topic isn't buried under them).
    # A coding topic whose subject is the GOAL ITSELF re-implements what the specific member implementations
    # already cover ('Implementing BST Traversal' beside Implementing Inorder/Postorder/Preorder) — drop it.
    # BEFORE demotion: its title carries the goal acronym, which would shield the parent walkthrough from the
    # acronym-expansion demotion below.
    _dropped_umbrella_coding = _drop_umbrella_coding_topics(topics_out, goal)
    if _dropped_umbrella_coding:
        record_path_decision(path_plan, "topics.umbrella_coding_dropped", f"removed {_dropped_umbrella_coding}",
                             "a coding topic whose subject IS the whole goal re-implements what the "
                             "specific member implementations already cover")
    demoted_prereqs = _demote_parent_of_goal_topics(topics_out, goal)
    if demoted_prereqs:
        record_path_decision(path_plan, "topics.demoted_to_prerequisite", f"demoted {demoted_prereqs}",
                             "the topic's subject is a STRICT PARENT of the goal (foundation material the "
                             "learner is assumed to have, not the thing the goal asks to learn) — moved "
                             "from a taught topic to an external, linked prerequisite")
    teaching = [t for t in topics_out if not _is_opener(t)]
    # Deterministic backstop: concepts shared across ≥2 topics' in_scope but taught by none are prerequisites the
    # LLM tends to omit (e.g. 'conditional probability' on a Bayes path). Their gloss is harvested downstream from
    # the intro's key-terms card if it defines them (and the term is then removed from key-terms — see §overlap).
    auto_prereqs = _cross_topic_foundations(teaching, goal)
    structured_prereqs = [*llm_prereqs, *auto_prereqs, *dropped_prereqs, *demoted_prereqs]
    if structured_prereqs:
        for t in topics_out:
            if _is_opener(t):
                ap = list(t.get("assumed_prerequisites") or [])
                have = {_prereq_key(a) for a in ap}
                for p in structured_prereqs:
                    key = _prereq_key(p)
                    if p and key and key not in have:
                        ap.append(_prereq_display(p))
                        have.add(key)
                # A prereq that is itself a prerequisite OF another listed prereq is redundant — refreshing
                # the advanced one's path covers it (textbook model: offer the immediately-prior unit).
                ap = _drop_prereq_chain_redundancy(ap)
                # Umbrella dedup on the FINAL merged list too (demotion can add an umbrella beside the
                # model's — 'fluid dynamics' + 'Fluid Mechanics' are invisible to lexical dedup).
                ap = _drop_umbrella_prereqs(ap)
                t["assumed_prerequisites"] = ap
                if prereq_glosses or prereq_requirements:
                    meta = t.setdefault("decomposition_metadata", {})
                    # Key the maps by the DISPLAY name too ("graph theory basics" → "graph theory"), so the
                    # card grounding's name.lower() lookup still hits after the tail-qualifier strip.
                    def _with_display_keys(m: dict) -> dict:
                        out = dict(m)
                        for k, v in m.items():
                            dk = _prereq_display(k).lower()
                            if dk and dk not in out:
                                out[dk] = v
                        return out
                    if prereq_glosses:
                        meta["assumed_prerequisite_glosses"] = _with_display_keys({
                            **(meta.get("assumed_prerequisite_glosses") or {}), **prereq_glosses})
                    if prereq_requirements:
                        meta["assumed_prerequisite_requirements"] = _with_display_keys({
                            **(meta.get("assumed_prerequisite_requirements") or {}), **prereq_requirements})
                break

    # Collapse near-duplicate teaching topics (filler-only title difference) BEFORE renaming/ordering, so the
    # learner never gets the same lesson twice; the order_index renumber below closes any gap.
    _collapse_near_duplicate_topics(topics_out)
    ordered = sorted(topics_out, key=lambda t: int(t.get("order_index") or 0))
    _disambiguate_topic_titles(ordered, goal)
    title_by_id = {str(t.get("topic_id")): str(t.get("title") or "") for t in ordered if t.get("title")}
    # synthesized follow-ups have no title yet — give title_by_id their adapted title too
    for i, t in enumerate(ordered, start=1):
        if not t.get("title"):
            subject = str(t.get("subject_key") or "")
            title_by_id[str(t.get("topic_id"))] = (
                f"Implementing {_subject_phrase(subject)}"
                if canonical_action(t.get("primary_action")) == "implement" else _subject_phrase(subject))

    # Path-level decision trace (curriculum call, thin-plan retry, requirement coverage, prereq merging,
    # topic drops/demotions/folds) is attached to the opener LAST, once every path-level record_path_decision
    # call above has run — mirrors the goal_requirements attach pattern.
    _path_trace = take_path_trace(path_plan)
    if _path_trace:
        _opener = next((t for t in ordered if _is_opener(t)), None)
        if _opener is not None:
            _opener["path_decision_trace"] = _path_trace

    legacy = [_to_legacy(t, title_by_id, i) for i, t in enumerate(ordered, start=1)]
    for i, t in enumerate(legacy, start=1):
        t["order_index"] = i
    return legacy
