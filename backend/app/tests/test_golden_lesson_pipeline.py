"""Golden regression net for the deterministic lesson finalization (_normalize_lean_card_order).

The reviewer's core concern was silent partial degradation — best-effort passes swallowing failures so a
regression ships unnoticed (how the char-explosion and the prereq-card revert both happened). This drives the
REAL intro finalization pipeline on one rich fixture and asserts every property this session established, so any
future change that breaks one trips a loud test failure instead of reaching a learner.
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.lean_lesson_generator import _normalize_lean_card_order

_FLAG = "AZALEA_PREREQ_LINKS"


class _Topic:
    def __init__(self, tid, title, order, ctype, prereqs=None, glosses=None, reqs=None, in_scope=None):
        self.id, self.title, self.order_index = tid, title, order
        self.course_type = self.topic_type = ctype
        self.assumed_prerequisites = prereqs or []
        self.in_scope = in_scope or []
        self.decomposition_metadata = {"assumed_prerequisite_glosses": glosses or {},
                                       "assumed_prerequisite_requirements": reqs or {}}
        self.study_path = None


class _Path:
    def __init__(self, topics, domain="math", goal="learn bayes theorem"):
        self.topics, self.domain, self.goal = topics, domain, goal
        for t in topics:
            t.study_path = self


def _is_char_explosion(points) -> bool:
    """A worked-example shredded into one character per bullet — the class of bug this net must catch."""
    singles = sum(1 for p in points if len(str(p).strip().lstrip("- ").strip()) == 1)
    return singles >= 3


class GoldenIntroFinalization(unittest.TestCase):
    def setUp(self):
        self._prev = os.environ.get(_FLAG)
        os.environ[_FLAG] = "1"
        os.environ.pop("AZALEA_TERM_GLOSSES", None)      # popups off (no LLM call)

    def tearDown(self):
        if self._prev is None:
            os.environ.pop(_FLAG, None)
        else:
            os.environ[_FLAG] = self._prev

    def _run(self):
        intro = _Topic("i", "Introduction to Bayes", 0, "study_path_introduction",
                       prereqs=["conditional probability"],
                       glosses={"conditional probability": "the probability of one event given another"},
                       reqs={"conditional probability": "compute P(A|B) from a table"})
        bayes = _Topic("t1", "Bayes' Theorem", 1, "math_formula_method", in_scope=["posterior probability"])
        _Path([intro, bayes])
        cards = [
            {"blueprint_key": "background", "card_type": "background",
             "points": ["Bayes updates beliefs from evidence."]},
            {"blueprint_key": "prerequisites", "card_type": "prerequisites", "title": "Prerequisites",
             "points": ["placeholder prose the grounding replaces"]},
            {"blueprint_key": "components_terms", "card_type": "components_terms", "title": "Key Terms",
             "points": ["Conditional Probability", "  - prob of A given B",   # a PREREQUISITE -> relocated out
                        "Probability", "  - a measure of likelihood",          # elementary -> stripped
                        "Bayes' Theorem", "  - the update rule",               # a TAUGHT topic -> stripped
                        "Sample Space", "  - the set of all outcomes"]},       # genuine shared term -> kept
            {"blueprint_key": "roadmap", "card_type": "roadmap",
             "points": ["Bayes' Theorem:", "  - learn the update rule"]},
        ]
        return _normalize_lean_card_order(cards, intro)

    def test_all_golden_properties_hold(self):
        out = self._run()
        by_key = {}
        for c in out:
            by_key.setdefault(str(c.get("blueprint_key") or c.get("card_type")), c)

        # (a) no card was shredded into single characters
        for c in out:
            self.assertFalse(_is_char_explosion(c.get("points") or []), c.get("title"))

        # (b) prereq card = idea-group shape: bare name main bullet + two labeled sub-bullets
        prereq = by_key.get("prerequisites")
        self.assertIsNotNone(prereq)
        self.assertEqual(prereq["points"], [
            "conditional probability",
            "  - What it is: the probability of one event given another",
            "  - What to learn: compute P(A|B) from a table"])

        # (c) the prereq name is a live open_study_path link, anchored to its item
        links = prereq.get("interactive_links") or []
        osp = [l for l in links if l["action"] == "open_study_path"]
        self.assertEqual(len(osp), 1)
        self.assertEqual(osp[0]["text"], "conditional probability")
        self.assertEqual(osp[0]["anchor"], {"field": "points", "index": 0})

        # (d) key-terms card holds ONLY the genuine shared term — prereq/taught-topic/elementary all removed
        kt = by_key.get("components_terms")
        if kt is not None:
            joined = " ".join(kt.get("points") or [])
            self.assertIn("Sample Space", joined)
            self.assertNotIn("Conditional Probability", joined)   # prereq relocated
            self.assertNotIn("Probability —", joined)             # elementary stripped (bare "Probability")
            self.assertNotIn("Bayes' Theorem", joined)            # taught-topic stripped

    def test_pipeline_is_idempotent(self):
        # Running the finalizer twice must not double-transform (a pass that isn't idempotent is a latent bug).
        out1 = self._run()
        # feed its own output back in
        intro = _Topic("i", "Introduction to Bayes", 0, "study_path_introduction",
                       prereqs=["conditional probability"],
                       glosses={"conditional probability": "the probability of one event given another"},
                       reqs={"conditional probability": "compute P(A|B) from a table"})
        _Path([intro, _Topic("t1", "Bayes' Theorem", 1, "math_formula_method")])
        out2 = _normalize_lean_card_order(out1, intro)
        pre1 = next(c for c in out1 if (c.get("blueprint_key") or c.get("card_type")) == "prerequisites")
        pre2 = next(c for c in out2 if (c.get("blueprint_key") or c.get("card_type")) == "prerequisites")
        self.assertEqual(pre1["points"], pre2["points"])


if __name__ == "__main__":
    unittest.main()
