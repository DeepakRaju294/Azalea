"""THE canonical interactive-link quality report.

One name (`interactive_link_report`), one shape, written by every pipeline that touches links —
lean emission, the legacy validator (future-card regeneration), and core-text-only mode — so
operational monitoring never has to reconcile competing report keys/fields again.
`is_valid` is authoritative; `passed`/`removed_link_count` are kept for existing readers
(topic_quality_validator) and older stored lessons.
"""
from __future__ import annotations

from typing import Any

LINK_REPORT_KEY = "interactive_link_report"
LINK_CONTRACT = "prereq_links_v1"


def build_link_report(
    cards: list[dict[str, Any]] | None,
    *,
    source: str,
    removed_count: int = 0,
    repaired_card_count: int = 0,
    issues: list[str] | None = None,
) -> dict[str, Any]:
    """Build the canonical report from the FINAL cards (post-validation/repair).

    kept counts come from what actually survived on the cards; `generated_count` = kept + removed,
    so `removed_count` reads as "how much the validators had to take away".
    """
    issues = list(issues or [])
    kept_count = 0
    counts_by_action: dict[str, int] = {}
    for card in cards or []:
        if not isinstance(card, dict):
            continue
        for link in card.get("interactive_links") or []:
            if not isinstance(link, dict):
                continue
            kept_count += 1
            action = str(link.get("action") or "unknown")
            counts_by_action[action] = counts_by_action.get(action, 0) + 1
    return {
        "contract": LINK_CONTRACT,
        "source": source,
        "is_valid": not issues,
        "passed": not issues,                    # legacy alias
        "generated_count": kept_count + removed_count,
        "kept_count": kept_count,
        "removed_link_count": removed_count,     # legacy field name, read by topic_quality_validator
        "repaired_card_count": repaired_card_count,
        "counts_by_action": counts_by_action,
        "issues": issues,
    }


def attach_link_report(lesson_json: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    """Write the canonical report under the ONE canonical key."""
    lesson_json[LINK_REPORT_KEY] = report
    return report
