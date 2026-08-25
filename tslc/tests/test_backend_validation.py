"""Backend contradictions are diagnosed before artifact rendering."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from tslc.backend.cpp_capability import CPP_BACKEND
from tslc.backend.cpp_compiler_capabilities import (
    CPP_COMPILER_CAPABILITIES,
    cpp_compiler_capability,
    cpp_compiler_capability_header_defaults,
    cpp_extensions_compiler_capabilities,
)
from tslc.backend.cpp_validation import validate_cpp_profiles
from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.rust_const_args import RUST_CONST_ARG_WRAPPERS
from tslc.backend.rust_implementation_state import const_arg_type
from tslc.backend.rust_validation import validate_rust_profiles
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import (
    BackendExtensionMetadata,
    Extension,
    ExtensionMetadata,
    MaskPolicy,
)
from tslc.catalog.target_families import (
    BackendProfileFamily,
    ExtensionFamilyCapability,
    ProfileFamilyCapability,
)
from tslc.diagnostics import SourceSpan


@dataclass(frozen=True)
class _Specialization:
    extension_name: str
    type_tag: str = "si32"
    base_type_spelling: str = "i32"
    target: None = None
    mask_policy: str | None = None
    result_kind: str = "void"
    param_kinds: tuple[str, ...] = ("ptr",)
    required_features: frozenset[str] = frozenset()
    immediate: tuple[str, str] | None = None
    generic_params: tuple[tuple[str, str, str], ...] = ()
    source: SourceSpan | None = None


def test_cpp_unsupported_width_indexed_register_is_source_located() -> None:
    source = SourceSpan(Path("extensions.tsl"), 4, 1, 8, 1)
    extension = _extension("wide", cpp=True, vector_bits=192, source=source)
    profile = _profile(
        cpp={"add": (_Specialization("wide"),)},  # type: ignore[arg-type]
        extensions={"wide": extension},
    )

    diagnostics = validate_cpp_profiles((profile,))

    assert [diagnostic.code for diagnostic in diagnostics] == [
        "TSL-BACKEND-CPP-UNSUPPORTED-WIDTH-INDEXED-REGISTER-WIDTH"
    ]
    assert diagnostics[0].location == source.start
    assert CPP_BACKEND.validate_profiles((profile,)) == diagnostics


def test_cpp_unknown_auto_detect_gate_is_diagnosed_before_rendering() -> None:
    extension = _extension("base", cpp=True)
    profile = _profile(
        cpp={"add": (_Specialization("base"),)},  # type: ignore[arg-type]
        extensions={"base": extension},
        auto_detect_gate="future_accelerator",
    )

    diagnostics = validate_cpp_profiles((profile,))

    assert [diagnostic.code for diagnostic in diagnostics] == [
        "TSL-BACKEND-CPP-UNSUPPORTED-AUTO-DETECT-GATE"
    ]


def test_cpp_exact_lane_bitmask_requires_backend_spelling() -> None:
    source = SourceSpan(Path("extensions.tsl"), 7, 3, 9, 1)
    extension = _extension(
        "sized",
        cpp=True,
        family="generic_like",
        vector_bits=0,
        mask_policy=MaskPolicy(kind="exact_lane_bitmask", source=source),
    )
    profile = _profile(
        cpp={"add": (_Specialization("sized"),)},  # type: ignore[arg-type]
        extensions={"sized": extension},
    )

    diagnostics = validate_cpp_profiles((profile,))

    assert [diagnostic.code for diagnostic in diagnostics] == [
        "TSL-BACKEND-CPP-MISSING-MASK-SPELLING"
    ]
    assert diagnostics[0].location == source.start
    assert "backend_spelling.cpp" in diagnostics[0].message


def test_extension_capability_resolution_is_backend_owned_and_deduplicated() -> None:
    extensions = {
        "first": _extension(
            "first", cpp=True, capabilities=("elementwise_clzg",)
        ),
        "second": _extension(
            "second",
            cpp=True,
            capabilities=("clang_vector_types", "elementwise_clzg"),
        ),
    }

    capabilities = cpp_extensions_compiler_capabilities(
        ("first", "second"), extensions
    )

    assert tuple(capability.capability_id for capability in capabilities) == (
        "clang_vector_types",
        "elementwise_clzg",
    )


def test_cpp_clang_builtin_capabilities_use_has_builtin_probes() -> None:
    builtins = {
        "convertvector": "__builtin_convertvector",
        "elementwise_abs": "__builtin_elementwise_abs",
        "elementwise_fmod": "__builtin_elementwise_fmod",
        "elementwise_max": "__builtin_elementwise_max",
        "elementwise_min": "__builtin_elementwise_min",
        "elementwise_popcount": "__builtin_elementwise_popcount",
        "reduce_add": "__builtin_reduce_add",
        "reduce_and": "__builtin_reduce_and",
        "reduce_max": "__builtin_reduce_max",
        "reduce_min": "__builtin_reduce_min",
        "reduce_or": "__builtin_reduce_or",
        "shufflevector": "__builtin_shufflevector",
    }

    for capability_id, builtin in builtins.items():
        capability = cpp_compiler_capability(capability_id)
        assert capability.condition_macro == (
            f"TSL_COMPILER_HAS_{capability_id.upper()}"
        )
        assert capability.preprocessor_probe == f"__has_builtin({builtin})"


def test_cpp_capability_header_defaults_resolve_every_probe_to_boolean() -> None:
    capabilities = tuple(CPP_COMPILER_CAPABILITIES)

    defaults = cpp_compiler_capability_header_defaults(
        tuple(capability.capability_id for capability in capabilities)
    )

    for capability in capabilities:
        assert "\n".join(
            (
                f"#ifndef {capability.condition_macro}",
                f"#  if {capability.preprocessor_probe}",
                f"#    define {capability.condition_macro} 1",
                "#  else",
                f"#    define {capability.condition_macro} 0",
                "#  endif",
                "#endif",
            )
        ) in defaults
        assert (
            f"#  define {capability.condition_macro} "
            f"({capability.preprocessor_probe})"
            not in defaults
        )


def test_cpp_unknown_extension_compiler_capability_is_diagnosed() -> None:
    extension = _extension(
        "unit", cpp=True, capabilities=("missing_capability",)
    )
    profile = _profile(
        cpp={"add": (_Specialization("unit"),)},
        extensions={"unit": extension},
    )

    diagnostics = validate_cpp_profiles((profile,))

    assert [diagnostic.code for diagnostic in diagnostics] == [
        "TSL-BACKEND-CPP-UNKNOWN-COMPILER-CAPABILITY"
    ]


def test_cpp_unknown_profile_detection_is_source_located() -> None:
    source = SourceSpan(Path("target_families.tsl"), 8, 5, 10, 1)
    profile = EmittedProfile(
        profile=MachineProfile("test", "x86", frozenset(), {}),
        specializations_by_backend={"cpp": {}},
        profile_family=ProfileFamilyCapability(
            "x86",
            backends={
                "cpp": BackendProfileFamily(
                    detection="typo_detection",
                    source=source,
                )
            },
        ),
        immediate_split_names=frozenset(),
    )

    diagnostics = validate_cpp_profiles((profile,))

    assert [diagnostic.code for diagnostic in diagnostics] == [
        "TSL-BACKEND-CPP-UNSUPPORTED-PROFILE-DETECTION"
    ]
    assert diagnostics[0].location == source.start


def test_rust_unknown_benchmark_detection_is_source_located() -> None:
    source = SourceSpan(Path("target_families.tsl"), 11, 5, 13, 1)
    profile = EmittedProfile(
        profile=MachineProfile("test", "renamed", frozenset(), {}),
        specializations_by_backend={"rust": {}},
        profile_family=ProfileFamilyCapability(
            "renamed",
            backends={
                "rust": BackendProfileFamily(
                    detection="typo_detection",
                    source=source,
                )
            },
        ),
        immediate_split_names=frozenset(),
    )

    diagnostics = validate_rust_profiles((profile,))

    assert [diagnostic.code for diagnostic in diagnostics] == [
        "TSL-BACKEND-RUST-UNSUPPORTED-BENCHMARK-DETECTION"
    ]
    assert diagnostics[0].location == source.start


def test_rust_unsupported_const_query_type_is_diagnostic() -> None:
    source = SourceSpan(Path("primitive.tsl"), 12, 3, 12, 20)
    extension = _extension("scalar", rust=True, family="scalar", vector_bits=0)
    profile = _profile(
        rust={
            "query": (
                _Specialization(
                    "scalar",
                    generic_params=(("N", "u128", "0"),),
                    source=source,
                ),
            )
        },  # type: ignore[arg-type]
        extensions={"scalar": extension},
    )

    diagnostics = validate_rust_profiles((profile,))

    assert [diagnostic.code for diagnostic in diagnostics] == [
        "TSL-BACKEND-RUST-UNSUPPORTED-CONST-ARG-TYPE"
    ]
    assert diagnostics[0].location == source.start


def test_rust_multi_position_overload_is_rejected_before_rendering() -> None:
    source = SourceSpan(Path("primitive.tsl"), 3, 1, 3, 30)
    extension = _extension("scalar", cpp=True, rust=True, family="scalar", vector_bits=0)
    overloads = (
        _Specialization("scalar", result_kind="v", param_kinds=("v", "v"), source=source),
        _Specialization("scalar", result_kind="v", param_kinds=("s", "ptr"), source=source),
    )
    profile = _profile(
        cpp={"twist": overloads},  # type: ignore[arg-type]
        rust={"twist": overloads},  # type: ignore[arg-type]
        extensions={"scalar": extension},
    )

    diagnostics = validate_rust_profiles((profile,))

    assert [diagnostic.code for diagnostic in diagnostics] == [
        "TSL-BACKEND-RUST-UNSUPPORTED-MULTI-POSITION-OVERLOAD"
    ]
    assert diagnostics[0].location == source.start
    # C++ keeps its general multi-position handling: no such rejection there.
    assert all(
        "MULTI-POSITION" not in diagnostic.code
        for diagnostic in validate_cpp_profiles((profile,))
    )


def test_rust_single_position_overload_remains_legal() -> None:
    extension = _extension("scalar", rust=True, family="scalar", vector_bits=0)
    profile = _profile(
        rust={
            "store": (
                _Specialization("scalar", param_kinds=("ptr", "v")),
                _Specialization("scalar", param_kinds=("ptr", "s")),
            )
        },  # type: ignore[arg-type]
        extensions={"scalar": extension},
    )

    assert validate_rust_profiles((profile,)) == ()


@pytest.mark.parametrize(("type_name", "wrapper"), RUST_CONST_ARG_WRAPPERS.items())
def test_rust_const_argument_mapping_drives_emission(
    type_name: str, wrapper: str
) -> None:
    assert const_arg_type(type_name, "N") == f"{wrapper}<N>"


def _profile(
    *,
    cpp: dict[str, tuple[_Specialization, ...]] | None = None,
    rust: dict[str, tuple[_Specialization, ...]] | None = None,
    extensions: dict[str, Extension],
    auto_detect_gate: str | None = None,
) -> EmittedProfile:
    by_backend = {}
    if cpp is not None:
        by_backend["cpp"] = cpp
    if rust is not None:
        by_backend["rust"] = rust
    return EmittedProfile(
        profile=MachineProfile(
            "test",
            "test",
            frozenset(),
            {},
            auto_detect_gate=auto_detect_gate,
        ),
        specializations_by_backend=by_backend,  # type: ignore[arg-type]
        extensions=extensions,
        immediate_split_names=frozenset(),
    )


def _extension(
    name: str,
    *,
    cpp: bool = False,
    rust: bool = False,
    family: str = "x86",
    vector_bits: int = 128,
    capabilities: tuple[str, ...] = (),
    mask_policy: MaskPolicy | None = None,
    source: SourceSpan | None = None,
) -> Extension:
    backend_metadata = (
        {"cpp": BackendExtensionMetadata(compiler_capabilities=capabilities)}
        if capabilities
        else {}
    )
    return Extension(
        name=name,
        isa_name=name,
        family=family,
        family_capability=ExtensionFamilyCapability(
            family,
            width_indexed_registers=family == "x86",
        ),
        backend_supported={"cpp": cpp, "rust": rust},
        vector_bits=vector_bits,
        vector_bits_kind="fixed" if vector_bits else "",
        mask_policy=mask_policy or MaskPolicy(),
        metadata=ExtensionMetadata(backend=backend_metadata),
        source=source,
    )
