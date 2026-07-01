"""Missing-adapter demand tracker (ADAPTER_DEVELOPMENT_SPEC §coverage/routing).

When a COMPUTATIONAL topic (a coding/algorithmic implementation or walkthrough) has NO applicable adapter and
must defer to the weaker coverage-ladder paths, we RECORD it. Aggregated over time — once there are users —
this is the priority queue for which adapter to build next: the concepts learners actually request most often
while still unsupported. Append-only JSONL (concurrency-safe: every worker just appends); summarised on demand.

Nothing here ever raises into generation — demand tracking must never affect a lesson."""
from __future__ import annotations

import json
import os
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

# Topic types that WOULD benefit from an adapter (a determinate worked example). A concept/intro topic is not
# a "missing adapter" — it has no single worked instance to verify.
_COMPUTATIONAL_TYPES = {"coding_implementation", "truncated_coding_implementation",
                        "algorithm_walkthrough", "operation_walkthrough"}

_STOP = {"implementing", "implement", "implementation", "the", "a", "an", "of", "for", "in", "to", "with",
         "using", "and", "how", "code", "coding", "understanding", "introduction", "algorithm", "algorithms",
         "example", "examples", "solve", "solving", "compute", "computing",
         # language names: 'Radix Sort' and 'Radix Sort in Python' are the SAME missing adapter
         "python", "java", "cpp", "javascript", "typescript", "python3"}


def _log_path() -> Path:
    env = os.getenv("AZALEA_ADAPTER_DEMAND_LOG", "").strip()
    return Path(env) if env else Path(__file__).resolve().parents[3] / "logs" / "adapter_demand.jsonl"


def _signature(title: Any) -> str:
    """A normalized concept signature so 'Implementing Quick Sort' and 'Quick Sort in Python' aggregate to the
    same demand bucket (sorted significant tokens)."""
    toks = sorted({w for w in re.split(r"[^a-z0-9]+", str(title or "").lower())
                   if w and len(w) > 2 and w not in _STOP})
    return " ".join(toks)


def _get(topic: Any, key: str, default: Any = "") -> Any:
    return topic.get(key, default) if isinstance(topic, dict) else getattr(topic, key, default)


def record_unadapted_topic(topic: Any, *, has_adapter: bool | None = None) -> bool:
    """Record demand IFF the topic is computational AND has no adapter. `has_adapter` can be passed to avoid a
    re-route; otherwise it is computed. Returns whether an event was recorded. Never raises."""
    try:
        ttype = str(_get(topic, "topic_type", "") or _get(topic, "course_type", "") or "").lower()
        if ttype not in _COMPUTATIONAL_TYPES:
            return False
        if has_adapter is None:
            from .trace_pipeline import route_adapter
            has_adapter = route_adapter(topic if isinstance(topic, dict)
                                        else {"title": _get(topic, "title"), "topic_type": ttype}) is not None
        if has_adapter:
            return False
        title = str(_get(topic, "title", "") or _get(topic, "name", "") or "").strip()
        sig = _signature(title)
        if not sig:
            return False
        event = {"signature": sig, "title": title, "topic_type": ttype,
                 "topic_id": str(_get(topic, "id", "") or ""), "ts": time.time()}
        path = _log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        return True
    except Exception:  # noqa: BLE001 — demand tracking must never break a lesson
        return False


def summarize(min_count: int = 1) -> list[dict[str, Any]]:
    """Aggregate the demand log into ranked buckets: the most-requested UNSUPPORTED concepts first. Each bucket
    has count · distinct titles seen · first/last timestamps. This is the 'build these adapters next' queue."""
    path = _log_path()
    if not path.exists():
        return []
    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "titles": set(), "topic_types": set(), "first_ts": None, "last_ts": None})
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                e = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            b = buckets[str(e.get("signature") or "")]
            b["count"] += 1
            b["titles"].add(str(e.get("title") or ""))
            b["topic_types"].add(str(e.get("topic_type") or ""))
            ts = e.get("ts")
            if isinstance(ts, (int, float)):
                b["first_ts"] = ts if b["first_ts"] is None else min(b["first_ts"], ts)
                b["last_ts"] = ts if b["last_ts"] is None else max(b["last_ts"], ts)
    except Exception:  # noqa: BLE001
        return []
    out = [{"signature": sig, "count": b["count"], "distinct_titles": sorted(b["titles"])[:5],
            "topic_types": sorted(b["topic_types"]), "first_ts": b["first_ts"], "last_ts": b["last_ts"]}
           for sig, b in buckets.items() if b["count"] >= min_count]
    return sorted(out, key=lambda x: x["count"], reverse=True)
