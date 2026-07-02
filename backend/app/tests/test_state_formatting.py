"""No adapter may leak RAW backend state into a learner-facing string (C7/B5). Every adapter's per-step
`expected_visible_result` / `reason` / `decision` must read as prose — never a Python `repr` like
`[['C','E',5],...]`, `['A','B','C']`, or `{'in_tree': [...]}`. This is the standing regression guard across
ALL adapters + many seeds (the CP7 net only covers 6 topics)."""
import re
import unittest

from app.services.examples.trace_adapters import ADAPTERS
from app.services.examples.trace_pipeline import select_instance

# raw-state signatures: quoted list `['A'`, nested list `[[`, or a dict literal `{key:` / `{'key':`.
_RAW = [re.compile(r"\[\s*['\"]"), re.compile(r"\[\s*\["), re.compile(r"\{\s*['\"]?\w+['\"]?\s*:")]
_FIELDS = ("expected_visible_result", "reason", "decision")


class NoRawStateInLearnerStrings(unittest.TestCase):
    def test_every_adapter_renders_prose_not_repr(self):
        for slug, adapter in sorted(ADAPTERS.items()):
            for seed in range(1, 12):
                tr = select_instance(adapter, seed=seed)
                if tr is None:
                    continue
                for s in tr.steps:
                    for field in _FIELDS:
                        val = str(getattr(s, field, "") or "")
                        hit = next((p.pattern for p in _RAW if p.search(val)), None)
                        with self.subTest(slug=slug, seed=seed, field=field):
                            self.assertIsNone(hit, f"{slug} {field} leaked raw state ({hit}): {val!r}")


if __name__ == "__main__":
    unittest.main()
