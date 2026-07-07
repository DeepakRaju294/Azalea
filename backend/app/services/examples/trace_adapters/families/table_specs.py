"""T14 table-evaluation CONCEPT SPECS — truth tables of Boolean expressions on the table engine. Each is DATA: the
ordered variables + a local cell rule (the expression) + its display. Adding one = append a `TableSpec`."""
from __future__ import annotations

from .table_engine import TableSpec

TRUTH_TABLE_AND_OR = TableSpec(
    slug="truth_table_and_or",
    title="the truth table of A AND (B OR C)",
    problem_template="Build the truth table for {expr}.",
    variables=["A", "B", "C"],
    expr=lambda v: bool(v["A"] and (v["B"] or v["C"])),
    expr_str="A AND (B OR C)",
    # the generic "truth table" entry lives here (the default), but must NOT steal a sibling's specific query,
    # so the sibling discriminators are negative guards.
    aliases=["truth table", "truth table and or", "boolean truth table", "build a truth table",
             "logic truth table"],
    not_aliases=["karnaugh", "xor", "exclusive or", "implication", "conditional", "if then", "if-then",
                 "majority"],
    priority=54,
)

TRUTH_TABLE_XOR = TableSpec(
    slug="truth_table_xor",
    title="the truth table of A XOR B",
    problem_template="Build the truth table for {expr}.",
    variables=["A", "B"],
    expr=lambda v: bool(v["A"] ^ v["B"]),
    expr_str="A XOR B",
    aliases=["truth table xor", "xor truth table", "exclusive or truth table"],
    not_aliases=["karnaugh"],
    priority=52,
)

TRUTH_TABLE_IMPLICATION = TableSpec(
    slug="truth_table_implication",
    title="the truth table of A IMPLIES B",
    problem_template="Build the truth table for {expr}.",
    variables=["A", "B"],
    expr=lambda v: bool((not v["A"]) or v["B"]),
    expr_str="A IMPLIES B",
    aliases=["truth table implication", "implication truth table", "conditional truth table",
             "if then truth table"],
    not_aliases=["karnaugh"],
    priority=52,
)

TRUTH_TABLE_MAJORITY = TableSpec(
    slug="truth_table_majority",
    title="the truth table of MAJORITY(A, B, C)",
    problem_template="Build the truth table for {expr}.",
    variables=["A", "B", "C"],
    expr=lambda v: (v["A"] + v["B"] + v["C"]) >= 2,
    expr_str="MAJORITY(A, B, C)",
    aliases=["truth table majority", "majority function truth table", "majority gate truth table"],
    not_aliases=["karnaugh"],
    priority=50,
)


ALL_SPECS = [TRUTH_TABLE_AND_OR, TRUTH_TABLE_XOR, TRUTH_TABLE_IMPLICATION, TRUTH_TABLE_MAJORITY]
