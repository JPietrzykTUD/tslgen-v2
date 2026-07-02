"""Catalog/profile validation catches source-data shape errors before lowering."""

from __future__ import annotations

import re

from pathlib import Path

import pytest

from tslc.catalog.builder import CatalogBuilder
from tslc.catalog.machine_profiles import load_machine_profiles_checked
from tslc.catalog.target_families import ProfileFamilyCapability, TargetFamilyCatalog
from tslc.catalog.validation import validate_catalog
from tslc.catalog.validation._schema_extensions import known_extension_fields
from tslc.compiler_assets import load_default_tsl_grammar
from tslc.diagnostics import SourceLocation
from tslc.sources import SourceDocument
from tslc.syntax.parser import TslParser


def _diagnostics(text: str, *, backends: tuple[str, ...] = ("cpp", "rust")):
    document = SourceDocument(Path("catalog_validation_fixture.tsl"), text, "d", "tsl")
    parsed = TslParser(load_default_tsl_grammar()).parse((document,))
    assert parsed.diagnostics == (), parsed.diagnostics
    result = CatalogBuilder().build(parsed)
    assert result.catalog is not None
    return (*result.diagnostics, *validate_catalog(result.catalog, parsed, required_backends=backends))


def _target_family_catalog() -> TargetFamilyCatalog:
    return TargetFamilyCatalog(
        known_extension_families=frozenset({"scalar", "generic_like", "x86", "arm", "cuda"}),
        universal_extension_families=frozenset({"scalar", "generic_like"}),
        profile_families={
            "generic": ProfileFamilyCapability("generic"),
            "x86": ProfileFamilyCapability(
                "x86",
                frozenset({"x86"}),
                emulator_kinds=frozenset({"sde"}),
            ),
            "aarch64": ProfileFamilyCapability(
                "aarch64",
                frozenset({"arm"}),
                emulator_kinds=frozenset({"qemu-aarch64"}),
            ),
        },
    )


def _base_source(extra: str = "") -> str:
    return (
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "language rust:\n"
        '  s32 {type "i32"}\n'
        f"{extra}"
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        '          tsil "complete(data);"\n'
    )


def test_valid_tiny_catalog_has_no_validation_diagnostics() -> None:
    assert _diagnostics(_base_source()) == ()


def test_primitive_documentation_fields_are_accepted_and_promoted() -> None:
    source = _base_source().replace(
        "  impls:\n",
        '  brief_description "Identity operation."\n'
        '  detailed_description "Returns the input unchanged."\n'
        '  semantics """\n'
        "input: register data\n"
        "return data\n"
        '"""\n'
        "  impls:\n",
    )
    document = SourceDocument(Path("catalog_validation_fixture.tsl"), source, "d", "tsl")
    parsed = TslParser(load_default_tsl_grammar()).parse((document,))
    assert parsed.diagnostics == (), parsed.diagnostics
    result = CatalogBuilder().build(parsed)
    assert result.catalog is not None
    diagnostics = (
        *result.diagnostics,
        *validate_catalog(result.catalog, parsed, required_backends=("cpp", "rust")),
    )
    assert diagnostics == ()

    primitive = result.catalog.primitive("id")
    assert primitive is not None
    assert primitive.brief_description == "Identity operation."
    assert primitive.detailed_description == "Returns the input unchanged."
    assert "input: register data" in (primitive.semantics or "")
    assert "return data" in (primitive.semantics or "")


def test_duplicate_keys_are_diagnosed() -> None:
    diagnostics = _diagnostics(
        _base_source(
            "language cpp:\n"
            '  s32 {type "int"}\n'
        )
    )

    assert "TSL-CATALOG-DUPLICATE-BLOCK" in {d.code for d in diagnostics}


def test_unknown_fields_are_diagnosed() -> None:
    diagnostics = _diagnostics(
        _base_source(
            "extension generic:\n"
            '  extension_name "generic"\n'
            '  family "generic_like"\n'
            "  familly typo\n"
        )
    )

    diagnostic = next(d for d in diagnostics if d.code == "TSL-CATALOG-UNKNOWN-FIELD")
    assert "familly" in diagnostic.message
    assert diagnostic.location == SourceLocation(Path("catalog_validation_fixture.tsl"), 13, 3)


def test_unknown_extension_backend_metadata_fields_are_diagnosed() -> None:
    diagnostics = _diagnostics(
        _base_source(
            "extension generic:\n"
            '  extension_name "generic"\n'
            '  family "generic_like"\n'
            "  cpp:\n"
            "    supported true\n"
            '    test_suit_name "typo"\n'
        )
    )

    diagnostic = next(d for d in diagnostics if d.code == "TSL-CATALOG-UNKNOWN-FIELD")
    assert "test_suit_name" in diagnostic.message
    assert "extension backend cpp" in diagnostic.message


def test_extension_backend_field_names_follow_supported_backends() -> None:
    assert {"cpp", "rust"} <= known_extension_fields()
    assert "zig" in known_extension_fields(("zig",))
    assert "zig" not in known_extension_fields()


def test_scalable_cpp_extension_requires_runtime_lane_count() -> None:
    diagnostics = _diagnostics(
        _base_source(
            "extension sve_demo:\n"
            '  extension_name "sve_demo"\n'
            '  family "arm"\n'
            '  vector_bits "scalable"\n'
            "  cpp:\n"
            "    supported true\n"
        ),
        backends=("cpp",),
    )

    diagnostic = next(
        d
        for d in diagnostics
        if d.code == "TSL-CATALOG-MISSING-RUNTIME-LANE-COUNT"
    )
    assert "runtime_lane_count.cpp" in diagnostic.message


def test_invalid_enum_like_values_are_diagnosed() -> None:
    diagnostics = _diagnostics(
        "target_families:\n"
        "  known_extension_families [scalar]\n"
        "  universal_extension_families [scalar]\n"
        "  profile_families:\n"
        "    generic:\n"
        "      extension_families []\n"
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "nonsense"\n'
        "  mask_type_policy:\n"
        "    kind strange\n"
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "language rust:\n"
        '  s32 {type "i32"}\n'
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        '          tsil "complete(data);"\n'
    )

    messages = [d.message for d in diagnostics if d.code == "TSL-CATALOG-INVALID-ENUM"]
    assert any("family" in message for message in messages)
    assert any("mask_type_policy" in message for message in messages)


def test_target_family_data_makes_new_extension_family_additive() -> None:
    diagnostics = _diagnostics(
        "target_families:\n"
        "  known_extension_families [scalar, rvv]\n"
        "  universal_extension_families [scalar]\n"
        "  profile_families:\n"
        "    generic:\n"
        "      extension_families []\n"
        "    riscv:\n"
        "      extension_families [rvv]\n"
        "      sort_order 30\n"
        "      cpp_feature_flags false\n"
        '      cpp_target "riscv64-linux-gnu"\n'
        "      rust_target_features false\n"
        '      rust_target "riscv64gc-unknown-linux-gnu"\n'
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "extension rvv:\n"
        '  extension_name "rvv"\n'
        '  family "rvv"\n'
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "language rust:\n"
        '  s32 {type "i32"}\n'
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        '          tsil "complete(data);"\n'
    )

    assert "TSL-CATALOG-INVALID-ENUM" not in {d.code for d in diagnostics}


def test_target_family_typos_are_still_diagnosed() -> None:
    diagnostics = _diagnostics(
        "target_families:\n"
        "  known_extension_families [scalar, rvv]\n"
        "  universal_extension_families [scalar]\n"
        "  profile_families:\n"
        "    generic:\n"
        "      extension_families []\n"
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "extension typo:\n"
        '  extension_name "typo"\n'
        '  family "risc-v"\n'
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "language rust:\n"
        '  s32 {type "i32"}\n'
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        '          tsil "complete(data);"\n'
    )

    diagnostic = next(d for d in diagnostics if d.code == "TSL-CATALOG-INVALID-ENUM")
    assert "extension family 'risc-v'" in diagnostic.message
    assert "rvv" in diagnostic.message


def test_missing_backend_spellings_are_diagnosed() -> None:
    diagnostics = _diagnostics(
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "language cpp:\n"
        '  f32 {type "float"}\n'
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        '          tsil "complete(data);"\n',
        backends=("cpp",),
    )

    assert [d.code for d in diagnostics] == ["TSL-CATALOG-MISSING-TYPE-SPELLING"]
    assert "si32" in diagnostics[0].message


def test_bad_extension_inheritance_is_diagnosed() -> None:
    diagnostics = _diagnostics(
        _base_source(
            "extension child:\n"
            '  extension_name "child"\n'
            '  family "scalar"\n'
            "  inherits missing\n"
        )
    )

    assert "TSL-CATALOG-UNKNOWN-INHERITS" in {d.code for d in diagnostics}


def test_extension_inheritance_cycles_are_diagnosed() -> None:
    diagnostics = _diagnostics(
        "types:\n"
        "  ints {types [si32]}\n"
        "extension a:\n"
        '  extension_name "a"\n'
        "  inherits b\n"
        "extension b:\n"
        '  extension_name "b"\n'
        "  inherits a\n"
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "language rust:\n"
        '  s32 {type "i32"}\n'
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    a:\n"
        "      ints:\n"
        "        implementation:\n"
        '          tsil "complete(data);"\n'
    )

    assert "TSL-CATALOG-INHERITS-CYCLE" in {d.code for d in diagnostics}


def test_malformed_requires_shape_is_diagnosed() -> None:
    diagnostics = _diagnostics(
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "language rust:\n"
        '  s32 {type "i32"}\n'
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        requires:\n"
        "          scalar:\n"
        "            default nope\n"
        "        implementation:\n"
        '          tsil "complete(data);"\n'
    )

    diagnostic = next(d for d in diagnostics if d.code == "TSL-CATALOG-MALFORMED-REQUIRES")
    assert "flag list" in diagnostic.message


def test_malformed_call_body_region_is_diagnosed() -> None:
    diagnostics = _diagnostics(
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "language rust:\n"
        '  s32 {type "i32"}\n'
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        '          tsil "call<primitive=set_zero trailing>(data);"\n'
    )

    diagnostic = next(d for d in diagnostics if d.code == "TSL-BODY-BAD-CALL-SELECTOR")
    assert "malformed call selector" in diagnostic.message


def test_malformed_let_body_region_is_diagnosed() -> None:
    diagnostics = _diagnostics(
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "language rust:\n"
        '  s32 {type "i32"}\n'
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        '          tsil "let<type>(AliasOnly); complete(data);"\n'
    )

    diagnostic = next(d for d in diagnostics if d.code == "TSL-BODY-BAD-LET")
    assert "let<type>(Name, type-expression)" in diagnostic.message


def test_malformed_intrin_body_region_is_diagnosed() -> None:
    diagnostics = _diagnostics(
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "language rust:\n"
        '  s32 {type "i32"}\n'
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        '          tsil "complete(intrin<add, suffix=epi32>(data));"\n'
    )

    diagnostic = next(d for d in diagnostics if d.code == "TSL-BODY-BAD-INTRIN-SELECTOR")
    assert "build" in diagnostic.message


def test_query_region_selectors_are_diagnosed() -> None:
    diagnostics = _diagnostics(
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "language rust:\n"
        '  s32 {type "i32"}\n'
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        '          tsil "complete(cast<static>(type<generation>(base::in), value<backend>(uninit::array)));"\n'
    )

    messages = [
        diagnostic.message
        for diagnostic in diagnostics
        if diagnostic.code == "TSL-BODY-BAD-QUERY-SELECTOR"
    ]
    assert len(messages) == 2
    assert any("use `type(query)`" in message for message in messages)
    assert any("use `value(query)`" in message for message in messages)


@pytest.mark.parametrize(
    "body",
    [
        "complete(mask<set:1>(data, 0));",
        "complete(mask<set>(data, 0, true));",
        "complete(mask<lane_true>(data));",
        "complete(mask<all>(data));",
        "complete(mask<test, integral>(data, 0));",
        "complete(mask<test, imask>(data));",
    ],
)
def test_malformed_mask_body_region_is_diagnosed(body: str) -> None:
    diagnostics = _diagnostics(
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "language rust:\n"
        '  s32 {type "i32"}\n'
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        f'          tsil "{body}"\n'
    )

    diagnostic = next(d for d in diagnostics if d.code == "TSL-BODY-BAD-MASK-SELECTOR")
    assert "malformed mask selector" in diagnostic.message


@pytest.mark.parametrize(
    ("body", "keyword", "reason"),
    [
        ("call<primitive=set_zero(data);", "call", "unterminated selector"),
        ("call<primitive=set_zero>;", "call", "missing argument payload"),
        ("call<primitive=set_zero>(data;", "call", "unterminated argument payload"),
        (
            "if<generation>(value(type::is_integral)) complete(data);",
            "if",
            "missing block",
        ),
        (
            "switch<compile>(scale) { 1 { complete(data); } }",
            "switch",
            "malformed switch arms",
        ),
    ],
)
def test_malformed_tsil_region_shells_are_diagnosed(
    body: str, keyword: str, reason: str
) -> None:
    diagnostics = _diagnostics(
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "language rust:\n"
        '  s32 {type "i32"}\n'
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        f'          tsil "{body}"\n'
    )

    diagnostic = next(d for d in diagnostics if d.code == "TSL-BODY-MALFORMED-REGION")
    assert f"malformed TSIL region '{keyword}'" in diagnostic.message
    assert reason in diagnostic.message
    assert diagnostic.location is not None


def test_legacy_pointer_cast_shell_is_diagnosed() -> None:
    diagnostics = _diagnostics(
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "language rust:\n"
        '  s32 {type "i32"}\n'
        "prim<v:=v> id(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        '          tsil "complete(cast<reinterpret>(type(base::in) const *, data));"\n'
    )

    diagnostic = next(d for d in diagnostics if d.code == "TSL-BODY-BAD-CAST")
    assert "cast<reinterpret, type=ptr|const_ptr>" in diagnostic.message


def test_primitive_source_uses_explicit_pointer_cast_selectors() -> None:
    legacy_pointer_cast = re.compile(r"cast<reinterpret>\(\s*[^,]*\*,", re.S)
    offenders = [
        str(path)
        for path in Path("tsldata/primitives").rglob("*.tsl")
        if legacy_pointer_cast.search(path.read_text(encoding="utf-8"))
    ]

    assert offenders == []


@pytest.mark.parametrize(
    ("signature", "code"),
    [
        ("lanes<s>:=v", "TSL-CATALOG-LANE-LIST-RESULT"),
        ("v:=(lanes<>)", "TSL-CATALOG-LANE-LIST-EMPTY"),
        ("v:=(lanes<v>)", "TSL-CATALOG-LANE-LIST-ELEMENT"),
        ("v:=(lanes<lanes<s>>)", "TSL-CATALOG-LANE-LIST-NESTED"),
    ],
)
def test_lane_list_signature_validation_reports_rejected_shapes(
    signature: str, code: str
) -> None:
    diagnostics = _diagnostics(
        "types:\n"
        "  ints {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "language rust:\n"
        '  s32 {type "i32"}\n'
        f"prim<{signature}> id(values):\n"
        "  impls:\n"
        "    scalar:\n"
        "      ints:\n"
        "        implementation:\n"
        '          tsil "complete(values);"\n'
    )

    assert code in {diagnostic.code for diagnostic in diagnostics}


def test_machine_profile_validation_reports_shape_errors(tmp_path: Path) -> None:
    path = tmp_path / "machine_profiles.json"
    path.write_text(
        '{\n'
        '  "x86": [\n'
        '    {"name": "dup", "flags": "sse", "extra": true},\n'
        '    {"name": "dup", "flags": "avx"}\n'
        '  ],\n'
        '  "strange": [],\n'
        '  "generic": [{"name": "scalar", "flags": "NOSIMD-INVALID", "alternatives": []}]\n'
        '}\n',
        encoding="utf-8",
    )

    result = load_machine_profiles_checked(path, _target_family_catalog())

    codes = {diagnostic.code for diagnostic in result.diagnostics}
    assert {
        "TSL-PROFILE-DUPLICATE-NAME",
        "TSL-PROFILE-INVALID-FAMILY",
        "TSL-PROFILE-MALFORMED-ALTERNATIVES",
        "TSL-PROFILE-UNKNOWN-FIELD",
    } <= codes


def test_machine_profile_duplicate_json_keys_are_diagnosed(tmp_path: Path) -> None:
    path = tmp_path / "machine_profiles.json"
    path.write_text(
        '{"x86": [{"name": "first", "name": "second", "flags": "sse"}]}\n',
        encoding="utf-8",
    )

    result = load_machine_profiles_checked(path, _target_family_catalog())

    assert "TSL-PROFILE-DUPLICATE-KEY" in {d.code for d in result.diagnostics}


def test_machine_profile_cpp_flags_are_validated(tmp_path: Path) -> None:
    path = tmp_path / "machine_profiles.json"
    path.write_text(
        '{\n'
        '  "aarch64": [\n'
        '    {"name": "neon", "flags": "neon", "cpp_flags": []},\n'
        '    {"name": "bad", "flags": "sve", "cpp_flags": "-march=armv8-a+sve"}\n'
        '  ]\n'
        '}\n',
        encoding="utf-8",
    )

    result = load_machine_profiles_checked(path)

    assert result.profiles["neon"].cpp_flags == ()
    assert "TSL-PROFILE-MALFORMED-FIELD" in {d.code for d in result.diagnostics}


def test_machine_profile_emulator_metadata_is_validated(tmp_path: Path) -> None:
    path = tmp_path / "machine_profiles.json"
    path.write_text(
        '{\n'
        '  "x86": [\n'
        '    {"name": "avx2", "flags": "avx avx2", '
        '"emulator": {"kind": "sde", "profile": "-hsw"}},\n'
        '    {"name": "bad", "flags": "avx", "emulator": []}\n'
        '  ]\n'
        '}\n',
        encoding="utf-8",
    )

    result = load_machine_profiles_checked(path, _target_family_catalog())

    assert result.profiles["avx2"].emulator is not None
    assert result.profiles["avx2"].emulator.kind == "sde"
    assert result.profiles["avx2"].emulator.profile == "hsw"
    assert "TSL-PROFILE-MALFORMED-EMULATOR" in {d.code for d in result.diagnostics}


def test_machine_profile_emulator_kinds_come_from_target_families(tmp_path: Path) -> None:
    path = tmp_path / "machine_profiles.json"
    path.write_text(
        '{\n'
        '  "x86": [\n'
        '    {"name": "bad", "flags": "sse", '
        '"emulator": {"kind": "qemu-aarch64", "profile": "cortex-a76"}}\n'
        '  ]\n'
        '}\n',
        encoding="utf-8",
    )

    result = load_machine_profiles_checked(path, _target_family_catalog())

    diagnostic = next(
        d for d in result.diagnostics if d.code == "TSL-PROFILE-UNSUPPORTED-EMULATOR"
    )
    assert "declared for family 'x86'" in diagnostic.message
    assert "sde" in diagnostic.message
