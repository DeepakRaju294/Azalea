"""Retrieval-grounded example subsystem (RETRIEVAL_GROUNDED_EXAMPLE_SPEC).

Phase 1A implemented here: the OFFLINE, deterministic core — the frozen §5.1 instance-only schemas, canonical
fingerprints, evidence-integrity + assurance derivation, and the assurance-only Slice 1A pipeline. No
retrieval, no delivery, no catalog, no LLM, no live path — those arrive at their named sub-gates.
"""
from app.services.examples.retrieval.model import (  # noqa: F401
    AnswerComparison, AssuranceStrength, EvidenceCheck, EvidenceIntegrityError, EvidenceRecord,
    EvidenceRevocation, InstanceAssuranceDecision, InstanceAssuranceLevel, InstanceAssuranceProfile,
    InstanceAssumption, PublishedInstance, ShippingPolicyError, VerifierDependency, VerifierName,
)
from app.services.examples.retrieval.fingerprints import (  # noqa: F401
    CanonicalizationError, InstanceFingerprintSet, build_instance_fingerprints, hash_canonical,
    make_evidence_subject,
)
from app.services.examples.retrieval.validate import (  # noqa: F401
    derive_instance_assurance, validate_assurance_decision,
)
from app.services.examples.retrieval.slice1a import run_slice1a  # noqa: F401
from app.services.examples.retrieval.producer import try_resolve  # noqa: F401
from app.services.examples.retrieval.pipeline import resolve_and_assure, resolve_from_cache  # noqa: F401
from app.services.examples.retrieval.backends import registered_backends, resolve_candidate  # noqa: F401
from app.services.examples.retrieval.cache import (  # noqa: F401
    CachedContract, VerifiedContractCache, default_cache,
)
from app.services.examples.retrieval.delivery import (  # noqa: F401
    DeliveredInstance, ShippingPolicy, assert_delivery_scope, ship_disposition, validate_shipping_eligibility,
)
from app.services.examples.retrieval.escalation import (  # noqa: F401
    ResolutionResult, next_state, route_disposition, route_retrieval_miss,
)
from app.services.examples.retrieval.compare import ComparisonOutcome, compare_answer  # noqa: F401
from app.services.examples.retrieval.compute_backend import (  # noqa: F401
    ComputationalApiBackend, parse_wolfram_answer, wolfram_transport,
)
from app.services.examples.retrieval.shadow import is_observing, observe_grounding  # noqa: F401
from app.services.examples.retrieval import sources  # noqa: F401
