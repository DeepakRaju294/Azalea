"""Visual compiler registry.

Each base_type has exactly one compiler. The orchestrator dispatches by
intent.base_type. Support visuals bypass this registry — they don't go
through compilation.

Usage:
    from app.services.visual_compilers import get_compiler
    compiler = get_compiler("node_link_diagram")
    visual_model = compiler.compile(intent, plan, context)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.visual_compilers.base import VisualCompiler


_REGISTRY: dict[str, "VisualCompiler"] = {}


def register(compiler: "VisualCompiler") -> None:
    """Register a compiler under its base_type. Last registration wins."""
    _REGISTRY[compiler.base_type] = compiler


def get_compiler(base_type: str) -> "VisualCompiler | None":
    """Return the compiler for a base_type, or None if no compiler is
    registered (caller should fall back to the stub renderer)."""
    return _REGISTRY.get(base_type)


def registered_base_types() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY.keys()))


def _bootstrap() -> None:
    """Import every concrete compiler so its module-level register() runs.

    Each compiler module is expected to call register() at module load.
    Wrapped in try/except so a broken compiler doesn't break the orchestrator.
    """
    # Import order doesn't matter; each module self-registers.
    # Wrapped individually so one broken module doesn't take out others.
    for module_name in (
        "node_link",
        "code_execution",
        "indexed_sequence",
        "formula",
        "table",
        "grid_matrix",
        "coordinate_graph",
        "memory_layout",
        "geometric",
        "timeline_sequence",
        "set_region",
        "image_illustration",
    ):
        try:
            __import__(f"app.services.visual_compilers.{module_name}")
        except ImportError:
            # Compiler module doesn't exist yet (Phase 6+ work).
            # Caller can check registered_base_types() to know what's available.
            pass


_bootstrap()
