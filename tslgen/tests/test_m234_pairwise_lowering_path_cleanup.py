from __future__ import annotations

from dataclasses import is_dataclass
from hashlib import sha256
from pathlib import Path

from tslgen.analysis.selection import Selector, Target
from tslgen.domain.catalog import LowerableDirective, NamedPrimitiveReference
from tslgen.io.sources import SourceDocument
from tslgen.lowering import LoweredBinaryOperationExpression, Lowerer
from tslgen.lowering.source_body_fragments import (
    PrimitiveCallKeywordDirective,
    PrimitiveCallKeywordDirectiveExtractionResult,
    extract_primitive_call_directives,
    lower_source_body_fragments,
    payload_tokens_from_fragment_sequence,
)
from tslgen.pipeline import catalog_builder
from tslgen.pipeline.catalog_builder import CatalogBuilder
from tslgen.syntax.parser import TslParser
from tslgen.syntax.source_body_regions import SourceBodyKeyword, SourceBodyText


def test_m234_primitive_call_fragment_values_are_frozen_slotted_dataclasses() -> None:
    classes = (
        PrimitiveCallKeywordDirective,
        PrimitiveCallKeywordDirectiveExtractionResult,
    )

    for value_type in classes:
        assert is_dataclass(value_type)
        assert value_type.__dataclass_params__.frozen
        assert "__dict__" not in value_type.__slots__


def test_m234_extracts_call_fragments_without_parent_context_special_cases() -> None:
    result = _lower(
        "emit_return(call<primitive=sub[Vec]>(left, right));\n"
        "if<generation>(cond) {\n"
        "  call<primitive=store>(ptr, value);\n"
        "}"
    )

    extraction = extract_primitive_call_directives(result.sequence)

    assert result.diagnostics == ()
    assert extraction.diagnostics == ()
    assert tuple(
        directive.directive.primitive_call.selector.source_text
        for directive in extraction.directives
        if directive.directive.primitive_call is not None
    ) == ("sub[Vec]", "store")
    assert tuple(directive.fragment.keyword for directive in extraction.directives) == (
        SourceBodyKeyword.CALL,
        SourceBodyKeyword.CALL,
    )


def test_m234_emit_return_payload_tokens_are_built_from_recursive_fragments() -> None:
    result = _lower("emit_return(call<primitive=sub[Vec]>(left, right));")
    emit_return = result.sequence.keyword_fragments[0]
    assert emit_return.payload_fragments is not None

    payload_tokens = payload_tokens_from_fragment_sequence(
        emit_return.payload_fragments,
    )

    assert len(payload_tokens) == 1
    token = payload_tokens[0]
    assert isinstance(token, LowerableDirective)
    assert token.name == "call"
    assert token.primitive_call is not None
    target = token.primitive_call.selector.target
    assert isinstance(target, NamedPrimitiveReference)
    assert target.name == "sub"
    assert token.primitive_call.selector.specialization == "Vec"
    assert tuple(argument.text for argument in token.primitive_call.arguments) == (
        "left",
        "right",
    )


def test_m234_catalog_emit_return_call_payload_uses_recursive_fragment_tokens(
    tmp_path: Path,
) -> None:
    catalog = _catalog_from_source(
        tmp_path,
        "emit_return(call<primitive=sub[Vec]>(left, right));",
    )
    primitive = catalog.primitives[0]
    body_token = primitive.implementations[0].body.tokens[0]

    assert isinstance(body_token, LowerableDirective)
    assert body_token.name == "emit_return"
    assert len(body_token.payload_tokens) == 1
    payload_token = body_token.payload_tokens[0]
    assert isinstance(payload_token, LowerableDirective)
    assert payload_token.primitive_call is not None
    target = payload_token.primitive_call.selector.target
    assert isinstance(target, NamedPrimitiveReference)
    assert target.name == "sub"


def test_m234_exact_add_call_payload_still_lowers_to_add_operation(
    tmp_path: Path,
) -> None:
    catalog = _catalog_from_source(
        tmp_path,
        "emit_return(call<primitive=add>(left, right));",
    )
    selected = Selector().select(
        catalog,
        Target(
            backend="cpp",
            primitive_name="add",
            extension="scalar",
            type_tag="si32",
        ),
    ).selected[0]

    result = Lowerer().lower(selected, catalog=catalog)

    assert result.diagnostics == ()
    assert result.function is not None
    assert isinstance(
        result.function.body.return_statement.expression,
        LoweredBinaryOperationExpression,
    )


def test_m234_pairwise_helpers_are_not_production_extension_points() -> None:
    forbidden_names = (
        "_classify_emit_return_payload_tokens",
        "_classify_emit_return_payload_token",
        "_primitive_call_expression_result_from_exact_emit_return_body",
        "EmitReturnCall",
        "EmitReturnIntrinCompose",
        "ReturnPayloadCall",
    )
    production_names = (
        *dir(catalog_builder),
        *dir(__import__("tslgen.lowering.lowerer", fromlist=["*"])),
        *dir(__import__("tslgen.lowering.source_body_fragments", fromlist=["*"])),
    )

    assert not any(
        forbidden in name
        for name in production_names
        for forbidden in forbidden_names
    )


def _lower(text: str):
    return lower_source_body_fragments(
        SourceBodyText(
            path=Path("fixture.tsl"),
            line=1,
            column=1,
            text=text,
        )
    )


def _catalog_from_source(tmp_path: Path, body_payload: str):
    source = _source_document(
        tmp_path,
        "current_add.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                '    tsil """',
                f"      {body_payload}",
                '    """',
            )
        ),
    )
    parse_result = TslParser().parse((source,))
    assert parse_result.diagnostics == ()
    catalog_result = CatalogBuilder().build(parse_result.documents)
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    return catalog_result.catalog


def _source_document(tmp_path: Path, name: str, text: str) -> SourceDocument:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return SourceDocument(
        path=path,
        text=text,
        digest=sha256(text.encode("utf-8")).hexdigest(),
        kind="tsl",
    )
