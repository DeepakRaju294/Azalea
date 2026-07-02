"""CP3a — default checkpoint emission into the runtime payload (SPEC_IMPLEMENTATION_CHECKPOINTS §CP3a).

Every adapter-backed card must cite exactly one adapter-produced `checkpoint_id` with valid contiguous
source-transition provenance, BEFORE grouped checkpoints exist. This is the prerequisite that makes the frozen
checkpoint architecture real at runtime. The 6-step contract below runs across every registered adapter."""
import unittest

from app.services.examples.trace_adapters import ADAPTERS
from app.services.examples.trace_pipeline import (_attach_checkpoints, _checkpoint_coverage_fields,
                                                  _deterministic_narration, select_instance)


class CP3aDefaultCheckpointEmission(unittest.TestCase):
    def _case(self, slug, adapter):
        trace = select_instance(adapter, seed=5)
        self.assertIsNotNone(trace, f"{slug}: no teaching trace")
        order = {s.id: i for i, s in enumerate(trace.steps)}

        # (1) default identity TeachingCheckpoint[] + (2) deterministic narration with provenance attached
        cards = _deterministic_narration(trace)
        checkpoints = _attach_checkpoints(cards, trace, adapter)
        self.assertTrue(checkpoints, f"{slug}: adapter emitted no checkpoints")
        cp_ids = {cp.checkpoint_id for cp in checkpoints}

        for c in cards:
            # (3) exactly one checkpoint_id per artifact
            self.assertIn("checkpoint_id", c, f"{slug}: card missing checkpoint_id")
            self.assertIsInstance(c["checkpoint_id"], str)
            self.assertTrue(c["checkpoint_id"], f"{slug}: empty checkpoint_id")
            # (4) that checkpoint exists in the adapter's teaching_checkpoints set
            self.assertIn(c["checkpoint_id"], cp_ids, f"{slug}: card cites unknown checkpoint")

        # (5) every checkpoint's start/end are stable transition IDs bounding a contiguous, ordered range
        for cp in checkpoints:
            ids = list(cp.source_step_ids)
            self.assertIn(cp.source_step_start, order, f"{slug}: checkpoint start not a trace transition")
            self.assertIn(cp.source_step_end, order, f"{slug}: checkpoint end not a trace transition")
            self.assertEqual(cp.source_step_start, ids[0], f"{slug}: start != first source step")
            self.assertEqual(cp.source_step_end, ids[-1], f"{slug}: end != last source step")
            idxs = [order[s] for s in ids]
            self.assertEqual(idxs, list(range(idxs[0], idxs[0] + len(idxs))),
                             f"{slug}: checkpoint source range not contiguous in trace order")

        # (6) the terminal transition is covered — the last card maps to a checkpoint holding the last step
        terminal_id = trace.steps[-1].id
        covering = [cp.checkpoint_id for cp in checkpoints if terminal_id in cp.source_step_ids]
        self.assertTrue(covering, f"{slug}: terminal transition not covered by any checkpoint")
        self.assertEqual(cards[-1]["checkpoint_id"], covering[0], f"{slug}: last card not the terminal checkpoint")

        # CP6b report provenance is well-formed + required checkpoints are all rendered here (identity 1:1)
        fields = _checkpoint_coverage_fields(trace, cards, checkpoints)
        self.assertEqual(fields["missing_required_checkpoint_ids"], [],
                         f"{slug}: a required checkpoint was not rendered")
        self.assertEqual(len(fields["checkpoint_ids_rendered"]), len(cards),
                         f"{slug}: not every card contributed a rendered checkpoint")

    def test_every_adapter_emits_default_checkpoints_with_provenance(self):
        for slug, adapter in ADAPTERS.items():
            with self.subTest(slug=slug):
                self._case(slug, adapter)


if __name__ == "__main__":
    unittest.main()
