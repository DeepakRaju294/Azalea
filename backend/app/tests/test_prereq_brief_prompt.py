"""generate_prereq_briefs (llm_client.py) is the backstop that writes a prerequisite's "gloss"/
"required_knowledge" lines when a foundation-folded topic reaches the intro with only a bare name (no
structured gloss from decomposition). 44th path review: a topic titled "Modeling Turbulence" folded into
the intro's prerequisites card with required_knowledge "be able to apply Navier-Stokes equations to
simulate turbulent flows" — advanced turbulence-modeling content, not a simpler prior subject, on an
INTRODUCTORY 'learn fluid turbulence' path. The prompt had no guardrail against this. Offline: monkeypatches
the internal LLM call so no network access is needed.
Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_prereq_brief_prompt
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

import app.services.llm_client as llm_client


class PrereqBriefPromptGuardrail(unittest.TestCase):
    def test_system_prompt_forbids_advanced_required_knowledge(self):
        captured = {}

        def fake_create(call_name, **kwargs):
            captured["system"] = kwargs["input"][0]["content"]
            class _Resp:
                output_text = '{"briefs": []}'
            return _Resp()

        orig = llm_client._create_with_usage
        llm_client._create_with_usage = fake_create
        try:
            llm_client.generate_prereq_briefs(["Modeling Turbulence"], "learn fluid turbulence")
        finally:
            llm_client._create_with_usage = orig

        system = captured["system"]
        self.assertIn("EARLIER, SIMPLER subject", system)
        self.assertIn("never describe a skill more advanced than the path's own goal", system)
        self.assertIn("Navier-Stokes", system)   # the concrete live example, kept as a named anti-pattern


if __name__ == "__main__":
    unittest.main()
