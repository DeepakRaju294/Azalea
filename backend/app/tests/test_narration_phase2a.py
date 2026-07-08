"""Phase-2A narration structured core (DOMAIN_CARD_NARRATION_AND_RENDERING_SPEC §2/§3/§4/§9.1).

Covers the pure, decision-light artifacts: the card-contract matrix + eligibility gate, the fact-source /
adapter-capability registry, the AZALEA_DOMAIN_NARRATION_V2 rollout ladder, and the per-domain narration
contracts. The renderer spike + invasive blueprint/trace wiring are Phase-2B and not exercised here.

Run: python -m unittest app.tests.test_narration_phase2a
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.narration import audit, contracts, fact_source, matrix, rollout


class Matrix(unittest.TestCase):
    def test_domain_normalization(self):
        self.assertEqual(matrix.narration_domain_of("physics"), "science")
        self.assertEqual(matrix.narration_domain_of("finance"), "concept")   # expository → concept
        self.assertEqual(matrix.narration_domain_of("concept"), "concept")
        self.assertEqual(matrix.narration_domain_of("coding"), "coding")
        self.assertIsNone(matrix.narration_domain_of("mixed"))

    def test_status_lookup(self):
        self.assertEqual(matrix.card_status("process", "math"), matrix.DEFINED)
        self.assertEqual(matrix.card_status("formula_breakdown", "math"), matrix.DEFINED)   # now defined
        self.assertEqual(matrix.card_status("formula_breakdown", "science"), matrix.DEFERRED)
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
        # comparison is deferred for every domain — use it as the deferred exemplar
        opt = matrix.evaluate_card("comparison", "math", blueprint_optional=True)
        self.assertEqual(opt.action, matrix.PRUNE)
        self.assertEqual(opt.reason, "deferred_card_pruned")
        req = matrix.evaluate_card("comparison", "math", blueprint_optional=False)
        self.assertEqual(req.action, matrix.WITHHOLD)
        self.assertEqual(req.reason, "deferred_required_blocks_rollout")

    def test_gate_unmapped_fails_closed(self):
        self.assertEqual(matrix.evaluate_card("mystery", "math", blueprint_optional=True).action, matrix.WITHHOLD)
        self.assertEqual(matrix.evaluate_card("process", "mixed", blueprint_optional=True).action, matrix.WITHHOLD)

    def test_formula_breakdown_math_now_defined_and_gated_by_sources(self):
        # completing-the-square's required formula_breakdown(math) is now `defined`: it PROCEEDS when its contract
        # + fact-sources are ready, and WITHHOLDS (not deferred) when they are not — never generic fallback.
        self.assertEqual(matrix.card_status("formula_breakdown", "math"), matrix.DEFINED)
        ready = matrix.evaluate_card("formula_breakdown", "math", blueprint_optional=False,
                                     contract_registered=True, fact_sources_ready=True)
        self.assertEqual(ready.action, matrix.PROCEED)
        missing = matrix.evaluate_card("formula_breakdown", "math", blueprint_optional=False)
        self.assertEqual(missing.action, matrix.WITHHOLD)
        self.assertEqual(missing.reason, "contract_or_fact_source_missing")

    def test_formula_breakdown_science_still_deferred(self):
        d = matrix.evaluate_card("formula_breakdown", "science", blueprint_optional=False)
        self.assertEqual(d.action, matrix.WITHHOLD)
        self.assertEqual(d.reason, "deferred_required_blocks_rollout")

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


class NarrationDataAudit(unittest.TestCase):
    def test_formula_engine_supplies_units_and_rule_not_interpretation(self):
        audit.register_audited_capabilities()
        units = fact_source.get_fact_source("worked_example", "result_units", "science")
        interp = fact_source.get_fact_source("worked_example", "interpretation", "science")
        # units + rule identifier ARE supplied (calculation framing is allowed)…
        self.assertTrue(fact_source.adapter_can_supply("t6_formula_engine", units, quantitative=True))
        # …but interpretation is NOT (quantity_kind / final-status gaps) → correctly omitted, never invented
        self.assertFalse(fact_source.adapter_can_supply("t6_formula_engine", interp))

    def test_audit_summary_records_gaps(self):
        s = audit.audit_summary()
        self.assertFalse(s["science_interpretation_available"])
        self.assertIn("trace.step.quantity_kind", s["gaps"])
        self.assertTrue(s["formula_engine_supplies"]["units"])

    def test_derivation_engine_supplies_math_worked_example_and_formula_breakdown(self):
        # T8b (completing-the-square etc.) is the audited provider for the math on_enforced slice: it must supply
        # the REQUIRED math worked_example fields (result, reasoning) and the formula_breakdown rule/form — so the
        # gate's on_enforced capability check no longer fails closed for this family.
        audit.register_audited_capabilities()
        slug = "t8b_derivation_engine"
        we_result = fact_source.get_fact_source("worked_example", "result", "math")
        we_reason = fact_source.get_fact_source("worked_example", "reasoning", "math")
        fb_rule = fact_source.get_fact_source("formula_breakdown", "rule", "math")
        fb_form = fact_source.get_fact_source("formula_breakdown", "form", "math")
        for fs in (we_result, we_reason, fb_rule, fb_form):
            self.assertIsNotNone(fs)
            self.assertTrue(fact_source.adapter_can_supply(slug, fs),
                            f"{slug} must supply {fs.card_type}.{fs.field}")
        # dimensionless algebra → no units claim invented
        self.assertFalse(audit.DERIVATION_ENGINE_CAPABILITY.supports_units)
        self.assertIn(slug, audit.audit_summary()["audited_adapters"])


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

    def test_formula_breakdown_framing_math_only(self):
        self.assertIsNotNone(contracts.formula_breakdown_framing("math"))
        self.assertIn("why", contracts.formula_breakdown_framing("math"))
        self.assertIsNone(contracts.formula_breakdown_framing("physics"))   # science deferred
        self.assertIsNone(contracts.formula_breakdown_framing("coding"))    # not_applicable

    def test_formula_breakdown_fact_sources_registered(self):
        self.assertIsNotNone(fact_source.get_fact_source("formula_breakdown", "rule", "math"))
        self.assertIsNotNone(fact_source.get_fact_source("formula_breakdown", "form", "math"))
        req = fact_source.required_sources_for("formula_breakdown", "math")
        self.assertEqual({f.field for f in req}, {"rule", "form"})


if __name__ == "__main__":
    unittest.main()
