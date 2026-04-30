from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from tslgen.core.diagnostics import Diagnostic, SourceLocation, sort_diagnostics
from tslgen.core.frozen_map import FrozenMap
from tslgen.domain.primitives import PrimitiveAttribute, PrimitiveDeclaration
from tslgen.domain.signatures import Signature
from tslgen.domain.templates import OperationTemplate
from tslgen.domain.values import CatalogValue
from tslgen.validation.signature_rules import (
    candidate_template_names,
    condition_attribute_keys,
    condition_values_for_attribute,
)


_KNOWN_ATTRIBUTES = frozenset(
    {"mask", "aligned", "packed", "op", "value", "cast", "direction", "arg_count"}
)
_BOOLEAN_OR_WILDCARD_ATTRIBUTES = frozenset({"aligned", "packed"})
_MASK_VALUES = frozenset({"zero", "pass_through"})
_OP_VALUES = frozenset({"pack", "expand", "keep"})
_VALUE_VALUES = frozenset({"zero", "undef", "all"})
_CAST_VALUES = frozenset({"convert", "reinterpret"})
_DIRECTION_VALUES = frozenset({"up", "down"})


@dataclass(frozen=True, slots=True)
class AttributeValidation:
    values: FrozenMap[str, CatalogValue]
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostics", sort_diagnostics(self.diagnostics))


def validate_primitive_attributes(
    primitive: PrimitiveDeclaration,
    signature: Signature,
    templates: Mapping[str, OperationTemplate],
) -> AttributeValidation:
    diagnostics: list[Diagnostic] = []
    values: dict[str, CatalogValue] = {}
    seen: set[str] = set()

    allowed_keys = _allowed_attribute_keys(signature, templates)
    for attribute in primitive.attributes:
        key = attribute.key
        if key in seen:
            diagnostics.append(
                _attribute_error(
                    "TSL-ATTR-DUPLICATE",
                    f"primitive {primitive.name!r} has duplicate attribute {key!r}",
                    attribute,
                )
            )
            continue
        seen.add(key)
        values[key] = attribute.value

    frozen_values = FrozenMap(values)
    for attribute in primitive.attributes:
        diagnostics.extend(
            _validate_attribute_shape(
                primitive,
                signature,
                attribute,
                allowed_keys,
                frozen_values,
            )
        )

    diagnostics.extend(
        _validate_repeated_parameter_count(primitive, signature, frozen_values)
    )
    diagnostics.extend(_validate_direction_dependency(primitive, signature, frozen_values))

    return AttributeValidation(values=frozen_values, diagnostics=tuple(diagnostics))


def validate_template_required_fields(
    primitive: PrimitiveDeclaration,
    template: OperationTemplate,
    attributes: Mapping[str, CatalogValue],
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    for field_name in template.required_fields:
        if field_name not in attributes:
            diagnostics.append(
                Diagnostic.error(
                    "TSL-ATTR-REQUIRED",
                    f"primitive {primitive.name!r} resolved to template "
                    f"{template.name!r} but is missing required attribute {field_name!r}",
                    location=primitive.source_span.location,
                )
            )
    return tuple(diagnostics)


def _validate_attribute_shape(
    primitive: PrimitiveDeclaration,
    signature: Signature,
    attribute: PrimitiveAttribute,
    allowed_keys: frozenset[str],
    all_attributes: Mapping[str, CatalogValue],
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    if attribute.name not in _KNOWN_ATTRIBUTES:
        return (
            _attribute_error(
                "TSL-ATTR-UNKNOWN",
                f"primitive {primitive.name!r} has unknown attribute {attribute.key!r}",
                attribute,
            ),
        )

    if attribute.name != "arg_count" and attribute.argument is not None:
        diagnostics.append(
            _attribute_error(
                "TSL-ATTR-SHAPE",
                f"attribute {attribute.name!r} must not have an argument",
                attribute,
            )
        )

    if attribute.name == "arg_count":
        diagnostics.extend(_validate_arg_count(primitive, signature, attribute))
    elif attribute.name not in allowed_keys:
        diagnostics.append(
            _attribute_error(
                "TSL-ATTR-UNEXPECTED",
                f"attribute {attribute.key!r} is not valid for signature "
                f"{signature.normalized!r}",
                attribute,
            )
        )

    diagnostics.extend(_validate_attribute_value(signature, attribute))
    diagnostics.extend(_validate_signature_specific_value(signature, attribute, all_attributes))
    return tuple(diagnostics)


def _validate_attribute_value(
    signature: Signature,
    attribute: PrimitiveAttribute,
) -> tuple[Diagnostic, ...]:
    value = attribute.value
    name = attribute.name
    if name in _BOOLEAN_OR_WILDCARD_ATTRIBUTES:
        if value == "*" or isinstance(value, bool):
            return ()
        return (
            _value_error(
                attribute,
                "expected true, false, or *",
            ),
        )
    if name == "mask":
        return _validate_string_choice(attribute, _MASK_VALUES)
    if name == "op":
        return _validate_string_choice(attribute, _OP_VALUES)
    if name == "value":
        return _validate_string_choice(attribute, _VALUE_VALUES)
    if name == "cast":
        return _validate_string_choice(attribute, _CAST_VALUES)
    if name == "direction":
        return _validate_string_choice(attribute, _DIRECTION_VALUES)
    if name == "arg_count":
        if value == "return_vector_length":
            return ()
        return (
            _value_error(
                attribute,
                "expected return_vector_length",
            ),
        )

    return ()


def _validate_signature_specific_value(
    signature: Signature,
    attribute: PrimitiveAttribute,
    all_attributes: Mapping[str, CatalogValue],
) -> tuple[Diagnostic, ...]:
    values = condition_values_for_attribute(signature, attribute.name)
    if (
        values
        and _passes_generic_value_check(attribute)
        and attribute.value not in values
    ):
        expected = ", ".join(str(value) for value in sorted(values, key=str))
        return (
            _value_error(
                attribute,
                f"expected one of {expected} for signature {signature.normalized!r}",
            ),
        )

    if signature.normalized == "v:=(m,v)" and attribute.name == "op":
        if all_attributes.get("mask") == "pass_through":
            return (
                _attribute_error(
                    "TSL-ATTR-UNEXPECTED",
                    "attribute 'op' is not valid when mask=pass_through",
                    attribute,
                ),
            )

    return ()


def _passes_generic_value_check(attribute: PrimitiveAttribute) -> bool:
    if attribute.name == "mask":
        return isinstance(attribute.value, str) and attribute.value in _MASK_VALUES
    if attribute.name == "op":
        return isinstance(attribute.value, str) and attribute.value in _OP_VALUES
    if attribute.name == "value":
        return isinstance(attribute.value, str) and attribute.value in _VALUE_VALUES
    if attribute.name == "cast":
        return isinstance(attribute.value, str) and attribute.value in _CAST_VALUES
    if attribute.name == "direction":
        return (
            isinstance(attribute.value, str)
            and attribute.value in _DIRECTION_VALUES
        )
    return True


def _validate_arg_count(
    primitive: PrimitiveDeclaration,
    signature: Signature,
    attribute: PrimitiveAttribute,
) -> tuple[Diagnostic, ...]:
    if attribute.argument is None:
        return (
            _attribute_error(
                "TSL-ATTR-SHAPE",
                "attribute 'arg_count' requires a parameter argument",
                attribute,
            ),
        )
    if not signature.has_repeated_parameter:
        return (
            _attribute_error(
                "TSL-ATTR-UNEXPECTED",
                f"attribute {attribute.key!r} is only valid for repeated signatures",
                attribute,
            ),
        )

    parameter_names = frozenset(
        parameter.name.removesuffix("...") for parameter in primitive.parameters
    )
    if attribute.argument not in parameter_names:
        return (
            _attribute_error(
                "TSL-ATTR-SHAPE",
                f"attribute {attribute.key!r} references unknown parameter "
                f"{attribute.argument!r}",
                attribute,
            ),
        )
    return ()


def _validate_repeated_parameter_count(
    primitive: PrimitiveDeclaration,
    signature: Signature,
    attributes: Mapping[str, CatalogValue],
) -> tuple[Diagnostic, ...]:
    arg_count_keys = tuple(
        key for key in attributes if key.startswith("arg_count(") and key.endswith(")")
    )
    if not signature.has_repeated_parameter:
        return ()
    if len(arg_count_keys) == 1:
        return ()
    return (
        Diagnostic.error(
            "TSL-ATTR-REQUIRED",
            f"primitive {primitive.name!r} signature {signature.normalized!r} requires "
            "exactly one arg_count(<param>) attribute",
            location=primitive.source_span.location,
        ),
    )


def _validate_direction_dependency(
    primitive: PrimitiveDeclaration,
    signature: Signature,
    attributes: Mapping[str, CatalogValue],
) -> tuple[Diagnostic, ...]:
    if signature.normalized != "v:=(v,sImm)":
        return ()
    if attributes.get("cast") == "convert" and "direction" not in attributes:
        return (
            Diagnostic.error(
                "TSL-ATTR-REQUIRED",
                f"primitive {primitive.name!r} signature {signature.normalized!r} "
                "requires direction=up|down when cast=convert",
                location=primitive.source_span.location,
            ),
        )
    if "direction" in attributes and attributes.get("cast") != "convert":
        location = _attribute_location(primitive.attributes, "direction")
        return (
            Diagnostic.error(
                "TSL-ATTR-UNEXPECTED",
                "attribute 'direction' requires cast=convert",
                location=location,
            ),
        )
    return ()


def _allowed_attribute_keys(
    signature: Signature,
    templates: Mapping[str, OperationTemplate],
) -> frozenset[str]:
    keys = set(condition_attribute_keys(signature))
    for template_name in candidate_template_names(signature):
        template = templates.get(template_name)
        if template is None:
            continue
        keys.update(template.required_fields)
    return frozenset(keys)


def _validate_string_choice(
    attribute: PrimitiveAttribute,
    expected_values: frozenset[str],
) -> tuple[Diagnostic, ...]:
    if isinstance(attribute.value, str) and attribute.value in expected_values:
        return ()
    expected = ", ".join(sorted(expected_values))
    return (_value_error(attribute, f"expected one of {expected}"),)


def _value_error(attribute: PrimitiveAttribute, expected: str) -> Diagnostic:
    return _attribute_error(
        "TSL-ATTR-VALUE",
        f"attribute {attribute.key!r} has invalid value {attribute.value!r}; {expected}",
        attribute,
    )


def _attribute_error(
    code: str,
    message: str,
    attribute: PrimitiveAttribute,
) -> Diagnostic:
    return Diagnostic.error(code, message, location=attribute.source_span.location)


def _attribute_location(
    attributes: tuple[PrimitiveAttribute, ...],
    key: str,
) -> SourceLocation | None:
    for attribute in attributes:
        if attribute.key == key:
            return attribute.source_span.location
    return None
