from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from importlib.resources import files
from typing import Any, cast

from lark import Lark, Token, Tree
from lark.exceptions import UnexpectedInput
from lark.indenter import Indenter

from tslgen.core.diagnostics import Diagnostic, SourceLocation, SourceSpan
from tslgen.core.result import Result
from tslgen.io.sources import SourceDocument, SourceSet
from tslgen.syntax.ast import ParsedDocument, ParsedDocumentSet, SyntaxNode, make_span


class _TslIndenter(Indenter):
    NL_type = "NEWLINE"
    OPEN_PAREN_types = ["LPAR", "LSQB", "LBRACE", "LT"]
    CLOSE_PAREN_types = ["RPAR", "RSQB", "RBRACE", "GT"]
    INDENT_type = "_INDENT"
    DEDENT_type = "_DEDENT"
    tab_len = 8


@dataclass(frozen=True, slots=True)
class TslParser:
    _parser: Lark

    @classmethod
    def from_packaged_grammar(cls) -> TslParser:
        grammar = files("tslgen.syntax.grammar").joinpath("tsl_data.lark").read_text()
        return cls(
            Lark(
                grammar,
                parser="lalr",
                postlex=_TslIndenter(),
                propagate_positions=True,
                start="start",
            )
        )

    def parse_document(self, source: SourceDocument) -> Result[ParsedDocument]:
        try:
            tree = cast(Tree[Token], self._parser.parse(source.text))
        except UnexpectedInput as error:
            return Result.failure((_syntax_diagnostic(source, error),))

        root = _convert_tree(source, tree)
        return Result.ok(ParsedDocument(source=source, root=root))

    def parse_sources(self, sources: SourceSet) -> Result[ParsedDocumentSet]:
        documents: list[ParsedDocument] = []
        diagnostics: list[Diagnostic] = []
        for source in sources:
            result = self.parse_document(source)
            diagnostics.extend(result.diagnostics)
            if result.is_ok:
                documents.append(result.unwrap())

        if diagnostics:
            return Result.failure(diagnostics)
        return Result.ok(ParsedDocumentSet(tuple(documents)))


def parse_document(source: SourceDocument) -> Result[ParsedDocument]:
    return TslParser.from_packaged_grammar().parse_document(source)


def parse_sources(sources: SourceSet) -> Result[ParsedDocumentSet]:
    return TslParser.from_packaged_grammar().parse_sources(sources)


def _convert_tree(source: SourceDocument, tree: Tree[Token]) -> SyntaxNode:
    children = tuple(
        node
        for child in tree.children
        if (node := _convert_child(source, child)) is not None
    )
    return SyntaxNode(
        kind=tree.data,
        span=_span_from_meta(source, tree.meta, source.text),
        children=children,
    )


def _convert_child(source: SourceDocument, child: object) -> SyntaxNode | None:
    if child is None:
        return None
    if isinstance(child, Tree):
        return _convert_tree(source, child)
    if isinstance(child, Token):
        return _convert_token(source, child)
    raise TypeError(f"unsupported parse tree child: {type(child).__qualname__}")


def _convert_token(source: SourceDocument, token: Token) -> SyntaxNode:
    return SyntaxNode(
        kind=token.type,
        text=token.value,
        span=make_span(
            source.path,
            line=int(token.line or 1),
            column=int(token.column or 1),
            end_line=token.end_line,
            end_column=token.end_column,
            text=token.value,
        ),
    )


def _span_from_meta(source: SourceDocument, meta: Any, source_text: str) -> SourceSpan:
    start_pos = getattr(meta, "start_pos", None)
    end_pos = getattr(meta, "end_pos", None)
    text: str | None = None
    if isinstance(start_pos, int) and isinstance(end_pos, int):
        text = source_text[start_pos:end_pos]

    line = getattr(meta, "line", None) or 1
    column = getattr(meta, "column", None) or 1
    end_line = getattr(meta, "end_line", None)
    end_column = getattr(meta, "end_column", None)
    return make_span(
        source.path,
        line=int(line),
        column=int(column),
        end_line=end_line,
        end_column=end_column,
        text=text,
    )


def _syntax_diagnostic(source: SourceDocument, error: UnexpectedInput) -> Diagnostic:
    expected = _expected_symbols(error)
    suffix = f"; expected one of: {expected}" if expected else ""
    return Diagnostic.error(
        "TSL-PARSE-SYNTAX",
        f"invalid TSL syntax near {source.logical_path}: {error.__class__.__name__}{suffix}",
        location=SourceLocation(
            path=source.path,
            line=error.line,
            column=error.column,
        ),
    )


def _expected_symbols(error: UnexpectedInput) -> str:
    expected = getattr(error, "expected", None)
    if not isinstance(expected, Iterable):
        return ""
    symbols = sorted(str(symbol) for symbol in expected)
    return ", ".join(symbols[:8])
