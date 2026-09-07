"""C++ rendering for typed whole-algorithm range contracts."""

from __future__ import annotations

from collections.abc import Mapping

from tslc.backend.algorithm_contracts import (
    ALGORITHM_ERROR_EXPLANATIONS,
    ALGORITHM_CONTRACTS,
    AlgorithmContract,
    AlgorithmMaskStorageKind,
    AlgorithmRangeBinding,
    AlgorithmRangeCondition,
    AlgorithmRangeConditionKind,
    AlgorithmRangeRole,
    AlgorithmResultKind,
)
from tslc.backend.cpp_algorithm_public_declarations import (
    cpp_algorithm_checked_twin_identity,
)
from tslc.backend.cpp_public_declarations import (
    CppPublicDeclaration,
    CppPublicParameter,
    CppTemplateParameter,
    cpp_type_parameter,
    cpp_value_parameter,
)
from tslc.backend.public_declarations import (
    PublicDeclarationKind,
    PublicDeclarationStability,
)
from tslc.backend.precondition_error_rendering import cpp_precondition_error


def _range_type(binding: AlgorithmRangeBinding) -> str:
    """Derive a C++ template spelling without assigning semantics by name."""

    words = binding.name.split("_")
    if words[-1] == "indices":
        words[-1] = "index"
    elif words[-1] == "masks":
        words[-1] = "mask"
    return "".join(word.capitalize() for word in words) + "Range"


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
) -> tuple[CppTemplateParameter, ...]:
    prefix: tuple[CppTemplateParameter, ...]
    if _is_selected(contract):
        prefix = (
            cpp_value_parameter("std::size_t", "ParallelN"),
            cpp_value_parameter("std::size_t", "Scale", default="0"),
        )
    else:
        prefix = (
            cpp_value_parameter("std::size_t", "ParallelN")
            if fixed
            else cpp_type_parameter(
                "Parallelism", default="::tsl::dataparallel::native"
            ),
        )
        if _has_mask(contract):
            prefix += (
                cpp_type_parameter(
                    "MaskLayout", default="mask_layout::integral"
                ),
            )
    return (
        *prefix,
        cpp_type_parameter("Op"),
        *(cpp_type_parameter(_range_type(binding)) for binding in contract.ranges),
    )


def _parameter(binding: AlgorithmRangeBinding) -> str:
    range_type = _range_type(binding)
    mutable = binding.role in {
        AlgorithmRangeRole.MASK_OUTPUT,
        AlgorithmRangeRole.VALUE_OUTPUT,
        AlgorithmRangeRole.INDEX_OUTPUT,
    }
    qualifier = "" if mutable else "const "
    return f"    {qualifier}{range_type}& {binding.name}"


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
    declaration = cpp_checked_algorithm_declaration(contract, fixed=False)
    ordinary_call = _call_expression(contract, checked=False)
    prologue: list[str] = []
    if _has_mask(contract):
        driver_type = _range_type(
            next(
                binding
                for binding in contract.ranges
                if binding.role is AlgorithmRangeRole.DRIVING_INPUT
            )
        )
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
{declaration.render_head(multiline=True)} {{
{body}
}}"""


def _render_fixed_forwarder(contract: AlgorithmContract) -> str:
    declaration = cpp_checked_algorithm_declaration(contract, fixed=True)
    call = _call_expression(contract, checked=True, fixed_forward=True)
    documentation = _cpp_algorithm_documentation(contract, fixed_forwarder=True)
    return f"""{documentation}
{declaration.render_head(multiline=True)} {{
    return {call};
}}"""


def cpp_checked_algorithm_declaration(
    contract: AlgorithmContract,
    *,
    fixed: bool,
) -> CppPublicDeclaration:
    parameters = [CppPublicParameter("op", "Op&&", "operation")]
    parameters.extend(
        CppPublicParameter(
            binding.name,
            (
                f"const {_range_type(binding)}&"
                if binding.role
                not in {
                    AlgorithmRangeRole.MASK_OUTPUT,
                    AlgorithmRangeRole.VALUE_OUTPUT,
                    AlgorithmRangeRole.INDEX_OUTPUT,
                }
                else f"{_range_type(binding)}&"
            ),
            f"range:{binding.role.value}",
        )
        for binding in contract.ranges
    )
    has_value_result = contract.result_kind is not AlgorithmResultKind.VOID
    if has_value_result:
        parameters.append(
            CppPublicParameter(
                "error", "::tsl::precondition_error&", "error_output"
            )
        )
    form = "fixed" if fixed else "policy"
    return CppPublicDeclaration(
        identity=f"tsl::algo::{contract.name}_checked#{form}",
        name=f"{contract.name}_checked",
        owner="tsl::algo",
        reachability=("tsl.hpp", "tsl_algorithm_checked.hpp"),
        stability=PublicDeclarationStability.STABLE,
        kind=PublicDeclarationKind.FUNCTION,
        overload=f"checked-algorithm:{form}:{contract.result_kind.value}",
        template_parameters=_template_parameters(contract, fixed=fixed),
        parameters=tuple(parameters),
        result_type=_return_type(contract),
        specifiers=("inline",),
        attributes=("[[nodiscard]]",),
        checked_of=cpp_algorithm_checked_twin_identity(
            contract.name,
            fixed=fixed,
        ),
        error_form=(
            "result-plus-error-reference" if has_value_result else "error-result"
        ),
    )


def cpp_checked_algorithm_declarations() -> tuple[CppPublicDeclaration, ...]:
    return tuple(
        declaration
        for contract in _cpp_contracts()
        for declaration in (
            cpp_checked_algorithm_declaration(contract, fixed=False),
            *(
                (cpp_checked_algorithm_declaration(contract, fixed=True),)
                if not _is_selected(contract)
                else ()
            ),
        )
    )


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
    return "\n\n".join(
        render_cpp_checked_algorithm_definition(contract)
        for contract in _cpp_contracts()
    )


def render_cpp_checked_algorithm_definition(contract: AlgorithmContract) -> str:
    """Render the checked C++ definitions owned by one typed contract."""

    definitions = [_render_primary_wrapper(contract)]
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
    "cpp_checked_algorithm_declaration",
    "cpp_checked_algorithm_declarations",
    "cpp_checked_algorithm_families",
    "cpp_algorithm_contract_holes",
    "render_cpp_algorithm_check",
    "render_cpp_checked_algorithm_definition",
    "render_cpp_checked_algorithm_definitions",
)
