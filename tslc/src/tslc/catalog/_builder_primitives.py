"""Promotion helpers for primitive declarations."""

from __future__ import annotations

from typing import cast

from tslc.catalog._builder_common import _bool_field
from tslc.catalog._builder_implementations import _implementations_from_entries
from tslc.catalog.arithmetic_promotion import build_arithmetic_contract
from tslc.catalog.benchmark_promotion import build_benchmark_spec
from tslc.catalog.conversion_promotion import build_conversion_contract
from tslc.catalog.memory_promotion import build_memory_contract
from tslc.catalog.semantic_promotion import build_semantic_contract
from tslc.catalog.shift_promotion import build_shift_contract
from tslc.catalog.model import (
    BOOLEAN_WILDCARD_ATTRIBUTES,
    GenericParam,
    GenericParamBaseWidthConstraint,
    GenericParamKind,
    ImmediateParam,
    ParamTypeRule,
    Primitive,
    RESULT_DIMENSIONS,
    RESULT_DIM_VECTOR,
)
from tslc.catalog.param_types import (
    parse_base_width_constraint,
    parse_param_type_condition,
    parse_param_type_expression,
)
from tslc.catalog.overloads import PrimitiveOverload
from tslc.catalog.signatures import parse_signature
from tslc.catalog.test_promotion import build_test_cases
from tslc.diagnostics import Diagnostic, SourceSpan, diagnostic_at
from tslc.syntax.access import child as _child
from tslc.syntax.access import children as _children
from tslc.syntax.access import field_text as _field_text
from tslc.syntax.access import list_text as _list_text
from tslc.syntax.access import source_span as _source_span
from tslc.syntax.ast import (
    ParsedPrimitiveDeclaration,
    ParsedTslAttribute,
    ParsedTslField,
    ParsedTslScalarValue,
)


_BOOLEAN_WILDCARD_VALUES = ("true", "false")


def _build_primitives(
    declaration: ParsedPrimitiveDeclaration,
    extension_names: frozenset[str],
    diagnostics: list[Diagnostic],
) -> list[Primitive]:
    """One declaration -> one Primitive, or several when a boolean wildcard attribute
    (`[aligned=*]`) expands into concrete-value variants."""

    # A representation-change primitive (`return_type: base|extension: Target`) carries a
    # second type axis; its selector nests a `<Target>:` level the impl-walk must split out.
    result_target = _result_target(declaration)
    target_name = (
        result_target[1]
        if result_target is not None and result_target[0] != RESULT_DIM_VECTOR
        else None
    )
    # Walk the selector-entry tree so each body keeps its entry's `requires` flags.
    implementations = tuple(
        _implementations_from_entries(
            declaration.impl_entries, extension_names, target_name
        )
    )
    attribute_keys = tuple(attribute.key.text for attribute in declaration.attributes)
    base_attributes = {a.key.text: _attribute_value(a) for a in declaration.attributes}

    # Per-parameter `sImm` immediate metadata from the `params:` block (type, value_range,
    # per-backend dispatch strategy), keyed by the signature parameter name.
    param_type_rules = _param_type_rules(declaration)
    immediate_params = _immediate_params(declaration, diagnostics)
    generic_params = _generic_params(declaration)
    tests = build_test_cases(declaration, diagnostics)
    benchmark = build_benchmark_spec(declaration)
    brief_description = _primitive_field_text(declaration, "brief_description")
    detailed_description = _primitive_field_text(declaration, "detailed_description")
    semantics = _primitive_field_text(declaration, "semantics")
    arithmetic = build_arithmetic_contract(declaration, diagnostics)
    operation = build_semantic_contract(declaration, diagnostics)
    memory = build_memory_contract(declaration, operation, diagnostics)
    conversion = build_conversion_contract(
        declaration,
        operation,
        result_target,
        diagnostics,
    )
    shift = build_shift_contract(declaration, operation, diagnostics)
    overload = _primitive_overload(declaration)
    cross_lane_fields = declaration.fields_by_name("cross_lane")
    cross_lane = _bool_field(cross_lane_fields[0].field) if cross_lane_fields else False

    def make(attributes: dict[str, str]) -> Primitive:
        return Primitive(
            name=declaration.name,
            signature=declaration.signature,
            parameters=declaration.parameters,
            attribute_keys=attribute_keys,
            implementations=implementations,
            attributes=attributes,
            param_type_rules=param_type_rules,
            immediate_params=immediate_params,
            generic_params=generic_params,
            result_target=result_target,
            tests=tests,
            benchmark=benchmark,
            brief_description=brief_description,
            detailed_description=detailed_description,
            semantics=semantics,
            arithmetic=arithmetic,
            operation=operation,
            memory=memory,
            conversion=conversion,
            shift=shift,
            overload=overload,
            cross_lane=cross_lane,
            source=_source_span(declaration.source),
            header_source=_source_span(declaration.header_source),
            signature_source=_source_span(declaration.signature_source),
        )

    return [make(attrs) for attrs in _expand_wildcards(base_attributes)]


def _primitive_field_text(
    declaration: ParsedPrimitiveDeclaration, name: str
) -> str | None:
    fields = declaration.fields_by_name(name)
    if not fields:
        return None
    return _field_text(fields[0].field)


def _primitive_overload(
    declaration: ParsedPrimitiveDeclaration,
) -> PrimitiveOverload | None:
    fields = declaration.fields_by_name("overload")
    if not fields:
        return None
    field = fields[0].field
    axis_field = _child(field, "axis")
    value_field = _child(field, "value")
    primary_field = _child(field, "primary")
    return PrimitiveOverload(
        axis=_field_text(axis_field) or "",
        value=_field_text(value_field) or "",
        declares_primary=_field_text(primary_field) == "true",
        source=_source_span(field.source),
        axis_source=None if axis_field is None else _source_span(axis_field.source),
        value_source=None if value_field is None else _source_span(value_field.source),
        primary_source=(
            None if primary_field is None else _source_span(primary_field.source)
        ),
    )



def _expand_wildcards(attributes: dict[str, str]) -> list[dict[str, str]]:
    """Expand each `*`-valued boolean wildcard attribute into true/false copies (the
    cartesian product over all such keys); other attributes pass through unchanged."""

    variants = [dict(attributes)]
    for key, value in attributes.items():
        if key in BOOLEAN_WILDCARD_ATTRIBUTES and value == "*":
            variants = [
                {**variant, key: concrete}
                for variant in variants
                for concrete in _BOOLEAN_WILDCARD_VALUES
            ]
    return variants



def _attribute_value(attribute: ParsedTslAttribute) -> str:
    value = attribute.value
    return value.text if isinstance(value, ParsedTslScalarValue) else ""



def _param_type_rules(declaration: ParsedPrimitiveDeclaration) -> tuple[ParamTypeRule, ...]:
    rules: list[ParamTypeRule] = []
    for field in declaration.fields_by_name("param_types"):
        for parameter in _children(field.field):
            for entry in _children(parameter):
                # Rejected conditions/empty types are dropped here; the schema
                # validator diagnoses them through the same shared grammar.
                condition = parse_param_type_condition(entry.key.text)
                type_text = _field_text(entry)
                type_expr = (
                    None
                    if type_text is None
                    else parse_param_type_expression(type_text)
                )
                if condition is None or type_expr is None:
                    continue
                attribute_name, attribute_value = condition
                rules.append(
                    ParamTypeRule(
                        parameter_name=parameter.key.text,
                        attribute_name=attribute_name,
                        attribute_value=attribute_value,
                        type_expr=type_expr,
                        source=_source_span(entry.source),
                    )
                )
    return tuple(rules)



def _generic_params(declaration: ParsedPrimitiveDeclaration) -> tuple[GenericParam, ...]:
    """The free template parameters from a `generic_params` block: each entry's `kind` +
    `default` (e.g. `PreserveSign {kind bool, default true}`)."""

    fields = declaration.fields_by_name("generic_params")
    if not fields:
        return ()
    return tuple(
        GenericParam(
            name=entry.key.text,
            # Typing-only narrow: schema validation diagnoses kinds outside
            # GenericParamKind.
            kind=cast(GenericParamKind, _field_text(_child(entry, "kind")) or "bool"),
            default=_field_text(_child(entry, "default")) or "false",
            base_type_constraints=_generic_param_base_types(entry),
            specialize_base=_bool_field(_child(entry, "specialize_base")),
            base_width_constraints=_generic_param_base_width_constraints(entry),
            source=_source_span(entry.source),
        )
        for entry in _children(fields[0].field)
    )


def _generic_param_base_types(entry: ParsedTslField) -> tuple[str, ...]:
    direct = _list_text(_child(entry, "base_types"))
    nested = _list_text(_child(_child(entry, "constraints"), "base_types"))
    return nested or direct


def _generic_param_base_width_constraints(
    entry: ParsedTslField,
) -> tuple[GenericParamBaseWidthConstraint, ...]:
    constraints = _child(entry, "constraints")
    if constraints is None:
        return ()
    result: list[GenericParamBaseWidthConstraint] = []
    for field in _children(constraints):
        relation = parse_base_width_constraint(field.key.text)
        if relation is None:
            continue
        result.append(
            GenericParamBaseWidthConstraint(
                relation=relation,
                source=_source_span(field.key.source),
            )
        )
    return tuple(result)



def _result_target(
    declaration: ParsedPrimitiveDeclaration,
) -> tuple[str, str] | None:
    """A `return_type: <dim>: <Target>` block -> `(dim, target_name)` where `dim` is
    "base" (reinterpret/cast/convert_up), "extension" (extract/insert), or "vector"
    (a caller-supplied SIMD type). None when absent."""

    fields = declaration.fields_by_name("return_type")
    if not fields:
        return None
    for child in _children(fields[0].field):
        if child.key.text in RESULT_DIMENSIONS:
            name = _field_text(child)
            if name:
                return (child.key.text, name)
    return None



def _immediate_params(
    declaration: ParsedPrimitiveDeclaration,
    diagnostics: list[Diagnostic],
) -> tuple[ImmediateParam, ...]:
    """The `params:` block -> per-name `ImmediateParam` metadata for `sImm` operands.

    Each entry refines a named `sImm` parameter from the signature with its public `type`,
    a `value_range`, and a per-language `dispatch` strategy. Entries that name a non-`sImm`
    parameter, an unknown parameter, or duplicate a name are diagnosed and dropped.
    """

    fields = declaration.fields_by_name("params")
    if not fields:
        return ()
    shape = parse_signature(declaration.signature)
    kinds = (
        dict(zip(declaration.parameters, shape.param_kinds)) if shape is not None else {}
    )
    name = declaration.name

    def reject(code: str, message: str, source: SourceSpan | None) -> None:
        diagnostics.append(
            diagnostic_at(severity="error", code=code, message=message, source=source)
        )

    result: list[ImmediateParam] = []
    seen: set[str] = set()
    for entry in _children(fields[0].field):
        param_name = entry.key.text
        if param_name in seen:
            reject(
                "TSL-PARAMS-DUPLICATE",
                f"duplicate `params` entry {param_name!r} on {name!r}",
                _source_span(entry.source),
            )
            continue
        seen.add(param_name)
        if param_name not in kinds:
            reject(
                "TSL-PARAMS-UNKNOWN-PARAM",
                f"`params` entry {param_name!r} is not a parameter of {name!r}",
                _source_span(entry.source),
            )
            continue
        if kinds[param_name] != "sImm":
            reject(
                "TSL-PARAMS-NOT-IMMEDIATE",
                f"`params` entry {param_name!r} on {name!r} is not an `sImm` immediate "
                f"(its signature kind is {kinds[param_name]!r})",
                _source_span(entry.source),
            )
            continue
        range_field = _child(entry, "value_range")
        range_text = _field_text(range_field)
        value_range = _parse_value_range(range_text)
        if range_text is not None and value_range is None:
            range_source = range_field.source if range_field is not None else entry.source
            reject(
                "TSL-PARAMS-BAD-RANGE",
                f"malformed `value_range` {range_text!r} for {param_name!r} on "
                f"{name!r} (expected `lo..hi` or `lo..=hi`)",
                _source_span(range_source),
            )
        dispatch = tuple(
            (child.key.text, _field_text(child) or "")
            for child in _children(_child(entry, "dispatch"))
        )
        result.append(
            ImmediateParam(
                name=param_name,
                type_tag=_field_text(_child(entry, "type")) or "ui32",
                value_range=value_range,
                dispatch=dispatch,
                source=_source_span(entry.source),
            )
        )
    return tuple(result)



def _parse_value_range(text: str | None) -> tuple[int, str, bool] | None:
    """`"0..base_bit_width(data)"` / `"1..=32"` -> `(lo, hi_expr, inclusive)`. `hi_expr` is
    kept symbolic (an int-literal string or a token like `base_bit_width(data)`) and resolved
    at lowering against the selected type. None when malformed."""

    if text is None:
        return None
    if "..=" in text:
        lo_text, hi_text = text.split("..=", 1)
        inclusive = True
    elif ".." in text:
        lo_text, hi_text = text.split("..", 1)
        inclusive = False
    else:
        return None
    lo_text, hi_text = lo_text.strip(), hi_text.strip()
    if not lo_text.lstrip("-").isdigit() or not hi_text:
        return None
    return (int(lo_text), hi_text, inclusive)
