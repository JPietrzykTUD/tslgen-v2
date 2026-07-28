"""Mask result kind (m), call<primitive> wrapper-calls, and profile-scoped closure."""

from __future__ import annotations

from dataclasses import replace
import re
from pathlib import Path

import pytest

from tslc.api import generate_project
from tslc.backend.registry import create_backend_dialect
from tslc.catalog.model import Catalog, GenericParam
from tslc.diagnostics import has_errors
from tslc.ir.region_syntax import ParsedCallSelector, parse_call_selector
from tslc.lower.dependencies import (
    CallDependency,
    GenericVectorReference,
    VectorIdentity,
    symbolic_call_dependency_error,
)
from tslc.lower.lowerer import Lowerer, _type_param_bounds
from tslc.ir.scan import scan
from tslc.pipeline import _dependency_discovery_requests
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


def _lowering_for_body(catalog, machine_profiles, body):
    slot = next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["avx2"], "add", ("si32",))
        .selected
        if selected.extension.name == "avx2"
        and selected.primitive.attributes.get("mask") is None
    )
    selected = replace(
        slot,
        implementation=replace(slot.implementation, body_text=body),
    )
    return Lowerer().lower(
        selected,
        catalog,
        create_backend_dialect(catalog, "cpp"),
    )


def _lowered_for_body(catalog, machine_profiles, body):
    lowered = _lowering_for_body(catalog, machine_profiles, body)
    assert lowered.specialization is not None, lowered.diagnostics
    return lowered.specialization


def _dependencies_for_body(catalog, machine_profiles, body):
    specialization = _lowered_for_body(catalog, machine_profiles, body)
    return frozenset(
        origin.dependency
        for origin in specialization.call_dependency_origins
    )


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


def test_runtime_indexed_call_ignores_split_immediate_overload(
    catalog: Catalog, machine_profiles
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["avx2"],
            "permute_lanes",
            ("si32",),
        )
        .selected
        if selected.extension.name == "avx2"
        and selected.primitive.signature == "v:=(m,v,v,vidx)"
    )

    lowered = Lowerer().lower(
        slot,
        catalog,
        create_backend_dialect(catalog, "rust"),
    )

    assert lowered.specialization is not None, lowered.diagnostics
    assert lowered.specialization.type_params[0].bounds == ("to_array",)
    assert "permute_lanes::<Self, IndicesType>(data, indexes)" in (
        lowered.specialization.body_text
    )
    assert "IndicesType, _>" not in lowered.specialization.body_text


@pytest.mark.parametrize(
    ("signature", "expected_body"),
    (
        (
            "v:=(m,v,v,vidx)",
            "return _mm512_mask_permutexvar_epi64(src, mask, indexes, data);",
        ),
        (
            "v:=(m,v,vidx)",
            "return _mm512_maskz_permutexvar_epi64(mask, indexes, data);",
        ),
    ),
)
def test_avx512_indexed_masked_permute_uses_native_intrinsic(
    catalog: Catalog,
    machine_profiles,
    signature: str,
    expected_body: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["skylake"],
            "permute_lanes",
            ("si64",),
        )
        .selected
        if selected.extension.name == "avx512"
        and selected.primitive.signature == signature
    )

    lowered = Lowerer().lower(
        slot,
        catalog,
        create_backend_dialect(catalog, "cpp"),
    )

    assert lowered.specialization is not None, lowered.diagnostics
    assert lowered.specialization.body_text == expected_body


@pytest.mark.parametrize(
    ("profile_name", "extension_name", "type_tag", "signature", "intrinsic"),
    (
        (
            "skylake",
            "avx2_vl",
            "si64",
            "v:=(m,v,v,vidx)",
            "_mm256_mask_permutexvar_epi64",
        ),
        (
            "skylake",
            "avx2_vl",
            "f64",
            "v:=(m,v,vidx)",
            "_mm256_maskz_permutexvar_pd",
        ),
        (
            "cannonlake",
            "avx2_vl",
            "si8",
            "v:=(m,v,v,vidx)",
            "_mm256_mask_permutexvar_epi8",
        ),
        (
            "skylake",
            "sse_vl",
            "si16",
            "v:=(m,v,v,vidx)",
            "_mm_mask_permutexvar_epi16",
        ),
        (
            "skylake",
            "sse_vl",
            "si32",
            "v:=(m,v,v,vidx)",
            "_mm_mask_permutevar_ps",
        ),
        (
            "skylake",
            "sse_vl",
            "f32",
            "v:=(m,v,v,vidx)",
            "_mm_mask_permutevar_ps",
        ),
        (
            "skylake",
            "sse_vl",
            "si64",
            "v:=(m,v,vidx)",
            "_mm_maskz_permutex2var_epi64",
        ),
        (
            "cannonlake",
            "sse_vl",
            "si8",
            "v:=(m,v,vidx)",
            "_mm_maskz_permutex2var_epi8",
        ),
    ),
)
def test_vl_indexed_masked_permute_uses_exact_native_intrinsic(
    catalog: Catalog,
    machine_profiles,
    profile_name: str,
    extension_name: str,
    type_tag: str,
    signature: str,
    intrinsic: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles[profile_name],
            "permute_lanes",
            (type_tag,),
        )
        .selected
        if selected.extension.name == extension_name
        and selected.primitive.signature == signature
    )

    lowered = Lowerer().lower(
        slot,
        catalog,
        create_backend_dialect(catalog, "cpp"),
    )

    assert lowered.specialization is not None, lowered.diagnostics
    body = lowered.specialization.body_text
    assert intrinsic in body
    assert "::tsl::mov_mask" not in body
    assert "::tsl::permute_lanes" not in body


@pytest.mark.parametrize("type_tag", ("si64", "f64"))
def test_sse_vl_indexed_merge_permute_keeps_64_bit_semantic_fallback(
    catalog: Catalog,
    machine_profiles,
    type_tag: str,
) -> None:
    slot = next(
        selected
        for selected in Selector()
        .select_profile(
            catalog,
            machine_profiles["skylake"],
            "permute_lanes",
            (type_tag,),
        )
        .selected
        if selected.extension.name == "sse_vl"
        and selected.primitive.signature == "v:=(m,v,v,vidx)"
    )

    lowered = Lowerer().lower(
        slot,
        catalog,
        create_backend_dialect(catalog, "cpp"),
    )

    assert lowered.specialization is not None, lowered.diagnostics
    body = lowered.specialization.body_text
    assert "::tsl::mov_mask" in body
    assert "::tsl::permute_lanes" in body
    assert "_mm_mask_permutevar_pd" not in body


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
        "attrs[mask=pass_through, aligned=value(primitive::attribute(aligned))]"
    ) == ParsedCallSelector(
        primitive_ref="@self",
        type_args=("Vec<UnsignedT>", "shift", "PreserveSign"),
        attrs=(
            ("mask", "pass_through"),
            ("aligned", "value(primitive::attribute(aligned))"),
        ),
    )
    assert parse_call_selector("primitive=set_zero[OutVec]") == ParsedCallSelector(
        primitive_ref="set_zero",
        type_args=("OutVec",),
    )
    assert parse_call_selector("primitive=@self[Vec] attrs[mask=zero]") is None
    assert parse_call_selector("primitive=set_zero trailing") is None


def test_call_bracket_args_require_exact_generic_param_references(
    catalog: Catalog, machine_profiles
) -> None:
    def _lowering_with_param(body: str):
        slot = next(
            selected
            for selected in Selector()
            .select_profile(catalog, machine_profiles["avx2"], "add", ("si32",))
            .selected
            if selected.extension.name == "avx2"
            and selected.primitive.attributes.get("mask") is None
        )
        slot = replace(
            slot,
            primitive=replace(
                slot.primitive,
                generic_params=(
                    GenericParam(name="PreserveSign", kind="bool", default="true"),
                ),
            ),
            implementation=replace(slot.implementation, body_text=body),
        )
        return Lowerer().lower(slot, catalog, create_backend_dialect(catalog, "cpp"))

    exact = _lowering_with_param(
        "complete(call<primitive=@self[Vec, PreserveSign]>(left, right));"
    )
    assert exact.specialization is not None, exact.diagnostics
    assert "PreserveSign" in exact.specialization.body_text

    # merely *mentioning* the declared param is not a symbolic reference: skip
    # instead of forwarding unresolved text into the emitted call.
    mention = _lowering_with_param(
        "complete(call<primitive=@self[Vec, foo(PreserveSign)]>(left, right));"
    )
    assert mention.specialization is None
    assert any(
        diagnostic.code == "TSL-LOWER-UNSUPPORTED-CALL-TYPEARGS"
        for diagnostic in mention.diagnostics
    )


def test_lowering_records_dependencies_after_resolving_type_aliases(
    catalog: Catalog, machine_profiles
) -> None:
    body = """
      let<type>(ScalarVec, type(vector::as_extension(scalar)));
      complete(call<primitive=@self[ScalarVec], attrs[mask=zero]>(left, right));
    """

    dependencies = _dependencies_for_body(catalog, machine_profiles, body)

    assert dependencies == frozenset(
        {
            CallDependency(
                "add",
                "zero",
                VectorIdentity("si32", "scalar"),
            )
        }
    )


def test_typed_region_arguments_resolve_direct_type_aliases(
    catalog: Catalog, machine_profiles
) -> None:
    body = """
      let<type>(UnsignedT, base::unsigned_of(base::in));
      var<typed>(UnsignedT, scalar_value, cast<static>(UnsignedT, 0));
      var<runtime_array>(UnsignedT, scratch, value(vector::length));
      if<generation>(type::is_same(UnsignedT, ui32)) {
        complete(cast<bitcast>(base::in, scalar_value));
      } else<generation> {
        complete(right);
      }
    """

    lowered = _lowered_for_body(catalog, machine_profiles, body)

    assert "uint32_t scalar_value = static_cast<uint32_t>(0);" in lowered.body_text
    assert "std::vector<uint32_t> scratch_storage" in lowered.body_text
    assert "return ::tsl::bit_cast<int32_t>(scalar_value);" in lowered.body_text
    assert "UnsignedT" not in lowered.body_text


def test_contextual_type_slot_rejects_non_type_query_value(
    catalog: Catalog, machine_profiles
) -> None:
    lowered = _lowering_for_body(
        catalog,
        machine_profiles,
        """
          let<type>(NotAType, type::is_same(base::in, si32));
          complete(left);
        """,
    )

    assert lowered.specialization is None
    assert [diagnostic.code for diagnostic in lowered.diagnostics] == [
        "TSL-LOWER-UNRESOLVED-LET-TYPE"
    ]


def test_lowering_dependency_facts_use_shared_query_functions(
    catalog: Catalog, machine_profiles
) -> None:
    body = """
      let<type>(
        SourceVec,
        type(
          select(
            type::is_same(type(base::in), si32),
            vector::as_extension(scalar),
            vector::as_extension(avx2)
          )
        )
      );
      complete(call<primitive=@self[SourceVec]>(left, right));
    """

    dependencies = _dependencies_for_body(catalog, machine_profiles, body)

    assert dependencies == frozenset(
        {CallDependency("add", None, VectorIdentity("si32", "scalar"))}
    )


def test_target_extension_dependency_preserves_source_vector_base(
    catalog: Catalog, machine_profiles
) -> None:
    body = """
      let<type>(BitBase, type(base::unsigned_of(type(base::in))));
      let<type>(BitVec, type(vector::as_base(BitBase)));
      var<const_infer>(low, call<primitive=extract[BitVec, sse, 0]>(left));
      complete(left);
    """

    dependencies = _dependencies_for_body(catalog, machine_profiles, body)

    assert dependencies == frozenset(
        {
            CallDependency(
                "extract",
                None,
                VectorIdentity("ui32", "avx2"),
                VectorIdentity("ui32", "sse"),
            )
        }
    )

    lowered = _lowered_for_body(catalog, machine_profiles, body)
    assert (
        "extract<tsl::simd<uint32_t, tsl::avx2>, "
        "tsl::simd<uint32_t, tsl::sse>, 0>"
    ) in lowered.body_text


def test_target_base_rendering_preserves_source_vector_extension(
    catalog: Catalog, machine_profiles
) -> None:
    body = """
      let<type>(HalfVec, type(vector::as(sse, type(base::in))));
      let<type>(ToBase, type(scalar::ui16));
      var<const_infer>(low, call<primitive=convert_down[HalfVec, ToBase]>(left));
      complete(left);
    """

    lowered = _lowered_for_body(catalog, machine_profiles, body)

    assert (
        "convert_down<tsl::simd<int32_t, tsl::sse>, "
        "tsl::simd<uint16_t, tsl::sse>>"
    ) in lowered.body_text
    assert "tsl::simd<uint16_t, tsl::avx2>" not in lowered.body_text


def test_dependency_closure_ignores_dead_generation_branch_calls(
    data_root: Path,
    machine_profiles_path: Path,
    tmp_path: Path,
) -> None:
    source = tmp_path / "dependency_probe.tsl"
    source.write_text(
        "prim<v:=v> dependency_probe(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      arith:\n"
        "        implementation:\n"
        '          tsil """\n'
        "            if<generation>(type::is_same(type(base::in), si32)) {\n"
        "              complete(call<primitive=set_zero[Vec]>());\n"
        "            } else {\n"
        "              complete(call<primitive=dead_branch_only[Vec]>());\n"
        "            }\n"
        '          """\n',
        encoding="utf-8",
    )

    result = generate_project(
        [data_root, source],
        machine_profiles_path=machine_profiles_path,
        primitives=["dependency_probe"],
        profiles=["scalar"],
        type_tags=["si32"],
        backends=["cpp"],
    )

    assert not has_errors(result.diagnostics), result.diagnostics
    emitted = {entry.primitive for entry in result.coverage}
    assert {"dependency_probe", "set_zero"} <= emitted
    assert "dead_branch_only" not in emitted
    assert not any(entry.primitive == "dependency_probe" for entry in result.skipped)


def test_dependency_closure_pulls_concrete_callee_source_types(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["shift_left"],
        profiles=["avx2"],
        type_tags=["si32"],
        backends=["cpp"],
    )

    assert not has_errors(result.diagnostics), result.diagnostics
    coverage = {
        (entry.primitive, entry.extension, entry.type_tag)
        for entry in result.coverage
    }
    for extension in (
        "clang_v128",
        "clang_v256",
        "clang_v512",
        "clang_v128_bool",
        "clang_v256_bool",
        "clang_v512_bool",
    ):
        assert ("shift_left", extension, "si32") in coverage
        assert ("reinterpret", extension, "ui32") in coverage
    assert not any(
        entry.primitive == "shift_left"
        and entry.extension.startswith("clang_v")
        and entry.type_tag == "si32"
        for entry in result.skipped
    )


def test_active_extension_variant_outweighs_fixed_fallback_registration(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["shift_left"],
        profiles=["skylake"],
        type_tags=["si32"],
        backends=["cpp"],
    )

    assert not has_errors(result.diagnostics), result.diagnostics
    header = next(
        artifact.content
        for artifact in result.artifacts.artifacts
        if artifact.logical_path == "cpp/include/tsl_skylake.hpp"
    )
    avx2_traits = header.split("struct simd<T, avx2> {", 1)[1].split("};", 1)[0]
    sse_traits = header.split("struct simd<T, sse> {", 1)[1].split("};", 1)[0]
    assert "using mask_type = typename detail::native_mask<256, T>::type;" in avx2_traits
    assert "using mask_type = typename detail::native_mask<128, T>::type;" in sse_traits


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


def test_symbolic_call_dependency_requires_declared_bound() -> None:
    dependency = CallDependency(
        "to_array",
        None,
        GenericVectorReference("Dst", "f64"),
    )

    assert "undeclared SIMD type parameter 'Dst'" in (
        symbolic_call_dependency_error(dependency, {}) or ""
    )
    assert "missing that primitive" in (
        symbolic_call_dependency_error(dependency, {"Dst": ()}) or ""
    )
    assert symbolic_call_dependency_error(
        dependency,
        {"Dst": ("to_array",)},
    ) is None


def test_symbolic_dependency_discovers_callee_without_an_extension_scope(
    catalog: Catalog,
) -> None:
    requests = _dependency_discovery_requests(
        frozenset(
            {
                CallDependency(
                    "to_array",
                    None,
                    GenericVectorReference("Dst", "f64"),
                ),
                CallDependency(
                    "set_zero",
                    None,
                    VectorIdentity("si32", "avx2"),
                ),
                CallDependency(
                    "from_array",
                    None,
                    GenericVectorReference("Unbound"),
                ),
            }
        ),
        backend="rust",
        catalog=catalog,
        fallback_types=("si8", "ui8"),
    )

    assert ("to_array", "f64", None, "rust") in requests
    assert ("set_zero", "si32", "avx2", "rust") in requests
    assert ("from_array", "si8", None, "rust") in requests
    assert ("from_array", "ui8", None, "rust") in requests


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
    assert "extract::<Simd<i8, Avx2>, Simd<i8, Sse>, 0>" in blob
