"""Lark-backed parser for outer TSL declaration envelopes."""

from __future__ import annotations

import ast
from collections.abc import Iterable
from functools import lru_cache
from importlib import resources

from lark import Lark, Token, Tree
from lark.exceptions import UnexpectedInput
from lark.indenter import Indenter

from tslc.diagnostics import Diagnostic, SourceLocation
from tslc.sources import SourceDocument
from tslc.syntax.ast import (
    OuterTslParseResult,
    ParsedBlockDeclaration,
    ParsedFieldDeclaration,
    ParsedImplementationBodyEnvelope,
    ParsedImplementationSelectorEntry,
    ParsedPrimitiveDeclaration,
    ParsedPrimitiveField,
    ParsedPrimitiveFieldKind,
    ParsedRequiresValue,
    ParsedTopLevelDeclaration,
    ParsedTopLevelDeclarationKind,
    ParsedTslAttribute,
    ParsedTslAttributeListValue,
    ParsedTslField,
    ParsedTslKey,
    ParsedTslListValue,
    ParsedTslMapValue,
    ParsedTslQuoteForm,
    ParsedTslScalarValue,
    ParsedTslSourceSpan,
    ParsedTslValue,
    ParsedOuterTslDocument,
)


_GRAMMAR_PACKAGE = "tslc.syntax.grammar"
_GRAMMAR_FILE = "tsl_data.lark"
_KNOWN_PRIMITIVE_FIELDS: dict[str, ParsedPrimitiveFieldKind] = {
    "brief_description": "brief_description",
    "generic_params": "generic_params",
    "impls": "impls",
    "operation": "operation",
    "return_type": "return_type",
    "sImm_type": "simm_type",
    "tests": "tests",
}


class _TslIndenter(Indenter):
    NL_type = "NEWLINE"
    OPEN_PAREN_types = ["LPAR", "LSQB", "LBRACE", "LT"]
    CLOSE_PAREN_types = ["RPAR", "RSQB", "RBRACE", "GT"]
    INDENT_type = "_INDENT"
    DEDENT_type = "_DEDENT"
    tab_len = 8


class TslParser:
    """Parse outer TSL declarations and preserve TSIL payload envelopes."""

    def parse(self, documents: tuple[SourceDocument, ...]) -> OuterTslParseResult:
        parsed_documents: list[ParsedOuterTslDocument] = []
        diagnostics: list[Diagnostic] = []
        parser = _lark_parser()
        for document in sorted(documents, key=lambda item: item.path.as_posix()):
            try:
                tree = parser.parse(document.text)
            except UnexpectedInput as error:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code="TSL-OUTER-PARSE-UNSUPPORTED-FORM",
                        message=f"outer TSL declaration parse failed: {error}",
                        location=SourceLocation(
                            document.path,
                            int(getattr(error, "line", 1) or 1),
                            int(getattr(error, "column", 1) or 1),
                        ),
                    )
                )
                continue

            parsed_documents.append(_DocumentTransformer(document).transform(tree))

        return OuterTslParseResult(
            documents=tuple(parsed_documents),
            diagnostics=tuple(diagnostics),
        )


@lru_cache(maxsize=1)
def _lark_parser() -> Lark:
    grammar = resources.files(_GRAMMAR_PACKAGE).joinpath(_GRAMMAR_FILE).read_text()
    return Lark(
        grammar,
        parser="lalr",
        postlex=_TslIndenter(),
        propagate_positions=True,
        maybe_placeholders=False,
    )


class _DocumentTransformer:
    def __init__(self, document: SourceDocument) -> None:
        self._document = document
        self._line_starts = _line_starts(document.text)
        self._source_order = 0

    def transform(self, tree: Tree) -> ParsedOuterTslDocument:
        declarations = tuple(
            self._parse_top_level_statement(statement)
            for statement in _statement_trees(tree)
        )
        return ParsedOuterTslDocument(
            path=self._document.path,
            declarations=declarations,
        )

    def _next_source_order(self) -> int:
        current = self._source_order
        self._source_order += 1
        return current

    def _parse_top_level_statement(self, tree: Tree) -> ParsedTopLevelDeclaration:
        if tree.data == "primitive_block":
            return self._parse_primitive_block(tree)
        if tree.data == "pair":
            field = self._parse_field(tree)
            kind: ParsedTopLevelDeclarationKind = (
                "description" if field.key.text == "description" else "field"
            )
            return ParsedFieldDeclaration(
                kind=kind,
                field=field,
                source_order=field.source_order,
            )

        kind = _block_kind(tree)
        name = _first_direct_token_text(tree, "NAME")
        return ParsedBlockDeclaration(
            kind=kind,
            name=name,
            fields=tuple(self._parse_field(field) for field in _field_trees(tree)),
            source=self._span(tree),
            source_order=self._next_source_order(),
        )

    def _parse_primitive_block(self, tree: Tree) -> ParsedPrimitiveDeclaration:
        signature = _first_direct_token(tree, "SIGNATURE")
        name = _first_direct_token(tree, "NAME")
        attr_list = _first_direct_tree_or_none(tree, "attr_list")
        fields = tuple(
            ParsedPrimitiveField(
                kind=_KNOWN_PRIMITIVE_FIELDS.get(field.key.text, "preserved"),
                field=field,
            )
            for field in (self._parse_field(field_tree) for field_tree in _field_trees(tree))
        )
        impl_field = next(
            (field.field for field in fields if field.field.key.text == "impls"),
            None,
        )
        impl_entries = (
            tuple(self._parse_impl_selector(field, ()) for field in impl_field.children)
            if impl_field is not None
            else ()
        )
        body_envelopes = tuple(_flatten_body_envelopes(impl_entries))
        return ParsedPrimitiveDeclaration(
            name=name.value,
            signature=signature.value,
            parameters=tuple(_param_text(param) for param in _direct_trees(tree, "param")),
            attributes=(
                self._parse_attributes(attr_list) if attr_list is not None else ()
            ),
            fields=fields,
            impl_entries=impl_entries,
            body_envelopes=body_envelopes,
            source=self._span(tree),
            header_source=self._header_span(tree),
            signature_source=self._span(signature),
            source_order=self._next_source_order(),
        )

    def _parse_impl_selector(
        self,
        field: ParsedTslField,
        parent_path: tuple[str, ...],
    ) -> ParsedImplementationSelectorEntry:
        selector_path = (*parent_path, field.key.text)
        requires = tuple(
            ParsedRequiresValue(child)
            for child in field.children
            if child.key.text == "requires"
        )
        body_envelopes = tuple(
            envelope
            for child in field.children
            if child.key.text == "implementation"
            for envelope in self._implementation_body_envelopes(child, selector_path)
        )
        nested = tuple(
            self._parse_impl_selector(child, selector_path)
            for child in field.children
            if child.key.text not in {"requires", "implementation", "unroll_variants"}
        )
        return ParsedImplementationSelectorEntry(
            selector=field.key,
            source=field.source,
            source_order=field.source_order,
            fields=field.children,
            children=nested,
            requires=requires,
            body_envelopes=body_envelopes,
        )

    def _implementation_body_envelopes(
        self,
        field: ParsedTslField,
        selector_path: tuple[str, ...],
    ) -> tuple[ParsedImplementationBodyEnvelope, ...]:
        envelopes: list[ParsedImplementationBodyEnvelope] = []
        for child in field.children:
            if child.key.text not in {"tsil", "tsl"} or not isinstance(
                child.value,
                ParsedTslScalarValue,
            ):
                continue
            if child.value.quote_form not in {"inline", "multiline"}:
                continue
            if child.value.payload_source is None:
                continue
            envelopes.append(
                ParsedImplementationBodyEnvelope(
                    selector_path=selector_path,
                    quote_form=child.value.quote_form,
                    payload_text=child.value.payload_source.text,
                    envelope_source=child.source,
                    payload_source=child.value.payload_source,
                    source_order=child.source_order,
                )
            )
        return tuple(envelopes)

    def _parse_attributes(self, tree: Tree) -> tuple[ParsedTslAttribute, ...]:
        return tuple(
            self._parse_attribute(attr_tree)
            for attr_tree in _direct_trees(tree, "attr_pair")
        )

    def _parse_attribute(self, tree: Tree) -> ParsedTslAttribute:
        key_tree = _first_direct_tree(tree, "attr_key")
        value_tree = next(
            child for child in tree.children if isinstance(child, Tree) and child is not key_tree
        )
        key_tokens = _direct_tokens(key_tree)
        key = self._key_from_token(key_tokens[0])
        key_argument = self._key_from_token(key_tokens[1]) if len(key_tokens) > 1 else None
        return ParsedTslAttribute(
            key=key,
            key_argument=key_argument,
            value=self._parse_value(value_tree),
            source=self._span(tree),
        )

    def _parse_field(self, tree: Tree) -> ParsedTslField:
        key_tree = _first_direct_tree(tree, "key")
        child_trees = tuple(
            child
            for child in tree.children
            if isinstance(child, Tree) and child is not key_tree
        )
        value: ParsedTslValue | None = None
        children: tuple[ParsedTslField, ...] = ()
        if child_trees:
            if _is_value_tree(child_trees[0]):
                value = self._parse_value(child_trees[0])
            else:
                children = tuple(
                    self._parse_field(field_tree)
                    for child_tree in child_trees
                    for field_tree in _statement_trees(child_tree)
                )
        return ParsedTslField(
            key=self._parse_key(key_tree),
            value=value,
            children=children,
            source=self._span(tree),
            source_order=self._next_source_order(),
        )

    def _parse_map_field(self, tree: Tree) -> ParsedTslField:
        key_tree = _first_direct_tree(tree, "key")
        value_trees = tuple(
            child
            for child in tree.children
            if isinstance(child, Tree) and child is not key_tree
        )
        value: ParsedTslValue | None = None
        children: tuple[ParsedTslField, ...] = ()
        if value_trees:
            if _is_value_tree(value_trees[0]):
                value = self._parse_value(value_trees[0])
            else:
                children = tuple(
                    self._parse_map_field(item)
                    for value_tree in value_trees
                    for item in _map_pair_trees(value_tree)
                )
        return ParsedTslField(
            key=self._parse_key(key_tree),
            value=value,
            children=children,
            source=self._span(tree),
            source_order=self._next_source_order(),
        )

    def _parse_key(self, tree: Tree) -> ParsedTslKey:
        direct_token = _first_direct_token_or_none(tree)
        if direct_token is not None:
            return self._key_from_token(direct_token)
        return ParsedTslKey(
            text=self._span(tree).text.strip(),
            source=self._span(tree),
        )

    def _key_from_token(self, token: Token) -> ParsedTslKey:
        return ParsedTslKey(
            text=token.value,
            source=self._span(token),
        )

    def _parse_value(self, tree: Tree) -> ParsedTslValue:
        if tree.data in {
            "bare",
            "bool",
            "multiline_string",
            "number",
            "string",
            "wildcard",
        }:
            return self._parse_scalar(tree)
        if tree.data == "list":
            return ParsedTslListValue(
                items=tuple(
                    self._parse_value(child)
                    for child in tree.children
                    if isinstance(child, Tree) and _is_value_tree(child)
                ),
                source=self._span(tree),
            )
        if tree.data == "list_block":
            return ParsedTslListValue(
                items=tuple(
                    self._parse_value(_first_value_tree(child))
                    for child in _direct_trees(tree, "list_item")
                ),
                source=self._span(tree),
            )
        if tree.data == "attr_list_nonempty":
            return ParsedTslAttributeListValue(
                attributes=tuple(
                    self._parse_attribute(child)
                    for child in _direct_trees(tree, "attr_pair")
                ),
                source=self._span(tree),
            )
        if tree.data == "map":
            return ParsedTslMapValue(
                entries=tuple(
                    self._parse_map_field(pair_tree)
                    for pair_tree in _map_pair_trees(tree)
                ),
                source=self._span(tree),
            )
        raise ValueError(f"unsupported value tree {tree.data!r}")

    def _parse_scalar(self, tree: Tree) -> ParsedTslScalarValue:
        token = _first_direct_token_or_none(tree)
        if token is None:
            raise ValueError(f"scalar tree {tree.data!r} has no token")
        raw_text = token.value
        quote_form: ParsedTslQuoteForm = "none"
        payload_source: ParsedTslSourceSpan | None = None
        text = raw_text
        if tree.data == "string":
            quote_form = "inline"
            text = ast.literal_eval(raw_text)
            payload_source = self._inner_string_span(token, 1)
        elif tree.data == "multiline_string":
            quote_form = "multiline"
            text = raw_text[3:-3]
            payload_source = self._inner_string_span(token, 3)
        return ParsedTslScalarValue(
            kind=tree.data,  # type: ignore[arg-type]
            text=text,
            raw_text=raw_text,
            quote_form=quote_form,
            source=self._span(token),
            payload_source=payload_source,
        )

    def _span(self, item: Tree | Token) -> ParsedTslSourceSpan:
        if isinstance(item, Token):
            return self._span_from_offsets(item.start_pos, item.end_pos)
        return self._span_from_offsets(item.meta.start_pos, item.meta.end_pos)

    def _header_span(self, tree: Tree) -> ParsedTslSourceSpan:
        return self._span_from_offsets(tree.meta.start_pos, _header_end_offset(tree))

    def _inner_string_span(self, token: Token, delimiter_width: int) -> ParsedTslSourceSpan:
        return self._span_from_offsets(
            token.start_pos + delimiter_width,
            token.end_pos - delimiter_width,
        )

    def _span_from_offsets(self, start: int, end: int) -> ParsedTslSourceSpan:
        start_line, start_column = _line_column(self._line_starts, start)
        end_line, end_column = _line_column(self._line_starts, end)
        return ParsedTslSourceSpan(
            path=self._document.path,
            line=start_line,
            column=start_column,
            end_line=end_line,
            end_column=end_column,
            text=self._document.text[start:end],
        )


def _statement_trees(tree: Tree) -> tuple[Tree, ...]:
    if tree.data == "start":
        return tuple(
            statement
            for child in tree.children
            if isinstance(child, Tree)
            for statement in _statement_trees(child)
        )
    if tree.data == "stmt_list":
        return tuple(child for child in tree.children if isinstance(child, Tree))
    if tree.data in {
        "pair",
        "primitive_block",
        "template_block",
        "extension_block",
        "types_block",
        "flags_block",
        "language_block",
        "translation_block",
        "lane_set_block",
    }:
        return (tree,)
    return ()


def _field_trees(tree: Tree) -> tuple[Tree, ...]:
    result: list[Tree] = []
    for child in tree.children:
        if not isinstance(child, Tree):
            continue
        if child.data == "pair":
            result.append(child)
        elif child.data == "stmt_list":
            result.extend(_field_trees(child))
    return tuple(result)


def _map_pair_trees(tree: Tree) -> tuple[Tree, ...]:
    if tree.data in {
        "pair_inline",
        "pair_inline_colon",
        "pair_inline_block",
    }:
        return (tree,)
    return tuple(
        pair
        for child in tree.children
        if isinstance(child, Tree)
        for pair in _map_pair_trees(child)
    )


def _flatten_body_envelopes(
    entries: Iterable[ParsedImplementationSelectorEntry],
) -> Iterable[ParsedImplementationBodyEnvelope]:
    for entry in entries:
        yield from entry.body_envelopes
        yield from _flatten_body_envelopes(entry.children)


def _block_kind(tree: Tree) -> ParsedTopLevelDeclarationKind:
    if tree.data == "template_block":
        return "template"
    if tree.data == "extension_block":
        return "extension"
    if tree.data == "types_block":
        return "types"
    if tree.data == "flags_block":
        return "flags"
    if tree.data == "language_block":
        return "language"
    if tree.data == "translation_block":
        return "translation"
    if tree.data == "lane_set_block":
        return "lane_set"
    raise ValueError(f"unsupported block {tree.data!r}")


def _is_value_tree(tree: Tree) -> bool:
    return tree.data in {
        "attr_list_nonempty",
        "bare",
        "bool",
        "list",
        "list_block",
        "map",
        "multiline_string",
        "number",
        "string",
        "wildcard",
    }


def _first_value_tree(tree: Tree) -> Tree:
    for child in tree.children:
        if isinstance(child, Tree) and _is_value_tree(child):
            return child
    raise ValueError(f"tree {tree.data!r} has no value child")


def _direct_trees(tree: Tree, data: str) -> tuple[Tree, ...]:
    return tuple(
        child for child in tree.children if isinstance(child, Tree) and child.data == data
    )


def _first_direct_token(tree: Tree, token_type: str) -> Token:
    for child in tree.children:
        if isinstance(child, Token) and child.type == token_type:
            return child
    raise ValueError(f"tree {tree.data!r} has no token {token_type!r}")


def _first_direct_token_or_none(tree: Tree) -> Token | None:
    for child in tree.children:
        if isinstance(child, Token):
            return child
    return None


def _first_direct_token_text(tree: Tree, token_type: str) -> str | None:
    for child in tree.children:
        if isinstance(child, Token) and child.type == token_type:
            return child.value
    return None


def _first_direct_tree_or_none(tree: Tree, data: str) -> Tree | None:
    for child in tree.children:
        if isinstance(child, Tree) and child.data == data:
            return child
    return None


def _first_direct_tree(tree: Tree, data: str) -> Tree:
    result = _first_direct_tree_or_none(tree, data)
    if result is None:
        raise ValueError(f"tree {tree.data!r} has no child tree {data!r}")
    return result


def _direct_tokens(tree: Tree) -> tuple[Token, ...]:
    return tuple(child for child in tree.children if isinstance(child, Token))


def _param_text(tree: Tree) -> str:
    return _first_direct_token(tree, "NAME").value


def _header_end_offset(tree: Tree) -> int:
    for child in tree.children:
        if isinstance(child, Token) and child.type == "NEWLINE":
            return child.start_pos
    return tree.meta.end_pos


def _line_starts(text: str) -> tuple[int, ...]:
    starts = [0]
    for index, character in enumerate(text):
        if character == "\n":
            starts.append(index + 1)
    return tuple(starts)


def _line_column(line_starts: tuple[int, ...], offset: int) -> tuple[int, int]:
    line_index = 0
    for index, start in enumerate(line_starts):
        if start > offset:
            break
        line_index = index
    return line_index + 1, offset - line_starts[line_index] + 1
