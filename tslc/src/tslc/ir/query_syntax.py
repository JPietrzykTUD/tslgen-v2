"""Syntax-only parser for nested TSIL query expressions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from tslc.ir.text import split_head_arg, split_top_level

_QUERY_NAME = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:::[A-Za-z_][A-Za-z0-9_]*)*$"
)


@dataclass(frozen=True, slots=True)
class QueryTerm:
    head: str
    args: tuple["QueryTerm", ...]


class QueryParser:
    def parse(self, text: str) -> QueryTerm | None:
        return _cached_parse_query(text.strip())


_QUERY_PARSE_CACHE_SIZE = 512


@lru_cache(maxsize=_QUERY_PARSE_CACHE_SIZE)
def _cached_parse_query(text: str) -> QueryTerm | None:
    split = split_head_arg(text)
    if split is None:
        return QueryTerm(head=text, args=())
    head_text, arg_text = split
    args: list[QueryTerm] = []
    for piece in split_top_level(arg_text):
        parsed = _cached_parse_query(piece.strip())
        if parsed is None:
            return None
        args.append(parsed)
    return QueryTerm(head=head_text.strip(), args=tuple(args))


def is_tsil_type_expression_syntax(text: str) -> bool:
    """Whether `text` has the target-neutral nested-query shell used in type positions.

    Resolution remains a lowering concern. This check intentionally accepts unknown
    identifiers and query names while rejecting target-language decorations such as
    `const` and `*` that sit outside the TSIL query grammar.
    """

    term = QueryParser().parse(text)
    return term is not None and _has_query_names(term)


def _has_query_names(term: QueryTerm) -> bool:
    return bool(_QUERY_NAME.fullmatch(term.head)) and all(
        _has_query_names(argument) for argument in term.args
    )


__all__ = (
    "QueryParser",
    "QueryTerm",
    "_QUERY_PARSE_CACHE_SIZE",
    "_cached_parse_query",
    "is_tsil_type_expression_syntax",
)
