"""Exact stable declarations for the profile-local Rust algorithm facade.

The literal table is the authoritative backend input. Algorithm assets retain
only named declaration holes and implementation bodies; generation never
parses target text to recover signatures.
"""

from __future__ import annotations

from dataclasses import dataclass

from tslc.backend.algorithm_contracts import ALGORITHM_CONTRACTS
from tslc.backend.algorithm_surface import (
    ALGORITHM_CALLABLE_FORMS,
    ALGORITHM_CHECKED_TWINS,
    ALGORITHM_FORMS_BY_NAME,
    AlgorithmBackendFormSupport,
    AlgorithmArity,
    AlgorithmCallableForm,
    AlgorithmMaskForm,
    AlgorithmResultKind,
    AlgorithmSemanticFamily,
    AlgorithmShape,
)
from tslc.backend.public_declarations import (
    PublicDeclarationKind,
    PublicDeclarationStability,
)
from tslc.backend.rust_public_declarations import (
    RustGenericParameter,
    RustPublicDeclaration,
    RustPublicParameter,
    rust_const_parameter,
    rust_type_parameter,
)


_PROFILE_ALGORITHM_OWNER = 'crate::profile::algo'

_PROFILE_ALGORITHM_SUPPORT_REEXPORTS = (
    'mask_layout',
    'BinaryAggregateKernel',
    'BinaryConsumeKernel',
    'BinaryKernel',
    'BinaryPredicateKernel',
    'ChunkKernel',
    'IntegralMaskWord',
    'MaskedBinaryAggregateKernel',
    'MaskedBinaryConsumeKernel',
    'MaskedBinaryKernel',
    'MaskedUnaryAggregateKernel',
    'MaskedUnaryConsumeKernel',
    'MaskedUnaryKernel',
    'UnaryAggregateKernel',
    'UnaryConsumeKernel',
    'UnaryKernel',
    'UnaryPredicateKernel',
    'MaskLayout',
)

@dataclass(frozen=True, slots=True)
class RustAlgorithmDeclarationSpec:
    hole: str | None
    name: str
    unsafe: bool
    generic_parameters: tuple[RustGenericParameter, ...]
    parameters: tuple[RustPublicParameter, ...]
    where_predicates: tuple[str, ...]
    result_type: str | None

    def declaration(
        self,
        *,
        owner: str,
        reachability: tuple[str, ...],
    ) -> RustPublicDeclaration:
        identity = f"{owner}::{self.name}#algorithm"
        checked_twin = ALGORITHM_CHECKED_TWINS.get(self.name)
        checked_of = (
            f'{owner}::{checked_twin}#algorithm-alias'
            if checked_twin is not None
            else None
        )
        result_form = (
            'implicit-unit'
            if self.result_type is None
            else 'result'
            if checked_twin is not None
            else 'direct'
        )
        return RustPublicDeclaration(
            identity=identity, name=self.name, owner=owner,
            reachability=reachability, stability=PublicDeclarationStability.STABLE,
            kind=PublicDeclarationKind.FUNCTION, overload='profile-algorithm-function',
            visibility='pub', generic_parameters=self.generic_parameters,
            parameters=self.parameters, where_predicates=self.where_predicates,
            result_type=self.result_type, result_form=result_form, unsafe=self.unsafe,
            checked_of=checked_of, error_form='result' if checked_of is not None else None,
        )


def _rust_algorithm_parameter(name: str, type_spelling: str) -> RustPublicParameter:
    return RustPublicParameter(
        name=name,
        type_spelling=type_spelling,
        role=f"algorithm-parameter:{name}",
    )


def _rust_algorithm_generics(
    form: AlgorithmCallableForm,
    *,
    scaled: bool,
) -> tuple[RustGenericParameter, ...]:
    return (
        *((rust_const_parameter("SCALE", "u32"),) if scaled else ()),
        rust_type_parameter("Policy"),
        *((rust_type_parameter("Layout"),)
          if form.mask_form is AlgorithmMaskForm.LAYOUT else ()),
        rust_type_parameter("Op"),
        rust_type_parameter("T"),
    )


def _rust_algorithm_parameters(
    form: AlgorithmCallableForm,
    *,
    safe: bool,
) -> tuple[RustPublicParameter, ...]:
    parameters = [
        _rust_algorithm_parameter("policy", "Policy"),
        _rust_algorithm_parameter("op", "&mut Op"),
    ]
    if form.family.semantic_family is AlgorithmSemanticFamily.ITERATION:
        parameters.append(
            _rust_algorithm_parameter("data", "&[T]" if safe else "*const T")
        )
    elif form.family.arity is AlgorithmArity.UNARY:
        parameters.append(
            _rust_algorithm_parameter("input", "&[T]" if safe else "*const T")
        )
    else:
        parameters.extend(
            (
                _rust_algorithm_parameter(
                    "left", "&[T]" if safe else "*const T"
                ),
                _rust_algorithm_parameter(
                    "right", "&[T]" if safe else "*const T"
                ),
            )
        )

    if form.family.semantic_family is AlgorithmSemanticFamily.PREDICATE:
        if form.mask_form is AlgorithmMaskForm.LAYOUT:
            storage = (
                "<Layout as MaskLayout<Profile, "
                "<Policy as VectorFor<Profile, T>>::Vec,>>::Storage"
            )
        else:
            storage = (
                "<<Policy as VectorFor<Profile, T>>::Vec as "
                "SimdVector>::ImaskType"
            )
        parameters.append(
            _rust_algorithm_parameter(
                "masks",
                f"&mut [{storage}]" if safe else f"*mut {storage}",
            )
        )
    elif form.family.shape is AlgorithmShape.MASKED:
        storage = (
            "<Layout as MaskLayout<Profile, "
            "<Policy as VectorFor<Profile, T>>::Vec>>::Storage"
            if form.mask_form is AlgorithmMaskForm.LAYOUT
            else (
                "<<Policy as VectorFor<Profile, T>>::Vec as "
                "SimdVector>::ImaskType"
            )
        )
        parameters.append(
            _rust_algorithm_parameter(
                "masks",
                f"&[{storage}]" if safe else f"*const {storage}",
            )
        )
    elif form.family.shape is AlgorithmShape.SELECTED:
        parameters.append(
            _rust_algorithm_parameter(
                "indices", "&[usize]" if safe else "*const usize"
            )
        )

    if not safe:
        count_name = (
            "selected_count"
            if form.family.shape is AlgorithmShape.SELECTED
            else "count"
        )
        parameters.append(_rust_algorithm_parameter(count_name, "usize"))
    return tuple(parameters)


def _rust_algorithm_where_predicates(
    form: AlgorithmCallableForm,
    *,
    scaled: bool,
) -> tuple[str, ...]:
    predicates = [
        "Policy: VectorFor<Profile, T>",
        "<Policy as VectorFor<Profile, T>>::Vec: "
        "StaticSimdVector<BaseType = T>",
        "Simd<T, Scalar>: StaticSimdVector<BaseType = T>",
    ]
    if form.mask_form is AlgorithmMaskForm.LAYOUT:
        predicates.append(
            "Layout: MaskLayout<Profile, "
            "<Policy as VectorFor<Profile, T>>::Vec>"
        )
    if form.family.semantic_family is not AlgorithmSemanticFamily.ITERATION:
        if form.family.shape is AlgorithmShape.SELECTED:
            scale = "SCALE" if scaled else "0"
            profile = (
                "Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, "
                f"{scale}> + SelectedLoad<Simd<T, Scalar>, {scale}>"
            )
        else:
            profile = (
                "Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec> "
                "+ LoadStore<Simd<T, Scalar>>"
            )
        profile += (
            " + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec> "
            "+ IntegralMask<Simd<T, Scalar>>"
        )
        if (
            form.family.semantic_family is AlgorithmSemanticFamily.PREDICATE
            and form.mask_form is AlgorithmMaskForm.LAYOUT
        ):
            profile += (
                " + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>"
            )
        predicates.append(profile)

    kernel = (
        "ChunkKernel"
        if form.family.semantic_family is AlgorithmSemanticFamily.ITERATION
        else (
            "UnaryPredicateKernel"
            if form.family.arity is AlgorithmArity.UNARY
            else "BinaryPredicateKernel"
        )
    )
    predicates.append(
        f"Op: {kernel}<<Policy as VectorFor<Profile, T>>::Vec> "
        f"+ {kernel}<Simd<T, Scalar>>"
    )
    if form.family.semantic_family is not AlgorithmSemanticFamily.ITERATION:
        predicates.extend(
            (
                "<<Policy as VectorFor<Profile, T>>::Vec as "
                "SimdVector>::ImaskType: IntegralMaskWord",
                "<Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord",
            )
        )
    return tuple(predicates)


def _rust_algorithm_spec(
    form: AlgorithmCallableForm,
    name: str,
    *,
    safe: bool,
    scaled: bool = False,
) -> RustAlgorithmDeclarationSpec:
    checked = name == form.checked_name
    return RustAlgorithmDeclarationSpec(
        hole=None,
        name=name,
        unsafe=not safe,
        generic_parameters=_rust_algorithm_generics(form, scaled=scaled),
        parameters=_rust_algorithm_parameters(form, safe=safe),
        where_predicates=_rust_algorithm_where_predicates(form, scaled=scaled),
        result_type=(
            None
            if form.family.semantic_family is AlgorithmSemanticFamily.ITERATION
            else "Result<usize, crate::PreconditionError>"
            if checked
            else "usize"
        ),
    )


def _rust_iteration_form_specs(
    form: AlgorithmCallableForm,
) -> tuple[RustAlgorithmDeclarationSpec, ...]:
    if form.raw_name is None:
        raise ValueError("Rust iteration forms require a raw callable")
    return (
        _rust_algorithm_spec(form, form.name, safe=True),
        _rust_algorithm_spec(form, form.raw_name, safe=False),
    )


def _rust_iteration_specs() -> tuple[RustAlgorithmDeclarationSpec, ...]:
    form = next(
        form
        for form in ALGORITHM_CALLABLE_FORMS
        if form.family.semantic_family is AlgorithmSemanticFamily.ITERATION
    )
    return _rust_iteration_form_specs(form)


def _rust_predicate_count_form_specs(
    form: AlgorithmCallableForm,
) -> tuple[RustAlgorithmDeclarationSpec, ...]:
    primary_name = form.checked_name or form.name
    specs = [_rust_algorithm_spec(form, primary_name, safe=True)]
    if form.raw_name is not None:
        specs.append(_rust_algorithm_spec(form, form.raw_name, safe=False))
    if form.scaled_raw_name is not None:
        specs.append(
            _rust_algorithm_spec(
                form,
                form.scaled_raw_name,
                safe=False,
                scaled=True,
            )
        )
    return tuple(specs)


def _rust_predicate_count_specs() -> tuple[RustAlgorithmDeclarationSpec, ...]:
    forms = tuple(
        form
        for semantic_family in (
            AlgorithmSemanticFamily.PREDICATE,
            AlgorithmSemanticFamily.COUNT,
        )
        for shape, mask_form in (
            (
                (
                    (AlgorithmShape.PLAIN, AlgorithmMaskForm.DEFAULT),
                    (AlgorithmShape.PLAIN, AlgorithmMaskForm.LAYOUT),
                )
                if semantic_family is AlgorithmSemanticFamily.PREDICATE
                else (
                    (AlgorithmShape.PLAIN, AlgorithmMaskForm.DEFAULT),
                    (AlgorithmShape.MASKED, AlgorithmMaskForm.DEFAULT),
                    (AlgorithmShape.MASKED, AlgorithmMaskForm.LAYOUT),
                    (AlgorithmShape.SELECTED, AlgorithmMaskForm.DEFAULT),
                )
            )
        )
        for form in ALGORITHM_CALLABLE_FORMS
        if form.family.semantic_family is semantic_family
        and form.family.shape is shape
        and form.mask_form is mask_form
    )
    return tuple(
        spec
        for form in forms
        for spec in _rust_predicate_count_form_specs(form)
    )


def rust_iteration_predicate_count_function_declarations(
    form: AlgorithmCallableForm,
    reachability: tuple[str, ...],
) -> tuple[RustPublicDeclaration, ...]:
    """Project one first-slice form into exact Rust function declarations."""

    if form.family.semantic_family is AlgorithmSemanticFamily.ITERATION:
        if (
            form.family.shape is not AlgorithmShape.CHUNK_ITERATION
            or form.mask_form is not AlgorithmMaskForm.DEFAULT
        ):
            raise ValueError("Rust iteration forms require plain chunk iteration")
        specs = _rust_iteration_form_specs(form)
    elif form.family.semantic_family is AlgorithmSemanticFamily.PREDICATE:
        if form.family.shape is not AlgorithmShape.PLAIN:
            raise ValueError("Rust predicate forms require the plain shape")
        specs = _rust_predicate_count_form_specs(form)
    elif form.family.semantic_family is AlgorithmSemanticFamily.COUNT:
        if form.family.shape not in {
            AlgorithmShape.PLAIN,
            AlgorithmShape.MASKED,
            AlgorithmShape.SELECTED,
        } or (
            form.mask_form is AlgorithmMaskForm.LAYOUT
            and form.family.shape is not AlgorithmShape.MASKED
        ):
            raise ValueError("Rust count form has an unsupported shape")
        specs = _rust_predicate_count_form_specs(form)
    else:
        raise ValueError("algorithm form is outside the first Rust projection slice")
    return tuple(
        spec.declaration(
            owner=_PROFILE_ALGORITHM_OWNER,
            reachability=reachability,
        )
        for spec in specs
    )


def _rust_selection_parameters(
    form: AlgorithmCallableForm,
    *,
    safe: bool,
) -> tuple[RustPublicParameter, ...]:
    parameters = [
        _rust_algorithm_parameter("policy", "Policy"),
        _rust_algorithm_parameter("op", "&mut Op"),
    ]
    if form.family.arity is AlgorithmArity.UNARY:
        parameters.append(
            _rust_algorithm_parameter("input", "&[T]" if safe else "*const T")
        )
    else:
        parameters.extend(
            (
                _rust_algorithm_parameter(
                    "left", "&[T]" if safe else "*const T"
                ),
                _rust_algorithm_parameter(
                    "right", "&[T]" if safe else "*const T"
                ),
            )
        )

    if form.family.shape in {
        AlgorithmShape.MASKED,
        AlgorithmShape.MASKED_INDICES,
    }:
        storage = (
            "<Layout as MaskLayout<Profile, "
            "<Policy as VectorFor<Profile, T>>::Vec>>::Storage"
            if form.mask_form is AlgorithmMaskForm.LAYOUT
            else (
                "<<Policy as VectorFor<Profile, T>>::Vec as "
                "SimdVector>::ImaskType"
            )
        )
        parameters.append(
            _rust_algorithm_parameter(
                "masks", f"&[{storage}]" if safe else f"*const {storage}"
            )
        )

    if form.family.shape in {
        AlgorithmShape.PLAIN,
        AlgorithmShape.MASKED,
    }:
        parameters.append(
            _rust_algorithm_parameter(
                "output", "&mut [T]" if safe else "*mut T"
            )
        )
    elif form.family.shape in {
        AlgorithmShape.INDICES,
        AlgorithmShape.MASKED_INDICES,
    }:
        parameters.append(
            _rust_algorithm_parameter(
                "indices", "&mut [usize]" if safe else "*mut usize"
            )
        )
    else:
        parameters.extend(
            (
                _rust_algorithm_parameter(
                    "input_indices",
                    "&[usize]" if safe else "*const usize",
                ),
                _rust_algorithm_parameter(
                    "output_indices",
                    "&mut [usize]" if safe else "*mut usize",
                ),
            )
        )

    if not safe:
        count_name = (
            "selected_count"
            if form.family.shape is AlgorithmShape.SELECTED_INDICES
            else "count"
        )
        parameters.append(_rust_algorithm_parameter(count_name, "usize"))
    return tuple(parameters)


def _rust_selection_where_predicates(
    form: AlgorithmCallableForm,
    *,
    scaled: bool,
) -> tuple[str, ...]:
    predicates = [
        "Policy: VectorFor<Profile, T>",
        "<Policy as VectorFor<Profile, T>>::Vec: "
        "StaticSimdVector<BaseType = T>",
        "Simd<T, Scalar>: StaticSimdVector<BaseType = T>",
    ]
    if form.mask_form is AlgorithmMaskForm.LAYOUT:
        predicates.append(
            "Layout: MaskLayout<Profile, "
            "<Policy as VectorFor<Profile, T>>::Vec>"
        )

    if form.family.shape is AlgorithmShape.SELECTED_INDICES:
        scale = "SCALE" if scaled else "0"
        profile = (
            "Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, "
            f"{scale}> + SelectedLoad<Simd<T, Scalar>, {scale}>"
            " + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>"
            " + IntegralMask<Simd<T, Scalar>>"
        )
    elif form.family.shape in {
        AlgorithmShape.PLAIN,
        AlgorithmShape.MASKED,
    }:
        profile = (
            "Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec> "
            "+ LoadStore<Simd<T, Scalar>>"
            " + CompressStore<<Policy as VectorFor<Profile, T>>::Vec>"
        )
        if form.mask_form is AlgorithmMaskForm.DEFAULT:
            profile += (
                " + MaskPopulationCount<<Policy as VectorFor<Profile, T>>::Vec>"
            )
        if form.family.shape is AlgorithmShape.MASKED:
            profile += (
                " + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>"
                " + IntegralMask<Simd<T, Scalar>>"
                " + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>"
            )
        else:
            profile += " + IntegralMask<Simd<T, Scalar>>"
    else:
        profile = (
            "Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec> "
            "+ LoadStore<Simd<T, Scalar>>"
            " + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>"
            " + IntegralMask<Simd<T, Scalar>>"
        )
    predicates.append(profile)

    kernel = (
        "UnaryPredicateKernel"
        if form.family.arity is AlgorithmArity.UNARY
        else "BinaryPredicateKernel"
    )
    predicates.append(
        f"Op: {kernel}<<Policy as VectorFor<Profile, T>>::Vec> "
        f"+ {kernel}<Simd<T, Scalar>>"
    )
    if form.family.shape in {
        AlgorithmShape.PLAIN,
        AlgorithmShape.MASKED,
    }:
        predicates.extend(
            (
                "<<Policy as VectorFor<Profile, T>>::Vec as "
                "SimdVector>::RegisterType: Copy",
                "<<Policy as VectorFor<Profile, T>>::Vec as "
                "SimdVector>::MaskType: Copy",
                "<Simd<T, Scalar> as SimdVector>::RegisterType: Copy",
            )
        )
    predicates.extend(
        (
            "<<Policy as VectorFor<Profile, T>>::Vec as "
            "SimdVector>::ImaskType: IntegralMaskWord",
            "<Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord",
        )
    )
    return tuple(predicates)


def _rust_selection_form_specs(
    form: AlgorithmCallableForm,
) -> tuple[RustAlgorithmDeclarationSpec, ...]:
    if form.checked_name is None or form.raw_name is None:
        raise ValueError("Rust selection forms require checked and raw callables")
    specs = [
        RustAlgorithmDeclarationSpec(
            hole=None,
            name=form.checked_name,
            unsafe=False,
            generic_parameters=_rust_algorithm_generics(form, scaled=False),
            parameters=_rust_selection_parameters(form, safe=True),
            where_predicates=_rust_selection_where_predicates(
                form,
                scaled=False,
            ),
            result_type="Result<usize, crate::PreconditionError>",
        ),
        RustAlgorithmDeclarationSpec(
            hole=None,
            name=form.raw_name,
            unsafe=True,
            generic_parameters=_rust_algorithm_generics(form, scaled=False),
            parameters=_rust_selection_parameters(form, safe=False),
            where_predicates=_rust_selection_where_predicates(
                form,
                scaled=False,
            ),
            result_type="usize",
        ),
    ]
    if form.scaled_raw_name is not None:
        specs.append(
            RustAlgorithmDeclarationSpec(
                hole=None,
                name=form.scaled_raw_name,
                unsafe=True,
                generic_parameters=_rust_algorithm_generics(form, scaled=True),
                parameters=_rust_selection_parameters(form, safe=False),
                where_predicates=_rust_selection_where_predicates(
                    form,
                    scaled=True,
                ),
                result_type="usize",
            )
        )
    return tuple(specs)


def _rust_selection_specs() -> tuple[RustAlgorithmDeclarationSpec, ...]:
    forms = tuple(
        form
        for shape, mask_form in (
            (AlgorithmShape.PLAIN, AlgorithmMaskForm.DEFAULT),
            (AlgorithmShape.MASKED, AlgorithmMaskForm.DEFAULT),
            (AlgorithmShape.MASKED, AlgorithmMaskForm.LAYOUT),
            (AlgorithmShape.INDICES, AlgorithmMaskForm.DEFAULT),
            (AlgorithmShape.MASKED_INDICES, AlgorithmMaskForm.DEFAULT),
            (AlgorithmShape.MASKED_INDICES, AlgorithmMaskForm.LAYOUT),
            (AlgorithmShape.SELECTED_INDICES, AlgorithmMaskForm.DEFAULT),
        )
        for form in ALGORITHM_CALLABLE_FORMS
        if form.family.semantic_family is AlgorithmSemanticFamily.SELECT
        and form.family.shape is shape
        and form.mask_form is mask_form
    )
    return tuple(
        spec for form in forms for spec in _rust_selection_form_specs(form)
    )


def rust_selection_function_declarations(
    form: AlgorithmCallableForm,
    reachability: tuple[str, ...],
) -> tuple[RustPublicDeclaration, ...]:
    """Project one selection form into exact Rust function declarations."""

    if form.family.semantic_family is not AlgorithmSemanticFamily.SELECT:
        raise ValueError("form is not a Rust selection form")
    if form.family.shape not in {
        AlgorithmShape.PLAIN,
        AlgorithmShape.MASKED,
        AlgorithmShape.INDICES,
        AlgorithmShape.MASKED_INDICES,
        AlgorithmShape.SELECTED_INDICES,
    } or (
        form.mask_form is AlgorithmMaskForm.LAYOUT
        and form.family.shape not in {
            AlgorithmShape.MASKED,
            AlgorithmShape.MASKED_INDICES,
        }
    ):
        raise ValueError("Rust selection form has an unsupported shape")
    return tuple(
        spec.declaration(
            owner=_PROFILE_ALGORITHM_OWNER,
            reachability=reachability,
        )
        for spec in _rust_selection_form_specs(form)
    )


def _rust_transform_parameters(
    form: AlgorithmCallableForm,
    *,
    safe: bool,
) -> tuple[RustPublicParameter, ...]:
    parameters = [
        _rust_algorithm_parameter("policy", "Policy"),
        _rust_algorithm_parameter("op", "&mut Op"),
    ]
    if form.family.arity is AlgorithmArity.UNARY:
        parameters.append(
            _rust_algorithm_parameter("input", "&[T]" if safe else "*const T")
        )
    else:
        parameters.extend(
            (
                _rust_algorithm_parameter(
                    "left", "&[T]" if safe else "*const T"
                ),
                _rust_algorithm_parameter(
                    "right", "&[T]" if safe else "*const T"
                ),
            )
        )
    if form.family.shape in {AlgorithmShape.WHERE, AlgorithmShape.MASKED}:
        storage = (
            "<Layout as MaskLayout<Profile, "
            "<Policy as VectorFor<Profile, T>>::Vec,>>::Storage"
            if form.mask_form is AlgorithmMaskForm.LAYOUT
            else (
                "<<Policy as VectorFor<Profile, T>>::Vec as "
                "SimdVector>::ImaskType"
            )
        )
        parameters.append(
            _rust_algorithm_parameter(
                "masks", f"&[{storage}]" if safe else f"*const {storage}"
            )
        )
    elif form.family.shape is AlgorithmShape.SELECTED:
        parameters.append(
            _rust_algorithm_parameter(
                "indices", "&[usize]" if safe else "*const usize"
            )
        )
    parameters.append(
        _rust_algorithm_parameter(
            "output", "&mut [T]" if safe else "*mut T"
        )
    )
    if not safe:
        count_name = (
            "selected_count"
            if form.family.shape is AlgorithmShape.SELECTED
            else "count"
        )
        parameters.append(_rust_algorithm_parameter(count_name, "usize"))
    return tuple(parameters)


def _rust_transform_where_predicates(
    form: AlgorithmCallableForm,
    *,
    scaled: bool,
) -> tuple[str, ...]:
    predicates = [
        "Policy: VectorFor<Profile, T>",
        "<Policy as VectorFor<Profile, T>>::Vec: "
        "StaticSimdVector<BaseType = T>",
        "Simd<T, Scalar>: StaticSimdVector<BaseType = T>",
    ]
    if form.mask_form is AlgorithmMaskForm.LAYOUT:
        predicates.append(
            "Layout: MaskLayout<Profile, "
            "<Policy as VectorFor<Profile, T>>::Vec>"
        )

    if form.family.shape is AlgorithmShape.SELECTED:
        scale = "SCALE" if scaled else "0"
        profile = (
            "Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, "
            f"{scale}> + SelectedLoad<Simd<T, Scalar>, {scale}>"
            " + LoadStore<<Policy as VectorFor<Profile, T>>::Vec>"
            " + LoadStore<Simd<T, Scalar>>"
        )
    else:
        profile = (
            "Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec> "
            "+ LoadStore<Simd<T, Scalar>>"
        )
        if form.family.shape in {AlgorithmShape.WHERE, AlgorithmShape.MASKED}:
            if form.mask_form is AlgorithmMaskForm.DEFAULT:
                profile += (
                    " + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>"
                )
            profile += " + MaskFromIntegral<Simd<T, Scalar>>"
            if form.family.shape is AlgorithmShape.WHERE:
                profile += (
                    " + MaskedStore<<Policy as VectorFor<Profile, T>>::Vec>"
                )
    predicates.append(profile)

    masked = form.family.shape in {AlgorithmShape.WHERE, AlgorithmShape.MASKED}
    kernel_prefix = "Masked" if masked else ""
    arity = "Unary" if form.family.arity is AlgorithmArity.UNARY else "Binary"
    kernel = f"{kernel_prefix}{arity}Kernel"
    predicates.append(
        f"Op: {kernel}<<Policy as VectorFor<Profile, T>>::Vec> "
        f"+ {kernel}<Simd<T, Scalar>>"
    )
    if form.family.shape is AlgorithmShape.WHERE:
        predicates.append(
            "<<Policy as VectorFor<Profile, T>>::Vec as "
            "SimdVector>::MaskType: Copy"
        )
    if masked:
        predicates.extend(
            (
                "<<Policy as VectorFor<Profile, T>>::Vec as "
                "SimdVector>::ImaskType: IntegralMaskWord",
                "<Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord",
            )
        )
    return tuple(predicates)


def _rust_transform_form_specs(
    form: AlgorithmCallableForm,
) -> tuple[RustAlgorithmDeclarationSpec, ...]:
    if form.checked_name is None or form.raw_name is None:
        raise ValueError("Rust transform forms require checked and raw callables")
    specs = [
        RustAlgorithmDeclarationSpec(
            hole=None,
            name=form.checked_name,
            unsafe=False,
            generic_parameters=_rust_algorithm_generics(form, scaled=False),
            parameters=_rust_transform_parameters(form, safe=True),
            where_predicates=_rust_transform_where_predicates(
                form,
                scaled=False,
            ),
            result_type="Result<(), crate::PreconditionError>",
        ),
        RustAlgorithmDeclarationSpec(
            hole=None,
            name=form.raw_name,
            unsafe=True,
            generic_parameters=_rust_algorithm_generics(form, scaled=False),
            parameters=_rust_transform_parameters(form, safe=False),
            where_predicates=_rust_transform_where_predicates(
                form,
                scaled=False,
            ),
            result_type=None,
        ),
    ]
    if form.scaled_raw_name is not None:
        specs.append(
            RustAlgorithmDeclarationSpec(
                hole=None,
                name=form.scaled_raw_name,
                unsafe=True,
                generic_parameters=_rust_algorithm_generics(form, scaled=True),
                parameters=_rust_transform_parameters(form, safe=False),
                where_predicates=_rust_transform_where_predicates(
                    form,
                    scaled=True,
                ),
                result_type=None,
            )
        )
    return tuple(specs)


def _rust_transform_specs(
    shape: AlgorithmShape,
) -> tuple[RustAlgorithmDeclarationSpec, ...]:
    if shape is AlgorithmShape.WHERE:
        forms = tuple(
            form
            for form in ALGORITHM_CALLABLE_FORMS
            if form.family.semantic_family is AlgorithmSemanticFamily.TRANSFORM
            and form.family.shape is shape
        )
    else:
        forms = tuple(
            form
            for mask_form in (
                AlgorithmMaskForm.DEFAULT,
                AlgorithmMaskForm.LAYOUT,
            )
            for form in ALGORITHM_CALLABLE_FORMS
            if form.family.semantic_family is AlgorithmSemanticFamily.TRANSFORM
            and form.family.shape is shape
            and form.mask_form is mask_form
        )
    return tuple(
        spec for form in forms for spec in _rust_transform_form_specs(form)
    )


def rust_transform_function_declarations(
    form: AlgorithmCallableForm,
    reachability: tuple[str, ...],
) -> tuple[RustPublicDeclaration, ...]:
    """Project one transform form into exact Rust function declarations."""

    if form.family.semantic_family is not AlgorithmSemanticFamily.TRANSFORM:
        raise ValueError("form is not a Rust transform form")
    if form.family.shape not in {
        AlgorithmShape.PLAIN,
        AlgorithmShape.WHERE,
        AlgorithmShape.MASKED,
        AlgorithmShape.SELECTED,
    } or (
        form.mask_form is AlgorithmMaskForm.LAYOUT
        and form.family.shape not in {AlgorithmShape.WHERE, AlgorithmShape.MASKED}
    ):
        raise ValueError("Rust transform form has an unsupported shape")
    return tuple(
        spec.declaration(
            owner=_PROFILE_ALGORITHM_OWNER,
            reachability=reachability,
        )
        for spec in _rust_transform_form_specs(form)
    )


def _rust_consume_aggregate_parameters(
    form: AlgorithmCallableForm,
    *,
    safe: bool,
) -> tuple[RustPublicParameter, ...]:
    parameters = [
        _rust_algorithm_parameter("policy", "Policy"),
        _rust_algorithm_parameter("op", "&mut Op"),
    ]
    if form.family.arity is AlgorithmArity.UNARY:
        parameters.append(
            _rust_algorithm_parameter("input", "&[T]" if safe else "*const T")
        )
    else:
        parameters.extend(
            (
                _rust_algorithm_parameter(
                    "left", "&[T]" if safe else "*const T"
                ),
                _rust_algorithm_parameter(
                    "right", "&[T]" if safe else "*const T"
                ),
            )
        )
    if form.family.shape is AlgorithmShape.MASKED:
        storage = (
            "<<Policy as VectorFor<Profile, T>>::Vec as "
            "SimdVector>::ImaskType"
        )
        parameters.append(
            _rust_algorithm_parameter(
                "masks", f"&[{storage}]" if safe else f"*const {storage}"
            )
        )
    elif form.family.shape is AlgorithmShape.SELECTED:
        parameters.append(
            _rust_algorithm_parameter(
                "indices", "&[usize]" if safe else "*const usize"
            )
        )
    if not safe:
        count_name = (
            "selected_count"
            if form.family.shape is AlgorithmShape.SELECTED
            else "count"
        )
        parameters.append(_rust_algorithm_parameter(count_name, "usize"))
    return tuple(parameters)


def _rust_consume_aggregate_kernel(form: AlgorithmCallableForm) -> str:
    mask_prefix = "Masked" if form.family.shape is AlgorithmShape.MASKED else ""
    arity = "Unary" if form.family.arity is AlgorithmArity.UNARY else "Binary"
    operation = (
        "Consume"
        if form.family.semantic_family is AlgorithmSemanticFamily.CONSUME
        else "Aggregate"
    )
    return f"{mask_prefix}{arity}{operation}Kernel"


def _rust_consume_aggregate_where_predicates(
    form: AlgorithmCallableForm,
    *,
    scaled: bool,
) -> tuple[str, ...]:
    predicates = [
        "Policy: VectorFor<Profile, T>",
        "<Policy as VectorFor<Profile, T>>::Vec: "
        "StaticSimdVector<BaseType = T>",
        "Simd<T, Scalar>: StaticSimdVector<BaseType = T>",
    ]
    if form.family.shape is AlgorithmShape.SELECTED:
        scale = "SCALE" if scaled else "0"
        predicates.append(
            "Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, "
            f"{scale}> + SelectedLoad<Simd<T, Scalar>, {scale}>"
        )
    else:
        profile = (
            "Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec> "
            "+ LoadStore<Simd<T, Scalar>>"
        )
        if form.family.shape is AlgorithmShape.MASKED:
            profile += (
                " + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>"
                " + MaskFromIntegral<Simd<T, Scalar>>"
            )
        predicates.append(profile)
    kernel = _rust_consume_aggregate_kernel(form)
    predicates.append(
        f"Op: {kernel}<<Policy as VectorFor<Profile, T>>::Vec> "
        f"+ {kernel}<Simd<T, Scalar>>"
    )
    if form.family.shape is AlgorithmShape.MASKED:
        predicates.extend(
            (
                "<<Policy as VectorFor<Profile, T>>::Vec as "
                "SimdVector>::ImaskType: IntegralMaskWord",
                "<Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord",
            )
        )
    return tuple(predicates)


def _rust_consume_aggregate_result(
    form: AlgorithmCallableForm,
    *,
    checked: bool,
) -> str | None:
    if form.family.result_kind is AlgorithmResultKind.VOID:
        return "Result<(), crate::PreconditionError>" if checked else None
    if form.family.result_kind is not AlgorithmResultKind.VALUE:
        raise ValueError("consume/aggregate form has an unsupported result kind")
    kernel = _rust_consume_aggregate_kernel(form)
    output = (
        f"<Op as {kernel}<<Policy as VectorFor<Profile, T>>::Vec>>::Output"
    )
    return (
        f"Result<{output}, crate::PreconditionError>" if checked else output
    )


def _rust_consume_aggregate_form_specs(
    form: AlgorithmCallableForm,
) -> tuple[RustAlgorithmDeclarationSpec, ...]:
    if form.raw_name is None:
        raise ValueError("Rust consume/aggregate forms require a raw callable")
    primary_name = form.checked_name or form.name
    checked = form.checked_name is not None
    specs = [
        RustAlgorithmDeclarationSpec(
            hole=None,
            name=primary_name,
            unsafe=False,
            generic_parameters=_rust_algorithm_generics(form, scaled=False),
            parameters=_rust_consume_aggregate_parameters(form, safe=True),
            where_predicates=_rust_consume_aggregate_where_predicates(
                form,
                scaled=False,
            ),
            result_type=_rust_consume_aggregate_result(
                form,
                checked=checked,
            ),
        ),
        RustAlgorithmDeclarationSpec(
            hole=None,
            name=form.raw_name,
            unsafe=True,
            generic_parameters=_rust_algorithm_generics(form, scaled=False),
            parameters=_rust_consume_aggregate_parameters(form, safe=False),
            where_predicates=_rust_consume_aggregate_where_predicates(
                form,
                scaled=False,
            ),
            result_type=_rust_consume_aggregate_result(form, checked=False),
        ),
    ]
    if form.scaled_raw_name is not None:
        specs.append(
            RustAlgorithmDeclarationSpec(
                hole=None,
                name=form.scaled_raw_name,
                unsafe=True,
                generic_parameters=_rust_algorithm_generics(form, scaled=True),
                parameters=_rust_consume_aggregate_parameters(form, safe=False),
                where_predicates=_rust_consume_aggregate_where_predicates(
                    form,
                    scaled=True,
                ),
                result_type=_rust_consume_aggregate_result(
                    form,
                    checked=False,
                ),
            )
        )
    return tuple(specs)


def _rust_consume_aggregate_specs(
    semantic_family: AlgorithmSemanticFamily,
    *,
    selected: bool,
) -> tuple[RustAlgorithmDeclarationSpec, ...]:
    return tuple(
        spec
        for form in ALGORITHM_CALLABLE_FORMS
        if form.family.semantic_family is semantic_family
        and (form.family.shape is AlgorithmShape.SELECTED) is selected
        for spec in _rust_consume_aggregate_form_specs(form)
    )


def rust_consume_aggregate_function_declarations(
    form: AlgorithmCallableForm,
    reachability: tuple[str, ...],
) -> tuple[RustPublicDeclaration, ...]:
    """Project one consume/aggregate form into exact Rust declarations."""

    if form.family.semantic_family not in {
        AlgorithmSemanticFamily.CONSUME,
        AlgorithmSemanticFamily.AGGREGATE,
    }:
        raise ValueError("form is not a Rust consume/aggregate form")
    if (
        form.family.shape
        not in {
            AlgorithmShape.PLAIN,
            AlgorithmShape.MASKED,
            AlgorithmShape.SELECTED,
        }
        or form.mask_form is not AlgorithmMaskForm.DEFAULT
    ):
        raise ValueError("Rust consume/aggregate form has an unsupported shape")
    return tuple(
        spec.declaration(
            owner=_PROFILE_ALGORITHM_OWNER,
            reachability=reachability,
        )
        for spec in _rust_consume_aggregate_form_specs(form)
    )


_SPECS = (
    *_rust_transform_specs(AlgorithmShape.PLAIN),
    RustAlgorithmDeclarationSpec(
        hole='profile_algorithm_declaration_integral_mask_chunk_count',
        name='integral_mask_chunk_count',
        unsafe=False,
        generic_parameters=(
            RustGenericParameter(name='Policy', kind='type', declaration='Policy', bounds=(), type_spelling=None, default=None),
            RustGenericParameter(name='T', kind='type', declaration='T', bounds=(), type_spelling=None, default=None),
        ),
        parameters=(
            RustPublicParameter(name='policy', type_spelling='Policy', role='algorithm-parameter:policy'),
            RustPublicParameter(name='count', type_spelling='usize', role='algorithm-parameter:count'),
        ),
        where_predicates=(
            'Policy: VectorFor<Profile, T>',
            '<Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>',
            '<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord',
        ),
        result_type='usize',
    ),
    RustAlgorithmDeclarationSpec(
        hole='profile_algorithm_declaration_mask_chunk_count',
        name='mask_chunk_count',
        unsafe=False,
        generic_parameters=(
            RustGenericParameter(name='Policy', kind='type', declaration='Policy', bounds=(), type_spelling=None, default=None),
            RustGenericParameter(name='Layout', kind='type', declaration='Layout', bounds=(), type_spelling=None, default=None),
            RustGenericParameter(name='T', kind='type', declaration='T', bounds=(), type_spelling=None, default=None),
        ),
        parameters=(
            RustPublicParameter(name='policy', type_spelling='Policy', role='algorithm-parameter:policy'),
            RustPublicParameter(name='count', type_spelling='usize', role='algorithm-parameter:count'),
        ),
        where_predicates=(
            'Policy: VectorFor<Profile, T>',
            '<Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>',
            'Layout: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>',
            '<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord',
        ),
        result_type='usize',
    ),
    RustAlgorithmDeclarationSpec(
        hole='profile_algorithm_declaration_native_mask_chunk_count',
        name='native_mask_chunk_count',
        unsafe=False,
        generic_parameters=(
            RustGenericParameter(name='Policy', kind='type', declaration='Policy', bounds=(), type_spelling=None, default=None),
            RustGenericParameter(name='T', kind='type', declaration='T', bounds=(), type_spelling=None, default=None),
        ),
        parameters=(
            RustPublicParameter(name='policy', type_spelling='Policy', role='algorithm-parameter:policy'),
            RustPublicParameter(name='count', type_spelling='usize', role='algorithm-parameter:count'),
        ),
        where_predicates=(
            'Policy: VectorFor<Profile, T>',
            '<Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>',
            'mask_layout::Native: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>',
            '<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord',
        ),
        result_type='usize',
    ),
    RustAlgorithmDeclarationSpec(
        hole='profile_algorithm_declaration_byte_mask_count',
        name='byte_mask_count',
        unsafe=False,
        generic_parameters=(
            RustGenericParameter(name='Policy', kind='type', declaration='Policy', bounds=(), type_spelling=None, default=None),
            RustGenericParameter(name='T', kind='type', declaration='T', bounds=(), type_spelling=None, default=None),
        ),
        parameters=(
            RustPublicParameter(name='policy', type_spelling='Policy', role='algorithm-parameter:policy'),
            RustPublicParameter(name='count', type_spelling='usize', role='algorithm-parameter:count'),
        ),
        where_predicates=(
            'Policy: VectorFor<Profile, T>',
            '<Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>',
            'mask_layout::Bytes: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>',
            '<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord',
        ),
        result_type='usize',
    ),
    RustAlgorithmDeclarationSpec(
        hole='profile_algorithm_declaration_bit_mask_count',
        name='bit_mask_count',
        unsafe=False,
        generic_parameters=(
            RustGenericParameter(name='Policy', kind='type', declaration='Policy', bounds=(), type_spelling=None, default=None),
            RustGenericParameter(name='T', kind='type', declaration='T', bounds=(), type_spelling=None, default=None),
        ),
        parameters=(
            RustPublicParameter(name='policy', type_spelling='Policy', role='algorithm-parameter:policy'),
            RustPublicParameter(name='count', type_spelling='usize', role='algorithm-parameter:count'),
        ),
        where_predicates=(
            'Policy: VectorFor<Profile, T>',
            '<Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>',
            'mask_layout::Bits: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>',
            '<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord',
        ),
        result_type='usize',
    ),
    *_rust_predicate_count_specs(),
    *_rust_selection_specs(),
    *_rust_transform_specs(AlgorithmShape.SELECTED),
    *_rust_consume_aggregate_specs(AlgorithmSemanticFamily.CONSUME, selected=True),
    *_rust_consume_aggregate_specs(AlgorithmSemanticFamily.AGGREGATE, selected=True),
    *_rust_transform_specs(AlgorithmShape.WHERE),
    *_rust_transform_specs(AlgorithmShape.MASKED),
    *_rust_consume_aggregate_specs(AlgorithmSemanticFamily.CONSUME, selected=False),
    *_rust_consume_aggregate_specs(AlgorithmSemanticFamily.AGGREGATE, selected=False),
    *_rust_iteration_specs(),
)


def rust_profile_algorithm_public_declarations(
    reachability: tuple[str, ...],
    *,
    admitted_form_names: frozenset[str] | None = None,
) -> tuple[RustPublicDeclaration, ...]:
    admitted_names = _admitted_algorithm_names(admitted_form_names)
    functions = tuple(
        spec.declaration(
            owner=_PROFILE_ALGORITHM_OWNER,
            reachability=reachability,
        )
        for spec in _SPECS
        if admitted_names is None or spec.name in admitted_names
    )
    aliases = tuple(
        _algorithm_alias(
            name,
            owner=_PROFILE_ALGORITHM_OWNER,
            reachability=reachability,
        )
        for name in sorted(ALGORITHM_CONTRACTS)
        if admitted_form_names is None or name in admitted_form_names
    )
    return (*functions, *aliases)


def _admitted_algorithm_names(
    form_names: frozenset[str] | None,
) -> frozenset[str] | None:
    if form_names is None:
        return None
    forms = tuple(ALGORITHM_FORMS_BY_NAME[name] for name in sorted(form_names))
    return frozenset(
        name
        for form in forms
        for name in (
            form.name,
            form.raw_name,
            form.checked_name,
            form.scaled_raw_name,
            form.scaled_checked_name,
        )
        if name is not None
    )


def rust_algorithm_form_support(
    form: AlgorithmCallableForm,
) -> AlgorithmBackendFormSupport:
    """Join one target-neutral form to the exact Rust declaration inventory."""

    if form not in ALGORITHM_CALLABLE_FORMS:
        return AlgorithmBackendFormSupport(
            "rust",
            form,
            False,
            "algorithm form is not registered in the shared surface",
        )
    projected_names = {spec.name for spec in _SPECS} | set(ALGORITHM_CONTRACTS)
    if form.name not in projected_names:
        return AlgorithmBackendFormSupport(
            "rust",
            form,
            False,
            "algorithm form has no exact Rust declaration",
        )
    return AlgorithmBackendFormSupport("rust", form, True)


def rust_profile_algorithm_module_declaration(
    reachability: tuple[str, ...],
) -> RustPublicDeclaration:
    """Own the stable module that makes profile algorithms reachable."""

    return RustPublicDeclaration(
        identity=f'{_PROFILE_ALGORITHM_OWNER}#module',
        name='algo',
        owner='crate::profile',
        reachability=reachability,
        stability=PublicDeclarationStability.STABLE,
        kind=PublicDeclarationKind.MODULE,
        overload='profile-algorithm-facade',
        visibility='pub',
    )


def rust_profile_algorithm_support_reexports(
    reachability: tuple[str, ...],
) -> tuple[RustPublicDeclaration, ...]:
    """Classify and render profile-local exports of advanced kernel traits."""

    return tuple(
        RustPublicDeclaration(
            identity=f'{_PROFILE_ALGORITHM_OWNER}::{name}#support-reexport',
            name=name,
            owner=_PROFILE_ALGORITHM_OWNER,
            reachability=reachability,
            stability=PublicDeclarationStability.UNSTABLE,
            kind=PublicDeclarationKind.REEXPORT,
            overload='advanced-algorithm-support-reexport',
            visibility='pub',
            reexport_target=f'crate::tsl_algorithm::{name}',
            reexport_of='crate::tsl_algorithm#module',
        )
        for name in _PROFILE_ALGORITHM_SUPPORT_REEXPORTS
    )


def rust_profile_algorithm_declaration_holes(
    admitted_form_names: frozenset[str] | None = None,
) -> dict[str, str]:
    reachability = ('profile', 'algo')
    admitted_names = _admitted_algorithm_names(admitted_form_names)
    holes: dict[str, str] = {}
    for spec in _SPECS:
        declaration = spec.declaration(
            owner=_PROFILE_ALGORITHM_OWNER,
            reachability=reachability,
        )
        hole = spec.hole or _rust_algorithm_declaration_hole(declaration)
        head = declaration.render_definition_head()
        if admitted_names is not None and spec.name not in admitted_names:
            head = head.replace('pub ', 'pub(crate) ', 1)
        holes[hole] = _indent(head, 4)
    return holes


def rust_profile_algorithm_aliases(
    reachability: tuple[str, ...],
    *,
    owner: str,
    indent: int = 0,
    admitted_form_names: frozenset[str] | None = None,
) -> str:
    return '\n'.join(
        _indent(
            '/// Unchecked raw-pointer form. The caller must uphold the '
            'documented safety contract.\n'
            '#[allow(unused_imports)]\n'
            + _algorithm_alias(
                name,
                owner=owner,
                reachability=reachability,
            ).render_head()
            + ';',
            indent,
        )
        for name in sorted(ALGORITHM_CONTRACTS)
        if admitted_form_names is None or name in admitted_form_names
    )


def _algorithm_alias(
    name: str,
    *,
    owner: str,
    reachability: tuple[str, ...],
) -> RustPublicDeclaration:
    return RustPublicDeclaration(
        identity=f'{owner}::{name}#algorithm-alias',
        name=name,
        owner=owner,
        reachability=reachability,
        stability=PublicDeclarationStability.STABLE,
        kind=PublicDeclarationKind.REEXPORT,
        overload='unchecked-algorithm-alias',
        visibility='pub',
        attributes=('#[allow(unused_imports)]',),
        reexport_target=f'self::{name}_raw',
        reexport_of=f'{owner}::{name}_raw#algorithm',
    )


def _rust_algorithm_declaration_hole(
    declaration: RustPublicDeclaration,
) -> str:
    identity = f"{declaration.owner}::{declaration.name}#algorithm"
    if declaration.identity != identity:
        raise ValueError(
            f"Rust algorithm declaration {declaration.identity!r} "
            "cannot derive its render hole"
        )
    return f"profile_algorithm_declaration_{declaration.name}"


def _indent(text: str, spaces: int) -> str:
    prefix = ' ' * spaces
    return '\n'.join(
        f'{prefix}{line}' if line else '' for line in text.splitlines()
    )


__all__ = (
    'rust_algorithm_form_support',
    'rust_consume_aggregate_function_declarations',
    'rust_iteration_predicate_count_function_declarations',
    'rust_profile_algorithm_aliases',
    'rust_profile_algorithm_declaration_holes',
    'rust_profile_algorithm_module_declaration',
    'rust_profile_algorithm_public_declarations',
    'rust_profile_algorithm_support_reexports',
    'rust_selection_function_declarations',
    'rust_transform_function_declarations',
)
