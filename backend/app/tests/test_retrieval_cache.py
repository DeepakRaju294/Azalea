"""Verified-contract cache + backend seam + cache-first pipeline tests (offline).

Proves the amortization layer ('store verified contracts, not documents'): a verified instance is cached by
fingerprint, monotonic (stronger overwrites weaker, never the reverse), guided is never cached, and a repeat
instance is served from cache WITHOUT a produced answer.
"""
import os
import tempfile
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples.retrieval.backends import registered_backends, resolve_candidate
from app.services.examples.retrieval.cache import CachedContract, VerifiedContractCache
from app.services.examples.retrieval.pipeline import resolve_and_assure, resolve_from_cache


def _entry(level, subject="subj-1", concept="motional_emf", aid="a1"):
    return CachedContract(concept_key=concept, subject_fingerprint=subject, semantic_fingerprint="sem",
                          level=level, assurance_id=aid, assurance_policy_version="v1", created_at="t")


class Cache(unittest.TestCase):
    def test_put_get_verified(self):
        c = VerifiedContractCache()
        self.assertTrue(c.put(_entry("verified_reproduction")))
        self.assertEqual(c.get("subj-1").level, "verified_reproduction")

    def test_guided_never_cached(self):
        c = VerifiedContractCache()
        self.assertFalse(c.put(_entry("guided")))
        self.assertIsNone(c.get("subj-1"))

    def test_monotonic_stronger_overwrites_weaker(self):
        c = VerifiedContractCache()
        self.assertTrue(c.put(_entry("provisional", aid="prov")))
        self.assertTrue(c.put(_entry("verified_reproduction", aid="ver")))
        self.assertEqual(c.get("subj-1").assurance_id, "ver")

    def test_monotonic_weaker_never_overwrites_stronger(self):
        c = VerifiedContractCache()
        c.put(_entry("verified_reproduction", aid="ver"))
        self.assertFalse(c.put(_entry("provisional", aid="prov")))
        self.assertEqual(c.get("subj-1").assurance_id, "ver")

    def test_persistence_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "cache.jsonl")
            VerifiedContractCache(path).put(_entry("verified_reproduction"))
            reloaded = VerifiedContractCache(path)
            self.assertEqual(reloaded.get("subj-1").level, "verified_reproduction")


class BackendSeam(unittest.TestCase):
    def test_curated_corpus_registered_and_resolves(self):
        names = {b.name for b in registered_backends()}
        self.assertIn("curated_corpus", names)
        cand, backend = resolve_candidate({"title": "Motional EMF"})
        self.assertIsNotNone(cand)
        self.assertEqual(backend, "curated_corpus")

    def test_miss(self):
        cand, backend = resolve_candidate({"title": "Bubble Sort"})
        self.assertIsNone(cand)
        self.assertIsNone(backend)


class CacheFirstPipeline(unittest.TestCase):
    def test_verify_then_serve_from_cache_without_produced_answer(self):
        cache = VerifiedContractCache()
        topic = {"title": "Motional EMF"}
        first = resolve_and_assure(topic, "1.0 V", cache=cache)
        self.assertEqual(first["level"], "verified_reproduction")
        self.assertFalse(first["from_cache"])
        # a repeat now needs NO produced answer — served from cache (the S2 saving)
        cached = resolve_from_cache(topic, cache=cache)
        self.assertIsNotNone(cached)
        self.assertTrue(cached["from_cache"])
        self.assertEqual(cached["level"], "verified_reproduction")
        # and resolve_and_assure short-circuits to the cache regardless of the produced answer passed
        again = resolve_and_assure(topic, "WRONG 999 V", cache=cache)
        self.assertTrue(again["from_cache"])
        self.assertEqual(again["level"], "verified_reproduction")

    def test_refuted_not_cached(self):
        cache = VerifiedContractCache()
        topic = {"title": "Motional EMF"}
        rep = resolve_and_assure(topic, "9 V", cache=cache)   # wrong -> refute -> guided
        self.assertEqual(rep["level"], "guided")
        self.assertIsNone(resolve_from_cache(topic, cache=cache))   # guided never cached

    def test_miss_returns_none(self):
        self.assertIsNone(resolve_and_assure({"title": "Bubble Sort"}, "x", cache=VerifiedContractCache()))


if __name__ == "__main__":
    unittest.main()
