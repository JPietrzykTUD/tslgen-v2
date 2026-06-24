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
    basic = next(t for t in add.tests if t.name == "add_si32_basic")
    assert basic.type_tag == "si32"
    assert basic.tags == ("basic",)
    assert basic.lanes == 8
    assert [a.kind for a in basic.inputs] == ["vector", "vector"]
    assert basic.inputs[0].values == ("1", "2", "3", "4", "5", "6", "7", "8")
    assert basic.expected == ("9", "9", "9", "9", "9", "9", "9", "9")


def test_masked_add_routes_mask_arg(catalog: Catalog) -> None:
    masked = _first(catalog, "add", masked=True)
    case = next(t for t in masked.tests if t.name == "add_si32_maskz_basic")
    # The mask bitmask is captured as a distinct `mask` arg (a bare integer token), not a vector.
    kinds = [a.kind for a in case.inputs]
    assert "mask" in kinds
    mask_arg = next(a for a in case.inputs if a.kind == "mask")
    assert mask_arg.mask_bits is not None


def test_scalar_and_compile_test_fields_are_promoted(catalog: Catalog) -> None:
    shift = _first(catalog, "shift_right_imask", masked=False)
    case = next(t for t in shift.tests if t.name == "shift_right_imask_ui32_basic")
    assert case.role == "value"
    assert [arg.kind for arg in case.inputs] == ["mask", "scalar"]
    assert case.inputs[0].mask_bits == "240"
    assert case.inputs[1].scalar == "4"

    undef = _first(catalog, "set_undef", masked=False)
    compile_case = next(t for t in undef.tests if t.role == "compile")
    assert compile_case.name == "set_undef_si32_compile"
    assert compile_case.lanes == 4


def test_flat_ptr_plus_test_input_is_promoted_as_buffer_vector(catalog: Catalog) -> None:
    load_convert = _first(catalog, "load_convert_up", masked=False)
    case = next(t for t in load_convert.tests if t.name == "load_convert_up_ui8_avx2_to_ui16_basic")
    assert len(case.inputs) == 1
    assert case.inputs[0].kind == "vector"
    assert case.inputs[0].values[:4] == ("1", "2", "3", "4")


def test_equal_mask_result_expected_is_per_lane(catalog: Catalog) -> None:
    equal = _first(catalog, "equal", masked=False)
    basic = next(t for t in equal.tests if t.name == "equal_ui32_basic")
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
    misaligned = next(t for t in store.tests if t.name == "store_ui32_aligned_false_misaligned")
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
        '          tsil "complete(data);"\n'
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
        '    - {tags [basic], type "si32", bogus "x", '
        "case {inputs [[1]], expected [1]}}\n"
    )
    assert "TSL-CATALOG-UNKNOWN-TEST-FIELD" in codes


def test_missing_required_test_field_is_diagnosed() -> None:
    codes = _diagnostics(
        '  tests:\n    - {type "si32", case {inputs [[1]], expected [1]}}\n'
    )
    assert "TSL-CATALOG-TEST-MISSING-FIELD" in codes


def test_non_positive_lane_count_is_diagnosed() -> None:
    codes = _diagnostics(
        "  tests:\n"
        '    - {tags [basic], type "si32", lane_count 0, '
        "case {inputs [[1]], expected [1]}}\n"
    )
    assert "TSL-CATALOG-TEST-BAD-LANE-COUNT" in codes


def test_unknown_test_role_is_diagnosed() -> None:
    codes = _diagnostics(
        "  tests:\n"
        '    - {role "runtime", tags [basic], type "si32", '
        "case {inputs [[1]], expected [1]}}\n"
    )
    assert "TSL-CATALOG-INVALID-ENUM" in codes


def test_well_formed_tests_have_no_diagnostics() -> None:
    codes = _diagnostics(
        "  tests:\n"
        '    - {tags [basic], type "si32", '
        "case {inputs [[1, 2, 3, 4]], expected [1, 2, 3, 4]}}\n"
    )
    assert not {c for c in codes if "TEST" in c}
