"""Reviewed grammar manifest (spec §5.1).

The `direct_formula_calculation` grammar owns the executable semantics a binding may specialize but never
extend. Milestone B has exactly one grammar; it names the substrate node allowlist and the versioned
numeric/unit policy so a binding cannot smuggle in a node or policy the executor has not proven.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.examples.runtime_binding.policy import NUMERIC_UNIT_POLICY


@dataclass(frozen=True)
class GrammarSlot:
    slot_id: str
    role: str                       # input_symbols | output_symbol | relationship | convention
    cardinality: str                # one | one_or_more
    required: bool


@dataclass(frozen=True)
class GrammarManifest:
    grammar_id: str
    version: int
    required_slots: tuple[GrammarSlot, ...]
    optional_slots: tuple[GrammarSlot, ...]
    supported_expression_nodes: tuple[str, ...]
    numeric_policy_ref: str


DIRECT_FORMULA_CALCULATION = GrammarManifest(
    grammar_id="direct_formula_calculation",
    version=1,
    required_slots=(
        GrammarSlot("given_symbols", "input_symbols", "one_or_more", True),
        GrammarSlot("unknown_symbol", "output_symbol", "one", True),
        GrammarSlot("relationship", "relationship", "one", True),
    ),
    optional_slots=(GrammarSlot("unit_convention", "convention", "one", False),),
    # exactly the Milestone A Wave-0 restricted-AST nodes; nothing else executes
    supported_expression_nodes=("literal", "variable", "add", "subtract", "multiply", "divide", "power", "negate"),
    numeric_policy_ref=NUMERIC_UNIT_POLICY["version"],
)

GRAMMARS: dict[str, GrammarManifest] = {DIRECT_FORMULA_CALCULATION.grammar_id: DIRECT_FORMULA_CALCULATION}
