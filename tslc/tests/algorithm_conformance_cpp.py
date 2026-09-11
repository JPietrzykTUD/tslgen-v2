"""C++ compile-witness adapter for the test-owned algorithm inventory."""

from __future__ import annotations

from collections.abc import Sequence

from tslc.backend.algorithm_surface import (
    ALGORITHM_FORMS_BY_NAME,
    AlgorithmArity,
    AlgorithmSemanticFamily,
    AlgorithmShape,
)
from tslc.backend.cpp_algorithm_contracts import (
    cpp_checked_algorithm_declarations,
)
from tslc.backend.cpp_algorithm_public_declarations import (
    cpp_algorithm_public_declarations,
)
from tslc.backend.cpp_public_declarations import (
    CppPublicDeclaration,
    CppPublicParameter,
    CppTemplateParameterKind,
)
from tslc.backend.public_declarations import (
    PublicDeclarationKind,
    PublicDeclarationStability,
)

from algorithm_conformance import AlgorithmBehaviorCase


def cpp_algorithm_compile_declarations() -> tuple[CppPublicDeclaration, ...]:
    declarations = (
        *cpp_algorithm_public_declarations(),
        *cpp_checked_algorithm_declarations(),
    )
    return tuple(
        declaration
        for declaration in declarations
        if declaration.kind is PublicDeclarationKind.FUNCTION
        and declaration.stability is PublicDeclarationStability.STABLE
    )


def cpp_algorithm_compile_identities() -> frozenset[str]:
    return frozenset(
        declaration.identity for declaration in cpp_algorithm_compile_declarations()
    )


def _form_name(declaration: CppPublicDeclaration) -> str:
    return declaration.name.removesuffix("_checked")


def _uses_fixed_parallelism(declaration: CppPublicDeclaration) -> bool:
    return any(
        parameter.name == "ParallelN"
        for parameter in declaration.template_parameters
    )


def _operation_name(declaration: CppPublicDeclaration) -> str:
    form = ALGORITHM_FORMS_BY_NAME[_form_name(declaration)]
    family = form.family
    suffix = "unary" if family.arity is AlgorithmArity.UNARY else "binary"
    if family.semantic_family is AlgorithmSemanticFamily.ITERATION:
        return "chunk_op"
    if family.semantic_family in {
        AlgorithmSemanticFamily.PREDICATE,
        AlgorithmSemanticFamily.COUNT,
        AlgorithmSemanticFamily.SELECT,
    }:
        return f"{suffix}_predicate"
    if family.semantic_family is AlgorithmSemanticFamily.TRANSFORM:
        prefix = "masked_" if family.shape is AlgorithmShape.MASKED else ""
        return f"{prefix}{suffix}_value"
    if family.semantic_family in {
        AlgorithmSemanticFamily.CONSUME,
        AlgorithmSemanticFamily.AGGREGATE,
    }:
        prefix = "masked_" if family.shape is AlgorithmShape.MASKED else ""
        return f"{prefix}{suffix}_sink"
    raise ValueError(f"algorithm utility {family.name!r} has no operation")


def _template_arguments(declaration: CppPublicDeclaration) -> str:
    form = ALGORITHM_FORMS_BY_NAME[_form_name(declaration)]
    if form.family.semantic_family is not AlgorithmSemanticFamily.UTILITY:
        first = declaration.template_parameters[0]
        return "1" if first.kind is CppTemplateParameterKind.VALUE else "policy"

    arguments: list[str] = []
    for parameter in declaration.template_parameters:
        if parameter.name == "ParallelN":
            arguments.append("1")
        elif parameter.name == "Parallelism":
            arguments.append("policy")
        elif parameter.name == "MaskLayout":
            arguments.append("::tsl::algo::mask_layout::integral")
        elif parameter.name == "T":
            arguments.append("std::int32_t")
        else:
            raise ValueError(
                f"unsupported utility template parameter {parameter.name!r}"
            )
    return ", ".join(arguments)


def _argument(
    declaration: CppPublicDeclaration,
    parameter: CppPublicParameter,
) -> str:
    name = parameter.name
    pointer = "*" in parameter.type_spelling
    fixed = _uses_fixed_parallelism(declaration)
    if name in {"op", "predicate"}:
        return _operation_name(declaration)
    if name in {"count", "selected_count"}:
        return "0"
    if name == "error":
        return "error"
    if name in {"data", "input", "left", "right"}:
        value = "input" if name in {"data", "input"} else name
        return f"{value}.data()" if pointer else value
    if name == "output":
        return "output.data()" if pointer else "output"
    if name in {"input_indices", "indices"}:
        value = (
            "selected_indices"
            if "const" in parameter.type_spelling
            else "output_indices"
        )
        return f"{value}.data()" if pointer else value
    if name == "output_indices":
        return "output_indices.data()" if pointer else "output_indices"
    if name == "masks":
        value = "fixed_masks" if fixed else "policy_masks"
        return f"{value}.data()" if pointer else value
    raise ValueError(
        f"unsupported C++ conformance parameter {declaration.identity}:{name}"
    )


def _render_call(declaration: CppPublicDeclaration) -> str:
    arguments = ", ".join(
        _argument(declaration, parameter)
        for parameter in declaration.parameters
    )
    templates = _template_arguments(declaration)
    return (
        f"    // witness: {declaration.identity}\n"
        f"    (void)::tsl::algo::{declaration.name}<{templates}>({arguments});"
    )


def render_cpp_algorithm_compile_witness(
    declarations: Sequence[CppPublicDeclaration] | None = None,
) -> tuple[str, frozenset[str]]:
    selected = tuple(
        cpp_algorithm_compile_declarations()
        if declarations is None
        else declarations
    )
    calls = "\n".join(_render_call(declaration) for declaration in selected)
    source = f"""#include <cstddef>
#include <cstdint>
#include <vector>

#include <tsl.hpp>

struct unary_predicate_op {{
    template <class Vec>
    typename Vec::mask_type operator()(typename ::tsl::reg_param<Vec>::type) const {{
        return {{}};
    }}
}};

struct binary_predicate_op {{
    template <class Vec>
    typename Vec::mask_type operator()(
        typename ::tsl::reg_param<Vec>::type,
        typename ::tsl::reg_param<Vec>::type) const {{
        return {{}};
    }}
}};

struct unary_value_op {{
    template <class Vec>
    typename Vec::register_type operator()(
        typename ::tsl::reg_param<Vec>::type value) const {{
        return value;
    }}
}};

struct binary_value_op {{
    template <class Vec>
    typename Vec::register_type operator()(
        typename ::tsl::reg_param<Vec>::type left,
        typename ::tsl::reg_param<Vec>::type) const {{
        return left;
    }}
}};

struct masked_unary_value_op {{
    template <class Vec>
    typename Vec::register_type operator()(
        typename Vec::mask_type,
        typename ::tsl::reg_param<Vec>::type value) const {{
        return value;
    }}
}};

struct masked_binary_value_op {{
    template <class Vec>
    typename Vec::register_type operator()(
        typename Vec::mask_type,
        typename ::tsl::reg_param<Vec>::type left,
        typename ::tsl::reg_param<Vec>::type) const {{
        return left;
    }}
}};

struct unary_sink_op {{
    template <class Vec>
    void operator()(typename ::tsl::reg_param<Vec>::type) {{}}
    std::int64_t finalize() const {{ return 0; }}
}};

struct binary_sink_op {{
    template <class Vec>
    void operator()(
        typename ::tsl::reg_param<Vec>::type,
        typename ::tsl::reg_param<Vec>::type) {{}}
    std::int64_t finalize() const {{ return 0; }}
}};

struct masked_unary_sink_op {{
    template <class Vec>
    void operator()(
        typename Vec::mask_type,
        typename ::tsl::reg_param<Vec>::type) {{}}
    std::int64_t finalize() const {{ return 0; }}
}};

struct masked_binary_sink_op {{
    template <class Vec>
    void operator()(
        typename Vec::mask_type,
        typename ::tsl::reg_param<Vec>::type,
        typename ::tsl::reg_param<Vec>::type) {{}}
    std::int64_t finalize() const {{ return 0; }}
}};

struct chunk_op_type {{
    template <class Vec>
    void operator()(const std::int32_t*, std::size_t, std::size_t) {{}}
}};

int main() {{
    using policy = ::tsl::dataparallel::generic<4>;
    using fixed_mask_type = ::tsl::algo::fixed_mask_storage_type<
        ::tsl::algo::mask_layout::integral, 1, std::int32_t>;
    using policy_mask_type = ::tsl::algo::mask_storage_type<
        ::tsl::algo::mask_layout::integral, policy, std::int32_t>;
    std::vector<std::int32_t> input;
    std::vector<std::int32_t> left;
    std::vector<std::int32_t> right;
    std::vector<std::int32_t> output;
    std::vector<std::size_t> selected_indices;
    std::vector<std::size_t> output_indices;
    std::vector<fixed_mask_type> fixed_masks;
    std::vector<policy_mask_type> policy_masks;
    unary_predicate_op unary_predicate;
    binary_predicate_op binary_predicate;
    unary_value_op unary_value;
    binary_value_op binary_value;
    masked_unary_value_op masked_unary_value;
    masked_binary_value_op masked_binary_value;
    unary_sink_op unary_sink;
    binary_sink_op binary_sink;
    masked_unary_sink_op masked_unary_sink;
    masked_binary_sink_op masked_binary_sink;
    chunk_op_type chunk_op;
    auto error = ::tsl::precondition_error::none;
{calls}
    return 0;
}}
"""
    return source, frozenset(declaration.identity for declaration in selected)


def render_cpp_algorithm_behavior(case: AlgorithmBehaviorCase) -> str:
    values = ", ".join(str(value) for value in case.input_values)
    lengths = ", ".join(str(length) for length in case.lengths)
    return f"""#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <vector>

#include <tsl.hpp>

struct unary_identity {{
    std::size_t calls = 0;
    template <class Vec>
    typename Vec::register_type operator()(
        typename ::tsl::reg_param<Vec>::type value) {{
        ++calls;
        return value;
    }}
}};

struct binary_identity {{
    std::size_t calls = 0;
    template <class Vec>
    typename Vec::register_type operator()(
        typename ::tsl::reg_param<Vec>::type left,
        typename ::tsl::reg_param<Vec>::type) {{
        ++calls;
        return left;
    }}
}};

template <class Range>
void print_values(const Range& values) {{
    for (std::size_t index = 0; index < values.size(); ++index) {{
        if (index != 0) {{
            std::cout << ',';
        }}
        std::cout << values[index];
    }}
}}

int main() {{
    using policy = ::tsl::dataparallel::generic<4>;
    const std::vector<std::int32_t> input{{{values}}};
    const std::size_t lengths[]{{{lengths}}};
    std::vector<std::int32_t> output(input.size(), {case.sentinel});
    unary_identity unary;
    for (const auto length : lengths) {{
        std::fill(output.begin(), output.end(), {case.sentinel});
        std::vector<std::int32_t> prefix(input.begin(), input.begin() + length);
        std::vector<std::int32_t> produced(length, {case.sentinel});
        auto error = ::tsl::algo::transform_unary_checked<policy>(
            unary, prefix, produced);
        if (error != ::tsl::precondition_error::none || produced != prefix) {{
            return 1;
        }}
        if (length == input.size()) {{
            output = produced;
        }}
    }}

    auto alias = input;
    ::tsl::algo::transform_unary<policy>(
        unary, alias.data(), alias.data(), alias.size());

    std::vector<std::int32_t> short_right(input.begin(), input.end() - 1);
    std::vector<std::int32_t> failure_output(input.size(), {case.sentinel});
    binary_identity binary;
    auto failure = ::tsl::algo::transform_binary_checked<policy>(
        binary, input, short_right, failure_output);
    const bool unchanged = std::all_of(
        failure_output.begin(), failure_output.end(),
        [](std::int32_t value) {{ return value == {case.sentinel}; }});
    const char* failure_name =
        failure == ::tsl::precondition_error::insufficient_input
            ? "insufficient_input"
            : "unexpected";

    std::cout << "values=";
    print_values(output);
    std::cout << ";alias=";
    print_values(alias);
    std::cout << ";failure=" << failure_name
              << ";unchanged=" << (unchanged ? "true" : "false")
              << ";failure_calls=" << binary.calls;
    return 0;
}}
"""


__all__ = (
    "cpp_algorithm_compile_declarations",
    "cpp_algorithm_compile_identities",
    "render_cpp_algorithm_behavior",
    "render_cpp_algorithm_compile_witness",
)
