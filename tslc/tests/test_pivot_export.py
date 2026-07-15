"""The explicit PIVOT exporter stays isolated and reports honest subset coverage."""

from __future__ import annotations

from pathlib import Path

from tslc import cli
from tslc.api import _expand_sources, generate_project
from tslc.backend.registry import registered_backend_ids
from tslc.pivot import PivotExportRequest, export_pivot
from tslc.pivot.model import PivotDefinition, PivotDocument
from tslc.pivot.render_yaml import render_pivot_yaml


def _export_add(data_root: Path, machine_profiles_path: Path):
    return export_pivot(
        PivotExportRequest(
            source_paths=_expand_sources((data_root,)),
            machine_profiles_path=machine_profiles_path,
            primitives=("add",),
            profiles=("avx2",),
            type_tags=("si8",),
        )
    )


def test_leaf_specializations_render_concrete_pivot_yaml(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = _export_add(data_root, machine_profiles_path)

    assert result.diagnostics == ()
    document = next(item for item in result.documents if item.name == "add")
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
    assert all(
        definition.direct[-1].startswith("res = ")
        for definition in by_isa.values()
    )

    artifact = next(
        item
        for item in result.artifacts.artifacts
        if item.logical_path == "add.yaml"
    )
    assert artifact.content.startswith('name: "add"\ninput:\n')
    assert '  - isa: "sse2"\n    dtype: "int8"\n' in artifact.content
    assert '      - "res = _mm_add_epi8(left, right);"\n' in artifact.content


def test_primitive_calls_are_recursively_inlined_into_direct_flow(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = _export_add(data_root, machine_profiles_path)
    document = next(item for item in result.documents if item.name == "add_maskz")
    definition = next(item for item in document.definitions if item.isa == "avx2")

    direct = "\n".join(definition.direct)
    assert "_mm256_add_epi8(left, right)" in direct
    assert "_mm256_setzero_si256()" in direct
    assert "_mm256_blendv_epi8" in direct
    assert "::tsl::" not in direct
    assert "__tslc_pivot_call_" not in direct
    assert definition.direct[-1].startswith("res = ")


def test_control_and_cast_implementations_are_skipped_with_reasons(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    result = _export_add(data_root, machine_profiles_path)

    assert any(
        skip.primitive == "add_maskz"
        and skip.extension == "scalar"
        and "does not support 'if' regions" in skip.reason
        for skip in result.skipped
    )
    assert any(
        skip.primitive == "add_maskz"
        and "does not support 'cast' regions" in skip.reason
        for skip in result.skipped
    )


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

    assert pivot.documents
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
            "--output-root",
            str(output),
        ]
    )

    assert status == 0
    assert (output / "add.yaml").is_file()
    assert not (output / "cpp").exists()
    assert not (output / "rust").exists()
    assert "exported 3 PIVOT YAML files" in capsys.readouterr().out
