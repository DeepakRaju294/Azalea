"""Goal-keyed curriculum persistence (scope-plan increment #3): app/services/goal_plan_cache.py.

Off by default — see the module docstring for why: ~350 existing tests call _goal_requirements /
generate_decomposed_topics directly with an injected model_fn and assert exact call counts, so an
always-on cache would make those order-dependent on whatever goal string a prior test happened to use.
Every test here explicitly enables the flag and points at an isolated scratch file, then restores both.
Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_goal_plan_cache
"""
import contextlib
import os
import shutil
import tempfile
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services import goal_plan_cache as gpc

_FLAG = "AZALEA_GOAL_PLAN_CACHE"
_PATH_VAR = "AZALEA_GOAL_PLAN_CACHE_PATH"


class _CacheTestCase(unittest.TestCase):
    """Enables the cache against a throwaway file for the duration of each test."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="goal_plan_cache_test_")
        self._path = os.path.join(self._tmpdir, "cache.json")
        self._prev = {k: os.environ.get(k) for k in (_FLAG, _PATH_VAR)}
        os.environ[_FLAG] = "1"
        os.environ[_PATH_VAR] = self._path

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)
        for k, v in self._prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class DisabledByDefault(unittest.TestCase):
    def test_lookup_and_store_are_no_ops_without_the_flag(self):
        for k in (_FLAG, _PATH_VAR):
            os.environ.pop(k, None)
        self.assertIsNone(gpc.lookup_cached_plan("learn fluid turbulence"))
        gpc.store_plan("learn fluid turbulence", [{"requirement_id": "R1", "statement": "s",
                                                    "kind": "core", "name": "n"}], [])
        self.assertIsNone(gpc.lookup_cached_plan("learn fluid turbulence"))   # still nothing — never wrote


class StoreAndLookup(_CacheTestCase):
    def test_round_trip(self):
        reqs = [{"requirement_id": "R1", "name": "Flow regimes", "kind": "core",
                 "statement": "distinguish laminar and turbulent flow"}]
        prereqs = [{"name": "fluid dynamics", "gloss": "g", "required_knowledge": "r"}]
        gpc.store_plan("learn fluid turbulence", reqs, prereqs)
        cached = gpc.lookup_cached_plan("learn fluid turbulence")
        self.assertIsNotNone(cached)
        self.assertEqual(cached["requirements"], reqs)
        self.assertEqual(cached["assumed_prerequisites"], prereqs)

    def test_goal_phrasing_variance_hits_the_same_entry(self):
        # goal_key_for reuses the same framing-stripped normalization certification uses for goal_core
        # matching — "learn X" / "I want to understand X" / "want to learn about X" all collapse.
        reqs = [{"requirement_id": "R1", "name": "n", "kind": "core", "statement": "s"}]
        gpc.store_plan("learn fluid turbulence", reqs, [])
        self.assertIsNotNone(gpc.lookup_cached_plan("I want to understand fluid turbulence"))
        self.assertIsNotNone(gpc.lookup_cached_plan("Want to learn about fluid turbulence"))

    def test_different_goals_never_collide(self):
        gpc.store_plan("learn fluid turbulence", [{"requirement_id": "R1", "kind": "core",
                                                    "statement": "s", "name": "n"}], [])
        self.assertIsNone(gpc.lookup_cached_plan("learn binary search tree traversal"))

    def test_empty_requirements_never_cached(self):
        gpc.store_plan("learn fluid turbulence", [], [])
        self.assertIsNone(gpc.lookup_cached_plan("learn fluid turbulence"))

    def test_overwrite_replaces_prior_entry(self):
        gpc.store_plan("learn fluid turbulence", [{"requirement_id": "R1", "kind": "core",
                                                    "statement": "old", "name": "n"}], [])
        gpc.store_plan("learn fluid turbulence", [{"requirement_id": "R1", "kind": "core",
                                                    "statement": "new", "name": "n"}], [])
        cached = gpc.lookup_cached_plan("learn fluid turbulence")
        self.assertEqual(cached["requirements"][0]["statement"], "new")

    def test_hit_count_increments(self):
        gpc.store_plan("learn fluid turbulence", [{"requirement_id": "R1", "kind": "core",
                                                    "statement": "s", "name": "n"}], [])
        gpc.record_cache_hit("learn fluid turbulence")
        gpc.record_cache_hit("learn fluid turbulence")
        with open(self._path, encoding="utf-8") as f:
            import json
            data = json.load(f)
        entry = next(iter(data.values()))
        self.assertEqual(entry["hit_count"], 2)

    def test_corrupt_file_treated_as_empty_not_fatal(self):
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            f.write("{not valid json")
        self.assertIsNone(gpc.lookup_cached_plan("learn fluid turbulence"))
        gpc.store_plan("learn fluid turbulence", [{"requirement_id": "R1", "kind": "core",
                                                    "statement": "s", "name": "n"}], [])
        self.assertIsNotNone(gpc.lookup_cached_plan("learn fluid turbulence"))   # self-heals on next write


class KeyCollisionGuard(_CacheTestCase):
    """Plan-stability fix: goal_key_for reuses _canonical_concept_key's alias-match resolution, which could
    (in principle, via a future alias-table bug) collapse two genuinely different goals onto the same cache
    key, causing store_plan's unconditional overwrite to silently serve one goal's curriculum for another.
    lookup_cached_plan now compares the incoming goal against the entry's own stored source_goal and treats
    a poor match as a miss rather than reusing it."""

    def test_compatible_phrasing_still_matches(self):
        self.assertTrue(gpc._goals_compatible("bst traversal", "bst traversal algorithms"))
        self.assertTrue(gpc._goals_compatible("learn fluid turbulence", "I want to understand fluid turbulence"))

    def test_unrelated_goals_do_not_match(self):
        self.assertFalse(gpc._goals_compatible("bst traversal", "mst algorithms"))

    def test_forced_key_collision_is_treated_as_a_miss(self):
        # Simulate an alias-table bug that collapses two unrelated goals onto the same canonical key —
        # goal_key_for itself is trusted to be correct today; this proves the READ-side guard catches it
        # independently, as defense in depth.
        orig = gpc.goal_key_for
        gpc.goal_key_for = lambda goal: "forced_shared_key"
        try:
            gpc.store_plan("bst traversal", [{"requirement_id": "R1", "kind": "core",
                                              "statement": "s", "name": "n"}], [])
            self.assertIsNone(gpc.lookup_cached_plan("mst algorithms"))    # different goal, same forced key
            self.assertIsNotNone(gpc.lookup_cached_plan("bst traversal"))  # same goal -> still a hit
        finally:
            gpc.goal_key_for = orig


_RELEVANCE_FLAG = "AZALEA_PREREQ_RELEVANCE_CHECK"


def _requirements_response(prereq_names):
    return {"requirements": [{"requirement_id": "R1", "name": "n", "kind": "core", "statement": "s"}],
            "assumed_prerequisites": [{"name": name, "gloss": "g", "required_knowledge": "r"}
                                      for name in prereq_names]}


class PrereqRelevanceFilterBasic(unittest.TestCase):
    """The live bug this was built for: 'vector calculus' as a prerequisite of a Stokes'-theorem goal
    (circular) alongside 'differential equations' (unrelated) — neither existing structural guard catches
    either. Cache stays disabled here (default) so these tests exercise only the filter, in isolation."""

    def test_flag_off_by_default_a_rejecting_classifier_is_never_consulted(self):
        from app.services.topic_decomposition_pipeline import _goal_requirements
        response = _requirements_response(["vector calculus", "differential equations"])
        relevance_calls = []

        def relevance_fn(payload):
            relevance_calls.append(payload)
            return {"relevant": False, "rationale": "circular"}

        _, prereqs, _ = _goal_requirements("learn stokes theorem", "s", lambda p: response,
                                           relevance_model_fn=relevance_fn)
        self.assertEqual({p["name"] for p in prereqs}, {"vector calculus", "differential equations"})
        self.assertEqual(len(relevance_calls), 0)

    def test_flag_on_rejected_prereq_is_dropped_accepted_is_kept(self):
        from app.services.topic_decomposition_pipeline import _goal_requirements
        response = _requirements_response(["vector calculus", "line integrals"])

        def relevance_fn(payload):
            return {"relevant": payload["canonical_name"] != "vector calculus", "rationale": "x"}

        with _flag_on(_RELEVANCE_FLAG):
            _, prereqs, _ = _goal_requirements("learn stokes theorem", "s", lambda p: response,
                                               relevance_model_fn=relevance_fn)
        self.assertEqual({p["name"] for p in prereqs}, {"line integrals"})

    def test_flag_on_one_classifier_failure_does_not_affect_other_candidates(self):
        from app.services.topic_decomposition_pipeline import _goal_requirements
        response = _requirements_response(["vector calculus", "line integrals", "differential equations"])

        def relevance_fn(payload):
            name = payload["canonical_name"]
            if name == "line integrals":
                raise RuntimeError("simulated classifier failure")
            return {"relevant": name != "vector calculus", "rationale": "x"}

        with _flag_on(_RELEVANCE_FLAG):
            _, prereqs, _ = _goal_requirements("learn stokes theorem", "s", lambda p: response,
                                               relevance_model_fn=relevance_fn)
        # "vector calculus" confidently rejected -> dropped; "line integrals" failed -> kept (fail-open);
        # "differential equations" confidently accepted -> kept.
        self.assertEqual({p["name"] for p in prereqs}, {"line integrals", "differential equations"})

    def test_flag_on_no_prereqs_is_a_no_op(self):
        from app.services.topic_decomposition_pipeline import _goal_requirements
        response = _requirements_response([])
        calls = []

        def relevance_fn(payload):
            calls.append(1)
            return {"relevant": False, "rationale": "x"}

        with _flag_on(_RELEVANCE_FLAG):
            _, prereqs, _ = _goal_requirements("learn stokes theorem", "s", lambda p: response,
                                               relevance_model_fn=relevance_fn)
        self.assertEqual(prereqs, [])
        self.assertEqual(len(calls), 0)


@contextlib.contextmanager
def _flag_on(name):
    prev = os.environ.get(name)
    os.environ[name] = "1"
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = prev


class PrereqRelevanceFilterCaching(_CacheTestCase):
    """Filtering happens BEFORE store_plan — a rejected prerequisite must never reach the cache, which is
    what made the live bug persist (the same bad 'vector calculus'/'differential equations' pair was served
    from cache 15 times before being found)."""

    def test_rejected_prereq_never_reaches_the_cache(self):
        from app.services.topic_decomposition_pipeline import _goal_requirements
        response = _requirements_response(["vector calculus", "line integrals"])

        def relevance_fn(payload):
            return {"relevant": payload["canonical_name"] != "vector calculus", "rationale": "x"}

        with _flag_on(_RELEVANCE_FLAG):
            _goal_requirements("learn stokes theorem", "s", lambda p: response, relevance_model_fn=relevance_fn)
            cached = gpc.lookup_cached_plan("learn stokes theorem")
        self.assertIsNotNone(cached)
        self.assertEqual({p["name"] for p in cached["assumed_prerequisites"]}, {"line integrals"})


class RequirementsCallIntegration(_CacheTestCase):
    """The actual wiring point: _goal_requirements bypasses the LLM call on a cache hit, bypasses the
    cache READ on feedback, and always writes on a real (successful) call."""

    def test_second_no_feedback_call_reuses_cache_without_hitting_the_model(self):
        from app.services.topic_decomposition_pipeline import _goal_requirements
        response = {"requirements": [{"requirement_id": "R1", "name": "Flow regimes", "kind": "core",
                                      "statement": "distinguish laminar and turbulent flow"}],
                    "assumed_prerequisites": [{"name": "fluid dynamics", "gloss": "g",
                                               "required_knowledge": "r"}]}
        calls = []
        def fn(payload):
            calls.append(1)
            return response
        reqs1, prereqs1, src1 = _goal_requirements("learn fluid turbulence", "s", fn)
        self.assertEqual(src1, "fresh_call")
        self.assertEqual(len(calls), 1)
        reqs2, prereqs2, src2 = _goal_requirements("learn fluid turbulence", "s", fn)
        self.assertEqual(src2, "cache_hit")
        self.assertEqual(len(calls), 1)                       # model NOT called the second time
        self.assertEqual(reqs1, reqs2)
        self.assertEqual(prereqs1, prereqs2)

    def test_feedback_bypasses_cache_read_but_still_writes(self):
        from app.services.topic_decomposition_pipeline import _goal_requirements
        first = {"requirements": [{"requirement_id": "R1", "name": "n", "kind": "core", "statement": "old"}],
                 "assumed_prerequisites": []}
        second = {"requirements": [{"requirement_id": "R1", "name": "n", "kind": "core",
                                    "statement": "new, feedback-informed"}],
                  "assumed_prerequisites": []}
        calls = []
        def fn(payload):
            calls.append(1)
            return first if len(calls) == 1 else second
        _goal_requirements("learn fluid turbulence", "s", fn)
        reqs2, _, src2 = _goal_requirements("learn fluid turbulence", "s", fn,
                                            feedback="make it broader, add more topics")
        self.assertEqual(src2, "fresh_call_feedback")
        self.assertEqual(len(calls), 2)                        # feedback -> the model WAS called again
        self.assertEqual(reqs2[0]["statement"], "new, feedback-informed")
        # the feedback-informed result is now the cached plan for a LATER no-feedback call
        reqs3, _, src3 = _goal_requirements("learn fluid turbulence", "s", fn)
        self.assertEqual(src3, "cache_hit")
        self.assertEqual(len(calls), 2)                        # still not called a third time
        self.assertEqual(reqs3[0]["statement"], "new, feedback-informed")

    def test_disabled_flag_short_circuits_before_cache_or_model(self):
        from app.services.topic_decomposition_pipeline import _goal_requirements
        os.environ["AZALEA_GOAL_REQUIREMENTS"] = "0"
        try:
            calls = []
            reqs, prereqs, src = _goal_requirements("learn fluid turbulence", "s", lambda p: calls.append(1))
            self.assertEqual((reqs, prereqs, src), ([], [], "disabled"))
            self.assertEqual(len(calls), 0)
        finally:
            os.environ.pop("AZALEA_GOAL_REQUIREMENTS", None)


if __name__ == "__main__":
    unittest.main()
