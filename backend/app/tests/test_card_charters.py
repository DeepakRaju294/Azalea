"""Card-content charters — CARD_CONTENT_CHARTER_SPEC.md v5, Phase 1 (background family).

Deterministic acceptance rows A1–A5, A11, A12, A15, A16, A18 on the resolver / charter_for / resolve_card
output (the built-prompt rows A8/A10 are exercised after the prompt-injection wiring). Offline.
Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_card_charters
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.core.card_charters import (
    TopicPlan, active_charter_families, charter_for, resolve_card, resolve_card_for, resolve_ownership,
)


def _tp(key, ttype, order):
    return TopicPlan(topic_key=key, topic_type=ttype, order_index=order)


class Charters(unittest.TestCase):
    # --- A2 / A3: charter shape ---------------------------------------------------------------------------
    def test_A2_math_background_expresses_overview_not_procedure(self):
        c = charter_for("math_formula_method", "background")
        self.assertEqual(c.expresses, ("PROCEDURE_OVERVIEW", "STRUCTURE"))
        self.assertNotIn("PROCEDURE", c.expresses)
        self.assertEqual(set(c.fallback_expresses), {"INTUIT", "MOTIVATE", "DEFINE_GLOBAL"})

    def test_A3_concept_background_expresses_intuit_motivate(self):
        c = charter_for("concept_intuition", "background")
        self.assertEqual(set(c.expresses), {"INTUIT", "MOTIVATE"})

    # --- A1: single-owner invariant ------------------------------------------------------------------------
    def test_A1_each_carried_slot_resolves_once_and_define_local_never(self):
        topics = [_tp("t1", "concept_intuition", 0), _tp("t2", "math_formula_method", 1)]
        plans = {"t1": ["background", "edge_case", "practice"],
                 "t2": ["background", "components_terms", "formula_breakdown", "worked_example", "edge_case", "practice"]}
        own = resolve_ownership(topics, plans)
        self.assertNotIn("DEFINE_LOCAL", own)               # universal, never resolved
        # ownership is a dict → inherently one owner per slot; spot-check the contested ones resolve
        self.assertIn("INTUIT", own)
        self.assertIn("PROCEDURE", own)
        self.assertEqual(own["INTUIT"].topic_type, "concept_intuition")   # concept owns intuition

    # --- A4: concept sibling present → method bg excludes INTUIT -------------------------------------------
    def test_A4_method_bg_excludes_intuit_when_concept_present(self):
        topics = [_tp("i", "study_path_introduction", 0), _tp("c", "concept_intuition", 1),
                  _tp("m", "math_formula_method", 2)]
        plans = {"i": ["background", "roadmap"], "c": ["background"],
                 "m": ["background", "components_terms", "formula_breakdown"]}
        own = resolve_ownership(topics, plans)
        self.assertEqual(own["INTUIT"].topic_type, "concept_intuition")
        m = resolve_card(charter_for("math_formula_method", "background"), own, topics[2], "background")
        self.assertIn("INTUIT", m.exclude_slots)
        self.assertNotIn("INTUIT", m.include_slots)
        self.assertIn("PROCEDURE_OVERVIEW", m.include_slots)  # its own primary slot

    # --- A5: no concept → method bg fallback fires ---------------------------------------------------------
    def test_A5_method_bg_fallback_when_no_concept(self):
        topics = [_tp("i", "study_path_introduction", 0), _tp("m", "math_formula_method", 1)]
        plans = {"i": ["background", "roadmap"], "m": ["background"]}     # no components_terms, no concept
        own = resolve_ownership(topics, plans)
        m = resolve_card(charter_for("math_formula_method", "background"), own, topics[1], "background")
        self.assertIn("INTUIT", m.include_slots)
        self.assertIn("MOTIVATE", m.include_slots)
        self.assertIn("DEFINE_GLOBAL", m.include_slots)      # no later definition card → fallback fires

    # --- A11 / A12: directive prose ------------------------------------------------------------------------
    def test_A11_exclude_directive_points_to_intuition_topic(self):
        topics = [_tp("c", "concept_intuition", 0), _tp("m", "math_formula_method", 1)]
        plans = {"c": ["background"], "m": ["background", "formula_breakdown"]}
        own = resolve_ownership(topics, plans)
        m = resolve_card(charter_for("math_formula_method", "background"), own, topics[1], "background")
        blob = " ".join(m.exclude_directives)
        self.assertIn("the intuition topic", blob)
        self.assertIn("what is this", blob.lower())

    def test_A12_include_directive_has_intuition_when_no_concept(self):
        topics = [_tp("m", "math_formula_method", 0)]
        plans = {"m": ["background"]}
        own = resolve_ownership(topics, plans)
        m = resolve_card(charter_for("math_formula_method", "background"), own, topics[0], "background")
        self.assertTrue(any("mental model" in d for d in m.include_directives))

    # --- A15: card-aware fallback (concept card pruned) ---------------------------------------------------
    def test_A15_pruned_concept_card_lets_method_bg_own_intuit(self):
        topics = [_tp("c", "concept_intuition", 0), _tp("m", "math_formula_method", 1)]
        plans = {"c": ["worked_example"], "m": ["background"]}   # concept topic present but NO intuition card
        own = resolve_ownership(topics, plans)
        self.assertEqual((own["INTUIT"].topic_type, own["INTUIT"].card_type), ("math_formula_method", "background"))
        m = resolve_card(charter_for("math_formula_method", "background"), own, topics[1], "background")
        self.assertIn("INTUIT", m.include_slots)              # content not dropped

    # --- A16: definition card out-owns background's DEFINE_GLOBAL fallback --------------------------------
    def test_A16_definition_card_beats_background_fallback(self):
        topics = [_tp("m", "math_formula_method", 0)]
        plans = {"m": ["background", "components_terms", "formula_breakdown"]}   # no terminology topic
        own = resolve_ownership(topics, plans)
        self.assertEqual(own["DEFINE_GLOBAL"].card_type, "components_terms")
        m = resolve_card(charter_for("math_formula_method", "background"), own, topics[0], "background")
        self.assertNotIn("DEFINE_GLOBAL", m.include_slots)
        self.assertIn("DEFINE_GLOBAL", m.exclude_slots)

    # --- A18: background vs method_process — no double-owned procedure ------------------------------------
    def test_A6_definition_owned_by_earliest_topic_not_highest_priority(self):
        # two topics carry a definition card; the EARLIER one (intro) owns DEFINE_GLOBAL so the later (method)
        # references it — never a forward reference. (§5 tier-2 = earliest occurrence, not topic priority.)
        topics = [_tp("i", "study_path_introduction", 0), _tp("m", "math_formula_method", 1)]
        plans = {"i": ["background", "components_terms", "roadmap"],
                 "m": ["background", "components_terms", "formula_breakdown"]}
        own = resolve_ownership(topics, plans)
        self.assertEqual(own["DEFINE_GLOBAL"].topic_type, "study_path_introduction")
        method_def = resolve_card(charter_for("math_formula_method", "components_terms"), own, topics[1], "components_terms")
        self.assertIn("DEFINE_GLOBAL", method_def.exclude_slots)          # method references, doesn't redefine
        self.assertNotIn("DEFINE_GLOBAL", method_def.include_slots)

    def test_A18_background_overview_method_process_full(self):
        topics = [_tp("m", "math_formula_method", 0)]
        plans = {"m": ["background", "formula_breakdown"]}
        own = resolve_ownership(topics, plans)
        self.assertEqual(own["PROCEDURE_OVERVIEW"].card_type, "background")
        self.assertEqual(own["PROCEDURE"].card_type, "formula_breakdown")
        m = resolve_card(charter_for("math_formula_method", "background"), own, topics[0], "background")
        self.assertIn("PROCEDURE_OVERVIEW", m.include_slots)
        self.assertNotIn("PROCEDURE", m.include_slots)
        self.assertNotIn("PROCEDURE", m.exclude_slots)       # bg never touches full PROCEDURE at all
        self.assertTrue(m.scope_note)

    # --- widening beyond background/definition/edge_case (Phase 2 candidate families) --------------------
    def test_widened_families_resolve_ownership_sensibly_across_a_full_card_set(self):
        # A realistic math_formula_method topic with cards from EVERY family CARD_CHARTER_DEFAULTS defines
        # (not just background/definition/edge_case) — confirms the resolver generalizes correctly before
        # actually widening AZALEA_CARD_CHARTERS in .env (a live prompt-construction flag, not test-only state).
        prev = os.environ.pop("AZALEA_CARD_CHARTERS", None)
        try:
            os.environ["AZALEA_CARD_CHARTERS"] = "all"
            topics = [_tp("m", "math_formula_method", 0)]
            plans = {"m": ["background", "formula_breakdown", "worked_example", "edge_case", "practice"]}
            own = resolve_ownership(topics, plans)
            self.assertEqual(own["PROCEDURE_OVERVIEW"].card_type, "background")
            self.assertEqual(own["PROCEDURE"].card_type, "formula_breakdown")
            self.assertEqual(own["DERIVE"].card_type, "formula_breakdown")
            self.assertEqual(own["INSTANCE"].card_type, "worked_example")
            self.assertEqual(own["EDGE"].card_type, "edge_case")
            self.assertEqual(own["PRACTICE"].card_type, "practice")

            worked = resolve_card_for(topics[0], "worked_example", own)
            self.assertIsNotNone(worked, "worked_example family must be injectable once active")
            self.assertIn("INSTANCE", worked.include_slots)
            self.assertEqual(worked.exclude_slots, ())      # worked_example expresses only INSTANCE

            bg = resolve_card_for(topics[0], "background", own)
            self.assertIn("PROCEDURE_OVERVIEW", bg.include_slots)
            # background must NOT also claim the full procedure once formula_breakdown owns it
            self.assertNotIn("PROCEDURE", bg.include_slots)

            practice = resolve_card_for(topics[0], "practice", own)
            self.assertIn("PRACTICE", practice.include_slots)
        finally:
            os.environ.pop("AZALEA_CARD_CHARTERS", None)
            if prev is not None:
                os.environ["AZALEA_CARD_CHARTERS"] = prev

    # --- rollout flag + gating ----------------------------------------------------------------------------
    def test_family_flag_parsing_and_gating(self):
        prev = os.environ.pop("AZALEA_CARD_CHARTERS", None)
        try:
            self.assertEqual(active_charter_families(), frozenset())     # unset = off
            os.environ["AZALEA_CARD_CHARTERS"] = "background,definition"
            self.assertEqual(active_charter_families(), frozenset({"background", "definition"}))
            topics = [_tp("m", "math_formula_method", 0)]
            own = resolve_ownership(topics, {"m": ["background"]})
            self.assertIsNotNone(resolve_card_for(topics[0], "background", own))   # background family active
            # a non-active family's card resolves to None (not injected)
            os.environ["AZALEA_CARD_CHARTERS"] = "definition"
            self.assertIsNone(resolve_card_for(topics[0], "background", own))
        finally:
            os.environ.pop("AZALEA_CARD_CHARTERS", None)
            if prev is not None:
                os.environ["AZALEA_CARD_CHARTERS"] = prev


import types

from app.prompts.lean_lesson_prompt import build_lean_user_prompt


def _fake_topic(topic_id, ttype, order, sp):
    return types.SimpleNamespace(
        id=topic_id, title="Completing the Square", description="", topic_type=ttype, course_type=ttype,
        order_index=order, study_path=sp, purpose="", learner_outcome=None, in_scope=None, out_of_scope=None,
        modifiers=None, decomposition_metadata=None, assumed_prerequisites=None)


class PromptWiring(unittest.TestCase):
    def setUp(self):
        self._prev = os.environ.get("AZALEA_CARD_CHARTERS")
        os.environ["AZALEA_CARD_CHARTERS"] = "background"

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("AZALEA_CARD_CHARTERS", None)
        else:
            os.environ["AZALEA_CARD_CHARTERS"] = self._prev

    def test_A8_method_prompt_excludes_intuition_when_concept_sibling(self):
        sp = types.SimpleNamespace(goal="learn completing the square", domain="math", topics=[])
        concept = _fake_topic("c", "concept_intuition", 0, sp)
        method = _fake_topic("m", "math_formula_method", 1, sp)
        sp.topics = [concept, method]
        prompt = build_lean_user_prompt(method, [])
        self.assertIn("content_charter", prompt)                          # charter injected
        self.assertIn("the intuition topic", prompt)                      # exclude points to the concept topic
        self.assertNotIn("Give the one-sentence mental model", prompt)    # NOT told to give intuition (A8)

    def test_method_prompt_includes_intuition_when_no_concept(self):
        sp = types.SimpleNamespace(goal="learn completing the square", domain="math", topics=[])
        method = _fake_topic("m", "math_formula_method", 0, sp)
        sp.topics = [method]
        prompt = build_lean_user_prompt(method, [])
        self.assertIn("Give the one-sentence mental model", prompt)       # fallback fired → self-contained

    def test_flag_off_is_dark(self):
        os.environ.pop("AZALEA_CARD_CHARTERS", None)
        sp = types.SimpleNamespace(goal="x", domain="math", topics=[])
        method = _fake_topic("m", "math_formula_method", 0, sp)
        sp.topics = [method]
        self.assertNotIn("content_charter", build_lean_user_prompt(method, []))


if __name__ == "__main__":
    unittest.main()
