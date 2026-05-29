"""Cohesive primitive-call lowering resolution and dependency collection."""

from collections.abc import Iterator
from dataclasses import dataclass

from tslgen.analysis.selection import SelectedImplementation, Selector, Target
from tslgen.analysis.selection import TargetAttribute
from tslgen.analysis.selection import TargetReturnTypeBaseBinding
from tslgen.analysis.selection import TargetReturnTypeExtensionBinding
from tslgen.analysis.selection import TargetSpecializationBinding
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import (
    BodyToken,
    Catalog,
    ImplementationBody,
    LowerableDirective,
    NamedPrimitiveReference,
    PayloadToken,
    PrimitiveCall,
    SelfPrimitiveReference,
    TypeTag,
)
from tslgen.lowering.model import (
    CurrentVector,
    ExtensionOperand,
    LoweredBackendTypeReference,
    LoweredCurrentScalarType,
    LoweredPrimitiveCallExpression,
    LoweredScalarTypeIdentity,
    LoweredTypeValue,
    LoweredVectorAsExtensionType,
    LoweredVectorTransformType,
    PrimitiveCallArgumentBinding,
    PrimitiveCallArgumentBindingResult,
    PrimitiveCallDependencyClosure,
    PrimitiveCallExpressionLoweringResult,
    PrimitiveCallReference,
    PrimitiveCallReferenceInventory,
    PrimitiveCallSelectorPayload,
    PrimitiveCallTargetMatch,
    PrimitiveCallTargetMatchingResult,
    SelectedImplementationLoweringContext,
    SelectedTypeEnvironment,
    SelectorAttribute,
    SelectorLiteral,
    SelectorSpecializationValue,
    SelectorSymbol,
    build_selected_implementation_lowering_context,
)
from tslgen.lowering.selector_payload import lower_primitive_call_selector_payload
from tslgen.lowering.type_queries import build_selected_type_environment

_MISSING_PRIMITIVE_CALL_CAPABILITY = (
    "primitive-call dependency resolution is not implemented yet"
)
_MISSING_PRIMITIVE_CALL_SELECTION_CAPABILITY = (
    "dependency implementation selection/lowering is not implemented yet"
)
_MISSING_SPECIALIZATION_TARGET_CAPABILITY = (
    "specialization-specific target reference resolution is not implemented yet"
)
_MISSING_ATTRS_TARGET_CAPABILITY = (
    "attribute-specific target reference resolution is not implemented yet"
)

_SelectedIdentity = tuple[
    str,
    str,
    str,
    str,
    tuple[tuple[str, str, str], ...],
    tuple[tuple[str, str, str, str], ...],
]
_ReturnBindingSelectorValue = LoweredScalarTypeIdentity | ExtensionOperand


@dataclass(frozen=True, slots=True)
class _SelectorTargetParts:
    vector: CurrentVector
    return_binding_value: _ReturnBindingSelectorValue | None = None


class PrimitiveCallResolver:
    """Resolve recognized primitive-call tokens against one catalog."""

    def __init__(self, catalog: Catalog) -> None:
        self._catalog = catalog

    def match_target(
        self,
        context: SelectedImplementationLoweringContext,
        selector_payload: PrimitiveCallSelectorPayload,
    ) -> PrimitiveCallTargetMatchingResult:
        """Match a lowered selector payload to one catalog implementation."""

        parts = _selector_target_parts(context, selector_payload)
        if isinstance(parts, Diagnostic):
            return PrimitiveCallTargetMatchingResult(
                match=None,
                diagnostics=(parts,),
            )

        target = Target(
            backend=context.backend,
            primitive_name=_target_name(context, selector_payload),
            extension=str(parts.vector.extension),
            type_tag=str(parts.vector.type_tag),
            attributes=_target_attributes(selector_payload.attributes),
        )
        selection = Selector().select(self._catalog, target)
        if selection.diagnostics:
            return PrimitiveCallTargetMatchingResult(
                match=None,
                diagnostics=tuple(
                    _with_selector_source(diagnostic, selector_payload.source)
                    for diagnostic in selection.diagnostics
                ),
            )

        selected = selection.selected[0]
        target_binding = _target_return_binding(
            selected,
            parts.return_binding_value,
            selector_payload,
        )
        if isinstance(target_binding, Diagnostic):
            return PrimitiveCallTargetMatchingResult(
                match=None,
                diagnostics=(target_binding,),
            )
        if target_binding is not None:
            selected = _selected_with_target_binding(selected, target_binding)

        return PrimitiveCallTargetMatchingResult(
            match=PrimitiveCallTargetMatch(
                selected=selected,
                selector_payload=selector_payload,
                source=selector_payload.source,
            ),
            diagnostics=(),
        )

    @staticmethod
    def bind_arguments(
        primitive_call: PrimitiveCall,
        target_match: PrimitiveCallTargetMatch,
    ) -> PrimitiveCallArgumentBindingResult:
        """Bind raw call arguments positionally to target parameters."""

        context = build_selected_implementation_lowering_context(
            target_match.selected
        )
        parameter_names = context.parameter_names
        arguments = primitive_call.arguments
        if len(arguments) != len(parameter_names):
            return PrimitiveCallArgumentBindingResult(
                reference=None,
                diagnostics=(
                    Diagnostic(
                        severity="error",
                        code="TSL-LOWER-PRIMITIVE-CALL-ARGUMENT-COUNT-MISMATCH",
                        message=(
                            "primitive-call target "
                            f"{context.primitive_name!r} expects "
                            f"{len(parameter_names)} argument(s) for parameters "
                            f"{_format_parameter_names(parameter_names)}; got "
                            f"{len(arguments)} argument(s)"
                        ),
                        location=primitive_call.source,
                    ),
                ),
            )

        bindings = tuple(
            PrimitiveCallArgumentBinding(parameter_name=name, argument=argument)
            for name, argument in zip(parameter_names, arguments, strict=True)
        )
        return PrimitiveCallArgumentBindingResult(
            reference=PrimitiveCallReference(
                primitive_call=primitive_call,
                target_match=target_match,
                bindings=bindings,
                source=primitive_call.source,
            ),
            diagnostics=(),
        )

    def lower_expression(
        self,
        selected: SelectedImplementation,
        primitive_call: PrimitiveCall,
        *,
        environment: SelectedTypeEnvironment | None = None,
    ) -> PrimitiveCallExpressionLoweringResult:
        """Resolve one primitive call into a reusable lowered expression."""

        context = build_selected_implementation_lowering_context(selected)
        selected_environment = (
            environment
            if environment is not None
            else build_selected_type_environment(context)
        )
        selector_result = lower_primitive_call_selector_payload(
            context,
            self._catalog,
            primitive_call,
            selected_environment,
        )
        if selector_result.payload is None:
            return PrimitiveCallExpressionLoweringResult(
                expression=None,
                diagnostics=selector_result.diagnostics,
            )

        match_result = self.match_target(context, selector_result.payload)
        if match_result.match is None:
            return PrimitiveCallExpressionLoweringResult(
                expression=None,
                diagnostics=match_result.diagnostics,
            )

        binding_result = self.bind_arguments(primitive_call, match_result.match)
        if binding_result.reference is None:
            return PrimitiveCallExpressionLoweringResult(
                expression=None,
                diagnostics=binding_result.diagnostics,
            )

        return PrimitiveCallExpressionLoweringResult(
            expression=LoweredPrimitiveCallExpression(binding_result.reference),
            diagnostics=(),
        )


class PrimitiveCallDependencyCollector:
    """Collect primitive-call references and dependency closure facts."""

    def __init__(self, catalog: Catalog) -> None:
        self._catalog = catalog
        self._resolver = PrimitiveCallResolver(catalog)

    def reference_inventory(
        self,
        selected: SelectedImplementation,
    ) -> PrimitiveCallReferenceInventory:
        """Collect resolved primitive-call references in selected body order."""

        context = build_selected_implementation_lowering_context(selected)
        environment = build_selected_type_environment(context)
        references: list[PrimitiveCallReference] = []
        diagnostics: list[Diagnostic] = []

        for primitive_call in _primitive_calls_in_source_order(selected):
            expression_result = self._resolver.lower_expression(
                selected,
                primitive_call,
                environment=environment,
            )
            if expression_result.expression is None:
                diagnostics.extend(expression_result.diagnostics)
                continue

            references.append(expression_result.expression.reference)

        return PrimitiveCallReferenceInventory(
            references=tuple(references),
            diagnostics=tuple(diagnostics),
        )

    def dependency_closure(
        self,
        root: SelectedImplementation,
    ) -> PrimitiveCallDependencyClosure:
        """Discover selected implementations reachable through primitive calls."""

        selected: list[SelectedImplementation] = [root]
        references: list[PrimitiveCallReference] = []
        diagnostics: list[Diagnostic] = []
        seen: set[_SelectedIdentity] = {_selected_identity(root)}
        queue: list[SelectedImplementation] = [root]

        while queue:
            current = queue.pop(0)
            inventory = self.reference_inventory(current)
            diagnostics.extend(inventory.diagnostics)

            for reference in inventory.references:
                references.append(reference)
                dependency = reference.target_match.selected
                identity = _selected_identity(dependency)
                if identity in seen:
                    continue
                seen.add(identity)
                selected.append(dependency)
                queue.append(dependency)

        return PrimitiveCallDependencyClosure(
            selected=tuple(selected),
            references=tuple(references),
            diagnostics=tuple(diagnostics),
        )


def unsupported_primitive_call_diagnostics(
    body: ImplementationBody,
    *,
    selected: SelectedImplementation,
    catalog: Catalog | None,
) -> tuple[Diagnostic, ...]:
    return _unsupported_primitive_call_diagnostics_from_directives(
        _primitive_call_directives_from_body(body),
        selected=selected,
        catalog=catalog,
    )


def unsupported_primitive_call_diagnostics_from_payload_tokens(
    tokens: tuple[PayloadToken, ...],
    *,
    selected: SelectedImplementation,
    catalog: Catalog | None,
) -> tuple[Diagnostic, ...]:
    primitive_call_tokens = _primitive_call_directives_from_tokens(tokens)
    if not primitive_call_tokens or len(primitive_call_tokens) != len(tokens):
        return ()
    return _unsupported_primitive_call_diagnostics_from_directives(
        primitive_call_tokens,
        selected=selected,
        catalog=catalog,
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


def _selector_target_parts(
    context: SelectedImplementationLoweringContext,
    selector_payload: PrimitiveCallSelectorPayload,
) -> _SelectorTargetParts | Diagnostic:
    specializations = selector_payload.specializations
    if not specializations:
        return _SelectorTargetParts(
            vector=CurrentVector(extension=context.extension, type_tag=context.type_tag)
        )

    if len(specializations) > 2:
        return _unsupported_specialization_diagnostic(
            selector_payload,
            (
                "primitive-call selector target matching supports only an "
                "optional concrete vector specialization and optional selected "
                "return-type binding; got "
                f"{len(specializations)} entries in {selector_payload.source_text!r}"
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

    if len(specializations) == 1:
        return _SelectorTargetParts(vector=vector)

    return_binding_value = specializations[1]
    if not _is_selected_return_binding_entry(selector_payload, 1) or not isinstance(
        return_binding_value,
        LoweredScalarTypeIdentity | ExtensionOperand,
    ):
        return _unsupported_specialization_diagnostic(
            selector_payload,
            (
                "primitive-call selector target matching supports two-entry "
                "selectors only as a concrete vector plus selected return-type "
                "binding; got 2 entries in "
                f"{selector_payload.source_text!r}; unsupported second entry is "
                f"{_format_specialization_value(return_binding_value)}"
            ),
        )
    return _SelectorTargetParts(
        vector=vector,
        return_binding_value=return_binding_value,
    )


def _is_selected_return_binding_entry(
    selector_payload: PrimitiveCallSelectorPayload,
    index: int,
) -> bool:
    return (
        index < len(selector_payload.selected_return_binding_names)
        and selector_payload.selected_return_binding_names[index] is not None
    )


def _target_return_binding(
    selected: SelectedImplementation,
    value: _ReturnBindingSelectorValue | None,
    selector_payload: PrimitiveCallSelectorPayload,
) -> TargetSpecializationBinding | Diagnostic | None:
    if value is None:
        return None

    declaration = selected.primitive.return_type_binding
    if declaration is None:
        return _unsupported_specialization_diagnostic(
            selector_payload,
            (
                "primitive-call selector return-type binding cannot be matched; "
                f"target primitive {selected.primitive.name!r} has no "
                "primitive-local return_type declaration"
            ),
            location=_specialization_source(value, selector_payload.source),
        )

    if isinstance(value, LoweredScalarTypeIdentity):
        if declaration.kind != "base":
            return _wrong_return_binding_kind_diagnostic(
                selector_payload,
                expected=declaration.kind,
                actual="base",
                location=selector_payload.source,
            )
        return TargetReturnTypeBaseBinding(
            name=declaration.name,
            type_tag=value.type_tag,
        )

    if declaration.kind != "extension":
        return _wrong_return_binding_kind_diagnostic(
            selector_payload,
            expected=declaration.kind,
            actual="extension",
            location=value.source,
        )
    return TargetReturnTypeExtensionBinding(
        name=declaration.name,
        extension=value.name,
    )


def _selected_with_target_binding(
    selected: SelectedImplementation,
    binding: TargetSpecializationBinding,
) -> SelectedImplementation:
    return SelectedImplementation(
        target=Target(
            backend=selected.target.backend,
            primitive_name=selected.target.primitive_name,
            extension=selected.target.extension,
            type_tag=selected.target.type_tag,
            attributes=selected.target.attributes,
            specialization_bindings=(
                *selected.target.specialization_bindings,
                binding,
            ),
        ),
        primitive=selected.primitive,
        implementation=selected.implementation,
    )


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
    if isinstance(value, LoweredVectorTransformType):
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


def _wrong_return_binding_kind_diagnostic(
    selector_payload: PrimitiveCallSelectorPayload,
    *,
    expected: str,
    actual: str,
    location: SourceLocation,
) -> Diagnostic:
    return _unsupported_specialization_diagnostic(
        selector_payload,
        (
            "primitive-call selector return-type binding has the wrong kind "
            "for the matched target declaration; expected "
            f"return_type.{expected}, got return_type.{actual}"
        ),
        location=location,
    )


def _specialization_source(
    value: SelectorSpecializationValue,
    fallback: SourceLocation,
) -> SourceLocation:
    if isinstance(value, SelectorSymbol | SelectorLiteral):
        return value.source
    if isinstance(value, ExtensionOperand):
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


def _format_parameter_names(parameter_names: tuple[str, ...]) -> str:
    if not parameter_names:
        return "<none>"
    return "(" + ", ".join(parameter_names) + ")"


def _primitive_calls_in_source_order(
    selected: SelectedImplementation,
) -> Iterator[PrimitiveCall]:
    for token in selected.implementation.body.tokens:
        yield from _primitive_calls_from_token(token)


def _primitive_calls_from_token(token: BodyToken) -> Iterator[PrimitiveCall]:
    if not isinstance(token, LowerableDirective):
        return

    if token.primitive_call is not None:
        yield token.primitive_call

    for payload_token in token.payload_tokens:
        yield from _primitive_calls_from_token(payload_token)


def _selected_identity(selected: SelectedImplementation) -> _SelectedIdentity:
    return selected.target.sort_key()


def _unsupported_primitive_call_diagnostics_from_directives(
    directives: tuple[LowerableDirective, ...],
    *,
    selected: SelectedImplementation,
    catalog: Catalog | None,
) -> tuple[Diagnostic, ...]:
    return tuple(
        _unsupported_primitive_call_diagnostic(
            directive,
            selected=selected,
            catalog=catalog,
        )
        for directive in directives
    )


def _primitive_call_directives_from_body(
    body: ImplementationBody,
) -> tuple[LowerableDirective, ...]:
    return tuple(
        token
        for token in body.tokens
        if isinstance(token, LowerableDirective)
        and token.name == "call"
        and _has_primitive_call_shape(token)
    )


def _primitive_call_directives_from_tokens(
    tokens: tuple[PayloadToken, ...],
) -> tuple[LowerableDirective, ...]:
    return tuple(
        token
        for token in tokens
        if isinstance(token, LowerableDirective)
        and token.name == "call"
        and _has_primitive_call_shape(token)
    )


def _has_primitive_call_shape(directive: LowerableDirective) -> bool:
    return directive.primitive_call is not None or (
        len(directive.arguments) == 3 and directive.arguments[0] == "primitive"
    )


def _unsupported_primitive_call_diagnostic(
    directive: LowerableDirective,
    *,
    selected: SelectedImplementation,
    catalog: Catalog | None,
) -> Diagnostic:
    if _is_unknown_named_primitive_call_target(directive, catalog):
        code = "TSL-LOWER-UNKNOWN-PRIMITIVE-CALL-TARGET"
        message_prefix = "primitive call target is not in the catalog"
    else:
        code = "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL"
        message_prefix = "primitive call cannot be lowered by this exact boundary"

    return Diagnostic(
        severity="error",
        code=code,
        message=(
            f"{message_prefix}; "
            f"{_primitive_call_context(directive, selected=selected, catalog=catalog)}"
        ),
        location=directive.source,
    )


def _is_unknown_named_primitive_call_target(
    directive: LowerableDirective,
    catalog: Catalog | None,
) -> bool:
    if catalog is None or directive.primitive_call is None:
        return False
    target = directive.primitive_call.selector.target
    return (
        isinstance(target, NamedPrimitiveReference)
        and target.name not in _catalog_primitive_names(catalog)
    )


def _primitive_call_context(
    directive: LowerableDirective,
    *,
    selected: SelectedImplementation,
    catalog: Catalog | None,
) -> str:
    primitive_call = directive.primitive_call
    if primitive_call is None:
        return (
            f"selector remains opaque: {directive.arguments[1]!r}; "
            f"payload remains opaque: {directive.arguments[2]!r}; "
            f"{_MISSING_PRIMITIVE_CALL_CAPABILITY}"
        )

    selector = primitive_call.selector
    if isinstance(selector.target, NamedPrimitiveReference):
        target_details = (
            "target kind is named primitive",
            f"target name is {selector.target.name!r}",
        )
        base_target_known = (
            selector.target.name in _catalog_primitive_names(catalog)
            if catalog is not None
            else False
        )
    else:
        target_details = ("target kind is '@self'",)
        base_target_known = catalog is not None

    details = [
        *target_details,
        f"selector source text is {selector.source_text!r}",
    ]
    if catalog is not None:
        details.extend(
            _base_target_lookup_context(
                selected,
                selector.target,
                catalog,
            )
        )
    if selector.specialization is not None:
        details.append(
            f"specialization remains opaque: {selector.specialization!r}"
        )
        if base_target_known and catalog is not None:
            details.append(_MISSING_SPECIALIZATION_TARGET_CAPABILITY)
    if selector.attrs is not None:
        details.append(f"attrs remain opaque: {selector.attrs!r}")
        if base_target_known and catalog is not None:
            details.append(_MISSING_ATTRS_TARGET_CAPABILITY)
    details.append(f"raw argument count is {len(primitive_call.arguments)}")
    details.append(
        "raw argument payloads remain opaque: "
        f"{tuple(argument.text for argument in primitive_call.arguments)!r}"
    )
    details.append(f"payload remains opaque: {primitive_call.payload!r}")
    if catalog is None:
        details.append(_MISSING_PRIMITIVE_CALL_CAPABILITY)
    elif base_target_known:
        details.append(_MISSING_PRIMITIVE_CALL_SELECTION_CAPABILITY)
    return "; ".join(details)


def _base_target_lookup_context(
    selected: SelectedImplementation,
    target: object,
    catalog: Catalog,
) -> tuple[str, ...]:
    if not isinstance(target, NamedPrimitiveReference):
        return (
            "base target lookup succeeded: "
            f"'@self' identifies current primitive {selected.primitive.name!r}",
        )

    primitive_names = _catalog_primitive_names(catalog)
    if target.name in primitive_names:
        return (
            "base target lookup succeeded: "
            f"primitive {target.name!r} exists in catalog",
        )

    return (
        f"base target lookup failed: primitive {target.name!r} is not in catalog",
        f"known primitive names are: {_format_primitive_names(primitive_names)}",
    )


def _catalog_primitive_names(catalog: Catalog | None) -> tuple[str, ...]:
    if catalog is None:
        return ()
    return tuple(sorted(primitive.name for primitive in catalog.primitives))


def _format_primitive_names(names: tuple[str, ...]) -> str:
    if not names:
        return "<none>"
    return ", ".join(names)
