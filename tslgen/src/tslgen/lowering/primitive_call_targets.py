"""Typed target matching for already lowered primitive-call selectors."""

from tslgen.analysis.selection import Selector, Target, TargetAttribute
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import (
    Catalog,
    NamedPrimitiveReference,
    SelfPrimitiveReference,
    TypeTag,
)
from tslgen.lowering.model import (
    CurrentVector,
    ExtensionOperand,
    LoweredBackendTypeReference,
    LoweredCurrentScalarType,
    LoweredScalarTypeIdentity,
    LoweredTypeValue,
    LoweredVectorAsExtensionType,
    PrimitiveCallSelectorPayload,
    PrimitiveCallTargetMatch,
    PrimitiveCallTargetMatchingResult,
    SelectedImplementationLoweringContext,
    SelectorAttribute,
    SelectorLiteral,
    SelectorSpecializationValue,
    SelectorSymbol,
)


def lower_primitive_call_target_match(
    context: SelectedImplementationLoweringContext,
    catalog: Catalog,
    selector_payload: PrimitiveCallSelectorPayload,
) -> PrimitiveCallTargetMatchingResult:
    """Match an M144 selector payload to one catalog implementation candidate."""

    vector = _selector_vector(context, selector_payload)
    if isinstance(vector, Diagnostic):
        return PrimitiveCallTargetMatchingResult(
            match=None,
            diagnostics=(vector,),
        )

    target = Target(
        backend=context.backend,
        primitive_name=_target_name(context, selector_payload),
        extension=str(vector.extension),
        type_tag=str(vector.type_tag),
        attributes=_target_attributes(selector_payload.attributes),
    )
    selection = Selector().select(catalog, target)
    if selection.diagnostics:
        return PrimitiveCallTargetMatchingResult(
            match=None,
            diagnostics=tuple(
                _with_selector_source(diagnostic, selector_payload.source)
                for diagnostic in selection.diagnostics
            ),
        )

    return PrimitiveCallTargetMatchingResult(
        match=PrimitiveCallTargetMatch(
            selected=selection.selected[0],
            selector_payload=selector_payload,
            source=selector_payload.source,
        ),
        diagnostics=(),
    )


def _target_name(
    context: SelectedImplementationLoweringContext,
    selector_payload: PrimitiveCallSelectorPayload,
) -> str:
    target = selector_payload.target
    if isinstance(target, SelfPrimitiveReference):
        return context.primitive_name
    if isinstance(target, NamedPrimitiveReference):
        return target.name
    raise AssertionError(f"unsupported primitive-call target: {target!r}")


def _selector_vector(
    context: SelectedImplementationLoweringContext,
    selector_payload: PrimitiveCallSelectorPayload,
) -> CurrentVector | Diagnostic:
    specializations = selector_payload.specializations
    if not specializations:
        return CurrentVector(extension=context.extension, type_tag=context.type_tag)

    if len(specializations) != 1:
        return _unsupported_specialization_diagnostic(
            selector_payload,
            (
                "primitive-call selector target matching supports at most one "
                f"concrete vector specialization; got {len(specializations)} "
                f"entries in {selector_payload.source_text!r}"
            ),
        )

    value = specializations[0]
    vector = _concrete_vector_from_value(value)
    if vector is None:
        return _unsupported_specialization_diagnostic(
            selector_payload,
            (
                "primitive-call selector specialization cannot be matched by "
                "this boundary; expected a concrete vector specialization, got "
                f"{_format_specialization_value(value)}"
            ),
            location=_specialization_source(value, selector_payload.source),
        )
    return vector


def _concrete_vector_from_value(
    value: SelectorSpecializationValue | LoweredTypeValue,
) -> CurrentVector | None:
    if isinstance(value, CurrentVector):
        return value
    if isinstance(value, LoweredBackendTypeReference):
        return _concrete_vector_from_value(value.request.value)
    if isinstance(value, LoweredVectorAsExtensionType):
        type_tag = _scalar_type_tag(value.base_type)
        if type_tag is not None:
            return CurrentVector(extension=value.extension, type_tag=type_tag)
    return None


def _scalar_type_tag(value: LoweredTypeValue) -> TypeTag | None:
    if isinstance(value, LoweredCurrentScalarType | LoweredScalarTypeIdentity):
        return value.type_tag
    if isinstance(value, CurrentVector):
        return value.type_tag
    if isinstance(value, LoweredBackendTypeReference):
        return _scalar_type_tag(value.request.value)
    return None


def _target_attributes(
    attributes: tuple[SelectorAttribute, ...],
) -> tuple[TargetAttribute, ...]:
    return tuple(
        TargetAttribute(
            key=attribute.key,
            value=attribute.value,
            key_argument=attribute.key_argument,
        )
        for attribute in attributes
    )


def _unsupported_specialization_diagnostic(
    selector_payload: PrimitiveCallSelectorPayload,
    message: str,
    *,
    location: SourceLocation | None = None,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL-SELECTOR",
        message=message,
        location=location or selector_payload.source,
    )


def _specialization_source(
    value: SelectorSpecializationValue,
    fallback: SourceLocation,
) -> SourceLocation:
    if isinstance(value, SelectorSymbol | SelectorLiteral):
        return value.source
    if isinstance(value, LoweredBackendTypeReference):
        return value.request.source
    return fallback


def _format_specialization_value(value: SelectorSpecializationValue) -> str:
    if isinstance(value, SelectorSymbol):
        return f"selector symbol {value.name!r}"
    if isinstance(value, SelectorLiteral):
        return f"selector literal {value.text!r}"
    if isinstance(value, LoweredBackendTypeReference):
        return f"backend type query {value.request.source_text!r}"
    if isinstance(value, ExtensionOperand):
        return f"extension operand {str(value.name)!r}"
    return type(value).__name__


def _with_selector_source(
    diagnostic: Diagnostic,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity=diagnostic.severity,
        code=diagnostic.code,
        message=diagnostic.message,
        location=source,
    )
