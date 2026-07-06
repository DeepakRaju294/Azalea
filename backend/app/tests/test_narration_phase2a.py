"""Phase-2A narration structured core (DOMAIN_CARD_NARRATION_AND_RENDERING_SPEC §2/§3/§4/§9.1).

Covers the pure, decision-light artifacts: the card-contract matrix + eligibility gate, the fact-source /
adapter-capability registry, the AZALEA_DOMAIN_NARRATION_V2 rollout ladder, and the per-domain narration
contracts. The renderer spike + invasive blueprint/trace wiring are Phase-2B and not exercised here.

Run: python -m unittest app.tests.test_narration_phase2a
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.narration import contracts, fact_source, matrix, rollout


class Matrix(unittest.TestCase):
    def test_domain_normalization(self):
        self.assertEqual(matrix.narration_domain_of("physics"), "science")
        self.assertEqual(matrix.narration_domain_of("finance"), "concept")   # expository → concept
        self.assertEqual(matrix.narration_domain_of("concept"), "concept")
        self.assertEqual(matrix.narration_domain_of("coding"), "coding")
        self.assertIsNone(matrix.narration_domain_of("mixed"))

    def test_status_lookup(self):
        self.assertEqual(matrix.card_status("process", "math"), matrix.DEFINED)
        self.assertEqual(matrix.card_status("formula_breakdown", "math"), matrix.DEFERRED)
        self.assertEqual(matrix.card_status("formula_breakdown", "coding"), matrix.NOT_APPLICABLE)
        self.assertEqual(matrix.card_status("complexity_analysis", "science"), matrix.NOT_APPLICABLE)
        self.assertEqual(matrix.card_status("code_walkthrough", "coding"), matrix.DEFERRED)

    def test_gate_defined_requires_contract_and_sources(self):
        ready = matrix.evaluate_card("process", "math", blueprint_optional=False,
                                     contract_registered=True, fact_sources_ready=True)
        self.assertEqual(ready.action, matrix.PROCEED)
        missing = matrix.evaluate_card("process", "math", blueprint_optional=False)
        self.assertEqual(missing.action, matrix.WITHHOLD)
        self.assertEqual(missing.reason, "contract_or_fact_source_missing")

    def test_gate_not_applicable_is_safety_failure(self):
        d = matrix.evaluate_card("complexity_analysis", "math", blueprint_optional=False)
        self.assertEqual(d.action, matrix.SAFETY_FAILURE)
        self.assertEqual(d.reason, "not_applicable_card")

    def test_gate_deferred_optional_prunes_required_withholds(self):
        opt = matrix.evaluate_card("formula_breakdown", "math", blueprint_optional=True)
        self.assertEqual(opt.action, matrix.PRUNE)
        self.assertEqual(opt.reason, "deferred_card_pruned")
        req = matrix.evaluate_card("formula_breakdown", "math", blueprint_optional=False)
        self.assertEqual(req.action, matrix.WITHHOLD)
        self.assertEqual(req.reason, "deferred_required_blocks_rollout")

    def test_gate_unmapped_fails_closed(self):
        self.assertEqual(matrix.evaluate_card("mystery", "math", blueprint_optional=True).action, matrix.WITHHOLD)
        self.assertEqual(matrix.evaluate_card("process", "mixed", blueprint_optional=True).action, matrix.WITHHOLD)

    def test_first_math_slice_is_blocked_until_formula_breakdown_defined(self):
        # completing-the-square cannot enter on_enforced while required formula_breakdown (math) is deferred
        self.assertEqual(matrix.card_status("formula_breakdown", "math"), matrix.DEFERRED)
        d = matrix.evaluate_card("formula_breakdown", "math", blueprint_optional=False)
        self.assertEqual(d.action, matrix.WITHHOLD)

    def test_matrix_covers_live_blueprint_inventory(self):
        # §9 DoD: every card type the blueprints emit must appear in the matrix (no card silently omitted).
        import app.core.course_blueprints as cb
        seen: set[str] = set()
        for name in ("EXAMPLE_CARD_RULES", "VISUAL_CARD_RULES", "TOPIC_BLUEPRINTS"):
            table = getattr(cb, name, None)
            if not isinstance(table, dict):
                continue
            for rules in table.values():
                if isinstance(rules, dict):
                    seen |= {k for k, v in rules.items() if isinstance(v, dict)}
        self.assertEqual(seen - set(matrix.CARD_CONTRACT_MATRIX), set(),
                         "blueprint card types missing from the §2 matrix")


class FactSourceRegistry(unittest.TestCase):
    def test_seed_entries_present(self):
        fs = fact_source.get_fact_source("worked_example", "result", "math")
        self.assertIsNotNone(fs)
        self.assertEqual(fs.mode, fact_source.DIRECT)
        self.assertEqual(fs.direct_source, "trace.step.result_expression")

    def test_required_sources_respect_when_quantitative(self):
        base = fact_source.required_sources_for("worked_example", "science", quantitative=False)
        self.assertNotIn("result_units", [f.field for f in base])
        quant = fact_source.required_sources_for("worked_example", "science", quantitative=True)
        self.assertIn("result_units", [f.field for f in quant])

    def test_interpretation_is_derived_not_free(self):
        fs = fact_source.get_fact_source("worked_example", "interpretation", "science")
        self.assertEqual(fs.mode, fact_source.DERIVED)
        self.assertIsNotNone(fs.derived)
        self.assertEqual(fs.derived.template_id, "science_quantity_interpretation_v1")

    def test_unregistered_adapter_fails_closed(self):
        fs = fact_source.get_fact_source("worked_example", "result", "math")
        self.assertFalse(fact_source.adapter_can_supply("no_such_adapter", fs))

    def test_registered_adapter_capability(self):
        fact_source.register_adapter_capability(fact_source.AdapterCapability(
            adapter_slug="quadratic_v1", supported_domains=("math",),
            supports_verified_worked_example=True, supports_rule_identifier=True))
        fs = fact_source.get_fact_source("worked_example", "result", "math")
        self.assertTrue(fact_source.adapter_can_supply("quadratic_v1", fs))
        reasoning = fact_source.get_fact_source("worked_example", "reasoning", "math")
        self.assertTrue(fact_source.adapter_can_supply("quadratic_v1", reasoning))


class Rollout(unittest.TestCase):
    def setUp(self):
        os.environ.pop(rollout._ENV_FLAG, None)
        rollout._FAMILY_MODES.clear()

    def tearDown(self):
        os.environ.pop(rollout._ENV_FLAG, None)
        rollout._FAMILY_MODES.clear()

    def test_default_is_off_legacy(self):
        self.assertEqual(rollout.resolve_mode("math", "process"), rollout.OFF_LEGACY)

    def test_env_flag_sets_global_default(self):
        os.environ[rollout._ENV_FLAG] = "shadow_validate"
        self.assertEqual(rollout.resolve_mode("math", "process"), rollout.SHADOW_VALIDATE)
        os.environ[rollout._ENV_FLAG] = "garbage"
        self.assertEqual(rollout.resolve_mode("math", "process"), rollout.OFF_LEGACY)

    def test_family_override_is_most_specific(self):
        rollout.set_family_mode("math", "process", rollout.SHADOW_VALIDATE)
        rollout.set_family_mode("math", "process", rollout.ON_ENFORCED, optional_topic_type="math_formula_method")
        self.assertEqual(rollout.resolve_mode("math", "process"), rollout.SHADOW_VALIDATE)
        self.assertEqual(
            rollout.resolve_mode("math", "process", "math_formula_method"), rollout.ON_ENFORCED)

    def test_cannot_roll_back_to_off_legacy(self):
        rollout.set_family_mode("math", "process", rollout.ON_ENFORCED)
        with self.assertRaises(ValueError):
            rollout.set_family_mode("math", "process", rollout.OFF_LEGACY)

    def test_rollback_target_never_off_legacy(self):
        self.assertEqual(rollout.rollback_target(rollout.ON_ENFORCED), rollout.SHADOW_VALIDATE)
        self.assertEqual(rollout.rollback_target(rollout.SHADOW_VALIDATE), rollout.SHADOW_VALIDATE)


class Contracts(unittest.TestCase):
    def test_math_process_has_no_loop_scaffold(self):
        c = contracts.narration_contract_for("math")
        self.assertEqual(c.process_scaffold, ("Setup", "Operation", "Result", "Why"))
        self.assertNotIn("Loop / repeated action", c.process_scaffold)

    def test_science_result_includes_units_and_interpretation(self):
        c = contracts.narration_contract_for("physics")
        self.assertIn("units", c.worked_example_fields["result"])
        self.assertIn("interpretation", c.worked_example_fields["result"])

    def test_concept_scaffold(self):
        c = contracts.narration_contract_for("finance")            # expository → concept
        self.assertEqual(c.domain, "concept")
        self.assertEqual(c.process_scaffold, ("Idea", "Structure", "Example"))

    def test_non_gating_domain_has_no_contract(self):
        self.assertIsNone(contracts.narration_contract_for("mixed"))

    def test_cross_cutting_rules_present(self):
        c = contracts.narration_contract_for("coding")
        self.assertEqual(c.step_title_rule, "action_not_rule_name")
        self.assertEqual(c.result_line_rule, "terminal_not_narrated")


if __name__ == "__main__":
    unittest.main()
