"""Card-generation failure log (#3).

Every time a required lesson card fails to generate, comes out empty, or is dropped, record WHAT card,
WHERE in the pipeline, and WHY — durably — so silent drops (the malformed 2-card Kruskal topic) become
a queryable dataset: which families/cards fail, the reason, and whether a backfill recovered them.

Sink is ``AZALEA_CARD_FAILURE_LOG_PATH`` (one JSON line per event); with none set it logs at WARNING so
the event is at least visible. Best-effort — logging a failure must never raise into generation.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Optional

_log = logging.getLogger(__name__)


def log_card_failure(
    *,
    topic: Optional[dict[str, Any]] = None,
    topic_id: str = "",
    topic_type: str = "",
    topic_family: str = "",
    card_key: str,
    stage: str,
    reason: str,
    action: str = "dropped",       # dropped | regenerated | fallback | withheld
    detail: str = "",
    path: Optional[str] = None,
) -> None:
    """Record one card failure/drop. `stage` = where (input_gen / solver / materialization / validation /
    plan_path / blueprint_enforcement / backfill); `action` = what we did about it."""
    if topic:
        topic_id = topic_id or str(topic.get("id") or topic.get("title") or "?")
        topic_type = topic_type or str(topic.get("topic_type") or topic.get("course_type") or "")
        topic_family = topic_family or str(topic.get("topic_family") or topic.get("family") or "")
    record = {
        "ts": datetime.utcnow().isoformat(timespec="seconds"),
        "topic_id": topic_id, "topic_type": topic_type, "topic_family": topic_family,
        "card_key": card_key, "stage": stage, "reason": reason, "action": action, "detail": detail,
    }
    try:
        line = json.dumps(record, ensure_ascii=False)
        sink = path or os.getenv("AZALEA_CARD_FAILURE_LOG_PATH")
        if not sink:
            _log.warning("card_failure %s", line)
            return
        with open(sink, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception as exc:  # noqa: BLE001 — logging a failure must never break generation
        _log.warning("card_failure log write failed (%s): %s/%s %s", exc, card_key, stage, reason)
