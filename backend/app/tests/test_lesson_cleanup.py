"""Two deterministic lesson-cleanup passes: collapse duplicate edge_case cards into one, and strip intro
key-terms that a single later topic owns (so the intro previews only SHARED terms)."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.lean_lesson_generator import (
    _dedupe_intro_key_terms_against_scope, _expand_math_point, _formula_variable_letters, _is_inline_formula_point,
    _is_prose_symbol_breakdown, _key_term_header, _lean_card_to_legacy, _merge_duplicate_edge_cases,
    _reconcile_formula_notation_conflict, _split_embedded_newline_points, _strip_formula_breakdown_from_purpose,
    _strip_generic_intro_key_terms, _strip_prerequisite_key_terms, _strip_sibling_topic_key_terms,
    _strip_taught_topics_from_prereq_card,
)


class GroundedEdgeCardCrossTopicDedup(unittest.TestCase):
    def test_same_adapter_siblings_keep_one_grounded_edge_card(self):
        # Live: 3 topics on one Gaussian path all routed to gaussian_elimination -> 3 identical grounded
        # Edge Cases cards. The FIRST keeps the grounded card; later same-adapter topics drop theirs.
        from app.services.lean_lesson_generator import _ground_edge_case_card

        class _SP:  # noqa: N801 — minimal duck-typed path
            pass

        class _T2:  # noqa: N801
            def __init__(self, title, order):
                self.title, self.order_index = title, order
                self.course_type, self.topic_type, self.study_path = "math_formula_method", None, None

        sp = _SP()
        first, later = _T2("Row Echelon Form", 2), _T2("Gaussian Elimination", 4)
        sp.topics = [first, later]
        first.study_path = later.study_path = sp

        def edge_cards():
            return [{"blueprint_key": "edge_case", "card_type": "edge_case",
                     "title": "Edge Case: X", "points": ["wrong llm claim"]}]

        c1 = edge_cards()
        self.assertTrue(_ground_edge_case_card(c1, first))
        self.assertEqual(len(c1), 1)                       # grounded card kept, 3 correct facts
        self.assertEqual(len(c1[0]["points"]), 3)
        c2 = edge_cards()
        self.assertTrue(_ground_edge_case_card(c2, later))
        self.assertEqual(c2, [])                           # duplicate grounded card dropped entirely


class MixedDelimiterAndInlineSymbol(unittest.TestCase):
    def test_dollar_wrapped_equation_repaired_before_split_no_orphan_dollars(self):
        # Live bug: "$\(z = \frac{x-\mu}{\sigma}$)" was split into its own bullet BEFORE the delimiter repair,
        # leaving an orphaned "$ $". Repair must run first so the equation extracts cleanly.
        card = {"card_type": "purpose_context", "blueprint_key": "purpose_context", "title": "Z",
                "points": [r"Uses the formula $\(z = \frac{x - \mu}{\sigma}\)$:"]}
        out = _lean_card_to_legacy(card, 0, [], topic_hint="z-score")
        joined = " ".join(out.get("points") or [])
        self.assertNotIn("$", joined)                       # no orphaned dollar signs
        self.assertIn(r"\(z = \frac{x - \mu}{\sigma}\)", joined)

    def test_bare_inline_symbol_stays_inline(self):
        # A single inline symbol \(\mu\) is NOT an equation — moving it to a subpoint strands "Mean ( )".
        self.assertIsNone(_expand_math_point(r"Mean (\(\mu\)) is the average of the values"))

    def test_bold_wrapped_bare_symbol_stays_inline(self):
        # live: "\(\mathbf{F}\)" is 14 chars — long enough to slip past a pure character-count floor — but it's
        # still just a variable name, not an equation. Splitting it out stranded "ensuring that is continuously
        # differentiable" with no subject, because the "F" it needed got severed into its own orphaned bullet.
        self.assertIsNone(_expand_math_point(
            r"Conditions for valid use include ensuring that \(\mathbf{F}\) is continuously differentiable"))
        self.assertIsNone(_expand_math_point(r"The vector field is \(\mathbf{F}\) here"))

    def test_real_equation_still_splits(self):
        out = _expand_math_point(r"The z-score uses \(z = \frac{x-\mu}{\sigma}\) to standardize")
        self.assertIsNotNone(out)
        self.assertTrue(out[1].strip().startswith("-"))     # equation moved to a subpoint


class _Topic:
    def __init__(self, tid, title, order, in_scope=None, ctype="math_formula_method"):
        self.id, self.title, self.order_index = tid, title, order
        self.course_type, self.topic_type = ctype, None
        self.in_scope = in_scope or []
        self.assumed_prerequisites = []
        self.decomposition_metadata = {}
        self.study_path = None


class _Path:
    def __init__(self, topics):
        self.topics = topics
        for t in topics:
            t.study_path = self


class MergeDuplicateEdgeCases(unittest.TestCase):
    def test_two_edge_cards_merge_into_one(self):
        cards = [
            {"card_type": "formula", "points": ["f"]},
            {"card_type": "edge_case", "points": ["P(B)=0 is undefined"]},
            {"card_type": "edge_case", "points": ["likelihood 0 case", "P(B)=0 is undefined"]},
        ]
        out = _merge_duplicate_edge_cases(cards)
        edge = [c for c in out if c["card_type"] == "edge_case"]
        self.assertEqual(len(edge), 1)
        self.assertEqual(edge[0]["points"], ["P(B)=0 is undefined", "likelihood 0 case"])  # union, deduped, ordered

    def test_single_edge_card_is_noop(self):
        cards = [{"card_type": "edge_case", "points": ["a"]}]
        self.assertEqual(_merge_duplicate_edge_cases(cards), cards)

    def test_no_edge_cards_is_noop(self):
        cards = [{"card_type": "formula", "points": ["f"]}]
        self.assertEqual(_merge_duplicate_edge_cases(cards), cards)


class DedupeIntroKeyTermsAgainstScope(unittest.TestCase):
    def _intro_and_path(self, kt_points):
        intro = _Topic("i", "Intro", 0, ctype="study_path_introduction")
        bayes = _Topic("t2", "Bayes' Theorem", 2,
                       in_scope=["prior probability", "posterior probability", "likelihood"])
        ltp = _Topic("t1", "Law of Total Probability", 1, in_scope=["total probability"])
        _Path([intro, ltp, bayes])
        cards = [
            {"card_type": "background", "points": ["overview"]},
            {"card_type": "definition", "title": "Key Terms", "points": kt_points},
        ]
        return intro, cards

    def test_topic_owned_terms_removed_shared_kept(self):
        intro, cards = self._intro_and_path([
            "Prior Probability", "  - the initial estimate",
            "Sample Space", "  - the set of all outcomes",     # not owned by any topic → kept
            "Posterior Probability", "  - the updated estimate",
        ])
        out = _dedupe_intro_key_terms_against_scope(cards, intro)
        kt = next(c for c in out if c["card_type"] == "definition")["points"]
        self.assertIn("Sample Space", kt)
        self.assertNotIn("Prior Probability", kt)
        self.assertNotIn("Posterior Probability", kt)
        self.assertNotIn("  - the initial estimate", kt)      # the owned term's definition line goes too

    def test_card_dropped_when_all_terms_owned(self):
        intro, cards = self._intro_and_path([
            "Prior Probability", "  - x", "Likelihood", "  - y"])
        out = _dedupe_intro_key_terms_against_scope(cards, intro)
        self.assertFalse(any(c["card_type"] == "definition" for c in out))   # emptied card removed

    def test_noop_off_intro(self):
        body = _Topic("t2", "Bayes' Theorem", 2, in_scope=["prior probability"])
        _Path([body])
        cards = [{"card_type": "definition", "points": ["Prior Probability", "  - x"]}]
        self.assertEqual(_dedupe_intro_key_terms_against_scope(cards, body)[0]["points"],
                         ["Prior Probability", "  - x"])

    def test_noop_when_siblings_have_no_scope(self):
        intro = _Topic("i", "Intro", 0, ctype="study_path_introduction")
        _Path([intro, _Topic("t1", "Bayes", 1, in_scope=[])])
        cards = [{"card_type": "definition", "points": ["Prior Probability", "  - x"]}]
        self.assertEqual(_dedupe_intro_key_terms_against_scope(cards, intro)[0]["points"],
                         ["Prior Probability", "  - x"])

    def test_removes_intro_key_term_matching_a_topic_title_even_without_in_scope(self):
        # Regression (round 5): decomposition left in_scope EMPTY, so the intro key-terms card re-previewed
        # 'Bayes' Theorem' — which the Bayes topic teaches. Title match must catch it with no in_scope at all.
        intro = _Topic("i", "Intro", 0, ctype="study_path_introduction")
        bayes = _Topic("t2", "Bayes' Theorem", 2, in_scope=[])
        ltp = _Topic("t1", "Law of Total Probability", 1, in_scope=[])
        _Path([intro, ltp, bayes])
        cards = [{"card_type": "definition", "points": [
            "Bayes' Theorem", "  - a formula", "Sample Space", "  - all outcomes"]}]
        out = _dedupe_intro_key_terms_against_scope(cards, intro)
        kt = out[0]["points"]
        self.assertNotIn("Bayes' Theorem", kt)      # matches topic title → removed
        self.assertIn("Sample Space", kt)           # not a topic → stays

    def test_fuzzy_match_against_combined_in_scope_phrase(self):
        # Real regression: the topic listed 'prior and posterior probabilities' as ONE in_scope phrase, so an
        # exact match missed the separate 'Prior Probability' / 'Posterior Probability' intro key terms.
        intro = _Topic("i", "Intro", 0, ctype="study_path_introduction")
        bayes = _Topic("t1", "Bayes", 1, in_scope=["prior and posterior probabilities"])
        _Path([intro, bayes])
        cards = [{"card_type": "definition", "points": [
            "Prior Probability", "  - a", "Posterior Probability", "  - b", "Sample Space", "  - c"]}]
        out = _dedupe_intro_key_terms_against_scope(cards, intro)
        kt = out[0]["points"]
        self.assertNotIn("Prior Probability", kt)
        self.assertNotIn("Posterior Probability", kt)
        self.assertIn("Sample Space", kt)          # not owned → stays


class SplitEmbeddedNewlines(unittest.TestCase):
    def test_splits_header_and_subbullet_packed_in_one_point(self):
        cards = [{"card_type": "definition", "points": [
            "Conditional Probability \n  - the probability of E given A", "Partition \n  - a disjoint cover"]}]
        out = _split_embedded_newline_points(cards)
        self.assertEqual(out[0]["points"], [
            "Conditional Probability ", "  - the probability of E given A",
            "Partition ", "  - a disjoint cover"])

    def test_leaves_clean_points_untouched_and_drops_empty_fragments(self):
        cards = [{"card_type": "formula", "points": ["$$P(A)$$", "line1\n\nline2"]}]
        out = _split_embedded_newline_points(cards)
        self.assertEqual(out[0]["points"], ["$$P(A)$$", "line1", "line2"])   # blank fragment dropped


class StripPrerequisiteKeyTerms(unittest.TestCase):
    def test_key_term_header_handles_all_separators(self):
        self.assertEqual(_key_term_header("Conditional Probability - the prob..."), "Conditional Probability")
        self.assertEqual(_key_term_header("P(A|B): posterior"), "P(A|B)")
        self.assertEqual(_key_term_header("Disjoint Events"), "Disjoint Events")

    def test_drops_prereq_term_keeps_topic_terms(self):
        # LTP topic re-defining 'conditional probability' (a declared intro prerequisite) inline with a dash.
        intro = _Topic("i", "Intro", 0, ctype="study_path_introduction")
        intro.assumed_prerequisites = ["basic probability", "conditional probability"]
        ltp = _Topic("t1", "Law of Total Probability", 1)
        _Path([intro, ltp])
        cards = [{"card_type": "definition", "points": [
            "Marginal Probability - the probability of an event irrespective of others.",
            "Conditional Probability - the probability of an event given another has occurred.",
            "Disjoint Events - events that cannot occur simultaneously."]}]
        out = _strip_prerequisite_key_terms(cards, ltp)
        pts = out[0]["points"]
        self.assertTrue(any("Marginal Probability" in p for p in pts))
        self.assertTrue(any("Disjoint Events" in p for p in pts))
        self.assertFalse(any(p.startswith("Conditional Probability") for p in pts))   # prereq dropped

    def test_drops_header_plus_indented_definition(self):
        intro = _Topic("i", "Intro", 0, ctype="study_path_introduction")
        intro.assumed_prerequisites = ["conditional probability"]
        body = _Topic("t1", "Bayes", 1)
        _Path([intro, body])
        cards = [{"card_type": "definition", "points": [
            "Conditional Probability", "  - prob of A given B", "Posterior", "  - updated belief"]}]
        out = _strip_prerequisite_key_terms(cards, body)
        pts = out[0]["points"]
        self.assertEqual(pts, ["Posterior", "  - updated belief"])

    def test_noop_on_intro(self):
        intro = _Topic("i", "Intro", 0, ctype="study_path_introduction")
        intro.assumed_prerequisites = ["conditional probability"]
        _Path([intro])
        cards = [{"card_type": "definition", "points": ["Conditional Probability - x"]}]
        self.assertEqual(_strip_prerequisite_key_terms(cards, intro)[0]["points"],
                         ["Conditional Probability - x"])


class FunctionGeneralFormulaDetectors(unittest.TestCase):
    def test_inline_formula_beyond_probability(self):
        self.assertTrue(_is_inline_formula_point(r"Uses the formula: \(C(n,r) = \frac{n!}{r!(n-r)!}\)"))
        self.assertTrue(_is_inline_formula_point("The formula is given by: P(H|E) = P(E|H)P(H)/P(E)"))
        self.assertFalse(_is_inline_formula_point("Combinations count selections where order is irrelevant."))

    def test_prose_breakdown_beyond_probability(self):
        self.assertTrue(_is_prose_symbol_breakdown("Where C(n,r) is the count and P(n,r) is the arrangements."))
        self.assertFalse(_is_prose_symbol_breakdown("Consider a (specific) case and an (edge) case here."))  # a/an excluded


class StripSiblingTopicKeyTerms(unittest.TestCase):
    def test_permutations_topic_drops_the_combination_key_term(self):
        perms = _Topic("t4", "Permutations", 4)
        combos = _Topic("t3", "Combinations", 3)
        _Path([combos, perms])
        cards = [{"card_type": "definition", "points": [
            "Permutation: An arrangement where order matters.",
            "Factorial (n!): product of positive integers up to n.",
            "Combination: A selection where order does not matter."]}]
        out = _strip_sibling_topic_key_terms(cards, perms)
        pts = out[0]["points"]
        self.assertTrue(any(p.startswith("Permutation") for p in pts))     # own concept stays
        self.assertTrue(any("Factorial" in p for p in pts))
        self.assertFalse(any(p.startswith("Combination:") for p in pts))   # sibling-owned → dropped

    def test_combinations_topic_keeps_its_own_combination_term(self):
        combos = _Topic("t3", "Combinations", 3)
        perms = _Topic("t4", "Permutations", 4)
        _Path([combos, perms])
        cards = [{"card_type": "definition", "points": ["Combination: order does not matter.", "  - detail"]}]
        out = _strip_sibling_topic_key_terms(cards, combos)
        self.assertTrue(any(p.startswith("Combination") for p in out[0]["points"]))   # its own topic → kept


class StripGenericIntroKeyTerms(unittest.TestCase):
    def test_drops_elementary_terms_keeps_substantive_ones(self):
        intro = _Topic("i", "Intro", 0, ctype="study_path_introduction")
        _Path([intro])
        cards = [{"card_type": "definition", "points": [
            "Probability — A measure of the likelihood an event will occur.",
            "Conditional Probability — The probability of an event given another.",
            "Event — A specific outcome from a random process.",
            "Sample Space — The set of all possible outcomes."]}]
        out = _strip_generic_intro_key_terms(cards, intro)
        kt = out[0]["points"]
        self.assertEqual(len(kt), 1)
        self.assertTrue(kt[0].startswith("Sample Space"))     # substantive → stays
        # Probability / Conditional Probability / Event all have an elementary head noun → dropped

    def test_drops_the_whole_card_when_all_elementary(self):
        intro = _Topic("i", "Intro", 0, ctype="study_path_introduction")
        _Path([intro])
        cards = [{"card_type": "background", "points": ["overview"]},
                 {"card_type": "definition", "points": [
                     "Probability", "  - a measure", "Event", "  - an outcome"]}]
        out = _strip_generic_intro_key_terms(cards, intro)
        self.assertFalse(any(c["card_type"] == "definition" for c in out))   # emptied → dropped
        self.assertTrue(any(c["card_type"] == "background" for c in out))

    def test_noop_off_intro(self):
        body = _Topic("t1", "Bayes", 1)
        _Path([body])
        cards = [{"card_type": "definition", "points": ["Probability — a measure"]}]
        self.assertEqual(_strip_generic_intro_key_terms(cards, body)[0]["points"], ["Probability — a measure"])


class StripTaughtTopicsFromPrereqCard(unittest.TestCase):
    def _intro_path(self, prereq_points):
        intro = _Topic("i", "Intro", 0, ctype="study_path_introduction")
        ltp = _Topic("t1", "Law of Total Probability", 1)
        bayes = _Topic("t2", "Bayes' Theorem", 2)
        _Path([intro, ltp, bayes])
        return intro, [{"card_type": "purpose_context", "title": "Foundational Concepts",
                        "points": prereq_points}]

    def test_drops_bullet_naming_a_taught_topic(self):
        intro, cards = self._intro_path([
            "Understanding of basic probability concepts",
            "  - Probability", "  - Conditional probability",
            "Recognition of Bayes' Theorem as a formula connecting conditional probabilities."])
        out = _strip_taught_topics_from_prereq_card(cards, intro)
        pts = out[0]["points"]
        self.assertTrue(any("basic probability" in p for p in pts))       # real prereq stays
        self.assertIn("  - Conditional probability", pts)                 # its sub-bullets stay
        self.assertFalse(any("Bayes" in p for p in pts))                  # taught topic dropped

    def test_keeps_prereq_that_only_mentions_a_topic_as_motivation(self):
        intro, cards = self._intro_path([
            "Conditional probability, which is needed for Bayes' Theorem"])
        out = _strip_taught_topics_from_prereq_card(cards, intro)
        self.assertEqual(len(out[0]["points"]), 1)                        # subject is the prereq, not Bayes → kept

    def test_noop_off_intro(self):
        body = _Topic("t2", "Bayes' Theorem", 2)
        _Path([body])
        cards = [{"card_type": "purpose_context", "title": "Prerequisites",
                  "points": ["Recognition of Bayes' Theorem"]}]
        self.assertEqual(_strip_taught_topics_from_prereq_card(cards, body)[0]["points"],
                         ["Recognition of Bayes' Theorem"])


class FormulaNotationConflict(unittest.TestCase):
    def test_letters_extracted_from_P_of(self):
        self.assertEqual(_formula_variable_letters(r"$$P(A) = \sum_i P(A|B_i)P(B_i)$$"), {"A", "B"})
        self.assertEqual(_formula_variable_letters(r"P(A|B) = P(B|A)P(A)/P(B)"), {"A", "B"})

    def test_drops_key_terms_card_that_introduces_a_foreign_letter(self):
        # Regression: LTP formula uses event A + partitions B_i, but the key-terms card defined event E /
        # partitions A_i — a direct contradiction on adjacent cards.
        cards = [
            {"card_type": "formula", "points": [r"$$P(A) = \sum_i P(A|B_i)P(B_i)$$", "A is the event."]},
            {"card_type": "definition", "points": ["P(A_i): each event", "P(E|A): prob of E given A"]},
            {"card_type": "method_process", "points": ["step"]},
        ]
        out = _reconcile_formula_notation_conflict(cards)
        keys = [c["card_type"] for c in out]
        self.assertNotIn("definition", keys)        # conflicting card dropped (E not in {A, B})
        self.assertIn("formula", keys)
        self.assertIn("method_process", keys)

    def test_keeps_consistent_key_terms_card(self):
        cards = [
            {"card_type": "formula", "points": [r"$$P(A|B) = \frac{P(B|A)P(A)}{P(B)}$$"]},
            {"card_type": "definition", "points": ["P(A): prior", "P(B|A): likelihood", "P(A|B): posterior"]},
        ]
        out = _reconcile_formula_notation_conflict(cards)
        self.assertEqual(len([c for c in out if c["card_type"] == "definition"]), 1)   # only {A,B} → kept

    def test_noop_without_formula(self):
        cards = [{"card_type": "definition", "points": ["P(Z): something"]}]
        self.assertEqual(_reconcile_formula_notation_conflict(cards), cards)


class StripFormulaBreakdownFromPurpose(unittest.TestCase):
    def test_removes_symbol_breakdown_and_scaffold(self):
        # Bayes purpose card duplicated the formula's symbol breakdown before the formula was even shown.
        cards = [
            {"card_type": "purpose_context", "points": [
                "Bayes' Theorem helps calculate the probability given prior knowledge:",
                "  - For events A and B, it calculates:",
                "  - Where:",
                r"    - \( P(A|B) \): posterior probability",
                r"    - \( P(B|A) \): likelihood",
                r"    - \( P(A) \): prior probability",
                "This method updates probability when new information appears."]},
            {"card_type": "formula", "points": [r"$$P(A|B) = \frac{P(B|A)P(A)}{P(B)}$$"]},
        ]
        out = _strip_formula_breakdown_from_purpose(cards)
        pts = out[0]["points"]
        self.assertEqual(pts, [
            "Bayes' Theorem helps calculate the probability given prior knowledge:",
            "This method updates probability when new information appears."])

    def test_removes_dangling_formula_lead_in(self):
        # LTP purpose card ended on "Mathematically defined as where each B ...:" with no formula on that card.
        cards = [
            {"card_type": "purpose_context", "points": [
                "Law of Total Probability",
                "  - Calculates the overall probability across disjoint scenarios",
                "Mathematically defined as where each B represents mutually exclusive conditions:"]},
            {"card_type": "formula", "points": [r"$$P(A) = \sum_i P(A|B_i)P(B_i)$$"]},
        ]
        out = _strip_formula_breakdown_from_purpose(cards)
        self.assertEqual(out[0]["points"], [
            "Law of Total Probability", "  - Calculates the overall probability across disjoint scenarios"])

    def test_removes_inline_formula_and_prose_breakdown(self):
        # Bayes purpose card embedded the equation INLINE (in P(H|E) notation, conflicting with the P(A|B)
        # formula card) plus a prose 'Where P(H|E) is ...' breakdown.
        cards = [
            {"card_type": "purpose_context", "points": [
                "Bayes' Theorem calculates the probability of a hypothesis from evidence:",
                r"  - The formula is given by: \(P(H|E) = \frac{P(E|H) \cdot P(H)}{P(E)}\)",
                "  - Where P(H|E) is the posterior probability, P(E|H) is the likelihood, P(H) is the prior.",
                "This theorem updates beliefs in light of new data."]},
            {"card_type": "formula", "points": [r"$$P(A|B) = \frac{P(B|A)P(A)}{P(B)}$$"]},
        ]
        out = _strip_formula_breakdown_from_purpose(cards)
        self.assertEqual(out[0]["points"], [
            "Bayes' Theorem calculates the probability of a hypothesis from evidence:",
            "This theorem updates beliefs in light of new data."])

    def test_noop_without_formula_card(self):
        cards = [{"card_type": "purpose_context", "points": ["P(A|B): posterior", "motivation:"]}]
        self.assertEqual(_strip_formula_breakdown_from_purpose(cards), cards)

    def test_does_not_empty_a_card(self):
        cards = [
            {"card_type": "purpose_context", "points": ["P(A|B): posterior", "P(A): prior"]},
            {"card_type": "formula", "points": ["$$x$$"]},
        ]
        out = _strip_formula_breakdown_from_purpose(cards)
        self.assertEqual(out[0]["points"], ["P(A|B): posterior", "P(A): prior"])   # left intact, not emptied


if __name__ == "__main__":
    unittest.main()
