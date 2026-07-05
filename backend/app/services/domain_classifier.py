"""Goal → domain classifier (Phase 0, DOMAIN_ROUTING_AND_TOPIC_GATE_SPEC §3).

Deterministic heuristic (no LLM, zero latency): a weighted count of per-domain keyword / notation / unit /
language-slug hits. `confidence` is the top−runner-up margin. The four v1 domains are `coding · math · science ·
concept`; anything that matches nothing resolves to `concept` with `classification_status = fallback_concept`
(NOT `classifier_failed` — a genuine classifier *failure* is an exception the caller catches, §3.2).

Stage-2 LLM escalation on low confidence is a deliberate v1 hook (see `classify_domain(..., escalate=)`), not
implemented here. All keyword lists / weights / thresholds are **tunable config**, not blockers (§7).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- tunable constants -----------------------------------------------------------------------------------
_HIGH_CONFIDENCE = 0.40          # >= this margin -> `classified`; below -> `low_confidence`
_KW_WEIGHT = 1                   # a plain keyword hit
_STRONG_WEIGHT = 2               # notation / units / language names / CS-slug hits (higher signal)

# Per-domain plain keywords (weight 1). Kept lowercase; matched on word boundaries.
_KEYWORDS: dict[str, tuple[str, ...]] = {
    "coding": (
        "implement", "implementation", "code", "coding", "program", "programming", "function", "method",
        "class", "api", "compile", "debug", "algorithm", "data structure", "array", "linked list", "hashmap",
        "hash table", "recursion", "loop", "pointer", "stack", "queue", "binary search", "sorting", "sort",
        "traversal", "dfs", "bfs", "dynamic programming", "leetcode", "runtime", "big o",
    ),
    "math": (
        "solve", "prove", "proof", "derive", "derivation", "equation", "formula", "theorem", "integral",
        "integrate", "derivative", "differentiate", "matrix", "matrices", "vector", "polynomial", "factor",
        "factoring", "quadratic", "completing the square", "logarithm", "exponent", "trigonometry", "sine",
        "cosine", "calculus", "algebra", "algebraic", "inequality", "expression", "simplify", "mathematically",
    ),
    "science": (
        "physics", "chemistry", "biology", "chemical", "reaction", "force", "velocity", "acceleration",
        "momentum", "energy", "circuit", "voltage", "current", "resistance", "kinematics", "thermodynamics",
        "cell", "dna", "photosynthesis", "evolution", "molecule", "atom", "stoichiometry", "molarity",
        "ecosystem", "gravity", "newton's", "ohm's law", "density", "mass",
    ),
    "concept": (
        "inflation", "economics", "economy", "history", "historical", "philosophy", "ethics", "essay",
        "writing", "business", "marketing", "finance", "politics", "sociology", "psychology", "definition",
        "compare", "difference between", "meaning of", "what is",
    ),
}

# Strong signals (weight 2). `coding` gets language names; `math` notation; `science` units.
_LANGUAGES: tuple[str, ...] = (
    "python", "java", "javascript", "typescript", "c++", "cpp", "c#", "golang", "rust", "ruby", "php",
    "kotlin", "swift", "scala", "sql", "pytorch", "tensorflow", "numpy",
)
_MATH_NOTATION: tuple[str, ...] = ("∑", "∫", "√", "π", "θ", "≤", "≥", "≠", "^2", "x^", "dx", "dy/dx")
_SCIENCE_UNITS: tuple[str, ...] = ("m/s", "m/s^2", "m/s²", " mol", " n)", " kg", "joule", "volt", " amp",
                                   "ohm", "km/h", "= ma", "f = ma", "f=ma")

# Controlled subdomain families (§3.2), best-effort match within the winning domain.
_SUBDOMAIN_FAMILIES: dict[str, dict[str, tuple[str, ...]]] = {
    "coding": {
        "algorithms": ("algorithm", "sort", "search", "dfs", "bfs", "traversal", "dynamic programming"),
        "data-structures": ("array", "linked list", "stack", "queue", "hash", "tree", "graph", "heap"),
        "web-development": ("html", "css", "react", "http", "frontend", "backend", "web"),
        "databases": ("sql", "database", "query", "index", "join"),
        "machine-learning": ("neural", "pytorch", "tensorflow", "gradient descent", "model", "training"),
        "programming-basics": ("function", "loop", "variable", "class", "method"),
    },
    "math": {
        "algebra": ("algebra", "quadratic", "completing the square", "polynomial", "factor", "equation"),
        "calculus": ("calculus", "integral", "derivative", "differentiate", "limit"),
        "linear-algebra": ("matrix", "matrices", "vector", "eigen"),
        "probability-statistics": ("probability", "statistics", "variance", "distribution", "mean"),
        "geometry": ("geometry", "triangle", "circle", "angle", "area"),
        "discrete-math": ("graph theory", "combinatorics", "logic", "set theory"),
    },
    "science": {
        "physics": ("physics", "force", "velocity", "acceleration", "newton", "kinematics", "energy", "circuit"),
        "chemistry": ("chemistry", "chemical", "reaction", "molecule", "atom", "mole", "stoichiometry"),
        "biology": ("biology", "cell", "dna", "photosynthesis", "evolution", "ecosystem"),
        "earth-science": ("plate tectonics", "geology", "weather", "climate"),
    },
    "concept": {
        "economics": ("inflation", "economics", "economy", "finance", "market"),
        "history": ("history", "historical", "war", "revolution"),
        "philosophy": ("philosophy", "ethics", "logic", "epistemology"),
        "business": ("business", "marketing", "management", "strategy"),
        "writing": ("essay", "writing", "grammar", "rhetoric"),
        "general": (),
    },
}

_DOMAINS = ("coding", "math", "science", "concept")


@dataclass
class DomainSignals:
    """The Phase-0 classifier output (a subset of `PromptSignals`, §3)."""
    domain: str                                   # coding | math | science | concept
    confidence: float                             # top − runner-up margin, 0..1
    classification_status: str                    # classified | low_confidence | fallback_concept | classifier_failed
    subdomain_family: str = ""                    # controlled (§3.2) or ""
    subdomain_label: str = ""                     # free text (reserved; "" in v1)
    scores: dict[str, float] = field(default_factory=dict)  # per-domain raw scores (debug/telemetry)


def _count(text: str, needles: tuple[str, ...], *, word_boundary: bool) -> int:
    hits = 0
    for n in needles:
        if not n:
            continue
        if word_boundary and n.isalnum():
            if re.search(rf"\b{re.escape(n)}\b", text):
                hits += 1
        elif n in text:                            # phrases / notation / units: plain substring
            hits += 1
    return hits


def _domain_scores(text: str) -> dict[str, float]:
    scores: dict[str, float] = {}
    for domain in _DOMAINS:
        s = _KW_WEIGHT * _count(text, _KEYWORDS[domain], word_boundary=True)
        scores[domain] = float(s)
    scores["coding"] += _STRONG_WEIGHT * _count(text, _LANGUAGES, word_boundary=False)
    scores["math"] += _STRONG_WEIGHT * _count(text, _MATH_NOTATION, word_boundary=False)
    scores["science"] += _STRONG_WEIGHT * _count(text, _SCIENCE_UNITS, word_boundary=False)
    return scores


def _best_subdomain_family(domain: str, text: str) -> str:
    best, best_hits = "", 0
    for family, needles in _SUBDOMAIN_FAMILIES.get(domain, {}).items():
        h = _count(text, needles, word_boundary=False)
        if h > best_hits:
            best, best_hits = family, h
    return best


def classify_domain(goal: str) -> DomainSignals:
    """Map a raw goal string to a `DomainSignals`. Never raises for normal input; nothing-matches ⇒
    `fallback_concept`. (A real classifier *failure* — e.g. an escalation call throwing — is the caller's
    responsibility to catch and turn into `classification_status = classifier_failed`, §3.2.)"""
    text = f" {str(goal or '').lower().strip()} "
    scores = _domain_scores(text)

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top_domain, top_score = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0.0

    if top_score <= 0:
        return DomainSignals("concept", 0.0, "fallback_concept", "general", "", scores)

    confidence = max(0.0, min(1.0, (top_score - runner_up) / top_score))
    status = "classified" if confidence >= _HIGH_CONFIDENCE else "low_confidence"
    family = _best_subdomain_family(top_domain, text)
    return DomainSignals(top_domain, round(confidence, 3), status, family, "", scores)
