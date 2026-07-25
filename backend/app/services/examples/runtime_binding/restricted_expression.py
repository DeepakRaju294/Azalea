"""Restricted rational-closed expression AST for Milestone A.

The compiler accepts only the reviewed FormulaSpec expression-string subset. It never calls
Python eval and fails closed on every node outside the frozen scalar grammar.
"""

from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Literal, TypeAlias


class RestrictedExpressionError(ValueError):
    pass


@dataclass(frozen=True)
class Literal:
    value: Fraction


@dataclass(frozen=True)
class Variable:
    name: str


@dataclass(frozen=True)
class Binary:
    op: Literal["add", "subtract", "multiply", "divide", "power"]
    left: "RestrictedExpression"
    right: "RestrictedExpression"


@dataclass(frozen=True)
class Negate:
    operand: "RestrictedExpression"


RestrictedExpression: TypeAlias = Literal | Variable | Binary | Negate


def _literal_from_source(node: ast.Constant, source: str) -> Literal:
    if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
        raise RestrictedExpressionError(f"unsupported literal type: {type(node.value).__name__}")
    token = ast.get_source_segment(source, node)
    if not token:
        token = repr(node.value)
    try:
        return Literal(Fraction(token))
    except (ValueError, ZeroDivisionError) as exc:
        raise RestrictedExpressionError(f"noncanonical numeric literal: {token!r}") from exc


def _compile_node(node: ast.AST, source: str, *, depth: int, max_depth: int) -> RestrictedExpression:
    if depth > max_depth:
        raise RestrictedExpressionError(f"expression depth exceeds {max_depth}")
    if isinstance(node, ast.Constant):
        return _literal_from_source(node, source)
    if isinstance(node, ast.Name):
        return Variable(node.id)
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.USub):
            return Negate(_compile_node(node.operand, source, depth=depth + 1, max_depth=max_depth))
        if isinstance(node.op, ast.UAdd):
            return _compile_node(node.operand, source, depth=depth + 1, max_depth=max_depth)
        raise RestrictedExpressionError(f"unsupported unary operator: {type(node.op).__name__}")
    if isinstance(node, ast.BinOp):
        op_map: dict[type[ast.operator], Literal["add", "subtract", "multiply", "divide", "power"]] = {
            ast.Add: "add",
            ast.Sub: "subtract",
            ast.Mult: "multiply",
            ast.Div: "divide",
            ast.Pow: "power",
        }
        op = op_map.get(type(node.op))
        if op is None:
            raise RestrictedExpressionError(f"unsupported binary operator: {type(node.op).__name__}")
        left = _compile_node(node.left, source, depth=depth + 1, max_depth=max_depth)
        right = _compile_node(node.right, source, depth=depth + 1, max_depth=max_depth)
        if op == "power" and not (
            isinstance(right, Literal) and right.value.denominator == 1
        ):
            raise RestrictedExpressionError("power exponent must be a constant integer")
        return Binary(op=op, left=left, right=right)
    raise RestrictedExpressionError(f"unsupported AST node: {type(node).__name__}")


def compile_restricted_expression(
    source: str,
    *,
    max_nodes: int = 128,
    max_depth: int = 24,
) -> RestrictedExpression:
    try:
        parsed = ast.parse(source, mode="eval")
    except SyntaxError as exc:
        raise RestrictedExpressionError(
            f"invalid expression syntax at line {exc.lineno}, column {exc.offset}: {exc.msg}"
        ) from exc
    node_count = sum(1 for _ in ast.walk(parsed))
    if node_count > max_nodes:
        raise RestrictedExpressionError(f"expression node count {node_count} exceeds {max_nodes}")
    return _compile_node(parsed.body, source, depth=1, max_depth=max_depth)


def expression_variables(expression: RestrictedExpression) -> frozenset[str]:
    if isinstance(expression, Literal):
        return frozenset()
    if isinstance(expression, Variable):
        return frozenset({expression.name})
    if isinstance(expression, Negate):
        return expression_variables(expression.operand)
    return expression_variables(expression.left) | expression_variables(expression.right)


def expression_to_canonical(expression: RestrictedExpression) -> dict[str, Any]:
    if isinstance(expression, Literal):
        return {
            "node": "literal",
            "numerator": str(expression.value.numerator),
            "denominator": str(expression.value.denominator),
        }
    if isinstance(expression, Variable):
        return {"node": "variable", "name": expression.name}
    if isinstance(expression, Negate):
        return {"node": "negate", "operand": expression_to_canonical(expression.operand)}
    return {
        "node": expression.op,
        "left": expression_to_canonical(expression.left),
        "right": expression_to_canonical(expression.right),
    }


def expression_canonical_json(expression: RestrictedExpression) -> str:
    return json.dumps(
        expression_to_canonical(expression),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def expression_canonical_digest(expression: RestrictedExpression) -> str:
    return hashlib.sha256(expression_canonical_json(expression).encode("utf-8")).hexdigest()

