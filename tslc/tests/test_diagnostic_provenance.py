"""Diagnostics preserve source locations after parser/catalog promotion."""

from __future__ import annotations

from pathlib import Path

from tslc.backend.translation import create_backend_dialect
from tslc.catalog.builder import CatalogBuildResult, CatalogBuilder
from tslc.catalog.machine_profiles import MachineProfile
from tslc.compiler_assets import load_default_tsl_grammar
from tslc.diagnostics import SourceLocation
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
    assert diagnostic.code == "TSL-LOWER-UNRESOLVED-QUERY-REGION"
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
