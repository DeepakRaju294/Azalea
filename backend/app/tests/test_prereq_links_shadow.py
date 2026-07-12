"""Prereq-links production shadow (PREREQ_LINKS_SPEC v8 §6.1/§6.3a/§6.7).

`app.services.prereq_links_shadow` imports only the pure `prereq_links` + `study_path_scope` packages + stdlib
(no routes/deps), so it is safe to import here without the .env/load_dotenv landmine. Topics are duck-typed."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.prereq_links_shadow import (
    maybe_log_prereq_links_shadow, shadow_report, topics_to_classification,
)

_FLAG = "AZALEA_PREREQ_LINKS"


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
        rep = maybe_log_prereq_links_shadow("goal", "physics", _ohms_law_path())
        self.assertIsNotNone(rep)
        self.assertTrue(rep["ok"])


if __name__ == "__main__":
    unittest.main()
