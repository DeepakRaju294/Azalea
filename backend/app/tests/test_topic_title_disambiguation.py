"""Decomposition validation (naming): a LATE synthesis/application topic must not carry the whole path's
title ('Combinatorial Analysis' on a Combinatorial-Analysis path) and no topic may duplicate an earlier
one — both read as 'why is this here?'. A single-concept path whose one topic legitimately IS the subject
is left alone."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.topic_decomposition_pipeline import _disambiguate_topic_titles


def _t(title, role="math_formula_method", ttype="math_formula_method"):
    return {"title": title, "content_role": role, "topic_type": ttype}


def _intro():
    return {"title": "Introduction", "topic_type": "study_path_introduction", "content_role": "orientation"}


class Disambiguation(unittest.TestCase):
    def test_late_synthesis_named_like_path_is_renamed(self):
        topics = [_intro(), _t("Permutations"), _t("Combinations"), _t("Binomial Theorem"),
                  _t("Combinatorial Analysis", role="application", ttype="problem_solving_application")]
        _disambiguate_topic_titles(topics, "Want to learn about combinatorial analysis")
        self.assertEqual(topics[-1]["title"], "Applying Combinatorial Analysis")

    def test_single_concept_topic_named_like_goal_is_left_alone(self):
        # No teaching topics precede it — it IS the primary lesson, not a redundant synthesis.
        topics = [_intro(), _t("Bayes' Theorem", role="application", ttype="math_formula_method")]
        _disambiguate_topic_titles(topics, "learn bayes theorem")
        self.assertEqual(topics[-1]["title"], "Bayes' Theorem")

    def test_duplicate_title_is_disambiguated(self):
        topics = [_intro(), _t("Permutations"), _t("Combinations"), _t("Permutations")]
        _disambiguate_topic_titles(topics, "permutations and combinations")
        self.assertEqual(topics[1]["title"], "Permutations")          # first stays
        self.assertEqual(topics[3]["title"], "More on Permutations")  # second disambiguated

    def test_non_synthesis_role_named_like_path_not_verb_prefixed(self):
        # A teaching (not application) topic that happens to be titled the subject is NOT turned into "Applying"
        # (that verb would be wrong); only synthesis/application/practice/review roles get the verb rename.
        topics = [_intro(), _t("Graphs"), _t("Trees"),
                  _t("Combinatorial Analysis", role="math_formula_method", ttype="math_formula_method")]
        _disambiguate_topic_titles(topics, "combinatorial analysis")
        self.assertEqual(topics[-1]["title"], "Combinatorial Analysis")   # no synthesis verb → left as-is


if __name__ == "__main__":
    unittest.main()
