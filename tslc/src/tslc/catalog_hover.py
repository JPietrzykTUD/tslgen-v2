"""Hover presentation derived from typed catalog and index facts."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from tslc.catalog.arithmetic import (
    ARITHMETIC_GUARANTEE_SPECS,
    ARITHMETIC_OPERAND_ROLE_DESCRIPTIONS,
    ARITHMETIC_OPERATION_DESCRIPTIONS,
)
from tslc.catalog.conversion import (
    CONVERSION_KIND_DESCRIPTIONS,
    LANE_COUNT_RELATION_DESCRIPTIONS,
    NUMERIC_CONVERSION_MODE_DESCRIPTIONS,
)
from tslc.catalog.memory import MEMORY_ACCESS_DESCRIPTIONS, MEMORY_ADDRESSING_DESCRIPTIONS
from tslc.catalog.model import Catalog, Primitive
from tslc.catalog.semantics import OPERAND_ROLE_DESCRIPTIONS, PRIMITIVE_OPERATION_DESCRIPTIONS
from tslc.catalog.shift import SHIFT_COUNT_RULE_DESCRIPTIONS, SHIFT_LANE_RULE_DESCRIPTIONS
from tslc.catalog_index_model import SymbolKind, sorted_spans
from tslc.diagnostics import SourceSpan
from tslc.ir.region_registry import DEFAULT_TSIL_REGION_DESCRIPTORS

_TSIL_REGION_GUIDE = (
    "https://github.com/JPietrzykTUD/tslgen-v2/blob/main/docs/tsil-keywords.md"
)


def hover_text(
    catalog: Catalog,
    definitions: Mapping[SymbolKind, Mapping[str, Iterable[SourceSpan]]],
) -> dict[tuple[SymbolKind, str], str]:
    hover: dict[tuple[SymbolKind, str], str] = {}
    for name in sorted({primitive.name for primitive in catalog.primitives}):
        declarations = {
            (
                primitive.signature,
                primitive.parameters,
                primitive.brief_description,
                primitive.header_source,
            )
            for primitive in catalog.primitives_named(name, unmasked=False)
        }
        lines = [f"**Primitive** `{name}`", "", "**Declarations**", ""]
        for signature, parameters, brief, source in sorted(
            declarations,
            key=lambda item: (*_optional_span_key(item[3]), item[0], item[1]),
        ):
            declaration = f"prim<{signature}> {name}({', '.join(parameters)})"
            line = f"- `{declaration}`"
            if brief:
                line += f" — {brief}"
            if source is not None:
                line += f" ([{source.path.name}:{source.line}]({_source_uri(source)}))"
            lines.append(line)
        hover[("primitive", name)] = "\n".join(lines)
    for name, extension in sorted(catalog.extensions.items()):
        parts = [f"**Extension** `{name}`"]
        if extension.family:
            parts.append(f"**Family:** `{extension.family}`")
        if extension.inherits:
            parts.append(f"**Inherits:** `{extension.inherits}`")
        if extension.vector_bits:
            width = f"{extension.vector_bits} bits"
            if extension.vector_bits_kind:
                width += f" (`{extension.vector_bits_kind}`)"
            parts.append(f"**Width:** {width}")
        elif extension.vector_bits_kind in {"scalable", "sized"}:
            parts.append(f"**Width:** {extension.vector_bits_kind}")
        backends = tuple(
            sorted(
                backend
                for backend, supported in extension.backend_supported.items()
                if supported
            )
        )
        if backends:
            parts.append(f"**Supported backends:** {_inline_code(backends)}")
        target_features = tuple(sorted(extension.active_when.target_features))
        if target_features:
            parts.append(
                f"**Required target features:** {_inline_code(target_features)}"
            )
        compile_modes = tuple(sorted(extension.active_when.compile_modes))
        if compile_modes:
            parts.append(f"**Required compile modes:** {_inline_code(compile_modes)}")
        if extension.source is not None:
            parts.append(
                f"[Declaration: {extension.source.path.name}:{extension.source.line}]"
                f"({_source_uri(extension.source)})"
            )
        hover[("extension", name)] = "\n\n".join(parts)
    for name, members in sorted(catalog.type_groups.items()):
        parts = [f"**Type group** `{name}`", _inline_code(members)]
        declaration_links = _declaration_links(
            definitions["type-group"].get(name, ())
        )
        if declaration_links:
            parts.append(f"**Declared at:** {', '.join(declaration_links)}")
        hover[("type-group", name)] = "\n\n".join(parts)
    for descriptor in DEFAULT_TSIL_REGION_DESCRIPTORS:
        forms = "\n".join(f"- `{form}`" for form in descriptor.accepted_forms)
        guide = f"{_TSIL_REGION_GUIDE}#{descriptor.keyword}"
        hover[("region", descriptor.keyword)] = "\n\n".join(
            (
                f"**TSIL region** `{descriptor.keyword}`",
                descriptor.purpose,
                f"**Accepted forms**\n\n{forms}",
                f"[TSIL region guide]({guide})",
            )
        )
    for name, axis in catalog.overload_registry.axes.items():
        hover[("overload-axis", name)] = "\n\n".join(
            (
                f"**Overload axis** `{name}`",
                f"**Values:** {_inline_code(axis.values)}",
            )
        )
    for operation, description in ARITHMETIC_OPERATION_DESCRIPTIONS.items():
        hover[("arithmetic-operation", operation.value)] = "\n\n".join(
            (f"**Arithmetic operation** `{operation.value}`", description)
        )
    for role, description in ARITHMETIC_OPERAND_ROLE_DESCRIPTIONS.items():
        hover[("arithmetic-role", role.value)] = "\n\n".join(
            (f"**Arithmetic operand role** `{role.value}`", description)
        )
    for guarantee, spec in ARITHMETIC_GUARANTEE_SPECS.items():
        facts = [f"**Arithmetic guarantee** `{guarantee.value}`", spec.description]
        required = spec.required_all_operations | spec.required_any_operations
        if required:
            facts.append(
                "**Operations:** "
                + _inline_code(sorted(item.value for item in required))
            )
        if spec.numeric_domain is not None:
            facts.append(f"**Numeric domain:** `{spec.numeric_domain.value}`")
        hover[("arithmetic-guarantee", guarantee.value)] = "\n\n".join(facts)
    semantic_descriptions: tuple[
        tuple[SymbolKind, str, Iterable[tuple[object, str]]], ...
    ] = (
        ("primitive-operation", "Primitive operation", PRIMITIVE_OPERATION_DESCRIPTIONS.items()),
        ("operand-role", "Operand role", OPERAND_ROLE_DESCRIPTIONS.items()),
        ("memory-access", "Memory access", MEMORY_ACCESS_DESCRIPTIONS.items()),
        ("memory-addressing", "Memory addressing", MEMORY_ADDRESSING_DESCRIPTIONS.items()),
        ("conversion-kind", "Conversion kind", CONVERSION_KIND_DESCRIPTIONS.items()),
        ("lane-count-relation", "Lane-count relation", LANE_COUNT_RELATION_DESCRIPTIONS.items()),
        ("numeric-conversion-mode", "Numeric conversion mode", NUMERIC_CONVERSION_MODE_DESCRIPTIONS.items()),
        ("shift-count-rule", "Shift count rule", SHIFT_COUNT_RULE_DESCRIPTIONS.items()),
        ("shift-lane-rule", "Shift lane rule", SHIFT_LANE_RULE_DESCRIPTIONS.items()),
    )
    for symbol_kind, label, descriptions in semantic_descriptions:
        for value, description in descriptions:
            enum_value = str(value)
            hover[(symbol_kind, enum_value)] = "\n\n".join(
                (f"**{label}** `{enum_value}`", description)
            )
    return hover


def overload_value_hover(catalog: Catalog) -> dict[tuple[str, str], str]:
    return {
        (axis_name, value_name): "\n\n".join(
            (
                f"**Overload value** `{axis_name}={value_name}`",
                f"**Accepted operand kinds:** {_inline_code(value.operand_kinds)}",
            )
        )
        for axis_name, axis in catalog.overload_registry.axes.items()
        for value_name, value in axis.values.items()
    }


def arithmetic_operand_hover(catalog: Catalog) -> dict[tuple[str, str], str]:
    hover: dict[tuple[str, str], str] = {}
    for primitive in catalog.primitives:
        contract = primitive.arithmetic
        scope = _primitive_scope(primitive)
        if contract is None or scope is None:
            continue
        for binding in contract.operand_bindings:
            hover[(scope, binding.parameter_name)] = "\n\n".join(
                (
                    f"**Arithmetic operand** `{binding.parameter_name}`",
                    f"**Role:** `{binding.role.value}`",
                    f"**Resolved signature kind:** `{binding.parameter_kind}`",
                    f"**Parameter index:** `{binding.parameter_index}`",
                    f"**Non-mask ordinal:** `{binding.non_mask_ordinal}`",
                )
            )
    return hover


def semantic_operand_hover(catalog: Catalog) -> dict[tuple[str, str], str]:
    hover: dict[tuple[str, str], str] = {}
    for primitive in catalog.primitives:
        contract = primitive.operation
        scope = _primitive_scope(primitive)
        if contract is None or scope is None:
            continue
        for binding in contract.operand_bindings:
            hover[(scope, binding.parameter_name)] = "\n\n".join(
                (
                    f"**Semantic operand** `{binding.parameter_name}`",
                    f"**Role:** `{binding.role.value}`",
                    f"**Resolved signature kind:** `{binding.parameter_kind}`",
                    f"**Parameter index:** `{binding.parameter_index}`",
                )
            )
    return hover


def _primitive_scope(primitive: Primitive) -> str | None:
    source = primitive.header_source or primitive.source
    if source is None:
        return None
    return f"{source.path.resolve().as_posix()}:{source.line}:{source.column}:{primitive.name}"


def _optional_span_key(span: SourceSpan | None) -> tuple[str, int, int]:
    if span is None:
        return ("", 0, 0)
    return (span.path.as_posix(), span.line, span.column)


def _source_uri(span: SourceSpan) -> str:
    return f"{span.path.resolve().as_uri()}#L{span.line},{span.column}"


def _declaration_links(spans: Iterable[SourceSpan]) -> tuple[str, ...]:
    return tuple(
        f"[{span.path.name}:{span.line}]({_source_uri(span)})"
        for span in sorted_spans(spans)
    )


def _inline_code(values: Iterable[str]) -> str:
    return ", ".join(f"`{value}`" for value in values)


__all__ = (
    "arithmetic_operand_hover",
    "hover_text",
    "overload_value_hover",
    "semantic_operand_hover",
)
