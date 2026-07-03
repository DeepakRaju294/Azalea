"""Type-grouped adapter TEMPLATES + DECLARATIONS (scalable-adapters infra, Layer 1 + 3).

One module per adapter TYPE (t1_traversal, t5_dp, …). Each holds the type's template (the generic
trace-grammar builder) and the declarations for that type's adapters (config + small kernels). Shared
MACHINERY still lives in `families/` (Layer 2); a declaration names its `family` and the loader
(`decl.hydrate`) reunites template + family machinery + kernels into a runtime adapter.

Grouping-by-type here is intentional and orthogonal to grouping-by-family in `families/`: a T5 adapter's
spec/recurrence resembles other T5 adapters, while its instance-generation/visual machinery is shared with
its family. See ADAPTER_DEVELOPMENT_SPEC / the scalable-adapters design notes."""


def declare(cls, slug: str, typ: str):
    """Build a declaration from an existing adapter class, pulling family/routing/canonical from the manifest +
    routing table. Used to migrate hand-written adapters onto the declarative infra (byte-identical)."""
    from ..decl import decl_from_class
    from ..manifest import MANIFEST, ROUTING_RULES
    m = MANIFEST[slug]
    return decl_from_class(cls, type=typ, family=m["family"], routing=ROUTING_RULES.get(slug, {}),
                           canonical=m.get("canonical_solution"))
