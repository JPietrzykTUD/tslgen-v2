"""Pure authoring lookup over the registered typed TSIL query vocabulary."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
import re
from typing import Literal, Mapping

from tslc.lower._query_leaf import DEFAULT_QUERY_LEAF_NAMESPACES
from tslc.lower._query_model import (
    ALL_QUERY_KINDS,
    QueryArgumentRole,
    QueryFunction,
    QueryFunctionDescriptor,
    QueryLeafNamespaceDescriptor,
    QueryValueKind,
)
from tslc.lower.queries import DEFAULT_QUERY_FUNCTIONS


QueryAuthoringCandidateKind = Literal["function", "namespace", "type", "value"]

_TOKEN_SUFFIX = re.compile(r"[A-Za-z_][A-Za-z0-9_:]*$")
_CALL_HEAD_SUFFIX = re.compile(
    r"([A-Za-z_][A-Za-z0-9_]*(?:::[A-Za-z_][A-Za-z0-9_]*)*)\s*$"
)
_VALID_PATH = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*(?:::[A-Za-z_][A-Za-z0-9_]*)*(?:::)?$"
)


@dataclass(frozen=True, slots=True)
class QueryScopeSymbol:
    """One source-known name that is safe to offer inside a TSIL expression."""

    name: str
    kinds: frozenset[QueryValueKind]
    detail: str
    role: QueryArgumentRole = "query"


@dataclass(frozen=True, slots=True)
class QueryAuthoringCandidate:
    label: str
    insert_text: str
    replacement_start: int
    detail: str
    kind: QueryAuthoringCandidateKind
    commit_characters: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class QueryCursor:
    replacement_start: int
    prefix: str
    expected_kinds: frozenset[QueryValueKind]
    role: QueryArgumentRole


@dataclass(frozen=True, slots=True)
class _Delimiter:
    opening: str
    query_head: str | None = None
    argument_index: int = 0


class QueryAuthoringIndex:
    """Precomputed namespace tree built from the evaluator's function registry."""

    def __init__(
        self,
        functions: tuple[QueryFunction, ...],
        leaf_namespaces: tuple[QueryLeafNamespaceDescriptor, ...],
    ) -> None:
        self.functions: Mapping[str, QueryFunctionDescriptor] = MappingProxyType(
            {function.head: function.descriptor for function in functions}
        )
        self.leaf_namespaces: Mapping[str, QueryLeafNamespaceDescriptor] = (
            MappingProxyType(
                {descriptor.name: descriptor for descriptor in leaf_namespaces}
            )
        )
        namespace_children: dict[str, set[str]] = {}
        for head in self.functions:
            self._record_namespaces(head, namespace_children)
        for descriptor in leaf_namespaces:
            namespace_children.setdefault("", set()).add(descriptor.name)
            namespace_children.setdefault(descriptor.name, set()).update(
                descriptor.values
            )
        self.namespace_children: Mapping[str, tuple[str, ...]] = MappingProxyType(
            {
                namespace: tuple(sorted(children))
                for namespace, children in namespace_children.items()
            }
        )

    @staticmethod
    def _record_namespaces(
        head: str,
        namespace_children: dict[str, set[str]],
    ) -> None:
        parts = head.split("::")
        if len(parts) == 1:
            return
        for index in range(len(parts) - 1):
            parent = "::".join(parts[:index])
            namespace_children.setdefault(parent, set()).add(parts[index])
        namespace_children.setdefault("::".join(parts[:-1]), set()).add(parts[-1])

    def complete(
        self,
        text: str,
        symbols: tuple[QueryScopeSymbol, ...] = (),
    ) -> tuple[QueryAuthoringCandidate, ...]:
        cursor = self.cursor(text)
        if cursor is None or not cursor.expected_kinds:
            return ()
        if cursor.role != "query":
            return self._scope_candidates(cursor, symbols)
        if "::" in cursor.prefix:
            candidates = self._path_candidates(cursor)
        else:
            candidates = (
                *self._root_candidates(cursor),
                *self._scope_candidates(cursor, symbols),
            )
        unique = {
            (candidate.label, candidate.detail): candidate for candidate in candidates
        }
        return tuple(
            sorted(
                unique.values(),
                key=lambda candidate: (candidate.label, candidate.detail),
            )
        )

    def cursor(self, text: str) -> QueryCursor | None:
        token_match = _TOKEN_SUFFIX.search(text)
        token = token_match.group(0) if token_match is not None else ""
        token_start = token_match.start() if token_match is not None else len(text)
        if not token and not _can_start_expression(text):
            return None
        expected = ALL_QUERY_KINDS
        role: QueryArgumentRole = "query"
        frame = self._active_query_call(text[:token_start])
        if frame is not None and frame.query_head is not None:
            descriptor = self.functions[frame.query_head]
            argument = descriptor.argument(frame.argument_index)
            if argument is None:
                expected = frozenset()
            else:
                expected = argument.kinds
                role = argument.role
        return QueryCursor(token_start, token, expected, role)

    def _active_query_call(self, text: str) -> _Delimiter | None:
        stack: list[_Delimiter] = []
        index = 0
        while index < len(text):
            opaque_end = _skip_opaque(text, index)
            if opaque_end is not None:
                index = opaque_end
                continue
            character = text[index]
            if character in "([{":
                query_head: str | None = None
                if character == "(":
                    match = _CALL_HEAD_SUFFIX.search(text[:index])
                    if match is not None and match.group(1) in self.functions:
                        query_head = match.group(1)
                stack.append(_Delimiter(character, query_head))
            elif character in ")]}":
                expected_open = {")": "(", "]": "[", "}": "{"}[character]
                if stack and stack[-1].opening == expected_open:
                    stack.pop()
            elif character == "," and stack and stack[-1].opening == "(":
                frame = stack[-1]
                stack[-1] = _Delimiter(
                    frame.opening,
                    frame.query_head,
                    frame.argument_index + 1,
                )
            index += 1
        return next(
            (frame for frame in reversed(stack) if frame.opening == "("),
            None,
        )

    def _root_candidates(
        self,
        cursor: QueryCursor,
    ) -> tuple[QueryAuthoringCandidate, ...]:
        candidates: list[QueryAuthoringCandidate] = []
        for head, descriptor in self.functions.items():
            if "::" in head or not head.startswith(cursor.prefix):
                continue
            if not descriptor.result_kinds & cursor.expected_kinds:
                continue
            candidates.append(
                self._function_candidate(
                    head,
                    descriptor,
                    cursor.replacement_start,
                    exact=head == cursor.prefix,
                )
            )
        for namespace in self.namespace_children.get("", ()):
            if not namespace.startswith(cursor.prefix):
                continue
            if not self._namespace_result_kinds(namespace) & cursor.expected_kinds:
                continue
            candidates.append(
                QueryAuthoringCandidate(
                    namespace,
                    namespace,
                    cursor.replacement_start,
                    "TSIL query namespace",
                    "namespace",
                    (":",),
                )
            )
        return tuple(candidates)

    def _path_candidates(
        self,
        cursor: QueryCursor,
    ) -> tuple[QueryAuthoringCandidate, ...]:
        if _VALID_PATH.fullmatch(cursor.prefix) is None:
            return ()
        namespace, separator, child_prefix = cursor.prefix.rpartition("::")
        if not separator or namespace not in self.namespace_children:
            return ()
        replacement_start = cursor.replacement_start + len(namespace) + len(separator)
        candidates: list[QueryAuthoringCandidate] = []
        for child in self.namespace_children[namespace]:
            if not child.startswith(child_prefix):
                continue
            path = f"{namespace}::{child}"
            descriptor = self.functions.get(path)
            leaf_namespace = self.leaf_namespaces.get(namespace)
            if descriptor is not None:
                if not descriptor.result_kinds & cursor.expected_kinds:
                    continue
                if child == child_prefix and not descriptor.arguments:
                    continue
                candidates.append(
                    self._function_candidate(
                        child,
                        descriptor,
                        replacement_start,
                        exact=child == child_prefix,
                    )
                )
            elif leaf_namespace is not None and child in leaf_namespace.values:
                if not leaf_namespace.result_kinds & cursor.expected_kinds:
                    continue
                if child == child_prefix:
                    continue
                candidates.append(
                    QueryAuthoringCandidate(
                        child,
                        child,
                        replacement_start,
                        "scalar type query leaf",
                        "type",
                    )
                )
            elif path in self.namespace_children:
                if not self._namespace_result_kinds(path) & cursor.expected_kinds:
                    continue
                candidates.append(
                    QueryAuthoringCandidate(
                        child,
                        child,
                        replacement_start,
                        "TSIL query namespace",
                        "namespace",
                        (":",),
                    )
                )
        return tuple(candidates)

    @staticmethod
    def _function_candidate(
        label: str,
        descriptor: QueryFunctionDescriptor,
        replacement_start: int,
        *,
        exact: bool,
    ) -> QueryAuthoringCandidate:
        argument_details = ", ".join(
            "/".join(sorted(argument.kinds)) for argument in descriptor.arguments
        )
        optional = "?" if descriptor.minimum_arguments < len(descriptor.arguments) else ""
        signature = f"({argument_details}{optional})" if descriptor.arguments else ""
        results = "/".join(sorted(descriptor.result_kinds))
        description = "TSIL query"
        if signature:
            description = f"{description} {signature}"
        return QueryAuthoringCandidate(
            label,
            label,
            replacement_start,
            f"{description} → {results}",
            "function",
            ("(",) if descriptor.arguments or exact else (),
        )

    @staticmethod
    def _scope_candidates(
        cursor: QueryCursor,
        symbols: tuple[QueryScopeSymbol, ...],
    ) -> tuple[QueryAuthoringCandidate, ...]:
        return tuple(
            QueryAuthoringCandidate(
                symbol.name,
                symbol.name,
                cursor.replacement_start,
                symbol.detail,
                "type" if symbol.kinds == frozenset({"type"}) else "value",
            )
            for symbol in symbols
            if symbol.role == cursor.role
            and symbol.name.startswith(cursor.prefix)
            and symbol.kinds & cursor.expected_kinds
            and symbol.name != cursor.prefix
        )

    def _namespace_result_kinds(self, namespace: str) -> frozenset[QueryValueKind]:
        kinds: set[QueryValueKind] = set()
        prefix = f"{namespace}::"
        for head, descriptor in self.functions.items():
            if head.startswith(prefix):
                kinds.update(descriptor.result_kinds)
        leaf = self.leaf_namespaces.get(namespace)
        if leaf is not None:
            kinds.update(leaf.result_kinds)
        return frozenset(kinds)


def _can_start_expression(text: str) -> bool:
    stripped = text.rstrip()
    if not stripped:
        return True
    if len(stripped) != len(text) and (
        stripped[-1].isalnum() or stripped[-1] in '_")]}\''
    ):
        return False
    return stripped[-1] in "(,[=:+-*/%!&|?"


def _skip_opaque(text: str, index: int) -> int | None:
    if text.startswith("//", index):
        newline = text.find("\n", index + 2)
        return len(text) if newline < 0 else newline + 1
    if text.startswith("/*", index):
        close = text.find("*/", index + 2)
        return len(text) if close < 0 else close + 2
    if text[index] not in {'"', "'"}:
        return None
    quote = text[index]
    position = index + 1
    while position < len(text):
        if text[position] == "\\":
            position += 2
            continue
        if text[position] == quote:
            return position + 1
        position += 1
    return len(text)


DEFAULT_QUERY_AUTHORING_INDEX = QueryAuthoringIndex(
    DEFAULT_QUERY_FUNCTIONS,
    DEFAULT_QUERY_LEAF_NAMESPACES,
)


__all__ = (
    "DEFAULT_QUERY_AUTHORING_INDEX",
    "QueryAuthoringCandidate",
    "QueryAuthoringIndex",
    "QueryCursor",
    "QueryScopeSymbol",
)
