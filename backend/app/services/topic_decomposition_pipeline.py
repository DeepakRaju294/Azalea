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
from app.prompts.topic_decomposition_prompt import SYSTEM_PROMPT, build_decomposition_prompt

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


def _normalize_topic(t: dict[str, Any]) -> dict[str, Any]:
    """Format-normalize the model's fields (subject_key, primary_action, topic_type) before validation."""
    t = dict(t)
    t["subject_key"] = normalize_subject_key(t.get("subject_key"))
    if t.get("primary_action"):
        t["primary_action"] = canonical_action(t["primary_action"]) or t["primary_action"]
    if not t.get("topic_type") and t.get("content_role"):
        t["topic_type"] = resolve_topic_type(t["content_role"])
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
    payload = {"system": SYSTEM_PROMPT,
               "user": build_decomposition_prompt(goal=goal, chunks_text=chunks_text, feedback=feedback)}
    parsed = _coerce((model_fn or _default_model_fn)(payload))
    raw_topics = [t for t in (parsed.get("topics") or []) if isinstance(t, dict)]
    if not raw_topics:
        return []

    path_plan = parsed.get("path_plan") if isinstance(parsed.get("path_plan"), dict) else {}
    path_plan.setdefault("required_capabilities", [])
    path_plan.setdefault("end_capability_actions", [])

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
    # De-conflate: an 'orientation' topic the LLM actually loaded with a concrete concept is a mislabeled
    # teaching topic — restore its teaching type so the concept is TAUGHT (worked example + adapter), which
    # also frees the intro slot so a real generic orientation topic is synthesized below.
    opener_seen = False
    for t in topics_out:
        if _is_conflated_intro(t):
            t["topic_type"] = "math_formula_method"       # domain gate remaps for non-math paths
            t["content_role"] = "calculation"
            _log.info("topic_decomposition: de-conflated mislabeled intro %r -> teaching topic", t.get("title"))
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
                # An opener titled with a whole-DISCIPLINE umbrella orients the WRONG subject (live: a
                # 'fluid turbulence' path opened with an intro titled 'Fluid Dynamics' whose background card
                # was 'Why Fluid Dynamics Matters'). The intro's title is the GOAL's, not the parent field's.
                stripped_title = " ".join(w for w in _norm_title(str(t.get("title") or "")).split()
                                          if w not in _GENERIC_TOPIC_FILLER)
                if stripped_title in _UMBRELLA_FIELDS:
                    new_title = _intro_title(goal)
                    _log.info("topic_decomposition: retitled umbrella-named intro %r -> %r",
                              t.get("title"), new_title)
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
    foundations = [t for t in topics_out
                   if not _is_opener(t) and _role(t) == "foundation" and not _goal_names_topic(t, goal)
                   and not _is_circular_prereq(str(t.get("title") or t.get("subject_key") or ""), goal)]
    real_concepts = [t for t in topics_out if not _is_opener(t) and _role(t) != "foundation"]
    dropped_prereqs: list[str] = []
    if foundations and real_concepts:
        dropped_prereqs = [str(t.get("title") or _subject_phrase(str(t.get("subject_key") or ""))).strip()
                           for t in foundations]
        drop_ids = {id(t) for t in foundations}
        topics_out = [t for t in topics_out if id(t) not in drop_ids]
        _log.info("topic_decomposition: folded %d prerequisite topic(s) into the intro: %s",
                  len(dropped_prereqs), dropped_prereqs)

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

    # The intro's prerequisites are the SINGLE structured source of truth for its prerequisites card and the
    # prereq links: the LLM's explicit path_plan.assumed_prerequisites (clean concept names + glosses) plus
    # any foundation topics we folded above. No prose parsing — these names are canonical by construction.
    # Exclude any prereq the GOAL itself names (that concept is in-scope, taught, not an external prereq).
    llm_prereqs, prereq_glosses, prereq_requirements = _path_assumed_prereqs(path_plan)
    # Drop a declared prereq the goal names (in scope, taught) or one that is circular (goal subject in generic
    # wrapping) — those must stay taught topics, never external links.
    llm_prereqs = [p for p in llm_prereqs
                   if not _goal_names_topic({"title": p, "subject_key": p}, goal)
                   and not _is_circular_prereq(p, goal)]
    # Drop a broad umbrella-discipline prereq ('Statistics') when a more specific one remains ('mean and
    # median') — the umbrella just vaguely restates the specific concept, which is the redundancy learners notice.
    llm_prereqs = _drop_umbrella_prereqs(llm_prereqs)
    # A concept is EITHER an external prerequisite OR a topic this path teaches — never both. When the LLM
    # declares a concept as a prereq AND also emits a standalone topic for it (live failure: 'Graph
    # Representation' prereq + the 'Implementing Graph Representation' topic on a Dijkstra path), the learner is
    # ASSUMED to have it — so keep the PREREQUISITE (external, linked) and fold away the redundant topic, rather
    # than padding a Dijkstra path with a full graph-representation lesson. Recompute `teaching` afterward.
    _fold_prereq_topics(topics_out, llm_prereqs, goal)
    # A teaching topic whose subject is a STRICT PARENT of the goal ('TCP Overview' on a 'TCP congestion control'
    # path) teaches FOUNDATION material, not the goal — demote it to a prerequisite so the path isn't front-loaded
    # with the very basics the learner is assumed to have (and the goal topic isn't buried under them).
    # A coding topic whose subject is the GOAL ITSELF re-implements what the specific member implementations
    # already cover ('Implementing BST Traversal' beside Implementing Inorder/Postorder/Preorder) — drop it.
    # BEFORE demotion: its title carries the goal acronym, which would shield the parent walkthrough from the
    # acronym-expansion demotion below.
    _drop_umbrella_coding_topics(topics_out, goal)
    demoted_prereqs = _demote_parent_of_goal_topics(topics_out, goal)
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

    legacy = [_to_legacy(t, title_by_id, i) for i, t in enumerate(ordered, start=1)]
    for i, t in enumerate(legacy, start=1):
        t["order_index"] = i
    return legacy
