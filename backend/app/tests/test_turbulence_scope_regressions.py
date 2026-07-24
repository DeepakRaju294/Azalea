import os
from types import SimpleNamespace
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")


class TurbulenceScopeCoverageTests(unittest.TestCase):
    def test_name_drops_do_not_satisfy_owned_application_scope(self):
        from app.services.scope_validator import validate_owned_scope_coverage

        cards = [
            {
                "blueprint_key": "background",
                "points": [
                    "Applications include aerodynamic drag, industrial mixing, and natural bodies of water."
                ],
            },
            {
                "blueprint_key": "process",
                "points": ["Use vehicle shape and speed to reason about aerodynamic drag."],
            },
        ]
        contract = {
            "owned_scope_content": [
                "aerodynamic drag in vehicles",
                "mixing processes in industrial applications",
                "turbulent flow in natural bodies of water",
            ]
        }
        issues = validate_owned_scope_coverage(cards, contract)
        self.assertFalse(any("aerodynamic drag" in issue for issue in issues))
        self.assertTrue(any("mixing processes" in issue for issue in issues))
        self.assertTrue(any("natural bodies" in issue for issue in issues))

    def test_mechanism_process_covers_energy_cascade_commitments(self):
        from app.services.scope_validator import validate_owned_scope_coverage

        cards = [{
            "blueprint_key": "process",
            "points": [
                "Large eddies receive and carry turbulent kinetic energy.",
                "Nonlinear eddy interactions transfer energy to progressively smaller scales.",
                "At the smallest scales, viscosity converts turbulent kinetic energy into heat.",
            ],
        }]
        contract = {"owned_scope_content": [
            "role of large eddies in energy transfer",
            "how energy cascades to smaller scales",
            "the eventual dissipation via viscosity",
        ]}
        self.assertEqual(validate_owned_scope_coverage(cards, contract), [])

    def test_route_adapter_uses_subject_key_when_title_is_a_paraphrase(self):
        """37th path review: 'Fluid Turbulence Dynamics' generated with ZERO worked examples anywhere.
        Root cause: the topic 'Key Quantities in Turbulence' (subject_key='turbulence_reynolds_number') got
        the correct canonical identity (_canonical_concept_key checks subject_key) but route_adapter — used
        for verified_example resolution at certification and card grounding — only ever looked at title/slug,
        never subject_key. A learner-facing title that paraphrases the concept (no 'Reynolds' in it at all)
        silently lost its verified adapter, ending in we_policy='withhold_fabricated' for the one topic in the
        path that should have shipped a worked example."""
        from app.services.examples.trace_pipeline import route_adapter

        title_only = route_adapter({"title": "Key Quantities in Turbulence", "topic_type": "science_mechanism"})
        self.assertIsNone(title_only)

        with_subject_key = route_adapter({
            "title": "Key Quantities in Turbulence",
            "subject_key": "turbulence_reynolds_number",
            "topic_type": "science_mechanism",
        })
        self.assertIsNotNone(with_subject_key)
        self.assertEqual(with_subject_key.slug, "reynolds_number")

    def test_route_adapter_does_not_false_match_across_field_boundary(self):
        """38th-round-adjacent regression IN the subject_key fix itself: joining slug/subject_key/title with
        a bare space can accidentally SPELL a real alias across the boundary between two fields that never
        said it individually. Live: subject_key 'energy_transfer_turbulence' + title 'Energy Transfer in
        Turbulence' joined with a space reads '...turbulence energy transfer...', which contains the
        substring 'turbulence energy' — a genuine alias for turbulent_kinetic_energy — even though neither
        field alone is about TKE. A mechanism/energy-cascade topic wrongly certified verified_example=
        'turbulent_kinetic_energy' and shipped a k=(u'^2+v'^2+w'^2)/2 worked example that has nothing to do
        with its actual content."""
        from app.services.examples.trace_pipeline import route_adapter

        a = route_adapter({
            "title": "Energy Transfer in Turbulence",
            "subject_key": "energy_transfer_turbulence",
            "topic_type": "science_mechanism",
            "course_type": "science_mechanism",
        })
        self.assertIsNone(a)

        # a topic that GENUINELY is about turbulent kinetic energy must still route.
        b = route_adapter({
            "title": "Turbulent Kinetic Energy",
            "subject_key": "turbulent_kinetic_energy",
            "topic_type": "science_mechanism",
        })
        self.assertIsNotNone(b)
        self.assertEqual(b.slug, "turbulent_kinetic_energy")

    def test_plan_allowed_adapter_resolves_via_subject_key(self):
        from app.services.lean_lesson_generator import _plan_allowed_adapter

        topic = SimpleNamespace(
            title="Key Quantities in Turbulence",
            course_type="science_mechanism",
            topic_type="science_mechanism",
            decomposition_metadata={
                "subject_key": "turbulence_reynolds_number",
                "scope_plan": {"verified_example": "reynolds_number", "we_policy": "verified"},
            },
        )
        adapter = _plan_allowed_adapter(topic)
        self.assertIsNotNone(adapter)
        self.assertEqual(adapter.slug, "reynolds_number")

    def test_certify_path_scope_resolves_verified_example_via_subject_key(self):
        """The actual site that decides `verified_example` at certification. Before the fix this topic
        certified with verified_example=None / we_policy='withhold_fabricated' despite owning the adapter's
        concept, because its title alone never matched a Reynolds-number alias."""
        from app.services.topic_generator import _certify_path_scope

        topics = [{
            "title": "Key Quantities in Turbulence",
            "subject_key": "turbulence_reynolds_number",
            "topic_type": "science_mechanism",
            "course_type": "science_mechanism",
            "purpose": "Quantify the Reynolds number for a pipe flow and classify the regime.",
            "learner_outcome": "Compute Re and classify the flow as laminar or turbulent.",
            "in_scope": ["Reynolds number", "flow regime classification"],
            "out_of_scope": [],
            "prerequisite_topics": [],
        }]
        certified = _certify_path_scope(topics, "Learn fluid turbulence")
        plan = (certified[0].get("decomposition_metadata") or {}).get("scope_plan") or {}
        self.assertEqual(plan.get("verified_example"), "reynolds_number")
        self.assertNotEqual(plan.get("we_policy"), "withhold_fabricated")

    def test_lean_pipeline_no_longer_stamps_missing_practice_as_valid(self):
        from app.services.lean_lesson_generator import _attach_lean_validation_reports

        topic = SimpleNamespace(
            title="Real-World Applications of Turbulence",
            purpose="Apply turbulence concepts",
            learner_outcome="Analyze turbulence applications",
            course_type="problem_solving_application",
            topic_type="problem_solving_application",
            secondary_course_types=[],
            in_scope=["aerodynamic drag in vehicles", "industrial mixing"],
            out_of_scope=[],
            assumed_prerequisites=[],
            prerequisite_topics=None,
            decomposition_metadata={},
            study_path=None,
        )
        lesson = {
            "lesson_cards": [
                {"blueprint_key": "background", "card_type": "purpose_context", "points": ["Why it matters"]},
                {"blueprint_key": "process", "card_type": "method_process", "points": ["Analyze drag"]},
            ],
            "practice_questions": [],
            "visual_validation_report": {"requires_regeneration": False, "issues": []},
        }
        _attach_lean_validation_reports(lesson, topic)
        self.assertTrue(lesson["practice_quality_report"]["requires_regeneration"])
        self.assertTrue(lesson["validation_report"]["requires_regeneration"])


class PracticeCardWordingDoesNotSatisfyOwnedCoverage(unittest.TestCase):
    """Live bug (Stokes' theorem path review, 'Fundamentals of Vector Calculus' repeat complaint): a
    concept_intuition topic synthesized to own "gradients, curls, divergences" instead wrote its
    background/edge_case cards entirely about Stokes' theorem itself (explicitly out of scope) — but
    validate_owned_scope_coverage flagged only 1 of its 4 owned commitments, because the OTHER 3 "passed"
    purely on the practice card's own question wording echoing the commitment's words ("Explain the
    significance of curls and gradients...") — never any actual teaching content."""

    def test_practice_only_mention_is_not_substantive_coverage(self):
        from app.services.scope_validator import validate_owned_scope_coverage

        cards = [
            {"blueprint_key": "background", "title": "What is Stokes' Theorem?",
             "points": ["Stokes' Theorem relates surface integrals to line integrals."]},
            {"blueprint_key": "edge_case", "points": [
                "A surface with zero curl indicates no rotation in the vector field."]},
            {"blueprint_key": "practice",
             "title": "Explain the Significance of Curls and Gradients in Physics",
             "points": ["Articulate how gradients represent potential changes in a field."]},
        ]
        contract = {"owned_scope_content": ["gradients and their significance",
                                            "understanding curls and divergences"]}
        issues = validate_owned_scope_coverage(cards, contract)
        self.assertTrue(any("gradients and their significance" in i for i in issues))
        self.assertTrue(any("understanding curls and divergences" in i for i in issues))

    def test_real_teaching_content_still_counts_as_covered(self):
        from app.services.scope_validator import validate_owned_scope_coverage

        cards = [
            {"blueprint_key": "background", "points": ["Orientation only."]},
            {"blueprint_key": "edge_case", "points": [
                "The gradient's significance: it points in the direction of steepest increase."]},
            {"blueprint_key": "practice", "points": ["Explain the significance of gradients."]},
        ]
        contract = {"owned_scope_content": ["gradients and their significance"]}
        self.assertEqual(validate_owned_scope_coverage(cards, contract), [])


class BareSiblingTitlePhraseNoise(unittest.TestCase):
    """Live bug (Stokes' theorem path review): out_of_scope_content/must_not_teach include bare SIBLING
    TOPIC TITLES (build_scope_boundaries_from_siblings appends sibling_title directly), not just real
    forbidden-content descriptions. A passing, legitimate mention of a sibling's name — unavoidable on a
    path where every topic connects back to the same handful of concepts — used to trip "teaches forbidden
    content" via a bare substring/ratio match with no "is this actually central to the card" gate. Measured
    on the real path: 98% of one topic's ~475 flagged issues were this false-positive class. Fixed: every
    must_not_teach/out_of_scope check (card- and point-level) is now gated by is_taught_as_main_content."""

    def test_passing_mention_of_a_sibling_title_is_not_flagged(self):
        from app.services.scope_validator import validate_scope_adherence

        lesson_json = {"lesson_cards": [{
            "blueprint_key": "background",
            "title": "What is a Line Integral?",
            "main_concept": "Line integrals sum a vector field's effect along a curve.",
            "points": [
                "A line integral totals a vector field's effect along a curve.",
                "This result underlies Stokes' Theorem, covered in a later topic.",
            ],
        }]}
        contract = {"out_of_scope_content": ["Stokes' Theorem"],
                   "must_not_teach": ["Stokes' Theorem", "how Stokes' Theorem works"]}
        report = validate_scope_adherence(lesson_json, contract)
        self.assertEqual(report["issues"], [])
        self.assertTrue(report["passed"])

    def test_a_card_actually_centered_on_the_forbidden_topic_is_still_flagged(self):
        from app.services.scope_validator import validate_scope_adherence

        lesson_json = {"lesson_cards": [{
            "blueprint_key": "background",
            "title": "What is Stokes' Theorem?",
            "main_concept": "Stokes' Theorem relates a surface integral to a line integral.",
            "points": ["Stokes' Theorem relates a surface integral to a line integral."],
        }]}
        contract = {"out_of_scope_content": ["Stokes' Theorem"], "must_not_teach": []}
        report = validate_scope_adherence(lesson_json, contract)
        self.assertFalse(report["passed"])
        self.assertTrue(any("stokes' theorem" in issue for issue in report["issues"]))

    def test_genuinely_forbidden_content_description_still_caught_at_point_level(self):
        # not a title — a real content description the card's own subject is centrally about.
        from app.services.scope_validator import validate_scope_adherence

        lesson_json = {"lesson_cards": [{
            "blueprint_key": "background",
            "title": "Statement and proof of the divergence theorem",
            "main_concept": "Statement and proof of the divergence theorem",
            "points": ["Statement and proof of the divergence theorem, in full detail with derivation."],
        }]}
        contract = {"out_of_scope_content": ["statement and proof of the divergence theorem"],
                   "must_not_teach": []}
        report = validate_scope_adherence(lesson_json, contract)
        self.assertFalse(report["passed"])


class SupportingBeforeGoalCoreOrdering(unittest.TestCase):
    """Live UX bug (Stokes' theorem path, 18:35 regen): the model emitted the goal-core topic FIRST
    ([Stokes' Theorem, Evaluating Surface Integrals, Computing Line Integrals, Applying the Divergence
    Theorem]) — a first-time learner met the theorem relating line and surface integrals before either was
    taught. _certify_path_scope now moves a supporting topic before the goal_core topic when its subject
    shares NO vocabulary with the goal (a true building block, not a family member)."""

    @staticmethod
    def _stokes_topics():
        return [
            {"title": "Stokes' Theorem", "subject_key": "stokes_theorem",
             "topic_type": "math_formula_method", "course_type": "math_formula_method",
             "purpose": "p", "learner_outcome": "o", "in_scope": ["statement of stokes theorem"],
             "out_of_scope": [], "prerequisite_topics": [], "order_index": 1},
            {"title": "Evaluating Surface Integrals", "subject_key": "surface_integrals",
             "topic_type": "math_formula_method", "course_type": "math_formula_method",
             "purpose": "p", "learner_outcome": "o", "in_scope": ["surface integral evaluation"],
             "out_of_scope": [], "prerequisite_topics": [], "order_index": 2},
            {"title": "Computing Line Integrals", "subject_key": "line_integrals",
             "topic_type": "math_formula_method", "course_type": "math_formula_method",
             "purpose": "p", "learner_outcome": "o", "in_scope": ["line integral computation"],
             "out_of_scope": [], "prerequisite_topics": [], "order_index": 3},
            {"title": "Applying the Divergence Theorem", "subject_key": "divergence_theorem",
             "topic_type": "problem_solving_application", "course_type": "problem_solving_application",
             "content_role": "application",
             "purpose": "p", "learner_outcome": "o", "in_scope": ["divergence theorem applications"],
             "out_of_scope": [], "prerequisite_topics": [], "order_index": 4},
        ]

    def test_building_block_supporting_topics_move_before_the_goal_core(self):
        from app.services.topic_generator import _certify_path_scope

        certified = _certify_path_scope(self._stokes_topics(), "want to learn about stokes theorem")
        titles = [t["title"] for t in certified]
        self.assertLess(titles.index("Evaluating Surface Integrals"), titles.index("Stokes' Theorem"))
        self.assertLess(titles.index("Computing Line Integrals"), titles.index("Stokes' Theorem"))
        # the application topic stays after the goal core; order_index matches the new list order
        self.assertGreater(titles.index("Applying the Divergence Theorem"), titles.index("Stokes' Theorem"))
        self.assertEqual([t["order_index"] for t in certified], list(range(1, len(certified) + 1)))
        core = next(t for t in certified if t["title"] == "Stokes' Theorem")
        trace = (core.get("decomposition_metadata") or {}).get("decision_trace") or []
        self.assertTrue(any(e["stage"] == "order.supporting_moved_before_goal_core" for e in trace))

    def test_family_members_sharing_goal_vocabulary_do_not_move(self):
        from app.services.topic_generator import _certify_path_scope

        topics = [
            {"title": "In-Order Traversal", "subject_key": "in_order_traversal",
             "topic_type": "algorithm_walkthrough", "course_type": "algorithm_walkthrough",
             "purpose": "p", "learner_outcome": "o", "in_scope": ["visit order"],
             "out_of_scope": [], "prerequisite_topics": [], "order_index": 1},
            {"title": "Pre-Order Traversal", "subject_key": "pre_order_traversal",
             "topic_type": "algorithm_walkthrough", "course_type": "algorithm_walkthrough",
             "purpose": "p", "learner_outcome": "o", "in_scope": ["root first"],
             "out_of_scope": [], "prerequisite_topics": [], "order_index": 2},
        ]
        certified = _certify_path_scope(topics, "want to learn about bst traversal algorithms")
        self.assertEqual([t["title"] for t in certified], ["In-Order Traversal", "Pre-Order Traversal"])

    def test_coding_implementation_never_moves_before_its_walkthrough(self):
        from app.services.topic_generator import _certify_path_scope

        topics = [
            {"title": "Dijkstra's Algorithm Walkthrough", "subject_key": "dijkstra",
             "topic_type": "algorithm_walkthrough", "course_type": "algorithm_walkthrough",
             "purpose": "p", "learner_outcome": "o", "in_scope": ["trace"],
             "out_of_scope": [], "prerequisite_topics": [], "order_index": 1},
            {"title": "Implementing Priority Queues", "subject_key": "priority_queue",
             "topic_type": "coding_implementation", "course_type": "coding_implementation",
             "purpose": "p", "learner_outcome": "o", "in_scope": ["heap code"],
             "out_of_scope": [], "prerequisite_topics": [], "order_index": 2},
        ]
        certified = _certify_path_scope(topics, "learn dijkstra's algorithm")
        self.assertEqual([t["title"] for t in certified],
                         ["Dijkstra's Algorithm Walkthrough", "Implementing Priority Queues"])


if __name__ == "__main__":
    unittest.main()
