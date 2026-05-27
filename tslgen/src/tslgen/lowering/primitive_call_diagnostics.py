"""Primitive-call lowering diagnostics for recognized TSIL call islands."""

from tslgen.analysis.selection import SelectedImplementation
from tslgen.core.diagnostics import Diagnostic
from tslgen.domain.catalog import (
    Catalog,
    ImplementationBody,
    LowerableDirective,
    NamedPrimitiveReference,
    PayloadToken,
)

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


def unsupported_primitive_call_diagnostics(
    body: ImplementationBody,
    *,
    selected: SelectedImplementation,
    catalog: Catalog | None,
) -> tuple[Diagnostic, ...]:
    return unsupported_primitive_call_diagnostics_from_directives(
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
    return unsupported_primitive_call_diagnostics_from_directives(
        primitive_call_tokens,
        selected=selected,
        catalog=catalog,
    )


def unsupported_primitive_call_diagnostics_from_directives(
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
