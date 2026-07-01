"""The three TEMPLATE adapters (ADAPTER_CATALOG) that every new adapter follows: a coding concept
(tree_inorder), a math concept (quadratic), and a science concept (kinematics). Each must produce a verified,
correct trace and route from a natural topic title. (Contract/conformance/adversarial coverage is asserted for
ALL adapters in test_adapter_conformance / test_adapter_artifacts / test_trace_prose_adversarial.)"""
import unittest

from app.services.examples.trace_adapters import ADAPTERS
from app.services.examples.trace_contract import structural_invariants
from app.services.examples.trace_pipeline import route_adapter, select_instance


class TemplateAdaptersProduceCorrectTraces(unittest.TestCase):
    def _verified(self, slug):
        adapter = ADAPTERS[slug]
        trace = select_instance(adapter, seed=7)
        self.assertIsNotNone(trace, f"{slug}: no teaching instance")
        self.assertEqual(structural_invariants(trace, adapter), [], f"{slug}: structural gate")
        return adapter, trace

    def test_coding_inorder_outputs_sorted_values(self):
        adapter, trace = self._verified("tree_inorder")
        order = trace.final_answer["inorder"]
        self.assertEqual(order, sorted(order))                 # inorder of a BST is ascending
        self.assertEqual(len(trace.steps), len(order))         # one visit per node

    def test_math_quadratic_roots_satisfy_the_equation(self):
        adapter, trace = self._verified("quadratic")
        a = trace.steps[0].inputs["a"]; b = trace.steps[0].inputs["b"]; c = trace.steps[0].inputs["c"]
        for r in trace.final_answer["roots"]:
            if isinstance(r, (int, float)):
                self.assertAlmostEqual(a * r * r + b * r + c, 0, places=6)   # each root solves ax^2+bx+c=0

    def test_science_kinematics_matches_the_equations(self):
        adapter, trace = self._verified("kinematics")
        u = trace.steps[0].inputs["u"]; a = trace.steps[0].inputs["a"]; t = trace.steps[0].inputs["t"]
        self.assertEqual(trace.final_answer["v"], u + a * t)                  # v = u + a t
        self.assertEqual(trace.final_answer["s"], u * t + (a * t * t) / 2 if (u * t + (a * t * t) / 2) % 1
                         else int(u * t + (a * t * t) / 2))                   # s = u t + a t^2 / 2

    def test_templates_route_from_natural_titles(self):
        self.assertEqual(route_adapter({"title": "Inorder Traversal of a BST"}).slug, "tree_inorder")
        self.assertEqual(route_adapter({"title": "Solving a Quadratic Equation"}).slug, "quadratic")
        self.assertEqual(route_adapter({"title": "Kinematics: Constant Acceleration"}).slug, "kinematics")

    def test_coding_template_has_canonical_code_but_science_math_do_not(self):
        from app.services.examples.canonical_solutions import CANONICAL_SOLUTIONS
        self.assertIn("tree_inorder", CANONICAL_SOLUTIONS)     # coding concept ships code
        self.assertNotIn("quadratic", CANONICAL_SOLUTIONS)     # math/science are code-free
        self.assertNotIn("kinematics", CANONICAL_SOLUTIONS)


if __name__ == "__main__":
    unittest.main()
