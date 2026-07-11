"""Phase-1A production shadow (STUDY_PATH_SCOPE_SPEC §10): map real topics → a scope plan → neutral diff.
Duck-typed topics, no DB, no route imports (so no .env contamination)."""
import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.scope_shadow import (
    maybe_log_shadow, shadow_report, topics_to_baseline, topics_to_decomposition_input,
)


def _topic(title, course_type, order_index, *, subject_key=None, content_role=None, prereqs=None):
    md = {}
    if subject_key:
        md["subject_key"] = subject_key
    if content_role:
        md["content_role"] = content_role
    return SimpleNamespace(title=title, course_type=course_type, order_index=order_index,
                           decomposition_metadata=md, assumed_prerequisites=list(prereqs or []))


def _bayes_topics():
    return [
        _topic("Introduction to Bayes & Total Probability", "study_path_introduction", 1,
               content_role="orientation"),
        _topic("Law of Total Probability", "math_formula_method", 2, subject_key="total_probability",
               prereqs=["conditional probability"]),
        _topic("Bayes' Theorem", "math_formula_method", 3, subject_key="bayes_theorem",
               prereqs=["conditional probability"]),
    ]


class ShadowReport(unittest.TestCase):
    def test_intro_is_excluded_from_concepts(self):
        inp = topics_to_decomposition_input("bayes", "math", _bayes_topics())
        keys = {c.canonical_concept_key for c in inp.concepts}
        self.assertEqual(keys, {"total_probability", "bayes_theorem"})       # intro is derived, not a concept

    def test_prereq_kept_separate_from_concepts(self):
        inp = topics_to_decomposition_input("bayes", "math", _bayes_topics())
        self.assertIn("conditional_probability", {p.id for p in inp.prereqs})
        self.assertNotIn("conditional_probability", {c.canonical_concept_key for c in inp.concepts})

    def test_report_is_structurally_valid_and_reproduces_the_pipeline(self):
        r = shadow_report("bayes", "math", _bayes_topics())
        self.assertEqual(r["planning_status"], "structurally_valid")
        self.assertEqual(r["failed_invariants"], [])
        self.assertEqual(r["concept_count"], 2)
        # plan built from the same topics → structurally identical → "same".
        self.assertEqual(r["diff_class"], "same")
        self.assertEqual(r["metrics"]["hard_edge_violation_count"], 0)

    def test_coding_topic_in_math_path_is_flagged_rejected(self):
        topics = _bayes_topics()
        topics[2].course_type = "coding_implementation"        # illegal for a math domain (§4.6)
        r = shadow_report("bayes", "math", topics)
        self.assertEqual(r["planning_status"], "rejected")
        self.assertIn("domain_legality", r["failed_invariants"])

    def test_baseline_matches_concept_topics(self):
        base = topics_to_baseline(_bayes_topics())
        self.assertEqual(base.concept_order, ["total_probability", "bayes_theorem"])

    def test_maybe_log_is_dark_by_default(self):
        os.environ.pop("AZALEA_STUDY_PATH_SCOPE", None)
        self.assertIsNone(maybe_log_shadow("bayes", "math", _bayes_topics()))    # flag off → no-op

    def test_maybe_log_runs_when_flagged(self):
        os.environ["AZALEA_STUDY_PATH_SCOPE"] = "1"
        try:
            r = maybe_log_shadow("bayes", "math", _bayes_topics())
            self.assertIsNotNone(r)
            self.assertEqual(r["planning_status"], "structurally_valid")
        finally:
            os.environ.pop("AZALEA_STUDY_PATH_SCOPE", None)


if __name__ == "__main__":
    unittest.main()
