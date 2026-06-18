"""Diagnostics preserve source locations after parser/catalog promotion."""

from __future__ import annotations

from pathlib import Path

from tslc.backend.translation import create_backend_dialect
from tslc.catalog.builder import CatalogBuildResult, CatalogBuilder
from tslc.catalog.machine_profiles import MachineProfile
from tslc.diagnostics import SourceLocation
from tslc.lower.lowerer import Lowerer
from tslc.select.selector import Selector
from tslc.sources import SourceDocument
from tslc.syntax.parser import TslParser


def _build(text: str, path: Path = Path("diagnostic_fixture.tsl")) -> CatalogBuildResult:
    document = SourceDocument(path=path, text=text, digest="d", kind="tsl")
    parsed = TslParser().parse((document,))
    assert parsed.diagnostics == (), parsed.diagnostics
    return CatalogBuilder().build(parsed)


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
        '          tsil "emit_return(data);"\n'
    )

    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-PARAMS-UNKNOWN-PARAM"
    assert diagnostic.location == SourceLocation(Path("diagnostic_fixture.tsl"), 3, 5)


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
        '          tsil "emit_return(data);"\n'
        "      idqword:\n"
        "        implementation:\n"
        '          tsil "emit_return(data);"\n'
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


def test_lowerer_missing_emit_return_has_body_source_location() -> None:
    result = _build(
        "types:\n"
        "  si32 {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
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
    assert diagnostic.code == "TSL-LOWER-NO-EMIT-RETURN"
    assert diagnostic.location == SourceLocation(Path("diagnostic_fixture.tsl"), 13, 17)


def test_lowerer_handler_diagnostic_has_region_source_location() -> None:
    result = _build(
        "types:\n"
        "  si32 {types [si32]}\n"
        "extension scalar:\n"
        '  extension_name "scalar"\n'
        '  family "scalar"\n'
        "language cpp:\n"
        '  s32 {type "int32_t"}\n'
        "prim<v:=v> bad_query(data):\n"
        "  impls:\n"
        "    scalar:\n"
        "      si32:\n"
        "        implementation:\n"
        '          tsil "emit_return(value<generation>(vector::unknown));"\n'
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
    assert diagnostic.code == "TSL-LOWER-UNRESOLVED-QUERY-REGION"
    assert diagnostic.location == SourceLocation(Path("diagnostic_fixture.tsl"), 13, 29)
