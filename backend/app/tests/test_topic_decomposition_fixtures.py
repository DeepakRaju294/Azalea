"""Engine-B Phase 3 — decomposition FIXTURES over the goal shapes that matter (injected LLM, no API call).

Validates the capability-graph pipeline (validate -> repair -> adapt) end-to-end for:
  * a multi-concept goal where the model emits BOTH concepts (kept, distinct, prereq-ordered),
  * the DROPPED-concept case (model emits one; coverage repair synthesizes the other) — the live regression,
  * a single technique (one capability -> one topic, no padding).
Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_topic_decomposition_fixtures
"""
import unittest

from app.services.topic_decomposition_pipeline import generate_decomposed_topics


def _cap(cid, *, prereqs=None, subject=None, primary=None, role="calculation"):
    return {"capability_id": cid, "ownership_mode": "standalone", "owner_topic_id": None,
            "prerequisite_capability_ids": prereqs or [], "satisfies_end_actions": ["calculate"], "basis": "goal",
            "primary_capability": primary or cid, "subject_key": subject or cid, "content_role": role}


def _topic(cid, *, subject, title, role="calculation", tt="math_formula_method", output="a value"):
    return {"topic_id": f"t_{cid}", "capability_id": cid, "subject_key": subject, "primary_action": "calculate",
            "content_role": role, "topic_type": tt, "title": title, "unit_title": "u", "purpose": "p",
            "in_scope": ["x"], "practice_target": "compute it", "practice_format": "math_input",
            "practice_evidence_type": "compute_value", "expected_output": output, "basis": "goal"}


_TP_CAP = _cap("total_prob", subject="total_probability", primary="Law of Total Probability")
_BAYES_CAP = _cap("bayes", prereqs=["total_prob"], subject="bayes", primary="Bayes' Theorem")
_PLAN_BOTH = {"end_capability_actions": ["calculate"], "required_capabilities": [_TP_CAP, _BAYES_CAP]}
_TP_TOPIC = _topic("total_prob", subject="total_probability", title="Law of Total Probability", output="P(A)")
_BAYES_TOPIC = _topic("bayes", subject="bayes", title="Bayes' Theorem", output="P(A|B)")

GOAL = "law of total probability and bayes theorem"


class MultiConceptFixtures(unittest.TestCase):
    def _run(self, resp):
        return generate_decomposed_topics(GOAL, "source", model_fn=lambda p: resp)

    def test_both_concepts_emitted_are_kept_and_ordered(self):
        topics = self._run({"path_plan": _PLAN_BOTH, "topics": [_BAYES_TOPIC, _TP_TOPIC]})  # emitted out of order
        self.assertEqual(topics[0]["course_type"], "study_path_introduction")  # synthesized intro leads
        self.assertTrue(topics[0]["title"].startswith("Introduction to"))
        self.assertEqual([t["title"] for t in topics[1:]],
                         ["Law of Total Probability", "Bayes' Theorem"])   # prereq order: TP before Bayes
        self.assertEqual([t["order_index"] for t in topics], [1, 2, 3])
        self.assertEqual({t["course_type"] for t in topics[1:]}, {"math_formula_method"})

    def test_dropped_concept_is_synthesized(self):
        # THE regression: the model returns only the Bayes topic; the path plan requires both.
        topics = self._run({"path_plan": _PLAN_BOTH, "topics": [_BAYES_TOPIC]})
        titles = [t["title"] for t in topics]
        self.assertIn("Law of Total Probability", titles)   # synthesized back in
        self.assertIn("Bayes' Theorem", titles)
        self.assertEqual(len(topics), 3)   # intro + the two concepts
        self.assertEqual(topics[0]["course_type"], "study_path_introduction")  # intro first
        tp = next(t for t in topics if t["course_type"] == "math_formula_method"
                  and "Total Probability" in t["title"])
        self.assertEqual(tp["course_type"], "math_formula_method")   # type from the capability's content_role
        self.assertEqual([t["order_index"] for t in topics], [1, 2, 3])  # contiguous order indices

    def test_intro_conflated_with_a_concept_is_split(self):
        # THE 23:10 regression: the model titled the intro after the first concept (orientation role, but a
        # concrete subject + a teaching deliverable), so that concept got the intro blueprint (no worked
        # example) and there was no real intro. De-conflate -> teach the concept + synthesize a real intro.
        tp_as_intro = _topic("total_prob", subject="total_probability", title="Law of Total Probability",
                             role="orientation", tt="study_path_introduction")
        tp_as_intro["practice_evidence_type"] = "explain_model"
        tp_as_intro["expected_output"] = "A clear explanation of the Law of Total Probability."
        topics = self._run({"path_plan": _PLAN_BOTH, "topics": [tp_as_intro, _BAYES_TOPIC]})
        intros = [t for t in topics if t["course_type"] == "study_path_introduction"]
        self.assertEqual(len(intros), 1)                                  # exactly one, and it's generic
        self.assertTrue(intros[0]["title"].startswith("Introduction to"))
        # Total Probability is now a TAUGHT topic (math_formula_method), not the intro
        tp = next(t for t in topics if "Total Probability" in t["title"]
                  and t["course_type"] != "study_path_introduction")
        self.assertEqual(tp["course_type"], "math_formula_method")
        self.assertEqual(len(topics), 3)                                  # intro + both concepts

    def test_prerequisite_topic_is_folded_into_the_intro_not_taught(self):
        # The model promoted a prerequisite (conditional probability, role 'foundation') to a full topic.
        # Prereqs are NAMED not taught: drop it and surface it as an assumed prerequisite on the intro.
        cond = _topic("cond", subject="conditional_probability", title="Conditional Probability",
                      role="foundation", tt="math_formula_method")
        plan = {"end_capability_actions": ["calculate"],
                "required_capabilities": [
                    _cap("cond", subject="conditional_probability", primary="Conditional Probability", role="foundation"),
                    _cap("ltp", subject="law_total_probability", primary="Law of Total Probability", role="application")]}
        ltp = _topic("ltp", subject="law_total_probability", title="Law of Total Probability", role="application")
        topics = generate_decomposed_topics("learn the law of total probability", "s",
                                            model_fn=lambda p: {"path_plan": plan, "topics": [cond, ltp]})
        titles = [t["title"] for t in topics]
        self.assertNotIn("Conditional Probability", titles)               # not a standalone teaching topic
        self.assertIn("Law of Total Probability", titles)
        intro = next(t for t in topics if t["course_type"] == "study_path_introduction")
        self.assertIn("Conditional Probability", intro.get("assumed_prerequisites") or [])   # named as a prereq

    def test_emitted_intro_is_not_duplicated(self):
        # when the model DOES emit an orientation topic, we must NOT synthesize a second one.
        intro = {"topic_id": "t_intro", "capability_id": "orient", "subject_key": "probability",
                 "primary_action": "understand", "content_role": "orientation",
                 "topic_type": "study_path_introduction", "title": "Probability, Start Here",
                 "unit_title": "u", "purpose": "orient", "in_scope": ["x"], "basis": "goal"}
        plan = {"end_capability_actions": ["calculate"],
                "required_capabilities": [{"capability_id": "orient", "ownership_mode": "standalone",
                                           "owner_topic_id": None, "prerequisite_capability_ids": [],
                                           "satisfies_end_actions": [], "basis": "goal"}, _TP_CAP, _BAYES_CAP]}
        topics = self._run({"path_plan": plan, "topics": [intro, _TP_TOPIC, _BAYES_TOPIC]})
        intros = [t for t in topics if t["course_type"] == "study_path_introduction"]
        self.assertEqual(len(intros), 1)                       # exactly one, the model's own
        self.assertEqual(intros[0]["title"], "Probability, Start Here")
        self.assertEqual(topics[0]["course_type"], "study_path_introduction")  # still first

    def test_dropped_concept_ordered_before_its_dependent(self):
        topics = self._run({"path_plan": _PLAN_BOTH, "topics": [_BAYES_TOPIC]})
        order = {t["title"]: t["order_index"] for t in topics}
        self.assertLess(order["Law of Total Probability"], order["Bayes' Theorem"])   # prereq first

    def test_understand_and_apply_split_is_collapsed_end_to_end(self):
        # The live Engine-B regression: the model split each concept into an "understand" topic and an
        # "apply" topic (distinct subject_keys w/ an _application suffix). The pipeline must collapse each
        # pair into ONE teaching topic so the goal's two concepts yield two topics, not four.
        cap_u = _cap("understand_bayes", subject="bayes_theorem", primary="Bayes' Theorem", role="concept_intuition")
        cap_a = _cap("apply_bayes", prereqs=["understand_bayes"], subject="bayes_theorem_application",
                     primary="Bayes' Theorem", role="problem_solving_application")
        plan = {"end_capability_actions": ["apply"], "required_capabilities": [cap_u, cap_a]}
        t_u = _topic("understand_bayes", subject="bayes_theorem", title="Understanding Bayes' Theorem",
                     role="concept_intuition", tt="concept_intuition")
        t_a = _topic("apply_bayes", subject="bayes_theorem_application", title="Applying Bayes' Theorem",
                     role="problem_solving_application", tt="problem_solving_application")
        t_a["primary_action"] = "apply"
        topics = generate_decomposed_topics("learn bayes theorem", "s",
                                            model_fn=lambda p: {"path_plan": plan, "topics": [t_u, t_a]})
        # understand + apply folded into ONE teaching topic; a synthesized intro opens the path
        # (every path gets an intro — product decision) but never adds a second teaching topic.
        teaching = [t for t in topics if t["course_type"] != "study_path_introduction"]
        self.assertEqual(len(teaching), 1)
        self.assertEqual(teaching[0]["title"], "Bayes' Theorem")  # leading study-verb stripped
        self.assertEqual(teaching[0]["course_type"], "problem_solving_application")

    def test_single_technique_one_topic_no_padding(self):
        plan = {"end_capability_actions": ["calculate"],
                "required_capabilities": [_cap("cts", subject="completing_the_square",
                                               primary="Completing the Square")]}
        topic = _topic("cts", subject="completing_the_square", title="Completing the Square")
        topics = generate_decomposed_topics("learn completing the square", "s", model_fn=lambda p: {
            "path_plan": plan, "topics": [topic]})
        # one capability -> one TEACHING topic (no padding); the synthesized intro is the only addition
        teaching = [t for t in topics if t["course_type"] != "study_path_introduction"]
        self.assertEqual(len(teaching), 1)
        self.assertEqual(teaching[0]["title"], "Completing the Square")
        self.assertEqual(topics[0]["course_type"], "study_path_introduction")  # intro opens the path


if __name__ == "__main__":
    unittest.main()
