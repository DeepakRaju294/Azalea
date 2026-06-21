"""Generation foundation — shadow schemas + deterministic validators.

Implements GENERATION_AND_VISUAL_FOUNDATION_SPEC §12 step 1: the new card
contracts (§4), the semantic-state keystone (§7), trace/projection (§5), the
projection caps (§5.2), projection-coverage (§9.1), and trace-confidence metadata
(§6). Pure and unit-tested; **nothing here is wired into production** — it is built
behind the shadow flag so it can be measured before replacing the legacy solver.

No module here calls an LLM, renders a card, or touches the DB.
"""
from __future__ import annotations

SPEC_VERSION = "v11"  # GENERATION_AND_VISUAL_FOUNDATION_SPEC text pipeline
