"""Exact stable declarations for the public C++ algorithm facade.

The literal table is the authoritative backend input. Algorithm assets retain
only named declaration holes and implementation bodies; generation never
parses target text to recover signatures.
"""

from __future__ import annotations

from dataclasses import dataclass

from tslc.backend.algorithm_surface import (
    ALGORITHM_CALLABLE_FORMS,
    ALGORITHM_FORMS_BY_NAME,
    AlgorithmBackendFormSupport,
    AlgorithmArity,
    AlgorithmCallableForm,
    AlgorithmMaskForm,
    AlgorithmSemanticFamily,
    AlgorithmShape,
)
from tslc.backend.cpp_public_declarations import (
    CppPublicDeclaration,
    CppPublicParameter,
    CppTemplateParameter,
    CppTemplateParameterKind,
)
from tslc.backend.public_declarations import (
    PublicDeclarationKind,
    PublicDeclarationStability,
)


@dataclass(frozen=True, slots=True)
class CppAlgorithmDeclarationSpec:
    hole: str | None
    name: str
    overload_index: int
    template_parameters: tuple[CppTemplateParameter, ...]
    parameters: tuple[CppPublicParameter, ...]
    result_type: str

    def declaration(self) -> CppPublicDeclaration:
        return CppPublicDeclaration(
            identity=f'tsl::algo::{self.name}#overload-{self.overload_index}',
            name=self.name,
            owner='tsl::algo',
            reachability=('tsl.hpp', 'tsl_algorithm.hpp'),
            stability=PublicDeclarationStability.STABLE,
            kind=PublicDeclarationKind.FUNCTION,
            overload=f'algorithm-overload-{self.overload_index}',
            template_parameters=self.template_parameters,
            parameters=self.parameters,
            result_type=self.result_type,
            specifiers=('inline',),
        )


@dataclass(frozen=True, slots=True)
class CppAlgorithmAliasSpec:
    hole: str
    name: str
    template_parameters: tuple[CppTemplateParameter, ...]
    alias_target: str

    def declaration(self) -> CppPublicDeclaration:
        return CppPublicDeclaration(
            identity=f'tsl::algo::{self.name}#alias',
            name=self.name,
            owner='tsl::algo',
            reachability=('tsl.hpp', 'tsl_algorithm.hpp'),
            stability=PublicDeclarationStability.STABLE,
            kind=PublicDeclarationKind.TYPE_ALIAS,
            overload='algorithm-type-alias',
            template_parameters=self.template_parameters,
            alias_target=self.alias_target,
        )


def _cpp_type_parameter(
    name: str,
    *,
    default: str | None = None,
) -> CppTemplateParameter:
    return CppTemplateParameter(
        name=name,
        kind=CppTemplateParameterKind.TYPE,
        type_spelling=None,
        default=default,
        constraint=None,
    )


def _cpp_value_parameter(
    name: str,
    *,
    default: str | None = None,
) -> CppTemplateParameter:
    return CppTemplateParameter(
        name=name,
        kind=CppTemplateParameterKind.VALUE,
        type_spelling="std::size_t",
        default=default,
        constraint=None,
    )


def _cpp_algorithm_parameter(name: str, type_spelling: str) -> CppPublicParameter:
    return CppPublicParameter(
        name=name,
        type_spelling=type_spelling,
        role=f"algorithm-parameter:{name}",
    )


def _cpp_parallelism_parameter(*, fixed: bool) -> CppTemplateParameter:
    if fixed:
        return _cpp_value_parameter("ParallelN")
    return _cpp_type_parameter(
        "Parallelism",
        default="::tsl::dataparallel::native",
    )


def _cpp_algorithm_spec(
    form: AlgorithmCallableForm,
    overload_index: int,
    template_parameters: tuple[CppTemplateParameter, ...],
    parameters: tuple[CppPublicParameter, ...],
    result_type: str,
) -> CppAlgorithmDeclarationSpec:
    return CppAlgorithmDeclarationSpec(
        hole=None,
        name=form.family.name,
        overload_index=overload_index,
        template_parameters=template_parameters,
        parameters=parameters,
        result_type=result_type,
    )


def _cpp_iteration_form_specs(
    form: AlgorithmCallableForm,
) -> tuple[CppAlgorithmDeclarationSpec, ...]:
    specs: list[CppAlgorithmDeclarationSpec] = []
    for pointer in (True, False):
        for fixed in (False, True):
            overload_index = (2 if fixed else 4) if pointer else (1 if fixed else 3)
            range_type = "T" if pointer else "Range"
            specs.append(
                _cpp_algorithm_spec(
                    form,
                    overload_index,
                    (
                        _cpp_parallelism_parameter(fixed=fixed),
                        _cpp_type_parameter("Op"),
                        _cpp_type_parameter(range_type),
                    ),
                    (
                        _cpp_algorithm_parameter("op", "Op&&"),
                        _cpp_algorithm_parameter(
                            "data", "T*" if pointer else "Range&"
                        ),
                        *((_cpp_algorithm_parameter(
                            "count", "std::size_t"
                        ),) if pointer else ()),
                    ),
                    "void",
                )
            )
    return tuple(specs)


def _cpp_iteration_specs() -> tuple[CppAlgorithmDeclarationSpec, ...]:
    form = next(
        form
        for form in ALGORITHM_CALLABLE_FORMS
        if form.family.semantic_family is AlgorithmSemanticFamily.ITERATION
    )
    return _cpp_iteration_form_specs(form)


def _cpp_predicate_count_parameters(
    form: AlgorithmCallableForm,
    *,
    pointer: bool,
    fixed: bool,
) -> tuple[CppPublicParameter, ...]:
    operation_name = (
        "op"
        if form.family.semantic_family is AlgorithmSemanticFamily.PREDICATE
        else "predicate"
    )
    parameters = [_cpp_algorithm_parameter(operation_name, "Op&&")]
    if form.family.arity is AlgorithmArity.UNARY:
        parameters.append(
            _cpp_algorithm_parameter(
                "input", "const T*" if pointer else "const InputRange&"
            )
        )
    else:
        parameters.extend(
            (
                _cpp_algorithm_parameter(
                    "left", "const T*" if pointer else "const LeftRange&"
                ),
                _cpp_algorithm_parameter(
                    "right", "const T*" if pointer else "const RightRange&"
                ),
            )
        )

    has_masks = (
        form.family.semantic_family is AlgorithmSemanticFamily.PREDICATE
        or form.family.shape is AlgorithmShape.MASKED
    )
    if has_masks:
        mutable = (
            form.family.semantic_family is AlgorithmSemanticFamily.PREDICATE
        )
        if pointer:
            storage = (
                "fixed_mask_storage_type<MaskLayout, ParallelN, T>"
                if fixed
                else (
                    "typename detail::mask_for<MaskLayout, "
                    "Parallelism, T>::type"
                )
            )
            mask_type = f"{storage}*" if mutable else f"const {storage}*"
        else:
            mask_type = "MaskRange&" if mutable else "const MaskRange&"
        parameters.append(_cpp_algorithm_parameter("masks", mask_type))

    if form.family.shape is AlgorithmShape.SELECTED:
        parameters.append(
            _cpp_algorithm_parameter(
                "indices", "const IndexT*" if pointer else "const IndexRange&"
            )
        )
        if pointer:
            parameters.append(
                _cpp_algorithm_parameter("selected_count", "std::size_t")
            )
    elif pointer:
        parameters.append(_cpp_algorithm_parameter("count", "std::size_t"))
    return tuple(parameters)


def _cpp_predicate_count_templates(
    form: AlgorithmCallableForm,
    *,
    pointer: bool,
    fixed: bool,
) -> tuple[CppTemplateParameter, ...]:
    parameters = [_cpp_parallelism_parameter(fixed=fixed)]
    if form.family.shape is AlgorithmShape.SELECTED:
        parameters.append(_cpp_value_parameter("Scale", default="0"))
    else:
        parameters.append(
            _cpp_type_parameter("Alignment", default="alignment::detect")
        )
    if (
        form.family.semantic_family is AlgorithmSemanticFamily.PREDICATE
        or form.family.shape is AlgorithmShape.MASKED
    ):
        parameters.append(
            _cpp_type_parameter("MaskLayout", default="mask_layout::integral")
        )
    parameters.append(_cpp_type_parameter("Op"))
    if pointer:
        parameters.append(_cpp_type_parameter("T"))
        if form.family.shape is AlgorithmShape.SELECTED:
            parameters.append(_cpp_type_parameter("IndexT"))
    elif form.family.arity is AlgorithmArity.UNARY:
        parameters.append(_cpp_type_parameter("InputRange"))
    else:
        parameters.extend(
            (
                _cpp_type_parameter("LeftRange"),
                _cpp_type_parameter("RightRange"),
            )
        )
    if not pointer and (
        form.family.semantic_family is AlgorithmSemanticFamily.PREDICATE
        or form.family.shape is AlgorithmShape.MASKED
    ):
        parameters.append(_cpp_type_parameter("MaskRange"))
    if not pointer and form.family.shape is AlgorithmShape.SELECTED:
        parameters.append(_cpp_type_parameter("IndexRange"))
    return tuple(parameters)


def _cpp_predicate_count_form_specs(
    form: AlgorithmCallableForm,
) -> tuple[CppAlgorithmDeclarationSpec, ...]:
    specs: list[CppAlgorithmDeclarationSpec] = []
    fixed_options = (True,) if form.family.shape is AlgorithmShape.SELECTED else (False, True)
    for pointer in (True, False):
        for fixed in fixed_options:
            overload_index = (2 if fixed else 4) if pointer else (1 if fixed else 3)
            specs.append(
                _cpp_algorithm_spec(
                    form,
                    overload_index,
                    _cpp_predicate_count_templates(
                        form,
                        pointer=pointer,
                        fixed=fixed,
                    ),
                    _cpp_predicate_count_parameters(
                        form,
                        pointer=pointer,
                        fixed=fixed,
                    ),
                    "std::size_t",
                )
            )
    return tuple(specs)


def _cpp_predicate_specs() -> tuple[CppAlgorithmDeclarationSpec, ...]:
    return tuple(
        spec
        for form in ALGORITHM_CALLABLE_FORMS
        if form.family.semantic_family is AlgorithmSemanticFamily.PREDICATE
        and form.mask_form is AlgorithmMaskForm.DEFAULT
        for spec in _cpp_predicate_count_form_specs(form)
    )


def _cpp_count_specs(*, selected: bool) -> tuple[CppAlgorithmDeclarationSpec, ...]:
    return tuple(
        spec
        for form in ALGORITHM_CALLABLE_FORMS
        if form.family.semantic_family is AlgorithmSemanticFamily.COUNT
        and form.mask_form is AlgorithmMaskForm.DEFAULT
        and (form.family.shape is AlgorithmShape.SELECTED) is selected
        for spec in _cpp_predicate_count_form_specs(form)
    )


def cpp_iteration_predicate_count_declarations(
    form: AlgorithmCallableForm,
) -> tuple[CppPublicDeclaration, ...]:
    """Project one first-slice form into exact C++ function declarations."""

    if form.mask_form is not AlgorithmMaskForm.DEFAULT:
        raise ValueError(
            "C++ algorithm forms project mask layout through a template axis"
        )
    if form.family.semantic_family is AlgorithmSemanticFamily.ITERATION:
        if form.family.shape is not AlgorithmShape.CHUNK_ITERATION:
            raise ValueError("C++ iteration forms require chunk iteration")
        specs = _cpp_iteration_form_specs(form)
    elif form.family.semantic_family is AlgorithmSemanticFamily.PREDICATE:
        if form.family.shape is not AlgorithmShape.PLAIN:
            raise ValueError("C++ predicate forms require the plain shape")
        specs = _cpp_predicate_count_form_specs(form)
    elif form.family.semantic_family is AlgorithmSemanticFamily.COUNT:
        if form.family.shape not in {
            AlgorithmShape.PLAIN,
            AlgorithmShape.MASKED,
            AlgorithmShape.SELECTED,
        }:
            raise ValueError("C++ count form has an unsupported shape")
        specs = _cpp_predicate_count_form_specs(form)
    else:
        raise ValueError("algorithm form is outside the first C++ projection slice")
    return tuple(spec.declaration() for spec in specs)


_FUNCTION_SPECS: tuple[CppAlgorithmDeclarationSpec, ...] = (
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_integral_mask_chunk_count_2',
        name='integral_mask_chunk_count',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_integral_mask_chunk_count_1',
        name='integral_mask_chunk_count',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_native_mask_chunk_count_2',
        name='native_mask_chunk_count',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_native_mask_chunk_count_1',
        name='native_mask_chunk_count',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_mask_chunk_count_2',
        name='mask_chunk_count',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_mask_chunk_count_1',
        name='mask_chunk_count',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_byte_mask_count_2',
        name='byte_mask_count',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_byte_mask_count_1',
        name='byte_mask_count',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_bit_mask_count_2',
        name='bit_mask_count',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_bit_mask_count_1',
        name='bit_mask_count',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='std::size_t',
    ),
    *_cpp_iteration_specs(),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_transform_unary_4',
        name='transform_unary',
        overload_index=4,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const T*', role='algorithm-parameter:input'),
            CppPublicParameter(name='output', type_spelling='T*', role='algorithm-parameter:output'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_transform_unary_3',
        name='transform_unary',
        overload_index=3,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='InputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='OutputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const InputRange&', role='algorithm-parameter:input'),
            CppPublicParameter(name='output', type_spelling='OutputRange&', role='algorithm-parameter:output'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_transform_unary_2',
        name='transform_unary',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const T*', role='algorithm-parameter:input'),
            CppPublicParameter(name='output', type_spelling='T*', role='algorithm-parameter:output'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_transform_unary_1',
        name='transform_unary',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='InputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='OutputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const InputRange&', role='algorithm-parameter:input'),
            CppPublicParameter(name='output', type_spelling='OutputRange&', role='algorithm-parameter:output'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_transform_binary_4',
        name='transform_binary',
        overload_index=4,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const T*', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const T*', role='algorithm-parameter:right'),
            CppPublicParameter(name='output', type_spelling='T*', role='algorithm-parameter:output'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_transform_binary_3',
        name='transform_binary',
        overload_index=3,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='LeftRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='RightRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='OutputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const LeftRange&', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const RightRange&', role='algorithm-parameter:right'),
            CppPublicParameter(name='output', type_spelling='OutputRange&', role='algorithm-parameter:output'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_transform_binary_2',
        name='transform_binary',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const T*', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const T*', role='algorithm-parameter:right'),
            CppPublicParameter(name='output', type_spelling='T*', role='algorithm-parameter:output'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_transform_binary_1',
        name='transform_binary',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='LeftRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='RightRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='OutputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const LeftRange&', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const RightRange&', role='algorithm-parameter:right'),
            CppPublicParameter(name='output', type_spelling='OutputRange&', role='algorithm-parameter:output'),
        ),
        result_type='void',
    ),
    *_cpp_predicate_specs(),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_transform_where_unary_4',
        name='transform_where_unary',
        overload_index=4,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const T*', role='algorithm-parameter:input'),
            CppPublicParameter(name='masks', type_spelling='const typename detail::mask_for<MaskLayout, Parallelism, T>::type*', role='algorithm-parameter:masks'),
            CppPublicParameter(name='output', type_spelling='T*', role='algorithm-parameter:output'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_transform_where_unary_2',
        name='transform_where_unary',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const T*', role='algorithm-parameter:input'),
            CppPublicParameter(name='masks', type_spelling='const fixed_mask_storage_type<MaskLayout, ParallelN, T>*', role='algorithm-parameter:masks'),
            CppPublicParameter(name='output', type_spelling='T*', role='algorithm-parameter:output'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_transform_where_unary_3',
        name='transform_where_unary',
        overload_index=3,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='InputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='MaskRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='OutputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const InputRange&', role='algorithm-parameter:input'),
            CppPublicParameter(name='masks', type_spelling='const MaskRange&', role='algorithm-parameter:masks'),
            CppPublicParameter(name='output', type_spelling='OutputRange&', role='algorithm-parameter:output'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_transform_where_unary_1',
        name='transform_where_unary',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='InputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='MaskRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='OutputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const InputRange&', role='algorithm-parameter:input'),
            CppPublicParameter(name='masks', type_spelling='const MaskRange&', role='algorithm-parameter:masks'),
            CppPublicParameter(name='output', type_spelling='OutputRange&', role='algorithm-parameter:output'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_transform_where_binary_4',
        name='transform_where_binary',
        overload_index=4,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const T*', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const T*', role='algorithm-parameter:right'),
            CppPublicParameter(name='masks', type_spelling='const typename detail::mask_for<MaskLayout, Parallelism, T>::type*', role='algorithm-parameter:masks'),
            CppPublicParameter(name='output', type_spelling='T*', role='algorithm-parameter:output'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_transform_where_binary_2',
        name='transform_where_binary',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const T*', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const T*', role='algorithm-parameter:right'),
            CppPublicParameter(name='masks', type_spelling='const fixed_mask_storage_type<MaskLayout, ParallelN, T>*', role='algorithm-parameter:masks'),
            CppPublicParameter(name='output', type_spelling='T*', role='algorithm-parameter:output'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_transform_where_binary_3',
        name='transform_where_binary',
        overload_index=3,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='LeftRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='RightRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='MaskRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='OutputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const LeftRange&', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const RightRange&', role='algorithm-parameter:right'),
            CppPublicParameter(name='masks', type_spelling='const MaskRange&', role='algorithm-parameter:masks'),
            CppPublicParameter(name='output', type_spelling='OutputRange&', role='algorithm-parameter:output'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_transform_where_binary_1',
        name='transform_where_binary',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='LeftRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='RightRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='MaskRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='OutputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const LeftRange&', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const RightRange&', role='algorithm-parameter:right'),
            CppPublicParameter(name='masks', type_spelling='const MaskRange&', role='algorithm-parameter:masks'),
            CppPublicParameter(name='output', type_spelling='OutputRange&', role='algorithm-parameter:output'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_transform_masked_unary_4',
        name='transform_masked_unary',
        overload_index=4,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const T*', role='algorithm-parameter:input'),
            CppPublicParameter(name='masks', type_spelling='const typename detail::mask_for<MaskLayout, Parallelism, T>::type*', role='algorithm-parameter:masks'),
            CppPublicParameter(name='output', type_spelling='T*', role='algorithm-parameter:output'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_transform_masked_unary_2',
        name='transform_masked_unary',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const T*', role='algorithm-parameter:input'),
            CppPublicParameter(name='masks', type_spelling='const fixed_mask_storage_type<MaskLayout, ParallelN, T>*', role='algorithm-parameter:masks'),
            CppPublicParameter(name='output', type_spelling='T*', role='algorithm-parameter:output'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_transform_masked_unary_3',
        name='transform_masked_unary',
        overload_index=3,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='InputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='MaskRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='OutputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const InputRange&', role='algorithm-parameter:input'),
            CppPublicParameter(name='masks', type_spelling='const MaskRange&', role='algorithm-parameter:masks'),
            CppPublicParameter(name='output', type_spelling='OutputRange&', role='algorithm-parameter:output'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_transform_masked_unary_1',
        name='transform_masked_unary',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='InputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='MaskRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='OutputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const InputRange&', role='algorithm-parameter:input'),
            CppPublicParameter(name='masks', type_spelling='const MaskRange&', role='algorithm-parameter:masks'),
            CppPublicParameter(name='output', type_spelling='OutputRange&', role='algorithm-parameter:output'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_transform_masked_binary_4',
        name='transform_masked_binary',
        overload_index=4,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const T*', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const T*', role='algorithm-parameter:right'),
            CppPublicParameter(name='masks', type_spelling='const typename detail::mask_for<MaskLayout, Parallelism, T>::type*', role='algorithm-parameter:masks'),
            CppPublicParameter(name='output', type_spelling='T*', role='algorithm-parameter:output'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_transform_masked_binary_2',
        name='transform_masked_binary',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const T*', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const T*', role='algorithm-parameter:right'),
            CppPublicParameter(name='masks', type_spelling='const fixed_mask_storage_type<MaskLayout, ParallelN, T>*', role='algorithm-parameter:masks'),
            CppPublicParameter(name='output', type_spelling='T*', role='algorithm-parameter:output'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_transform_masked_binary_3',
        name='transform_masked_binary',
        overload_index=3,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='LeftRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='RightRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='MaskRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='OutputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const LeftRange&', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const RightRange&', role='algorithm-parameter:right'),
            CppPublicParameter(name='masks', type_spelling='const MaskRange&', role='algorithm-parameter:masks'),
            CppPublicParameter(name='output', type_spelling='OutputRange&', role='algorithm-parameter:output'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_transform_masked_binary_1',
        name='transform_masked_binary',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='LeftRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='RightRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='MaskRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='OutputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const LeftRange&', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const RightRange&', role='algorithm-parameter:right'),
            CppPublicParameter(name='masks', type_spelling='const MaskRange&', role='algorithm-parameter:masks'),
            CppPublicParameter(name='output', type_spelling='OutputRange&', role='algorithm-parameter:output'),
        ),
        result_type='void',
    ),
    *_cpp_count_specs(selected=False),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_unary_4',
        name='select_unary',
        overload_index=4,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='input', type_spelling='const T*', role='algorithm-parameter:input'),
            CppPublicParameter(name='output', type_spelling='T*', role='algorithm-parameter:output'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_unary_2',
        name='select_unary',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='input', type_spelling='const T*', role='algorithm-parameter:input'),
            CppPublicParameter(name='output', type_spelling='T*', role='algorithm-parameter:output'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_unary_3',
        name='select_unary',
        overload_index=3,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='InputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='OutputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='input', type_spelling='const InputRange&', role='algorithm-parameter:input'),
            CppPublicParameter(name='output', type_spelling='OutputRange&', role='algorithm-parameter:output'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_unary_1',
        name='select_unary',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='InputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='OutputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='input', type_spelling='const InputRange&', role='algorithm-parameter:input'),
            CppPublicParameter(name='output', type_spelling='OutputRange&', role='algorithm-parameter:output'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_binary_4',
        name='select_binary',
        overload_index=4,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='left', type_spelling='const T*', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const T*', role='algorithm-parameter:right'),
            CppPublicParameter(name='output', type_spelling='T*', role='algorithm-parameter:output'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_binary_2',
        name='select_binary',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='left', type_spelling='const T*', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const T*', role='algorithm-parameter:right'),
            CppPublicParameter(name='output', type_spelling='T*', role='algorithm-parameter:output'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_binary_3',
        name='select_binary',
        overload_index=3,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='LeftRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='RightRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='OutputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='left', type_spelling='const LeftRange&', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const RightRange&', role='algorithm-parameter:right'),
            CppPublicParameter(name='output', type_spelling='OutputRange&', role='algorithm-parameter:output'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_binary_1',
        name='select_binary',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='LeftRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='RightRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='OutputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='left', type_spelling='const LeftRange&', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const RightRange&', role='algorithm-parameter:right'),
            CppPublicParameter(name='output', type_spelling='OutputRange&', role='algorithm-parameter:output'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_masked_unary_4',
        name='select_masked_unary',
        overload_index=4,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='input', type_spelling='const T*', role='algorithm-parameter:input'),
            CppPublicParameter(name='masks', type_spelling='const typename detail::mask_for<MaskLayout, Parallelism, T>::type*', role='algorithm-parameter:masks'),
            CppPublicParameter(name='output', type_spelling='T*', role='algorithm-parameter:output'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_masked_unary_2',
        name='select_masked_unary',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='input', type_spelling='const T*', role='algorithm-parameter:input'),
            CppPublicParameter(name='masks', type_spelling='const fixed_mask_storage_type<MaskLayout, ParallelN, T>*', role='algorithm-parameter:masks'),
            CppPublicParameter(name='output', type_spelling='T*', role='algorithm-parameter:output'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_masked_unary_3',
        name='select_masked_unary',
        overload_index=3,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='InputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='MaskRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='OutputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='input', type_spelling='const InputRange&', role='algorithm-parameter:input'),
            CppPublicParameter(name='masks', type_spelling='const MaskRange&', role='algorithm-parameter:masks'),
            CppPublicParameter(name='output', type_spelling='OutputRange&', role='algorithm-parameter:output'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_masked_unary_1',
        name='select_masked_unary',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='InputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='MaskRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='OutputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='input', type_spelling='const InputRange&', role='algorithm-parameter:input'),
            CppPublicParameter(name='masks', type_spelling='const MaskRange&', role='algorithm-parameter:masks'),
            CppPublicParameter(name='output', type_spelling='OutputRange&', role='algorithm-parameter:output'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_masked_binary_4',
        name='select_masked_binary',
        overload_index=4,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='left', type_spelling='const T*', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const T*', role='algorithm-parameter:right'),
            CppPublicParameter(name='masks', type_spelling='const typename detail::mask_for<MaskLayout, Parallelism, T>::type*', role='algorithm-parameter:masks'),
            CppPublicParameter(name='output', type_spelling='T*', role='algorithm-parameter:output'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_masked_binary_2',
        name='select_masked_binary',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='left', type_spelling='const T*', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const T*', role='algorithm-parameter:right'),
            CppPublicParameter(name='masks', type_spelling='const fixed_mask_storage_type<MaskLayout, ParallelN, T>*', role='algorithm-parameter:masks'),
            CppPublicParameter(name='output', type_spelling='T*', role='algorithm-parameter:output'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_masked_binary_3',
        name='select_masked_binary',
        overload_index=3,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='LeftRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='RightRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='MaskRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='OutputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='left', type_spelling='const LeftRange&', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const RightRange&', role='algorithm-parameter:right'),
            CppPublicParameter(name='masks', type_spelling='const MaskRange&', role='algorithm-parameter:masks'),
            CppPublicParameter(name='output', type_spelling='OutputRange&', role='algorithm-parameter:output'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_masked_binary_1',
        name='select_masked_binary',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='LeftRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='RightRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='MaskRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='OutputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='left', type_spelling='const LeftRange&', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const RightRange&', role='algorithm-parameter:right'),
            CppPublicParameter(name='masks', type_spelling='const MaskRange&', role='algorithm-parameter:masks'),
            CppPublicParameter(name='output', type_spelling='OutputRange&', role='algorithm-parameter:output'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_indices_unary_4',
        name='select_indices_unary',
        overload_index=4,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='IndexT', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='input', type_spelling='const T*', role='algorithm-parameter:input'),
            CppPublicParameter(name='indices', type_spelling='IndexT*', role='algorithm-parameter:indices'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_indices_unary_2',
        name='select_indices_unary',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='IndexT', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='input', type_spelling='const T*', role='algorithm-parameter:input'),
            CppPublicParameter(name='indices', type_spelling='IndexT*', role='algorithm-parameter:indices'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_indices_unary_3',
        name='select_indices_unary',
        overload_index=3,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='InputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='IndexRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='input', type_spelling='const InputRange&', role='algorithm-parameter:input'),
            CppPublicParameter(name='indices', type_spelling='IndexRange&', role='algorithm-parameter:indices'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_indices_unary_1',
        name='select_indices_unary',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='InputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='IndexRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='input', type_spelling='const InputRange&', role='algorithm-parameter:input'),
            CppPublicParameter(name='indices', type_spelling='IndexRange&', role='algorithm-parameter:indices'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_indices_binary_4',
        name='select_indices_binary',
        overload_index=4,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='IndexT', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='left', type_spelling='const T*', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const T*', role='algorithm-parameter:right'),
            CppPublicParameter(name='indices', type_spelling='IndexT*', role='algorithm-parameter:indices'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_indices_binary_2',
        name='select_indices_binary',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='IndexT', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='left', type_spelling='const T*', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const T*', role='algorithm-parameter:right'),
            CppPublicParameter(name='indices', type_spelling='IndexT*', role='algorithm-parameter:indices'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_indices_binary_3',
        name='select_indices_binary',
        overload_index=3,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='LeftRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='RightRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='IndexRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='left', type_spelling='const LeftRange&', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const RightRange&', role='algorithm-parameter:right'),
            CppPublicParameter(name='indices', type_spelling='IndexRange&', role='algorithm-parameter:indices'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_indices_binary_1',
        name='select_indices_binary',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='LeftRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='RightRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='IndexRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='left', type_spelling='const LeftRange&', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const RightRange&', role='algorithm-parameter:right'),
            CppPublicParameter(name='indices', type_spelling='IndexRange&', role='algorithm-parameter:indices'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_masked_indices_unary_4',
        name='select_masked_indices_unary',
        overload_index=4,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='IndexT', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='input', type_spelling='const T*', role='algorithm-parameter:input'),
            CppPublicParameter(name='masks', type_spelling='const typename detail::mask_for<MaskLayout, Parallelism, T>::type*', role='algorithm-parameter:masks'),
            CppPublicParameter(name='indices', type_spelling='IndexT*', role='algorithm-parameter:indices'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_masked_indices_unary_2',
        name='select_masked_indices_unary',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='IndexT', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='input', type_spelling='const T*', role='algorithm-parameter:input'),
            CppPublicParameter(name='masks', type_spelling='const fixed_mask_storage_type<MaskLayout, ParallelN, T>*', role='algorithm-parameter:masks'),
            CppPublicParameter(name='indices', type_spelling='IndexT*', role='algorithm-parameter:indices'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_masked_indices_unary_3',
        name='select_masked_indices_unary',
        overload_index=3,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='InputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='MaskRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='IndexRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='input', type_spelling='const InputRange&', role='algorithm-parameter:input'),
            CppPublicParameter(name='masks', type_spelling='const MaskRange&', role='algorithm-parameter:masks'),
            CppPublicParameter(name='indices', type_spelling='IndexRange&', role='algorithm-parameter:indices'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_masked_indices_unary_1',
        name='select_masked_indices_unary',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='InputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='MaskRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='IndexRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='input', type_spelling='const InputRange&', role='algorithm-parameter:input'),
            CppPublicParameter(name='masks', type_spelling='const MaskRange&', role='algorithm-parameter:masks'),
            CppPublicParameter(name='indices', type_spelling='IndexRange&', role='algorithm-parameter:indices'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_masked_indices_binary_4',
        name='select_masked_indices_binary',
        overload_index=4,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='IndexT', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='left', type_spelling='const T*', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const T*', role='algorithm-parameter:right'),
            CppPublicParameter(name='masks', type_spelling='const typename detail::mask_for<MaskLayout, Parallelism, T>::type*', role='algorithm-parameter:masks'),
            CppPublicParameter(name='indices', type_spelling='IndexT*', role='algorithm-parameter:indices'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_masked_indices_binary_2',
        name='select_masked_indices_binary',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='IndexT', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='left', type_spelling='const T*', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const T*', role='algorithm-parameter:right'),
            CppPublicParameter(name='masks', type_spelling='const fixed_mask_storage_type<MaskLayout, ParallelN, T>*', role='algorithm-parameter:masks'),
            CppPublicParameter(name='indices', type_spelling='IndexT*', role='algorithm-parameter:indices'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_masked_indices_binary_3',
        name='select_masked_indices_binary',
        overload_index=3,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='LeftRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='RightRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='MaskRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='IndexRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='left', type_spelling='const LeftRange&', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const RightRange&', role='algorithm-parameter:right'),
            CppPublicParameter(name='masks', type_spelling='const MaskRange&', role='algorithm-parameter:masks'),
            CppPublicParameter(name='indices', type_spelling='IndexRange&', role='algorithm-parameter:indices'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_masked_indices_binary_1',
        name='select_masked_indices_binary',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='LeftRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='RightRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='MaskRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='IndexRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='left', type_spelling='const LeftRange&', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const RightRange&', role='algorithm-parameter:right'),
            CppPublicParameter(name='masks', type_spelling='const MaskRange&', role='algorithm-parameter:masks'),
            CppPublicParameter(name='indices', type_spelling='IndexRange&', role='algorithm-parameter:indices'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_selected_indices_unary_2',
        name='select_selected_indices_unary',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Scale', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default='0', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='InputIndexT', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='OutputIndexT', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='input', type_spelling='const T*', role='algorithm-parameter:input'),
            CppPublicParameter(name='input_indices', type_spelling='const InputIndexT*', role='algorithm-parameter:input_indices'),
            CppPublicParameter(name='output_indices', type_spelling='OutputIndexT*', role='algorithm-parameter:output_indices'),
            CppPublicParameter(name='selected_count', type_spelling='std::size_t', role='algorithm-parameter:selected_count'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_selected_indices_unary_1',
        name='select_selected_indices_unary',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Scale', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default='0', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='InputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='InputIndexRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='OutputIndexRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='input', type_spelling='const InputRange&', role='algorithm-parameter:input'),
            CppPublicParameter(name='input_indices', type_spelling='const InputIndexRange&', role='algorithm-parameter:input_indices'),
            CppPublicParameter(name='output_indices', type_spelling='OutputIndexRange&', role='algorithm-parameter:output_indices'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_selected_indices_binary_2',
        name='select_selected_indices_binary',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Scale', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default='0', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='InputIndexT', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='OutputIndexT', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='left', type_spelling='const T*', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const T*', role='algorithm-parameter:right'),
            CppPublicParameter(name='input_indices', type_spelling='const InputIndexT*', role='algorithm-parameter:input_indices'),
            CppPublicParameter(name='output_indices', type_spelling='OutputIndexT*', role='algorithm-parameter:output_indices'),
            CppPublicParameter(name='selected_count', type_spelling='std::size_t', role='algorithm-parameter:selected_count'),
        ),
        result_type='std::size_t',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_select_selected_indices_binary_1',
        name='select_selected_indices_binary',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Scale', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default='0', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='LeftRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='RightRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='InputIndexRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='OutputIndexRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='predicate', type_spelling='Op&&', role='algorithm-parameter:predicate'),
            CppPublicParameter(name='left', type_spelling='const LeftRange&', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const RightRange&', role='algorithm-parameter:right'),
            CppPublicParameter(name='input_indices', type_spelling='const InputIndexRange&', role='algorithm-parameter:input_indices'),
            CppPublicParameter(name='output_indices', type_spelling='OutputIndexRange&', role='algorithm-parameter:output_indices'),
        ),
        result_type='std::size_t',
    ),
    *_cpp_count_specs(selected=True),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_transform_selected_unary_2',
        name='transform_selected_unary',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Scale', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default='0', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='IndexT', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const T*', role='algorithm-parameter:input'),
            CppPublicParameter(name='indices', type_spelling='const IndexT*', role='algorithm-parameter:indices'),
            CppPublicParameter(name='output', type_spelling='T*', role='algorithm-parameter:output'),
            CppPublicParameter(name='selected_count', type_spelling='std::size_t', role='algorithm-parameter:selected_count'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_transform_selected_unary_1',
        name='transform_selected_unary',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Scale', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default='0', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='InputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='IndexRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='OutputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const InputRange&', role='algorithm-parameter:input'),
            CppPublicParameter(name='indices', type_spelling='const IndexRange&', role='algorithm-parameter:indices'),
            CppPublicParameter(name='output', type_spelling='OutputRange&', role='algorithm-parameter:output'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_transform_selected_binary_2',
        name='transform_selected_binary',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Scale', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default='0', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='IndexT', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const T*', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const T*', role='algorithm-parameter:right'),
            CppPublicParameter(name='indices', type_spelling='const IndexT*', role='algorithm-parameter:indices'),
            CppPublicParameter(name='output', type_spelling='T*', role='algorithm-parameter:output'),
            CppPublicParameter(name='selected_count', type_spelling='std::size_t', role='algorithm-parameter:selected_count'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_transform_selected_binary_1',
        name='transform_selected_binary',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Scale', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default='0', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='LeftRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='RightRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='IndexRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='OutputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const LeftRange&', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const RightRange&', role='algorithm-parameter:right'),
            CppPublicParameter(name='indices', type_spelling='const IndexRange&', role='algorithm-parameter:indices'),
            CppPublicParameter(name='output', type_spelling='OutputRange&', role='algorithm-parameter:output'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_aggregate_selected_unary_2',
        name='aggregate_selected_unary',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Scale', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default='0', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='IndexT', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const T*', role='algorithm-parameter:input'),
            CppPublicParameter(name='indices', type_spelling='const IndexT*', role='algorithm-parameter:indices'),
            CppPublicParameter(name='selected_count', type_spelling='std::size_t', role='algorithm-parameter:selected_count'),
        ),
        result_type='auto',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_aggregate_selected_unary_1',
        name='aggregate_selected_unary',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Scale', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default='0', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='InputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='IndexRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const InputRange&', role='algorithm-parameter:input'),
            CppPublicParameter(name='indices', type_spelling='const IndexRange&', role='algorithm-parameter:indices'),
        ),
        result_type='auto',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_aggregate_selected_binary_2',
        name='aggregate_selected_binary',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Scale', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default='0', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='IndexT', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const T*', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const T*', role='algorithm-parameter:right'),
            CppPublicParameter(name='indices', type_spelling='const IndexT*', role='algorithm-parameter:indices'),
            CppPublicParameter(name='selected_count', type_spelling='std::size_t', role='algorithm-parameter:selected_count'),
        ),
        result_type='auto',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_aggregate_selected_binary_1',
        name='aggregate_selected_binary',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Scale', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default='0', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='LeftRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='RightRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='IndexRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const LeftRange&', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const RightRange&', role='algorithm-parameter:right'),
            CppPublicParameter(name='indices', type_spelling='const IndexRange&', role='algorithm-parameter:indices'),
        ),
        result_type='auto',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_consume_selected_unary_2',
        name='consume_selected_unary',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Scale', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default='0', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='IndexT', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const T*', role='algorithm-parameter:input'),
            CppPublicParameter(name='indices', type_spelling='const IndexT*', role='algorithm-parameter:indices'),
            CppPublicParameter(name='selected_count', type_spelling='std::size_t', role='algorithm-parameter:selected_count'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_consume_selected_unary_1',
        name='consume_selected_unary',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Scale', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default='0', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='InputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='IndexRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const InputRange&', role='algorithm-parameter:input'),
            CppPublicParameter(name='indices', type_spelling='const IndexRange&', role='algorithm-parameter:indices'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_consume_selected_binary_2',
        name='consume_selected_binary',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Scale', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default='0', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='IndexT', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const T*', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const T*', role='algorithm-parameter:right'),
            CppPublicParameter(name='indices', type_spelling='const IndexT*', role='algorithm-parameter:indices'),
            CppPublicParameter(name='selected_count', type_spelling='std::size_t', role='algorithm-parameter:selected_count'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_consume_selected_binary_1',
        name='consume_selected_binary',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Scale', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default='0', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='LeftRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='RightRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='IndexRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const LeftRange&', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const RightRange&', role='algorithm-parameter:right'),
            CppPublicParameter(name='indices', type_spelling='const IndexRange&', role='algorithm-parameter:indices'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_aggregate_unary_4',
        name='aggregate_unary',
        overload_index=4,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const T*', role='algorithm-parameter:input'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='auto',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_aggregate_unary_2',
        name='aggregate_unary',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const T*', role='algorithm-parameter:input'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='auto',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_aggregate_unary_3',
        name='aggregate_unary',
        overload_index=3,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='InputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const InputRange&', role='algorithm-parameter:input'),
        ),
        result_type='auto',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_aggregate_unary_1',
        name='aggregate_unary',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='InputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const InputRange&', role='algorithm-parameter:input'),
        ),
        result_type='auto',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_aggregate_binary_4',
        name='aggregate_binary',
        overload_index=4,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const T*', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const T*', role='algorithm-parameter:right'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='auto',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_aggregate_binary_2',
        name='aggregate_binary',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const T*', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const T*', role='algorithm-parameter:right'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='auto',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_aggregate_binary_3',
        name='aggregate_binary',
        overload_index=3,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='LeftRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='RightRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const LeftRange&', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const RightRange&', role='algorithm-parameter:right'),
        ),
        result_type='auto',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_aggregate_binary_1',
        name='aggregate_binary',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='LeftRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='RightRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const LeftRange&', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const RightRange&', role='algorithm-parameter:right'),
        ),
        result_type='auto',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_aggregate_masked_unary_4',
        name='aggregate_masked_unary',
        overload_index=4,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const T*', role='algorithm-parameter:input'),
            CppPublicParameter(name='masks', type_spelling='const typename detail::mask_for<MaskLayout, Parallelism, T>::type*', role='algorithm-parameter:masks'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='auto',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_aggregate_masked_unary_2',
        name='aggregate_masked_unary',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const T*', role='algorithm-parameter:input'),
            CppPublicParameter(name='masks', type_spelling='const fixed_mask_storage_type<MaskLayout, ParallelN, T>*', role='algorithm-parameter:masks'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='auto',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_aggregate_masked_unary_3',
        name='aggregate_masked_unary',
        overload_index=3,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='InputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='MaskRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const InputRange&', role='algorithm-parameter:input'),
            CppPublicParameter(name='masks', type_spelling='const MaskRange&', role='algorithm-parameter:masks'),
        ),
        result_type='auto',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_aggregate_masked_unary_1',
        name='aggregate_masked_unary',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='InputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='MaskRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const InputRange&', role='algorithm-parameter:input'),
            CppPublicParameter(name='masks', type_spelling='const MaskRange&', role='algorithm-parameter:masks'),
        ),
        result_type='auto',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_aggregate_masked_binary_4',
        name='aggregate_masked_binary',
        overload_index=4,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const T*', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const T*', role='algorithm-parameter:right'),
            CppPublicParameter(name='masks', type_spelling='const typename detail::mask_for<MaskLayout, Parallelism, T>::type*', role='algorithm-parameter:masks'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='auto',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_aggregate_masked_binary_2',
        name='aggregate_masked_binary',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const T*', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const T*', role='algorithm-parameter:right'),
            CppPublicParameter(name='masks', type_spelling='const fixed_mask_storage_type<MaskLayout, ParallelN, T>*', role='algorithm-parameter:masks'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='auto',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_aggregate_masked_binary_3',
        name='aggregate_masked_binary',
        overload_index=3,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='LeftRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='RightRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='MaskRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const LeftRange&', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const RightRange&', role='algorithm-parameter:right'),
            CppPublicParameter(name='masks', type_spelling='const MaskRange&', role='algorithm-parameter:masks'),
        ),
        result_type='auto',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_aggregate_masked_binary_1',
        name='aggregate_masked_binary',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='LeftRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='RightRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='MaskRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const LeftRange&', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const RightRange&', role='algorithm-parameter:right'),
            CppPublicParameter(name='masks', type_spelling='const MaskRange&', role='algorithm-parameter:masks'),
        ),
        result_type='auto',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_consume_unary_4',
        name='consume_unary',
        overload_index=4,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const T*', role='algorithm-parameter:input'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_consume_unary_2',
        name='consume_unary',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const T*', role='algorithm-parameter:input'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_consume_unary_3',
        name='consume_unary',
        overload_index=3,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='InputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const InputRange&', role='algorithm-parameter:input'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_consume_unary_1',
        name='consume_unary',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='InputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const InputRange&', role='algorithm-parameter:input'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_consume_binary_4',
        name='consume_binary',
        overload_index=4,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const T*', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const T*', role='algorithm-parameter:right'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_consume_binary_2',
        name='consume_binary',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const T*', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const T*', role='algorithm-parameter:right'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_consume_binary_3',
        name='consume_binary',
        overload_index=3,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='LeftRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='RightRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const LeftRange&', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const RightRange&', role='algorithm-parameter:right'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_consume_binary_1',
        name='consume_binary',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='LeftRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='RightRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const LeftRange&', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const RightRange&', role='algorithm-parameter:right'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_consume_masked_unary_4',
        name='consume_masked_unary',
        overload_index=4,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const T*', role='algorithm-parameter:input'),
            CppPublicParameter(name='masks', type_spelling='const typename detail::mask_for<MaskLayout, Parallelism, T>::type*', role='algorithm-parameter:masks'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_consume_masked_unary_2',
        name='consume_masked_unary',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const T*', role='algorithm-parameter:input'),
            CppPublicParameter(name='masks', type_spelling='const fixed_mask_storage_type<MaskLayout, ParallelN, T>*', role='algorithm-parameter:masks'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_consume_masked_unary_3',
        name='consume_masked_unary',
        overload_index=3,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='InputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='MaskRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const InputRange&', role='algorithm-parameter:input'),
            CppPublicParameter(name='masks', type_spelling='const MaskRange&', role='algorithm-parameter:masks'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_consume_masked_unary_1',
        name='consume_masked_unary',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='InputRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='MaskRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='input', type_spelling='const InputRange&', role='algorithm-parameter:input'),
            CppPublicParameter(name='masks', type_spelling='const MaskRange&', role='algorithm-parameter:masks'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_consume_masked_binary_4',
        name='consume_masked_binary',
        overload_index=4,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const T*', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const T*', role='algorithm-parameter:right'),
            CppPublicParameter(name='masks', type_spelling='const typename detail::mask_for<MaskLayout, Parallelism, T>::type*', role='algorithm-parameter:masks'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_consume_masked_binary_2',
        name='consume_masked_binary',
        overload_index=2,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const T*', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const T*', role='algorithm-parameter:right'),
            CppPublicParameter(name='masks', type_spelling='const fixed_mask_storage_type<MaskLayout, ParallelN, T>*', role='algorithm-parameter:masks'),
            CppPublicParameter(name='count', type_spelling='std::size_t', role='algorithm-parameter:count'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_consume_masked_binary_3',
        name='consume_masked_binary',
        overload_index=3,
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='::tsl::dataparallel::native', constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='LeftRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='RightRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='MaskRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const LeftRange&', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const RightRange&', role='algorithm-parameter:right'),
            CppPublicParameter(name='masks', type_spelling='const MaskRange&', role='algorithm-parameter:masks'),
        ),
        result_type='void',
    ),
    CppAlgorithmDeclarationSpec(
        hole='algorithm_declaration_consume_masked_binary_1',
        name='consume_masked_binary',
        overload_index=1,
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='Alignment', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='alignment::detect', constraint=None),
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default='mask_layout::integral', constraint=None),
            CppTemplateParameter(name='Op', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='LeftRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='RightRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='MaskRange', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        parameters=(
            CppPublicParameter(name='op', type_spelling='Op&&', role='algorithm-parameter:op'),
            CppPublicParameter(name='left', type_spelling='const LeftRange&', role='algorithm-parameter:left'),
            CppPublicParameter(name='right', type_spelling='const RightRange&', role='algorithm-parameter:right'),
            CppPublicParameter(name='masks', type_spelling='const MaskRange&', role='algorithm-parameter:masks'),
        ),
        result_type='void',
    ),
)


_ALIAS_SPECS: tuple[CppAlgorithmAliasSpec, ...] = (
    CppAlgorithmAliasSpec(
        hole='algorithm_alias_vector_type',
        name='vector_type',
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        alias_target='typename detail::vector_for_parallelism<Parallelism, T>::type',
    ),
    CppAlgorithmAliasSpec(
        hole='algorithm_alias_integral_mask_type',
        name='integral_mask_type',
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        alias_target='typename detail::integral_mask_for<Parallelism, T>::type',
    ),
    CppAlgorithmAliasSpec(
        hole='algorithm_alias_native_mask_type',
        name='native_mask_type',
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        alias_target='typename detail::native_mask_for<Parallelism, T>::type',
    ),
    CppAlgorithmAliasSpec(
        hole='algorithm_alias_mask_storage_type',
        name='mask_storage_type',
        template_parameters=(
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        alias_target='typename detail::mask_for<MaskLayout, Parallelism, T>::type',
    ),
    CppAlgorithmAliasSpec(
        hole='algorithm_alias_byte_mask_type',
        name='byte_mask_type',
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        alias_target='mask_storage_type<mask_layout::bytes, Parallelism, T>',
    ),
    CppAlgorithmAliasSpec(
        hole='algorithm_alias_bit_mask_type',
        name='bit_mask_type',
        template_parameters=(
            CppTemplateParameter(name='Parallelism', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        alias_target='mask_storage_type<mask_layout::bits, Parallelism, T>',
    ),
    CppAlgorithmAliasSpec(
        hole='algorithm_alias_fixed_integral_mask_type',
        name='fixed_integral_mask_type',
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        alias_target='integral_mask_type<::tsl::dataparallel::fixed<ParallelN>, T>',
    ),
    CppAlgorithmAliasSpec(
        hole='algorithm_alias_fixed_native_mask_type',
        name='fixed_native_mask_type',
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        alias_target='native_mask_type<::tsl::dataparallel::fixed<ParallelN>, T>',
    ),
    CppAlgorithmAliasSpec(
        hole='algorithm_alias_fixed_mask_storage_type',
        name='fixed_mask_storage_type',
        template_parameters=(
            CppTemplateParameter(name='MaskLayout', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        alias_target='mask_storage_type<MaskLayout, ::tsl::dataparallel::fixed<ParallelN>, T>',
    ),
    CppAlgorithmAliasSpec(
        hole='algorithm_alias_fixed_byte_mask_type',
        name='fixed_byte_mask_type',
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        alias_target='fixed_mask_storage_type<mask_layout::bytes, ParallelN, T>',
    ),
    CppAlgorithmAliasSpec(
        hole='algorithm_alias_fixed_bit_mask_type',
        name='fixed_bit_mask_type',
        template_parameters=(
            CppTemplateParameter(name='ParallelN', kind=CppTemplateParameterKind.VALUE, type_spelling='std::size_t', default=None, constraint=None),
            CppTemplateParameter(name='T', kind=CppTemplateParameterKind.TYPE, type_spelling=None, default=None, constraint=None),
        ),
        alias_target='fixed_mask_storage_type<mask_layout::bits, ParallelN, T>',
    ),
)


def cpp_algorithm_public_declarations() -> tuple[CppPublicDeclaration, ...]:
    return (
        *(spec.declaration() for spec in _ALIAS_SPECS),
        *(spec.declaration() for spec in _FUNCTION_SPECS),
    )


def cpp_algorithm_declaration_holes() -> dict[str, str]:
    holes: dict[str, str] = {}
    for alias_spec in _ALIAS_SPECS:
        declaration = alias_spec.declaration()
        holes[alias_spec.hole] = declaration.render_head(multiline=True) + ';'
    for function_spec in _FUNCTION_SPECS:
        declaration = function_spec.declaration()
        hole = function_spec.hole or _cpp_algorithm_declaration_hole(
            declaration,
            function_spec.overload_index,
        )
        holes[hole] = declaration.render_head(multiline=True) + ' {'
    return holes


def _cpp_algorithm_declaration_hole(
    declaration: CppPublicDeclaration,
    overload_index: int,
) -> str:
    identity = f"{declaration.owner}::{declaration.name}#overload-{overload_index}"
    if declaration.identity != identity:
        raise ValueError(
            f"C++ algorithm declaration {declaration.identity!r} "
            "cannot derive its render hole"
        )
    return f"algorithm_declaration_{declaration.name}_{overload_index}"


def cpp_algorithm_checked_twin_identity(name: str, *, fixed: bool) -> str:
    form = ALGORITHM_FORMS_BY_NAME.get(name)
    if (
        form is None
        or not form.family.has_contract
        or form.mask_form is AlgorithmMaskForm.LAYOUT
        or (fixed and form.family.has_scaled_form)
    ):
        form_name = 'fixed' if fixed else 'policy'
        raise ValueError(
            f'checked C++ algorithm {name!r} has no explicit {form_name} twin'
        )
    overload_index = 1 if fixed or form.family.has_scaled_form else 3
    identity = f'tsl::algo::{name}#overload-{overload_index}'
    if identity not in {
        spec.declaration().identity for spec in _FUNCTION_SPECS
    }:
        form_name = 'fixed' if fixed else 'policy'
        raise ValueError(
            f'checked C++ algorithm {name!r} has no explicit {form_name} twin'
        )
    return identity


def cpp_algorithm_form_support(
    form: AlgorithmCallableForm,
) -> AlgorithmBackendFormSupport:
    """Join one target-neutral form to the exact C++ declaration inventory."""

    if form not in ALGORITHM_CALLABLE_FORMS:
        return AlgorithmBackendFormSupport(
            "cpp",
            form,
            False,
            "algorithm form is not registered in the shared surface",
        )
    if form.mask_form is AlgorithmMaskForm.LAYOUT:
        return AlgorithmBackendFormSupport(
            "cpp",
            form,
            False,
            "C++ projects mask layout as a template axis on the default form",
        )
    if not any(spec.name == form.name for spec in _FUNCTION_SPECS):
        return AlgorithmBackendFormSupport(
            "cpp",
            form,
            False,
            "algorithm form has no exact C++ declaration",
        )
    return AlgorithmBackendFormSupport("cpp", form, True)


__all__ = (
    'cpp_algorithm_checked_twin_identity',
    'cpp_algorithm_declaration_holes',
    'cpp_algorithm_form_support',
    'cpp_algorithm_public_declarations',
    'cpp_iteration_predicate_count_declarations',
)
