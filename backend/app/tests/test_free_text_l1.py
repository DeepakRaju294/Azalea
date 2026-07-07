"""L1 scope adherence (FREE_TEXT_CONTENT_VALIDATION_SPEC.md §3 / §7).

Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_free_text_l1
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.free_text import l1_scope as l1


def _vocab(**over):
    base = dict(
        assumed_prerequisite_terms=frozenset({"force", "equation"}),
        introduced_terms=(l1.IntroducedTerm("net_force", "net force", "concept_net_force_intro"),),
        term_aliases={"forces": "force", "net-force": "net force"},
        technical_terms=frozenset({"force", "net force", "hamiltonian", "eigenvalue"}),
    )
    base.update(over)
    return l1.TopicVocabulary(**base)


class L1(unittest.TestCase):
    def test_l1_rejects_out_of_scope_term(self):
        r = l1.check_scope("The Hamiltonian governs the system's evolution.", _vocab())
        self.assertEqual(r.status, l1.FAIL)
        self.assertIn("hamiltonian", r.out_of_scope_terms)

    def test_l1_does_not_reject_nontechnical_prose(self):
        r = l1.check_scope("This idea shows up all the time and is genuinely useful.", _vocab())
        self.assertEqual(r.status, l1.PASS)

    def test_l1_allows_prerequisite_and_taught_terms(self):
        r = l1.check_scope("The net force is the sum of every force acting on the object.", _vocab())
        self.assertEqual(r.status, l1.PASS)

    def test_l1_normalizes_aliases_before_lookup(self):
        # "forces" → force (a prerequisite) — must not be flagged
        r = l1.check_scope("Several forces act at once.", _vocab())
        self.assertEqual(r.status, l1.PASS)

    def test_l1_low_confidence_unknown_goes_to_review_not_hardfail(self):
        r = l1.check_scope("The eigenvalue determines stability.",
                           _vocab(low_confidence_terms=frozenset({"eigenvalue"})))
        self.assertEqual(r.status, l1.REVIEW)
        self.assertIn("eigenvalue", r.review_terms)
        self.assertEqual(r.out_of_scope_terms, ())

    def test_l1_term_allowance_is_by_stable_id_not_position(self):
        # reordering the introduced_terms tuple must not change what's allowed (matched by id/display, not order)
        v1 = _vocab(introduced_terms=(
            l1.IntroducedTerm("net_force", "net force", "concept_net_force_intro"),
            l1.IntroducedTerm("eigenvalue", "eigenvalue", "eigen_intro"),
        ))
        v2 = _vocab(introduced_terms=tuple(reversed(v1.introduced_terms)))
        text = "The eigenvalue and the net force both appear here."
        self.assertEqual(l1.check_scope(text, v1).status, l1.check_scope(text, v2).status)
        self.assertEqual(l1.check_scope(text, v1).status, l1.PASS)


if __name__ == "__main__":
    unittest.main()
