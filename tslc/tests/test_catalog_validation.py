"""Catalog/profile validation catches source-data shape errors before lowering."""

from __future__ import annotations

from pathlib import Path

import pytest

from tslc.catalog.builder import CatalogBuilder
from tslc.catalog.machine_profiles import load_machine_profiles_checked
from tslc.catalog.validation import validate_catalog
from tslc.diagnostics import SourceLocation
from tslc.sources import SourceDocument
from tslc.syntax.parser import TslParser


def _diagnostics(text: str, *, backends: tuple[str, ...] = ("cpp", "rust")):
    document = SourceDocument(Path("catalog_validation_fixture.tsl"), text, "d", "tsl")
    parsed = TslParser().parse((document,))
    assert parsed.diagnostics == (), parsed.diagnostics
    result = CatalogBuilder().build(parsed)
    assert result.catalog is not None
    return (*result.diagnostics, *validate_catalog(result.catalog, parsed, required_backends=backends))


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


def test_invalid_enum_like_values_are_diagnosed() -> None:
    diagnostics = _diagnostics(
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

    result = load_machine_profiles_checked(path)

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

    result = load_machine_profiles_checked(path)

    assert "TSL-PROFILE-DUPLICATE-KEY" in {d.code for d in result.diagnostics}


def test_machine_profile_sde_metadata_is_validated(tmp_path: Path) -> None:
    path = tmp_path / "machine_profiles.json"
    path.write_text(
        '{\n'
        '  "x86": [\n'
        '    {"name": "avx2", "flags": "avx avx2", "sde": "-hsw"},\n'
        '    {"name": "bad", "flags": "avx", "sde": []}\n'
        '  ]\n'
        '}\n',
        encoding="utf-8",
    )

    result = load_machine_profiles_checked(path)

    assert result.profiles["avx2"].sde == "hsw"
    assert "TSL-PROFILE-MALFORMED-SDE" in {d.code for d in result.diagnostics}
