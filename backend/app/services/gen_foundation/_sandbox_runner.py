"""Standalone sandbox runner — executes one snippet in a SEPARATE process (isolation + hard timeout).

Invoked as ``python -m app.services.gen_foundation._sandbox_runner <in.json> <out.json>``. Reads
{code, language, input}, runs the in-process executor (AST-gated + bounded), and writes the structured
result back as JSON. A crash or hang here cannot take down the generation worker, and the parent's
subprocess timeout is a hard kill the in-process step-budget can't guarantee against a tight loop.
"""
import json
import sys


def main() -> int:
    infile, outfile = sys.argv[1], sys.argv[2]
    with open(infile, encoding="utf-8") as fh:
        payload = json.load(fh)
    # executor imports only stdlib (+ the light package __init__), so this stays cheap.
    from app.services.gen_foundation.executor import execute

    res = execute(payload["code"], payload.get("language", "python"), payload.get("input"))
    out = {
        "status": res.status, "skip_reason": res.skip_reason, "trace_events": res.trace_events,
        "return_value": res.return_value, "exception": res.exception, "elapsed_ms": res.elapsed_ms,
    }
    with open(outfile, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
