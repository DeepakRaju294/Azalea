"""Computational-API (Wolfram) backend tests — fully OFFLINE via an injected transport (no network, no key).

Proves: the Full-Results JSON parser extracts the answer; the backend builds a candidate from a reviewed
problem template + the engine's authoritative answer; availability gates on the AppID; and when available it
is the PRIMARY backend (ahead of the curated corpus). The real WolframTransport is never called here.
"""
import json
import os
import unittest
from unittest import mock

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples.retrieval.compute_backend import (
    ComputationalApiBackend, parse_wolfram_answer, wolfram_transport,
)


def _wolfram_json(answer: str, *, success=True, title="Result", primary=True):
    return json.dumps({"queryresult": {"success": success, "numpods": 2, "pods": [
        {"title": "Input interpretation", "subpods": [{"plaintext": "motional emf"}]},
        {"title": title, "primary": primary, "subpods": [{"plaintext": answer}]},
    ]}})


class Parser(unittest.TestCase):
    def test_extracts_result_pod(self):
        self.assertEqual(parse_wolfram_answer(_wolfram_json("1 V")), "1 V")

    def test_primary_pod_when_no_result_title(self):
        self.assertEqual(parse_wolfram_answer(_wolfram_json("9 J", title="Value", primary=True)), "9 J")

    def test_failure_returns_none(self):
        self.assertIsNone(parse_wolfram_answer(_wolfram_json("x", success=False)))
        self.assertIsNone(parse_wolfram_answer("not json"))
        self.assertIsNone(parse_wolfram_answer(json.dumps({"queryresult": {"success": True, "pods": []}})))


class Backend(unittest.TestCase):
    def test_fetch_builds_candidate_from_engine_answer(self):
        # inject a transport that returns a recorded Wolfram response — no network
        be = ComputationalApiBackend(transport=lambda q: _wolfram_json("1 V"))
        cand = be.fetch({"title": "Motional EMF"})
        self.assertIsNotNone(cand)
        self.assertEqual(cand.concept_key, "motional_emf")
        self.assertEqual(cand.payload.published_answer, "1 V")          # engine answer, not hand-authored
        self.assertEqual(cand.sources[0].publisher_id, "wolfram_alpha")
        self.assertTrue(cand.sources[0].snapshot.content_hash)

    def test_transport_miss_is_a_miss(self):
        self.assertIsNone(ComputationalApiBackend(transport=lambda q: None).fetch({"title": "Motional EMF"}))

    def test_unknown_concept_is_a_miss(self):
        be = ComputationalApiBackend(transport=lambda q: _wolfram_json("1 V"))
        self.assertIsNone(be.fetch({"title": "Bubble Sort"}))

    def test_availability_gates_on_appid(self):
        be = ComputationalApiBackend(transport=lambda q: _wolfram_json("1 V"))
        with mock.patch.dict(os.environ, {"AZALEA_WOLFRAM_APPID": ""}, clear=False):
            os.environ.pop("AZALEA_WOLFRAM_APPID", None)
            self.assertFalse(be.available())
        with mock.patch.dict(os.environ, {"AZALEA_WOLFRAM_APPID": "TEST-APPID"}, clear=False):
            self.assertTrue(be.available())

    def test_real_transport_no_key_returns_none(self):
        # the real transport must fail closed with no AppID (never raise, never call out)
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AZALEA_WOLFRAM_APPID", None)
            self.assertIsNone(wolfram_transport("anything"))


class PrimaryOrdering(unittest.TestCase):
    def test_compute_api_is_primary_when_available(self):
        # patch the registered compute backend's transport + force availability, and confirm it wins over corpus
        import app.services.examples.retrieval.backends as B
        with mock.patch.dict(os.environ, {"AZALEA_WOLFRAM_APPID": "TEST-APPID"}, clear=False):
            for be in B._BACKENDS:
                if be.name == "compute_api":
                    be._transport = lambda q: _wolfram_json("1 V")
            cand, backend = B.resolve_candidate({"title": "Motional EMF"})
        self.assertEqual(backend, "compute_api")
        self.assertEqual(cand.payload.published_answer, "1 V")

    def test_falls_back_to_corpus_without_key(self):
        import app.services.examples.retrieval.backends as B
        os.environ.pop("AZALEA_WOLFRAM_APPID", None)
        cand, backend = B.resolve_candidate({"title": "Motional EMF"})
        self.assertEqual(backend, "curated_corpus")


if __name__ == "__main__":
    unittest.main()
