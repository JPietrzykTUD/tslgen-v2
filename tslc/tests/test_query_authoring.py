"""Typed TSIL query-vocabulary lookup for editor completion."""

from __future__ import annotations

import pytest

from tslc.lower._query_leaf import DEFAULT_QUERY_LEAF_NAMESPACES
from tslc.lower.queries import DEFAULT_QUERY_FUNCTIONS
from tslc.lower.query_authoring import (
    DEFAULT_QUERY_AUTHORING_INDEX,
    QueryScopeSymbol,
)


def _labels(text: str, symbols: tuple[QueryScopeSymbol, ...] = ()) -> set[str]:
    return {
        candidate.label
        for candidate in DEFAULT_QUERY_AUTHORING_INDEX.complete(text, symbols)
    }


def test_root_and_namespace_completion_are_derived_from_registered_queries() -> None:
    index = DEFAULT_QUERY_AUTHORING_INDEX
    root_functions = {
        function.head for function in DEFAULT_QUERY_FUNCTIONS if "::" not in function.head
    }

    assert _labels("") == root_functions | set(index.namespace_children[""])
    for namespace in index.namespace_children[""]:
        assert _labels(f"{namespace}::") == set(
            index.namespace_children[namespace]
        )


@pytest.mark.parametrize(
    "head",
    tuple(
        function.head
        for function in DEFAULT_QUERY_FUNCTIONS
        if "::" in function.head and not function.descriptor.arguments
    ),
)
def test_terminal_query_functions_close_the_completion_path(head: str) -> None:
    assert DEFAULT_QUERY_AUTHORING_INDEX.complete(head) == ()


@pytest.mark.parametrize(
    "leaf",
    tuple(
        f"{namespace.name}::{value}"
        for namespace in DEFAULT_QUERY_LEAF_NAMESPACES
        for value in namespace.values
    ),
)
def test_terminal_query_leaves_close_the_completion_path(leaf: str) -> None:
    assert DEFAULT_QUERY_AUTHORING_INDEX.complete(leaf) == ()


def test_query_argument_kinds_filter_roots_and_invalid_paths_stop() -> None:
    type_argument = _labels("base::signed_of(")

    assert {"base", "scalar", "type", "value"} <= type_argument
    assert {"generic", "intrin", "primitive", "register"}.isdisjoint(type_argument)
    assert _labels("vector::bogus") == set()
    assert _labels("base:bogus") == set()


def test_named_query_roles_offer_only_matching_typed_scope_facts() -> None:
    symbols = (
        QueryScopeSymbol("data", frozenset({"text"}), "primitive parameter"),
        QueryScopeSymbol(
            "aligned",
            frozenset({"text"}),
            "primitive selector axis",
            role="attribute",
        ),
        QueryScopeSymbol(
            "avx2",
            frozenset({"text"}),
            "extension",
            role="extension",
        ),
    )

    assert _labels("primitive::attribute(al", symbols) == {"aligned"}
    assert _labels("vector::as_extension(av", symbols) == {"avx2"}
    assert _labels("primitive::attribute(da", symbols) == set()


def test_authoring_index_covers_exactly_the_evaluator_function_registry() -> None:
    assert set(DEFAULT_QUERY_AUTHORING_INDEX.functions) == {
        function.head for function in DEFAULT_QUERY_FUNCTIONS
    }
    assert all(function.descriptor.result_kinds for function in DEFAULT_QUERY_FUNCTIONS)
