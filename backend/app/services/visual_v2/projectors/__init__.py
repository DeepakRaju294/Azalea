"""Per-shape state projectors (PROJECTOR_SYSTEM_SPEC §4, §13).

A projector turns a runtime trace into a shape's per-step visual deltas. It contains
no algorithm logic and never branches on the application name — it only reads named
variables out of a trace and normalizes them. node_link is the first shape; sequence
and grid follow the same contract+reader+validator pattern.
"""
