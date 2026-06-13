"""Compilers — translate folded FrameState[] into a renderer-consumable VisualModel.

A compiler STYLES the trace (semantic states, layout, panels); it never re-decides
it (no changing active elements, visited sets, output — VISUAL_SYSTEM_SPEC §6.3).
"""
