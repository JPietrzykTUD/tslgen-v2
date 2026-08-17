"""Maintenance suggestions for source-owned safety/requires metadata."""

from __future__ import annotations

from pathlib import Path

from tslc.diagnostics import has_errors
from tslc.maintenance.metadata_audit import (
    apply_suggestions,
    audit_metadata,
    interactive_apply,
    main,
)
from tslc.pipeline import GenerationRequest, generate
from tslc.sources import expand_source_paths


def test_safety_suggestion_applies_missing_direct_facts(tmp_path: Path) -> None:
    source = tmp_path / "safety_fixture.tsl"
    source.write_text(_safety_source(), encoding="utf-8")

    result = audit_metadata(
        (source,),
        checks=("safety",),
        machine_profiles_path=None,
        backends=("cpp",),
    )

    assert result.diagnostics == ()
    assert len(result.suggestions) == 1
    suggestion = result.suggestions[0]
    assert suggestion.kind == "safety"
    assert suggestion.applicable
    assert "raw_pointer" in suggestion.after
    assert "intrinsic" in suggestion.after

    assert apply_suggestions(result.suggestions, kinds=("safety",)) == 1
    text = source.read_text(encoding="utf-8")
    assert (
        "        safety:\n"
        "          internal_unsafe true\n"
        "          caller_unsafe true\n"
        "          reasons [intrinsic, raw_pointer]\n"
        "        implementation:\n"
    ) in text


def test_interactive_apply_accepts_applicable_suggestion(tmp_path: Path) -> None:
    source = tmp_path / "interactive_fixture.tsl"
    source.write_text(_safety_source(), encoding="utf-8")
    result = audit_metadata(
        (source,),
        checks=("safety",),
        machine_profiles_path=None,
        backends=("cpp",),
    )

    written = interactive_apply(result.suggestions, input_func=lambda _prompt: "a")

    assert written == 1
    assert "reasons [intrinsic, raw_pointer]" in source.read_text(encoding="utf-8")


def test_safety_audit_keeps_raw_comments_and_literals_opaque(tmp_path: Path) -> None:
    source = tmp_path / "opaque_safety_fixture.tsl"
    source.write_text(
        _safety_source()
        .replace("prim<void:=(ptr,v)> store(ptr, data):", "prim<v:=v> store(data):")
        .replace(
            'tsil "intrin<store>(ptr, data);"',
            (
                'tsil "// intrin<fake>(data)\\n'
                'const char* note = \\"mem<copy>(a,b,c)\\";\\n'
                'complete(data);"'
            ),
        ),
        encoding="utf-8",
    )

    result = audit_metadata(
        (source,), checks=("safety",), machine_profiles_path=None, backends=("cpp",)
    )

    assert result.diagnostics == ()
    assert result.suggestions == ()


def test_requires_suggestion_uses_transitive_call_requirements(
    tmp_path: Path,
    machine_profiles_path: Path,
) -> None:
    source = tmp_path / "requires_fixture.tsl"
    source.write_text(_requires_source(), encoding="utf-8")

    result = audit_metadata(
        (source,),
        checks=("requires",),
        machine_profiles_path=machine_profiles_path,
        profiles=("avx2",),
        primitives=("caller",),
        type_tags=("si32",),
        backends=("cpp",),
    )

    assert result.diagnostics == ()
    assert len(result.suggestions) == 1
    suggestion = result.suggestions[0]
    assert suggestion.kind == "requires"
    assert suggestion.applicable
    assert "transitive primitive calls require [avx2]" in suggestion.reason
    assert suggestion.after.strip() == "requires [avx2]"

    assert apply_suggestions(result.suggestions, kinds=("requires",)) == 1
    text = source.read_text(encoding="utf-8")
    assert (
        "      ints:\n"
        "        requires [avx2]\n"
        "        safety:\n"
    ) in text


def test_catalog_validation_error_aborts_audit(tmp_path: Path) -> None:
    source = tmp_path / "invalid_fixture.tsl"
    source.write_text(
        _safety_source().replace(
            "        implementation:\n",
            "        frobnicate true\n        implementation:\n",
        ),
        encoding="utf-8",
    )

    result = audit_metadata((source,), machine_profiles_path=None, backends=("cpp",))

    assert result.suggestions == ()
    assert has_errors(result.diagnostics)
    assert any(
        diagnostic.code == "TSL-CATALOG-UNKNOWN-FIELD"
        for diagnostic in result.diagnostics
    )
    assert main(["--sources", str(source), "--backends", "cpp"]) == 1


def test_requires_suggestions_match_pipeline_facts_for_single_backend_callee(
    tmp_path: Path,
    machine_profiles_path: Path,
) -> None:
    source = tmp_path / "single_backend_fixture.tsl"
    source.write_text(_single_backend_callee_source(), encoding="utf-8")

    result = audit_metadata(
        (source,),
        checks=("requires",),
        machine_profiles_path=machine_profiles_path,
        profiles=("avx2",),
        primitives=("caller",),
        type_tags=("si32",),
        backends=("cpp", "rust"),
    )
    generation = generate(
        GenerationRequest(
            source_paths=expand_source_paths((source,)),
            machine_profiles_path=machine_profiles_path,
            primitives=("caller",),
            profiles=("avx2",),
            type_tags=("si32",),
            backends=("cpp", "rust"),
            render_artifacts=False,
            collect_lowering_trace=True,
        )
    )

    assert generation.lowering_trace is not None
    caller_slots = [
        slot
        for slot in generation.lowering_trace.slots
        if slot.emitted
        and slot.specialization.source_primitive_name == "caller"
        and slot.specialization.required_features > slot.selection_required_features
    ]
    assert caller_slots, "the pipeline must emit a caller slot with a feature delta"
    assert {slot.backend for slot in caller_slots} == {"cpp"}
    expected_missing = sorted(
        {
            feature
            for slot in caller_slots
            for feature in (
                slot.specialization.required_features
                - slot.selection_required_features
            )
        }
    )
    expected_reasons = sorted(
        f"{slot.profile}/{slot.backend}/{slot.specialization.type_tag}"
        for slot in caller_slots
    )

    assert result.diagnostics == ()
    assert len(result.suggestions) == 1
    suggestion = result.suggestions[0]
    assert suggestion.kind == "requires"
    assert suggestion.reason == (
        "transitive primitive calls require "
        f"[{', '.join(expected_missing)}] ({', '.join(expected_reasons)})"
    )
    assert "rust" not in suggestion.reason


def _safety_source() -> str:
    return (
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "prim<void:=(ptr,v)> store(ptr, data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        '          tsil "intrin<store>(ptr, data);"\n'
    )


def _requires_source() -> str:
    return (
        "types:\n"
        "  ints {types [si32]}\n"
        "extension avx2:\n"
        '  extension_name "avx2"\n'
        '  family "x86"\n'
        "  vector_bits 256\n"
        "  cpp:\n"
        "    supported true\n"
        "  vector_register_types:\n"
        "    ints:\n"
        '      cpp "__m256i"\n'
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "prim<v:=v> callee(data):\n"
        "  impls:\n"
        "    avx2:\n"
        "      ints:\n"
        "        requires [avx2]\n"
        "        safety:\n"
        "          internal_unsafe false\n"
        "          caller_unsafe false\n"
        "          reasons []\n"
        "        implementation:\n"
        '          tsil "complete(data);"\n'
        "prim<v:=v> caller(data):\n"
        "  impls:\n"
        "    avx2:\n"
        "      ints:\n"
        "        requires []\n"
        "        safety:\n"
        "          internal_unsafe false\n"
        "          caller_unsafe false\n"
        "          reasons []\n"
        "        implementation:\n"
        '          tsil "complete(call<primitive=callee>(data));"\n'
        "target_families:\n"
        "  known_extension_families [scalar, generic_like, x86, arm, rvv, wasm]\n"
        "  universal_extension_families [scalar, generic_like]\n"
        "  profile_families:\n"
        "    generic:\n"
        "      extension_families []\n"
        "      runner_kinds []\n"
        "    x86:\n"
        "      extension_families [x86]\n"
        "      runner_kinds [sde]\n"
        "    aarch64:\n"
        "      extension_families [arm]\n"
        '      runner_kinds ["qemu-aarch64"]\n'
        "    riscv:\n"
        "      extension_families [rvv]\n"
        '      runner_kinds ["qemu-riscv64"]\n'
        "      backends:\n"
        "        cpp:\n"
        "          feature_flags false\n"
        "    wasm32:\n"
        "      extension_families [wasm]\n"
        "      runner_kinds [wasmtime]\n"
    )


def _single_backend_callee_source() -> str:
    """A caller/callee pair whose extension only supports the C++ backend."""

    return (
        "types:\n"
        "  ints {types [si32]}\n"
        "extension avx2:\n"
        '  extension_name "avx2"\n'
        '  family "x86"\n'
        "  vector_bits 256\n"
        "  cpp:\n"
        "    supported true\n"
        "  vector_register_types:\n"
        "    ints:\n"
        '      cpp "__m256i"\n'
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "language rust:\n"
        '  s32 {type "i32"}\n'
        "prim<v:=v> callee(data):\n"
        "  impls:\n"
        "    avx2:\n"
        "      ints:\n"
        "        requires [avx2]\n"
        "        implementation:\n"
        '          tsil "complete(_mm256_add_epi32(data, data));"\n'
        "prim<v:=v> caller(data):\n"
        "  impls:\n"
        "    avx2:\n"
        "      ints:\n"
        "        requires []\n"
        "        implementation:\n"
        '          tsil "complete(call<primitive=callee>(data));"\n'
        "target_families:\n"
        "  known_extension_families [scalar, generic_like, x86, arm, rvv, wasm]\n"
        "  universal_extension_families [scalar, generic_like]\n"
        "  profile_families:\n"
        "    generic:\n"
        "      extension_families []\n"
        "      runner_kinds []\n"
        "    x86:\n"
        "      extension_families [x86]\n"
        "      runner_kinds [sde]\n"
        "    aarch64:\n"
        "      extension_families [arm]\n"
        '      runner_kinds ["qemu-aarch64"]\n'
        "    riscv:\n"
        "      extension_families [rvv]\n"
        '      runner_kinds ["qemu-riscv64"]\n'
        "      backends:\n"
        "        cpp:\n"
        "          feature_flags false\n"
        "    wasm32:\n"
        "      extension_families [wasm]\n"
        "      runner_kinds [wasmtime]\n"
    )
