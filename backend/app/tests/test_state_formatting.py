"""No adapter may leak RAW backend state into a learner-facing string (C7/B5). This checks the ASSEMBLED
learner-facing cards (via the deterministic narration — result = verified EVR + the appended completion clause,
reasoning = the step's verified reason, work = the decision) for every adapter across many seeds. It catches
both the adapter's own strings AND the completion clause (`_final_answer_text`), which an earlier raw-step-only
check missed (quadratic shipped `{'roots': [2, 3]}`; arithmetic shipped `[6, '-', 64]`)."""
import re
import unittest

from app.services.examples.trace_adapters import ADAPTERS
from app.services.examples.trace_pipeline import _deterministic_narration, select_instance

# raw-state signatures in learner prose:
#   [,\[]\s*['\"]  a quote right after `[` or `,`  -> ['A', 'B']  or  [6, '-', 64]
#   \[\s*\[        a nested list                    -> [[3, 5], [8]]
#   \{\s*..\s*:    a dict literal                   -> {'roots': ...}  or  {v: ...}
_RAW = [re.compile(r"[,\[]\s*['\"]"), re.compile(r"\[\s*\["), re.compile(r"\{\s*['\"]?\w+['\"]?\s*:")]


class NoRawStateInLearnerStrings(unittest.TestCase):
    def _scan(self, slug, seed, label, text):
        val = str(text or "")
        hit = next((p.pattern for p in _RAW if p.search(val)), None)
        with self.subTest(slug=slug, seed=seed, field=label):
            self.assertIsNone(hit, f"{slug} {label} leaked raw state ({hit}): {val!r}")

    def test_every_adapter_renders_prose_not_repr(self):
        for slug, adapter in sorted(ADAPTERS.items()):
            for seed in range(1, 12):
                tr = select_instance(adapter, seed=seed)
                if tr is None:
                    continue
                for c in _deterministic_narration(tr):        # the ACTUAL learner-facing cards
                    self._scan(slug, seed, "result", c.get("result"))
                    self._scan(slug, seed, "reasoning", c.get("reasoning"))
                    for w in (c.get("work") or []):
                        self._scan(slug, seed, "work", w)


if __name__ == "__main__":
    unittest.main()
