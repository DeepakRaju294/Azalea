"""The artifact chain (§2.5–2.8): every adapter assembles a well-formed AdapterOutput from its verified trace —
projection (interface), step band (§2.3), objectives (§2.7), diagnostics (§2.6.1) — and LessonIntent (§2.5.1)
derives from a topic."""
import unittest

from app.services.examples.trace_adapters import ADAPTERS
from app.services.examples.trace_adapters.artifacts import (AdapterDiagnostics, AdapterOutput, LessonIntent,
                                                            TeachingObjectives, TeachingProjection)
from app.services.examples.trace_pipeline import select_instance


class EveryAdapterProducesAWellFormedOutput(unittest.TestCase):
    def test_adapter_output_contract(self):
        for slug, adapter in sorted(ADAPTERS.items()):
            with self.subTest(slug=slug):
                trace = select_instance(adapter, seed=7)
                self.assertTrue(trace and trace.steps, f"{slug}: no trace")
                out = adapter.build_adapter_output(trace, seed=7, candidate_id="c")

                self.assertIsInstance(out, AdapterOutput)
                self.assertIs(out.trace, trace)
                self.assertEqual(out.verification_level, "trace_verified")

                # §2.5.2 projection: surfaced transitions in order, a terminal, kinds for each
                p = out.projection
                self.assertIsInstance(p, TeachingProjection)
                self.assertEqual(p.transition_ids, [s.id for s in trace.steps])
                self.assertEqual(p.terminal_transition_id, trace.steps[-1].id)
                self.assertEqual(set(p.step_kinds), set(p.transition_ids))

                # §2.3 step band: min <= target <= max, target == the trace's transition count
                b = out.step_band
                self.assertLessEqual(b["min"], b["target"])
                self.assertLessEqual(b["target"], b["max"])
                self.assertEqual(b["target"], len(trace.steps))

                # §2.7 objectives + §2.6.1 diagnostics
                self.assertIsInstance(out.objectives, TeachingObjectives)
                d = out.diagnostics
                self.assertIsInstance(d, AdapterDiagnostics)
                self.assertEqual(d.adapter, slug)
                self.assertTrue(d.instance_accepted)
                self.assertEqual(d.missing_required_cases, [], f"{slug}: required case not covered")

    def test_step_band_widens_with_trace_length(self):
        # a longer trace predicts a larger target — the band tracks the ACTUAL trace, not a constant
        prim = select_instance(ADAPTERS["prim"], seed=7)
        dijkstra = select_instance(ADAPTERS["dijkstra"], seed=7)
        self.assertLess(ADAPTERS["prim"].estimate_teaching_step_band(prim)["target"],
                        ADAPTERS["dijkstra"].estimate_teaching_step_band(dijkstra)["target"])


class LessonIntentFromTopic(unittest.TestCase):
    def test_from_topic_dict(self):
        li = LessonIntent.from_topic({"title": "Kruskal MST", "learning_goal": "build an MST"})
        self.assertEqual(li.concept, "Kruskal MST")
        self.assertEqual(li.learning_goal, "build an MST")
        self.assertEqual(li.audience_level, "intro")


if __name__ == "__main__":
    unittest.main()
