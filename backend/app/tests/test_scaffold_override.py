"""Phase-3 card-level scaffold overrides / mixed-domain (DOMAIN_CARD_NARRATION_AND_RENDERING_SPEC §5).

The mechanism ships DISABLED (empty allow-list). These lock the bounded-override rules: whitelisted-only,
deterministic-source-only, safety-preserving, and identity by default.

Run: python -m unittest app.tests.test_scaffold_override
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.narration import scaffold_override as so


class ScaffoldOverride(unittest.TestCase):
    def tearDown(self):
        so.clear_override_allowlist()

    def test_default_is_identity_no_override(self):
        r = so.resolve_scaffold("worked_example", "math")
        self.assertFalse(r.overridden)
        self.assertEqual(r.scaffold_domain, "math")
        self.assertEqual(r.reason, "no_override")

    def test_v1_allowlist_empty_rejects_override(self):
        # even a well-formed deterministic override is rejected while the card type isn't whitelisted
        r = so.resolve_scaffold("worked_example", "math",
                                requested_scaffold_domain="coding", source="adapter_flag:merge_sort")
        self.assertFalse(r.overridden)
        self.assertEqual(r.reason, "card_type_not_whitelisted")

    def test_whitelisted_deterministic_override_applies(self):
        so.register_override_allowed("worked_example")
        r = so.resolve_scaffold("worked_example", "math",
                                requested_scaffold_domain="coding", source="adapter_flag:merge_sort")
        self.assertTrue(r.overridden)
        self.assertEqual(r.scaffold_domain, "coding")

    def test_non_deterministic_source_rejected(self):
        so.register_override_allowed("worked_example")
        r = so.resolve_scaffold("worked_example", "math",
                                requested_scaffold_domain="coding", source="llm")
        self.assertFalse(r.overridden)
        self.assertEqual(r.reason, "non_deterministic_source")

    def test_override_may_not_bypass_card_safety(self):
        # complexity_analysis is not_applicable on math → cannot borrow a math scaffold even if whitelisted
        so.register_override_allowed("complexity_analysis")
        r = so.resolve_scaffold("complexity_analysis", "coding",
                                requested_scaffold_domain="math", source="metadata:mixed")
        self.assertFalse(r.overridden)
        self.assertEqual(r.reason, "would_bypass_card_safety")

    def test_same_domain_request_is_identity(self):
        so.register_override_allowed("worked_example")
        r = so.resolve_scaffold("worked_example", "physics",
                                requested_scaffold_domain="science", source="metadata:x")
        self.assertFalse(r.overridden)          # physics and science normalize to the same narration domain
        self.assertEqual(r.reason, "no_override")


if __name__ == "__main__":
    unittest.main()
