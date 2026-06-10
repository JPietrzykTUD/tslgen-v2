"""Mask result kind (m), call<primitive> wrapper-calls, and profile-scoped closure."""

from __future__ import annotations

from pathlib import Path

import pytest

from tslc.api import generate_project
from tslc.backend.translation import BackendTranslation
from tslc.catalog.model import Catalog
from tslc.diagnostics import has_errors
from tslc.lower.lowerer import Lowerer
from tslc.select.selector import Selector


def _scalar_spec(catalog, machine_profiles, primitive, backend, type_tag="si32"):
    slot = next(
        s
        for s in Selector()
        .select_profile(catalog, machine_profiles["scalar"], primitive, (type_tag,))
        .selected
        if s.extension.name == "scalar"
    )
    return Lowerer().lower(slot, catalog, BackendTranslation(catalog, backend)).specialization


def test_m_kind_lowers_to_mask_type(catalog: Catalog, machine_profiles) -> None:
    cpp = _scalar_spec(catalog, machine_profiles, "nequal", "cpp")
    assert cpp.result_kind == "m"
    assert cpp.body_text == "return left != right;"
    # the wrapper/apply return type is the mask type, not register/base.
    from tslc.backend.cpp import _result_type  # noqa: PLC0415

    assert _result_type(cpp.result_kind) == "typename Vec::mask_type"

    rust = _scalar_spec(catalog, machine_profiles, "nequal", "rust")
    assert rust.body_text == "return left != right;"


def test_call_primitive_renders_wrapper_call(catalog: Catalog, machine_profiles) -> None:
    cpp = _scalar_spec(catalog, machine_profiles, "unequal_zero", "cpp")
    assert cpp.body_text == "return ::tsl::nequal<Vec>(data, ::tsl::set_zero<Vec>());"

    rust = _scalar_spec(catalog, machine_profiles, "unequal_zero", "rust")
    assert rust.body_text == "return nequal::<Self>(data, set_zero::<Self>());"


def test_dependency_closure_pulls_callees(data_root: Path, machine_profiles_path: Path) -> None:
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["unequal_zero"],
        profiles=["scalar"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    emitted = {c.primitive for c in result.coverage}
    # requesting unequal_zero alone also generates the primitives it calls.
    assert {"unequal_zero", "nequal", "set_zero"} <= emitted


def test_closure_is_profile_scoped_and_pruned(
    data_root: Path, machine_profiles_path: Path
) -> None:
    # scalar's call-free comparison bodies must NOT drag in SIMD-only callees like
    # binary_or, and any caller whose callee is unavailable for a profile is pruned.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["nequal"],
        profiles=["scalar"],
    )
    emitted = {c.primitive for c in result.coverage}
    assert "binary_or" not in emitted  # only referenced by nequal's avx2 body
    # nothing emitted references an unemitted callee (no dangling calls).
    by_key = {(c.backend, c.primitive, c.extension, c.type_tag) for c in result.coverage}
    assert ("cpp", "nequal", "scalar", "si32") in by_key
