from __future__ import annotations

from dataclasses import dataclass

from tslgen.analysis.candidates import ImplementationCandidate
from tslgen.core.diagnostics import Diagnostic, has_errors, sort_diagnostics
from tslgen.core.result import Result
from tslgen.lowering import (
    BackendIntrinsicModifier,
    BackendTypeSpelling,
    LoweredImplementation,
    LoweringPlan,
    TsilBinaryExpression,
    TsilIntrinsicComposeExpression,
    TsilParameterReference,
    TsilReturnStatement,
)
from tslgen.lowering.translations import TranslatedIntrinsicCall

from .naming import (
    cpp_detail_functor_name,
    cpp_wrapper_function_name,
    cpp_wrapper_parameter_names,
)
from .translation import CppNativeTranslationPlan


_CPP_SCALAR_TYPE_BY_TAG = {
    "si32": "int32_t",
    "ui32": "uint32_t",
}
_CPP_SCALAR_TYPE_ORDER = {
    type_tag: index
    for index, type_tag in enumerate(_CPP_SCALAR_TYPE_BY_TAG)
}
_CPP_NATIVE_INTEGER_TYPE_BY_TAG = {
    "si32": "int32_t",
    "ui32": "uint32_t",
}
_CPP_NATIVE_INTEGER_INTRINSIC_SUFFIX = "epi32"
_CPP_NATIVE_INTEGER_SUFFIX_SOURCE_KIND = "base.signed_of"
_CPP_NATIVE_INTEGER_TYPE_SOURCE_KIND = "base.in"
_CPP_NATIVE_INTEGER_SOURCE_TYPE_TAG = "si32"
_CPP_NATIVE_INTRINSIC_BACKEND = "cpp"
_CPP_NATIVE_INTRINSIC_EXTENSION = "avx2"
_CPP_NATIVE_INTRINSIC_BASE = "add"


@dataclass(frozen=True, slots=True)
class CppScalarBinarySpecialization:
    candidate_id: str
    type_tag: str
    cpp_type: str
    detail_name: str
    parameter_names: tuple[str, str]
    return_expression: str

    @property
    def key(self) -> tuple[object, ...]:
        return (
            _CPP_SCALAR_TYPE_ORDER[self.type_tag],
            self.cpp_type,
            self.detail_name,
            self.parameter_names,
            self.return_expression,
            self.candidate_id,
        )


@dataclass(frozen=True, slots=True)
class CppNativeBinarySpecialization:
    candidate_id: str
    type_tag: str
    cpp_type: str
    extension_name: str
    detail_name: str
    parameter_names: tuple[str, str]
    return_expression: str

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.extension_name,
            self.type_tag,
            self.cpp_type,
            self.detail_name,
            self.parameter_names,
            self.return_expression,
            self.candidate_id,
        )


@dataclass(frozen=True, slots=True)
class _NativeIntegerRenderValues:
    suffix_modifier: BackendIntrinsicModifier
    type_spelling: BackendTypeSpelling


@dataclass(frozen=True, slots=True)
class CppScalarBinarySlice:
    detail_name: str
    wrapper_name: str
    parameter_names: tuple[str, str]
    specializations: tuple[CppScalarBinarySpecialization, ...]
    native_specializations: tuple[CppNativeBinarySpecialization, ...] = ()

    def __post_init__(self) -> None:
        specializations = tuple(
            sorted(self.specializations, key=lambda specialization: specialization.key)
        )
        object.__setattr__(self, "specializations", specializations)
        native_specializations = tuple(
            sorted(
                self.native_specializations,
                key=lambda specialization: specialization.key,
            )
        )
        object.__setattr__(
            self,
            "native_specializations",
            native_specializations,
        )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.detail_name,
            self.wrapper_name,
            self.parameter_names,
            tuple(specialization.key for specialization in self.specializations),
            tuple(specialization.key for specialization in self.native_specializations),
        )


def plan_cpp_scalar_binary_slice(
    candidates: tuple[ImplementationCandidate, ...],
    lowering_plan: LoweringPlan,
    native_translation_plan: CppNativeTranslationPlan | None = None,
) -> Result[CppScalarBinarySlice | None]:
    if not candidates:
        return Result.ok(None)

    diagnostics: list[Diagnostic] = []
    specializations: list[CppScalarBinarySpecialization] = []
    native_specializations: list[CppNativeBinarySpecialization] = []
    detail_name = ""
    wrapper_name = ""
    wrapper_parameter_names: tuple[str, str] | None = None
    for candidate in candidates:
        candidate_kind = _candidate_kind(candidate)
        support_diagnostic = _unsupported_candidate_diagnostic(candidate, candidate_kind)
        if support_diagnostic is not None:
            diagnostics.append(support_diagnostic)
            continue

        location = candidate.variant.source.declaration.source_span.location
        planned_detail_name = cpp_detail_functor_name(
            candidate.emitted_primitive_name,
            candidate.template_name,
            location=location,
        )
        planned_wrapper_name = cpp_wrapper_function_name(
            candidate.emitted_primitive_name,
            location=location,
        )
        parameter_names = cpp_wrapper_parameter_names(
            (
                parameter.name
                for parameter in candidate.variant.source.declaration.parameters
            ),
            location=location,
        )
        diagnostics.extend(planned_detail_name.diagnostics)
        diagnostics.extend(planned_wrapper_name.diagnostics)
        diagnostics.extend(parameter_names.diagnostics)
        if not planned_detail_name.is_ok or not planned_wrapper_name.is_ok:
            continue
        if not parameter_names.is_ok:
            continue
        candidate_parameter_names = parameter_names.unwrap()
        if len(candidate_parameter_names) != 2:
            diagnostics.append(_unsupported_parameter_shape_diagnostic(candidate))
            continue
        typed_parameter_names = (
            candidate_parameter_names[0],
            candidate_parameter_names[1],
        )
        if detail_name and detail_name != planned_detail_name.unwrap():
            diagnostics.append(_mixed_scalar_slice_diagnostic(candidate, "detail functor"))
            continue
        if wrapper_name and wrapper_name != planned_wrapper_name.unwrap():
            diagnostics.append(_mixed_scalar_slice_diagnostic(candidate, "wrapper"))
            continue
        if (
            wrapper_parameter_names is not None
            and wrapper_parameter_names != typed_parameter_names
        ):
            diagnostics.append(_mixed_scalar_slice_diagnostic(candidate, "parameters"))
            continue

        detail_name = planned_detail_name.unwrap()
        wrapper_name = planned_wrapper_name.unwrap()
        wrapper_parameter_names = typed_parameter_names
        lowered = lowering_plan.implementations_by_candidate_id.get(
            candidate.candidate_id
        )
        if lowered is None:
            diagnostics.append(_missing_lowered_body_diagnostic(candidate))
            continue

        if candidate_kind == "scalar":
            return_expression = _scalar_return_expression_for_lowered(
                candidate,
                lowered,
                typed_parameter_names,
            )
            diagnostics.extend(return_expression.diagnostics)
            if not return_expression.is_ok:
                continue
            specializations.append(
                CppScalarBinarySpecialization(
                    candidate_id=candidate.candidate_id,
                    type_tag=candidate.type_tag,
                    cpp_type=_CPP_SCALAR_TYPE_BY_TAG[candidate.type_tag],
                    detail_name=detail_name,
                    parameter_names=typed_parameter_names,
                    return_expression=return_expression.unwrap(),
                )
            )
        elif candidate_kind == "native":
            if candidate.type_tag in _CPP_NATIVE_INTEGER_TYPE_BY_TAG:
                native_values = _native_integer_render_values(
                    candidate,
                    native_translation_plan,
                )
                diagnostics.extend(native_values.diagnostics)
                if not native_values.is_ok:
                    continue
                expression = _native_integer_intrinsic_expression_for_lowered(
                    candidate,
                    lowered,
                    typed_parameter_names,
                    native_values.unwrap().suffix_modifier,
                )
                diagnostics.extend(expression.diagnostics)
                if not expression.is_ok:
                    continue
                native_specializations.append(
                    CppNativeBinarySpecialization(
                        candidate_id=candidate.candidate_id,
                        type_tag=candidate.type_tag,
                        cpp_type=native_values.unwrap().type_spelling.spelling,
                        extension_name=candidate.target_extension,
                        detail_name=detail_name,
                        parameter_names=typed_parameter_names,
                        return_expression=expression.unwrap(),
                    )
                )
                continue
            translated_call = _native_translated_call(candidate, native_translation_plan)
            diagnostics.extend(translated_call.diagnostics)
            if not translated_call.is_ok:
                continue
            call = translated_call.unwrap()
            call_validation = _native_translated_call_for_lowered(
                candidate,
                lowered,
                typed_parameter_names,
                call,
            )
            diagnostics.extend(call_validation.diagnostics)
            if not call_validation.is_ok:
                continue
            native_specializations.append(
                CppNativeBinarySpecialization(
                    candidate_id=candidate.candidate_id,
                    type_tag=candidate.type_tag,
                    cpp_type=call.backend_type,
                    extension_name=candidate.target_extension,
                    detail_name=detail_name,
                    parameter_names=typed_parameter_names,
                    return_expression=_translated_call_expression(call),
                )
            )

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    if (
        not specializations
        and not native_specializations
    ) or wrapper_parameter_names is None:
        return Result.ok(None, diagnostics=ordered)
    return Result.ok(
        CppScalarBinarySlice(
            detail_name=detail_name,
            wrapper_name=wrapper_name,
            parameter_names=wrapper_parameter_names,
            specializations=tuple(specializations),
            native_specializations=tuple(native_specializations),
        ),
        diagnostics=ordered,
    )


def cpp_native_header_no_lowering_diagnostic(
    candidate: ImplementationCandidate,
) -> Diagnostic | None:
    candidate_kind = _candidate_kind(candidate)
    if candidate_kind == "native":
        if not _is_selected_native_shape(candidate):
            return _unsupported_candidate_diagnostic(candidate, None)
        return _missing_lowered_body_diagnostic(candidate)
    if _is_native_like_candidate(candidate):
        return _unsupported_candidate_diagnostic(candidate, candidate_kind)
    return None


def render_cpp_scalar_binary_detail_lines(
    scalar_slice: CppScalarBinarySlice | None,
) -> tuple[str, ...]:
    if scalar_slice is None:
        return ()
    lines = [
        "template <VectorProcessingStyle Vec>",
        f"struct {scalar_slice.detail_name} {{",
        "  using return_type = typename Vec::register_type;",
        "  template <typename... Args>",
        "  static return_type apply(Args&&...);",
        "};",
    ]
    for specialization in scalar_slice.specializations:
        lines.append("")
        lines.extend(_specialization_lines(specialization))
    for native_specialization in scalar_slice.native_specializations:
        lines.append("")
        lines.extend(_native_specialization_lines(native_specialization))
    return tuple(lines)


def render_cpp_scalar_binary_wrapper_lines(
    scalar_slice: CppScalarBinarySlice | None,
) -> tuple[str, ...]:
    if scalar_slice is None:
        return ()
    left, right = scalar_slice.parameter_names
    return (
        "template <typename Vec>",
        f"TSL_FORCE_INLINE auto {scalar_slice.wrapper_name}(",
        f"    typename detail::reg_param<Vec>::type {left},",
        f"    typename detail::reg_param<Vec>::type {right}",
        f") -> decltype(::tsl::detail::{scalar_slice.detail_name}<Vec>::apply({left}, {right})) {{",
        f"  return ::tsl::detail::{scalar_slice.detail_name}<Vec>::apply({left}, {right});",
        "}",
    )


def _specialization_lines(
    specialization: CppScalarBinarySpecialization,
) -> tuple[str, ...]:
    left, right = specialization.parameter_names
    return (
        "template <>",
        f"struct {specialization.detail_name}<"
        f"simd<{specialization.cpp_type}, scalar>> {{",
        f"  using Vec = simd<{specialization.cpp_type}, scalar>;",
        "  using return_type = typename Vec::register_type;",
        "",
        "  static constexpr bool has_return_value() {",
        "    return true;",
        "  }",
        "",
        "  static constexpr bool native_supported() {",
        "    return true;",
        "  }",
        "",
        "  [[nodiscard]]",
        "  TSL_FORCE_INLINE",
        "  static typename Vec::register_type apply(",
        f"      typename reg_param<Vec>::type {left},",
        f"      typename reg_param<Vec>::type {right}",
        "  ) {",
        f"    return {specialization.return_expression};",
        "  }",
        "};",
    )


def _native_specialization_lines(
    specialization: CppNativeBinarySpecialization,
) -> tuple[str, ...]:
    left, right = specialization.parameter_names
    return (
        "template <>",
        f"struct {specialization.detail_name}<"
        f"simd<{specialization.cpp_type}, {specialization.extension_name}>> {{",
        f"  using Vec = simd<{specialization.cpp_type}, "
        f"{specialization.extension_name}>;",
        "  using return_type = typename Vec::register_type;",
        "",
        "  static constexpr bool has_return_value() {",
        "    return true;",
        "  }",
        "",
        "  static constexpr bool native_supported() {",
        "    return true;",
        "  }",
        "",
        "  [[nodiscard]]",
        "  TSL_FORCE_INLINE",
        "  static typename Vec::register_type apply(",
        f"      typename reg_param<Vec>::type {left},",
        f"      typename reg_param<Vec>::type {right}",
        "  ) {",
        f"    return {specialization.return_expression};",
        "  }",
        "};",
    )


def _candidate_kind(candidate: ImplementationCandidate) -> str | None:
    common_supported = (
        candidate.emitted_primitive_name == "add"
        and candidate.template_name == "binary"
        and candidate.variant.source.signature.normalized == "v:=(v,v)"
    )
    if not common_supported:
        return None
    if (
        candidate.target_extension == "scalar"
        and candidate.source_extension == "scalar"
        and candidate.type_tag in _CPP_SCALAR_TYPE_BY_TAG
    ):
        return "scalar"
    if (
        candidate.target_extension != "scalar"
        and candidate.source_extension != "scalar"
        and candidate.target_extension == _CPP_NATIVE_INTRINSIC_EXTENSION
        and candidate.source_extension == _CPP_NATIVE_INTRINSIC_EXTENSION
        and candidate.type_tag in ("f32", *_CPP_NATIVE_INTEGER_TYPE_BY_TAG)
    ):
        return "native"
    return None


def _unsupported_candidate_diagnostic(
    candidate: ImplementationCandidate,
    candidate_kind: str | None,
) -> Diagnostic | None:
    if candidate_kind is not None:
        return None
    if _is_native_like_candidate(candidate):
        return Diagnostic.error(
            "TSL-CPP-RENDER-NATIVE-UNSUPPORTED",
            "C++ native parity rendering supports only the selected "
            "fundamental/add binary avx2/f32 and avx2/si32/ui32 slices; "
            "candidate "
            f"{candidate.candidate_id!r} has primitive "
            f"{candidate.emitted_primitive_name!r}, template "
            f"{candidate.template_name!r}, signature "
            f"{candidate.variant.source.signature.normalized!r}, target extension "
            f"{candidate.target_extension!r}, source extension "
            f"{candidate.source_extension!r}, and type tag {candidate.type_tag!r}",
            location=candidate.variant.source.declaration.source_span.location,
        )
    return Diagnostic.error(
        "TSL-CPP-RENDER-SCALAR-UNSUPPORTED",
        "C++ scalar parity rendering supports only the selected "
        "fundamental/add binary scalar si32/ui32 slice; candidate "
        f"{candidate.candidate_id!r} has primitive "
        f"{candidate.emitted_primitive_name!r}, template "
        f"{candidate.template_name!r}, signature "
        f"{candidate.variant.source.signature.normalized!r}, target extension "
        f"{candidate.target_extension!r}, source extension "
        f"{candidate.source_extension!r}, and type tag {candidate.type_tag!r}",
        location=candidate.variant.source.declaration.source_span.location,
    )


def _is_native_like_candidate(candidate: ImplementationCandidate) -> bool:
    return (
        candidate.target_extension != "scalar"
        and candidate.source_extension != "scalar"
    )


def _is_selected_native_shape(candidate: ImplementationCandidate) -> bool:
    return (
        candidate.emitted_primitive_name == "add"
        and candidate.template_name == "binary"
        and candidate.variant.source.signature.normalized == "v:=(v,v)"
        and candidate.target_extension == _CPP_NATIVE_INTRINSIC_EXTENSION
        and candidate.source_extension == _CPP_NATIVE_INTRINSIC_EXTENSION
        and candidate.type_tag in ("f32", *_CPP_NATIVE_INTEGER_TYPE_BY_TAG)
    )


def _scalar_return_expression_for_lowered(
    candidate: ImplementationCandidate,
    lowered: LoweredImplementation,
    parameter_names: tuple[str, str],
) -> Result[str]:
    if lowered.status != "lowered" or len(lowered.statements) != 1:
        return Result.failure((_unsupported_lowered_body_diagnostic(candidate, lowered),))

    statement = lowered.statements[0]
    if not isinstance(statement, TsilReturnStatement):
        return Result.failure((_unsupported_lowered_body_diagnostic(candidate, lowered),))

    expression = _cpp_expression(statement.expression)
    if expression is None:
        return Result.failure((_unsupported_lowered_body_diagnostic(candidate, lowered),))

    referenced_names = _referenced_parameter_names(statement.expression)
    unknown_names = tuple(sorted(referenced_names - frozenset(parameter_names)))
    if unknown_names:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-CPP-RENDER-SCALAR-PARAMETER",
                    "C++ scalar parity rendering received lowered parameter "
                    f"reference(s) not present in primitive {candidate.emitted_primitive_name!r}: "
                    f"{', '.join(repr(name) for name in unknown_names)}",
                    location=candidate.variant.source.declaration.source_span.location,
                ),
            )
        )
    return Result.ok(expression)


def _native_translated_call(
    candidate: ImplementationCandidate,
    native_translation_plan: CppNativeTranslationPlan | None,
) -> Result[TranslatedIntrinsicCall]:
    translated_call = (
        None
        if native_translation_plan is None
        else native_translation_plan.calls_by_candidate_id.get(candidate.candidate_id)
    )
    if translated_call is None:
        return Result.failure((_missing_translated_call_diagnostic(candidate),))
    return Result.ok(translated_call)


def _native_integer_render_values(
    candidate: ImplementationCandidate,
    native_translation_plan: CppNativeTranslationPlan | None,
) -> Result[_NativeIntegerRenderValues]:
    if native_translation_plan is None:
        return Result.failure((_missing_native_integer_plan_diagnostic(candidate),))

    suffix = _native_integer_suffix_modifier(candidate, native_translation_plan)
    type_spelling = _native_integer_type_spelling(candidate, native_translation_plan)
    diagnostics = (*suffix.diagnostics, *type_spelling.diagnostics)
    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    return Result.ok(
        _NativeIntegerRenderValues(
            suffix_modifier=suffix.unwrap(),
            type_spelling=type_spelling.unwrap(),
        ),
        diagnostics=ordered,
    )


def _native_integer_suffix_modifier(
    candidate: ImplementationCandidate,
    native_translation_plan: CppNativeTranslationPlan,
) -> Result[BackendIntrinsicModifier]:
    suffix_modifiers = tuple(
        modifier
        for modifier in native_translation_plan.modifiers
        if modifier.kind == "suffix"
    )
    if not suffix_modifiers:
        return Result.failure((_missing_native_integer_suffix_diagnostic(candidate),))

    matching_context = tuple(
        modifier
        for modifier in suffix_modifiers
        if (
            modifier.backend_id == _CPP_NATIVE_INTRINSIC_BACKEND
            and modifier.extension == candidate.target_extension
            and modifier.intrinsic == _CPP_NATIVE_INTRINSIC_BASE
        )
    )
    if not matching_context:
        return Result.failure(
            (_unsupported_native_integer_suffix_diagnostic(candidate, suffix_modifiers),)
        )

    unique_modifiers = _unique_modifiers(matching_context)
    if len(unique_modifiers) > 1:
        return Result.failure(
            (_ambiguous_native_integer_suffix_diagnostic(candidate, unique_modifiers),)
        )
    modifier = unique_modifiers[0]
    if (
        modifier.value != _CPP_NATIVE_INTEGER_INTRINSIC_SUFFIX
        or modifier.source_ref_kind != _CPP_NATIVE_INTEGER_SUFFIX_SOURCE_KIND
        or modifier.source_type_tag != _CPP_NATIVE_INTEGER_SOURCE_TYPE_TAG
    ):
        return Result.failure(
            (_unsupported_native_integer_suffix_diagnostic(candidate, (modifier,)),)
        )
    return Result.ok(modifier)


def _native_integer_type_spelling(
    candidate: ImplementationCandidate,
    native_translation_plan: CppNativeTranslationPlan,
) -> Result[BackendTypeSpelling]:
    expected_spelling = _CPP_NATIVE_INTEGER_TYPE_BY_TAG[candidate.type_tag]
    candidate_spellings = tuple(
        spelling
        for spelling in native_translation_plan.type_spellings
        if spelling.type_tag == candidate.type_tag
    )
    if not candidate_spellings:
        return Result.failure(
            (_missing_native_integer_type_spelling_diagnostic(candidate),)
        )

    base_spellings = tuple(
        spelling
        for spelling in candidate_spellings
        if (
            spelling.backend_id == _CPP_NATIVE_INTRINSIC_BACKEND
            and spelling.source_ref_kind == _CPP_NATIVE_INTEGER_TYPE_SOURCE_KIND
        )
    )
    if not base_spellings:
        return Result.failure(
            (
                _unsupported_native_integer_type_spelling_diagnostic(
                    candidate,
                    candidate_spellings,
                ),
            )
        )

    unique_spellings = _unique_type_spellings(base_spellings)
    if len(unique_spellings) > 1:
        return Result.failure(
            (_ambiguous_native_integer_type_spelling_diagnostic(candidate, unique_spellings),)
        )
    spelling = unique_spellings[0]
    if spelling.spelling != expected_spelling:
        return Result.failure(
            (_unsupported_native_integer_type_spelling_diagnostic(candidate, (spelling,)),)
        )
    return Result.ok(spelling)


def _native_integer_intrinsic_expression_for_lowered(
    candidate: ImplementationCandidate,
    lowered: LoweredImplementation,
    parameter_names: tuple[str, str],
    suffix_modifier: BackendIntrinsicModifier,
) -> Result[str]:
    expression = _native_intrinsic_compose_for_lowered(candidate, lowered)
    if not expression.is_ok:
        return Result.failure(expression.diagnostics)
    intrinsic_expression = expression.unwrap()
    if intrinsic_expression.intrinsic != suffix_modifier.intrinsic:
        return Result.failure((_unsupported_lowered_body_diagnostic(candidate, lowered),))
    if suffix_modifier.value != _CPP_NATIVE_INTEGER_INTRINSIC_SUFFIX:
        return Result.failure(
            (_unsupported_native_integer_suffix_diagnostic(candidate, (suffix_modifier,)),)
        )
    argument_names = tuple(argument.name for argument in intrinsic_expression.arguments)
    unknown_names = tuple(sorted(set(argument_names) - set(parameter_names)))
    if unknown_names:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-CPP-RENDER-NATIVE-PARAMETER",
                    "C++ native integer parity rendering received lowered "
                    "parameter reference(s) not present in primitive "
                    f"{candidate.emitted_primitive_name!r}: "
                    f"{', '.join(repr(name) for name in unknown_names)}",
                    location=candidate.variant.source.declaration.source_span.location,
                ),
            )
        )
    arguments = ", ".join(argument_names)
    return Result.ok(
        f"_mm256_{suffix_modifier.intrinsic}_{suffix_modifier.value}({arguments})"
    )


def _native_translated_call_for_lowered(
    candidate: ImplementationCandidate,
    lowered: LoweredImplementation,
    parameter_names: tuple[str, str],
    translated_call: TranslatedIntrinsicCall,
) -> Result[None]:
    expression = _native_intrinsic_compose_for_lowered(candidate, lowered)
    if not expression.is_ok:
        return Result.failure(expression.diagnostics)
    intrinsic_expression = expression.unwrap()
    if intrinsic_expression.key != (
        "intrin_compose",
        translated_call.intrinsic,
        tuple(argument.key for argument in translated_call.arguments),
    ):
        return Result.failure((_unsupported_lowered_body_diagnostic(candidate, lowered),))
    if translated_call.backend_id != "cpp":
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-CPP-RENDER-TRANSLATED-CALL-BACKEND",
                    "C++ native rendering received translated call IR for "
                    f"backend {translated_call.backend_id!r}",
                    location=candidate.variant.source.declaration.source_span.location,
                ),
            )
        )
    if len(translated_call.arguments) != 2:
        return Result.failure((_unsupported_lowered_body_diagnostic(candidate, lowered),))

    argument_names = tuple(argument.name for argument in translated_call.arguments)
    unknown_names = tuple(sorted(set(argument_names) - set(parameter_names)))
    if unknown_names:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-CPP-RENDER-NATIVE-PARAMETER",
                    "C++ native parity rendering received lowered parameter "
                    f"reference(s) not present in primitive {candidate.emitted_primitive_name!r}: "
                    f"{', '.join(repr(name) for name in unknown_names)}",
                    location=candidate.variant.source.declaration.source_span.location,
                ),
            )
        )
    return Result.ok(None)


def _native_intrinsic_compose_for_lowered(
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


def _translated_call_expression(call: TranslatedIntrinsicCall) -> str:
    arguments = ", ".join(argument.name for argument in call.arguments)
    return f"{call.function_name}({arguments})"


def _unique_modifiers(
    modifiers: tuple[BackendIntrinsicModifier, ...],
) -> tuple[BackendIntrinsicModifier, ...]:
    return tuple({modifier.key: modifier for modifier in modifiers}.values())


def _unique_type_spellings(
    spellings: tuple[BackendTypeSpelling, ...],
) -> tuple[BackendTypeSpelling, ...]:
    return tuple({spelling.key: spelling for spelling in spellings}.values())


def _cpp_expression(expression: object) -> str | None:
    if isinstance(expression, TsilParameterReference):
        return expression.name
    if isinstance(expression, TsilBinaryExpression) and expression.operator == "+":
        left = _cpp_expression(expression.left)
        right = _cpp_expression(expression.right)
        if left is not None and right is not None:
            return f"{left} + {right}"
    return None


def _referenced_parameter_names(expression: object) -> frozenset[str]:
    if isinstance(expression, TsilParameterReference):
        return frozenset((expression.name,))
    if isinstance(expression, TsilBinaryExpression):
        return (
            _referenced_parameter_names(expression.left)
            | _referenced_parameter_names(expression.right)
        )
    return frozenset()


def _missing_lowered_body_diagnostic(
    candidate: ImplementationCandidate,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-RENDER-LOWERING-MISSING",
        "C++ binary parity rendering requires a lowered implementation for "
        f"candidate {candidate.candidate_id!r}",
        location=candidate.variant.source.declaration.source_span.location,
    )


def _missing_translated_call_diagnostic(
    candidate: ImplementationCandidate,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-RENDER-TRANSLATED-CALL-MISSING",
        "C++ native rendering requires translated backend-call IR for "
        f"candidate {candidate.candidate_id!r}",
        location=candidate.variant.source.declaration.source_span.location,
    )


def _missing_native_integer_plan_diagnostic(
    candidate: ImplementationCandidate,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-RENDER-NATIVE-TRANSLATION-MISSING",
        "C++ native integer rendering requires a translated native plan with "
        "M45 suffix and M46 type-spelling values; got no translated plan for "
        f"candidate {candidate.candidate_id!r}",
        location=candidate.variant.source.declaration.source_span.location,
    )


def _missing_native_integer_suffix_diagnostic(
    candidate: ImplementationCandidate,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-RENDER-NATIVE-SUFFIX-MISSING",
        "C++ native integer rendering requires a Milestone 45 suffix modifier "
        f"value {_CPP_NATIVE_INTEGER_INTRINSIC_SUFFIX!r} for candidate "
        f"{candidate.candidate_id!r}; renderer will not infer the intrinsic suffix",
        location=candidate.variant.source.declaration.source_span.location,
    )


def _unsupported_native_integer_suffix_diagnostic(
    candidate: ImplementationCandidate,
    modifiers: tuple[BackendIntrinsicModifier, ...],
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-RENDER-NATIVE-SUFFIX-UNSUPPORTED",
        "C++ native integer rendering supports only translated suffix modifier "
        f"{_CPP_NATIVE_INTEGER_INTRINSIC_SUFFIX!r} from source ref kind "
        f"{_CPP_NATIVE_INTEGER_SUFFIX_SOURCE_KIND!r}; got "
        f"{_modifier_list_text(modifiers)} for candidate {candidate.candidate_id!r}",
        location=candidate.variant.source.declaration.source_span.location,
    )


def _ambiguous_native_integer_suffix_diagnostic(
    candidate: ImplementationCandidate,
    modifiers: tuple[BackendIntrinsicModifier, ...],
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-RENDER-NATIVE-SUFFIX-AMBIGUOUS",
        "C++ native integer rendering received multiple translated suffix "
        f"modifier values for candidate {candidate.candidate_id!r}: "
        f"{_modifier_list_text(modifiers)}",
        location=candidate.variant.source.declaration.source_span.location,
    )


def _missing_native_integer_type_spelling_diagnostic(
    candidate: ImplementationCandidate,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-RENDER-NATIVE-TYPE-SPELLING-MISSING",
        "C++ native integer rendering requires a Milestone 46 base type "
        f"spelling for type tag {candidate.type_tag!r}; renderer will not infer "
        "the C++ type spelling",
        location=candidate.variant.source.declaration.source_span.location,
    )


def _unsupported_native_integer_type_spelling_diagnostic(
    candidate: ImplementationCandidate,
    spellings: tuple[BackendTypeSpelling, ...],
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-RENDER-NATIVE-TYPE-SPELLING-UNSUPPORTED",
        "C++ native integer rendering supports only M46 base type spelling "
        f"{_CPP_NATIVE_INTEGER_TYPE_BY_TAG[candidate.type_tag]!r} for type tag "
        f"{candidate.type_tag!r}; got {_type_spelling_list_text(spellings)}",
        location=candidate.variant.source.declaration.source_span.location,
    )


def _ambiguous_native_integer_type_spelling_diagnostic(
    candidate: ImplementationCandidate,
    spellings: tuple[BackendTypeSpelling, ...],
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-RENDER-NATIVE-TYPE-SPELLING-AMBIGUOUS",
        "C++ native integer rendering received multiple translated type "
        f"spelling values for candidate {candidate.candidate_id!r}: "
        f"{_type_spelling_list_text(spellings)}",
        location=candidate.variant.source.declaration.source_span.location,
    )


def _modifier_list_text(modifiers: tuple[BackendIntrinsicModifier, ...]) -> str:
    return ", ".join(
        "BackendIntrinsicModifier("
        f"kind={modifier.kind!r}, backend_id={modifier.backend_id!r}, "
        f"extension={modifier.extension!r}, intrinsic={modifier.intrinsic!r}, "
        f"value={modifier.value!r}, source_type_tag={modifier.source_type_tag!r}, "
        f"source_ref_kind={modifier.source_ref_kind!r})"
        for modifier in modifiers
    )


def _type_spelling_list_text(spellings: tuple[BackendTypeSpelling, ...]) -> str:
    return ", ".join(
        "BackendTypeSpelling("
        f"backend_id={spelling.backend_id!r}, type_tag={spelling.type_tag!r}, "
        f"spelling={spelling.spelling!r}, "
        f"source_ref_kind={spelling.source_ref_kind!r}, "
        f"source_type_tag={spelling.source_type_tag!r})"
        for spelling in spellings
    )


def _unsupported_parameter_shape_diagnostic(
    candidate: ImplementationCandidate,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-RENDER-SCALAR-UNSUPPORTED",
        "C++ scalar parity rendering supports only binary candidates with two "
        f"parameters; candidate {candidate.candidate_id!r} has "
        f"{len(candidate.variant.source.declaration.parameters)} parameter(s)",
        location=candidate.variant.source.declaration.source_span.location,
    )


def _unsupported_lowered_body_diagnostic(
    candidate: ImplementationCandidate,
    lowered: LoweredImplementation,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-RENDER-LOWERING-UNSUPPORTED",
        "C++ binary parity rendering supports only one mini-lowered return "
        f"statement for candidate {candidate.candidate_id!r}; lowered status is "
        f"{lowered.status!r} with {len(lowered.statements)} statement(s)",
        location=candidate.variant.source.declaration.source_span.location,
    )


def _mixed_scalar_slice_diagnostic(
    candidate: ImplementationCandidate,
    dimension: str,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CPP-RENDER-SCALAR-MIXED",
        "C++ scalar parity rendering requires one primitive/template/wrapper "
        f"shape per artifact; candidate {candidate.candidate_id!r} has a "
        f"different {dimension}",
        location=candidate.variant.source.declaration.source_span.location,
    )
