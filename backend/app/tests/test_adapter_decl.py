"""Scalable-adapters infra, Phase 1: prove an AdapterDecl hydrated by a TYPE TEMPLATE produces a runtime
adapter that satisfies the FULL adapter contract — the same gauntlet the hand-written classes pass
(structural invariants, machine fidelity, prose fidelity, the Phase-1.5 visual contract, and the artifact
projection). Uses a self-contained toy template so the test proves the MACHINERY, independent of any real
adapter. Fully offline."""
import unittest

from app.services.examples import trace_pipeline as tp
from app.services.examples.trace_adapters.decl import AdapterDecl, hydrate
from app.services.examples.trace_adapters.example_spec import ExampleSpec, InstanceShape, StageSpec
from app.services.examples.trace_contract import (ContractTrace, Step, fact, structural_invariants,
                                                  validate_fidelity, validate_prose,
                                                  visual_contract_violations)


def _running_sum_template(slug: str) -> AdapterDecl:
    """A toy TYPE TEMPLATE: builds the whole methods bundle for a 'running sum of a list' adapter, closed over
    nothing adapter-specific here (a real template would close over kernels). Exercises reference + every hook."""
    spec = ExampleSpec(
        input=InstanceShape("integers", count=(3, 3)),
        stages={"add": StageSpec("add", "add the next element to the running total")},
        structure="add+ until the list is consumed",
        must_exercise=["add", "completion"], terminal="the whole list is summed", output_shape="the total")

    def candidates(self, seed):
        yield {"nums": [1, 2, 3], "_id": "toy_0"}

    def is_teaching_trace(self, trace):
        return len(trace.steps) >= 2 and bool(trace.case_evidence.get("add"))

    def reference(self, example_input, *, candidate_id="", attempt=1, seed=0):
        nums = list(example_input["nums"])
        total = 0
        steps, evidence = [], {}
        for i, x in enumerate(nums, start=1):
            prior = {"sum": total, "seen": i - 1}
            total += x
            after = {"sum": total, "seen": i}
            sid = f"s{i}"
            evidence.setdefault("add", []).append(sid)
            reason = f"add {x} to the running total, giving {total}."
            evr = f"Running total is now {total}."
            allowed = sorted({int(t) for t in __import__("re").findall(r"\d+", reason + " " + evr)})
            steps.append(Step(
                id=sid, operation="add", prior_state=prior, state_after=after,
                inputs={"element": x, "total": total}, decision=f"add {x}", reason=reason,
                visual_state={"kind": "array", "array": list(nums), "active": i - 1},
                visual_delta={"added": x}, expected_visible_result=evr,
                facts={"allowed_values": allowed, "required_facts": [fact("total", total)],
                       "forbidden_claims": []}))
        if steps:
            evidence.setdefault("completion", []).append(steps[-1].id)
        return ContractTrace(
            problem=f"Sum the list {nums}.", conventions={}, initial_state={"sum": 0, "seen": 0},
            final_answer={"value": total}, steps=steps,
            invariants=[{"id": "sum_nonneg", "scope": "every_step", "statement": "the total never decreases"}],
            required_cases=["add", "completion"], case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                        attempt=attempt))

    def states_equivalent(self, a, b):
        a, b = a or {}, b or {}
        return a.get("sum") == b.get("sum") and a.get("seen") == b.get("seen")

    def final_answer_entails(self, state, answer):
        return (state or {}).get("sum") == (answer or {}).get("value")

    def invariant_holds(self, inv, state):
        return (state or {}).get("sum", 0) >= 0

    def validate_step_shape(self, step):
        return [] if step.operation == "add" else [f"unexpected operation {step.operation!r}"]

    def validate_prose_claims(self, card, step):
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        return [] if str(step.inputs["total"]) in prose else [("total_not_stated", str(step.inputs["total"]))]

    methods = {"candidates": candidates, "is_teaching_trace": is_teaching_trace, "reference": reference,
               "states_equivalent": states_equivalent, "final_answer_entails": final_answer_entails,
               "invariant_holds": invariant_holds, "validate_step_shape": validate_step_shape,
               "validate_prose_claims": validate_prose_claims}
    return AdapterDecl(slug=slug, type="T8a", family="sequence", example_spec=spec, methods=methods,
                       label_convention="ints", routing={"any": [slug]}, canonical=None)


class HydratedAdapterConformance(unittest.TestCase):
    def setUp(self):
        self.adapter = hydrate(_running_sum_template("toy_running_sum"))

    def test_hydrate_produces_a_family_adapter(self):
        from app.services.examples.trace_adapters.families.base import FamilyAdapterBase
        self.assertIsInstance(self.adapter, FamilyAdapterBase)
        self.assertEqual(self.adapter.slug, "toy_running_sum")

    def test_full_contract_gauntlet(self):
        trace = tp.select_instance(self.adapter, seed=1)
        self.assertIsNotNone(trace)
        self.assertEqual(structural_invariants(trace, self.adapter), [])       # structural
        self.assertEqual(visual_contract_violations(trace), [])                # Phase-1.5 visual contract
        cards = tp._deterministic_narration(trace, self.adapter)
        self.assertTrue(validate_fidelity(cards, trace, self.adapter, validate_visual_state=True).ok)  # fidelity
        from app.services.examples.trace_contract import hard_prose_violations
        self.assertEqual(hard_prose_violations(validate_prose(cards, trace, self.adapter)), [])  # prose
        self.assertEqual(tp._final_answer_text(trace), "= 6")                  # 1+2+3
        # the shared base artifact chain works on a hydrated adapter (uses self.* the base defines)
        out = self.adapter.build_adapter_output(trace)
        self.assertTrue(out.diagnostics.structural_ok)
        self.assertEqual(out.projection.label_convention, "ints")

    def test_missing_method_is_rejected(self):
        decl = _running_sum_template("bad")
        decl.methods.pop("reference")
        with self.assertRaises(ValueError):
            hydrate(decl)


if __name__ == "__main__":
    unittest.main()
