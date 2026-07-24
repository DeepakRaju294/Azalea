"""app/core/decision_trace_coverage.py — the AST-based scanner that makes decision-trace silence legible
(does a file have ANY recognizable logging call, and does a persisted stage string still match a real call
site in current source). Fixture-based tests use temp .py files for stable, assertable line numbers; the
smoke test at the bottom checks the real repo but only for stage/file/logger, never a line number.

Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_decision_trace_coverage
"""
import os
import shutil
import tempfile
import textwrap
import unittest
from pathlib import Path

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.core.decision_trace_coverage import (
    DEFAULT_APP_ROOT, display_path, file_status, files_with_decision_trace_calls, resolve_stage,
    scan_decision_trace_call_sites,
)


class _FixtureCase(unittest.TestCase):
    """Writes fixture .py files into a fresh temp dir (guaranteed OUTSIDE BACKEND_ROOT) per test."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="decision_trace_coverage_test_")
        self.root = Path(self._tmpdir)

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _write(self, name: str, content: str) -> Path:
        p = self.root / name
        p.write_text(textwrap.dedent(content), encoding="utf-8")
        return p

    def _scan(self):
        return scan_decision_trace_call_sites(root=self.root)


class CallDetection(_FixtureCase):
    def test_bare_name_call_is_detected(self):
        self._write("a.py", """
            from app.core.decision_trace import record_path_decision
            def f(plan):
                record_path_decision(plan, "curriculum.thin_plan_retry", "retried", "why")
        """)
        result = self._scan()
        self.assertEqual(len(result.call_sites), 1)
        site = result.call_sites[0]
        self.assertEqual(site.stage, "curriculum.thin_plan_retry")
        self.assertEqual(site.logger, "record_path_decision")
        self.assertEqual(site.file, "a.py")

    def test_attribute_qualified_call_is_detected(self):
        self._write("a.py", """
            from app.core import decision_trace
            def f(topic):
                decision_trace.record_topic_decision(topic, "adapter.rejected", "d", "r")
        """)
        result = self._scan()
        self.assertEqual(len(result.call_sites), 1)
        self.assertEqual(result.call_sites[0].stage, "adapter.rejected")
        self.assertEqual(result.call_sites[0].logger, "record_topic_decision")

    def test_keyword_form_stage_is_detected(self):
        self._write("a.py", """
            from app.core.decision_trace import record_topic_decision
            def f(topic):
                record_topic_decision(topic, decision="d", reason="r", stage="scope.out_backfilled")
        """)
        result = self._scan()
        self.assertEqual(result.call_sites[0].stage, "scope.out_backfilled")

    def test_positional_form_stage_is_detected(self):
        self._write("a.py", """
            from app.core.decision_trace import record_topic_decision
            def f(topic):
                record_topic_decision(topic, "identity.assigned", "d", "r")
        """)
        result = self._scan()
        self.assertEqual(result.call_sites[0].stage, "identity.assigned")

    def test_dynamic_stage_yields_none_with_raw_source_captured(self):
        self._write("a.py", """
            from app.core.decision_trace import record_topic_decision
            def f(topic, kind):
                record_topic_decision(topic, f"dedup.{kind}_collapsed", "d", "r")
        """)
        result = self._scan()
        site = result.call_sites[0]
        self.assertIsNone(site.stage)
        self.assertTrue(site.raw_call_source)   # never empty/None
        self.assertIn("record_topic_decision", site.raw_call_source)

    def test_two_dynamic_stage_sites_are_not_collapsed(self):
        self._write("a.py", """
            from app.core.decision_trace import record_topic_decision
            def f(topic, kind):
                record_topic_decision(topic, f"dedup.{kind}_a", "d", "r")
                record_topic_decision(topic, f"dedup.{kind}_b", "d", "r")
        """)
        result = self._scan()
        self.assertEqual(len(result.call_sites), 2)
        self.assertTrue(all(s.stage is None for s in result.call_sites))
        self.assertEqual(len({s.line for s in result.call_sites}), 2)   # two distinct lines, not collapsed

    def test_reassigned_alias_is_not_detected(self):
        # Documented limitation, not a silent gap — this test pins the behavior explicitly.
        self._write("a.py", """
            from app.core.decision_trace import record_topic_decision
            def f(topic):
                logger = record_topic_decision
                logger(topic, "adapter.rejected", "d", "r")
        """)
        result = self._scan()
        self.assertEqual(result.call_sites, [])


class AmbiguousAndUnresolvedStages(_FixtureCase):
    def test_same_stage_twice_in_one_file_is_ambiguous_not_resolved(self):
        self._write("a.py", """
            from app.core.decision_trace import record_topic_decision
            def f(topic):
                record_topic_decision(topic, "adapter.rejected", "d1", "r1")
                record_topic_decision(topic, "adapter.rejected", "d2", "r2")
        """)
        result = self._scan()
        outcome, sites = resolve_stage("adapter.rejected", result)
        self.assertEqual(outcome, "ambiguous")
        self.assertEqual(len({s.line for s in sites}), 2)   # both call sites present, distinct lines

    def test_unknown_stage_is_unresolved(self):
        self._write("a.py", """
            from app.core.decision_trace import record_topic_decision
            def f(topic):
                record_topic_decision(topic, "adapter.rejected", "d", "r")
        """)
        result = self._scan()
        outcome, sites = resolve_stage("this.stage.does.not.exist", result)
        self.assertEqual(outcome, "unresolved")
        self.assertEqual(sites, [])

    def test_unique_stage_is_resolved(self):
        self._write("a.py", """
            from app.core.decision_trace import record_topic_decision
            def f(topic):
                record_topic_decision(topic, "adapter.rejected", "d", "r")
        """)
        result = self._scan()
        outcome, sites = resolve_stage("adapter.rejected", result)
        self.assertEqual(outcome, "resolved")
        self.assertEqual(len(sites), 1)


class ParseFailuresStayVisible(_FixtureCase):
    def test_syntax_error_file_is_reported_not_silently_skipped(self):
        self._write("broken.py", "def f(:\n    this is not valid python\n")
        self._write("clean.py", """
            from app.core.decision_trace import record_topic_decision
            def f(topic):
                record_topic_decision(topic, "adapter.rejected", "d", "r")
        """)
        result = self._scan()
        self.assertEqual(len(result.parse_errors), 1)
        self.assertEqual(result.parse_errors[0]["file"], "broken.py")
        self.assertNotIn("broken.py", result.scanned_files)
        self.assertIn("clean.py", result.scanned_files)
        # the clean file's call site is still found despite the sibling failure
        self.assertEqual(len(result.call_sites), 1)

    def test_parse_failure_reports_unknown_not_no_instrumentation(self):
        self._write("broken.py", "def f(:\n    invalid\n")
        result = self._scan()
        self.assertEqual(file_status("broken.py", result), "unknown")

    def test_clean_zero_call_file_reports_no_instrumentation(self):
        self._write("empty.py", "x = 1\n")
        result = self._scan()
        self.assertEqual(file_status("empty.py", result), "no instrumentation detected")

    def test_file_with_calls_reports_some_instrumentation(self):
        self._write("a.py", """
            from app.core.decision_trace import record_topic_decision
            def f(topic):
                record_topic_decision(topic, "adapter.rejected", "d", "r")
        """)
        result = self._scan()
        self.assertEqual(file_status("a.py", result), "some instrumentation detected")
        self.assertEqual(files_with_decision_trace_calls(result), {"a.py": 1})


class DisplayPathOutsideBackendRoot(_FixtureCase):
    def test_fixture_root_outside_backend_root_does_not_raise(self):
        self._write("a.py", "x = 1\n")
        # the temp fixture dir is guaranteed outside BACKEND_ROOT; display_path must not raise
        path = self.root / "a.py"
        rendered = display_path(path, self.root)
        self.assertEqual(rendered, "a.py")


class RealRepoSmokeTest(unittest.TestCase):
    """Checks the real repo via DEFAULT_APP_ROOT. Stage/file/logger only — never a line number, which
    would break on unrelated edits. No assertion that trace_pipeline.py has zero call sites (that fact is
    surfaced only via scripts/explain_path.py's report, so phase 2 adding real coverage there doesn't break
    this test suite by succeeding)."""

    def test_a_known_stable_stage_resolves_in_current_source(self):
        result = scan_decision_trace_call_sites()
        outcome, sites = resolve_stage("topics.foundation_kept_core_requirement", result)
        self.assertEqual(outcome, "resolved")
        self.assertEqual(sites[0].logger, "record_path_decision")
        self.assertEqual(sites[0].file, "app/services/topic_decomposition_pipeline.py")

    def test_no_test_files_leak_into_the_default_scan(self):
        result = scan_decision_trace_call_sites()
        self.assertFalse(any(c.file.startswith("app/tests/") for c in result.call_sites))
        self.assertFalse(any(f.startswith("app/tests/") for f in result.scanned_files))

    def test_default_app_root_is_anchored_to_file_not_cwd(self):
        self.assertTrue(DEFAULT_APP_ROOT.is_dir())
        self.assertTrue(DEFAULT_APP_ROOT.name == "app")


if __name__ == "__main__":
    unittest.main()
