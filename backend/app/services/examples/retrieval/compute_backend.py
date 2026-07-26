"""Computational-API source backend (the chosen PRIMARY online source) — Wolfram Alpha Full Results API.

The engine returns an AUTHORITATIVE computed answer for a problem; that answer is the independent oracle the
solver reproduces against. Design (division of labour): a reviewed problem TEMPLATE supplies the problem +
inputs (from the curated corpus), and the compute API supplies the ANSWER — so no answer is hand-authored, and
the answer comes from an independent authority.

The HTTP call is behind an injectable `ComputeTransport`, so the whole backend is unit-tested offline with
recorded responses; the real `WolframTransport` (stdlib urllib, reads AZALEA_WOLFRAM_APPID) drops in when the
key + network exist. Fail-closed throughout: any error / no key => the backend is unavailable or misses, and
the pipeline falls through to the curated corpus. NOTHING here runs a network call at import or test time.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import replace
from typing import Any, Callable, Optional

from app.services.examples.retrieval import sources
from app.services.examples.retrieval.fingerprints import hash_canonical
from app.services.examples.retrieval.model import (
    CandidateArtifact, PublishedInstance, SourceRef, SourceSnapshot,
)

# concept_key -> the natural-language query sent to the compute engine. Reviewed, deterministic.
_QUERY_TEMPLATES: dict[str, str] = {
    "motional_emf": "motional EMF for B=0.5 T, L=0.2 m, v=10 m/s",
    "faraday_emf": "induced EMF for 200 turns, flux change 0.05 Wb, time 0.1 s",
    "inductor_energy": "energy stored in a 2 H inductor with 3 A current",
    "rl_time_constant": "time constant of an RL circuit with L=10 H and R=5 ohm",
    "kinetic_energy": "kinetic energy of 2 kg at 3 m/s",
    "ohms_law": "current for 12 V across 4 ohm",
    "compound_interest": "1000 at 5% compounded annually for 2 years",
}

# a transport takes the query string and returns the RAW response text (or None on any failure / no key).
ComputeTransport = Callable[[str], Optional[str]]

_WOLFRAM_URL = "https://api.wolframalpha.com/v2/query"
_APPID_ENV = "AZALEA_WOLFRAM_APPID"


def wolfram_transport(query: str, *, timeout: float = 8.0) -> Optional[str]:
    """Real Wolfram Full Results API call (stdlib only). Returns raw JSON text, or None on no key / any error
    (fail-closed — a retrieval failure is a miss, never an exception into generation)."""
    appid = os.getenv(_APPID_ENV)
    if not appid:
        return None
    params = urllib.parse.urlencode({"appid": appid, "input": query, "output": "json",
                                     "format": "plaintext", "podtitle": "Result"})
    try:
        with urllib.request.urlopen(f"{_WOLFRAM_URL}?{params}", timeout=timeout) as resp:  # noqa: S310 - fixed host
            if resp.status != 200:
                return None
            return resp.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001 - any network/parse error is a miss
        return None


def parse_wolfram_answer(raw: str) -> Optional[str]:
    """Extract the plaintext answer from a Wolfram Full Results JSON response. Prefers the 'Result' pod, then
    any primary pod, else the first non-input pod. Returns None if nothing usable."""
    try:
        qr = json.loads(raw).get("queryresult", {})
    except (json.JSONDecodeError, AttributeError):
        return None
    if not qr.get("success"):
        return None
    pods = qr.get("pods") or []

    def _plaintext(pod: dict[str, Any]) -> Optional[str]:
        for sub in pod.get("subpods") or []:
            text = str(sub.get("plaintext") or "").strip()
            if text:
                return text
        return None

    for pod in pods:                                            # 1) the Result pod
        if str(pod.get("title", "")).strip().lower() == "result":
            if (t := _plaintext(pod)):
                return t
    for pod in pods:                                            # 2) a primary pod
        if pod.get("primary") and (t := _plaintext(pod)):
            return t
    for pod in pods:                                            # 3) first non-input pod
        if str(pod.get("title", "")).strip().lower() not in ("input", "input interpretation"):
            if (t := _plaintext(pod)):
                return t
    return None


class ComputationalApiBackend:
    """Primary online source. For a topic whose concept has a reviewed query template, query the compute engine
    for the authoritative answer and build a candidate (reviewed problem + engine answer). Unavailable (a
    guaranteed miss) when no AppID is configured."""
    name = "compute_api"

    def __init__(self, transport: ComputeTransport = wolfram_transport,
                 method_version: str = "wolfram-full-results/v1") -> None:
        self._transport = transport
        self._method_version = method_version

    def available(self) -> bool:
        return bool(os.getenv(_APPID_ENV))

    def _query_for(self, topic: dict[str, Any]) -> Optional[tuple[str, str, CandidateArtifact]]:
        from app.services.examples.retrieval.producer import _concept_key
        key = _concept_key(topic)
        template = sources.lookup(key) if key else None      # reviewed problem template
        query = _QUERY_TEMPLATES.get(key or "")
        if template is None or not query:
            return None
        return key, query, template  # type: ignore[return-value]

    def fetch(self, topic: dict[str, Any]) -> Optional[CandidateArtifact]:
        got = self._query_for(topic)
        if got is None:
            return None
        concept_key, query, template = got
        raw = self._transport(query)
        if not raw:
            return None
        answer = parse_wolfram_answer(raw)
        if not answer:
            return None
        # reviewed problem + AUTHORITATIVE engine answer
        inst: PublishedInstance = replace(template.payload, published_answer=answer)
        snapshot = SourceSnapshot(
            content_hash=hash_canonical({"query": query, "answer": answer, "engine": "wolfram"},
                                        schema="compute-snapshot/v1"),
            retrieved_at="", retrieval_method_version=self._method_version,
            license_policy_version="wolfram-api-terms/v1")
        ref = SourceRef(source_id=f"wolfram:{concept_key}", publisher_id="wolfram_alpha",
                        corpus_family="wolfram_alpha", tier="reference",
                        reuse_policy="internal_verification_only", snapshot=snapshot)
        return CandidateArtifact(artifact_id=f"compute-{concept_key}", concept_key=concept_key,
                                 payload=inst, sources=(ref,))
