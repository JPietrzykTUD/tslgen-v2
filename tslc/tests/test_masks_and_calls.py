"""Mask result kind (m), call<primitive> wrapper-calls, and profile-scoped closure."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tslc.api import generate_project
from tslc.backend.translation import create_backend_dialect
from tslc.catalog.model import Catalog
from tslc.diagnostics import has_errors
from tslc.lower.calls import ParsedCallSelector, parse_call_selector
from tslc.lower.dependencies import (
    CallDependency,
    VectorIdentity,
    extract_call_dependencies_from_segments,
)
from tslc.lower.lowerer import Lowerer, _type_param_bounds
from tslc.ir.scan import scan
from tslc.select.selector import Selector
from tslc.support_policy_views import immediate_split_names


def _scalar_spec(catalog, machine_profiles, primitive, backend, type_tag="si32"):
    slot = next(
        s
        for s in Selector()
        .select_profile(catalog, machine_profiles["scalar"], primitive, (type_tag,))
        .selected
        if s.extension.name == "scalar"
    )
    return Lowerer().lower(slot, catalog, create_backend_dialect(catalog, backend)).specialization


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


def test_immediate_split_names_only_mixed_immediate_families(catalog: Catalog) -> None:
    split_names = immediate_split_names(catalog)
    assert "shift_right" in split_names
    assert "insert" not in split_names
    assert "extract" not in split_names


def test_call_selector_parser_keeps_syntax_only_shape() -> None:
    assert parse_call_selector(
        "primitive=@self[Vec<UnsignedT>, shift, PreserveSign], "
        "attrs[mask=pass_through, aligned=value<generation>(primitive::attribute(aligned))]"
    ) == ParsedCallSelector(
        primitive_ref="@self",
        type_args=("Vec<UnsignedT>", "shift", "PreserveSign"),
        attrs=(
            ("mask", "pass_through"),
            ("aligned", "value<generation>(primitive::attribute(aligned))"),
        ),
    )
    assert parse_call_selector("primitive=set_zero[OutVec]") == ParsedCallSelector(
        primitive_ref="set_zero",
        type_args=("OutVec",),
    )
    assert parse_call_selector("primitive=@self[Vec] attrs[mask=zero]") is None
    assert parse_call_selector("primitive=set_zero trailing") is None


def test_dependency_extraction_resolves_queries_without_backend_dialect(
    catalog: Catalog,
) -> None:
    body = """
      let<type>(ScalarVec, type<backend>(vector::as_extension(scalar)));
      call<primitive=@self[ScalarVec], attrs[mask=zero]>(left, right);
    """

    dependencies = extract_call_dependencies_from_segments(
        scan(body),
        "add",
        "avx2",
        "si32",
        None,
        None,
        None,
        catalog,
    )

    assert dependencies == frozenset(
        {
            CallDependency(
                "add",
                "zero",
                VectorIdentity("si32", "scalar"),
            )
        }
    )


def test_primitive_corpus_uses_comma_separated_call_attrs(data_root: Path) -> None:
    stale: list[str] = []
    pattern = re.compile(r"call<[^>\n]*[^,]\s+attrs\[")
    for path in sorted((data_root / "primitives").rglob("*.tsl")):
        for line_number, line in enumerate(path.read_text().splitlines(), start=1):
            if pattern.search(line):
                stale.append(f"{path}:{line_number}:{line.strip()}")

    assert stale == []


def test_type_param_bounds_use_call_regions_not_raw_text() -> None:
    body = '''
        var<infer>(idx_array, call<primitive=to_array[IndicesType]>(index));
        if<generation>(true) {
            var<infer>(tmp, call<primitive=mask_test[IndicesType], attrs[mask=zero]>(index));
        }
        ignored = "call<primitive=from_string[IndicesType]>(index)";
    '''
    assert _type_param_bounds(body, "IndicesType") == ("mask_test", "to_array")


def test_convert_down_insert_call_uses_target_vector_alias(
    data_root: Path, machine_profiles_path: Path
) -> None:
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["convert_down"],
        profiles=["avx2", "skylake"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics

    blob = "\n".join(artifact.content for artifact in result.artifacts.artifacts)
    assert "insert_imm" not in blob
    assert ", avx2, index" not in blob
    assert ", avx2_vl, index" not in blob
    assert ", avx512, index" not in blob
    assert (
        "::tsl::insert<tsl::simd<float, tsl::sse>, "
        "tsl::simd<float, tsl::avx2>, index>"
    ) in blob
    assert "insert::<Simd<f32, Sse>, Simd<f32, Avx2>, index>" in blob


def test_call_type_args_accept_extension_and_literal_index(
    data_root: Path, machine_profiles_path: Path
) -> None:
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["cast"],
        profiles=["avx2"],
        backends=["cpp", "rust"],
        type_tags=["si8"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert all("call type-args" not in skip.reason for skip in result.skipped)

    blob = "\n".join(artifact.content for artifact in result.artifacts.artifacts)
    assert "::tsl::extract<Vec, tsl::simd<int8_t, tsl::sse>, 0>" in blob
    assert "extract::<Self, Simd<i8, Sse>, 0>" in blob
