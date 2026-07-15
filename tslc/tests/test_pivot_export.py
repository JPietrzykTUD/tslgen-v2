"""The explicit PIVOT exporter stays isolated and reports honest subset coverage."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from tslc import cli
from tslc.api import _expand_sources, generate_project
from tslc.backend.cpp_translation import CppBackendDialect
from tslc.backend.registry import registered_backend_ids
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import Catalog
from tslc.ir.scan import scan
from tslc.lower.lowerer import Lowerer
from tslc.pivot import PivotExportRequest, PivotLanguage, export_pivot
from tslc.pivot._lowering import PivotCallCapture, pivot_region_lowerers
from tslc.pivot.model import PivotDefinition, PivotDocument
from tslc.pivot.planner import _contributing_indexes
from tslc.pivot.profiles import profiles_for_distinct_feature_sets
from tslc.pivot.render_yaml import render_pivot_yaml
from tslc.select.selector import Selector


def _export_add(data_root: Path, machine_profiles_path: Path):
    return export_pivot(
        PivotExportRequest(
            source_paths=_expand_sources((data_root,)),
            machine_profiles_path=machine_profiles_path,
            languages=(PivotLanguage.CPP,),
            primitives=("add",),
            profiles=("avx2",),
            type_tags=("si8",),
        )
    )


def test_profiles_are_projected_to_distinct_hardware_feature_sets() -> None:
    common = {
        "family": "demo",
        "features": frozenset({"feature_a"}),
        "alternatives": {},
    }
    projected = profiles_for_distinct_feature_sets(
        (
            MachineProfile(name="plain", **common),
            MachineProfile(
                name="mode_b",
                compile_modes=frozenset({"mode_b"}),
                **common,
            ),
            MachineProfile(
                name="other_features",
                family="demo",
                features=frozenset({"feature_a", "feature_b"}),
                alternatives={},
            ),
            MachineProfile(
                name="other_family",
                family="other",
                features=frozenset({"feature_a"}),
                alternatives={},
            ),
        )
    )

    assert len(projected) == 3
    merged = next(item for item in projected if item.name == "mode_b+plain")
    assert merged.features == frozenset({"feature_a"})
    assert merged.compile_modes == frozenset({"mode_b"})


def test_only_feature_sets_that_add_an_implementation_are_retained() -> None:
    indexes = _contributing_indexes(
        (
            frozenset({1, 2}),
            frozenset({2, 3}),
            frozenset({1, 2, 3}),
            frozenset({4}),
        )
    )

    assert indexes == (2, 3)


def test_leaf_specializations_render_concrete_pivot_yaml(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = _export_add(data_root, machine_profiles_path)

    assert result.diagnostics == ()
    document = next(
        item for item in result.projections[0].documents if item.name == "add"
    )
    by_isa = {definition.isa: definition for definition in document.definitions}

    assert document.inputs == ("left", "right")
    assert document.output == "res"
    assert by_isa["sse2"].signature == (
        ("left", "__m128i"),
        ("right", "__m128i"),
        ("res", "__m128i"),
    )
    assert by_isa["sse2"].direct == ("res = _mm_add_epi8(left, right);",)
    assert by_isa["avx2"].direct == ("res = _mm256_add_epi8(left, right);",)
    fixed_16 = (
        "::tsl::dataparallel::simd_for_t<"
        "::tsl::dataparallel::fixed<16>, int8_t>"
    )
    assert by_isa["tsl_128"].signature == (
        ("left", f"typename {fixed_16}::register_type"),
        ("right", f"typename {fixed_16}::register_type"),
        ("res", f"typename {fixed_16}::register_type"),
    )
    assert by_isa["tsl_128"].direct == (
        f"res = ::tsl::add<{fixed_16}>(left, right);",
    )
    assert "tsl_256" in by_isa
    # Compiler-vector overlays deliberately do not participate in fixed<N>
    # inference, so their 512-bit spelling must not create a TSL fixed alias.
    assert "tsl_512" not in by_isa
    assert all(
        definition.direct[-1].startswith("res = ")
        for definition in by_isa.values()
    )

    artifact = next(
        item
        for item in result.artifacts.artifacts
        if item.logical_path == "cpp/add.yaml"
    )
    assert artifact.content.startswith('name: "add"\ninput:\n')
    assert '  - isa: "sse2"\n    dtype: "int8"\n' in artifact.content
    assert '      - "res = _mm_add_epi8(left, right);"\n' in artifact.content


def test_tsl_fixed_512_definition_uses_lane_count_not_bit_width(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = export_pivot(
        PivotExportRequest(
            source_paths=_expand_sources((data_root,)),
            machine_profiles_path=machine_profiles_path,
            languages=(PivotLanguage.CPP,),
            primitives=("add",),
            profiles=("skylake",),
            type_tags=("si8",),
        )
    )

    document = next(
        item for item in result.projections[0].documents if item.name == "add"
    )
    definition = next(
        item for item in document.definitions if item.isa == "tsl_512"
    )
    assert "fixed<64>" in definition.signature[0][1]
    assert "fixed<512>" not in definition.signature[0][1]
    assert definition.direct == (
        "res = ::tsl::add<::tsl::dataparallel::simd_for_t<"
        "::tsl::dataparallel::fixed<64>, int8_t>>(left, right);",
    )


def test_rust_projection_uses_backend_intrinsics_and_fixed_vector_for(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = export_pivot(
        PivotExportRequest(
            source_paths=_expand_sources((data_root,)),
            machine_profiles_path=machine_profiles_path,
            languages=(PivotLanguage.RUST,),
            primitives=("add",),
            profiles=("avx2",),
            type_tags=("si8",),
        )
    )

    assert result.diagnostics == ()
    projection = result.projections[0]
    assert projection.language is PivotLanguage.RUST
    document = next(item for item in projection.documents if item.name == "add")
    by_isa = {definition.isa: definition for definition in document.definitions}
    assert by_isa["avx2"].signature == (
        ("left", "core::arch::x86_64::__m256i"),
        ("right", "core::arch::x86_64::__m256i"),
        ("res", "core::arch::x86_64::__m256i"),
    )
    assert by_isa["avx2"].direct == (
        "res = core::arch::x86_64::_mm256_add_epi8(left, right);",
    )
    fixed = (
        "<tsl::dataparallel::Fixed<32> as "
        "tsl::tsl_algorithm::VectorFor<tsl::profile::algo::Profile, i8>>::Vec"
    )
    assert by_isa["tsl_256"].signature == (
        ("left", f"<{fixed} as tsl::tsl_core::SimdVector>::RegisterType"),
        ("right", f"<{fixed} as tsl::tsl_core::SimdVector>::RegisterType"),
        ("res", f"<{fixed} as tsl::tsl_core::SimdVector>::RegisterType"),
    )
    assert by_isa["tsl_256"].direct == (
        f"res = tsl::profile::add::<{fixed}>(left, right);",
    )
    artifact = next(
        item
        for item in result.artifacts.artifacts
        if item.logical_path == "rust/add.yaml"
    )
    assert 'left: "core::arch::x86_64::__m256i"' in artifact.content
    maskz = next(item for item in projection.documents if item.name == "add_maskz")
    maskz_avx2 = next(item for item in maskz.definitions if item.isa == "avx2")
    assert maskz_avx2.direct[0].startswith("let __pivot_tmp_")
    assert "_mm256_add_epi8(left, right)" in "\n".join(maskz_avx2.direct)
    assert "__tslc_pivot_call_" not in "\n".join(maskz_avx2.direct)
    assert maskz_avx2.direct[-1].startswith("res = ")


def test_tsl_call_definition_remains_when_plain_body_contains_a_cast(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = export_pivot(
        PivotExportRequest(
            source_paths=_expand_sources((data_root,)),
            machine_profiles_path=machine_profiles_path,
            languages=(PivotLanguage.CPP,),
            primitives=("set1",),
            profiles=("avx2",),
            type_tags=("si8",),
        )
    )

    document = next(
        item for item in result.projections[0].documents if item.name == "set1"
    )
    assert {item.isa for item in document.definitions} == {
        "scalar",
        "tsl_128",
        "tsl_256",
    }
    assert any(
        skip.primitive == "set1"
        and skip.extension == "avx2"
        and "contains a cast" in skip.reason
        for skip in result.skipped
    )


def test_primitive_calls_are_recursively_inlined_into_direct_flow(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = _export_add(data_root, machine_profiles_path)
    document = next(
        item for item in result.projections[0].documents if item.name == "add_maskz"
    )
    definition = next(item for item in document.definitions if item.isa == "avx2")

    direct = "\n".join(definition.direct)
    assert "_mm256_add_epi8(left, right)" in direct
    assert "_mm256_setzero_si256()" in direct
    assert "_mm256_blendv_epi8" in direct
    assert "::tsl::" not in direct
    assert "__tslc_pivot_call_" not in direct
    assert definition.direct[-1].startswith("res = ")


def test_residual_control_and_casts_are_skipped_after_normal_lowering(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = _export_add(data_root, machine_profiles_path)

    assert any(
        skip.primitive == "add_maskz"
        and skip.extension == "scalar"
        and "residual control flow" in skip.reason
        for skip in result.skipped
    )
    assert any(
        skip.primitive == "add_maskz"
        and "contains a cast" in skip.reason
        for skip in result.skipped
    )


def test_generation_loop_is_expanded_by_the_standard_lowerer(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
) -> None:
    selection = Selector().select_profile(
        catalog,
        machine_profiles["avx2"],
        "add",
        ("si8",),
        backend_id="cpp",
    )
    slot = next(
        item
        for item in selection.selected
        if item.extension.isa_name == "avx2"
        and item.primitive.attributes.get("mask") is None
    )
    capture = PivotCallCapture()
    result = Lowerer(region_lowerers=pivot_region_lowerers(capture)).lower(
        slot,
        catalog,
        CppBackendDialect(catalog),
        body_segments=scan(
            """
            var<infer>(acc, left);
            loop<generation>(i, 0, 2, 1) {
              acc = op<add>(acc, right);
            }
            complete(acc);
            """
        ),
    )

    assert result.diagnostics == ()
    assert result.specialization is not None
    body = result.specialization.body_text
    assert "loop" not in body
    assert "{" not in body
    assert body.count("acc = (acc + right);") == 2
    assert body.strip().endswith("return acc;")


def test_yaml_renderer_handles_empty_inputs_without_changing_schema_shape() -> None:
    text = render_pivot_yaml(
        PivotDocument(
            name="zero",
            inputs=(),
            output="res",
            definitions=(
                PivotDefinition(
                    isa="scalar",
                    dtype="int8",
                    signature=(("res", "int8_t"),),
                    direct=("res = 0;",),
                ),
            ),
        )
    )

    assert text == (
        'name: "zero"\n'
        "input: []\n"
        'output: "res"\n'
        "definitions:\n"
        '  - isa: "scalar"\n'
        '    dtype: "int8"\n'
        "    signature:\n"
        '      res: "int8_t"\n'
        "    direct:\n"
        '      - "res = 0;"\n'
    )


def test_pivot_export_does_not_mutate_normal_generation(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    kwargs = {
        "machine_profiles_path": machine_profiles_path,
        "primitives": ("add",),
        "profiles": ("avx2",),
        "type_tags": ("si8",),
        "backends": ("cpp",),
    }
    before = generate_project((data_root,), **kwargs)
    pivot = _export_add(data_root, machine_profiles_path)
    after = generate_project((data_root,), **kwargs)

    assert pivot.projections[0].documents
    assert registered_backend_ids() == ("cpp", "rust")
    assert before.artifacts.digest_manifest() == after.artifacts.digest_manifest()
    assert before.coverage == after.coverage
    assert before.skipped == after.skipped


def test_explicit_export_command_writes_only_pivot_artifacts(
    data_root: Path,
    machine_profiles_path: Path,
    tmp_path: Path,
    capsys,
) -> None:
    output = tmp_path / "pivot"

    status = cli.main(
        [
            "export",
            "pivot",
            "--sources",
            str(data_root),
            "--machine-profiles",
            str(machine_profiles_path),
            "--primitives",
            "add",
            "--profiles",
            "avx2",
            "--types",
            "si8",
            "--language",
            "cpp,rust",
            "--output-root",
            str(output),
        ]
    )

    assert status == 0
    assert (output / "cpp" / "add.yaml").is_file()
    assert (output / "rust" / "add.yaml").is_file()
    assert not (output / "add.yaml").exists()
    assert "exported 6 PIVOT YAML files for cpp,rust" in capsys.readouterr().out
