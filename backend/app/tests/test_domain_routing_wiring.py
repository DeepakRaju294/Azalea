"""Phase-0 domain-routing WIRING acceptance fixtures (DOMAIN_ROUTING_AND_TOPIC_GATE_SPEC §5/§7).

The gate's pure logic is covered by test_domain_gate.py. This file locks the topic_generator *orchestration*:
the flag-gated shadow/enforce split, the coding-transform predicate (D-c), and the telemetry sink — the
launch-gate invariants that must hold before AZALEA_DOMAIN_ROUTING_GATE is flipped on in prod.

Run: python -m unittest app.tests.test_domain_routing_wiring
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")
# Never touch a real telemetry log during tests.
os.environ["AZALEA_DOMAIN_GATE_TELEMETRY_PATH"] = os.devnull

import app.services.topic_generator as tg


def _types(topics):
    return [t.get("course_type") for t in topics]


def _math_path():
    return [
        {"title": "Introduction to Completing the Square", "course_type": "study_path_introduction"},
        {"title": "Understanding the Process of Completing the Square", "course_type": "process_walkthrough"},
        {"title": "Implementing Completing Square Worked Examples", "course_type": "coding_implementation"},
    ]


class ShadowMode(unittest.TestCase):
    """Flag off ⇒ the emitted topics are byte-for-byte unchanged (telemetry still recorded)."""

    def setUp(self):
        os.environ.pop("AZALEA_DOMAIN_ROUTING_GATE", None)

    def test_math_path_unchanged_in_shadow(self):
        out = tg._apply_domain_gate([dict(t) for t in _math_path()], "math")
        self.assertEqual(_types(out), ["study_path_introduction", "process_walkthrough", "coding_implementation"])

    def test_shadow_does_not_mutate_input_dicts(self):
        topics = [dict(t) for t in _math_path()]
        tg._apply_domain_gate(topics, "math")
        # the gate ran on a deep copy — no rewrite audit fields leaked onto the originals
        self.assertTrue(all("rewrite_version" not in t for t in topics))

    def test_coding_transforms_run_in_shadow(self):
        # shadow must preserve legacy behavior for EVERY domain, including non-coding ones
        for d in ("math", "physics", "economics", "coding", None):
            self.assertTrue(tg._coding_transforms_enabled(d), d)

    def test_no_domain_is_noop(self):
        topics = [dict(t) for t in _math_path()]
        self.assertEqual(tg._apply_domain_gate(topics, None), topics)


class EnforcedMode(unittest.TestCase):
    """Flag on ⇒ the gate rewrites/drops, and coding-family backfills are skipped for non-coding paths."""

    def setUp(self):
        os.environ["AZALEA_DOMAIN_ROUTING_GATE"] = "1"

    def tearDown(self):
        os.environ.pop("AZALEA_DOMAIN_ROUTING_GATE", None)

    def test_math_path_remapped_and_coding_twin_dropped(self):
        out = tg._apply_domain_gate([dict(t) for t in _math_path()], "math")
        types = _types(out)
        self.assertNotIn("coding_implementation", types)
        self.assertNotIn("process_walkthrough", types)
        self.assertIn("math_formula_method", types)

    def test_coding_path_is_noop(self):
        path = [{"title": "DFS Walkthrough", "course_type": "algorithm_walkthrough"},
                {"title": "Implementing DFS", "course_type": "coding_implementation"}]
        self.assertEqual(_types(tg._apply_domain_gate(path, "coding")),
                         ["algorithm_walkthrough", "coding_implementation"])

    def test_coding_transforms_gated_by_family(self):
        self.assertFalse(tg._coding_transforms_enabled("math"))       # enforced + non-coding ⇒ skip backfills
        self.assertFalse(tg._coding_transforms_enabled("physics"))
        self.assertTrue(tg._coding_transforms_enabled("coding"))      # coding path ⇒ backfills still run
        self.assertTrue(tg._coding_transforms_enabled("mixed"))       # non-gating families keep legacy behavior
        self.assertTrue(tg._coding_transforms_enabled(None))

    def test_mixed_and_unknown_are_noops_even_when_enforced(self):
        for d in ("mixed", "unknown"):
            out = tg._apply_domain_gate([dict(t) for t in _math_path()], d)
            self.assertEqual(_types(out),
                             ["study_path_introduction", "process_walkthrough", "coding_implementation"], d)


class FlagParsing(unittest.TestCase):
    def test_flag_off_values(self):
        for v in ("", "0"):
            os.environ["AZALEA_DOMAIN_ROUTING_GATE"] = v
            self.assertFalse(tg._gate_enforced(), repr(v))
        os.environ.pop("AZALEA_DOMAIN_ROUTING_GATE", None)
        self.assertFalse(tg._gate_enforced())

    def test_flag_on_values(self):
        for v in ("1", "true", "on", "shadow_off"):
            os.environ["AZALEA_DOMAIN_ROUTING_GATE"] = v
            self.assertTrue(tg._gate_enforced(), repr(v))
        os.environ.pop("AZALEA_DOMAIN_ROUTING_GATE", None)


if __name__ == "__main__":
    unittest.main()
