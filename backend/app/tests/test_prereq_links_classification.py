"""Tier-2 classification validation (PREREQ_LINKS_SPEC v8 §6.3a) — the pure structural subset of PR1's
acceptance set. Imports ONLY the pure `app.core.prereq_links` package (no routes/services), so it does not
trip the .env/load_dotenv landmine.

Covers: clean pass, A11 (disjointness), A15 (missing target_goal), A37 (duplicate ownership), A41 (non-owning
synthesis topic is fine), A36-companion owner-resolvability, scope_rule validity per variant, and the
navigation-set normalized-alias uniqueness check."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.core.prereq_links import (
    AssumedPrerequisite, Classification, DecompositionClassification, FallbackReason, InPathFoundation,
    ScopeRule, TopicConceptIdentity, normalize_identity, validate_classification,
)


def _ap(concept_id, target_goal="Understand X.", canonical=None, aliases=None,
        scope_rule=ScopeRule.recognition_only_fallback):
    return AssumedPrerequisite(concept_id=concept_id, canonical_name=canonical or concept_id,
                              aliases=aliases or [], display_text=concept_id.title(),
                              target_goal=target_goal, scope_rule=scope_rule)


def _tci(topic_id, concept_id, index, canonical=None, aliases=None):
    return TopicConceptIdentity(topic_id=topic_id, topic_index=index, concept_id=concept_id,
                               canonical_name=canonical or concept_id, aliases=aliases or [])


def _foundation(concept_id, scope_rule=ScopeRule.competency_required, canonical=None):
    return InPathFoundation(concept_id=concept_id, canonical_name=canonical or concept_id, scope_rule=scope_rule)


def _reasons(result):
    return {f.reason for f in result.failures}


class CleanPass(unittest.TestCase):
    def test_valid_ohms_law_classification_passes(self):
        # A1/A2 shape: voltage/current/resistance out-of-scope prereqs; ohms_law is the taught owner.
        dc = DecompositionClassification(
            assumed_prerequisites=[_ap("voltage"), _ap("current"), _ap("resistance")],
            topic_identities=[_tci("t1", "ohms_law", 0)],
            review_referenced_concept_ids=[],
        )
        res = validate_classification(dc)
        self.assertTrue(res.ok, res.failures)
        self.assertIsNone(res.fallback_reason)


class DisjointnessA11(unittest.TestCase):
    def test_prereq_that_is_also_taught_is_tier2_overlap(self):
        dc = DecompositionClassification(
            assumed_prerequisites=[_ap("voltage")],
            topic_identities=[_tci("t1", "voltage", 0)],   # voltage owned AND assumed → contradiction
        )
        res = validate_classification(dc)
        self.assertFalse(res.ok)
        self.assertIn(FallbackReason.prerequisite_topic_overlap, _reasons(res))

    def test_prereq_overlapping_a_foundation_is_tier2_overlap(self):
        dc = DecompositionClassification(
            assumed_prerequisites=[_ap("vectors")],
            in_path_foundations=[_foundation("vectors")],
        )
        res = validate_classification(dc)
        self.assertFalse(res.ok)
        self.assertIn(FallbackReason.prerequisite_topic_overlap, _reasons(res))


class MissingTargetGoalA15(unittest.TestCase):
    def test_empty_target_goal_is_tier2_not_silent_omission(self):
        dc = DecompositionClassification(assumed_prerequisites=[_ap("voltage", target_goal="   ")])
        res = validate_classification(dc)
        self.assertFalse(res.ok)
        self.assertIn(FallbackReason.missing_target_goal, _reasons(res))


class DuplicateOwnershipA37(unittest.TestCase):
    def test_two_topics_owning_one_concept_is_tier2(self):
        dc = DecompositionClassification(topic_identities=[
            _tci("t1", "voltage", 0), _tci("t2", "voltage", 3),   # two owners for one concept_id
        ])
        res = validate_classification(dc)
        self.assertFalse(res.ok)
        self.assertIn(FallbackReason.duplicate_concept_ownership, _reasons(res))

    def test_duplicate_topic_id_is_tier2(self):
        dc = DecompositionClassification(topic_identities=[
            _tci("t1", "voltage", 0), _tci("t1", "current", 1),   # same topic_id twice
        ])
        res = validate_classification(dc)
        self.assertFalse(res.ok)
        self.assertIn(FallbackReason.duplicate_identity_key, _reasons(res))


class NonOwningSynthesisA41(unittest.TestCase):
    def test_synthesis_topic_without_identity_is_normal(self):
        # A synthesis/review topic simply emits no TopicConceptIdentity; owners stay unique; review still resolves.
        dc = DecompositionClassification(
            topic_identities=[_tci("t1", "voltage", 0), _tci("t2", "current", 1)],
            review_referenced_concept_ids=["voltage"],   # resolves to the one owner
        )
        res = validate_classification(dc)
        self.assertTrue(res.ok, res.failures)


class OwnerResolvability(unittest.TestCase):
    def test_review_reference_with_no_owner_is_tier2(self):
        dc = DecompositionClassification(
            topic_identities=[_tci("t1", "voltage", 0)],
            review_referenced_concept_ids=["capacitance"],   # no owner
        )
        res = validate_classification(dc)
        self.assertFalse(res.ok)
        self.assertIn(FallbackReason.missing_owner_for_review, _reasons(res))


class ScopeRuleValidity(unittest.TestCase):
    def test_assumed_prerequisite_must_be_recognition_only_fallback(self):
        dc = DecompositionClassification(
            assumed_prerequisites=[_ap("voltage", scope_rule=ScopeRule.competency_required)])
        res = validate_classification(dc)
        self.assertFalse(res.ok)
        self.assertIn(FallbackReason.invalid_scope_rule, _reasons(res))

    def test_foundation_must_use_an_in_scope_rule(self):
        dc = DecompositionClassification(
            in_path_foundations=[_foundation("voltage", scope_rule=ScopeRule.recognition_only_fallback)])
        res = validate_classification(dc)
        self.assertFalse(res.ok)
        self.assertIn(FallbackReason.invalid_scope_rule, _reasons(res))


class NavigationAliasUniqueness(unittest.TestCase):
    def test_one_normalized_alias_mapping_to_two_concepts_is_tier2(self):
        dc = DecompositionClassification(
            assumed_prerequisites=[_ap("emf", canonical="EMF", aliases=["Potential Difference"])],
            topic_identities=[_tci("t1", "voltage", 0, canonical="Voltage", aliases=["potential difference"])],
        )
        res = validate_classification(dc)
        self.assertFalse(res.ok)
        self.assertIn(FallbackReason.ambiguous_navigation_identity, _reasons(res))

    def test_same_concept_under_multiple_surfaces_is_fine(self):
        dc = DecompositionClassification(
            topic_identities=[_tci("t1", "voltage", 0, canonical="Voltage",
                                   aliases=["potential difference", "Potential Difference", "voltage"])])
        res = validate_classification(dc)
        self.assertTrue(res.ok, res.failures)


class Normalization(unittest.TestCase):
    def test_apostrophe_and_case_and_whitespace(self):
        self.assertEqual(normalize_identity("Ohm’s  Law"), normalize_identity("ohm's law"))

    def test_hyphen_is_preserved(self):
        self.assertNotEqual(normalize_identity("potential-difference"), normalize_identity("potential difference"))


if __name__ == "__main__":
    unittest.main()
