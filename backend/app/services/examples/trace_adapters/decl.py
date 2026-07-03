"""Declarative adapter records (scalable-adapters infra, Layer 1/3 glue).

An adapter is described by an `AdapterDecl` — identity + type + family + its `ExampleSpec` + a bundle of
behavior `methods` (reference + the contract hooks). The `methods` are produced by the adapter's TYPE
TEMPLATE (which supplies everything generic for that type), closed over the adapter's small kernels
(recurrence / oracle / prose). `hydrate(decl)` turns the record into a runtime object that is a normal
`FamilyAdapterBase` subclass — so everything downstream (routing, the pipeline, the contract tests) consumes
it exactly as it consumes today's hand-written classes. Nothing outside `trace_adapters/` changes.

This module is deliberately tiny: it is the seam between declarations (data, grouped by type) and the runtime
adapter interface. The intelligence lives in the type templates (`types/*.py`), not here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .families.base import FamilyAdapterBase

# The behavior a declaration must supply (all take `self` first — they become real bound methods on hydrate,
# so `self._provenance(...)` and the other base helpers work). A type template produces this whole bundle.
_REQUIRED_METHODS = (
    "candidates", "is_teaching_trace", "reference", "states_equivalent", "final_answer_entails",
    "invariant_holds", "validate_step_shape", "validate_prose_claims",
)


@dataclass
class AdapterDecl:
    slug: str
    type: str                                              # T1..T12 (must be a known ADAPTER_TYPE)
    family: str                                            # shared-machinery family (graph, sequence, ...)
    example_spec: Any                                      # ExampleSpec (usually built by the type template)
    methods: dict[str, Callable[..., Any]]                # name -> fn(self, ...): reference + the contract hooks
    label_convention: str = ""
    routing: dict[str, Any] = field(default_factory=dict)  # the ROUTING_RULES entry for this adapter
    canonical: Optional[str] = None                        # canonical-solution key (coding adapters), else None
    version: int = 1
    class_attrs: dict[str, Any] = field(default_factory=dict)  # extra class attrs the methods read (e.g. _walk)

    def missing_methods(self) -> list[str]:
        return [m for m in _REQUIRED_METHODS if m not in self.methods]


def decl_from_class(cls: type, *, type: str, family: str, routing: dict[str, Any],
                    canonical: Optional[str] = None) -> AdapterDecl:
    """Build a declaration from an existing adapter CLASS by pulling its methods + attributes. Used to migrate
    hand-written adapters onto the declarative infra with ZERO behavior change (the hydrated adapter runs the
    class's exact code). `type`/`family`/`routing` come from the manifest + routing table."""
    methods = {name: getattr(cls, name) for name in _REQUIRED_METHODS}
    _std = {"slug", "label_convention", "example_spec", "version", *_REQUIRED_METHODS}
    class_attrs = {k: v for k, v in vars(cls).items() if not k.startswith("__") and k not in _std}
    return AdapterDecl(
        slug=cls.slug, type=type, family=family, example_spec=cls.example_spec, methods=methods,
        label_convention=getattr(cls, "label_convention", ""), routing=routing, canonical=canonical,
        class_attrs=class_attrs, version=getattr(cls, "version", 1))


def hydrate(decl: AdapterDecl) -> FamilyAdapterBase:
    """Build a runtime adapter (a `FamilyAdapterBase` subclass instance) from a declaration. The declaration's
    `methods` become real methods on a fresh subclass, so the shared base helpers (`_provenance`,
    `teaching_projection`, `build_adapter_output`, …) keep working unchanged."""
    missing = decl.missing_methods()
    if missing:
        raise ValueError(f"adapter {decl.slug!r} declaration is missing methods: {missing}")
    ns: dict[str, Any] = {
        "slug": decl.slug, "label_convention": decl.label_convention,
        "example_spec": decl.example_spec, "version": decl.version,
        **decl.class_attrs, **decl.methods,
    }
    cls_name = "".join(part.capitalize() for part in decl.slug.split("_")) + "Adapter"
    cls = type(cls_name, (FamilyAdapterBase,), ns)
    return cls()
