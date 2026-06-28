"""Content-shape checker (§H / M6): the instructional-quality linter must flag the §H violations on a
bad lesson and pass a clean one. Offline."""
import unittest

from app.services.examples.content_shape import worked_example_shape_violations


def _step(title, work, result, goal="", meta_extra=None):
    md = {"example": {"role": "step"}}
    md.update(meta_extra or {})
    return {"blueprint_key": "worked_example", "title": title, "goal": goal,
            "work": work, "result": result, "metadata": md}


class ContentShapeChecker(unittest.TestCase):
    def test_clean_walkthrough_has_no_violations(self):
        cards = [
            _step("Step 1: Consider B-D", ["Add edge (B,D,5) to the MST"], "Edge (B,D,5) accept; MST grows"),
            _step("Step 2: Consider A-B", ["A and B already connected — skip it (cycle)"],
                  "Edge (A,B,8) skip; the MST is now complete — all vertices connected"),
        ]
        self.assertEqual(worked_example_shape_violations(cards), [])

    def test_too_many_work_lines_flagged(self):
        cards = [_step("Step 1", ["a", "b", "c", "d"], "all vertices connected; complete")]
        self.assertTrue(any("Work lines" in v for v in worked_example_shape_violations(cards)))

    def test_raw_dict_result_flagged(self):
        cards = [_step("Step 1", ["add edge"], "{'selected_edges': [['A','B',2]], 'components': []}")]
        self.assertTrue(any("raw dict" in v for v in worked_example_shape_violations(cards)))

    def test_raw_stage_id_goal_flagged(self):
        cards = [_step("Step 1: Consider edge", ["add edge"], "complete", goal="consider_edge")]
        self.assertTrue(any("raw stage id" in v for v in worked_example_shape_violations(cards)))

    def test_coding_step_without_code_anchor_flagged(self):
        cards = [_step("Step 1", ["mst.append(...) // add"], "mst now has it; complete")]
        self.assertTrue(any("no code anchor" in v
                            for v in worked_example_shape_violations(cards, coding=True)))
        # with an anchor -> not flagged
        cards2 = [_step("Step 1", ["mst.append(...) // add"], "mst now has it; complete",
                        meta_extra={"code_lines": [[3]]})]
        self.assertFalse(any("no code anchor" in v
                             for v in worked_example_shape_violations(cards2, coding=True)))

    def test_missing_completion_flagged(self):
        cards = [_step("Step 1", ["add edge"], "Edge (A,B,2) accept; MST so far [...]")]
        self.assertIn("final step does not state completion", worked_example_shape_violations(cards))


if __name__ == "__main__":
    unittest.main()
