"""The `params:` block promotes per-name `sImm` immediate metadata (type, value_range,
per-language dispatch), and diagnoses entries that don't name an `sImm` parameter."""

from __future__ import annotations

from pathlib import Path

from tslc.catalog.builder import CatalogBuilder
from tslc.catalog.model import Catalog
from tslc.sources import SourceDocument
from tslc.syntax.parser import TslParser


def _build(text: str):
    doc = SourceDocument(path=Path("inline.tsl"), text=text, digest="d", kind="tsl")
    parsed = TslParser().parse((doc,))
    assert parsed.diagnostics == (), parsed.diagnostics
    return CatalogBuilder().build(parsed)


def test_shift_right_immediate_params(catalog: Catalog) -> None:
    # shifts declare type, a symbolic value_range, and the literal_match Rust bridge.
    shift_right = catalog.primitive("shift_right")
    assert shift_right is not None
    param = shift_right.immediate_param("shift")
    assert param is not None
    assert param.type_tag == "ui32"
    assert param.value_range == (0, "base_bit_width(data)", False)
    assert param.dispatch_for("rust") == "literal_match"
    assert param.dispatch_for("cpp") is None  # C++ stays positional


def test_extract_index_is_si32_positional(catalog: Catalog) -> None:
    # extract's lane index is uniform `i32` -> just a type, no range, no bridge.
    extract = catalog.primitive("extract")
    assert extract is not None
    param = extract.immediate_param("index")
    assert param is not None
    assert param.type_tag == "si32"
    assert param.value_range is None
    assert param.dispatch == ()


def test_mul_imm_has_no_params_block(catalog: Catalog) -> None:
    # A primitive with an `sImm` but no `params:` carries no metadata (lowerer defaults ui32).
    mul_imm = catalog.primitive("mul_imm")
    assert mul_imm is not None
    assert mul_imm.immediate_params == ()


def test_params_on_non_immediate_diagnoses() -> None:
    result = _build(
        "prim<v:=(v,v)> foo(left, right):\n"
        '  brief_description "x"\n'
        "  params:\n"
        "    left:\n"
        "      type ui32\n"
        "  impls:\n"
        "    scalar:\n"
        "      arith:\n"
        "        implementation:\n"
        '          tsil "emit_return(left + right);"\n'
    )
    codes = {d.code for d in result.diagnostics}
    assert "TSL-PARAMS-NOT-IMMEDIATE" in codes, result.diagnostics


def test_params_unknown_param_diagnoses() -> None:
    result = _build(
        "prim<v:=(v,sImm)> foo(data, shift):\n"
        '  brief_description "x"\n'
        "  params:\n"
        "    nope:\n"
        "      type ui32\n"
        "  impls:\n"
        "    scalar:\n"
        "      arith:\n"
        "        implementation:\n"
        '          tsil "emit_return(data << shift);"\n'
    )
    codes = {d.code for d in result.diagnostics}
    assert "TSL-PARAMS-UNKNOWN-PARAM" in codes, result.diagnostics
