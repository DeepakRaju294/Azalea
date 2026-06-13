"""Deterministic concept-visual simulators for the non-CS example types
(EXAMPLE_SYSTEM_SPEC §9.4 widening): set/Venn, coordinate plots, memory layout,
protocol timelines, geometric construction. Each emits one step per teaching move,
revealing a static structure progressively (the renderers are reveal-based). All
quantities are computed, never asserted.
"""

from __future__ import annotations

import math
from typing import Any

from ..schemas import CanonicalExample, Trace


def _trace(example: CanonicalExample, key: str, initial: dict, steps: list[dict[str, Any]]) -> Trace:
    return Trace(
        trace_id=f"{example.get('example_id', 'ex')}:{key}",
        example_id=str(example.get("example_id", "")),
        trace_source="deterministic_simulator",
        initial_state=initial,
        steps=steps,
        final_state={},
        simulator_version="1",
    )


def _stepper():
    steps: list[dict[str, Any]] = []

    def step(kind: str, delta: dict[str, Any], notice: str) -> None:
        steps.append({
            "trace_step_id": f"s{len(steps) + 1}", "kind": kind, "delta": delta,
            "primary_change": next(iter(delta)), "learner_should_notice": notice,
            "code_line_refs": [], "runtime_label": "",
        })

    return steps, step


# --- set_region (two-set union/intersection counting) ---------------------------

def simulate_set_operation(example: CanonicalExample) -> Trace:
    base = example.get("base_structure") or {}
    only_a = int(base.get("only_a", 0))
    only_b = int(base.get("only_b", 0))
    both = int(base.get("both", 0))
    a_total, b_total = only_a + both, only_b + both
    union = only_a + only_b + both
    steps, step = _stepper()

    step("mark_regions", {"set_active_set": "A", "set_shaded_regions": ["only_a", "both"],
                          "set_region_counts": {"A": a_total}},
         f"Set A has {a_total} elements ({only_a} unique + {both} shared).")
    step("mark_regions", {"set_active_set": "B", "set_shaded_regions": ["only_b", "both"],
                          "set_region_counts": {"A": a_total, "B": b_total}},
         f"Set B has {b_total} elements ({only_b} unique + {both} shared).")
    step("apply_operation", {"set_active_set": None, "set_shaded_regions": ["both"],
                             "set_region_counts": {"intersection": both}},
         f"A ∩ B is the overlap only: {both} elements in BOTH sets.")
    step("apply_operation", {"set_shaded_regions": ["only_a", "only_b", "both"],
                             "set_region_counts": {"union": union}},
         f"A ∪ B counts every region ONCE: {only_a} + {only_b} + {both} = {union}.")
    initial = {"active_set": None, "active_region": None, "shaded_regions": [], "region_counts": {}}
    return _trace(example, "set_operation", initial, steps)


# --- coordinate (analyse a parabola y = ax^2 + bx + c) --------------------------

def simulate_function_plot(example: CanonicalExample) -> Trace:
    p = dict(example.get("input") or {})
    a, b, c = float(p.get("a", 1)), float(p.get("b", 0)), float(p.get("c", 0))
    steps, step = _stepper()

    def _poly(a: float, b: float, c: float) -> str:
        lead = "x²" if a == 1 else ("-x²" if a == -1 else f"{a:g}x²")
        out = lead
        out += f" + {b:g}x" if b > 0 else (f" − {abs(b):g}x" if b < 0 else "")
        out += f" + {c:g}" if c > 0 else (f" − {abs(c):g}" if c < 0 else "")
        return out

    step("plot_object", {"set_active_curve": "f"},
         f"Plot the parabola y = {_poly(a, b, c)}.")
    step("mark_feature", {"set_active_point": "y_intercept", "set_point_value": f"(0, {c:g})"},
         f"The y-intercept is where x = 0: y = {c:g}.")
    disc = b * b - 4 * a * c
    if disc >= 0:
        r = math.sqrt(disc)
        x1, x2 = (-b - r) / (2 * a), (-b + r) / (2 * a)
        step("mark_feature", {"set_active_point": "roots", "set_point_value": f"x = {x1:g}, {x2:g}"},
             f"The roots (y = 0) are x = {x1:g} and x = {x2:g}.")
    vx = -b / (2 * a)
    vy = a * vx * vx + b * vx + c
    step("mark_feature", {"set_active_point": "vertex", "set_point_value": f"({vx:g}, {vy:g})"},
         f"The vertex (turning point) is at x = -b/2a = {vx:g}, y = {vy:g}.")
    step("conclude", {"set_active_point": None},
         f"Opening {'upward' if a > 0 else 'downward'}, vertex at ({vx:g}, {vy:g}).")
    initial = {"active_point": None, "active_curve": None}
    return _trace(example, "function_plot", initial, steps)


# --- memory (stack variable -> heap array) --------------------------------------

def simulate_stack_heap(example: CanonicalExample) -> Trace:
    steps, step = _stepper()
    step("setup_memory_state", {"set_visible_frames": ["main"], "set_visible_objects": []},
         "main() begins — a stack frame is pushed for its local variables.")
    step("allocate", {"set_visible_objects": ["arr"], "set_active_object": "arr"},
         "x = [1, 2, 3] allocates the list on the HEAP — a separate region for dynamic data.")
    step("bind_reference", {"set_active_pointer": "x_to_arr", "set_active_object": "arr"},
         "x on the stack holds a REFERENCE (an address), not the list itself.")
    step("show_final_state", {"set_active_pointer": None, "set_active_object": None},
         "The stack variable points into the heap — the core of how references work.")
    initial = {"active_frame": None, "active_object": None, "active_pointer": None,
               "visible_frames": [], "visible_objects": []}
    return _trace(example, "stack_heap", initial, steps)


# --- timeline (TCP three-way handshake) -----------------------------------------

def simulate_protocol_sequence(example: CanonicalExample) -> Trace:
    base = example.get("base_structure") or {}
    messages = list(base.get("messages") or [])
    steps, step = _stepper()
    visible: list[str] = []
    notices = {
        "SYN": "The client sends SYN — 'I want to connect; here's my starting sequence number.'",
        "SYN-ACK": "The server replies SYN-ACK — 'Acknowledged, and here's MY sequence number.'",
        "ACK": "The client sends ACK — 'Got it.' The connection is now ESTABLISHED.",
    }
    for m in messages:
        mid = str(m.get("id") or m.get("label"))
        visible = visible + [mid]
        step("send_event", {"set_active_message": mid, "set_visible_messages": list(visible)},
             notices.get(str(m.get("label")), f"{m.get('from')} → {m.get('to')}: {m.get('label')}."))
    step("conclude", {"set_active_message": None, "set_actor_states": {"client": "established", "server": "established"}},
         "Three messages establish a reliable connection before any data flows.")
    initial = {"active_actor": None, "active_message": None, "visible_messages": [], "actor_states": {}}
    return _trace(example, "protocol_sequence", initial, steps)


# --- geometric (right triangle, Pythagorean) ------------------------------------

def simulate_triangle_geometry(example: CanonicalExample) -> Trace:
    p = dict(example.get("input") or {})
    leg_a, leg_b = float(p.get("a", 3)), float(p.get("b", 4))
    hyp = math.sqrt(leg_a * leg_a + leg_b * leg_b)
    steps, step = _stepper()

    step("draw_base_figure", {"set_active_segment": None},
         "Draw the right triangle — the small square marks the 90° angle.")
    step("label_knowns", {"set_active_segment": "a", "add_measurement": {"a": f"{leg_a:g}"}},
         f"One leg measures {leg_a:g}.")
    step("label_knowns", {"set_active_segment": "b", "add_measurement": {"b": f"{leg_b:g}"}},
         f"The other leg measures {leg_b:g}.")
    step("apply_property", {"set_active_segment": "c",
                            "add_measurement": {"c²": f"{leg_a:g}² + {leg_b:g}² = {leg_a*leg_a + leg_b*leg_b:g}"}},
         f"Pythagoras: c² = a² + b² = {leg_a*leg_a:g} + {leg_b*leg_b:g} = {leg_a*leg_a + leg_b*leg_b:g}.")
    step("compute_measure", {"add_measurement": {"c": f"{hyp:g}"}},
         f"The hypotenuse is c = √{leg_a*leg_a + leg_b*leg_b:g} = {hyp:g}.")
    initial = {"active_point": None, "active_segment": None, "shaded_regions": [], "measurements": {}}
    return _trace(example, "triangle_geometry", initial, steps)


def simulate_comparison(example: CanonicalExample) -> Trace:
    """A side-by-side comparison table: one step per dimension row, plus a closing
    'when to use which' takeaway. Rows are authored in base_structure (the content
    is the fixture's truth)."""
    b = example.get("base_structure") or {}
    rows = list(b.get("rows") or [])      # [[dimension, left, right], ...]
    left = str(b.get("left_label", "A"))
    right = str(b.get("right_label", "B"))
    steps, step = _stepper()
    for i, row in enumerate(rows):
        dim = str(row[0]) if row else ""
        lv = str(row[1]) if len(row) > 1 else ""
        rv = str(row[2]) if len(row) > 2 else ""
        step("compare_dimension", {"set_active_row": i},
             f"{dim}: {left} uses {lv}; {right} uses {rv}.")
    takeaway = str(b.get("takeaway", ""))
    if takeaway:
        step("extract_rule", {"set_active_row": None}, takeaway)
    return _trace(example, "comparison", {"active_row": None, "active_cell": None}, steps)
