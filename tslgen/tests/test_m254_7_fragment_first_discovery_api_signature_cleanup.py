from __future__ import annotations

import inspect
from collections.abc import Callable
from pathlib import Path

from tslgen.lowering.backend_control import discover_backend_control_directives
from tslgen.lowering.backend_intrinsics import discover_backend_intrinsic_requests
from tslgen.lowering.backend_output_source_islands import (
    discover_backend_output_requests,
)
from tslgen.lowering.backend_type_queries import discover_backend_type_queries
from tslgen.lowering.backend_value_queries import discover_backend_value_queries
from tslgen.lowering.generation_control import lower_generation_control_region
from tslgen.lowering.generation_loops import (
    discover_generation_loop_regions,
    lower_generation_loop_region,
)
from tslgen.lowering.generation_variables import (
    discover_generation_variable_declarations,
)
from tslgen.lowering.mask_keywords import discover_mask_keyword_requests
from tslgen.lowering.mask_lane_constants import (
    discover_mask_lane_constant_requests,
)
from tslgen.lowering.source_operations import discover_source_operation_requests


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "tslgen" / "src" / "tslgen"
TARGET_MODULES = (
    SRC / "lowering" / "backend_type_queries.py",
    SRC / "lowering" / "backend_value_queries.py",
    SRC / "lowering" / "backend_intrinsics.py",
    SRC / "lowering" / "backend_output_source_islands.py",
    SRC / "lowering" / "source_operations.py",
    SRC / "lowering" / "backend_control.py",
    SRC / "lowering" / "generation_variables.py",
    SRC / "lowering" / "generation_control.py",
    SRC / "lowering" / "generation_loops.py",
    SRC / "lowering" / "mask_keywords.py",
    SRC / "lowering" / "mask_lane_constants.py",
)


def test_m254_7_selected_discovery_api_signatures_are_context_first() -> None:
    functions: tuple[Callable[..., object], ...] = (
        discover_backend_type_queries,
        discover_backend_value_queries,
        discover_backend_intrinsic_requests,
        discover_backend_output_requests,
        discover_source_operation_requests,
        discover_backend_control_directives,
        discover_generation_variable_declarations,
        lower_generation_control_region,
        lower_generation_loop_region,
        discover_generation_loop_regions,
        discover_mask_keyword_requests,
        discover_mask_lane_constant_requests,
    )

    for function in functions:
        signature = inspect.signature(function)
        assert "context" in signature.parameters
        assert "body" not in signature.parameters


def test_m254_7_migrated_modules_do_not_expose_implementation_body() -> None:
    for module_path in TARGET_MODULES:
        module_text = module_path.read_text(encoding="utf-8")

        assert "ImplementationBody" not in module_text
        assert "body: ImplementationBody" not in module_text
        assert "context.implementation.source_body_fragments is not None" in module_text
        assert "context.implementation.body" in module_text


def test_m254_7_lowerer_facade_does_not_forward_body_tokens() -> None:
    lowerer_text = (SRC / "lowering" / "lowerer.py").read_text(encoding="utf-8")

    forbidden_snippets = (
        "discover_backend_type_queries(\n            context,\n            context.implementation.body",
        "discover_backend_value_queries(\n            context,\n            context.implementation.body",
        "discover_backend_intrinsic_requests(\n            context,\n            context.implementation.body",
        "discover_backend_output_requests(\n            context,\n            context.implementation.body",
        "discover_source_operation_requests(\n            context,\n            context.implementation.body",
        "discover_backend_control_directives(\n            context,\n            context.implementation.body",
        "discover_generation_variable_declarations(\n            context,\n            context.implementation.body",
        "lower_generation_control_region(\n                context,\n                body,",
        "lower_generation_control_region(\n            context,\n            context.implementation.body",
        "lower_generation_loop_region(\n            context,\n            context.implementation.body",
        "discover_generation_loop_regions(\n            context,\n            context.implementation.body",
        "discover_mask_keyword_requests(\n            context,\n            context.implementation.body",
        "discover_mask_lane_constant_requests(\n            context,\n            context.implementation.body",
    )

    assert not any(snippet in lowerer_text for snippet in forbidden_snippets)


def test_m254_7_guardrails_against_scanner_and_fixture_drift() -> None:
    module_text = "\n".join(
        module_path.read_text(encoding="utf-8") for module_path in TARGET_MODULES
    )
    module_text += (SRC / "lowering" / "lowerer.py").read_text(encoding="utf-8")

    forbidden = (
        "emit_return +",
        "call +",
        "real_scalar_pipeline",
        "real_avx2_pipeline",
        "SourceBodyLexicalRegionScanner(",
        "frozen.",
        "tslgenold",
    )

    assert not any(text in module_text for text in forbidden)
