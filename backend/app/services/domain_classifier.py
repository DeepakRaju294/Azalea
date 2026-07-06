"""Goal → domain classifier (Phase 0, DOMAIN_ROUTING_AND_TOPIC_GATE_SPEC §3).

Deterministic heuristic (no LLM, zero latency): a weighted count of per-domain keyword / notation / unit /
language-slug hits over the **fine scored domains**, plus two *derived* outcomes: `mixed` (two comparably-strong
gate FAMILIES) and `unknown` (nothing matched).

Two layers:
- **`domain`** (fine, persisted/analytics): `coding · math · physics · chemistry · biology ·
  electrical_engineering · finance · economics · humanities` — plus derived `mixed · unknown`.
- **`gate_family`** (coarse, drives the allow-list): `coding · math · science · expository` — or `""` for
  `mixed`/`unknown`, which are **non-gating** (the safe conservative fallback; existing behavior preserved).

`classification_status ∈ {classified · ambiguous · failed}` (`pending` is the pre-run DB state; `failed` is set
by the caller on exception, §3.2). All keyword lists / weights / thresholds are **tunable config** (§7).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- tunable constants -----------------------------------------------------------------------------------
_HIGH_CONFIDENCE = 0.40           # >= this fine-domain margin -> `classified`; below -> `ambiguous`
_KW_WEIGHT = 1                    # a plain keyword hit
_STRONG_WEIGHT = 2               # notation / units / language names / CS-slug hits (higher signal)
_MIXED_FLOOR = 3                 # both top-2 gate FAMILIES must reach this to be `mixed`
_MIXED_MARGIN = 1                # ...and be within this of each other

# Fine domain -> coarse gate family (the allow-list key). mixed/unknown map to "" (non-gating).
FAMILY_OF: dict[str, str] = {
    "coding": "coding", "machine_learning": "coding",
    "math": "math", "logic": "math", "statistics": "math",
    "physics": "science", "chemistry": "science", "biology": "science", "electrical_engineering": "science",
    "finance": "expository", "economics": "expository", "humanities": "expository",
}
_SCORED = tuple(FAMILY_OF.keys())

# Per-domain plain keywords (weight 1), lowercase, word-boundary matched.
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
    "machine_learning": (
        "machine learning", "neural network", "deep learning", "backpropagation", "training data", "classifier",
        "overfitting", "convolutional", "transformer", "embedding", "reinforcement learning", "supervised",
        "unsupervised", "feature engineering", "gradient descent",
    ),
    "logic": (
        "propositional logic", "predicate logic", "truth table", "syllogism", "tautology", "logical fallacy",
        "boolean algebra", "first-order logic", "modus ponens", "inference rule", "formal logic",
        "symbolic logic", "validity", "proposition", "deductive",
    ),
    "statistics": (
        "statistics", "statistical", "probability", "distribution", "regression", "hypothesis test", "p-value",
        "variance", "standard deviation", "correlation", "confidence interval", "bayesian", "median", "sample",
        "normal distribution", "chi-square", "sampling",
    ),
    "physics": (
        "physics", "force", "velocity", "acceleration", "momentum", "energy", "gravity", "motion", "newton's",
        "kinematics", "thermodynamics", "wave", "optics", "quantum", "friction", "projectile", "torque",
    ),
    "chemistry": (
        "chemistry", "chemical", "reaction", "molecule", "atom", "mole", "molar", "molarity", "stoichiometry",
        "bond", "acid", "base", "compound", "element", "periodic table", "solution", "titration",
    ),
    "biology": (
        "biology", "cell", "dna", "gene", "genetic", "photosynthesis", "evolution", "ecosystem", "organism",
        "protein", "enzyme", "mitosis", "meiosis", "species", "anatomy", "respiration",
    ),
    "electrical_engineering": (
        "circuit", "voltage", "current", "resistance", "capacitor", "inductor", "transistor", "amplifier",
        "logic gate", "signal", "electrical", "impedance", "diode", "kirchhoff", "ohm's law",
    ),
    "finance": (
        "finance", "financial", "investment", "stock", "interest", "compound interest", "portfolio", "bond",
        "revenue", "profit", "cash flow", "valuation", "npv", "accounting", "loan", "mortgage",
    ),
    "economics": (
        "economics", "economy", "inflation", "gdp", "supply", "demand", "market", "elasticity", "monetary",
        "fiscal", "unemployment", "trade", "recession", "macroeconomic", "microeconomic",
    ),
    "humanities": (
        "history", "historical", "war", "revolution", "philosophy", "ethics", "literature", "novel", "poem",
        "poetry", "essay", "rhetoric", "art", "culture", "politics", "government", "religion", "sociology",
        "psychology", "shakespeare", "hamlet", "theme", "themes", "literary",
    ),
}

# Strong signals (weight 2).
_LANGUAGES: tuple[str, ...] = (
    "python", "java", "javascript", "typescript", "c++", "cpp", "c#", "golang", "rust", "ruby", "php",
    "kotlin", "swift", "scala", "sql", "pytorch", "tensorflow", "numpy",
)
_MATH_NOTATION: tuple[str, ...] = ("∑", "∫", "√", "π", "θ", "≤", "≥", "≠", "^2", "x^", "dx", "dy/dx")
_PHYS_UNITS: tuple[str, ...] = ("m/s", "m/s^2", "m/s²", " kg", "joule", "newton", "= ma", "f = ma", "f=ma", "km/h")
_EE_UNITS: tuple[str, ...] = (" volt", " amp", "ohm", "watt", "hertz", "farad")
_CHEM_UNITS: tuple[str, ...] = (" mol", "g/mol", " ph ")


@dataclass
class DomainSignals:
    """Phase-0 classifier output (a subset of `PromptSignals`, §3)."""
    domain: str                                   # fine domain, or mixed | unknown
    gate_family: str                              # coding | math | science | expository | "" (non-gating)
    confidence: float                             # top − runner-up (fine) margin, 0..1
    classification_status: str                    # classified | ambiguous | failed  (pending set by DB)
    subdomain_family: str = ""                    # reserved; the fine `domain` already carries granularity
    scores: dict[str, float] = field(default_factory=dict)  # per-fine-domain raw scores (telemetry/debug)


def _count(text: str, needles: tuple[str, ...], *, word_boundary: bool) -> int:
    hits = 0
    for n in needles:
        if not n:
            continue
        if word_boundary and n.replace(" ", "").isalnum() and " " not in n:
            if re.search(rf"\b{re.escape(n)}\b", text):
                hits += 1
        elif n in text:                            # phrases / notation / units: plain substring
            hits += 1
    return hits


def _fine_scores(text: str) -> dict[str, float]:
    scores = {d: float(_KW_WEIGHT * _count(text, _KEYWORDS[d], word_boundary=True)) for d in _SCORED}
    scores["coding"] += _STRONG_WEIGHT * _count(text, _LANGUAGES, word_boundary=False)
    scores["math"] += _STRONG_WEIGHT * _count(text, _MATH_NOTATION, word_boundary=False)
    scores["physics"] += _STRONG_WEIGHT * _count(text, _PHYS_UNITS, word_boundary=False)
    scores["electrical_engineering"] += _STRONG_WEIGHT * _count(text, _EE_UNITS, word_boundary=False)
    scores["chemistry"] += _STRONG_WEIGHT * _count(text, _CHEM_UNITS, word_boundary=False)
    return scores


def _family_scores(fine: dict[str, float]) -> dict[str, float]:
    fam: dict[str, float] = {}
    for domain, score in fine.items():
        fam[FAMILY_OF[domain]] = fam.get(FAMILY_OF[domain], 0.0) + score
    return fam


def classify_domain(goal: str) -> DomainSignals:
    """Map a raw goal to a `DomainSignals`. Never raises for normal input. Nothing-matches ⇒ `unknown`
    (non-gating); two comparably-strong gate families ⇒ `mixed` (non-gating). A real classifier *failure* is an
    exception the caller catches and turns into `classification_status='failed'`, §3.2."""
    text = f" {str(goal or '').lower().strip()} "
    fine = _fine_scores(text)
    fam = _family_scores(fine)

    fine_ranked = sorted(fine.items(), key=lambda kv: kv[1], reverse=True)
    top_domain, top_score = fine_ranked[0]
    if top_score <= 0:
        return DomainSignals("unknown", "", 0.0, "ambiguous", "", fine)

    fam_ranked = sorted(fam.items(), key=lambda kv: kv[1], reverse=True)
    if len(fam_ranked) > 1:
        (f1, s1), (f2, s2) = fam_ranked[0], fam_ranked[1]
        if s1 >= _MIXED_FLOOR and s2 >= _MIXED_FLOOR and (s1 - s2) <= _MIXED_MARGIN:
            return DomainSignals("mixed", "", 0.0, "ambiguous", "", fine)

    runner_up = fine_ranked[1][1] if len(fine_ranked) > 1 else 0.0
    confidence = max(0.0, min(1.0, (top_score - runner_up) / top_score))
    status = "classified" if confidence >= _HIGH_CONFIDENCE else "ambiguous"
    return DomainSignals(top_domain, FAMILY_OF[top_domain], round(confidence, 3), status, "", fine)
