"""The legacy validator's normalize_link must preserve canonical link identity (concept_id) and must not
destroy navigation links for lacking an explanation — both bugs silently degraded links during future-card
regeneration (the only pipeline still using this validator)."""
import unittest

from app.services.interactive_link_validation import normalize_link


class NormalizeLink(unittest.TestCase):
    def test_concept_id_survives(self):
        out = normalize_link({"text": "conditional probability", "explanation": "", "action": "open_study_path",
                              "target": "Understand the basics.", "concept_id": "conditional_probability"})
        self.assertIsNotNone(out)
        self.assertEqual(out["concept_id"], "conditional_probability")

    def test_nav_links_allowed_without_explanation(self):
        for action in ("open_study_path", "review_earlier_topic"):
            out = normalize_link({"text": "x", "explanation": "", "action": action, "target": "t"})
            self.assertIsNotNone(out, action)

    def test_popup_still_requires_explanation(self):
        self.assertIsNone(normalize_link({"text": "x", "explanation": "", "action": "popup_only"}))
        self.assertIsNotNone(normalize_link({"text": "x", "explanation": "a gloss", "action": "popup_only"}))

    def test_unknown_action_defaults_to_popup_and_needs_explanation(self):
        self.assertIsNone(normalize_link({"text": "x", "explanation": "", "action": "bogus"}))


if __name__ == "__main__":
    unittest.main()
