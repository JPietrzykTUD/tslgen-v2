"""Evaluate the small TSIL generation/backend query language.

Queries are nested ``head(arg)`` forms used inside TSIL bodies and intrinsic
modifiers. The public module intentionally owns only the evaluator and default
registry; query vocabularies live in focused namespace modules:

- ``_query_model``: typed values, parsed terms, parser, and function protocol;
- ``_query_core``: base/type/value/intrinsic/primitive query functions;
- ``_query_vector``: vector/register/mask/generic query functions;
- ``_query_leaf``: source-level bare identifier resolution.
"""

from __future__ import annotations

from tslc.lower._query_core import (
    AttributeQuery,
    BaseInQuery,
    IntrinPrefixQuery,
    IntrinSuffixQuery,
    IsSameQuery,
    IsSignedQuery,
    SelectQuery,
    SameSizeQuery,
    SizeBitsQuery,
    SignedOfQuery,
    SizeBytesQuery,
    TypeQuery,
    UnsignedOfQuery,
    ValueQuery,
)
from tslc.lower._query_leaf import resolve_query_leaf
from tslc.lower._query_model import (
    BoolValue,
    QueryFunction,
    QueryParser,
    QueryTerm,
    QueryValue,
    SimdTypeParameterValue,
    TextValue,
    TypeValue,
)
from tslc.lower._query_vector import (
    AsBaseQuery,
    AsExtensionQuery,
    BaseGenericQuery,
    FixedFacadeQuery,
    GenericLengthQuery,
    GenericRuntimeLengthQuery,
    ImaskQuery,
    MaskQuery,
    RegisterGenericQuery,
    RegisterQuery,
    VectorAlignmentQuery,
    VectorAsQuery,
    VectorLengthQuery,
    VectorRuntimeLengthQuery,
    WindowBaseQuery,
)
from tslc.lower.context import LoweringSession

DEFAULT_QUERY_FUNCTIONS: tuple[QueryFunction, ...] = (
    BaseInQuery(),
    SignedOfQuery(),
    UnsignedOfQuery(),
    TypeQuery(),
    ValueQuery(),
    SelectQuery(),
    IntrinPrefixQuery(),
    IntrinSuffixQuery(),
    IsSameQuery(),
    SizeBytesQuery(),
    SizeBitsQuery(),
    SameSizeQuery(),
    IsSignedQuery(),
    AttributeQuery(),
    RegisterQuery(),
    RegisterGenericQuery(),
    MaskQuery(),
    ImaskQuery(),
    VectorAlignmentQuery(),
    VectorLengthQuery(),
    VectorRuntimeLengthQuery(),
    AsExtensionQuery(),
    FixedFacadeQuery(),
    AsBaseQuery(),
    WindowBaseQuery(),
    VectorAsQuery(),
    BaseGenericQuery(),
    GenericLengthQuery(),
    GenericRuntimeLengthQuery(),
)


class QueryEvaluator:
    def __init__(
        self,
        functions: tuple[QueryFunction, ...] = DEFAULT_QUERY_FUNCTIONS,
        parser: QueryParser | None = None,
    ) -> None:
        self._functions = {function.head: function for function in functions}
        self._parser = parser or QueryParser()

    def evaluate(self, text: str, context: LoweringSession) -> QueryValue | None:
        term = self._parser.parse(text)
        if term is None:
            return None
        return self.evaluate_term(term, context)

    def evaluate_term(self, term: QueryTerm, context: LoweringSession) -> QueryValue | None:
        evaluated_args: list[QueryValue] = []
        for arg in term.args:
            value = self.evaluate_term(arg, context)
            if value is None:
                return None
            evaluated_args.append(value)

        function = self._functions.get(term.head)
        if function is not None:
            args = tuple(evaluated_args)
            if not function.descriptor.accepts(args):
                return None
            return function.apply(args, context)
        if not term.args:
            return self.resolve_leaf(term.head, context)
        return None

    def resolve_leaf(self, head: str, context: LoweringSession) -> QueryValue | None:
        return resolve_query_leaf(head, context)


__all__ = [
    "AsBaseQuery",
    "AsExtensionQuery",
    "AttributeQuery",
    "BaseGenericQuery",
    "BaseInQuery",
    "BoolValue",
    "DEFAULT_QUERY_FUNCTIONS",
    "GenericLengthQuery",
    "FixedFacadeQuery",
    "GenericRuntimeLengthQuery",
    "ImaskQuery",
    "IntrinPrefixQuery",
    "IntrinSuffixQuery",
    "IsSameQuery",
    "IsSignedQuery",
    "MaskQuery",
    "QueryEvaluator",
    "QueryFunction",
    "QueryParser",
    "QueryTerm",
    "QueryValue",
    "RegisterGenericQuery",
    "RegisterQuery",
    "SameSizeQuery",
    "SelectQuery",
    "SignedOfQuery",
    "SimdTypeParameterValue",
    "SizeBitsQuery",
    "SizeBytesQuery",
    "TextValue",
    "TypeQuery",
    "TypeValue",
    "UnsignedOfQuery",
    "ValueQuery",
    "VectorAlignmentQuery",
    "VectorAsQuery",
    "VectorLengthQuery",
    "VectorRuntimeLengthQuery",
    "WindowBaseQuery",
]
