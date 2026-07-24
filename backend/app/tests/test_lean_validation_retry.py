"""build_lean_lesson_from_topic_and_chunks: the lean pipeline computes scope/quality/microcheck validation
reports (_attach_lean_validation_reports) but, before this fix, never acted on them — a lesson flagged
requires_regeneration=True still shipped as-is. Live bug: a concept_intuition topic shipped ~100% off its
own certified scope, with zero practice questions, both correctly flagged and both silently ignored.

Fixed: one retry, with feedback built from whichever validator(s) flagged requires_regeneration, keeping
whichever attempt has fewer outstanding issues (or a clean pass). Tests mock _convert_lean_to_legacy
directly (its own correctness is covered by test_card_cosmetics.py / test_math_sanitize.py) so this file
verifies only the retry ORCHESTRATION in build_lean_lesson_from_topic_and_chunks.

Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_lean_validation_retry
"""
import os
import unittest
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services import lean_lesson_generator as llg


def _topic():
    return SimpleNamespace(
        id="t1", title="Vector Calculus Basics", description="", course_type="concept_intuition",
        topic_type="concept_intuition", order_index=1, study_path_id="s1",
    )


def _report(cards_flag: str, requires: bool, issues=None):
    return {"requires_regeneration": requires, "issues": issues or []}


def _lesson(requires: bool, n_issues: int = 1):
    issues = [f"issue {i}" for i in range(n_issues)] if requires else []
    return {
        "lesson_cards": [{"blueprint_key": "background", "points": ["p"]}],
        "scope_validation_report": _report("scope", requires, issues),
        "topic_quality_report": _report("quality", False, []),
        "microcheck_validation_report": _report("micro", False, []),
        "validation_report": _report("combined", requires, issues),
    }


class RetriesOnceOnRequiresRegeneration(unittest.TestCase):
    def test_retries_once_and_ships_the_cleaner_attempt(self):
        bad, good = _lesson(True, n_issues=3), _lesson(False)
        calls = []

        def fake_convert(lean_json, topic, chunks):
            calls.append(1)
            return bad if len(calls) == 1 else good

        with mock.patch.object(llg, "generate_lean_structured_lesson", return_value={"cards": []}), \
             mock.patch.object(llg, "_convert_lean_to_legacy", side_effect=fake_convert), \
             mock.patch.object(llg, "_assert_lesson_is_renderable", return_value=None):
            result = llg.build_lean_lesson_from_topic_and_chunks(_topic(), [])

        self.assertEqual(len(calls), 2)   # retried exactly once, not looped
        self.assertFalse(result["validation_report"]["requires_regeneration"])   # shipped the clean retry

    def test_no_retry_when_the_first_attempt_already_passes(self):
        good = _lesson(False)
        calls = []

        def fake_convert(lean_json, topic, chunks):
            calls.append(1)
            return good

        with mock.patch.object(llg, "generate_lean_structured_lesson", return_value={"cards": []}), \
             mock.patch.object(llg, "_convert_lean_to_legacy", side_effect=fake_convert), \
             mock.patch.object(llg, "_assert_lesson_is_renderable", return_value=None):
            llg.build_lean_lesson_from_topic_and_chunks(_topic(), [])

        self.assertEqual(len(calls), 1)   # no retry needed

    def test_retry_that_is_still_worse_or_equal_keeps_the_original(self):
        first, retry = _lesson(True, n_issues=2), _lesson(True, n_issues=5)
        calls = []

        def fake_convert(lean_json, topic, chunks):
            calls.append(1)
            return first if len(calls) == 1 else retry

        with mock.patch.object(llg, "generate_lean_structured_lesson", return_value={"cards": []}), \
             mock.patch.object(llg, "_convert_lean_to_legacy", side_effect=fake_convert), \
             mock.patch.object(llg, "_assert_lesson_is_renderable", return_value=None):
            result = llg.build_lean_lesson_from_topic_and_chunks(_topic(), [])

        self.assertEqual(len(calls), 2)
        self.assertEqual(len(result["validation_report"]["issues"]), 2)   # kept the original (fewer issues)

    def test_a_raising_retry_keeps_the_original_instead_of_losing_it(self):
        bad = _lesson(True, n_issues=1)
        calls = []

        def fake_convert(lean_json, topic, chunks):
            calls.append(1)
            if len(calls) == 1:
                return bad
            raise RuntimeError("retry generation blew up")

        with mock.patch.object(llg, "generate_lean_structured_lesson", return_value={"cards": []}), \
             mock.patch.object(llg, "_convert_lean_to_legacy", side_effect=fake_convert), \
             mock.patch.object(llg, "_assert_lesson_is_renderable", return_value=None):
            result = llg.build_lean_lesson_from_topic_and_chunks(_topic(), [])

        self.assertEqual(len(calls), 2)
        self.assertTrue(result["validation_report"]["requires_regeneration"])   # original, even though flagged
        self.assertEqual(result, bad)

    def test_practice_only_failure_does_not_trigger_a_retry(self):
        # Measured live: practice-class failures fired the retry on ~every topic and the retry NEVER fixed
        # them (9/9 discarded) — intro topics are prompt-forbidden from practice yet validated against it,
        # and math topics can only emit short_answer/multiple_choice. No retry; failure stays recorded.
        lesson = _lesson(False)
        lesson["topic_quality_report"] = {
            "requires_regeneration": True,
            "issues": [{"severity": "error", "code": "missing_practice", "message": "m", "details": {}},
                       {"severity": "error", "code": "practice_quality_regeneration_required",
                        "message": "m", "details": {}}]}
        lesson["validation_report"] = {"requires_regeneration": True, "issues": ["x"]}
        calls = []

        def fake_convert(lean_json, topic, chunks):
            calls.append(1)
            return lesson

        with mock.patch.object(llg, "generate_lean_structured_lesson", return_value={"cards": []}), \
             mock.patch.object(llg, "_convert_lean_to_legacy", side_effect=fake_convert), \
             mock.patch.object(llg, "_assert_lesson_is_renderable", return_value=None):
            llg.build_lean_lesson_from_topic_and_chunks(_topic(), [])
        self.assertEqual(len(calls), 1)   # no retry

    def test_non_practice_quality_error_still_triggers_a_retry(self):
        first, second = _lesson(False), _lesson(False)
        first["topic_quality_report"] = {
            "requires_regeneration": True,
            "issues": [{"severity": "error", "code": "stage_content_gap", "message": "m",
                        "details": {"blueprint_key": "process"}}]}
        first["validation_report"] = {"requires_regeneration": True, "issues": ["x"]}
        calls = []

        def fake_convert(lean_json, topic, chunks):
            calls.append(1)
            return first if len(calls) == 1 else second

        with mock.patch.object(llg, "generate_lean_structured_lesson", return_value={"cards": []}), \
             mock.patch.object(llg, "_convert_lean_to_legacy", side_effect=fake_convert), \
             mock.patch.object(llg, "_assert_lesson_is_renderable", return_value=None):
            llg.build_lean_lesson_from_topic_and_chunks(_topic(), [])
        self.assertEqual(len(calls), 2)   # retried

    def test_intro_topic_gets_no_sibling_derived_out_of_scope(self):
        # An intro's job is to orient across its siblings — sibling titles as out_of_scope made every
        # intro fail scope validation by construction, one guaranteed-wasted retry per path.
        from app.services.topic_scope_service import build_scope_boundaries_from_siblings

        class _StudyPath:
            pass

        intro = SimpleNamespace(id="i1", title="Introduction to Stokes Theorem",
                                course_type="study_path_introduction",
                                topic_type="study_path_introduction", prerequisite_topics=None)
        sib = SimpleNamespace(id="t2", title="Stokes' Theorem", course_type="math_formula_method",
                              topic_type="math_formula_method", prerequisite_topics=None)
        sp = _StudyPath(); sp.topics = [intro, sib]
        _, _, out_of_scope, _ = build_scope_boundaries_from_siblings(intro, sp, None)
        self.assertEqual(out_of_scope, [])
        # a TEACHING topic still gets its siblings excluded
        _, _, out_of_scope_sib, _ = build_scope_boundaries_from_siblings(sib, sp, None)
        self.assertIn("Introduction to Stokes Theorem", out_of_scope_sib)

    def test_decision_trace_records_which_attempt_shipped(self):
        bad, good = _lesson(True, n_issues=1), _lesson(False)
        calls = []

        def fake_convert(lean_json, topic, chunks):
            calls.append(1)
            return bad if len(calls) == 1 else good

        topic = _topic()
        with mock.patch.object(llg, "generate_lean_structured_lesson", return_value={"cards": []}), \
             mock.patch.object(llg, "_convert_lean_to_legacy", side_effect=fake_convert), \
             mock.patch.object(llg, "_assert_lesson_is_renderable", return_value=None):
            llg.build_lean_lesson_from_topic_and_chunks(topic, [])

        trace = topic.decomposition_metadata["decision_trace"]
        self.assertEqual(trace[-1]["stage"], "lesson.validation_retry")
        self.assertIn("retry", trace[-1]["decision"])


if __name__ == "__main__":
    unittest.main()
