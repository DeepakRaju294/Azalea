"""Decision-trace COVERAGE — makes silence in `decision_trace.py`'s trace legible instead of ambiguous.

A persisted trace tells you what fired. It says nothing about what DIDN'T — and "no entry from this layer"
is genuinely ambiguous: it could mean nothing applied, or it could mean nobody ever wired that code path to
log at all (confirmed this session: `app/services/examples/trace_pipeline.py` has zero decision-trace calls,
and several real bugs lived exactly there, invisible to the trace).

This module answers "which decision points actually exist in source" by SCANNING for them via `ast`, not by
maintaining a hand-written registry — a hand list would just reintroduce the same drift problem (call sites
added/renamed/removed with nobody updating a separate list). The scan is the source of truth, always fresh.

Two distinct questions, kept separate on purpose:
  - `file_status()` / `files_with_decision_trace_calls()`: does this FILE contain any recognizable call at
    all? Presence only — one call in a 9,000-line file does not mean the file's other paths are covered.
  - `resolve_stage()`: for one STAGE STRING from a persisted trace, does it match a call site in the
    CURRENT source tree? "resolved" is a claim about source NOW, never proof a historical generation ran
    that exact line — source can (and does) change between when a path was generated and when it's read.

Scanner limitations, stated once here rather than silently: reassigned/aliased call references
(`record = record_topic_decision; record(...)`) are not tracked, and an `ast.Attribute` match
(`x.record_topic_decision(...)`) is syntactic, not type-checked — some unrelated object with a same-named
method would also match. This measures recognizable direct-call syntax, not every theoretically possible
invocation."""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# app/core/decision_trace_coverage.py -> app/core/ -> app/ -> backend/
BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_APP_ROOT = BACKEND_ROOT / "app"
_DEFAULT_EXCLUDE = ("app/tests/",)   # only applied when scanning the real app tree (never for fixture scans)

_LOGGER_NAMES = frozenset({"record_path_decision", "record_topic_decision", "record_lesson_decision"})


@dataclass
class CallSite:
    stage: Optional[str]        # literal value if statically extractable, else None (dynamic)
    raw_call_source: str        # source segment of the call — always a str, never None
    file: str                   # see display_path() for the exact relativization policy
    line: int
    logger: str                 # one of _LOGGER_NAMES


@dataclass
class CoverageScanResult:
    call_sites: list[CallSite] = field(default_factory=list)      # sorted by (file, line)
    scanned_files: list[str] = field(default_factory=list)        # successfully parsed, INCLUDING zero-call files
    parse_errors: list[dict] = field(default_factory=list)        # [{"file": str, "error": str}, ...]


def display_path(path: Path, scan_root: Path) -> str:
    """Report relative to BACKEND_ROOT when the file lives under it (the normal real-tree scan); otherwise
    (a fixture scan rooted outside BACKEND_ROOT) relative to the supplied scan_root instead of raising."""
    try:
        return path.relative_to(BACKEND_ROOT).as_posix()
    except ValueError:
        return path.relative_to(scan_root).as_posix()


def _stage_from_call(call: ast.Call, source: str) -> Optional[str]:
    # 1. second positional argument, if a string literal
    if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant) and isinstance(call.args[1].value, str):
        return call.args[1].value
    # 2. stage= keyword argument, if a string literal
    for kw in call.keywords:
        if kw.arg == "stage" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return kw.value.value
    # 3. dynamic — not statically extractable
    return None


def _raw_source(call: ast.Call, source: str) -> str:
    seg = ast.get_source_segment(source, call)
    if seg:
        return seg
    try:
        return ast.unparse(call)
    except Exception:  # noqa: BLE001 — raw_call_source must always be a truthful str, never None
        return ""


def _logger_name(call: ast.Call) -> Optional[str]:
    fn = call.func
    if isinstance(fn, ast.Name) and fn.id in _LOGGER_NAMES:
        return fn.id
    if isinstance(fn, ast.Attribute) and fn.attr in _LOGGER_NAMES:
        return fn.attr
    return None


def scan_decision_trace_call_sites(root: Path = DEFAULT_APP_ROOT,
                                   exclude: tuple[str, ...] = ()) -> CoverageScanResult:
    """Walk every .py file under `root`, find recognizable record_*_decision(...) calls via ast, and report
    them. Never raises: a file that fails to read or parse is recorded in `parse_errors` and skipped, the
    scan continues. `exclude` defaults to nothing for an explicit root (fixture tests); the real-tree default
    (`root is DEFAULT_APP_ROOT` and no explicit exclude) applies `_DEFAULT_EXCLUDE` so test files can never
    make a production file/layer look instrumented."""
    if not exclude and root == DEFAULT_APP_ROOT:
        exclude = _DEFAULT_EXCLUDE

    call_sites: list[CallSite] = []
    scanned_files: list[str] = []
    parse_errors: list[dict] = []

    for path in sorted(root.rglob("*.py")):
        rel = display_path(path, root)
        if any(rel.startswith(prefix) for prefix in exclude):
            continue
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=rel)
        except (SyntaxError, UnicodeDecodeError, OSError) as exc:
            parse_errors.append({"file": rel, "error": f"{type(exc).__name__}: {exc}"})
            continue
        scanned_files.append(rel)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            logger = _logger_name(node)
            if logger is None:
                continue
            call_sites.append(CallSite(
                stage=_stage_from_call(node, source), raw_call_source=_raw_source(node, source),
                file=rel, line=node.lineno, logger=logger))

    call_sites.sort(key=lambda c: (c.file, c.line))
    scanned_files.sort()
    parse_errors.sort(key=lambda e: e["file"])
    return CoverageScanResult(call_sites=call_sites, scanned_files=scanned_files, parse_errors=parse_errors)


def file_status(file: str, result: CoverageScanResult) -> str:
    """"unknown" (file is in parse_errors — status genuinely can't be determined; NEVER reported as "no
    instrumentation detected", which would recreate the exact misleading-silence problem this tool exists
    to fix), "some instrumentation detected" (scanned clean, >=1 call site), or "no instrumentation
    detected" (scanned clean, zero call sites)."""
    if any(e["file"] == file for e in result.parse_errors):
        return "unknown"
    count = sum(1 for c in result.call_sites if c.file == file)
    return "some instrumentation detected" if count else "no instrumentation detected"


def files_with_decision_trace_calls(result: CoverageScanResult) -> dict[str, int]:
    """file -> call count, for files with >=1 call site. PRESENCE ONLY — never implies the surrounding
    file/layer is covered; a single call in a large file establishes nothing about the rest of it."""
    counts: dict[str, int] = {}
    for c in result.call_sites:
        counts[c.file] = counts.get(c.file, 0) + 1
    return counts


def resolve_stage(stage: str, result: CoverageScanResult) -> tuple[str, list[CallSite]]:
    """"resolved" (exactly one current call site for this literal stage — even multiple sites in the SAME
    file stay "ambiguous", never silently downgraded to "resolved" just because the file agrees),
    "ambiguous" (multiple current call sites), or "unresolved" (no current literal match — renamed, removed,
    or was always dynamic). "resolved" is a claim about the CURRENT source tree, not proof a historical
    generation actually ran that exact file/line."""
    sites = [c for c in result.call_sites if c.stage == stage]
    if len(sites) == 1:
        return "resolved", sites
    if len(sites) > 1:
        return "ambiguous", sites
    return "unresolved", []


# A small, ADMITTED, hand-maintained presentation grouping — NOT a stage registry. Nothing is enforced
# against this list; it exists purely so a report can group files into architecturally meaningful sections
# instead of an unordered flat list. Unlike the AST-scanned call sites, this can go stale (a file moves,
# a new file joins a layer) without corrupting any data — worst case a mis-grouped label, caught by
# inspection whenever someone touches this area.
PIPELINE_LAYERS: dict[str, list[str]] = {
    "curriculum_decomposition": [
        "app/services/topic_decomposition_pipeline.py",
        "app/services/topic_generator.py",
        "app/core/topic_decomposition_validator.py",
        "app/services/domain_gate.py",
    ],
    "lesson_generation": [
        "app/services/lean_lesson_generator.py",
    ],
    "worked_example_pipeline": [
        "app/services/examples/trace_pipeline.py",
        "app/services/examples/handoff.py",
    ],
}
