"""The `tests:` block is promoted into the model and structurally validated."""

from __future__ import annotations

from pathlib import Path

from tslc.catalog.model import Catalog
from tslc.catalog.validation.schema_validation import validate_parsed_documents
from tslc.diagnostics import Diagnostic
from tslc.sources import SourceDocument
from tslc.syntax.parser import TslParser


def _first(catalog: Catalog, name: str, *, masked: bool):
    for primitive in catalog.primitives_named(name, unmasked=False):
        if ("mask" in primitive.attributes) == masked:
            return primitive
    raise AssertionError(f"no {'masked' if masked else 'unmasked'} primitive named {name!r}")


def test_add_tests_are_promoted(catalog: Catalog) -> None:
    add = _first(catalog, "add", masked=False)
    assert add.tests, "add should carry value-test cases"
    basic = next(t for t in add.tests if t.name == "add_i32_basic")
    assert basic.type_tag == "si32"
    assert basic.lanes == 8
    assert basic.lane_set == "lanes_i32"
    assert [a.kind for a in basic.inputs] == ["vector", "vector"]
    assert basic.inputs[0].values == ("1", "2", "3", "4", "5", "6", "7", "8")
    assert basic.expected == ("9", "9", "9", "9", "9", "9", "9", "9")


def test_masked_add_routes_mask_arg(catalog: Catalog) -> None:
    masked = _first(catalog, "add", masked=True)
    case = next(t for t in masked.tests if t.name.startswith("add_maskz_i32"))
    # The mask bitmask is captured as a distinct `mask` arg (a bare integer token), not a vector.
    kinds = [a.kind for a in case.inputs]
    assert "mask" in kinds
    mask_arg = next(a for a in case.inputs if a.kind == "mask")
    assert mask_arg.mask_bits is not None


def test_equal_mask_result_expected_is_per_lane(catalog: Catalog) -> None:
    equal = _first(catalog, "equal", masked=False)
    basic = next(t for t in equal.tests if t.name == "equal_u32_basic")
    # A mask result is authored per-lane as the all-ones/zero lane pattern.
    assert basic.expected[0] == "4294967295"
    assert basic.expected[1] == "0"


def test_conflict_cross_lane_tests_present(catalog: Catalog) -> None:
    conflict = _first(catalog, "conflict", masked=False)
    edge = next(t for t in conflict.tests if t.name == "conflict_ui8_edge")
    assert edge.lanes == 64  # width-pinned to the 512-bit specialization
    assert len(edge.inputs[0].values) == 64


def test_store_test_carries_offset_and_attrs(catalog: Catalog) -> None:
    store = _first(catalog, "store", masked=False)
    misaligned = next(t for t in store.tests if t.name == "storeu_u32_misaligned")
    assert misaligned.offset == 1
    assert misaligned.attrs.get("aligned") == "false"
    # The store buffer expected models offset+lanes, so it exceeds the lane count.
    assert len(misaligned.expected) > misaligned.lanes


def test_extension_test_config_is_promoted(catalog: Catalog) -> None:
    assert catalog.extensions["avx512"].default_test_target is True
    assert catalog.extensions["scalar"].default_test_target is False
    assert catalog.extensions["generic"].test_sizes_bits == (128,)
    assert "scatter" in catalog.extensions["avx2"].test_filter_exclude_templates


# --- structural validation ---------------------------------------------------


def _diagnostics(test_block: str) -> set[str]:
    source = (
        "prim<v:=v> id(data):\n"
        f"{test_block}"
        "  impls:\n"
        "    scalar:\n"
        "      anyint:\n"
        "        implementation:\n"
        '          tsil "emit_return(data);"\n'
    )
    document = SourceDocument(Path("tests_fixture.tsl"), source, "d", "tsl")
    parsed = TslParser().parse((document,))
    assert parsed.diagnostics == (), parsed.diagnostics
    diagnostics: list[Diagnostic] = []
    validate_parsed_documents(parsed, diagnostics)
    return {d.code for d in diagnostics}


def test_unknown_test_field_is_diagnosed() -> None:
    codes = _diagnostics(
        "  tests:\n"
        '    - {test_name "t", type "si32", bogus "x", '
        "case {inputs [[1]], expected [1]}}\n"
    )
    assert "TSL-CATALOG-UNKNOWN-TEST-FIELD" in codes


def test_missing_required_test_field_is_diagnosed() -> None:
    codes = _diagnostics(
        '  tests:\n    - {test_name "t", type "si32"}\n'
    )
    assert "TSL-CATALOG-TEST-MISSING-FIELD" in codes


def test_non_positive_lanes_is_diagnosed() -> None:
    codes = _diagnostics(
        "  tests:\n"
        '    - {test_name "t", type "si32", lanes 0, '
        "case {inputs [[1]], expected [1]}}\n"
    )
    assert "TSL-CATALOG-TEST-BAD-LANES" in codes


def test_well_formed_tests_have_no_diagnostics() -> None:
    codes = _diagnostics(
        "  tests:\n"
        '    - {test_name "t", type "si32", lanes 4, '
        "case {inputs [[1, 2, 3, 4]], expected [1, 2, 3, 4]}}\n"
    )
    assert not {c for c in codes if "TEST" in c}
