"""Multi-language aria-label scaffolding for v2 visuals.

Today's compilers hard-code English aria_labels into every
SelectableElement. This module localizes them at compile time based on
a configured language code.

Configuration:
  - Set `V2_LOCALE` env var (default: "en") to control the global default.
  - Per-lesson override: pass `locale` into compile_lesson_v2() via the
    CompileContext.metadata (orchestrator wires it through).
  - Per-element override: a compiler can call localize_aria(key, locale, **kwargs)
    directly with its own message keys.

The catalog uses sprintf-style templates with named placeholders. Adding
a language = adding a dict to _CATALOG.
"""

from __future__ import annotations

import os
from typing import Any

DEFAULT_LOCALE = os.environ.get("V2_LOCALE", "en")


_CATALOG: dict[str, dict[str, str]] = {
    "en": {
        # node_link
        "node": "Node {label}, state {state}",
        "node_with_role": "Node {label}, role {role}, state {state}",
        "edge": "Edge from {from_id} to {to_id}",
        "edge_with_label": "Edge from {from_id} to {to_id}, label {label}",
        "stack_item": "Call stack entry at depth {depth}, value {value}",
        "output_item": "Output entry at position {index}, value {value}",
        "frontier_item": "{kind} entry at position {index}, value {value}",
        # indexed_sequence
        "cell": "Cell at index {index}, value {value}",
        "cell_active": "Cell at index {index}, value {value}, active",
        "pointer": "Pointer {label} at index {position}",
        # code_execution
        "code_line": "Code line {line_number}: {content}",
        "code_line_active": "Code line {line_number}, currently executing: {content}",
        "code_variable": "Variable {name} equals {value}",
        # grid_matrix
        "grid_cell": "Cell row {row} column {column}, value {value}",
        # formula
        "subexpression": "Subexpression: {text}",
        "symbol": "Symbol {symbol} ({meaning})",
        # generic
        "whole_visual": "Whole visual: {base_type}",
    },
    "es": {
        "node": "Nodo {label}, estado {state}",
        "node_with_role": "Nodo {label}, rol {role}, estado {state}",
        "edge": "Arista de {from_id} a {to_id}",
        "edge_with_label": "Arista de {from_id} a {to_id}, etiqueta {label}",
        "stack_item": "Entrada de pila a profundidad {depth}, valor {value}",
        "output_item": "Salida en posición {index}, valor {value}",
        "frontier_item": "Entrada de {kind} en posición {index}, valor {value}",
        "cell": "Celda en índice {index}, valor {value}",
        "cell_active": "Celda en índice {index}, valor {value}, activa",
        "pointer": "Puntero {label} en índice {position}",
        "code_line": "Línea de código {line_number}: {content}",
        "code_line_active": "Línea de código {line_number}, ejecutando ahora: {content}",
        "code_variable": "Variable {name} igual a {value}",
        "grid_cell": "Celda fila {row} columna {column}, valor {value}",
        "subexpression": "Subexpresión: {text}",
        "symbol": "Símbolo {symbol} ({meaning})",
        "whole_visual": "Visual completo: {base_type}",
    },
    "fr": {
        "node": "Nœud {label}, état {state}",
        "node_with_role": "Nœud {label}, rôle {role}, état {state}",
        "edge": "Arête de {from_id} à {to_id}",
        "edge_with_label": "Arête de {from_id} à {to_id}, étiquette {label}",
        "stack_item": "Entrée de pile à profondeur {depth}, valeur {value}",
        "output_item": "Sortie à la position {index}, valeur {value}",
        "frontier_item": "Entrée {kind} à la position {index}, valeur {value}",
        "cell": "Cellule à l'index {index}, valeur {value}",
        "cell_active": "Cellule à l'index {index}, valeur {value}, active",
        "pointer": "Pointeur {label} à l'index {position}",
        "code_line": "Ligne de code {line_number} : {content}",
        "code_line_active": "Ligne de code {line_number}, en cours d'exécution : {content}",
        "code_variable": "Variable {name} égale à {value}",
        "grid_cell": "Cellule ligne {row} colonne {column}, valeur {value}",
        "subexpression": "Sous-expression : {text}",
        "symbol": "Symbole {symbol} ({meaning})",
        "whole_visual": "Visuel complet : {base_type}",
    },
}


def localize_aria(
    key: str,
    locale: str | None = None,
    **kwargs: Any,
) -> str:
    """Format an aria-label by key + named substitutions.

    Falls back to English when the locale or key is missing. Returns the
    raw key when nothing resolves (signal to a missing catalog entry).
    """
    lang = (locale or DEFAULT_LOCALE).lower().split("-", 1)[0]
    table = _CATALOG.get(lang) or _CATALOG["en"]
    template = table.get(key) or _CATALOG["en"].get(key) or key
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template


def available_locales() -> tuple[str, ...]:
    return tuple(sorted(_CATALOG.keys()))
