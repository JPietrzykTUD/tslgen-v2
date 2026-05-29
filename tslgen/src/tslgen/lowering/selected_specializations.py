"""Selected specialization binding helpers shared by lowering boundaries."""

import re

from tslgen.analysis.selection import (
    TargetReturnTypeBaseBinding,
    TargetReturnTypeExtensionBinding,
    TargetSpecializationBinding,
    TargetVectorTypeBinding,
)
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import ExtensionName
from tslgen.lowering.model import (
    CurrentVector,
    ExtensionOperand,
    LoweredScalarTypeIdentity,
    LoweredTypeValue,
    SelectedImplementationLoweringContext,
    SelectorSpecializationValue,
)

_BINDING_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def selected_specialization_binding_diagnostics(
    context: SelectedImplementationLoweringContext,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    seen_names: set[str] = set()
    duplicate_names: set[str] = set()
    for binding in context.selected_specialization_bindings:
        if _BINDING_NAME_RE.fullmatch(binding.name) is None:
            diagnostics.append(
                _malformed_selected_specialization_binding_diagnostic(
                    binding.name,
                    context.primitive_source,
                )
            )
        if binding.name in seen_names and binding.name not in duplicate_names:
            diagnostics.append(
                _duplicate_selected_specialization_binding_diagnostic(
                    binding.name,
                    context.primitive_source,
                )
            )
            duplicate_names.add(binding.name)
        seen_names.add(binding.name)
        validation = selected_specialization_binding_validation_diagnostic(
            context,
            binding,
            context.primitive_source,
        )
        if validation is not None:
            diagnostics.append(validation)
    return tuple(diagnostics)


def selected_specialization_type_value(
    context: SelectedImplementationLoweringContext,
    name: str,
    source: SourceLocation,
) -> LoweredTypeValue | Diagnostic | None:
    binding = find_selected_specialization_binding(context, name)
    if isinstance(binding, Diagnostic) or binding is None:
        return binding

    diagnostic = selected_specialization_binding_validation_diagnostic(
        context,
        binding,
        source,
    )
    if diagnostic is not None:
        return diagnostic

    if isinstance(binding, TargetReturnTypeBaseBinding):
        return LoweredScalarTypeIdentity(type_tag=binding.type_tag)
    if isinstance(binding, TargetVectorTypeBinding):
        return CurrentVector(
            extension=binding.extension,
            type_tag=binding.type_tag,
        )
    return selected_specialization_binding_kind_diagnostic(
        name,
        "return_type.base or type.vector",
        selected_specialization_binding_kind(binding),
        source,
    )


def selected_specialization_extension_name(
    context: SelectedImplementationLoweringContext,
    name: str,
    source: SourceLocation,
) -> ExtensionName | Diagnostic | None:
    binding = find_selected_specialization_binding(context, name)
    if isinstance(binding, Diagnostic):
        return binding
    if binding is None:
        declaration = context.primitive.return_type_binding
        if (
            declaration is not None
            and declaration.kind == "extension"
            and declaration.name == name
        ):
            return unbound_selected_specialization_binding_diagnostic(name, source)
        return None

    diagnostic = selected_specialization_binding_validation_diagnostic(
        context,
        binding,
        source,
    )
    if diagnostic is not None:
        return diagnostic
    if isinstance(binding, TargetReturnTypeExtensionBinding):
        return binding.extension
    return selected_specialization_binding_kind_diagnostic(
        binding.name,
        "return_type.extension",
        selected_specialization_binding_kind(binding),
        source,
    )


def selected_specialization_selector_value(
    context: SelectedImplementationLoweringContext,
    name: str,
    source: SourceLocation,
) -> SelectorSpecializationValue | Diagnostic | None:
    binding = find_selected_specialization_binding(context, name)
    if isinstance(binding, Diagnostic):
        return binding
    if binding is None:
        extension_name = selected_specialization_extension_name(
            context,
            name,
            source,
        )
        if isinstance(extension_name, Diagnostic):
            return extension_name
        return None

    diagnostic = selected_specialization_binding_validation_diagnostic(
        context,
        binding,
        source,
    )
    if diagnostic is not None:
        return diagnostic

    if isinstance(binding, TargetReturnTypeBaseBinding):
        return LoweredScalarTypeIdentity(type_tag=binding.type_tag)
    if isinstance(binding, TargetReturnTypeExtensionBinding):
        return ExtensionOperand(name=binding.extension, source=source)
    if isinstance(binding, TargetVectorTypeBinding):
        return CurrentVector(
            extension=binding.extension,
            type_tag=binding.type_tag,
        )
    raise AssertionError(f"unsupported specialization binding: {binding!r}")


def find_selected_specialization_binding(
    context: SelectedImplementationLoweringContext,
    name: str,
) -> TargetSpecializationBinding | Diagnostic | None:
    bindings = tuple(
        binding
        for binding in context.selected_specialization_bindings
        if binding.name == name
    )
    if not bindings:
        return None
    if len(bindings) > 1:
        return _duplicate_selected_specialization_binding_diagnostic(
            name,
            context.primitive_source,
        )
    return bindings[0]


def selected_specialization_binding_validation_diagnostic(
    context: SelectedImplementationLoweringContext,
    binding: TargetSpecializationBinding,
    source: SourceLocation,
) -> Diagnostic | None:
    if not isinstance(
        binding,
        TargetReturnTypeBaseBinding | TargetReturnTypeExtensionBinding,
    ):
        return None

    declaration = context.primitive.return_type_binding
    if declaration is None:
        return Diagnostic(
            severity="error",
            code="TSL-LOWER-UNDECLARED-SELECTED-SPECIALIZATION-BINDING",
            message=(
                "selected return-type specialization binding "
                f"{binding.name!r} has no primitive-local return_type "
                "declaration to validate against"
            ),
            location=source,
        )

    expected_kind = (
        "base"
        if isinstance(binding, TargetReturnTypeBaseBinding)
        else "extension"
    )
    if declaration.name != binding.name or declaration.kind != expected_kind:
        return Diagnostic(
            severity="error",
            code="TSL-LOWER-SELECTED-SPECIALIZATION-BINDING-MISMATCH",
            message=(
                "selected return-type specialization binding does not match "
                "the primitive-local return_type declaration; expected "
                f"{declaration.kind} binding {declaration.name!r}, got "
                f"{expected_kind} binding {binding.name!r}"
            ),
            location=source,
        )

    return None


def selected_specialization_binding_kind(
    binding: TargetSpecializationBinding,
) -> str:
    if isinstance(binding, TargetReturnTypeBaseBinding):
        return "return_type.base"
    if isinstance(binding, TargetReturnTypeExtensionBinding):
        return "return_type.extension"
    if isinstance(binding, TargetVectorTypeBinding):
        return "type.vector"
    raise AssertionError(f"unsupported specialization binding: {binding!r}")


def selected_specialization_binding_kind_diagnostic(
    name: str,
    expected: str,
    actual: str,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-SELECTED-SPECIALIZATION-BINDING-KIND-MISMATCH",
        message=(
            "selected specialization binding has the wrong kind for this "
            f"type expression; symbol {name!r} expected {expected}, got {actual}"
        ),
        location=source,
    )


def unbound_selected_specialization_binding_diagnostic(
    name: str,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-UNBOUND-SELECTED-SPECIALIZATION-BINDING",
        message=(
            "selected specialization symbol has a primitive-local "
            f"declaration but no selected binding was supplied for {name!r}"
        ),
        location=source,
    )


def _malformed_selected_specialization_binding_diagnostic(
    name: str,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-MALFORMED-SELECTED-SPECIALIZATION-BINDING",
        message=(
            "selected specialization binding name is malformed; expected an "
            f"identifier, got {name!r}"
        ),
        location=source,
    )


def _duplicate_selected_specialization_binding_diagnostic(
    name: str,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-DUPLICATE-SELECTED-SPECIALIZATION-BINDING",
        message=(
            "selected specialization binding names must be unique; duplicate "
            f"binding for {name!r}"
        ),
        location=source,
    )
