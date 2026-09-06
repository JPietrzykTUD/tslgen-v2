"""C++ rendering for typed whole-algorithm range contracts."""

from __future__ import annotations

from collections.abc import Mapping

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
from tslc.backend.precondition_error_rendering import cpp_precondition_error


_RANGE_TYPES = {
    "input": "InputRange",
    "left": "LeftRange",
    "right": "RightRange",
    "masks": "MaskRange",
    "indices": "IndexRange",
    "input_indices": "InputIndexRange",
    "output_indices": "OutputIndexRange",
    "output": "OutputRange",
}

def _driving_name(contract: AlgorithmContract) -> str:
    return next(
        binding.name
        for binding in contract.ranges
        if binding.role
        in {AlgorithmRangeRole.DRIVING_INPUT, AlgorithmRangeRole.DRIVING_INDEX}
    )


def _failure_lines(
    contract: AlgorithmContract,
    error_expression: str,
    *,
    indent: str = "        ",
) -> tuple[str, ...]:
    if contract.result_kind is AlgorithmResultKind.VOID:
        return (f"{indent}return {error_expression};",)
    return (
        f"{indent}error = {error_expression};",
        f"{indent}return result_type{{}};",
    )


def _condition_lines(
    contract: AlgorithmContract,
    condition: AlgorithmRangeCondition,
) -> tuple[str, ...]:
    error = cpp_precondition_error(condition.error)
    if condition.kind is AlgorithmRangeConditionKind.COVERS:
        return (
            f"    if (detail::range_size({condition.range_name}) <",
            f"        detail::range_size({condition.reference_name})) {{",
            *_failure_lines(contract, error),
            "    }",
        )
    if condition.kind is AlgorithmRangeConditionKind.MASK_COVERS:
        return (
            "    const auto required_masks = mask_chunk_count<",
            "        MaskLayout, Parallelism, value_type>(",
            f"            detail::range_size({condition.reference_name}));",
            f"    if (detail::range_size({condition.range_name}) < required_masks) {{",
            *_failure_lines(contract, error),
            "    }",
        )
    if condition.kind is AlgorithmRangeConditionKind.SELECTED_ADDRESSES:
        variable = f"{condition.range_name}_address_error"
        return (
            f"    const auto {variable} =",
            f"        detail::selected_address_error<Scale>({condition.range_name},",
            f"                                              {condition.reference_name});",
            f"    if ({variable} != ::tsl::precondition_error::none) {{",
            *_failure_lines(contract, variable),
            "    }",
        )
    raise ValueError(f"C++ algorithm renderer does not support {condition.kind.value!r}")


def _range_count_expression(contract: AlgorithmContract, name: str) -> str:
    binding = next(binding for binding in contract.ranges if binding.name == name)
    if binding.role in {
        AlgorithmRangeRole.MASK_INPUT,
        AlgorithmRangeRole.MASK_OUTPUT,
    }:
        return "required_masks"
    if binding.role is AlgorithmRangeRole.SELECTED_INPUT:
        return f"detail::range_size({name})"
    return f"detail::range_size({_driving_name(contract)})"


def render_cpp_algorithm_check(contract: AlgorithmContract) -> str:
    lines = [
        line
        for condition in contract.conditions
        for line in _condition_lines(contract, condition)
    ]
    for rule in contract.alias_rules:
        writable_count = _range_count_expression(
            contract, rule.writable_range_name
        )
        for readable_name in rule.readable_range_names:
            readable_count = _range_count_expression(contract, readable_name)
            exact_clause = (
                f" && !detail::ranges_share_start({rule.writable_range_name}, "
                f"{readable_name})"
                if rule.allow_exact_alias
                else ""
            )
            lines.extend(
                (
                    "    if (detail::range_prefixes_overlap(",
                    f"            {rule.writable_range_name}, {writable_count},",
                    f"            {readable_name}, {readable_count})",
                    f"        {exact_clause}) {{",
                    *_failure_lines(
                        contract,
                        "::tsl::precondition_error::overlapping_ranges",
                    ),
                    "    }",
                )
            )
    return "\n".join(lines)


def _has_mask(contract: AlgorithmContract) -> bool:
    return any(
        binding.role
        in {AlgorithmRangeRole.MASK_INPUT, AlgorithmRangeRole.MASK_OUTPUT}
        for binding in contract.ranges
    )


def _is_selected(contract: AlgorithmContract) -> bool:
    return any(
        binding.role is AlgorithmRangeRole.DRIVING_INDEX
        for binding in contract.ranges
    )


def _template_parameters(
    contract: AlgorithmContract,
    *,
    fixed: bool,
) -> tuple[str, ...]:
    prefix: tuple[str, ...]
    if _is_selected(contract):
        prefix = ("std::size_t ParallelN", "std::size_t Scale = 0")
    else:
        prefix = (
            "std::size_t ParallelN"
            if fixed
            else "class Parallelism = ::tsl::dataparallel::native",
        )
        if _has_mask(contract):
            prefix += ("class MaskLayout = mask_layout::integral",)
    return (
        *prefix,
        "class Op",
        *(f"class {_RANGE_TYPES[binding.name]}" for binding in contract.ranges),
    )


def _parameter(binding_name: str, role: AlgorithmRangeRole) -> str:
    range_type = _RANGE_TYPES[binding_name]
    mutable = role in {
        AlgorithmRangeRole.MASK_OUTPUT,
        AlgorithmRangeRole.VALUE_OUTPUT,
        AlgorithmRangeRole.INDEX_OUTPUT,
    }
    qualifier = "" if mutable else "const "
    return f"    {qualifier}{range_type}& {binding_name}"


def _call_template_arguments(
    contract: AlgorithmContract,
    *,
    checked: bool,
    fixed_forward: bool = False,
) -> str:
    if _is_selected(contract):
        return "ParallelN, Scale"
    parallelism = (
        "::tsl::dataparallel::fixed<ParallelN>" if fixed_forward else "Parallelism"
    )
    arguments = [parallelism]
    if not checked:
        arguments.append("alignment::detect")
    if _has_mask(contract):
        arguments.append("MaskLayout")
    return ", ".join(arguments)


def _call_expression(
    contract: AlgorithmContract,
    *,
    checked: bool,
    fixed_forward: bool = False,
) -> str:
    name = f"{contract.name}_checked" if checked else contract.name
    arguments = ["std::forward<Op>(op)", *(binding.name for binding in contract.ranges)]
    if checked and contract.result_kind is not AlgorithmResultKind.VOID:
        arguments.append("error")
    return (
        f"{name}<{_call_template_arguments(contract, checked=checked, fixed_forward=fixed_forward)}>(\n"
        f"        {', '.join(arguments)})"
    )


def _return_type(contract: AlgorithmContract) -> str:
    if contract.result_kind is AlgorithmResultKind.VOID:
        return "::tsl::precondition_error"
    if contract.result_kind is AlgorithmResultKind.COUNT:
        return "std::size_t"
    return "auto"


def _cpp_algorithm_documentation(
    contract: AlgorithmContract,
    *,
    fixed_forwarder: bool = False,
) -> str:
    form = "Fixed-width checked" if fixed_forwarder else "Checked"
    lines = [
        "/**",
        f" * {form} range form of `{contract.name}`.",
        " *",
        " * Every related range is validated before the operation is invoked.",
        " * Longer ranges are accepted and their suffixes remain untouched. The",
        " * unsuffixed overload is the unchecked expert path. This checked overload",
        " * detects alignment; explicit alignment promises remain on the unchecked path.",
        " * Each range must still describe live storage for its reported size, and the",
        " * supplied operation remains responsible for its own semantic contract.",
        " *",
    ]
    if contract.result_kind is AlgorithmResultKind.VOID:
        lines.append(" * @return `precondition_error::none` on success, or an error below.")
    else:
        lines.extend(
            (
                " * @param[out] error Receives `precondition_error::none` on success or",
                " *   one error below on failure.",
                (
                    " * @return The produced count on success, or zero on failure."
                    if contract.result_kind is AlgorithmResultKind.COUNT
                    else " * @return The operation result on success, or a default-constructed placeholder on failure."
                ),
            )
        )
    lines.extend((" *", " * @par Errors"))
    lines.extend(
        " * - `precondition_error::"
        f"{cpp_precondition_error(error, qualified=False)}` when "
        f"{ALGORITHM_ERROR_EXPLANATIONS[error]}."
        for error in contract.checked_errors
    )
    lines.append(" */")
    return "\n".join(lines)


def _render_primary_wrapper(contract: AlgorithmContract) -> str:
    template_lines = ",\n    ".join(_template_parameters(contract, fixed=False))
    parameters = ["    Op&& op", *(_parameter(binding.name, binding.role) for binding in contract.ranges)]
    if contract.result_kind is not AlgorithmResultKind.VOID:
        parameters.append("    ::tsl::precondition_error& error")
    parameter_lines = ",\n".join(parameters)
    ordinary_call = _call_expression(contract, checked=False)
    prologue: list[str] = []
    if _has_mask(contract):
        driver_type = _RANGE_TYPES[
            next(
                binding.name
                for binding in contract.ranges
                if binding.role is AlgorithmRangeRole.DRIVING_INPUT
            )
        ]
        prologue.extend(
            (
                "    using value_type =",
                f"        detail::checked_range_element_t<{driver_type}>;",
            )
        )
    if contract.result_kind is not AlgorithmResultKind.VOID:
        prologue.extend(
            (
                "    using result_type = decltype(",
                f"        {ordinary_call});",
            )
        )
    if contract.result_kind is AlgorithmResultKind.VALUE:
        prologue.extend(
            (
                "    static_assert(std::is_default_constructible<result_type>::value,",
                '                  "checked aggregate results must be default-constructible");',
            )
        )
    check = render_cpp_algorithm_check(contract)
    if contract.result_kind is AlgorithmResultKind.VOID:
        epilogue = (
            f"    {ordinary_call};",
            "    return ::tsl::precondition_error::none;",
        )
    else:
        epilogue = (
            "    error = ::tsl::precondition_error::none;",
            f"    return {ordinary_call};",
        )
    body = "\n".join((*prologue, check, *epilogue))
    documentation = _cpp_algorithm_documentation(contract)
    return f"""{documentation}
template <
    {template_lines}>
[[nodiscard]] inline {_return_type(contract)} {contract.name}_checked(
{parameter_lines}) {{
{body}
}}"""


def _render_fixed_forwarder(contract: AlgorithmContract) -> str:
    template_lines = ",\n    ".join(_template_parameters(contract, fixed=True))
    parameters = ["    Op&& op", *(_parameter(binding.name, binding.role) for binding in contract.ranges)]
    if contract.result_kind is not AlgorithmResultKind.VOID:
        parameters.append("    ::tsl::precondition_error& error")
    parameter_lines = ",\n".join(parameters)
    call = _call_expression(contract, checked=True, fixed_forward=True)
    documentation = _cpp_algorithm_documentation(contract, fixed_forwarder=True)
    return f"""{documentation}
template <
    {template_lines}>
[[nodiscard]] inline {_return_type(contract)} {contract.name}_checked(
{parameter_lines}) {{
    return {call};
}}"""


def _cpp_contracts() -> tuple[AlgorithmContract, ...]:
    return tuple(
        contract
        for contract in ALGORITHM_CONTRACTS.values()
        if not any(
            binding.mask_storage is AlgorithmMaskStorageKind.LAYOUT_STORAGE
            for binding in contract.ranges
        )
    )


def render_cpp_checked_algorithm_definitions() -> str:
    definitions: list[str] = []
    for contract in _cpp_contracts():
        definitions.append(_render_primary_wrapper(contract))
        if not _is_selected(contract):
            definitions.append(_render_fixed_forwarder(contract))
    return "\n\n".join(definitions)


def cpp_checked_algorithm_families() -> frozenset[str]:
    """Public checked algorithm families supported by the C++ range surface."""

    return frozenset(contract.name for contract in _cpp_contracts())


def cpp_algorithm_contract_holes() -> Mapping[str, str]:
    """Return semantic fragments required by the C++ checked asset."""

    return {
        **{
            f"check_{contract.name}": render_cpp_algorithm_check(contract)
            for contract in ALGORITHM_CONTRACTS.values()
        },
        "checked_algorithm_definitions": render_cpp_checked_algorithm_definitions(),
    }


__all__ = (
    "cpp_checked_algorithm_families",
    "cpp_algorithm_contract_holes",
    "render_cpp_algorithm_check",
    "render_cpp_checked_algorithm_definitions",
)
