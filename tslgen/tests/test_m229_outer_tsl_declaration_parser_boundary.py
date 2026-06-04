from __future__ import annotations

from dataclasses import is_dataclass
from hashlib import sha256
from importlib import resources
from pathlib import Path

from tslgen.io.sources import SourceDocument
from tslgen.syntax.outer_ast import (
    ParsedImplementationBodyEnvelope,
    ParsedOuterTslDocument,
    ParsedPrimitiveDeclaration,
)
from tslgen.syntax.outer_parser import OuterTslParser


_REPO_ROOT = Path(__file__).resolve().parents[2]
_TSLDATA_ROOT = _REPO_ROOT / "tsldata"


def test_m229_lark_package_data_is_declared_and_loadable() -> None:
    grammar = resources.files("tslgen.syntax.grammar").joinpath("tsl_data.lark")

    assert grammar.is_file()
    assert "primitive_block" in grammar.read_text()


def test_m229_parses_all_current_outer_tsl_declarations() -> None:
    result = OuterTslParser().parse(_all_tsldata_documents())

    assert result.diagnostics == ()
    assert len(result.documents) == 41
    assert sum(len(document.declarations) for document in result.documents) == 250
    assert sum(len(document.primitives) for document in result.documents) == 140
    assert sum(
        1
        for document in result.documents
        for field in document.fields
        if field.kind == "description"
    ) == 15
    assert _block_counts(result.documents) == {
        "extension": 12,
        "flags": 1,
        "language": 3,
        "lane_set": 6,
        "template": 69,
        "translation": 3,
        "types": 1,
    }


def test_m229_fundamental_add_reaches_raw_tsil_body_envelopes() -> None:
    result = OuterTslParser().parse(
        (
            _source_document(
                _TSLDATA_ROOT / "primitives" / "arithmetic" / "fundamental.tsl"
            ),
        )
    )

    assert result.diagnostics == ()
    add = result.documents[0].primitives[0]
    assert add.name == "add"
    assert add.signature == "v:=(v,v)"
    assert add.parameters == ("left", "right")
    assert add.attributes == ()
    assert tuple(field.field.key.text for field in add.fields) == (
        "brief_description",
        "operation",
        "tests",
        "impls",
    )

    avx2_integer = _body(add, ("avx2", "?i?"))
    assert avx2_integer.quote_form == "multiline"
    assert "intrin_compose<" in avx2_integer.payload_text
    assert "emit_return(" in avx2_integer.payload_text
    assert avx2_integer.envelope_source.line == 69
    assert avx2_integer.payload_source.line == 69


def test_m229_real_primitive_shapes_cover_attrs_and_preserved_fields() -> None:
    repr_change = OuterTslParser().parse(
        (
            _source_document(
                _TSLDATA_ROOT / "primitives" / "conversion" / "repr_change.tsl"
            ),
        )
    )
    shifts = OuterTslParser().parse(
        (
            _source_document(
                _TSLDATA_ROOT / "primitives" / "bitwise" / "shifts.tsl"
            ),
        )
    )
    load = OuterTslParser().parse(
        (
            _source_document(
                _TSLDATA_ROOT / "primitives" / "load_store" / "load.tsl"
            ),
        )
    )

    assert repr_change.diagnostics == ()
    assert shifts.diagnostics == ()
    assert load.diagnostics == ()

    convert_up = _primitive(repr_change.documents[0], "convert_up")
    assert tuple((attr.key.text, attr.value.text) for attr in convert_up.attributes) == (
        ("cast", "convert"),
        ("direction", "up"),
    )
    assert convert_up.fields_by_name("return_type")[0].kind == "return_type"
    assert ("sse", "?i8", "ToBase", "?i16") in {
        envelope.selector_path for envelope in convert_up.body_envelopes
    }

    shift_left = shifts.documents[0].primitives[0]
    assert shift_left.fields_by_name("sImm_type")[0].kind == "simm_type"
    assert all("override" not in envelope.selector_path for envelope in shift_left.body_envelopes)

    load_mask = _primitive(load.documents[0], "load_mask")
    assert tuple((attr.key.text, attr.value.text) for attr in load_mask.attributes) == (
        ("aligned", "*"),
        ("packed", "*"),
    )
    assert load_mask.fields_by_name("param_types")[0].kind == "preserved"


def test_m229_primitive_child_fields_are_order_insensitive(tmp_path: Path) -> None:
    result = OuterTslParser().parse(
        (
            _inline_document(
                tmp_path,
                "\n".join(
                    (
                        "prim<v:=(v,v)> add(left, right):",
                        "  impls:",
                        "    scalar:",
                        "      arith:",
                        "        implementation:",
                        '          tsil "emit_return(left + right);"',
                        "        requires []",
                        '  operation "source operation text"',
                        '  brief_description "brief text"',
                        "  generic_params:",
                        "    Index {kind imm, default 0}",
                        "  return_type:",
                        "    base ResultBase",
                        "",
                    )
                ),
            ),
        )
    )

    assert result.diagnostics == ()
    primitive = result.documents[0].primitives[0]
    assert tuple(field.field.key.text for field in primitive.fields) == (
        "impls",
        "operation",
        "brief_description",
        "generic_params",
        "return_type",
    )
    assert primitive.fields_by_name("brief_description")[0].kind == "brief_description"
    assert primitive.fields_by_name("operation")[0].kind == "operation"
    assert primitive.fields_by_name("generic_params")[0].kind == "generic_params"
    assert primitive.fields_by_name("return_type")[0].kind == "return_type"
    assert _body(primitive, ("scalar", "arith")).quote_form == "inline"


def test_m229_inline_tsil_body_payload_text_preserves_escaped_source() -> None:
    result = OuterTslParser().parse(
        (
            _source_document(
                _TSLDATA_ROOT / "primitives" / "conversion" / "cast.tsl"
            ),
        )
    )

    assert result.diagnostics == ()
    reinterpret = result.documents[0].primitives[0]
    body = _body(reinterpret, ("[avx512, avx2, sse]", "f?", "ToBase", "f?"))
    assert body.quote_form == "inline"
    assert 'infix_sep=\\"\\"' in body.payload_text
    assert body.payload_text == body.payload_source.text


def test_m229_multiline_metadata_string_does_not_create_top_level_declarations(
    tmp_path: Path,
) -> None:
    result = OuterTslParser().parse(
        (
            _inline_document(
                tmp_path,
                "\n".join(
                    (
                        "translation cpp:",
                        "  preamble \"\"\"",
                        "prim<v:=(v,v)> fake(left, right):",
                        "  impls:",
                        "    scalar:",
                        "      arith:",
                        '        tsil "not an implementation body"',
                        "  \"\"\"",
                        "",
                    )
                ),
            ),
        )
    )

    assert result.diagnostics == ()
    document = result.documents[0]
    assert document.primitives == ()
    assert len(document.blocks) == 1
    assert document.blocks[0].kind == "translation"
    assert document.blocks[0].fields[0].key.text == "preamble"


def test_m229_malformed_outer_tsl_reports_diagnostic(tmp_path: Path) -> None:
    result = OuterTslParser().parse(
        (
            _inline_document(
                tmp_path,
                "\n".join(
                    (
                        "prim<v:=(v,v)> broken(left, right):",
                        "  impls:",
                        "    scalar:",
                        "      arith:",
                        "        implementation:",
                        '          tsil "missing closing primitive block"',
                        "  ]",
                        "",
                    )
                ),
            ),
        )
    )

    assert result.documents == ()
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].code == "TSL-OUTER-PARSE-UNSUPPORTED-FORM"
    assert result.diagnostics[0].location is not None


def test_m229_public_values_are_frozen_slotted_dataclasses() -> None:
    classes = (
        ParsedOuterTslDocument,
        ParsedPrimitiveDeclaration,
        ParsedImplementationBodyEnvelope,
    )

    for value_type in classes:
        assert is_dataclass(value_type)
        assert value_type.__dataclass_params__.frozen
        assert "__dict__" not in value_type.__slots__


def _all_tsldata_documents() -> tuple[SourceDocument, ...]:
    return tuple(_source_document(path) for path in sorted(_TSLDATA_ROOT.rglob("*.tsl")))


def _source_document(path: Path) -> SourceDocument:
    text = path.read_text(encoding="utf-8")
    return SourceDocument(
        path=path.resolve(),
        text=text,
        digest=sha256(text.encode("utf-8")).hexdigest(),
        kind="tsl",
    )


def _inline_document(tmp_path: Path, text: str) -> SourceDocument:
    path = tmp_path / "fixture.tsl"
    return SourceDocument(
        path=path,
        text=text,
        digest=sha256(text.encode("utf-8")).hexdigest(),
        kind="tsl",
    )


def _block_counts(documents: tuple[ParsedOuterTslDocument, ...]) -> dict[str, int]:
    return {
        kind: sum(1 for document in documents for block in document.blocks if block.kind == kind)
        for kind in (
            "extension",
            "flags",
            "language",
            "lane_set",
            "template",
            "translation",
            "types",
        )
    }


def _primitive(
    document: ParsedOuterTslDocument,
    name: str,
) -> ParsedPrimitiveDeclaration:
    return next(primitive for primitive in document.primitives if primitive.name == name)


def _body(
    primitive: ParsedPrimitiveDeclaration,
    selector_path: tuple[str, ...],
) -> ParsedImplementationBodyEnvelope:
    return next(
        envelope
        for envelope in primitive.body_envelopes
        if envelope.selector_path == selector_path
    )
