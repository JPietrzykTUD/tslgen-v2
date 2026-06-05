"""Backend intrinsic invocation assembly over translated modifier values."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, NewType

from tslgen.backends.intrinsic_modifiers import (
    BackendIntrinsicImmediateGenericParameterReference,
    BackendIntrinsicImmediateLiteral,
    BackendIntrinsicImmediateParameterReference,
    BackendIntrinsicInfixSeparator,
    BackendIntrinsicLiteralFragment,
    BackendTranslatedIntrinsicModifier,
)
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.backend_metadata import BackendId
from tslgen.domain.catalog import ExtensionCatalog, ExtensionName, TypeTag
from tslgen.lowering.model import (
    BackendDirectIntrinsicHandoffRequest,
    BackendIntrinsicComposeHandoffRequest,
    BackendIntrinsicHandoffRequest,
    BackendIntrinsicModifierField,
)

BackendIntrinsicNameText = NewType("BackendIntrinsicNameText", str)
BackendIntrinsicArgumentPayloadText = NewType(
    "BackendIntrinsicArgumentPayloadText",
    str,
)
BackendIntrinsicNamePartRole = Literal["prefix", "base", "infix", "suffix", "post"]

BackendIntrinsicInvocationImmediateValue = (
    BackendIntrinsicImmediateLiteral
    | BackendIntrinsicImmediateGenericParameterReference
    | BackendIntrinsicImmediateParameterReference
)

_DIRECT_LITERAL_NAME_RE = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*(?:::[A-Za-z_][A-Za-z0-9_]*)*\Z",
)


@dataclass(frozen=True, slots=True)
class BackendIntrinsicInvocationArguments:
    text: BackendIntrinsicArgumentPayloadText
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendIntrinsicNamePart:
    role: BackendIntrinsicNamePartRole
    text: BackendIntrinsicNameText
    source: SourceLocation
    modifier: BackendTranslatedIntrinsicModifier | None = None


@dataclass(frozen=True, slots=True)
class BackendIntrinsicComposeDefaultPolicy:
    backend: BackendId
    extension: ExtensionName
    type_tag: TypeTag
    prefix: BackendIntrinsicNameText
    prefix_source: SourceLocation
    suffix: BackendIntrinsicNameText
    suffix_source: SourceLocation
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendIntrinsicInvocationImmediate:
    argument_index: int
    value: BackendIntrinsicInvocationImmediateValue
    source: SourceLocation
    modifier: BackendTranslatedIntrinsicModifier


@dataclass(frozen=True, slots=True)
class BackendDirectIntrinsicInvocation:
    backend: BackendId
    request: BackendDirectIntrinsicHandoffRequest
    intrinsic_name: BackendIntrinsicNameText
    arguments: BackendIntrinsicInvocationArguments
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendComposedIntrinsicInvocation:
    backend: BackendId
    request: BackendIntrinsicComposeHandoffRequest
    intrinsic_name: BackendIntrinsicNameText
    name_parts: tuple[BackendIntrinsicNamePart, ...]
    arguments: BackendIntrinsicInvocationArguments
    immediates: tuple[BackendIntrinsicInvocationImmediate, ...]
    modifiers: tuple[BackendTranslatedIntrinsicModifier, ...]
    source: SourceLocation


BackendAssembledIntrinsicInvocation = (
    BackendDirectIntrinsicInvocation | BackendComposedIntrinsicInvocation
)


@dataclass(frozen=True, slots=True)
class BackendIntrinsicInvocationAssemblyResult:
    invocation: BackendAssembledIntrinsicInvocation | None
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class BackendIntrinsicComposeDefaultPolicyResult:
    policy: BackendIntrinsicComposeDefaultPolicy | None
    diagnostics: tuple[Diagnostic, ...] = ()


def resolve_backend_intrinsic_compose_default_policy(
    extension_catalog: ExtensionCatalog,
    backend: BackendId | str,
    extension: ExtensionName | str,
    type_tag: TypeTag | str,
    source: SourceLocation,
) -> BackendIntrinsicComposeDefaultPolicyResult:
    """Resolve default compose prefix/suffix metadata for a selected target."""

    backend_id = BackendId(str(backend))
    extension_name = ExtensionName(str(extension))
    selected_type_tag = TypeTag(str(type_tag))

    if str(backend_id) not in {"cpp", "rust"}:
        return BackendIntrinsicComposeDefaultPolicyResult(
            policy=None,
            diagnostics=(
                _unsupported_default_policy_backend_diagnostic(backend_id, source),
            ),
        )

    selected_extension = extension_catalog.get(str(extension_name))
    if selected_extension is None:
        return BackendIntrinsicComposeDefaultPolicyResult(
            policy=None,
            diagnostics=(
                _unknown_default_policy_extension_diagnostic(extension_name, source),
            ),
        )

    policy = selected_extension.intrinsic_compose_policy
    if policy is None:
        return BackendIntrinsicComposeDefaultPolicyResult(
            policy=None,
            diagnostics=(
                _missing_default_policy_diagnostic(extension_name, source),
            ),
        )

    prefix = next(
        (
            item
            for item in policy.prefixes
            if item.backend == str(backend_id)
        ),
        None,
    )
    if prefix is None:
        return BackendIntrinsicComposeDefaultPolicyResult(
            policy=None,
            diagnostics=(
                _missing_default_policy_backend_prefix_diagnostic(
                    backend_id,
                    extension_name,
                    policy.source,
                ),
            ),
        )

    suffix = next(
        (
            item
            for item in policy.suffixes
            if item.type_tag == selected_type_tag
        ),
        None,
    )
    if suffix is None:
        return BackendIntrinsicComposeDefaultPolicyResult(
            policy=None,
            diagnostics=(
                _missing_default_policy_type_suffix_diagnostic(
                    extension_name,
                    selected_type_tag,
                    policy.source,
                ),
            ),
        )

    return BackendIntrinsicComposeDefaultPolicyResult(
        policy=BackendIntrinsicComposeDefaultPolicy(
            backend=backend_id,
            extension=extension_name,
            type_tag=selected_type_tag,
            prefix=BackendIntrinsicNameText(prefix.spelling),
            prefix_source=prefix.source,
            suffix=BackendIntrinsicNameText(suffix.suffix),
            suffix_source=suffix.source,
            source=policy.source,
        ),
        diagnostics=(),
    )


def assemble_backend_intrinsic_invocation(
    request: BackendIntrinsicHandoffRequest,
    backend: BackendId | str,
    translated_modifiers: tuple[BackendTranslatedIntrinsicModifier, ...] = (),
    *,
    default_compose_policy: BackendIntrinsicComposeDefaultPolicy | None = None,
) -> BackendIntrinsicInvocationAssemblyResult:
    """Assemble one backend intrinsic handoff request into an invocation value."""

    backend_id = BackendId(str(backend))
    if isinstance(request, BackendDirectIntrinsicHandoffRequest):
        return _assemble_direct_invocation(request, backend_id, translated_modifiers)
    if isinstance(request, BackendIntrinsicComposeHandoffRequest):
        return _assemble_composed_invocation(
            request,
            backend_id,
            translated_modifiers,
            default_compose_policy,
        )
    raise AssertionError("unreachable backend intrinsic handoff request type")


def _assemble_direct_invocation(
    request: BackendDirectIntrinsicHandoffRequest,
    backend: BackendId,
    translated_modifiers: tuple[BackendTranslatedIntrinsicModifier, ...],
) -> BackendIntrinsicInvocationAssemblyResult:
    diagnostics: list[Diagnostic] = []
    diagnostics.extend(
        _extra_modifier_translation_diagnostic(request, modifier)
        for modifier in translated_modifiers
    )

    if _DIRECT_LITERAL_NAME_RE.fullmatch(request.angle_payload_text) is None:
        diagnostics.append(_unsupported_direct_name_diagnostic(request))

    if diagnostics:
        return BackendIntrinsicInvocationAssemblyResult(
            invocation=None,
            diagnostics=tuple(diagnostics),
        )

    return BackendIntrinsicInvocationAssemblyResult(
        invocation=BackendDirectIntrinsicInvocation(
            backend=backend,
            request=request,
            intrinsic_name=BackendIntrinsicNameText(request.angle_payload_text),
            arguments=_arguments(request.argument_text, request.argument_source),
            source=request.source,
        ),
        diagnostics=(),
    )


def _assemble_composed_invocation(
    request: BackendIntrinsicComposeHandoffRequest,
    backend: BackendId,
    translated_modifiers: tuple[BackendTranslatedIntrinsicModifier, ...],
    default_compose_policy: BackendIntrinsicComposeDefaultPolicy | None,
) -> BackendIntrinsicInvocationAssemblyResult:
    if (
        default_compose_policy is not None
        and default_compose_policy.backend != backend
    ):
        return BackendIntrinsicInvocationAssemblyResult(
            invocation=None,
            diagnostics=(
                _default_policy_backend_mismatch_diagnostic(
                    default_compose_policy,
                    backend,
                ),
            ),
        )

    matched = _matched_modifiers(request, backend, translated_modifiers)
    if matched.diagnostics:
        return BackendIntrinsicInvocationAssemblyResult(
            invocation=None,
            diagnostics=matched.diagnostics,
        )

    prefix_parts: list[BackendIntrinsicNamePart] = []
    infix_parts: list[BackendIntrinsicNamePart] = []
    suffix_parts: list[BackendIntrinsicNamePart] = []
    post_parts: list[BackendIntrinsicNamePart] = []
    immediates: list[BackendIntrinsicInvocationImmediate] = []
    infix_separator = "_"
    diagnostics: list[Diagnostic] = []

    for modifier in matched.modifiers:
        if modifier.name in {"prefix", "infix", "suffix", "post"}:
            if isinstance(modifier.value, BackendIntrinsicLiteralFragment):
                part = BackendIntrinsicNamePart(
                    role=modifier.name,
                    text=BackendIntrinsicNameText(str(modifier.value.text)),
                    source=modifier.source,
                    modifier=modifier,
                )
                if modifier.name == "prefix":
                    prefix_parts.append(part)
                elif modifier.name == "infix":
                    infix_parts.append(part)
                elif modifier.name == "suffix":
                    suffix_parts.append(part)
                else:
                    post_parts.append(part)
                continue
            diagnostics.append(
                _unsupported_modifier_value_diagnostic(
                    modifier,
                    "literal fragment",
                ),
            )
            continue

        if modifier.name == "infix_sep":
            if isinstance(modifier.value, BackendIntrinsicInfixSeparator):
                infix_separator = str(modifier.value.text)
                continue
            diagnostics.append(
                _unsupported_modifier_value_diagnostic(
                    modifier,
                    "infix separator",
                ),
            )
            continue

        if modifier.name == "immediate":
            if isinstance(
                modifier.value,
                (
                    BackendIntrinsicImmediateLiteral,
                    BackendIntrinsicImmediateGenericParameterReference,
                    BackendIntrinsicImmediateParameterReference,
                ),
            ):
                immediates.append(
                    BackendIntrinsicInvocationImmediate(
                        argument_index=modifier.value.argument_index,
                        value=modifier.value,
                        source=modifier.source,
                        modifier=modifier,
                    )
                )
                continue
            diagnostics.append(
                _unsupported_modifier_value_diagnostic(
                    modifier,
                    "immediate metadata",
                ),
            )
            continue

        diagnostics.append(
            _unsupported_modifier_value_diagnostic(
                modifier,
                "prefix, infix, suffix, post, infix_sep, or immediate",
            )
        )

    explicit_name_parts = {
        modifier.name
        for modifier in matched.modifiers
        if modifier.name in {"prefix", "infix", "suffix", "post"}
    }
    if default_compose_policy is not None:
        if "prefix" not in explicit_name_parts:
            prefix_parts.insert(
                0,
                BackendIntrinsicNamePart(
                    role="prefix",
                    text=default_compose_policy.prefix,
                    source=default_compose_policy.prefix_source,
                    modifier=None,
                ),
            )
        if "suffix" not in explicit_name_parts:
            suffix_parts.append(
                BackendIntrinsicNamePart(
                    role="suffix",
                    text=default_compose_policy.suffix,
                    source=default_compose_policy.suffix_source,
                    modifier=None,
                )
            )

    if diagnostics:
        return BackendIntrinsicInvocationAssemblyResult(
            invocation=None,
            diagnostics=tuple(diagnostics),
        )

    base_part = BackendIntrinsicNamePart(
        role="base",
        text=BackendIntrinsicNameText(request.base_text),
        source=request.base_source,
        modifier=None,
    )
    name_parts = (
        tuple(prefix_parts)
        + (base_part,)
        + tuple(infix_parts)
        + tuple(suffix_parts)
        + tuple(post_parts)
    )

    return BackendIntrinsicInvocationAssemblyResult(
        invocation=BackendComposedIntrinsicInvocation(
            backend=backend,
            request=request,
            intrinsic_name=_assembled_composed_name(
                request.base_text,
                prefix_parts,
                infix_parts,
                suffix_parts,
                post_parts,
                infix_separator,
            ),
            name_parts=name_parts,
            arguments=_arguments(request.argument_text, request.argument_source),
            immediates=tuple(immediates),
            modifiers=matched.modifiers,
            source=request.source,
        ),
        diagnostics=(),
    )


@dataclass(frozen=True, slots=True)
class _MatchedModifiers:
    modifiers: tuple[BackendTranslatedIntrinsicModifier, ...]
    diagnostics: tuple[Diagnostic, ...]


def _matched_modifiers(
    request: BackendIntrinsicComposeHandoffRequest,
    backend: BackendId,
    translated_modifiers: tuple[BackendTranslatedIntrinsicModifier, ...],
) -> _MatchedModifiers:
    request_fields = {id(field): field for field in request.modifiers}
    seen: set[int] = set()
    invalid_field_ids: set[int] = set()
    matched_by_field: dict[int, BackendTranslatedIntrinsicModifier] = {}
    diagnostics: list[Diagnostic] = []

    for modifier in translated_modifiers:
        field_id = id(modifier.field)
        if field_id not in request_fields:
            diagnostics.append(
                _extra_modifier_translation_diagnostic(request, modifier)
            )
            continue
        if modifier.backend != backend:
            diagnostics.append(_modifier_backend_mismatch_diagnostic(modifier, backend))
            invalid_field_ids.add(field_id)
            continue
        if field_id in seen:
            diagnostics.append(_duplicate_modifier_translation_diagnostic(modifier))
            continue
        seen.add(field_id)
        matched_by_field[field_id] = modifier

    ordered: list[BackendTranslatedIntrinsicModifier] = []
    for field in request.modifiers:
        modifier = matched_by_field.get(id(field))
        if modifier is None:
            if id(field) in invalid_field_ids:
                continue
            diagnostics.append(_missing_modifier_translation_diagnostic(field))
            continue
        ordered.append(modifier)

    if diagnostics:
        return _MatchedModifiers(modifiers=(), diagnostics=tuple(diagnostics))
    return _MatchedModifiers(modifiers=tuple(ordered), diagnostics=())


def _assembled_composed_name(
    base_text: str,
    prefix_parts: list[BackendIntrinsicNamePart],
    infix_parts: list[BackendIntrinsicNamePart],
    suffix_parts: list[BackendIntrinsicNamePart],
    post_parts: list[BackendIntrinsicNamePart],
    infix_separator: str,
) -> BackendIntrinsicNameText:
    name = "".join(str(part.text) for part in prefix_parts) + base_text
    infix_texts = tuple(str(part.text) for part in infix_parts)
    suffix_texts = tuple(str(part.text) for part in suffix_parts)
    post_texts = tuple(str(part.text) for part in post_parts)

    if infix_texts:
        name += infix_separator + "_".join(infix_texts)
        if suffix_texts:
            name += "_" + "_".join(suffix_texts)
    elif suffix_texts:
        name += "_" + "_".join(suffix_texts)

    if post_texts:
        name += "_" + "_".join(post_texts)

    return BackendIntrinsicNameText(name)


def _arguments(
    text: str,
    source: SourceLocation,
) -> BackendIntrinsicInvocationArguments:
    return BackendIntrinsicInvocationArguments(
        text=BackendIntrinsicArgumentPayloadText(text),
        source=source,
    )


def _unsupported_direct_name_diagnostic(
    request: BackendDirectIntrinsicHandoffRequest,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-INTRINSIC-ASSEMBLY-UNSUPPORTED-DIRECT-NAME",
        message=(
            "direct backend intrinsic name is not a literal backend intrinsic "
            f"name: {request.angle_payload_text!r}; unresolved placeholders and "
            "template-like payloads require a later direct-name translation rule"
        ),
        location=request.angle_payload_source,
    )


def _extra_modifier_translation_diagnostic(
    request: BackendIntrinsicHandoffRequest,
    modifier: BackendTranslatedIntrinsicModifier,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-INTRINSIC-ASSEMBLY-EXTRA-MODIFIER-TRANSLATION",
        message=(
            "translated intrinsic modifier does not belong to this intrinsic "
            f"request: {modifier.field.source_text!r}"
        ),
        location=modifier.source,
    )


def _modifier_backend_mismatch_diagnostic(
    modifier: BackendTranslatedIntrinsicModifier,
    backend: BackendId,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-INTRINSIC-ASSEMBLY-BACKEND-MISMATCH",
        message=(
            f"translated intrinsic modifier backend {str(modifier.backend)!r} "
            f"does not match invocation backend {str(backend)!r}"
        ),
        location=modifier.source,
    )


def _duplicate_modifier_translation_diagnostic(
    modifier: BackendTranslatedIntrinsicModifier,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-INTRINSIC-ASSEMBLY-DUPLICATE-MODIFIER-TRANSLATION",
        message=(
            "intrinsic modifier field has more than one translated result: "
            f"{modifier.field.source_text!r}"
        ),
        location=modifier.source,
    )


def _missing_modifier_translation_diagnostic(
    field: BackendIntrinsicModifierField,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-INTRINSIC-ASSEMBLY-MISSING-MODIFIER-TRANSLATION",
        message=(
            "intrinsic compose modifier has no translated backend modifier "
            f"result: {field.source_text!r}"
        ),
        location=field.source,
    )


def _unsupported_modifier_value_diagnostic(
    modifier: BackendTranslatedIntrinsicModifier,
    expected: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-INTRINSIC-ASSEMBLY-UNSUPPORTED-MODIFIER-VALUE",
        message=(
            f"intrinsic modifier {modifier.field.key_text!r} translated to an "
            f"unsupported value for invocation assembly; expected {expected}"
        ),
        location=modifier.source,
    )


def _unsupported_default_policy_backend_diagnostic(
    backend: BackendId,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-INTRINSIC-COMPOSE-DEFAULT-UNSUPPORTED-BACKEND",
        message=(
            "default intrinsic compose policy supports only backend 'cpp' or "
            f"'rust', not {str(backend)!r}"
        ),
        location=source,
    )


def _unknown_default_policy_extension_diagnostic(
    extension: ExtensionName,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-INTRINSIC-COMPOSE-DEFAULT-UNKNOWN-EXTENSION",
        message=(
            "default intrinsic compose policy requested unknown extension "
            f"{str(extension)!r}"
        ),
        location=source,
    )


def _missing_default_policy_diagnostic(
    extension: ExtensionName,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-INTRINSIC-COMPOSE-DEFAULT-MISSING-POLICY",
        message=(
            "extension "
            f"{str(extension)!r} has no intrinsic_compose default policy"
        ),
        location=source,
    )


def _missing_default_policy_backend_prefix_diagnostic(
    backend: BackendId,
    extension: ExtensionName,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-INTRINSIC-COMPOSE-DEFAULT-MISSING-BACKEND-PREFIX",
        message=(
            "extension "
            f"{str(extension)!r} intrinsic_compose policy has no default "
            f"prefix for backend {str(backend)!r}"
        ),
        location=source,
    )


def _missing_default_policy_type_suffix_diagnostic(
    extension: ExtensionName,
    type_tag: TypeTag,
    source: SourceLocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-INTRINSIC-COMPOSE-DEFAULT-MISSING-TYPE-SUFFIX",
        message=(
            "extension "
            f"{str(extension)!r} intrinsic_compose policy has no default "
            f"suffix for type tag {str(type_tag)!r}"
        ),
        location=source,
    )


def _default_policy_backend_mismatch_diagnostic(
    policy: BackendIntrinsicComposeDefaultPolicy,
    backend: BackendId,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-BACKEND-INTRINSIC-COMPOSE-DEFAULT-BACKEND-MISMATCH",
        message=(
            "default intrinsic compose policy backend "
            f"{str(policy.backend)!r} does not match invocation backend "
            f"{str(backend)!r}"
        ),
        location=policy.source,
    )
