"""Rust rendering for typed whole-algorithm range contracts."""

from __future__ import annotations

from collections.abc import Mapping
from textwrap import wrap

from tslc.backend.algorithm_contracts import (
    ALGORITHM_ERROR_EXPLANATIONS,
    ALGORITHM_CONTRACTS,
    AlgorithmContract,
    AlgorithmMaskStorageKind,
    AlgorithmRangeCondition,
    AlgorithmRangeConditionKind,
    AlgorithmRangeRole,
    AlgorithmResultKind,
)
from tslc.backend.algorithm_surface import ALGORITHM_SCALED_CHECKED_TWINS
from tslc.backend.precondition_error_rendering import rust_precondition_error
from tslc.backend.public_declarations import (
    PublicDeclarationKind,
    PublicDeclarationStability,
)
from tslc.backend.rust_algorithm_public_declarations import (
    rust_profile_algorithm_aliases,
    rust_profile_algorithm_declaration_holes,
)
from tslc.backend.rust_public_declarations import (
    RustPublicDeclaration,
    RustPublicParameter,
    rust_const_parameter,
    rust_type_parameter,
)
from tslc.catalog.preconditions import PreconditionErrorKind


def render_rust_algorithm_error_docs(
    contract: AlgorithmContract,
    *,
    profile_wrapper: bool = False,
    scaled_selected: bool = False,
) -> str:
    """Render Rustdoc from the same errors that drive checked guards."""

    errors = tuple(
        error
        for error in contract.checked_errors
        if error is not PreconditionErrorKind.OVERLAPPING_RANGES
        and (scaled_selected or error is not PreconditionErrorKind.MISALIGNED)
    )
    lines: list[str] = []
    if profile_wrapper:
        lines.extend(
            (
                f"/// Checked profile wrapper for `{contract.name}`.",
                "///",
                "/// Validation completes before the operation is invoked.",
            )
        )
    lines.extend(("///", "/// # Errors", "///"))
    for error in errors:
        sentence = (
            "- Returns "
            f"`{rust_precondition_error(error, prefix='crate::PreconditionError::')}` "
            f"when {ALGORITHM_ERROR_EXPLANATIONS[error]}."
        )
        lines.extend(
            f"/// {line}"
            for line in wrap(sentence, width=96, subsequent_indent="  ")
        )
    return "\n".join(lines)


def _condition_lines(
    contract: AlgorithmContract,
    condition: AlgorithmRangeCondition,
    *,
    selected_scale: str,
) -> tuple[str, ...]:
    error = rust_precondition_error(condition.error, prefix="crate::PreconditionError::")
    if condition.kind is AlgorithmRangeConditionKind.COVERS:
        return (
            f"    if {condition.range_name}.len() < {condition.reference_name}.len() {{",
            f"        return Err({error});",
            "    }",
        )
    if condition.kind is AlgorithmRangeConditionKind.SELECTED_ADDRESSES:
        return (
            f"    if let Some(error) = selected_address_error::<T, {selected_scale}>(",
            f"        {condition.range_name}, {condition.reference_name}) {{",
            "        return Err(error);",
            "    }",
        )
    if condition.kind is AlgorithmRangeConditionKind.MASK_COVERS:
        binding = next(
            binding
            for binding in contract.ranges
            if binding.name == condition.range_name
        )
        required: tuple[str, ...]
        if binding.mask_storage is AlgorithmMaskStorageKind.INTEGRAL_CHUNKS:
            required = (
                "    let mask_lanes = validate_integral_mask_vector::<",
                "        <Policy as VectorFor<Profile, T>>::Vec",
                f"    >(\"tsl::algo::{contract.name}_checked\");",
                "    let required_masks = chunk_count_for_lanes(",
                f"        {condition.reference_name}.len(), mask_lanes);",
            )
        elif binding.mask_storage is AlgorithmMaskStorageKind.LAYOUT_STORAGE:
            required = (
                "    let mask_lanes = validate_mask_layout_vector::<",
                "        <Policy as VectorFor<Profile, T>>::Vec",
                f"    >(\"tsl::algo::{contract.name}_checked\");",
                "    let required_masks = <Layout as MaskLayout<",
                "        Profile, <Policy as VectorFor<Profile, T>>::Vec",
                "    >>::storage_count(",
                f"        {condition.reference_name}.len(), mask_lanes);",
            )
        else:
            raise ValueError(
                f"algorithm {contract.name!r} mask condition lacks storage semantics"
            )
        return (
            *required,
            f"    if {condition.range_name}.len() < required_masks {{",
            f"        return Err({error});",
            "    }",
        )
    raise ValueError(f"Rust algorithm renderer does not support {condition.kind.value!r}")


def render_rust_algorithm_check(
    contract: AlgorithmContract,
    *,
    selected_scale: str = "0",
) -> str:
    return "\n".join(
        line
        for condition in contract.conditions
        for line in _condition_lines(
            contract, condition, selected_scale=selected_scale
        )
    )


def _selected_kernel_trait(contract: AlgorithmContract) -> str:
    selected_inputs = sum(
        binding.role is AlgorithmRangeRole.SELECTED_INPUT
        for binding in contract.ranges
    )
    if selected_inputs not in {1, 2}:
        raise ValueError(
            f"selected algorithm {contract.name!r} requires unary or binary input"
        )
    arity = "Unary" if selected_inputs == 1 else "Binary"
    if contract.result_kind is AlgorithmResultKind.COUNT:
        category = "PredicateKernel"
    elif contract.result_kind is AlgorithmResultKind.VALUE:
        category = "AggregateKernel"
    elif any(
        binding.role is AlgorithmRangeRole.VALUE_OUTPUT
        for binding in contract.ranges
    ):
        category = "Kernel"
    else:
        category = "ConsumeKernel"
    return f"{arity}{category}"


def _rust_range_parameter(name: str, role: AlgorithmRangeRole) -> str:
    if role in {
        AlgorithmRangeRole.DRIVING_INPUT,
        AlgorithmRangeRole.SECONDARY_INPUT,
        AlgorithmRangeRole.SELECTED_INPUT,
    }:
        return f"    {name}: &[T],"
    if role is AlgorithmRangeRole.DRIVING_INDEX:
        return f"    {name}: &[usize],"
    if role is AlgorithmRangeRole.INDEX_OUTPUT:
        return f"    {name}: &mut [usize],"
    if role is AlgorithmRangeRole.VALUE_OUTPUT:
        return f"    {name}: &mut [T],"
    raise ValueError(f"unsupported selected Rust range {name!r} ({role!r})")


def _rust_range_public_parameter(
    name: str, role: AlgorithmRangeRole
) -> RustPublicParameter:
    rendered = _rust_range_parameter(name, role).strip().removesuffix(",")
    rendered_name, separator, type_spelling = rendered.partition(":")
    if not separator or rendered_name != name:
        raise ValueError("selected Rust range parameter rendering is incomplete")
    return RustPublicParameter(
        name=name,
        type_spelling=type_spelling.strip(),
        role=f"range:{role.value}",
    )


def _rust_selected_result(contract: AlgorithmContract, trait: str) -> str:
    if contract.result_kind is AlgorithmResultKind.VOID:
        return "()"
    if contract.result_kind is AlgorithmResultKind.COUNT:
        return "usize"
    return (
        f"<Op as {trait}<<Policy as VectorFor<Profile, T>>::Vec>>::Output"
    )


def _selected_extra_profile_bounds(contract: AlgorithmContract) -> tuple[str, ...]:
    if contract.result_kind is AlgorithmResultKind.COUNT:
        return (
            "        + IntegralMask<<Policy as VectorFor<Profile, T>>::Vec>",
            "        + IntegralMask<Simd<T, Scalar>>",
        )
    if any(
        binding.role is AlgorithmRangeRole.VALUE_OUTPUT
        for binding in contract.ranges
    ):
        return (
            "        + LoadStore<<Policy as VectorFor<Profile, T>>::Vec>",
            "        + LoadStore<Simd<T, Scalar>>",
        )
    return ()


def render_rust_scaled_checked_algorithm(contract: AlgorithmContract) -> str:
    """Render one checked selected-row algorithm from typed range roles."""

    declaration = rust_scaled_checked_algorithm_declaration(
        contract,
        reachability=("tsl_algorithm",),
        profile_wrapper=False,
    )
    driver = _driving_range(contract)
    raw_arguments = ["policy", "op"]
    for binding in contract.ranges:
        pointer = (
            "as_mut_ptr"
            if binding.role
            in {
                AlgorithmRangeRole.VALUE_OUTPUT,
                AlgorithmRangeRole.INDEX_OUTPUT,
            }
            else "as_ptr"
        )
        raw_arguments.append(f"{binding.name}.{pointer}()")
    raw_arguments.append(f"{driver}.len()")
    raw_call = ",\n            ".join(raw_arguments)
    check = render_rust_algorithm_check(contract, selected_scale="SCALE")
    if contract.result_kind is AlgorithmResultKind.VOID:
        invocation = f"""    unsafe {{
        {contract.name}_scaled_raw::<Profile, SCALE, Policy, Op, T>(
            {raw_call},
        );
    }}
    Ok(())"""
    else:
        invocation = f"""    Ok(unsafe {{
        {contract.name}_scaled_raw::<Profile, SCALE, Policy, Op, T>(
            {raw_call},
        )
    }})"""
    error_docs = render_rust_algorithm_error_docs(
        contract, scaled_selected=True
    )
    return f"""/// Checked selected-row form with an explicit byte scale.
/// Address multiplication, alignment, bounds, and output capacity are checked
/// before the operation is invoked.
{error_docs}
{declaration.render_definition_head()}
{check}
{invocation}
}}"""


def _driving_range(contract: AlgorithmContract) -> str:
    return next(
        binding.name
        for binding in contract.ranges
        if binding.role
        in {AlgorithmRangeRole.DRIVING_INPUT, AlgorithmRangeRole.DRIVING_INDEX}
    )


def _render_rust_profile_scaled_checked(contract: AlgorithmContract) -> str:
    declaration = rust_scaled_checked_algorithm_declaration(
        contract,
        reachability=("profile", "algo"),
        profile_wrapper=True,
    )
    arguments = ", ".join(
        ("policy", "op", *(binding.name for binding in contract.ranges))
    )
    docs = "\n".join(
        f"    {line}" if line else ""
        for line in render_rust_algorithm_error_docs(
            contract, profile_wrapper=True, scaled_selected=True
        ).splitlines()
    )
    return f"""{docs}
{_indent(declaration.render_definition_head(), 4)}
        crate::tsl_algorithm::{contract.name}_scaled_checked::<
            Profile, SCALE, Policy, Op, T,
        >({arguments})
    }}"""


def rust_scaled_checked_algorithm_declaration(
    contract: AlgorithmContract,
    *,
    reachability: tuple[str, ...],
    profile_wrapper: bool,
) -> RustPublicDeclaration:
    """Finalize one selected-row checked signature for rendering and manifesting."""

    trait = _selected_kernel_trait(contract)
    profile_bound = (
        "Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE> "
        "+ SelectedLoad<Simd<T, Scalar>, SCALE>"
        + "".join(f" {item.strip()}" for item in _selected_extra_profile_bounds(contract))
    )
    where_predicates = [
        "Policy: VectorFor<Profile, T>",
        "<Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>",
        "Simd<T, Scalar>: StaticSimdVector<BaseType = T>",
        profile_bound,
        (
            f"Op: {trait}<<Policy as VectorFor<Profile, T>>::Vec> "
            f"+ {trait}<Simd<T, Scalar>>"
        ),
    ]
    if contract.result_kind is AlgorithmResultKind.COUNT:
        where_predicates.extend(
            (
                "<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord",
                "<Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord",
            )
        )
    name = f"{contract.name}_scaled_checked"
    ordinary_twin = ALGORITHM_SCALED_CHECKED_TWINS.get(name)
    if ordinary_twin is None:
        raise ValueError(
            f"scaled checked Rust algorithm {name!r} has no registered twin"
        )
    owner = "crate::profile::algo" if profile_wrapper else "crate::tsl_algorithm"
    return RustPublicDeclaration(
        identity=f"{owner}::{name}#algorithm",
        name=name,
        owner=owner,
        reachability=reachability,
        stability=(
            PublicDeclarationStability.STABLE
            if profile_wrapper
            else PublicDeclarationStability.UNSTABLE
        ),
        kind=PublicDeclarationKind.FUNCTION,
        overload="selected-row-scaled-checked",
        visibility="pub",
        generic_parameters=(
            *((rust_type_parameter("Profile"),) if not profile_wrapper else ()),
            rust_const_parameter("SCALE", "u32"),
            rust_type_parameter("Policy"),
            rust_type_parameter("Op"),
            rust_type_parameter("T"),
        ),
        parameters=(
            RustPublicParameter("policy", "Policy", "policy"),
            RustPublicParameter("op", "&mut Op", "operation"),
            *(
                _rust_range_public_parameter(binding.name, binding.role)
                for binding in contract.ranges
            ),
        ),
        where_predicates=tuple(where_predicates),
        result_type=(
            f"Result<{_rust_selected_result(contract, trait)}, "
            "crate::PreconditionError>"
        ),
        result_form="result",
        checked_of=f"{owner}::{ordinary_twin}#algorithm",
        error_form="result",
    )


def rust_profile_scaled_checked_algorithm_declarations(
    reachability: tuple[str, ...],
) -> tuple[RustPublicDeclaration, ...]:
    return tuple(
        rust_scaled_checked_algorithm_declaration(
            contract,
            reachability=reachability,
            profile_wrapper=True,
        )
        for contract in _selected_contracts()
    )


def _indent(text: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(f"{prefix}{line}" if line else "" for line in text.splitlines())


def _selected_contracts() -> tuple[AlgorithmContract, ...]:
    return tuple(
        contract
        for contract in ALGORITHM_CONTRACTS.values()
        if any(
            binding.role is AlgorithmRangeRole.DRIVING_INDEX
            for binding in contract.ranges
        )
    )


def rust_algorithm_contract_holes() -> Mapping[str, str]:
    """Return all semantic fragments required by the Rust algorithm asset."""

    checks = {
        f"check_{contract.name}": render_rust_algorithm_check(contract)
        for contract in ALGORITHM_CONTRACTS.values()
    }
    aliases = rust_profile_algorithm_aliases(
        ("tsl_algorithm",),
        owner="crate::tsl_algorithm",
    )
    profile_aliases = rust_profile_algorithm_aliases(
        ("profile", "algo"),
        owner="crate::profile::algo",
        indent=4,
    )
    return {
        **rust_profile_algorithm_declaration_holes(),
        **checks,
        **{
            f"docs_{contract.name}": render_rust_algorithm_error_docs(contract)
            for contract in ALGORITHM_CONTRACTS.values()
        },
        **{
            f"profile_docs_{contract.name}": render_rust_algorithm_error_docs(
                contract, profile_wrapper=True
            )
            for contract in ALGORITHM_CONTRACTS.values()
        },
        "unchecked_algorithm_aliases": aliases,
        "profile_unchecked_algorithm_aliases": profile_aliases,
        "scaled_checked_algorithm_definitions": "\n\n".join(
            render_rust_scaled_checked_algorithm(contract)
            for contract in _selected_contracts()
        ),
        "profile_scaled_checked_algorithm_definitions": "\n\n".join(
            _render_rust_profile_scaled_checked(contract)
            for contract in _selected_contracts()
        ),
    }


__all__ = (
    "render_rust_algorithm_check",
    "render_rust_algorithm_error_docs",
    "render_rust_scaled_checked_algorithm",
    "rust_profile_scaled_checked_algorithm_declarations",
    "rust_scaled_checked_algorithm_declaration",
    "rust_algorithm_contract_holes",
)
