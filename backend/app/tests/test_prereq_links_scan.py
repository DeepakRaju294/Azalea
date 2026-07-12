"""Deterministic scan + projection + Tier-1 link validation (PREREQ_LINKS_SPEC v8 §2/§2.2/§2.5a/§5/§6.3b).
Imports ONLY the pure `app.core.prereq_links` package (no routes/services) → no .env landmine.

Covers: A2/A26 (open_study_path deterministic), A5/A10 (review via alias), A28 (token boundary), A33 (markdown
projection), A13 (overlapping longest), A12 (repeated → single anchor), A32 (ordinary earlier topic), A36
(future topic not reviewable), A38 (glossary/nav collision), A8/A21 (cap + priority), A6 (verbatim drop),
A18/A19 (unresolved/ambiguous)."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.core.prereq_links import (
    AssumedPrerequisite, GlossaryIdentity, LinkAction, ScanContext, ScannedLink, ScopeRule,
    TopicConceptIdentity, find_token_matches, project_to_plain_text, scan_card, validate_links,
)


def _ap(concept_id, target_goal="Understand it.", canonical=None, aliases=None):
    return AssumedPrerequisite(concept_id=concept_id, canonical_name=canonical or concept_id,
                              aliases=aliases or [], display_text=concept_id.title(), target_goal=target_goal,
                              scope_rule=ScopeRule.recognition_only_fallback)


def _tci(topic_id, concept_id, index, canonical=None, aliases=None):
    return TopicConceptIdentity(topic_id=topic_id, topic_index=index, concept_id=concept_id,
                               canonical_name=canonical or concept_id, aliases=aliases or [])


def _by_concept(res):
    return {l.concept_id: l for l in res.links}


class Projection(unittest.TestCase):
    def test_bold_stripped_keeps_inner(self):
        self.assertEqual(project_to_plain_text("**Potential difference** is..."), "Potential difference is...")

    def test_inline_code_dropped(self):
        self.assertNotIn("code", project_to_plain_text("run `code` now"))

    def test_math_delimiters_removed(self):
        self.assertEqual(project_to_plain_text(r"\(V = IR\)"), "V = IR")


class TokenBoundaryA28(unittest.TestCase):
    def test_ring_does_not_match_spring(self):
        self.assertEqual(find_token_matches("a spring force", "ring"), [])

    def test_whole_word_matches_with_real_casing(self):
        m = find_token_matches("The Voltage rises", "voltage")
        self.assertEqual([(t[2]) for t in m], ["Voltage"])   # surface keeps real casing


class OpenStudyPathA2A26(unittest.TestCase):
    def test_prerequisite_becomes_open_study_path_deterministically(self):
        # A26: no LLM proposal; the scan alone emits the nav link.
        ctx = ScanContext(current_topic_index=1, assumed_prerequisites=[_ap("voltage", target_goal="Learn voltage.")])
        res = scan_card("Here voltage drives the current.", ctx)
        link = _by_concept(res)["voltage"]
        self.assertEqual(link.action, LinkAction.open_study_path)
        self.assertEqual(link.target, "Learn voltage.")
        self.assertEqual(link.text, "voltage")


class ReviewEarlierA5A10A32(unittest.TestCase):
    def test_alias_resolves_to_review_earlier(self):
        # A10/A5: earlier topic "Voltage"; card says "potential difference".
        ctx = ScanContext(current_topic_index=2,
                          topic_identities=[_tci("t0", "voltage", 0, canonical="Voltage",
                                                 aliases=["potential difference"])])
        res = scan_card("The potential difference drives current.", ctx)
        link = _by_concept(res)["voltage"]
        self.assertEqual(link.action, LinkAction.review_earlier_topic)
        self.assertEqual(link.target, "t0")

    def test_ordinary_core_topic_not_a_foundation_still_reviewable(self):
        # A32: identity emitted for an ordinary earlier topic.
        ctx = ScanContext(current_topic_index=3, topic_identities=[_tci("t1", "kirchhoff_law", 1)])
        res = scan_card("Apply the kirchhoff_law here.", ctx)
        self.assertEqual(_by_concept(res)["kirchhoff_law"].action, LinkAction.review_earlier_topic)


class FutureTopicA36(unittest.TestCase):
    def test_future_topic_not_reviewable(self):
        ctx = ScanContext(current_topic_index=1, topic_identities=[_tci("t5", "capacitance", 5)])  # later topic
        res = scan_card("We will use capacitance soon.", ctx)
        self.assertEqual(res.links, [])   # no backward review link to a not-yet-taught concept


class OverlappingLongestA13(unittest.TestCase):
    def test_longest_phrase_wins(self):
        ctx = ScanContext(current_topic_index=2, topic_identities=[
            _tci("t0", "field", 0, canonical="field"),
            _tci("t1", "electric_field", 1, canonical="electric field"),
        ])
        res = scan_card("The electric field is strong.", ctx)
        self.assertEqual([l.concept_id for l in res.links], ["electric_field"])   # not "field"


class RepeatedTermA12(unittest.TestCase):
    def test_repeated_term_single_anchor(self):
        ctx = ScanContext(current_topic_index=1, assumed_prerequisites=[_ap("voltage")])
        res = scan_card("voltage here and voltage there and voltage again", ctx)
        self.assertEqual(len([l for l in res.links if l.concept_id == "voltage"]), 1)


class GlossaryNavCollisionA38(unittest.TestCase):
    def test_navigation_outranks_glossary(self):
        ctx = ScanContext(
            current_topic_index=2,
            topic_identities=[_tci("t0", "voltage", 0, canonical="Voltage")],
            glossary_identities=[GlossaryIdentity(concept_id="voltage_gloss", canonical_name="voltage")],
        )
        res = scan_card("Recall voltage from before.", ctx)
        link = _by_concept(res).get("voltage")
        self.assertIsNotNone(link)
        self.assertEqual(link.action, LinkAction.review_earlier_topic)   # not downgraded to popup
        self.assertNotIn("voltage_gloss", _by_concept(res))


class AmbiguousA19(unittest.TestCase):
    def test_one_surface_two_concepts_yields_no_link(self):
        ctx = ScanContext(current_topic_index=2, assumed_prerequisites=[
            _ap("emf", canonical="potential difference"),
            _ap("voltage", canonical="potential difference"),
        ])
        res = scan_card("The potential difference matters.", ctx)
        self.assertEqual(res.links, [])
        self.assertTrue(any(d.reason == "ambiguous_navigation_identity" for d in res.dropped))


class UnresolvedA18(unittest.TestCase):
    def test_unknown_term_yields_no_navigation_link(self):
        ctx = ScanContext(current_topic_index=1, assumed_prerequisites=[_ap("voltage")])
        res = scan_card("Something about entropy entirely.", ctx)
        self.assertEqual(res.links, [])


class CapAndPriorityA8A21(unittest.TestCase):
    def test_cap_three_and_priority_order(self):
        # 2 prereq + 2 earlier-topic + 2 glossary candidates on one card → exactly 3, prereq+earlier first.
        ctx = ScanContext(
            current_topic_index=5,
            assumed_prerequisites=[_ap("aa"), _ap("bb")],
            topic_identities=[_tci("t1", "cc", 1), _tci("t2", "dd", 2)],
            glossary_identities=[GlossaryIdentity(concept_id="ee", canonical_name="ee"),
                                 GlossaryIdentity(concept_id="ff", canonical_name="ff")],
        )
        res = scan_card("aa bb cc dd ee ff", ctx)
        self.assertEqual(len(res.links), 3)
        actions = {l.action for l in res.links}
        self.assertNotIn(LinkAction.popup_only, actions)   # glossary popups lose to prereq+earlier


class LinkValidationTier1(unittest.TestCase):
    def test_anchor_not_verbatim_is_dropped_A6(self):
        links = [ScannedLink(text="voltage", action=LinkAction.open_study_path, target="g", concept_id="v")]
        res = validate_links(links, "this card never says the word")
        self.assertEqual(res.links, [])
        self.assertEqual(res.dropped[0].reason, "anchor_not_verbatim")

    def test_open_study_path_missing_target_dropped(self):
        links = [ScannedLink(text="voltage", action=LinkAction.open_study_path, target="", concept_id="v")]
        res = validate_links(links, "voltage here")
        self.assertEqual(res.dropped[0].reason, "missing_target")

    def test_review_missing_concept_id_dropped(self):
        links = [ScannedLink(text="voltage", action=LinkAction.review_earlier_topic, target="t0", concept_id=None)]
        res = validate_links(links, "voltage here")
        self.assertEqual(res.dropped[0].reason, "missing_concept_id")

    def test_cap_enforced(self):
        links = [ScannedLink(text=t, action=LinkAction.popup_only, concept_id=t)
                 for t in ["aa", "bb", "cc", "dd"]]
        res = validate_links(links, "aa bb cc dd")
        self.assertEqual(len(res.links), 3)


if __name__ == "__main__":
    unittest.main()
