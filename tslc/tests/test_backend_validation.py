"""Backend contradictions are diagnosed before artifact rendering."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from tslc.backend.cpp_capability import CPP_BACKEND
from tslc.backend.cpp_validation import (
    resolve_cpp_compile_guards,
    validate_cpp_profiles,
)
from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.rust import _const_arg_type
from tslc.backend.rust_const_args import RUST_CONST_ARG_WRAPPERS
from tslc.backend.rust_validation import validate_rust_profiles
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import (
    BackendCompileGuard,
    BackendExtensionMetadata,
    Extension,
    ExtensionMetadata,
)
from tslc.diagnostics import SourceSpan


@dataclass(frozen=True)
class _Specialization:
    extension_name: str
    target: None = None
    mask_policy: str | None = None
    result_kind: str = "void"
    param_kinds: tuple[str, ...] = ("ptr",)
    immediate: tuple[str, str] | None = None
    generic_params: tuple[tuple[str, str, str], ...] = ()
    source: SourceSpan | None = None


def test_cpp_unsupported_declared_x86_width_is_source_located() -> None:
    source = SourceSpan(Path("extensions.tsl"), 4, 1, 8, 1)
    extension = _extension("wide", cpp=True, vector_bits=192, source=source)
    profile = _profile(
        cpp={"add": (_Specialization("wide"),)},  # type: ignore[arg-type]
        extensions={"wide": extension},
    )

    diagnostics = validate_cpp_profiles((profile,))

    assert [diagnostic.code for diagnostic in diagnostics] == [
        "TSL-BACKEND-CPP-UNSUPPORTED-X86-WIDTH"
    ]
    assert diagnostics[0].location == source.start
    assert CPP_BACKEND.validate_profiles((profile,)) == diagnostics


def test_compile_guard_conflicts_are_diagnostics_not_exceptions() -> None:
    first = BackendCompileGuard("mode_a", "MODE", "1")
    second = BackendCompileGuard("mode_b", "MODE", "2")
    extensions = {
        "first": _extension("first", cpp=True, guards=(first,)),
        "second": _extension("second", cpp=True, guards=(second,)),
    }

    resolution = resolve_cpp_compile_guards(
        ("first", "second"), extensions, profile_name="conflict"
    )

    assert tuple(guard.name for guard in resolution.guards) == ("mode_a",)
    assert [diagnostic.code for diagnostic in resolution.diagnostics] == [
        "TSL-BACKEND-CPP-CONFLICTING-COMPILE-GUARD-VALUE"
    ]


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


@pytest.mark.parametrize(("type_name", "wrapper"), RUST_CONST_ARG_WRAPPERS.items())
def test_rust_const_argument_mapping_drives_emission(
    type_name: str, wrapper: str
) -> None:
    assert _const_arg_type(type_name, "N") == f"{wrapper}<N>"


def _profile(
    *,
    cpp: dict[str, tuple[_Specialization, ...]] | None = None,
    rust: dict[str, tuple[_Specialization, ...]] | None = None,
    extensions: dict[str, Extension],
) -> EmittedProfile:
    by_backend = {}
    if cpp is not None:
        by_backend["cpp"] = cpp
    if rust is not None:
        by_backend["rust"] = rust
    return EmittedProfile(
        profile=MachineProfile("test", "test", frozenset(), {}),
        specializations_by_backend=by_backend,  # type: ignore[arg-type]
        extensions=extensions,
    )


def _extension(
    name: str,
    *,
    cpp: bool = False,
    rust: bool = False,
    family: str = "x86",
    vector_bits: int = 128,
    guards: tuple[BackendCompileGuard, ...] = (),
    source: SourceSpan | None = None,
) -> Extension:
    backend_metadata = (
        {"cpp": BackendExtensionMetadata(compile_guards=guards)} if guards else {}
    )
    return Extension(
        name=name,
        isa_name=name,
        family=family,
        compose_prefix={},
        compose_suffix_by_type={},
        backend_supported={"cpp": cpp, "rust": rust},
        vector_bits=vector_bits,
        vector_bits_kind="fixed" if vector_bits else "",
        metadata=ExtensionMetadata(backend=backend_metadata),
        source=source,
    )
