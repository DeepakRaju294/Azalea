"""Curated-corpus + producer + retrieval->assurance wiring tests (offline, no solver/API key).

Covers the chosen retrieval strategy (local curated corpus): every entry is a well-formed PublishedInstance
with a content-hashed snapshot, concept resolution is conservative (ambiguous -> miss), and the end-to-end
retrieve->assure pipeline yields the right assurance level for a supplied produced answer.
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples.retrieval import sources
from app.services.examples.retrieval.cache import VerifiedContractCache
from app.services.examples.retrieval.model import CandidateArtifact, PublishedInstance
from app.services.examples.retrieval.pipeline import resolve_and_assure as _resolve_and_assure
from app.services.examples.retrieval.producer import try_resolve


def resolve_and_assure(topic, produced_answer):
    # isolate each call with a fresh cache so tests don't contaminate via the process-wide default cache.
    return _resolve_and_assure(topic, produced_answer, cache=VerifiedContractCache())


class Corpus(unittest.TestCase):
    def test_entries_are_wellformed_with_snapshots(self):
        entries = sources.all_entries()
        self.assertGreaterEqual(len(entries), 6)
        for e in entries:
            self.assertIsInstance(e, CandidateArtifact)
            self.assertIsInstance(e.payload, PublishedInstance)
            self.assertTrue(e.payload.published_answer.strip())
            self.assertTrue(e.payload.inputs)
            self.assertEqual(e.kind, "published_instance")
            self.assertTrue(e.sources and e.sources[0].snapshot.content_hash)

    def test_snapshot_hashes_are_distinct_per_entry(self):
        hashes = {e.sources[0].snapshot.content_hash for e in sources.all_entries()}
        self.assertEqual(len(hashes), len(sources.all_entries()))

    def test_lookup(self):
        self.assertIsNotNone(sources.lookup("motional_emf"))
        self.assertIsNone(sources.lookup("nonexistent_concept"))


class Producer(unittest.TestCase):
    def test_resolves_by_subject_key(self):
        c = try_resolve({"subject_key": "motional_emf", "title": "x"})
        self.assertIsNotNone(c)
        self.assertEqual(c.concept_key, "motional_emf")

    def test_resolves_by_alias_title(self):
        self.assertEqual(try_resolve({"title": "Motional EMF"}).concept_key, "motional_emf")
        self.assertEqual(try_resolve({"title": "Understanding Faraday's Law"}).concept_key, "faraday_emf")

    def test_miss_returns_none(self):
        self.assertIsNone(try_resolve({"title": "Bubble Sort", "subject_key": "bubble_sort"}))

    def test_ambiguous_or_unknown_is_a_miss_not_a_guess(self):
        # nothing in the alias table matches -> None (never a wrong concept)
        self.assertIsNone(try_resolve({"title": "General Relativity"}))


class RetrieveThenAssure(unittest.TestCase):
    def test_correct_answer_verifies(self):
        rep = resolve_and_assure({"title": "Motional EMF"}, "1.0 V")
        self.assertEqual(rep["level"], "verified_reproduction")
        self.assertEqual(rep["concept_key"], "motional_emf")
        self.assertTrue(rep["sources"][0]["content_hash"])
        self.assertEqual(rep["sources"][0]["reuse_policy"], "derived_example_allowed")

    def test_wrong_answer_refuted_to_guided(self):
        rep = resolve_and_assure({"title": "Motional EMF"}, "5 V")
        self.assertEqual(rep["reproduction_status"], "refute")
        self.assertEqual(rep["level"], "guided")

    def test_indecisive_to_provisional(self):
        rep = resolve_and_assure({"title": "Faraday's Law"}, "roughly 100")
        # "roughly 100" has a magnitude (100) but no unit -> unit unknown -> indecisive -> provisional
        self.assertEqual(rep["level"], "provisional")

    def test_retrieval_miss_returns_none(self):
        self.assertIsNone(resolve_and_assure({"title": "Bubble Sort"}, "anything"))


if __name__ == "__main__":
    unittest.main()
