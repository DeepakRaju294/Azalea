"""T13 — Proof-obligation discharge, hand-coded member. Kept SEPARATE from t13_proof.py (which is exclusively
the induction engine's auto-generated declarations) — this file is for hand-coded T13 adapters, mirroring how
t11_backtracking.py holds hand-coded T11 declarations alongside declarative ones elsewhere."""
from . import declare
from ..families.vector_calculus import StokesTheoremAdapter

STOKES_THEOREM = declare(StokesTheoremAdapter, "stokes_theorem", "T13")

DECLARATIONS = [STOKES_THEOREM]
