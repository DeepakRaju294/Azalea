"""A worked example's shown arithmetic must be REPRODUCIBLE: the substitution the learner sees must evaluate
to the shown result. This regressed when an output's display used a rounded intermediate (P = V*I) while its
expr recomputed at full precision (V*(V/R)) — "13*1.18 = 15.36" is wrong (13*1.18 = 15.34)."""
import os
import re
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples.trace_adapters.families.formula_engine import _eval
from app.services.examples.trace_pipeline import route_adapter


def _reasons(title, given):
    adapter = route_adapter({"title": title, "course_type": "math_formula_method"})
    trace = adapter.reference(given)
    return [str(getattr(s, "reason", "") or "") for s in trace.steps]


class Reproducibility(unittest.TestCase):
    def _assert_reproducible(self, reasons):
        # each "… = <substitution> = <value> [unit]" line: eval(substitution) must equal the shown value.
        # Symbolic segments (V/R) raise and are skipped; the numeric substitution is what must reproduce.
        checked = 0
        for r in reasons:
            parts = [p.strip() for p in r.split("=")]
            if len(parts) < 3:
                continue
            mval = re.match(r"^(-?[0-9.]+)", parts[-1])
            if not mval:
                continue
            shown = float(mval.group(1))
            subst = parts[-2].replace("^", "**")            # display caret -> Python power
            try:
                got = _eval(subst, {})                       # sealed ns (sqrt/etc.); symbolic parts raise
            except Exception:
                continue
            checked += 1
            self.assertAlmostEqual(got, shown, delta=0.02, msg=f"'{r}': {subst} = {got} != {shown}")
        self.assertGreater(checked, 0)

    def test_ohms_law_power_step_is_reproducible_with_rounded_intermediate(self):
        # 13/11 = 1.1818 -> displayed 1.18; P must not read "13*1.18 = 15.36".
        rs = _reasons("Ohm's law", {"V": 13, "R": 11})
        self._assert_reproducible(rs)
        power = next(r for r in rs if r.startswith("P"))
        self.assertNotIn("13*1.18 = 15.36", power)               # the broken form is gone
        self.assertIn("13*(13/11)", power)                       # actual computed form shown

    def test_reproducible_across_a_few_formula_topics(self):
        for title, given in [("kinetic energy", {"m": 7, "v": 9}),
                             ("compound interest", {"P": 1500, "r": 7, "t": 3}),
                             ("z-score", {"x": 41, "mean": 55, "sd": 12}),
                             ("Pythagorean theorem", {"a": 7, "b": 13})]:
            self._assert_reproducible(_reasons(title, given))


if __name__ == "__main__":
    unittest.main()
