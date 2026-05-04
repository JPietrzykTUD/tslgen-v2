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
    BackendIntrinsicModifier,
    BackendIntrinsicModifierRequest,
    BackendTypeSpelling,
    BackendTypeSpellingRequest,
    GenerationTypeRef,
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
_SELECTED_INTEGER_SUFFIX_TYPE_TAGS = ("si32", "ui32")
_SELECTED_SUFFIX_SOURCE_REF_KIND = "base.signed_of"
_SELECTED_INTEGER_SUFFIX_TYPE_TAG = "si32"
_SELECTED_INTEGER_INTRINSIC_SUFFIX = "epi32"
_SELECTED_MODIFIER_METADATA_SNIPPET = "type_signed_of"
_SELECTED_TYPE_SPELLING_SOURCE_REF_KINDS = (
    "base.in",
    "base.signed_of",
    "base.unsigned_of",
)
_SELECTED_TYPE_SPELLING_TAGS = ("si32", "ui32")
_CPP_LANGUAGE_TYPE_KEY_BY_TAG = {
    "si32": "s32",
    "ui32": "u32",
}
_RAW_GENERATION_HELPER_MARKERS = (
    "if<generation>",
    "type<generation>",
    "value<generation>",
)


@dataclass(frozen=True, slots=True)
class CppNativeTranslationPlan:
    calls: tuple[TranslatedIntrinsicCall, ...] = ()
    modifiers: tuple[BackendIntrinsicModifier, ...] = ()
    type_spellings: tuple[BackendTypeSpelling, ...] = ()
    calls_by_candidate_id: FrozenMap[str, TranslatedIntrinsicCall] = field(
        init=False
    )

    def __post_init__(self) -> None:
        calls = tuple(sorted(self.calls, key=lambda call: call.key))
        modifiers = tuple(sorted(self.modifiers, key=lambda modifier: modifier.key))
        type_spellings = tuple(
            sorted(self.type_spellings, key=lambda spelling: spelling.key)
        )
        object.__setattr__(self, "calls", calls)
        object.__setattr__(self, "modifiers", modifiers)
        object.__setattr__(self, "type_spellings", type_spellings)
        object.__setattr__(
            self,
            "calls_by_candidate_id",
            FrozenMap((call.candidate_id, call) for call in calls),
        )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            tuple(call.key for call in self.calls),
            tuple(modifier.key for modifier in self.modifiers),
            tuple(spelling.key for spelling in self.type_spellings),
        )


@dataclass(frozen=True, slots=True)
class _CandidateTranslation:
    call: TranslatedIntrinsicCall | None = None
    modifier: BackendIntrinsicModifier | None = None
    type_spellings: tuple[BackendTypeSpelling, ...] = ()


def translate_cpp_intrinsic_suffix_modifier(
    request: BackendIntrinsicModifierRequest,
    *,
    translation_snippets: FrozenMap[str, TranslationSnippet] | None,
) -> Result[BackendIntrinsicModifier]:
    if _contains_raw_generation_helper(request.raw_helper_text):
        return Result.failure((_unresolved_modifier_generation_diagnostic(request),))

    malformed_fields = tuple(
        field_name
        for field_name, value in (
            ("kind", request.kind),
            ("backend_id", request.backend_id),
            ("extension", request.extension),
            ("intrinsic", request.intrinsic),
        )
        if not value
    )
    if malformed_fields:
        return Result.failure(
            (_malformed_modifier_request_diagnostic(request, malformed_fields),)
        )

    if request.kind != "suffix":
        return Result.failure((_unsupported_modifier_family_diagnostic(request),))
    if request.backend_id != CPP_TRANSLATION_BACKEND_ID:
        return Result.failure((_unsupported_modifier_backend_diagnostic(request),))
    if request.extension != _SELECTED_EXTENSION:
        return Result.failure((_unsupported_modifier_extension_diagnostic(request),))
    if translation_snippets is None or "emit_return" not in translation_snippets:
        return Result.failure((_missing_modifier_translation_metadata(request),))
    if _SELECTED_MODIFIER_METADATA_SNIPPET not in translation_snippets:
        return Result.failure((_missing_modifier_metadata_diagnostic(request),))
    if request.intrinsic != _SELECTED_INTRINSIC:
        return Result.failure((_unsupported_modifier_intrinsic_diagnostic(request),))
    type_ref = request.type_ref
    if type_ref is None:
        return Result.failure((_missing_modifier_type_ref_diagnostic(request),))
    if type_ref.kind != _SELECTED_SUFFIX_SOURCE_REF_KIND:
        return Result.failure((_unsupported_modifier_source_ref_diagnostic(request),))
    if (
        type_ref.type_tag != _SELECTED_INTEGER_SUFFIX_TYPE_TAG
        or type_ref.source_type_tag not in _SELECTED_INTEGER_SUFFIX_TYPE_TAGS
    ):
        return Result.failure((_unsupported_modifier_type_tag_diagnostic(request),))

    return Result.ok(
        BackendIntrinsicModifier(
            kind="suffix",
            backend_id=request.backend_id,
            extension=request.extension,
            intrinsic=request.intrinsic,
            value=_SELECTED_INTEGER_INTRINSIC_SUFFIX,
            source_type_tag=type_ref.type_tag,
            source_ref_kind=type_ref.kind,
        )
    )


def translate_cpp_backend_type_spelling(
    request: BackendTypeSpellingRequest,
    *,
    language_map_entries: FrozenMap[str, LanguageTypeEntry] | None,
) -> Result[BackendTypeSpelling]:
    if _contains_raw_generation_helper(request.raw_helper_text):
        return Result.failure((_unresolved_type_spelling_generation_diagnostic(request),))

    if not request.backend_id:
        return Result.failure((_malformed_type_spelling_request_diagnostic(request),))
    if request.backend_id != CPP_TRANSLATION_BACKEND_ID:
        return Result.failure((_unsupported_type_spelling_backend_diagnostic(request),))
    if language_map_entries is None:
        return Result.failure((_missing_type_spelling_language_map(request),))

    type_ref = request.type_ref
    if type_ref is None:
        return Result.failure((_missing_type_spelling_type_ref_diagnostic(request),))
    if type_ref.kind not in _SELECTED_TYPE_SPELLING_SOURCE_REF_KINDS:
        return Result.failure((_unsupported_type_spelling_source_ref_diagnostic(request),))
    if not _is_selected_type_spelling_ref(type_ref):
        return Result.failure((_unsupported_type_spelling_type_tag_diagnostic(request),))

    language_key = _CPP_LANGUAGE_TYPE_KEY_BY_TAG[type_ref.type_tag]
    type_entry = language_map_entries.get(language_key)
    if type_entry is None:
        return Result.failure(
            (_missing_type_spelling_metadata_diagnostic(request, language_key),)
        )

    return Result.ok(
        BackendTypeSpelling(
            backend_id=request.backend_id,
            type_tag=type_ref.type_tag,
            spelling=type_entry.target_type,
            source_ref_kind=type_ref.kind,
            source_type_tag=type_ref.source_type_tag,
        )
    )


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
    modifiers: list[BackendIntrinsicModifier] = []
    type_spellings: list[BackendTypeSpelling] = []
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
            candidate_translation = translated.unwrap()
            if candidate_translation.call is not None:
                calls.append(candidate_translation.call)
            if candidate_translation.modifier is not None:
                modifiers.append(candidate_translation.modifier)
            type_spellings.extend(candidate_translation.type_spellings)

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    return Result.ok(
        CppNativeTranslationPlan(
            tuple(calls),
            tuple(modifiers),
            tuple(type_spellings),
        ),
        diagnostics=ordered,
    )


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
) -> Result[_CandidateTranslation]:
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

    if (
        candidate.type_tag != _SELECTED_TYPE_TAG
        and candidate.type_tag not in _SELECTED_INTEGER_SUFFIX_TYPE_TAGS
    ):
        return Result.failure((_unsupported_type_diagnostic(candidate),))

    lowered = lowering_plan.implementations_by_candidate_id.get(candidate.candidate_id)
    if lowered is None:
        return Result.failure((_missing_lowered_body_diagnostic(candidate),))

    expression = _intrinsic_compose_expression(candidate, lowered)
    if not expression.is_ok:
        return Result.failure(expression.diagnostics)
    intrinsic_expression = expression.unwrap()
    if intrinsic_expression.intrinsic != _SELECTED_INTRINSIC:
        if candidate.type_tag in _SELECTED_INTEGER_SUFFIX_TYPE_TAGS:
            return Result.failure(
                (
                    _unsupported_modifier_intrinsic_diagnostic(
                        BackendIntrinsicModifierRequest(
                            kind="suffix",
                            backend_id=CPP_TRANSLATION_BACKEND_ID,
                            extension=candidate.target_extension,
                            intrinsic=intrinsic_expression.intrinsic,
                            source_location=(
                                candidate.variant.source.declaration.source_span.location
                            ),
                        )
                    ),
                )
            )
        return Result.failure(
            (_unsupported_intrinsic_diagnostic(candidate, intrinsic_expression.intrinsic),)
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

    if candidate.type_tag in _SELECTED_INTEGER_SUFFIX_TYPE_TAGS:
        type_spellings = _translate_generation_type_spellings(
            candidate,
            lowered,
            language_map_entries=language_map_entries,
        )
        if not type_spellings.is_ok:
            return Result.failure(type_spellings.diagnostics)

        type_ref = _suffix_generation_type_ref(candidate, lowered)
        if not type_ref.is_ok:
            return Result.failure(type_ref.diagnostics)
        if type_ref.unwrap() is None and lowered.generation_type_refs:
            return Result.failure(
                (_missing_integer_suffix_source_diagnostic(candidate, lowered),)
            )
        modifier = translate_cpp_intrinsic_suffix_modifier(
            BackendIntrinsicModifierRequest(
                kind="suffix",
                backend_id=CPP_TRANSLATION_BACKEND_ID,
                extension=candidate.target_extension,
                intrinsic=intrinsic_expression.intrinsic,
                type_ref=type_ref.unwrap(),
                source_location=candidate.variant.source.declaration.source_span.location,
            ),
            translation_snippets=translation_snippets,
        )
        if not modifier.is_ok:
            return Result.failure(modifier.diagnostics)
        return Result.ok(
            _CandidateTranslation(
                modifier=modifier.unwrap(),
                type_spellings=type_spellings.unwrap(),
            )
        )

    type_entry = language_map_entries.get(candidate.type_tag)
    backend_type = type_entry.target_type if type_entry is not None else None
    if candidate.type_tag != _SELECTED_TYPE_TAG or backend_type is None:
        return Result.failure((_unsupported_type_diagnostic(candidate),))

    prefix = _selected_intrinsic_prefix(extension)
    function_name = (
        f"{prefix}{intrinsic_expression.intrinsic}_{_SELECTED_INTRINSIC_SUFFIX}"
    )
    return Result.ok(
        _CandidateTranslation(
            call=TranslatedIntrinsicCall(
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
    )


def _translate_generation_type_spellings(
    candidate: ImplementationCandidate,
    lowered: LoweredImplementation,
    *,
    language_map_entries: FrozenMap[str, LanguageTypeEntry],
) -> Result[tuple[BackendTypeSpelling, ...]]:
    diagnostics: list[Diagnostic] = []
    spellings: list[BackendTypeSpelling] = []
    for type_ref in lowered.generation_type_refs:
        spelling = translate_cpp_backend_type_spelling(
            BackendTypeSpellingRequest(
                backend_id=CPP_TRANSLATION_BACKEND_ID,
                type_ref=type_ref,
                source_location=(
                    candidate.variant.source.declaration.source_span.location
                ),
            ),
            language_map_entries=language_map_entries,
        )
        diagnostics.extend(spelling.diagnostics)
        if spelling.is_ok:
            spellings.append(spelling.unwrap())

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    return Result.ok(tuple(spellings), diagnostics=ordered)


def _suffix_generation_type_ref(
    candidate: ImplementationCandidate,
    lowered: LoweredImplementation,
) -> Result[GenerationTypeRef | None]:
    suffix_refs = tuple(
        type_ref
        for type_ref in lowered.generation_type_refs
        if type_ref.kind == _SELECTED_SUFFIX_SOURCE_REF_KIND
    )
    if len(suffix_refs) > 1:
        return Result.failure(
            (
                _malformed_modifier_request_diagnostic(
                    BackendIntrinsicModifierRequest(
                        kind="suffix",
                        backend_id=CPP_TRANSLATION_BACKEND_ID,
                        extension=candidate.target_extension,
                        intrinsic=_SELECTED_INTRINSIC,
                        source_location=(
                            candidate.variant.source.declaration.source_span.location
                        ),
                    ),
                    ("generation_type_refs",),
                ),
            )
        )
    if not suffix_refs:
        return Result.ok(None)
    return Result.ok(suffix_refs[0])


def _missing_integer_suffix_source_diagnostic(
    candidate: ImplementationCandidate,
    lowered: LoweredImplementation,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-TRANSLATE-INTRINSIC-SUFFIX-MISSING",
        "C++ native integer translation requires the Milestone 45 suffix "
        "modifier source "
        "GenerationTypeRef(kind='base.signed_of', type_tag='si32', "
        "source_type_tag='si32' | 'ui32') before the integrated native "
        "integer plan can succeed; got generation type ref(s): "
        f"{', '.join(_type_ref_text(type_ref) for type_ref in lowered.generation_type_refs)}",
        location=candidate.variant.source.declaration.source_span.location,
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
    if lowered is not None and (
        lowered.generation_branches or lowered.generation_type_refs
    ):
        return None
    return Diagnostic.error(
        "TSL-CPP-TRANSLATE-GENERATION-UNRESOLVED",
        "C++ native translation requires generation-time helpers to be resolved "
        "to typed semantic values before backend translation",
        location=candidate.variant.source.declaration.source_span.location,
    )


def _contains_raw_generation_helper(text: str | None) -> bool:
    return text is not None and any(
        marker in text
        for marker in _RAW_GENERATION_HELPER_MARKERS
    )


def _is_selected_type_spelling_ref(type_ref: GenerationTypeRef) -> bool:
    if type_ref.kind == "base.in":
        return type_ref.type_tag in _SELECTED_TYPE_SPELLING_TAGS
    if type_ref.kind == "base.signed_of":
        return (
            type_ref.type_tag == _SELECTED_INTEGER_SUFFIX_TYPE_TAG
            and type_ref.source_type_tag in _SELECTED_TYPE_SPELLING_TAGS
        )
    if type_ref.kind == "base.unsigned_of":
        return (
            type_ref.type_tag == "ui32"
            and type_ref.source_type_tag in _SELECTED_TYPE_SPELLING_TAGS
        )
    return False


def _unresolved_modifier_generation_diagnostic(
    request: BackendIntrinsicModifierRequest,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-TRANSLATE-GENERATION-UNRESOLVED",
        "C++ intrinsic suffix modifier translation requires generation-time "
        "helpers to be resolved to typed GenerationTypeRef values before "
        f"backend translation; got raw helper text {request.raw_helper_text!r}",
        location=request.source_location,
    )


def _unresolved_type_spelling_generation_diagnostic(
    request: BackendTypeSpellingRequest,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-TRANSLATE-GENERATION-UNRESOLVED",
        "C++ backend type-spelling translation requires generation-time "
        "helpers to be resolved to typed GenerationTypeRef values before "
        f"backend translation; got raw helper text {request.raw_helper_text!r}",
        location=request.source_location,
    )


def _malformed_type_spelling_request_diagnostic(
    request: BackendTypeSpellingRequest,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-TRANSLATE-TYPE-SPELLING-MALFORMED",
        "C++ backend type-spelling translation received a malformed request; "
        f"backend {request.backend_id!r}, type ref {_type_ref_text(request.type_ref)}",
        location=request.source_location,
    )


def _unsupported_type_spelling_backend_diagnostic(
    request: BackendTypeSpellingRequest,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-TRANSLATE-UNSUPPORTED-BACKEND",
        "C++ backend type-spelling translation supports only backend "
        f"{CPP_TRANSLATION_BACKEND_ID!r}; got backend {request.backend_id!r}",
        location=request.source_location,
    )


def _missing_type_spelling_language_map(
    request: BackendTypeSpellingRequest,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-TRANSLATE-MISSING-LANGUAGE-MAP",
        "C++ backend type-spelling translation requires language type map "
        f"{request.backend_id!r}",
        location=request.source_location,
    )


def _missing_type_spelling_type_ref_diagnostic(
    request: BackendTypeSpellingRequest,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-TRANSLATE-TYPE-SPELLING-TYPE-MISSING",
        "C++ backend type-spelling translation requires a typed "
        f"GenerationTypeRef input; got none for backend {request.backend_id!r}",
        location=request.source_location,
    )


def _unsupported_type_spelling_source_ref_diagnostic(
    request: BackendTypeSpellingRequest,
) -> Diagnostic:
    type_ref = request.type_ref
    source_ref_kind = type_ref.kind if type_ref is not None else None
    source_type_tag = type_ref.source_type_tag if type_ref is not None else None
    return Diagnostic.error(
        "TSL-CPP-TRANSLATE-TYPE-SPELLING-SOURCE-REF-UNSUPPORTED",
        "C++ backend type-spelling translation supports only selected M43 "
        "base.in, base.signed_of, and base.unsigned_of GenerationTypeRef "
        f"kinds; got source ref kind {source_ref_kind!r}, source type tag "
        f"{source_type_tag!r}, backend {request.backend_id!r}",
        location=request.source_location,
    )


def _unsupported_type_spelling_type_tag_diagnostic(
    request: BackendTypeSpellingRequest,
) -> Diagnostic:
    type_ref = request.type_ref
    type_tag = type_ref.type_tag if type_ref is not None else None
    source_ref_kind = type_ref.kind if type_ref is not None else None
    source_type_tag = type_ref.source_type_tag if type_ref is not None else None
    return Diagnostic.error(
        "TSL-CPP-TRANSLATE-TYPE-SPELLING-TYPE-UNSUPPORTED",
        "C++ backend type-spelling translation supports only selected scalar "
        "integer tags 'si32' and 'ui32' for M43 base.in, base.signed_of, and "
        "base.unsigned_of inputs; got type tag "
        f"{type_tag!r}, source ref kind {source_ref_kind!r}, source type tag "
        f"{source_type_tag!r}, backend {request.backend_id!r}",
        location=request.source_location,
    )


def _missing_type_spelling_metadata_diagnostic(
    request: BackendTypeSpellingRequest,
    language_key: str,
) -> Diagnostic:
    type_ref = request.type_ref
    type_tag = type_ref.type_tag if type_ref is not None else None
    source_ref_kind = type_ref.kind if type_ref is not None else None
    source_type_tag = type_ref.source_type_tag if type_ref is not None else None
    return Diagnostic.error(
        "TSL-CPP-TRANSLATE-TYPE-SPELLING-METADATA-MISSING",
        "C++ backend type-spelling translation requires selected language-map "
        f"entry {language_key!r} for backend {request.backend_id!r}; got type "
        f"tag {type_tag!r}, source ref kind {source_ref_kind!r}, source type "
        f"tag {source_type_tag!r}",
        location=request.source_location,
    )


def _type_ref_text(type_ref: GenerationTypeRef | None) -> str:
    if type_ref is None:
        return "None"
    return (
        "GenerationTypeRef("
        f"kind={type_ref.kind!r}, "
        f"type_tag={type_ref.type_tag!r}, "
        f"source_type_tag={type_ref.source_type_tag!r})"
    )


def _malformed_modifier_request_diagnostic(
    request: BackendIntrinsicModifierRequest,
    field_names: tuple[str, ...],
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-TRANSLATE-MODIFIER-MALFORMED",
        "C++ intrinsic modifier translation received a malformed request; "
        f"missing or invalid field(s): {', '.join(field_names)}; backend "
        f"{request.backend_id!r}, extension {request.extension!r}, modifier "
        f"family {request.kind!r}, intrinsic base {request.intrinsic!r}",
        location=request.source_location,
    )


def _unsupported_modifier_family_diagnostic(
    request: BackendIntrinsicModifierRequest,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-TRANSLATE-MODIFIER-UNSUPPORTED",
        "C++ backend modifier translation supports only intrinsic suffix in "
        f"Milestone 45; got modifier family {request.kind!r} for backend "
        f"{request.backend_id!r}, extension {request.extension!r}, intrinsic "
        f"base {request.intrinsic!r}",
        location=request.source_location,
    )


def _unsupported_modifier_backend_diagnostic(
    request: BackendIntrinsicModifierRequest,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-TRANSLATE-UNSUPPORTED-BACKEND",
        "C++ intrinsic suffix modifier translation supports only backend "
        f"{CPP_TRANSLATION_BACKEND_ID!r}; got backend {request.backend_id!r}",
        location=request.source_location,
    )


def _unsupported_modifier_extension_diagnostic(
    request: BackendIntrinsicModifierRequest,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-TRANSLATE-UNSUPPORTED-EXTENSION",
        "C++ intrinsic suffix modifier translation supports only extension "
        f"{_SELECTED_EXTENSION!r}; got extension {request.extension!r} for "
        f"backend {request.backend_id!r} and intrinsic base {request.intrinsic!r}",
        location=request.source_location,
    )


def _missing_modifier_translation_metadata(
    request: BackendIntrinsicModifierRequest,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-TRANSLATE-MISSING-TRANSLATION-MAP",
        "C++ intrinsic suffix modifier translation requires translation map "
        f"{request.backend_id!r} with emit_return metadata before backend "
        f"modifier translation; extension {request.extension!r}, intrinsic "
        f"base {request.intrinsic!r}",
        location=request.source_location,
    )


def _missing_modifier_metadata_diagnostic(
    request: BackendIntrinsicModifierRequest,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-TRANSLATE-MODIFIER-METADATA-MISSING",
        "C++ intrinsic suffix modifier translation requires selected modifier "
        f"metadata {_SELECTED_MODIFIER_METADATA_SNIPPET!r} in translation map "
        f"{request.backend_id!r}; extension {request.extension!r}, intrinsic "
        f"base {request.intrinsic!r}",
        location=request.source_location,
    )


def _unsupported_modifier_intrinsic_diagnostic(
    request: BackendIntrinsicModifierRequest,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-TRANSLATE-MODIFIER-INTRINSIC-UNSUPPORTED",
        "C++ intrinsic suffix modifier translation supports only intrinsic "
        f"base {_SELECTED_INTRINSIC!r}; got {request.intrinsic!r} for backend "
        f"{request.backend_id!r} and extension {request.extension!r}",
        location=request.source_location,
    )


def _missing_modifier_type_ref_diagnostic(
    request: BackendIntrinsicModifierRequest,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-TRANSLATE-MODIFIER-TYPE-MISSING",
        "C++ intrinsic suffix modifier translation requires a typed "
        "GenerationTypeRef input; got none for backend "
        f"{request.backend_id!r}, extension {request.extension!r}, intrinsic "
        f"base {request.intrinsic!r}",
        location=request.source_location,
    )


def _unsupported_modifier_source_ref_diagnostic(
    request: BackendIntrinsicModifierRequest,
) -> Diagnostic:
    type_ref = request.type_ref
    source_ref_kind = type_ref.kind if type_ref is not None else None
    return Diagnostic.error(
        "TSL-CPP-TRANSLATE-MODIFIER-SOURCE-REF-UNSUPPORTED",
        "C++ intrinsic suffix modifier translation supports only "
        f"GenerationTypeRef kind {_SELECTED_SUFFIX_SOURCE_REF_KIND!r}; got "
        f"{source_ref_kind!r} for backend {request.backend_id!r}, extension "
        f"{request.extension!r}, intrinsic base {request.intrinsic!r}",
        location=request.source_location,
    )


def _unsupported_modifier_type_tag_diagnostic(
    request: BackendIntrinsicModifierRequest,
) -> Diagnostic:
    type_ref = request.type_ref
    type_tag = type_ref.type_tag if type_ref is not None else None
    selected_type_tag = type_ref.source_type_tag if type_ref is not None else None
    return Diagnostic.error(
        "TSL-CPP-TRANSLATE-MODIFIER-TYPE-UNSUPPORTED",
        "C++ intrinsic suffix modifier translation supports only resolved "
        f"type tag {_SELECTED_INTEGER_SUFFIX_TYPE_TAG!r} from selected source "
        f"tags {_SELECTED_INTEGER_SUFFIX_TYPE_TAGS!r}; got type tag "
        f"{type_tag!r} from source type tag {selected_type_tag!r} for backend "
        f"{request.backend_id!r}, extension {request.extension!r}, intrinsic "
        f"base {request.intrinsic!r}",
        location=request.source_location,
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


def _unsupported_intrinsic_diagnostic(
    candidate: ImplementationCandidate,
    intrinsic: str,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-TRANSLATE-UNSUPPORTED-INTRINSIC",
        "C++ native translation supports only lowered intrin_compose<add> for "
        "the selected avx2/f32 slice; got "
        f"{intrinsic!r}",
        location=candidate.variant.source.declaration.source_span.location,
    )
