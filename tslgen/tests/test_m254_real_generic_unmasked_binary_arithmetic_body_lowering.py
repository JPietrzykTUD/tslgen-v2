from __future__ import annotations

import ast
from hashlib import sha256
from pathlib import Path

from tslgen.domain.catalog import SelfPrimitiveReference
from tslgen.io.sources import SourceDocument
from tslgen.lowering.source_body_fragments import (
    KeywordRegionFragment,
    RawSourceFragment,
    extract_primitive_call_directives,
    lower_source_body_fragments,
)
from tslgen.syntax.outer_ast import (
    ParsedImplementationBodyEnvelope,
    ParsedPrimitiveDeclaration,
)
from tslgen.syntax.outer_parser import OuterTslParser
from tslgen.syntax.source_body_regions import SourceBodyKeyword, SourceBodyText


_REPO_ROOT = Path(__file__).resolve().parents[2]
_FUNDAMENTAL_PATH = (
    _REPO_ROOT / "tsldata" / "primitives" / "arithmetic" / "fundamental.tsl"
)
_SOURCE_BODY_REGIONS_PATH = (
    _REPO_ROOT / "tslgen" / "src" / "tslgen" / "syntax" / "source_body_regions.py"
)
_SOURCE_BODY_FRAGMENTS_PATH = (
    _REPO_ROOT / "tslgen" / "src" / "tslgen" / "lowering" / "source_body_fragments.py"
)


def test_m254_real_generic_add_sub_body_recursively_lowers_selected_islands() -> None:
    for primitive_name, envelope in _real_generic_add_sub_envelopes():
        result = lower_source_body_fragments(SourceBodyText.from_envelope(envelope))

        assert result.diagnostics == (), primitive_name
        assert _root_head_names(result.sequence.keyword_fragments) == (
            "var",
            "loop",
            "loop",
            "emit_return",
        )

        init_register, unroll, loop, emit_return = result.sequence.keyword_fragments
        assert init_register.keyword is SourceBodyKeyword.VAR
        assert init_register.source_region.selector is not None
        assert init_register.source_region.selector.payload_span.text == "init_register"
        assert init_register.source_region.payload is not None
        assert init_register.source_region.payload.payload_span.text == "result"
        first_statement_line = envelope.payload_source.line + 1
        assert init_register.source_region.head_span.line == first_statement_line

        assert unroll.keyword is SourceBodyKeyword.LOOP
        assert unroll.source_region.selector is not None
        assert unroll.source_region.selector.payload_span.text == "unroll"
        assert unroll.payload_fragments is not None
        assert _root_head_names(unroll.payload_fragments.keyword_fragments) == ("value",)
        assert unroll.payload_fragments.keyword_fragments[
            0
        ].source_region.full_span.text == "value<generation>(vector::length)"
        assert unroll.source_region.head_span.line == first_statement_line + 1

        assert loop.keyword is SourceBodyKeyword.LOOP
        assert loop.source_region.selector is not None
        assert loop.source_region.selector.payload_span.text == "range"
        assert loop.payload_fragments is not None
        assert _root_head_names(loop.payload_fragments.keyword_fragments) == ("value",)
        assert tuple(fragment.span.text for fragment in loop.payload_fragments.raw_fragments) == (
            "i, 0, ",
            ", 1",
        )
        assert loop.source_region.head_span.line == first_statement_line + 2

        assert emit_return.keyword is SourceBodyKeyword.EMIT_RETURN
        assert emit_return.payload_fragments is not None
        assert tuple(
            fragment.span.text for fragment in emit_return.payload_fragments.raw_fragments
        ) == ("result",)
        assert emit_return.payload_fragments.keyword_fragments == ()
        assert emit_return.source_region.head_span.line == first_statement_line + 5


def test_m254_real_generic_loop_body_keeps_assignment_and_indexing_raw() -> None:
    for primitive_name, envelope in _real_generic_add_sub_envelopes():
        result = lower_source_body_fragments(SourceBodyText.from_envelope(envelope))
        loop = result.sequence.keyword_fragments[2]
        assert loop.body_fragments is not None

        assert result.diagnostics == (), primitive_name
        assert tuple(
            fragment.span.text for fragment in loop.body_fragments.raw_fragments
        ) == (
            "\n              result[i] = ",
            ";\n            ",
        )
        assert _root_head_names(loop.body_fragments.keyword_fragments) == ("call",)

        call = loop.body_fragments.keyword_fragments[0]
        assert call.keyword is SourceBodyKeyword.CALL
        assert call.source_region.full_span.text == (
            "call<primitive=@self[type<backend>(vector::as_extension(scalar))]>"
            "(left[i], right[i])"
        )
        assert call.selector_fragments is not None
        assert tuple(
            fragment.span.text for fragment in call.selector_fragments.raw_fragments
        ) == (
            "primitive=@self[",
            "]",
        )
        assert _root_head_names(call.selector_fragments.keyword_fragments) == ("type",)
        assert call.selector_fragments.keyword_fragments[
            0
        ].source_region.full_span.text == "type<backend>(vector::as_extension(scalar))"

        assert call.payload_fragments is not None
        assert tuple(fragment.span.text for fragment in call.payload_fragments.raw_fragments) == (
            "left[i], right[i]",
        )
        assert call.payload_fragments.keyword_fragments == ()


def test_m254_real_generic_primitive_call_is_structured_without_self_resolution() -> None:
    for primitive_name, envelope in _real_generic_add_sub_envelopes():
        result = lower_source_body_fragments(SourceBodyText.from_envelope(envelope))
        extraction = extract_primitive_call_directives(result.sequence)

        assert result.diagnostics == (), primitive_name
        assert extraction.diagnostics == ()
        assert len(extraction.directives) == 1
        directive = extraction.directives[0].directive
        assert directive.name == "call"
        assert directive.arguments == (
            "primitive",
            "@self[type<backend>(vector::as_extension(scalar))]",
            "left[i], right[i]",
        )
        assert directive.primitive_call is not None
        selector = directive.primitive_call.selector
        assert isinstance(selector.target, SelfPrimitiveReference)
        assert selector.specialization == "type<backend>(vector::as_extension(scalar))"
        assert selector.attrs is None
        assert tuple(argument.text for argument in directive.primitive_call.arguments) == (
            "left[i]",
            "right[i]",
        )


def test_m254_recursive_lowering_guardrails_do_not_add_pairwise_paths() -> None:
    production_sources = (
        _SOURCE_BODY_REGIONS_PATH.read_text(encoding="utf-8"),
        _SOURCE_BODY_FRAGMENTS_PATH.read_text(encoding="utf-8"),
    )
    combined_source = "\n".join(production_sources)

    for forbidden in (
        "loop_call",
        "LoopCall",
        "emit_return_call",
        "EmitReturnCall",
        "assignment_call",
        "AssignmentCall",
        "result[i] = call<primitive=@self",
        "real_generic",
        "real_add",
        "real_sub",
        "fundamental.tsl",
    ):
        assert forbidden not in combined_source

    imported_modules = {
        node.module
        for source in production_sources
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom)
    } | {
        alias.name
        for source in production_sources
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    assert not any(module == "frozen" or module.startswith("frozen.") for module in imported_modules)
    assert not any(
        module == "tslgenold" or module.startswith("tslgenold.")
        for module in imported_modules
    )


def _root_head_names(fragments: tuple[KeywordRegionFragment, ...]) -> tuple[str, ...]:
    return tuple(fragment.source_region.head.name for fragment in fragments)


def _real_generic_add_sub_envelopes() -> tuple[
    tuple[str, ParsedImplementationBodyEnvelope],
    ...,
]:
    document = _parse_fundamental()
    return tuple(
        (name, _generic_unmasked_body(_primitive(document.primitives, name)))
        for name in ("add", "sub")
    )


def _primitive(
    primitives: tuple[ParsedPrimitiveDeclaration, ...],
    name: str,
) -> ParsedPrimitiveDeclaration:
    matches = tuple(
        primitive
        for primitive in primitives
        if primitive.name == name and primitive.signature == "v:=(v,v)"
    )
    assert len(matches) == 1
    return matches[0]


def _generic_unmasked_body(
    primitive: ParsedPrimitiveDeclaration,
) -> ParsedImplementationBodyEnvelope:
    matches = tuple(
        envelope
        for envelope in primitive.body_envelopes
        if envelope.selector_path == ("[generic, oneAPIfpga, oneAPIfpgaRTL]", "arith")
    )
    assert len(matches) == 1
    return matches[0]


def _parse_fundamental():
    text = _FUNDAMENTAL_PATH.read_text(encoding="utf-8")
    result = OuterTslParser().parse(
        (
            SourceDocument(
                path=_FUNDAMENTAL_PATH.resolve(),
                text=text,
                digest=sha256(text.encode("utf-8")).hexdigest(),
                kind="tsl",
            ),
        )
    )
    assert result.diagnostics == ()
    assert len(result.documents) == 1
    return result.documents[0]
