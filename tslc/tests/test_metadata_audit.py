"""Maintenance suggestions for source-owned safety/requires metadata."""

from __future__ import annotations

from pathlib import Path

from tslc.maintenance.metadata_audit import (
    apply_suggestions,
    audit_metadata,
    interactive_apply,
)


def test_safety_suggestion_applies_missing_direct_facts(tmp_path: Path) -> None:
    source = tmp_path / "safety_fixture.tsl"
    source.write_text(_safety_source(), encoding="utf-8")

    result = audit_metadata(
        (source,),
        checks=("safety",),
        machine_profiles_path=None,
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
    )

    written = interactive_apply(result.suggestions, input_func=lambda _prompt: "a")

    assert written == 1
    assert "reasons [intrinsic, raw_pointer]" in source.read_text(encoding="utf-8")


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
        "  known_extension_families [scalar, generic_like, x86, arm]\n"
        "  universal_extension_families [scalar, generic_like]\n"
        "  profile_families:\n"
        "    generic:\n"
        "      extension_families []\n"
        "      emulator_kinds []\n"
        "    x86:\n"
        "      extension_families [x86]\n"
        "      emulator_kinds [sde]\n"
        "    aarch64:\n"
        "      extension_families [arm]\n"
        '      emulator_kinds ["qemu-aarch64"]\n'
    )
