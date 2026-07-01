"""CP4 — the declared TeachingValidationContract makes the hard/soft prose boundary explicit: contradictions
of the verified trace BLOCK; imperfect-but-correct wording is advisory. Covers the four boundary cases from
SPEC_IMPLEMENTATION_CHECKPOINTS CP4."""
import unittest

from app.services.examples.trace_contract import (DEFAULT_TEACHING_VALIDATION, ProseViolation,
                                                  TeachingValidationContract, hard_prose_violations)


def _v(code: str, severity: str = "hard") -> ProseViolation:
    return ProseViolation(code, "detail", 0, "s1", severity=severity)


class DefaultContractBoundary(unittest.TestCase):
    def test_wrong_edge_or_decision_blocks(self):
        # "Kruskal accepts edge AB" when the trace rejects AB -> decision_contradiction (HARD)
        # "Stack contains C,B" when the trace says B,C        -> value_not_allowed      (HARD)
        for code in ("decision_contradiction", "value_not_allowed", "wrong_selected",
                     "wrong_final_answer", "invented_transition", "missing_terminal", "forbidden_claim"):
            self.assertTrue(DEFAULT_TEACHING_VALIDATION.is_hard(_v(code)), code)

    def test_bland_but_correct_is_advisory(self):
        # bland/paraphrased-but-correct reasoning -> passes with a warning, never blocks
        for code in ("missing_fact", "bland", "repetitive", "value_in_harmless_context"):
            self.assertFalse(DEFAULT_TEACHING_VALIDATION.is_hard(_v(code, "missing")), code)

    def test_hard_prose_violations_returns_only_blocking(self):
        vs = [_v("decision_contradiction"), _v("missing_fact", "missing"), _v("value_not_allowed")]
        self.assertEqual({v.code for v in hard_prose_violations(vs)},
                         {"decision_contradiction", "value_not_allowed"})

    def test_unknown_code_falls_back_to_severity(self):
        self.assertTrue(DEFAULT_TEACHING_VALIDATION.is_hard(_v("adapter_specific_claim", "hard")))
        self.assertFalse(DEFAULT_TEACHING_VALIDATION.is_hard(_v("adapter_specific_claim", "soft")))


class CustomContract(unittest.TestCase):
    def test_stricter_contract_can_promote_missing_fact(self):
        strict = TeachingValidationContract(hard_codes=frozenset({"missing_fact"}))
        self.assertEqual(len(hard_prose_violations([_v("missing_fact", "missing")], strict)), 1)

    def test_partition_splits_hard_and_soft(self):
        hard, soft = DEFAULT_TEACHING_VALIDATION.partition([_v("value_not_allowed"), _v("bland", "soft")])
        self.assertEqual([v.code for v in hard], ["value_not_allowed"])
        self.assertEqual([v.code for v in soft], ["bland"])


if __name__ == "__main__":
    unittest.main()
