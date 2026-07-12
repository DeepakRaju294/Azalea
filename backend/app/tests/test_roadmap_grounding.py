"""The intro roadmap card must be a CLEAN, accurate 'what's ahead' list built from the real upcoming topics —
never the model's free-text lead-in. Regression for a live path whose roadmap read:
  "Uh oh! Why did we avoid practicing Ohm's Law? It's because it's uniquely tied to:"
  "  - Understanding how these concepts interact in circuits: Fluidic Circuits: Voltage is the applied ..."
which is a hallucinated framing + concept-salad, not a topic preview."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.lean_lesson_generator import _ground_roadmap_card


class _Topic:
    def __init__(self, tid, title, order, purpose="", learner_outcome="", course_type="concept"):
        self.id, self.title, self.order_index = tid, title, order
        self.purpose, self.learner_outcome, self.course_type = purpose, learner_outcome, course_type
        self.topic_type = None
        self.study_path = None


class _Path:
    def __init__(self, topics):
        self.topics = topics
        for t in topics:
            t.study_path = self


def _roadmap_points(cards):
    return next(c["points"] for c in cards if c.get("card_type") == "roadmap")


class RoadmapGrounding(unittest.TestCase):
    def _intro_and_siblings(self, siblings):
        intro = _Topic("intro", "Introduction", 0, course_type="study_path_introduction")
        _Path([intro, *siblings])
        return intro

    def test_hallucinated_lead_in_is_replaced(self):
        sib = _Topic("t1", "Ohm's Law", 1,
                     learner_outcome="Apply Ohm's Law to solve for current, voltage, or resistance.")
        intro = self._intro_and_siblings([sib])
        cards = [{"card_type": "roadmap", "title": "Study Path Overview", "points": [
            "Uh oh! Why did we avoid practicing Ohm's Law? It's because it's uniquely tied to:",
            "  - Understanding how these concepts interact in circuits: Fluidic Circuits: Voltage is the applied "
            "pressure causing Current flow in a fluid-like electrical system!",
            "  - Using Ohm's law to analyze circuit performance and behavior.",
        ]}]
        pts = _roadmap_points(_ground_roadmap_card(cards, intro))
        blob = " ".join(pts)
        self.assertNotIn("Uh oh", blob)
        self.assertNotIn("Fluidic", blob)
        self.assertEqual(pts[0], "Ohm's Law:")                     # no misleading colon lead-in; topic first
        self.assertTrue(pts[1].strip().startswith("-"))            # its summary is a SUBbullet (correct nesting)
        self.assertTrue(any("Apply Ohm's Law" in p for p in pts))  # accurate summary from learner_outcome

    def test_multiple_siblings_listed_in_order(self):
        sibs = [_Topic("t1", "Voltage Basics", 1, learner_outcome="Understand voltage."),
                _Topic("t2", "Ohm's Law", 2, learner_outcome="Apply the formula.")]
        intro = self._intro_and_siblings(sibs)
        cards = [{"card_type": "roadmap", "points": ["whatever the model said"]}]
        pts = _roadmap_points(_ground_roadmap_card(cards, intro))
        self.assertEqual(pts[0], "Voltage Basics:")                              # first topic, no lead-in
        self.assertLess(pts.index("Voltage Basics:"), pts.index("Ohm's Law:"))   # topic order preserved

    def test_no_siblings_leaves_cards_untouched(self):
        intro = self._intro_and_siblings([])
        cards = [{"card_type": "roadmap", "points": ["original"]}]
        self.assertEqual(_ground_roadmap_card(cards, intro), cards)


if __name__ == "__main__":
    unittest.main()
