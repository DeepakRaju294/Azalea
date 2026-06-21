"""Offline-safe LLM adapters (spec §1).

Mirrors the existing ``examples.solver._default_solver`` contract: a callable taking a
``{"system","user"}`` payload and returning parsed JSON (or ``None`` when no API key /
on failure), so the pipeline never makes a network call in tests or offline enrichment.
These are the production seam; the pipeline accepts injected fakes for testing.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Callable, Optional

_log = logging.getLogger(__name__)

# A model call: payload -> parsed JSON object (or None on skip/failure).
ModelFn = Callable[[dict[str, str]], Optional[dict[str, Any]]]


def _call(payload: dict[str, str]) -> Optional[dict[str, Any]]:
    key = os.getenv("OPENAI_API_KEY")
    if not key or key.strip().lower() == "dummy":
        return None
    try:
        from app.services.llm_client import OPENAI_MODEL, client, llm_call

        with llm_call("worked_example_gf"):  # label this call in the usage CSV
            response = client.with_options(
                timeout=float(os.getenv("AZALEA_ENRICH_TIMEOUT_SECONDS", "60")),
                max_retries=max(0, int(os.getenv("AZALEA_ENRICH_MAX_RETRIES", "2"))),
            ).responses.create(
                model=OPENAI_MODEL,
                input=[
                    {"role": "system", "content": payload.get("system", "")},
                    {"role": "user", "content": payload.get("user", "")},
                ],
                text={"format": {"type": "json_object"}},
            )
        return json.loads(response.output_text)
    except Exception as exc:  # noqa: BLE001 — a failed call is non-fatal for the shadow path
        _log.warning("gen_foundation model call failed: %s", exc)
        return None


# Same underlying call for all three roles; the payload's system prompt differentiates.
default_solver: ModelFn = _call
default_auditor: ModelFn = _call
default_repair: ModelFn = _call
