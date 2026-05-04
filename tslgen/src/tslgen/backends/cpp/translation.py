from __future__ import annotations

from dataclasses import dataclass, field

from tslgen.analysis.candidates import ImplementationCandidate
from tslgen.core.diagnostics import Diagnostic, has_errors, sort_diagnostics
from tslgen.core.frozen_map import FrozenMap
from tslgen.core.result import Result
from tslgen.domain.backends import (
    BackendMetadataBoundary,
    LanguageTypeEntry,
    TranslationSnippet,
)
from tslgen.domain.extensions import Extension
from tslgen.lowering import (
    LoweredImplementation,
    LoweringPlan,
    TranslatedIntrinsicCall,
    TsilIntrinsicComposeExpression,
    TsilReturnStatement,
)


CPP_TRANSLATION_BACKEND_ID = "cpp"
_SELECTED_INTRINSIC = "add"
_SELECTED_EXTENSION = "avx2"
_SELECTED_TYPE_TAG = "f32"
_SELECTED_INTRINSIC_STYLE = "x86"
_SELECTED_VECTOR_BITS = 256
_SELECTED_INTRINSIC_SUFFIX = "ps"


@dataclass(frozen=True, slots=True)
class CppNativeTranslationPlan:
    calls: tuple[TranslatedIntrinsicCall, ...] = ()
    calls_by_candidate_id: FrozenMap[str, TranslatedIntrinsicCall] = field(
        init=False
    )

    def __post_init__(self) -> None:
        calls = tuple(sorted(self.calls, key=lambda call: call.key))
        object.__setattr__(self, "calls", calls)
        object.__setattr__(
            self,
            "calls_by_candidate_id",
            FrozenMap((call.candidate_id, call) for call in calls),
        )

    @property
    def key(self) -> tuple[object, ...]:
        return tuple(call.key for call in self.calls)


def translate_cpp_native_intrinsic_calls(
    candidates: tuple[ImplementationCandidate, ...],
    lowering_plan: LoweringPlan,
    *,
    metadata_boundary: BackendMetadataBoundary | None,
    extensions: tuple[Extension, ...] = (),
) -> Result[CppNativeTranslationPlan]:
    native_candidates = tuple(
        candidate
        for candidate in candidates
        if _is_native_translation_candidate(candidate)
    )
    if not native_candidates:
        return Result.ok(CppNativeTranslationPlan())

    metadata_diagnostics = _metadata_diagnostics(metadata_boundary)
    if metadata_diagnostics:
        ordered = sort_diagnostics(metadata_diagnostics)
        return Result.failure(ordered)
    if metadata_boundary is None:
        raise AssertionError("metadata diagnostics must cover missing boundary")

    language_map = metadata_boundary.metadata.language_maps_by_backend[
        CPP_TRANSLATION_BACKEND_ID
    ]
    translation_map = metadata_boundary.metadata.translation_maps_by_backend[
        CPP_TRANSLATION_BACKEND_ID
    ]
    extensions_by_name = FrozenMap(
        (extension.name, extension) for extension in extensions
    )

    diagnostics: list[Diagnostic] = []
    calls: list[TranslatedIntrinsicCall] = []
    for candidate in native_candidates:
        translated = _translate_candidate(
            candidate,
            lowering_plan,
            language_map_entries=language_map.entries_by_type,
            translation_snippets=translation_map.snippets_by_name,
            extensions_by_name=extensions_by_name,
        )
        diagnostics.extend(translated.diagnostics)
        if translated.is_ok:
            calls.append(translated.unwrap())

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    return Result.ok(CppNativeTranslationPlan(tuple(calls)), diagnostics=ordered)


def _metadata_diagnostics(
    metadata_boundary: BackendMetadataBoundary | None,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    if metadata_boundary is None:
        return (
            Diagnostic.error(
                "TSL-CPP-TRANSLATE-MISSING-LANGUAGE-MAP",
                "C++ native translation requires backend metadata containing "
                "language type map 'cpp'",
            ),
            Diagnostic.error(
                "TSL-CPP-TRANSLATE-MISSING-TRANSLATION-MAP",
                "C++ native translation requires backend metadata containing "
                "translation map 'cpp'",
            ),
        )
    if CPP_TRANSLATION_BACKEND_ID not in metadata_boundary.active_backend_ids:
        diagnostics.append(
            Diagnostic.error(
                "TSL-CPP-TRANSLATE-UNSUPPORTED-BACKEND",
                "C++ native translation requires active backend 'cpp'; active "
                f"backends: {', '.join(repr(item) for item in metadata_boundary.active_backend_ids)}",
            )
        )
    if CPP_TRANSLATION_BACKEND_ID not in metadata_boundary.metadata.language_maps_by_backend:
        diagnostics.append(
            Diagnostic.error(
                "TSL-CPP-TRANSLATE-MISSING-LANGUAGE-MAP",
                "C++ native translation requires language type map 'cpp'",
            )
        )
    if CPP_TRANSLATION_BACKEND_ID not in metadata_boundary.metadata.translation_maps_by_backend:
        diagnostics.append(
            Diagnostic.error(
                "TSL-CPP-TRANSLATE-MISSING-TRANSLATION-MAP",
                "C++ native translation requires translation map 'cpp'",
            )
        )
    return tuple(diagnostics)


def _translate_candidate(
    candidate: ImplementationCandidate,
    lowering_plan: LoweringPlan,
    *,
    language_map_entries: FrozenMap[str, LanguageTypeEntry],
    translation_snippets: FrozenMap[str, TranslationSnippet],
    extensions_by_name: FrozenMap[str, Extension],
) -> Result[TranslatedIntrinsicCall]:
    generation_diagnostic = _unresolved_generation_helper_diagnostic(
        candidate,
        lowering_plan,
    )
    if generation_diagnostic is not None:
        return Result.failure((generation_diagnostic,))

    if candidate.target_extension != _SELECTED_EXTENSION:
        return Result.failure((_unsupported_extension_diagnostic(candidate),))
    if candidate.source_extension != _SELECTED_EXTENSION:
        return Result.failure((_unsupported_extension_diagnostic(candidate),))
    extension = extensions_by_name.get(candidate.target_extension)
    if extension is None:
        return Result.failure((_unsupported_extension_diagnostic(candidate),))
    if (
        extension.fields.get("intrinsic_style") != _SELECTED_INTRINSIC_STYLE
        or extension.vector_bits != _SELECTED_VECTOR_BITS
    ):
        return Result.failure((_unsupported_extension_diagnostic(candidate),))

    type_entry = language_map_entries.get(candidate.type_tag)
    backend_type = type_entry.target_type if type_entry is not None else None
    if candidate.type_tag != _SELECTED_TYPE_TAG or backend_type is None:
        return Result.failure((_unsupported_type_diagnostic(candidate),))

    if "emit_return" not in translation_snippets:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-CPP-TRANSLATE-MISSING-TRANSLATION-MAP",
                    "C++ native translation requires translation map 'cpp' to "
                    "include emit_return metadata",
                    location=candidate.variant.source.declaration.source_span.location,
                ),
            )
        )

    lowered = lowering_plan.implementations_by_candidate_id.get(candidate.candidate_id)
    if lowered is None:
        return Result.failure((_missing_lowered_body_diagnostic(candidate),))

    expression = _intrinsic_compose_expression(candidate, lowered)
    if not expression.is_ok:
        return Result.failure(expression.diagnostics)
    intrinsic_expression = expression.unwrap()
    if intrinsic_expression.intrinsic != _SELECTED_INTRINSIC:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-CPP-TRANSLATE-UNSUPPORTED-INTRINSIC",
                    "C++ native translation supports only lowered "
                    "intrin_compose<add> for the selected avx2/f32 slice; got "
                    f"{intrinsic_expression.intrinsic!r}",
                    location=candidate.variant.source.declaration.source_span.location,
                ),
            )
        )
    if len(intrinsic_expression.arguments) != 2:
        return Result.failure((_unsupported_lowered_body_diagnostic(candidate, lowered),))

    argument_names = tuple(argument.name for argument in intrinsic_expression.arguments)
    parameter_names = tuple(
        parameter.name
        for parameter in candidate.variant.source.declaration.parameters
    )
    unknown_names = tuple(sorted(set(argument_names) - set(parameter_names)))
    if unknown_names:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-CPP-TRANSLATE-PARAMETER",
                    "C++ native translation received lowered parameter "
                    f"reference(s) not present in primitive {candidate.emitted_primitive_name!r}: "
                    f"{', '.join(repr(name) for name in unknown_names)}",
                    location=candidate.variant.source.declaration.source_span.location,
                ),
            )
        )

    prefix = _selected_intrinsic_prefix(extension)
    function_name = (
        f"{prefix}{intrinsic_expression.intrinsic}_{_SELECTED_INTRINSIC_SUFFIX}"
    )
    return Result.ok(
        TranslatedIntrinsicCall(
            candidate_id=candidate.candidate_id,
            backend_id=CPP_TRANSLATION_BACKEND_ID,
            intrinsic=intrinsic_expression.intrinsic,
            extension=candidate.target_extension,
            type_tag=candidate.type_tag,
            backend_type=backend_type,
            function_name=function_name,
            arguments=intrinsic_expression.arguments,
        )
    )


def _intrinsic_compose_expression(
    candidate: ImplementationCandidate,
    lowered: LoweredImplementation,
) -> Result[TsilIntrinsicComposeExpression]:
    if lowered.status != "lowered" or len(lowered.statements) != 1:
        return Result.failure((_unsupported_lowered_body_diagnostic(candidate, lowered),))
    statement = lowered.statements[0]
    if not isinstance(statement, TsilReturnStatement):
        return Result.failure((_unsupported_lowered_body_diagnostic(candidate, lowered),))
    expression = statement.expression
    if not isinstance(expression, TsilIntrinsicComposeExpression):
        return Result.failure((_unsupported_lowered_body_diagnostic(candidate, lowered),))
    return Result.ok(expression)


def _selected_intrinsic_prefix(extension: Extension) -> str:
    if (
        extension.fields.get("intrinsic_style") == _SELECTED_INTRINSIC_STYLE
        and extension.vector_bits == _SELECTED_VECTOR_BITS
    ):
        return "_mm256_"
    raise ValueError("selected C++ native prefix requested for unsupported extension")


def _is_native_translation_candidate(candidate: ImplementationCandidate) -> bool:
    return (
        candidate.emitted_primitive_name == "add"
        and candidate.template_name == "binary"
        and candidate.variant.source.signature.normalized == "v:=(v,v)"
        and candidate.target_extension != "scalar"
        and candidate.source_extension != "scalar"
    )


def _unresolved_generation_helper_diagnostic(
    candidate: ImplementationCandidate,
    lowering_plan: LoweringPlan,
) -> Diagnostic | None:
    lowering_input = lowering_plan.input_set.inputs_by_candidate_id.get(
        candidate.candidate_id
    )
    if lowering_input is None or not lowering_input.payload.has_generation_condition:
        return None
    lowered = lowering_plan.implementations_by_candidate_id.get(candidate.candidate_id)
    if lowered is not None and lowered.generation_branches:
        return None
    return Diagnostic.error(
        "TSL-CPP-TRANSLATE-GENERATION-UNRESOLVED",
        "C++ native translation requires generation-time helpers to be resolved "
        "before backend translation",
        location=candidate.variant.source.declaration.source_span.location,
    )


def _missing_lowered_body_diagnostic(
    candidate: ImplementationCandidate,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-TRANSLATE-LOWERING-MISSING",
        "C++ native translation requires a lowered implementation for "
        f"candidate {candidate.candidate_id!r}",
        location=candidate.variant.source.declaration.source_span.location,
    )


def _unsupported_lowered_body_diagnostic(
    candidate: ImplementationCandidate,
    lowered: LoweredImplementation,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-TRANSLATE-LOWERING-UNSUPPORTED",
        "C++ native translation supports only one lowered intrinsic-compose "
        f"return statement for candidate {candidate.candidate_id!r}; lowered "
        f"status is {lowered.status!r} with {len(lowered.statements)} statement(s)",
        location=candidate.variant.source.declaration.source_span.location,
    )


def _unsupported_extension_diagnostic(
    candidate: ImplementationCandidate,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-TRANSLATE-UNSUPPORTED-EXTENSION",
        "C++ native translation supports only the selected avx2 extension for "
        f"this slice; candidate {candidate.candidate_id!r} has target extension "
        f"{candidate.target_extension!r} and source extension {candidate.source_extension!r}",
        location=candidate.variant.source.declaration.source_span.location,
    )


def _unsupported_type_diagnostic(
    candidate: ImplementationCandidate,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-TRANSLATE-UNSUPPORTED-TYPE",
        "C++ native translation supports only the selected f32 type for this "
        f"slice; candidate {candidate.candidate_id!r} has type tag "
        f"{candidate.type_tag!r}",
        location=candidate.variant.source.declaration.source_span.location,
    )
