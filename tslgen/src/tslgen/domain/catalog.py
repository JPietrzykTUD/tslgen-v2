from __future__ import annotations

from ast import literal_eval
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Literal, cast

from tslgen.core.diagnostics import Diagnostic, SourceSpan
from tslgen.core.frozen_map import FrozenMap
from tslgen.core.ordering import stable_sorted
from tslgen.core.result import Result
from tslgen.domain.extensions import Extension
from tslgen.domain.primitives import (
    PrimitiveAttribute,
    PrimitiveDeclaration,
    PrimitiveParameter,
)
from tslgen.domain.templates import OperationTemplate
from tslgen.domain.types import LaneSet, TypeGroup
from tslgen.domain.values import CatalogMap, CatalogValue
from tslgen.syntax.ast import ParsedDocument, ParsedDocumentSet, SyntaxNode


type _DuplicatePolicy = Literal["error", "group"]


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    kind: str
    name: str
    fields: CatalogMap
    source_span: SourceSpan

    def __post_init__(self) -> None:
        if not self.kind:
            raise ValueError("catalog entry kind must be non-empty")
        if not self.name:
            raise ValueError("catalog entry name must be non-empty")


@dataclass(frozen=True, slots=True)
class SourceCatalogMetadata:
    logical_path: PurePosixPath
    fields: CatalogMap
    source_span: SourceSpan

    def __post_init__(self) -> None:
        object.__setattr__(self, "logical_path", PurePosixPath(self.logical_path))


@dataclass(frozen=True, slots=True)
class Catalog:
    type_groups: tuple[TypeGroup, ...] = ()
    lane_sets: tuple[LaneSet, ...] = ()
    extensions: tuple[Extension, ...] = ()
    templates: tuple[OperationTemplate, ...] = ()
    primitives: tuple[PrimitiveDeclaration, ...] = ()
    entries: tuple[CatalogEntry, ...] = ()
    source_metadata: tuple[SourceCatalogMetadata, ...] = ()
    type_groups_by_name: FrozenMap[str, TypeGroup] = field(init=False)
    lane_sets_by_name: FrozenMap[str, LaneSet] = field(init=False)
    extensions_by_name: FrozenMap[str, Extension] = field(init=False)
    templates_by_name: FrozenMap[str, OperationTemplate] = field(init=False)
    primitives_by_id: FrozenMap[str, PrimitiveDeclaration] = field(init=False)

    def __post_init__(self) -> None:
        type_groups = stable_sorted(self.type_groups, key=lambda item: item.name)
        lane_sets = stable_sorted(self.lane_sets, key=lambda item: item.name)
        extensions = stable_sorted(self.extensions, key=lambda item: item.name)
        templates = stable_sorted(self.templates, key=lambda item: item.name)
        primitives = stable_sorted(self.primitives, key=lambda item: item.catalog_id)
        entries = stable_sorted(self.entries, key=lambda item: (item.kind, item.name))
        source_metadata = stable_sorted(
            self.source_metadata,
            key=lambda item: item.logical_path.as_posix(),
        )

        object.__setattr__(self, "type_groups", type_groups)
        object.__setattr__(self, "lane_sets", lane_sets)
        object.__setattr__(self, "extensions", extensions)
        object.__setattr__(self, "templates", templates)
        object.__setattr__(self, "primitives", primitives)
        object.__setattr__(self, "entries", entries)
        object.__setattr__(self, "source_metadata", source_metadata)
        object.__setattr__(
            self,
            "type_groups_by_name",
            FrozenMap((item.name, item) for item in type_groups),
        )
        object.__setattr__(
            self,
            "lane_sets_by_name",
            FrozenMap((item.name, item) for item in lane_sets),
        )
        object.__setattr__(
            self,
            "extensions_by_name",
            FrozenMap((item.name, item) for item in extensions),
        )
        object.__setattr__(
            self,
            "templates_by_name",
            FrozenMap((item.name, item) for item in templates),
        )
        object.__setattr__(
            self,
            "primitives_by_id",
            FrozenMap((item.catalog_id, item) for item in primitives),
        )

    def primitive_declarations(self, name: str) -> tuple[PrimitiveDeclaration, ...]:
        return tuple(primitive for primitive in self.primitives if primitive.name == name)


def build_catalog(parsed: ParsedDocument | ParsedDocumentSet) -> Result[Catalog]:
    builder = _CatalogBuilder()
    for document in _documents(parsed):
        builder.add_document(document)

    if builder.diagnostics:
        return Result.failure(builder.diagnostics)
    return Result.ok(builder.catalog())


_BLOCK_KINDS = frozenset(
    {
        "pair",
        "primitive_block",
        "template_block",
        "extension_block",
        "types_block",
        "flags_block",
        "language_block",
        "translation_block",
        "lane_set_block",
    }
)
_VALUE_KINDS = frozenset(
    {
        "string",
        "multiline_string",
        "number",
        "bool",
        "wildcard",
        "bare",
        "list",
        "list_block",
        "attr_list_nonempty",
        "map",
    }
)
_MAP_PAIR_KINDS = frozenset(
    {
        "pair_inline",
        "pair_inline_colon",
        "pair_inline_block",
        "map_pair_line",
    }
)
_IGNORED_KINDS = frozenset(
    {
        "NEWLINE",
        "LBRACE",
        "RBRACE",
        "LSQB",
        "RSQB",
        "LPAR",
        "RPAR",
        "LT",
        "GT",
        "DASH",
    }
)
_KEY_TOKEN_KINDS = frozenset(
    {
        "NAME",
        "PRIM",
        "TEMPLATE",
        "TYPES",
        "FLAGS",
        "LANGUAGE",
        "OPERATION",
        "TRANSLATION",
        "GENERIC_PARAMS",
        "LANE_SET",
        "EXTENSION",
    }
)


class _CatalogBuilder:
    def __init__(self) -> None:
        self.diagnostics: list[Diagnostic] = []
        self._type_groups: list[TypeGroup] = []
        self._lane_sets: list[LaneSet] = []
        self._extensions: list[Extension] = []
        self._templates: list[OperationTemplate] = []
        self._primitives: list[PrimitiveDeclaration] = []
        self._entries: list[CatalogEntry] = []
        self._source_metadata: list[SourceCatalogMetadata] = []
        self._seen: set[tuple[str, str]] = set()

    def add_document(self, document: ParsedDocument) -> None:
        metadata_pairs: list[SyntaxNode] = []
        for statement in _top_level_statements(document.root):
            match statement.kind:
                case "types_block":
                    self._add_type_groups(statement)
                case "lane_set_block":
                    self._add_lane_set(statement)
                case "extension_block":
                    self._add_extension(statement)
                case "template_block":
                    self._add_template(statement)
                case "primitive_block":
                    self._add_primitive(statement)
                case "flags_block":
                    self._add_generic_block("flags", "flags", statement)
                case "language_block":
                    self._add_named_generic_block("language", statement)
                case "translation_block":
                    self._add_named_generic_block("translation", statement)
                case "pair":
                    metadata_pairs.append(statement)

        if metadata_pairs:
            self._source_metadata.append(
                SourceCatalogMetadata(
                    logical_path=document.logical_path,
                    fields=self._field_map(metadata_pairs, "source metadata", "error"),
                    source_span=metadata_pairs[0].span,
                )
            )

    def catalog(self) -> Catalog:
        return Catalog(
            type_groups=tuple(self._type_groups),
            lane_sets=tuple(self._lane_sets),
            extensions=tuple(self._extensions),
            templates=tuple(self._templates),
            primitives=tuple(self._primitives),
            entries=tuple(self._entries),
            source_metadata=tuple(self._source_metadata),
        )

    def _add_type_groups(self, block: SyntaxNode) -> None:
        for pair in _field_pairs(block):
            name, value = self._pair_item(pair, "type group")
            if not self._claim_unique("type group", name, pair):
                continue
            if not isinstance(value, FrozenMap):
                self._shape_error(pair, f"type group {name!r} must be a field map")
                continue
            fields = cast(CatalogMap, value)
            members = self._required_string_sequence(fields, "types", pair)
            if members is None:
                continue
            self._type_groups.append(
                TypeGroup(
                    name=name,
                    members=members,
                    fields=fields,
                    source_span=pair.span,
                )
            )

    def _add_lane_set(self, block: SyntaxNode) -> None:
        name = self._required_direct_text(block, "NAME", "lane set")
        if name is None or not self._claim_unique("lane set", name, block):
            return
        fields = self._body_map(block, "lane set")
        lanes = self._required_int_sequence(fields, "lanes", block)
        type_names = self._required_string_sequence(fields, "types", block)
        if lanes is None or type_names is None:
            return
        self._lane_sets.append(
            LaneSet(
                name=name,
                lanes=lanes,
                type_names=type_names,
                fields=fields,
                source_span=block.span,
            )
        )

    def _add_extension(self, block: SyntaxNode) -> None:
        name = self._required_direct_text(block, "NAME", "extension")
        if name is None or not self._claim_unique("extension", name, block):
            return
        fields = self._body_map(block, "extension")
        extension = Extension(
            name=name,
            fields=fields,
            source_span=block.span,
            vendor=self._optional_string(fields, "vendor", block),
            family=self._optional_string(fields, "family", block),
            extension_name=self._optional_string(fields, "extension_name", block),
            vector_bits=self._optional_int_or_string(fields, "vector_bits", block),
        )
        self._extensions.append(extension)

    def _add_template(self, block: SyntaxNode) -> None:
        name = self._required_direct_text(block, "NAME", "template")
        if name is None or not self._claim_unique("template", name, block):
            return
        fields = self._body_map(block, "template")
        self._templates.append(
            OperationTemplate(
                name=name,
                fields=fields,
                source_span=block.span,
                description=self._optional_string(fields, "description", block),
                shape=self._optional_string(fields, "shape", block),
                required_fields=self._optional_string_sequence(
                    fields,
                    "required_fields",
                    block,
                ),
                optional_fields=self._optional_string_sequence(
                    fields,
                    "optional_fields",
                    block,
                ),
            )
        )

    def _add_primitive(self, block: SyntaxNode) -> None:
        name = self._required_direct_text(block, "NAME", "primitive")
        signature = self._required_direct_text(block, "SIGNATURE", "primitive")
        if name is None or signature is None:
            return
        primitive = PrimitiveDeclaration(
            name=name,
            signature=signature,
            parameters=tuple(
                PrimitiveParameter(name=parameter_name, source_span=parameter.span)
                for parameter in _direct_children(block, "param")
                if (parameter_name := self._required_direct_text(parameter, "NAME", "parameter"))
                is not None
            ),
            attributes=self._primitive_attributes(block),
            fields=self._body_map(block, "primitive"),
            source_span=block.span,
        )
        if not self._claim_unique("primitive", primitive.catalog_id, block):
            return
        self._primitives.append(primitive)

    def _add_generic_block(self, kind: str, name: str, block: SyntaxNode) -> None:
        if not self._claim_unique(kind, name, block):
            return
        self._entries.append(
            CatalogEntry(
                kind=kind,
                name=name,
                fields=self._body_map(block, kind),
                source_span=block.span,
            )
        )

    def _add_named_generic_block(self, kind: str, block: SyntaxNode) -> None:
        name = self._required_direct_text(block, "NAME", kind)
        if name is None:
            return
        self._add_generic_block(kind, name, block)

    def _primitive_attributes(self, block: SyntaxNode) -> tuple[PrimitiveAttribute, ...]:
        attributes: list[PrimitiveAttribute] = []
        for attr_list in _direct_children(block, "attr_list"):
            for attr_pair in _direct_children(attr_list, "attr_pair"):
                key_node = _first_direct_child(attr_pair, "attr_key")
                if key_node is None:
                    self._shape_error(attr_pair, "primitive attribute is missing a key")
                    continue
                name, argument = self._attribute_key(key_node)
                value_node = _first_value_child(attr_pair)
                if value_node is None:
                    self._shape_error(attr_pair, f"primitive attribute {name!r} is missing a value")
                    continue
                attributes.append(
                    PrimitiveAttribute(
                        name=name,
                        argument=argument,
                        value=self._value(value_node, f"primitive attribute {name!r}"),
                        source_span=attr_pair.span,
                    )
                )
        return tuple(attributes)

    def _attribute_key(self, node: SyntaxNode) -> tuple[str, str | None]:
        names = [child.text for child in _direct_children(node, "NAME") if child.text is not None]
        if not names:
            self._shape_error(node, "primitive attribute key must contain a name")
            return "", None
        argument = names[1] if len(names) > 1 else None
        return names[0], argument

    def _body_map(self, node: SyntaxNode, context: str) -> CatalogMap:
        return self._field_map(_field_pairs(node), context, "error")

    def _field_map(
        self,
        pairs: list[SyntaxNode],
        context: str,
        duplicate_policy: _DuplicatePolicy,
    ) -> CatalogMap:
        items = [self._pair_item(pair, context) for pair in pairs]
        return self._frozen_map(items, pairs[0] if pairs else None, context, duplicate_policy)

    def _pair_item(self, pair: SyntaxNode, context: str) -> tuple[str, CatalogValue]:
        key_node = _first_direct_child(pair, "key")
        if key_node is None:
            self._shape_error(pair, f"{context} entry is missing a key")
            return "", None
        key = self._key(key_node)
        tail = _tail_after_first(pair, key_node)
        return key, self._value_from_tail(tail, pair, f"{context} field {key!r}")

    def _value_from_tail(
        self,
        tail: list[SyntaxNode],
        owner: SyntaxNode,
        context: str,
    ) -> CatalogValue:
        semantic_tail = [child for child in tail if child.kind not in _IGNORED_KINDS]
        if len(semantic_tail) == 1:
            child = semantic_tail[0]
            if child.kind == "stmt_list":
                return self._field_map(_field_pairs(child), context, "group")
            if child.kind == "list_block":
                return self._value(child, context)
            if child.kind in _VALUE_KINDS:
                return self._value(child, context)
            if child.kind == "pair":
                return self._field_map([child], context, "group")
        if semantic_tail and all(child.kind == "pair" for child in semantic_tail):
            return self._field_map(semantic_tail, context, "group")

        self._shape_error(owner, f"{context} has unsupported catalog shape")
        return None

    def _value(self, node: SyntaxNode, context: str) -> CatalogValue:
        match node.kind:
            case "string" | "multiline_string":
                return self._quoted_string(node, context)
            case "number":
                return self._number(node, context)
            case "bool":
                text = self._required_leaf_text(node, "BOOL", context)
                return text.casefold() == "true" if text is not None else None
            case "wildcard":
                return "*"
            case "bare":
                return self._required_leaf_text(node, "NAME", context)
            case "list":
                return tuple(
                    self._value(child, context)
                    for child in node.children
                    if child.kind in _VALUE_KINDS
                )
            case "list_block":
                return tuple(
                    self._list_item_value(child, context)
                    for child in _direct_children(node, "list_item")
                )
            case "list_item":
                return self._list_item_value(node, context)
            case "attr_list_nonempty":
                return self._attribute_map(node, context)
            case "map":
                return self._map(node, context)

        self._shape_error(node, f"{context} has unsupported value node {node.kind!r}")
        return None

    def _list_item_value(self, node: SyntaxNode, context: str) -> CatalogValue:
        value_node = _first_value_child(node)
        if value_node is None:
            self._shape_error(node, f"{context} list item is missing a value")
            return None
        return self._value(value_node, context)

    def _attribute_map(self, node: SyntaxNode, context: str) -> CatalogMap:
        items: list[tuple[str, CatalogValue]] = []
        for attr_pair in _direct_children(node, "attr_pair"):
            key_node = _first_direct_child(attr_pair, "attr_key")
            if key_node is None:
                self._shape_error(attr_pair, f"{context} attribute is missing a key")
                continue
            name, argument = self._attribute_key(key_node)
            key = name if argument is None else f"{name}({argument})"
            value_node = _first_value_child(attr_pair)
            if value_node is None:
                self._shape_error(attr_pair, f"{context} attribute {key!r} is missing a value")
                continue
            items.append((key, self._value(value_node, context)))
        return self._frozen_map(items, node, context, "error")

    def _map(self, node: SyntaxNode, context: str) -> CatalogMap:
        for child in node.children:
            if child.kind in {"map_inline", "map_multiline"}:
                return self._map_container(child, context)
        return FrozenMap.empty()

    def _map_container(self, node: SyntaxNode, context: str) -> CatalogMap:
        if node.kind == "map_pair_line":
            children = [child for child in node.children if child.kind not in _IGNORED_KINDS]
            if len(children) == 1 and children[0].kind in _MAP_PAIR_KINDS:
                return self._map_container(children[0], context)

        if node.kind in _MAP_PAIR_KINDS:
            key_node = _first_direct_child(node, "key")
            if key_node is None:
                self._shape_error(node, f"{context} map entry is missing a key")
                return FrozenMap.empty()
            key = self._key(key_node)
            value = self._value_from_tail(_tail_after_first(node, key_node), node, context)
            return self._frozen_map([(key, value)], node, context, "group")

        items: list[tuple[str, CatalogValue]] = []
        for child in node.children:
            if child.kind in _MAP_PAIR_KINDS:
                single = self._map_container(child, context)
                items.extend(single.items())
        return self._frozen_map(items, node, context, "group")

    def _key(self, node: SyntaxNode) -> str:
        if node.kind == "key":
            semantic_children = [child for child in node.children if child.kind not in _IGNORED_KINDS]
            if len(semantic_children) == 1:
                return self._key(semantic_children[0])
        if node.kind in _KEY_TOKEN_KINDS and node.text is not None:
            return node.text
        if node.kind == "ESCAPED_STRING" and node.text is not None:
            return cast(str, literal_eval(node.text))
        if node.kind == "key_list":
            items = [self._key(child) for child in _direct_children(node, "key_list_item")]
            return f"[{', '.join(items)}]"
        if node.kind == "key_list_item":
            semantic_children = [child for child in node.children if child.kind not in _IGNORED_KINDS]
            if len(semantic_children) == 1:
                return self._key(semantic_children[0])
        if node.kind == "key_list_parameterized_item":
            name = self._required_direct_text(node, "NAME", "key list item") or ""
            parameter_node = _first_direct_child(node, "key_list_parameter")
            parameter = self._key(parameter_node) if parameter_node is not None else ""
            return f"{name}<{parameter}>"
        if node.kind == "key_list_parameter":
            semantic_children = [child for child in node.children if child.kind not in _IGNORED_KINDS]
            if len(semantic_children) == 1:
                return self._key(semantic_children[0])
        if node.kind == "SIGNED_NUMBER" and node.text is not None:
            return node.text

        self._shape_error(node, f"unsupported key shape {node.kind!r}")
        return ""

    def _quoted_string(self, node: SyntaxNode, context: str) -> str | None:
        token = _first_direct_child(node, "ESCAPED_STRING") or _first_direct_child(
            node,
            "MULTILINE_STRING",
        )
        if token is None or token.text is None:
            self._shape_error(node, f"{context} string is missing source text")
            return None
        value = literal_eval(token.text)
        if not isinstance(value, str):
            self._shape_error(node, f"{context} string did not decode to text")
            return None
        return value

    def _number(self, node: SyntaxNode, context: str) -> int | float | None:
        text = self._required_leaf_text(node, "SIGNED_NUMBER", context)
        if text is None:
            return None
        if any(marker in text for marker in (".", "e", "E")):
            return float(text)
        return int(text)

    def _required_leaf_text(
        self,
        node: SyntaxNode,
        token_kind: str,
        context: str,
    ) -> str | None:
        text = self._first_direct_text(node, token_kind)
        if text is None:
            self._shape_error(node, f"{context} is missing {token_kind}")
        return text

    def _required_direct_text(
        self,
        node: SyntaxNode,
        token_kind: str,
        context: str,
    ) -> str | None:
        text = self._first_direct_text(node, token_kind)
        if text is None:
            self._shape_error(node, f"{context} is missing {token_kind}")
        return text

    def _first_direct_text(self, node: SyntaxNode, token_kind: str) -> str | None:
        child = _first_direct_child(node, token_kind)
        return child.text if child is not None else None

    def _required_string_sequence(
        self,
        fields: CatalogMap,
        field_name: str,
        node: SyntaxNode,
    ) -> tuple[str, ...] | None:
        value = fields.get(field_name)
        if value is None:
            self._missing_field(node, field_name)
            return None
        sequence = self._string_sequence(value, field_name, node)
        return sequence

    def _optional_string_sequence(
        self,
        fields: CatalogMap,
        field_name: str,
        node: SyntaxNode,
    ) -> tuple[str, ...]:
        value = fields.get(field_name)
        if value is None:
            return ()
        sequence = self._string_sequence(value, field_name, node)
        return sequence if sequence is not None else ()

    def _required_int_sequence(
        self,
        fields: CatalogMap,
        field_name: str,
        node: SyntaxNode,
    ) -> tuple[int, ...] | None:
        value = fields.get(field_name)
        if value is None:
            self._missing_field(node, field_name)
            return None
        if not isinstance(value, tuple) or not all(
            isinstance(item, int) and not isinstance(item, bool) for item in value
        ):
            self._shape_error(node, f"field {field_name!r} must be a list of integers")
            return None
        return cast(tuple[int, ...], value)

    def _string_sequence(
        self,
        value: CatalogValue,
        field_name: str,
        node: SyntaxNode,
    ) -> tuple[str, ...] | None:
        if not isinstance(value, tuple) or not all(isinstance(item, str) for item in value):
            self._shape_error(node, f"field {field_name!r} must be a list of strings")
            return None
        return cast(tuple[str, ...], value)

    def _optional_string(
        self,
        fields: CatalogMap,
        field_name: str,
        node: SyntaxNode,
    ) -> str | None:
        value = fields.get(field_name)
        if value is None:
            return None
        if not isinstance(value, str):
            self._shape_error(node, f"field {field_name!r} must be a string")
            return None
        return value

    def _optional_int_or_string(
        self,
        fields: CatalogMap,
        field_name: str,
        node: SyntaxNode,
    ) -> int | str | None:
        value = fields.get(field_name)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int | str):
            self._shape_error(node, f"field {field_name!r} must be an integer or string")
            return None
        return value

    def _frozen_map(
        self,
        items: list[tuple[str, CatalogValue]],
        node: SyntaxNode | None,
        context: str,
        duplicate_policy: _DuplicatePolicy,
    ) -> CatalogMap:
        grouped: dict[str, list[CatalogValue]] = {}
        for key, value in items:
            if key in grouped and duplicate_policy == "error":
                self._duplicate_error(node, context, key)
                continue
            grouped.setdefault(key, []).append(value)

        return FrozenMap(
            (key, values[0] if len(values) == 1 else tuple(values))
            for key, values in grouped.items()
        )

    def _claim_unique(self, kind: str, name: str, node: SyntaxNode) -> bool:
        key = (kind, name)
        if key in self._seen:
            self._duplicate_error(node, kind, name)
            return False
        self._seen.add(key)
        return True

    def _missing_field(self, node: SyntaxNode, field_name: str) -> None:
        self.diagnostics.append(
            Diagnostic.error(
                "TSL-CAT-MISSING-FIELD",
                f"catalog entry is missing required field {field_name!r}",
                location=node.span.location,
            )
        )

    def _shape_error(self, node: SyntaxNode, message: str) -> None:
        self.diagnostics.append(
            Diagnostic.error(
                "TSL-CAT-SHAPE",
                message,
                location=node.span.location,
            )
        )

    def _duplicate_error(
        self,
        node: SyntaxNode | None,
        context: str,
        name: str,
    ) -> None:
        self.diagnostics.append(
            Diagnostic.error(
                "TSL-CAT-DUPLICATE",
                f"duplicate {context} entry {name!r}",
                location=node.span.location if node is not None else None,
            )
        )


def _documents(parsed: ParsedDocument | ParsedDocumentSet) -> tuple[ParsedDocument, ...]:
    if isinstance(parsed, ParsedDocument):
        return (parsed,)
    return parsed.documents


def _top_level_statements(root: SyntaxNode) -> tuple[SyntaxNode, ...]:
    statements: list[SyntaxNode] = []
    for child in root.children:
        if child.kind == "stmt_list":
            statements.extend(_direct_statements(child))
        elif child.kind in _BLOCK_KINDS:
            statements.append(child)
    return tuple(statements)


def _direct_statements(node: SyntaxNode) -> list[SyntaxNode]:
    return [child for child in node.children if child.kind in _BLOCK_KINDS]


def _field_pairs(node: SyntaxNode) -> list[SyntaxNode]:
    pairs: list[SyntaxNode] = []
    for child in node.children:
        if child.kind == "pair":
            pairs.append(child)
        elif child.kind == "stmt_list":
            pairs.extend(_field_pairs(child))
    return pairs


def _direct_children(node: SyntaxNode, kind: str) -> tuple[SyntaxNode, ...]:
    return tuple(child for child in node.children if child.kind == kind)


def _first_direct_child(node: SyntaxNode, kind: str) -> SyntaxNode | None:
    return next((child for child in node.children if child.kind == kind), None)


def _first_value_child(node: SyntaxNode) -> SyntaxNode | None:
    return next((child for child in node.children if child.kind in _VALUE_KINDS), None)


def _tail_after_first(node: SyntaxNode, child: SyntaxNode) -> list[SyntaxNode]:
    for index, current in enumerate(node.children):
        if current is child:
            return list(node.children[index + 1 :])
    return []
