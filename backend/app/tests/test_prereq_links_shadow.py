"""Prereq-links production shadow (PREREQ_LINKS_SPEC v8 §6.1/§6.3a/§6.7).

`app.services.prereq_links_shadow` imports only the pure `prereq_links` + `study_path_scope` packages + stdlib
(no routes/deps), so it is safe to import here without the .env/load_dotenv landmine. Topics are duck-typed.

The real §3.1 classifier (app.services.prereq_scope_classifier) is exercised offline throughout via an injected
fake `model_fn` — never a live LLM call — and only activates when BOTH a non-empty `goal` is passed AND
AZALEA_PREREQ_SCOPE_CLASSIFICATION is explicitly on (the rollback kill-switch, default off)."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.core.prereq_links import validate_classification
from app.services.prereq_links_shadow import (
    _build_classification, maybe_log_prereq_links_shadow, shadow_report, topics_to_classification,
)

_FLAG = "AZALEA_PREREQ_LINKS"
_CLASSIFY_FLAG = "AZALEA_PREREQ_SCOPE_CLASSIFICATION"


class FakeTopic:
    def __init__(self, tid, title, order, prereqs=None, course_type="concept", metadata=None):
        self.id = tid
        self.title = title
        self.order_index = order
        self.course_type = course_type
        self.assumed_prerequisites = prereqs or []
        self.decomposition_metadata = metadata or {}


def _ohms_law_path():
    # Ohm's law taught; voltage/current/resistance are assumed prerequisites (disjoint from the taught concept).
    return [
        FakeTopic("intro", "Introduction", 0, course_type="study_path_introduction"),
        FakeTopic("t1", "Ohm's Law", 1, prereqs=["Voltage", "Current", "Resistance"]),
        FakeTopic("t2", "Power Dissipation", 2, prereqs=["Voltage"]),
    ]


class Mapping(unittest.TestCase):
    def test_intro_excluded_and_prereqs_deduped(self):
        dc = topics_to_classification(_ohms_law_path())
        self.assertEqual({t.canonical_name for t in dc.topic_identities}, {"Ohm's Law", "Power Dissipation"})
        self.assertEqual({p.canonical_name for p in dc.assumed_prerequisites},
                         {"Voltage", "Current", "Resistance"})

    def test_topic_index_is_monotonic(self):
        dc = topics_to_classification(_ohms_law_path())
        self.assertEqual([t.topic_index for t in dc.topic_identities], [0, 1])


class ShadowReport(unittest.TestCase):
    def test_clean_path_passes(self):
        rep = shadow_report(_ohms_law_path())
        self.assertTrue(rep["ok"], rep)
        self.assertIsNone(rep["fallback_reason"])
        self.assertEqual(rep["n_topics"], 2)
        self.assertEqual(rep["n_prereqs"], 3)

    def test_prereq_naming_an_earlier_topic_is_review_earlier_not_overlap(self):
        # A later topic naming an EARLIER taught topic as a "prerequisite" is an intra-path dependency →
        # in-scope review_earlier_topic, NOT a disjointness violation. (The corpus showed every such case is
        # benign "topic B builds on earlier topic A".) So it is reclassified, not routed to assumed_prerequisites.
        topics = [
            FakeTopic("t1", "Voltage", 0),                       # taught earlier
            FakeTopic("t2", "Ohm's Law", 1, prereqs=["Voltage"]),  # ...and reviewed by a later topic
        ]
        rep = shadow_report(topics)
        self.assertTrue(rep["ok"], rep)
        self.assertEqual(rep["n_prereqs"], 0)                    # "Voltage" is a review ref, not an external prereq

    def test_prereq_matching_no_topic_stays_external(self):
        # A prerequisite that matches no taught topic is a true external assumed_prerequisite.
        topics = [FakeTopic("t1", "Ohm's Law", 0, prereqs=["Voltage", "Current"])]
        rep = shadow_report(topics)
        self.assertTrue(rep["ok"], rep)
        self.assertEqual(rep["n_prereqs"], 2)

    def test_empty_topics_do_not_throw(self):
        rep = shadow_report([])
        self.assertTrue(rep["ok"])

    def test_prereqs_stored_on_intro_are_counted(self):
        # The real DB shape: the intro names the prerequisites (not the concept topics). Harvesting only from
        # concept topics would report n_prereqs=0 and never see the overlap.
        topics = [
            FakeTopic("i", "Introduction", 0, prereqs=["Voltage", "Current", "Resistance"],
                      course_type="study_path_introduction"),
            FakeTopic("t1", "Ohm's Law", 1),
        ]
        rep = shadow_report(topics)
        self.assertEqual(rep["n_prereqs"], 3)
        self.assertTrue(rep["ok"])   # prereqs disjoint from the one taught concept


class FlagGating(unittest.TestCase):
    def setUp(self):
        self._prev = os.environ.get(_FLAG)

    def tearDown(self):
        if self._prev is None:
            os.environ.pop(_FLAG, None)
        else:
            os.environ[_FLAG] = self._prev

    def test_off_returns_none(self):
        os.environ.pop(_FLAG, None)
        self.assertIsNone(maybe_log_prereq_links_shadow("goal", "physics", _ohms_law_path()))

    def test_on_returns_report(self):
        os.environ[_FLAG] = "1"
        # A non-empty goal now reaches _build_classification — pass an explicit fake model_fn so this stays
        # instant/offline (AZALEA_PREREQ_SCOPE_CLASSIFICATION also defaults off in this test's environment, so
        # no call would be attempted regardless, but an explicit fake documents that intentionally rather than
        # relying on the kill-switch's default).
        rep = maybe_log_prereq_links_shadow("goal", "physics", _ohms_law_path(), model_fn=_fake_fn())
        self.assertIsNotNone(rep)
        self.assertTrue(rep["ok"])


def _fake_fn(rule_for=None, raise_for=None):
    """A fake classifier model_fn. `rule_for`: {canonical_name: scope_rule string}, default fallback for
    anything unlisted. `raise_for`: canonical_names that raise instead of returning, to test isolation."""
    calls = []

    def fn(payload):
        calls.append(payload)
        name = payload.get("canonical_name")
        if raise_for and name in raise_for:
            raise RuntimeError(f"simulated classifier failure for {name!r}")
        rule = (rule_for or {}).get(name, "recognition_only_fallback")
        return {"scope_rule": rule, "scope_rationale": f"rationale for {name}"}

    fn.calls = calls
    return fn


class _ClassificationEnabled(unittest.TestCase):
    """Enables the AZALEA_PREREQ_SCOPE_CLASSIFICATION kill-switch for the duration of each test."""

    def setUp(self):
        self._prev = os.environ.get(_CLASSIFY_FLAG)
        os.environ[_CLASSIFY_FLAG] = "1"

    def tearDown(self):
        if self._prev is None:
            os.environ.pop(_CLASSIFY_FLAG, None)
        else:
            os.environ[_CLASSIFY_FLAG] = self._prev


class PrereqOhmsLaw(_ClassificationEnabled):
    """A1: a mention-only goal — voltage/current/resistance are genuinely out of scope; classification should
    agree (fallback), leaving scope_rule unchanged but now with a real rationale, and no mismatch."""

    def test_mention_only_goal_stays_fallback_with_rationale(self):
        fn = _fake_fn()   # everything falls back
        dc, mismatches, _dist = _build_classification(
            _ohms_law_path(), "Understand Ohm's law", "physics", fn)
        voltage = next(p for p in dc.assumed_prerequisites if p.canonical_name == "Voltage")
        self.assertEqual(voltage.scope_rule.value, "recognition_only_fallback")
        self.assertTrue(voltage.scope_rationale)
        self.assertEqual(mismatches, [])


class PrereqInPathFoundation(_ClassificationEnabled):
    """A9: a broad from-scratch goal with Voltage taught in-path and tagged content_role=foundation —
    classification should agree it's in scope, emitting a matching InPathFoundation."""

    def test_broad_beginner_goal_emits_in_path_foundation(self):
        topics = [
            FakeTopic("intro", "Introduction", 0, course_type="study_path_introduction"),
            FakeTopic("t1", "Voltage", 1, metadata={"content_role": "foundation"}),
            FakeTopic("t2", "Ohm's Law", 2, prereqs=["Voltage"]),
        ]
        fn = _fake_fn(rule_for={"Voltage": "beginner_minimum_sequence"})
        dc, mismatches, dist = _build_classification(
            topics, "Learn basic DC circuits from scratch", "physics", fn)
        self.assertEqual(len(dc.in_path_foundations), 1)
        foundation = dc.in_path_foundations[0]
        self.assertEqual(foundation.canonical_name, "Voltage")
        self.assertEqual(foundation.scope_rule.value, "beginner_minimum_sequence")
        self.assertTrue(foundation.scope_rationale)
        # still present as an ordinary identity too (unconditional, built before any classification)
        self.assertIn("Voltage", {t.canonical_name for t in dc.topic_identities})
        self.assertEqual(mismatches, [])
        self.assertEqual(dist, {"beginner_minimum_sequence": 1})


class PrereqMentionNotObjective(_ClassificationEnabled):
    """A29: a contextual-mention goal — classification should agree voltage/current stay assumed_prerequisite,
    no disagreement recorded."""

    def test_contextual_mention_stays_assumed_prerequisite(self):
        topics = [FakeTopic("t1", "Ohm's Law", 0, prereqs=["Voltage", "Current"])]
        fn = _fake_fn()   # everything falls back
        dc, mismatches, _dist = _build_classification(
            topics, "How does Ohm's law relate voltage and current?", "physics", fn)
        self.assertEqual({p.scope_rule.value for p in dc.assumed_prerequisites}, {"recognition_only_fallback"})
        self.assertEqual(mismatches, [])


class PrereqScopeRuleTelemetry(_ClassificationEnabled):
    """A35: both distribution counters round-trip through shadow_report, with a non-empty rationale."""

    def test_distributions_round_trip_through_shadow_report(self):
        topics = [
            FakeTopic("t1", "Voltage", 0, metadata={"content_role": "foundation"}),
            FakeTopic("t2", "Ohm's Law", 1, prereqs=["Current"]),
        ]
        fn = _fake_fn(rule_for={"Voltage": "beginner_minimum_sequence"})
        rep = shadow_report(topics, goal="Learn basic DC circuits from scratch", domain="physics", model_fn=fn)
        self.assertEqual(rep["scope_rule_distribution"], {"beginner_minimum_sequence": 1,
                                                           "recognition_only_fallback": 1})
        self.assertEqual(rep["classified_scope_rule_distribution"], {"beginner_minimum_sequence": 1,
                                                                      "recognition_only_fallback": 1})


class ContractSafety(_ClassificationEnabled):
    """The hard invariant (validation.py check #6): AssumedPrerequisite.scope_rule can ONLY ever be
    recognition_only_fallback, no matter what the classifier recommends."""

    def test_in_scope_recommendation_never_lands_on_the_object(self):
        topics = [FakeTopic("t1", "Ohm's Law", 0, prereqs=["Voltage"])]
        fn = _fake_fn(rule_for={"Voltage": "competency_required"})
        dc, mismatches, _dist = _build_classification(topics, "learn ohm's law well", "physics", fn)
        voltage = next(p for p in dc.assumed_prerequisites if p.canonical_name == "Voltage")
        self.assertEqual(voltage.scope_rule.value, "recognition_only_fallback")
        self.assertEqual(mismatches, [{
            "canonical_name": "Voltage", "candidate_kind": "assumed_prerequisite",
            "direction": "assumed_but_model_says_in_scope",
            "assigned_rule": "recognition_only_fallback", "classified_rule": "competency_required",
        }])
        self.assertTrue(validate_classification(dc).ok)   # never trips the Tier-2 validator

    def test_symmetric_taught_foundation_fallback_case(self):
        topics = [FakeTopic("t1", "Voltage", 0, metadata={"content_role": "foundation"})]
        fn = _fake_fn()   # classifier disagrees this belongs in-path
        dc, mismatches, _dist = _build_classification(topics, "learn ohm's law well", "physics", fn)
        self.assertEqual(dc.in_path_foundations, [])
        self.assertIn("Voltage", {t.canonical_name for t in dc.topic_identities})   # identity untouched
        self.assertEqual(mismatches, [{
            "canonical_name": "Voltage", "candidate_kind": "taught_foundation",
            "direction": "taught_but_model_says_fallback",
            "assigned_rule": None, "classified_rule": "recognition_only_fallback",
        }])
        self.assertTrue(validate_classification(dc).ok)


class FoundationOwnershipAndAliases(_ClassificationEnabled):
    def test_only_the_structural_owner_is_classified_not_a_later_duplicate_titled_topic(self):
        # Two topics share the same title (-> same concept_key); the EARLIEST is the structural owner. Only
        # the LATER one is tagged content_role=foundation — the owner itself carries no such tag, so this
        # concept must never be classified at all (owner's content_role is checked, not any mentioning topic's).
        topics = [
            FakeTopic("t1", "Voltage", 0),
            FakeTopic("t2", "Voltage", 1, metadata={"content_role": "foundation"}),
        ]
        fn = _fake_fn(rule_for={"Voltage": "beginner_minimum_sequence"})
        dc, mismatches, dist = _build_classification(topics, "learn voltage", "physics", fn)
        self.assertEqual(dc.in_path_foundations, [])
        self.assertEqual(mismatches, [])
        self.assertEqual(dist, {})
        self.assertEqual(len(fn.calls), 0)


class CandidateIsolation(_ClassificationEnabled):
    def test_one_failing_candidate_does_not_suppress_the_others(self):
        topics = [FakeTopic("t1", "Ohm's Law", 0, prereqs=["Voltage", "Current", "Resistance"])]
        fn = _fake_fn(raise_for={"Current"})
        dc, _mismatches, _dist = _build_classification(topics, "learn ohm's law well", "physics", fn)
        by_name = {p.canonical_name: p for p in dc.assumed_prerequisites}
        self.assertEqual(set(by_name), {"Voltage", "Current", "Resistance"})   # nothing dropped
        self.assertTrue(by_name["Voltage"].scope_rationale)
        self.assertTrue(by_name["Resistance"].scope_rationale)
        self.assertEqual(by_name["Current"].scope_rationale, "")               # degraded, not dropped
        self.assertEqual(by_name["Current"].scope_rule.value, "recognition_only_fallback")
        self.assertTrue(by_name["Current"].target_goal)                        # still built (deterministic, §A15)


class DuplicateMentionsDeduped(_ClassificationEnabled):
    def test_same_prerequisite_named_by_two_topics_is_classified_once(self):
        topics = [
            FakeTopic("t1", "Ohm's Law", 0, prereqs=["Voltage"]),
            FakeTopic("t2", "Power Dissipation", 1, prereqs=["Voltage"]),
        ]
        fn = _fake_fn()
        dc, _mismatches, _dist = _build_classification(topics, "learn ohm's law well", "physics", fn)
        self.assertEqual(len([p for p in dc.assumed_prerequisites if p.canonical_name == "Voltage"]), 1)
        self.assertEqual(len(fn.calls), 1)


class EmptyClassificationSurface(_ClassificationEnabled):
    def test_no_foundations_no_prereqs_empty_telemetry(self):
        topics = [FakeTopic("t1", "Some Topic", 0)]
        rep = shadow_report(topics, goal="learn some topic", domain="physics", model_fn=_fake_fn())
        self.assertEqual(rep["scope_rule_distribution"], {})
        self.assertEqual(rep["classified_scope_rule_distribution"], {})
        self.assertEqual(rep["scope_mismatches"], [])


class ClassificationKillSwitch(unittest.TestCase):
    """AZALEA_PREREQ_SCOPE_CLASSIFICATION defaults OFF — real classification must not run even with a
    non-empty goal and a real model_fn, until explicitly enabled."""

    def setUp(self):
        self._prev = os.environ.get(_CLASSIFY_FLAG)
        os.environ.pop(_CLASSIFY_FLAG, None)

    def tearDown(self):
        if self._prev is not None:
            os.environ[_CLASSIFY_FLAG] = self._prev

    def test_disabled_by_default_zero_model_calls(self):
        topics = [FakeTopic("t1", "Ohm's Law", 0, prereqs=["Voltage"])]
        fn = _fake_fn(rule_for={"Voltage": "competency_required"})
        dc, mismatches, dist = _build_classification(topics, "learn ohm's law well", "physics", fn)
        self.assertEqual(len(fn.calls), 0)
        self.assertEqual(dist, {})
        self.assertEqual(mismatches, [])
        voltage = next(p for p in dc.assumed_prerequisites if p.canonical_name == "Voltage")
        self.assertEqual(voltage.scope_rule.value, "recognition_only_fallback")
        self.assertEqual(voltage.scope_rationale, "")
        self.assertTrue(voltage.target_goal)   # still deterministic, still built


if __name__ == "__main__":
    unittest.main()
