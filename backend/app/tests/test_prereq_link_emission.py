"""§6.2 live emission: the lean generator populates each card's interactive_links from the deterministic
scanner — review_earlier_topic for a concept taught by an EARLIER topic in the path, open_study_path for an
external assumed prerequisite. Flag-gated (AZALEA_PREREQ_LINKS); off ⇒ links stay []."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.lean_lesson_generator import _emit_prereq_interactive_links

_FLAG = "AZALEA_PREREQ_LINKS"


class _Topic:
    def __init__(self, tid, title, order, prereqs=None, course_type="concept"):
        self.id, self.title, self.order_index = tid, title, order
        self.course_type, self.topic_type = course_type, None
        self.assumed_prerequisites = prereqs or []
        self.decomposition_metadata = {}
        self.study_path = None


class _Path:
    def __init__(self, topics, domain="cs"):
        self.topics, self.domain = topics, domain
        for t in topics:
            t.study_path = self


class PrereqLinkEmission(unittest.TestCase):
    def setUp(self):
        self._prev = os.environ.get(_FLAG)

    def tearDown(self):
        if self._prev is None:
            os.environ.pop(_FLAG, None)
        else:
            os.environ[_FLAG] = self._prev

    def _sorting_path(self):
        intro = _Topic("i", "Introduction to Sorting", 0, course_type="study_path_introduction")
        comp = _Topic("t1", "Comparison Sort", 1)
        quick = _Topic("t2", "Quick Sort", 2)
        _Path([intro, comp, quick])
        return intro, comp, quick

    def test_flag_off_leaves_links_empty(self):
        os.environ.pop(_FLAG, None)
        _, _, quick = self._sorting_path()
        cards = [{"card_type": "background", "points": ["Quick Sort relies on Comparison Sort ideas."]}]
        out = _emit_prereq_interactive_links(cards, quick)
        self.assertEqual(out[0].get("interactive_links", "MISSING"), "MISSING")

    def test_review_earlier_topic_for_intra_path_dependency(self):
        os.environ[_FLAG] = "1"
        _, comp, quick = self._sorting_path()
        cards = [{"card_type": "background", "points": ["Quick Sort builds on Comparison Sort."]}]
        out = _emit_prereq_interactive_links(cards, quick)
        links = out[0]["interactive_links"]
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["action"], "review_earlier_topic")
        self.assertEqual(links[0]["target"], "t1")                 # Comparison Sort's topic_id
        self.assertEqual(links[0]["text"], "Comparison Sort")
        self.assertEqual(links[0]["concept_id"], "comparison_sort")

    def test_no_self_link_to_current_topic(self):
        os.environ[_FLAG] = "1"
        _, _, quick = self._sorting_path()
        cards = [{"card_type": "background", "points": ["Quick Sort is a fast sort."]}]  # mentions itself only
        out = _emit_prereq_interactive_links(cards, quick)
        self.assertEqual(out[0]["interactive_links"], [])

    def test_open_study_path_for_external_prerequisite_on_intro(self):
        os.environ[_FLAG] = "1"
        intro = _Topic("i", "Introduction to Ohm's Law", 0, prereqs=["Voltage"],
                       course_type="study_path_introduction")
        _Path([intro, _Topic("t1", "Ohm's Law", 1)])
        cards = [{"card_type": "background", "points": ["This path assumes you know Voltage."]}]
        out = _emit_prereq_interactive_links(cards, intro)
        links = out[0]["interactive_links"]
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["action"], "open_study_path")
        self.assertEqual(links[0]["text"], "Voltage")
        self.assertTrue(links[0]["target"])                        # a scoped target goal


if __name__ == "__main__":
    unittest.main()
