"""Diagnostics preserve source locations after parser/catalog promotion."""

from __future__ import annotations

import ast
from inspect import signature
from pathlib import Path

from tslc.backend.registry import create_backend_dialect
from tslc.catalog.builder import CatalogBuildResult, CatalogBuilder
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.validation import validate_catalog
from tslc.compiler_assets import load_default_tsl_grammar
from tslc.diagnostics import Diagnostic, SourceLocation
from tslc.lower.lowerer import Lowerer
from tslc.select.selector import Selector
from tslc.sources import SourceDocument
from tslc.syntax.parser import TslParser


_TARGET_FAMILIES = (
    "\n"
    "target_families:\n"
    "  known_extension_families [scalar, x86]\n"
    "  universal_extension_families [scalar]\n"
    "  profile_families:\n"
    "    generic:\n"
    "      extension_families []\n"
    "    x86:\n"
    "      extension_families [x86]\n"
)


def test_compiler_diagnostic_producers_use_full_spans() -> None:
    assert "location" not in signature(Diagnostic).parameters
    source_root = Path(__file__).resolve().parents[1] / "src" / "tslc"
    offenders: list[str] = []
    for path in sorted(source_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            diagnostic_call = (
                isinstance(node.func, ast.Name) and node.func.id == "Diagnostic"
            ) or (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "Diagnostic"
            )
            if not diagnostic_call:
                continue
            if any(keyword.arg == "location" for keyword in node.keywords):
                offenders.append(f"{path.relative_to(source_root)}:{node.lineno}")
    assert offenders == []


def _build(text: str, path: Path = Path("diagnostic_fixture.tsl")) -> CatalogBuildResult:
    document = SourceDocument(
        path=path,
        text=text + _TARGET_FAMILIES,
        digest="d",
        kind="tsl",
    )
    parsed = TslParser(load_default_tsl_grammar()).parse((document,))
    assert parsed.diagnostics == (), parsed.diagnostics
    return CatalogBuilder().build(parsed)


def _validate(text: str) -> tuple:
    path = Path("diagnostic_fixture.tsl")
    document = SourceDocument(
        path=path,
        text=text + _TARGET_FAMILIES,
        digest="d",
        kind="tsl",
    )
    parsed = TslParser(load_default_tsl_grammar()).parse((document,))
    assert parsed.diagnostics == (), parsed.diagnostics
    built = CatalogBuilder().build(parsed)
    assert built.catalog is not None
    return validate_catalog(built.catalog, parsed, required_backends=())


def test_catalog_params_diagnostic_has_source_location() -> None:
    result = _build(
        "prim<v:=(v,sImm)> shift(data, amount):\n"
        "  params:\n"
        "    nope:\n"
        "      type ui32\n"
        "  impls:\n"
        "    scalar:\n"
        "      si32:\n"
        "        implementation:\n"
        '          tsil "complete(data);"\n'
    )

    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-PARAMS-UNKNOWN-PARAM"
    assert diagnostic.location == SourceLocation(Path("diagnostic_fixture.tsl"), 3, 5)


def test_unknown_field_has_full_span_and_nearest_name_help() -> None:
    diagnostics = _validate(
        "extension scalar:\n"
        '  extensoin_name "scalar"\n'
        '  family "scalar"\n'
    )

    diagnostic = next(item for item in diagnostics if item.code == "TSL-CATALOG-UNKNOWN-FIELD")
    assert diagnostic.span is not None
    assert diagnostic.span.end_column > diagnostic.span.column
    assert diagnostic.help == "did you mean 'extension_name'?"


def test_duplicate_block_points_back_to_first_definition() -> None:
    diagnostics = _validate(
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
    )

    diagnostic = next(item for item in diagnostics if item.code == "TSL-CATALOG-DUPLICATE-BLOCK")
    assert len(diagnostic.related) == 1
    assert diagnostic.related[0].span.line == 1


def test_selector_ambiguity_warning_has_source_location() -> None:
    result = _build(
        "types:\n"
        "  si? {types [si32, si64]}\n"
        "  idqword {types [si32, ui32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "prim<v:=v> amb(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      si?:\n"
        "        implementation:\n"
        '          tsil "complete(data);"\n'
        "      idqword:\n"
        "        implementation:\n"
        '          tsil "complete(data);"\n'
    )
    assert result.catalog is not None

    selection = Selector().select_profile(
        result.catalog,
        MachineProfile("scalar", "generic", frozenset(), {}),
        "amb",
        ("si32",),
    )

    diagnostic = selection.diagnostics[0]
    assert diagnostic.code == "TSL-SELECT-AMBIGUOUS-SPECIFICITY"
    assert diagnostic.location == SourceLocation(Path("diagnostic_fixture.tsl"), 10, 7)


def test_lowerer_missing_complete_has_body_source_location() -> None:
    result = _build(
        "types:\n"
        "  si32 {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "  cpp:\n"
        "    supported true\n"
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "prim<v:=v> no_return(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      si32:\n"
        "        implementation:\n"
        '          tsil "data;"\n'
    )
    assert result.catalog is not None
    selection = Selector().select_profile(
        result.catalog,
        MachineProfile("scalar", "generic", frozenset(), {}),
        "no_return",
        ("si32",),
    )
    assert len(selection.selected) == 1

    lowered = Lowerer().lower(
        selection.selected[0],
        result.catalog,
        create_backend_dialect(result.catalog, "cpp"),
    )

    diagnostic = lowered.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-NO-COMPLETE"
    assert diagnostic.location == SourceLocation(Path("diagnostic_fixture.tsl"), 15, 17)


def test_lowerer_handler_diagnostic_has_region_source_location() -> None:
    result = _build(
        "types:\n"
        "  si32 {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "  cpp:\n"
        "    supported true\n"
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "prim<v:=v> bad_query(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      si32:\n"
        "        implementation:\n"
        '          tsil "complete(value(vector::unknown));"\n'
    )
    assert result.catalog is not None
    selection = Selector().select_profile(
        result.catalog,
        MachineProfile("scalar", "generic", frozenset(), {}),
        "bad_query",
        ("si32",),
    )
    assert len(selection.selected) == 1

    lowered = Lowerer().lower(
        selection.selected[0],
        result.catalog,
        create_backend_dialect(result.catalog, "cpp"),
    )

    diagnostic = lowered.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNRESOLVED-VALUE-QUERY"
    assert diagnostic.location == SourceLocation(Path("diagnostic_fixture.tsl"), 15, 26)


def test_intrin_build_unresolved_suffix_has_region_source_location() -> None:
    result = _build(
        "types:\n"
        "  si32 {types [si32]}\n"
        "extension avx2:\n"
        '  extension_name "avx2"\n'
        '  family "x86"\n'
        "  cpp:\n"
        "    supported true\n"
        "  intrinsic_compose:\n"
        "    prefix:\n"
        '      cpp "_mm256_"\n'
        "    suffix:\n"
        "      by_type:\n"
        '        si32 "epi32"\n'
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "prim<v:=v> bad_suffix(data):\n"
        "  impls:\n"
        "    avx2:\n"
        "      si32:\n"
        "        implementation:\n"
        '          tsil "complete(intrin<add, build['
        'suffix=base::signed_of(si?)]>(data));"\n'
    )
    assert result.catalog is not None
    selection = Selector().select_profile(
        result.catalog,
        MachineProfile("avx2", "x86", frozenset(), {}),
        "bad_suffix",
        ("si32",),
    )
    assert selection.diagnostics == ()
    assert len(selection.selected) == 1

    lowered = Lowerer().lower(
        selection.selected[0],
        result.catalog,
        create_backend_dialect(result.catalog, "cpp"),
    )

    assert lowered.specialization is None
    diagnostic = lowered.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-UNRESOLVED-SUFFIX"
    assert diagnostic.severity == "info"
    assert "base::signed_of(si?)" in diagnostic.message
    assert diagnostic.location == SourceLocation(Path("diagnostic_fixture.tsl"), 21, 26)
