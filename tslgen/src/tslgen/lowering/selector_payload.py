"""Typed lowering for primitive-call selector payload islands."""

import re

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import Catalog, ExtensionName, PrimitiveCall
from tslgen.lowering.model import (
    CurrentVector,
    ExtensionOperand,
    LoweredBackendTypeReference,
    LoweredBaseTransformType,
    LoweredCurrentScalarType,
    LoweredGenericRegisterType,
    LoweredIntrinsicVectorImaskType,
    LoweredScalarTypeIdentity,
    LoweredSizeType,
    LoweredSpecializationTypeSymbol,
    LoweredTypeIsSamePredicate,
    LoweredTypeSelectType,
    LoweredTypeValue,
    LoweredVectorAsExtensionType,
    LoweredVectorMemberType,
    LoweredVectorTransformType,
    PrimitiveCallSelectorPayload,
    PrimitiveCallSelectorPayloadLoweringResult,
    SelectedImplementationLoweringContext,
    SelectedTypeEnvironment,
    SelectorAttribute,
    SelectorLiteral,
    SelectorSpecializationValue,
    SelectorSymbol,
)
from tslgen.syntax.tsil_lexical import (
    BRACKET_DELIMITER,
    PAREN_DELIMITER,
    LexicalPart,
    split_top_level_parts,
)
from tslgen.lowering.type_queries import lower_type_expression

_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:::[A-Za-z_][A-Za-z0-9_]*)*")
_ATTR_RE = re.compile(
    r"(?P<key>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\((?P<key_argument>[A-Za-z_][A-Za-z0-9_]*)\))?"
    r"=(?P<value>[^,]+)"
)
_INTEGER_RE = re.compile(r"\d+")
_TYPE_PREFIXES = (
    "base::",
    "intrin::",
    "register::",
    "scalar::",
    "type<",
    "value<",
    "vector::",
)


def lower_primitive_call_selector_payload(
    context: SelectedImplementationLoweringContext,
    catalog: Catalog,
    primitive_call: PrimitiveCall,
    environment: SelectedTypeEnvironment,
) -> PrimitiveCallSelectorPayloadLoweringResult:
    """Lower already structured primitive-call selector metadata."""

    diagnostics: list[Diagnostic] = list(environment.diagnostics)
    specializations: list[SelectorSpecializationValue] = []

    specialization = primitive_call.selector.specialization
    if specialization is not None:
        specialization_start = _selector_payload_start(
            primitive_call.selector.source_text,
            "[",
        )
        parts = _split_top_level_parts(specialization)
        if specialization_start is None or parts is None:
            diagnostics.append(
                _malformed_specialization_diagnostic(
                    specialization,
                    primitive_call.selector.source,
                )
            )
        else:
            for part in parts:
                part_source = _source_at(
                    primitive_call.selector.source,
                    primitive_call.selector.source_text,
                    specialization_start + part.start,
                )
                value = _lower_specialization_part(
                    context,
                    catalog,
                    environment,
                    part.text,
                    part_source,
                )
                if isinstance(value, Diagnostic):
                    diagnostics.append(value)
                else:
                    value_diagnostics = _unknown_extension_diagnostics(
                        value,
                        catalog,
                        part_source,
                    )
                    diagnostics.extend(value_diagnostics)
                    if not value_diagnostics:
                        specializations.append(value)

    attrs = primitive_call.selector.attrs
    attributes: list[SelectorAttribute] = []
    if attrs is not None:
        attrs_start = _selector_payload_start(
            primitive_call.selector.source_text,
            "attrs[",
        )
        parts = _split_top_level_parts(attrs)
        if attrs_start is None or parts is None:
            diagnostics.append(
                _malformed_attrs_diagnostic(attrs, primitive_call.selector.source)
            )
        else:
            for part in parts:
                part_source = _source_at(
                    primitive_call.selector.source,
                    primitive_call.selector.source_text,
                    attrs_start + part.start,
                )
                attribute = _lower_selector_attribute(part.text, part_source)
                if isinstance(attribute, Diagnostic):
                    diagnostics.append(attribute)
                else:
                    attributes.append(attribute)

    if diagnostics:
        return PrimitiveCallSelectorPayloadLoweringResult(
            payload=None,
            diagnostics=tuple(diagnostics),
        )

    return PrimitiveCallSelectorPayloadLoweringResult(
        payload=PrimitiveCallSelectorPayload(
            target=primitive_call.selector.target,
            specializations=tuple(specializations),
            attributes=tuple(attributes),
            source_text=primitive_call.selector.source_text,
            source=primitive_call.selector.source,
        ),
        diagnostics=(),
    )


def _lower_specialization_part(
    context: SelectedImplementationLoweringContext,
    catalog: Catalog,
    environment: SelectedTypeEnvironment,
    text: str,
    source: SourceLocation,
) -> SelectorSpecializationValue | Diagnostic:
    if _is_type_valued_selector_part(context, environment, text):
        result = lower_type_expression(
            context,
            text,
            source,
            environment=environment,
        )
        if result.value is None:
            return result.diagnostics[0]
        return result.value

    if catalog.extensions.get(text) is not None:
        return ExtensionOperand(name=ExtensionName(text), source=source)

    if _INTEGER_RE.fullmatch(text) is not None:
        return SelectorLiteral(text=text, source=source)

    if _IDENTIFIER_RE.fullmatch(text) is not None:
        return SelectorSymbol(name=text, source=source)

    return _malformed_specialization_diagnostic(text, source)


def _is_type_valued_selector_part(
    context: SelectedImplementationLoweringContext,
    environment: SelectedTypeEnvironment,
    text: str,
) -> bool:
    if text in (context.current_vector_keyword, context.current_scalar_keyword):
        return True
    if any(binding.alias_name == text for binding in environment.alias_bindings):
        return True
    return text.startswith(_TYPE_PREFIXES)


def _lower_selector_attribute(
    text: str,
    source: SourceLocation,
) -> SelectorAttribute | Diagnostic:
    match = _ATTR_RE.fullmatch(text)
    if match is None:
        return _malformed_attrs_diagnostic(text, source)
    value = match.group("value").strip()
    if not value or "?" in value or "*" in value:
        return _unsupported_attrs_diagnostic(text, source)
    return SelectorAttribute(
        key=match.group("key"),
        key_argument=match.group("key_argument"),
        value=value,
        source=source,
    )


def _unknown_extension_diagnostics(
    value: SelectorSpecializationValue,
    catalog: Catalog,
    source: SourceLocation,
) -> tuple[Diagnostic, ...]:
    extension_names = _extension_names_from_value(value)
    return tuple(
        _unknown_extension_diagnostic(name, source)
        for name in extension_names
        if catalog.extensions.get(str(name)) is None
    )


def _extension_names_from_value(
    value: SelectorSpecializationValue | LoweredTypeValue,
) -> tuple[ExtensionName, ...]:
    if isinstance(value, ExtensionOperand):
        return (value.name,)
    if isinstance(value, CurrentVector | LoweredVectorMemberType):
        return (value.extension,)
    if isinstance(value, LoweredVectorAsExtensionType):
        return (value.extension, *_extension_names_from_value(value.base_type))
    if isinstance(value, LoweredVectorTransformType):
        return (value.extension, *_extension_names_from_value(value.base_type))
    if isinstance(value, LoweredGenericRegisterType):
        return _extension_names_from_value(value.vector_type)
    if isinstance(value, LoweredBackendTypeReference):
        return _extension_names_from_value(value.request.value)
    if isinstance(value, LoweredBaseTransformType):
        return _extension_names_from_value(value.value)
    if isinstance(value, LoweredTypeSelectType):
        return (
            *_extension_names_from_predicate(value.condition),
            *_extension_names_from_value(value.then_type),
            *_extension_names_from_value(value.else_type),
        )
    return ()


def _extension_names_from_predicate(
    predicate: LoweredTypeIsSamePredicate,
) -> tuple[ExtensionName, ...]:
    return (
        *_extension_names_from_value(predicate.left),
        *_extension_names_from_value(predicate.right),
    )


def _split_top_level_parts(payload: str) -> tuple[LexicalPart, ...] | None:
    return split_top_level_parts(
        payload,
        delimiters=(PAREN_DELIMITER, BRACKET_DELIMITER),
        allow_empty_payload=True,
    )


def _selector_payload_start(selector_text: str, marker: str) -> int | None:
    index = selector_text.find(marker)
    if index == -1:
        return None
    return index + len(marker)


def _source_at(
    source: SourceLocation,
    selector_text: str,
    offset: int,
) -> SourceLocation:
    prefix = selector_text[:offset]
    line_offset = prefix.count("\n")
    if line_offset == 0:
        return SourceLocation(source.path, source.line, source.column + offset)
    column = len(prefix.rsplit("\n", 1)[-1]) + 1
    return SourceLocation(source.path, source.line + line_offset, column)


def _malformed_specialization_diagnostic(
    specialization: str,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-MALFORMED-SELECTOR-SPECIALIZATION",
        message=(
            "primitive-call selector specialization cannot be lowered; expected "
            "comma-separated top-level selector entries, got "
            f"{specialization!r}"
        ),
        location=source,
    )


def _malformed_attrs_diagnostic(attrs: str, source: SourceLocation) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-MALFORMED-SELECTOR-ATTRS",
        message=(
            "primitive-call selector attrs cannot be lowered; expected "
            "comma-separated key=value or key(argument)=value entries, got "
            f"{attrs!r}"
        ),
        location=source,
    )


def _unsupported_attrs_diagnostic(attrs: str, source: SourceLocation) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-UNSUPPORTED-SELECTOR-ATTRS",
        message=(
            "primitive-call selector attrs cannot be lowered with wildcard or "
            f"empty values, got {attrs!r}"
        ),
        location=source,
    )


def _unknown_extension_diagnostic(
    extension: ExtensionName,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-UNKNOWN-SELECTOR-EXTENSION",
        message=(
            "primitive-call selector references an extension that is not in the "
            f"extension catalog: {str(extension)!r}"
        ),
        location=source,
    )
