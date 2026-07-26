"""Validate the computational-API (Wolfram) backend against the REAL API.

Reads AZALEA_WOLFRAM_APPID from backend/.env, queries the engine for each curated concept, and reports:
  - the raw response's pod titles (so we can confirm parse_wolfram_answer targets the right pod),
  - the parsed answer,
  - whether the parsed answer REPRODUCES the curated expected value (compare_answer over the corpus entry).

This is the one piece that couldn't be validated offline (the real JSON shape). Run it; if the parser needs
adjustment for the actual response, the pod-title dump shows exactly what to target.

    cd backend && ./venv/Scripts/python.exe -m scripts.validate_wolfram
"""
from __future__ import annotations

import json
import os
import sys


def _load_env() -> None:
    try:
        from app.core import deps
        deps.load_dotenv()   # same loader the app uses
    except Exception:  # noqa: BLE001
        # minimal fallback: parse backend/.env
        from pathlib import Path
        env = Path(__file__).resolve().parents[1] / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.strip() and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())


def main() -> int:
    _load_env()
    from app.services.examples.retrieval import sources
    from app.services.examples.retrieval.compare import compare_answer
    from app.services.examples.retrieval.compute_backend import (
        _QUERY_TEMPLATES, parse_wolfram_answer, wolfram_transport,
    )

    if not os.getenv("AZALEA_WOLFRAM_APPID"):
        print("NO AZALEA_WOLFRAM_APPID in backend/.env — paste your AppID after the = and re-run.")
        return 2

    print(f"{'concept':<20}{'expected':<12}{'wolfram_answer':<22}{'reproduces':<12}pods")
    print("-" * 100)
    match = total = 0
    for concept, query in _QUERY_TEMPLATES.items():
        entry = sources.lookup(concept)
        expected = entry.payload.published_answer if entry else "?"
        raw = wolfram_transport(query)
        if not raw:
            print(f"{concept:<20}{expected:<12}{'<no response>':<22}{'-':<12}(transport miss)")
            continue
        total += 1
        try:
            pods = [str(p.get("title", "")) for p in json.loads(raw).get("queryresult", {}).get("pods", [])]
        except (json.JSONDecodeError, AttributeError):
            pods = ["<unparseable json>"]
        answer = parse_wolfram_answer(raw) or "<none>"
        outcome = compare_answer(expected, answer, entry.payload.comparison) if entry else None
        repro = outcome.status if outcome else "n/a"
        if repro == "confirm":
            match += 1
        print(f"{concept:<20}{expected:<12}{answer[:20]:<22}{repro:<12}{pods}")
    print("-" * 100)
    print(f"reproduced (confirm) {match}/{total}. If answers look right but 'reproduces' isn't 'confirm', the "
          "parser/comparison may need a tweak for the real answer wording (e.g. '1 volt' vs '1 V').")
    return 0


if __name__ == "__main__":
    sys.exit(main())
