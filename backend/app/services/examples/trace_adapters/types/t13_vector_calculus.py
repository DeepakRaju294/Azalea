"""T13 — Proof-obligation discharge, hand-coded member. Kept SEPARATE from t13_proof.py (which is exclusively
the induction engine's auto-generated declarations) — this file is for hand-coded T13 adapters, mirroring how
t11_backtracking.py holds hand-coded T11 declarations alongside declarative ones elsewhere."""
from . import declare
from ..families.vector_calculus import (DivergenceTheoremAdapter, LineIntegralAdapter,
                                        StokesTheoremAdapter, SurfaceIntegralAdapter)

STOKES_THEOREM = declare(StokesTheoremAdapter, "stokes_theorem", "T13")
LINE_INTEGRAL = declare(LineIntegralAdapter, "line_integral", "T13")
SURFACE_INTEGRAL = declare(SurfaceIntegralAdapter, "surface_integral", "T13")
DIVERGENCE_THEOREM = declare(DivergenceTheoremAdapter, "divergence_theorem", "T13")

DECLARATIONS = [STOKES_THEOREM, LINE_INTEGRAL, SURFACE_INTEGRAL, DIVERGENCE_THEOREM]
