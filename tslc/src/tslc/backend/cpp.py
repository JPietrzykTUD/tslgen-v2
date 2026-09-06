"""C++ backend: render a primitive as primary template + simd<> specializations + wrapper."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.backend.cpp_compiler_capabilities import cpp_compiler_capability
from tslc.backend.checked_api import CheckedConditionPlan
from tslc.backend.cpp_checked_api import CppCheckedApiPlan, plan_cpp_checked_api
from tslc.backend.cpp_documentation import (
    cpp_doc as _cpp_doc,
    cpp_register_doc as _cpp_register_doc,
    cpp_target_register_doc as _cpp_target_register_doc,
)
from tslc.backend.precondition_error_rendering import cpp_precondition_error
from tslc.backend.primitive_facade import (
    DataparallelPrimitiveFacade,
    DataparallelPrimitiveFacadeKind,
    classify_dataparallel_primitive_facade,
)
from tslc.backend.primitive_rendering import body_for as _body_for
from tslc.backend.primitive_rendering import variant_names as _variant_names
from tslc.backend.signature_types import CPP_SIGNATURE_TYPES
from tslc.catalog.preconditions import (
    PreconditionCheckPrimitive,
    PreconditionErrorKind,
    PreconditionKind,
)
from tslc.catalog.memory import MemoryAccess
from tslc.lower.lowerer import (
    LoweredArithmeticPrecondition,
    LoweredArithmeticPreconditionKind,
    LoweredSpecialization,
    LoweredTypeParam,
    effective_param_types,
    varying_positions,
)
from tslc.lower.implementation_state import (
    ImplementationState,
    combine_implementation_states,
)
from tslc.support_policy import DEFAULT_SUPPORT_POLICY


def _cpp_variant_names(
    specializations: tuple[LoweredSpecialization, ...]
) -> tuple[str, ...]:
    return _variant_names(
        tuple(
            branch
            for specialization in specializations
            for branch in specialization.compiler_branches
        )
    )


def _cpp_compiler_condition(
    specialization: LoweredSpecialization,
) -> str | None:
    macros = tuple(
        cpp_compiler_capability(capability_id).condition_macro
        for capability_id in sorted(
            specialization.required_compiler_capabilities
        )
    )
    return " && ".join(macros) if macros else None


def _cpp_compiler_diagnostic(
    specializations: tuple[LoweredSpecialization, ...],
) -> str:
    capability_ids = sorted(
        {
            capability_id
            for specialization in specializations
            for capability_id in specialization.required_compiler_capabilities
        }
    )
    return "; ".join(
        cpp_compiler_capability(capability_id).diagnostic
        for capability_id in capability_ids
    )


def _cpp_precondition_error(error: PreconditionErrorKind) -> str:
    return cpp_precondition_error(error)


def _cpp_checked_failure(
    condition: CheckedConditionPlan,
    plan: CppCheckedApiPlan,
    *,
    indent: str,
    error_expression: str | None = None,
) -> str:
    error = error_expression or _cpp_precondition_error(condition.error)
    if not plan.has_value_result:
        return f"{indent}return {error};"
    if plan.failure_placeholder_expression is None:
        raise ValueError("C++ checked value result requires a failure placeholder")
    return (
        f"{indent}{plan.error_parameter_name} = {error};\n"
        f"{indent}return {plan.failure_placeholder_expression};"
    )


def _cpp_checked_condition(
    condition: CheckedConditionPlan,
    plan: CppCheckedApiPlan,
) -> str:
    if condition.kind is PreconditionKind.LANE_INDEX_IN_RANGE:
        return (
            f"    if ({condition.parameter_name} >= Vec::lane_count()) {{\n"
            f"{_cpp_checked_failure(condition, plan, indent='        ')}\n"
            "    }"
        )
    if condition.kind is not PreconditionKind.ACTIVE_DIVISOR_NONZERO:
        if condition.kind is PreconditionKind.CONTIGUOUS_MEMORY_EXTENT:
            if (
                plan.memory_parameter_name is None
                or plan.required_extent_expression is None
            ):
                raise ValueError("C++ checked extent has no finalized range plan")
            return (
                f"    if ({plan.memory_parameter_name}.size() < "
                f"{plan.required_extent_expression}) {{\n"
                f"{_cpp_checked_failure(condition, plan, indent='        ')}\n"
                "    }"
            )
        if condition.kind is PreconditionKind.SELECTED_MEMORY_ALIGNMENT:
            if (
                plan.memory_parameter_name is None
                or plan.required_alignment_expression is None
                or plan.alignment_parameter_name is None
            ):
                raise ValueError("C++ checked alignment has no finalized range plan")
            return (
                f"    if constexpr ({plan.alignment_parameter_name}) {{\n"
                f"        if ((reinterpret_cast<std::uintptr_t>("
                f"{plan.memory_parameter_name}.data()) % "
                f"{plan.required_alignment_expression}) != 0) {{\n"
                f"{_cpp_checked_failure(condition, plan, indent='            ')}\n"
                "        }\n"
                "    }"
            )
        if condition.kind is PreconditionKind.INDEXED_MEMORY_ADDRESS_VALID:
            if (
                plan.memory_parameter_name is None
                or condition.index_parameter_name is None
                or condition.scale_parameter_name is None
            ):
                raise ValueError("C++ checked indexed memory plan is incomplete")
            if (
                PreconditionCheckPrimitive.VECTOR_TO_ARRAY
                not in condition.check_primitives
            ):
                raise ValueError("indexed-memory check plan has no to-array primitive")
            active = "true"
            active_setup: tuple[str, ...] = ()
            if condition.mask_parameter_name is not None:
                required_mask_primitives = {
                    PreconditionCheckPrimitive.MASK_FALSE,
                    PreconditionCheckPrimitive.MASK_SET_LANE,
                    PreconditionCheckPrimitive.MASK_AND,
                    PreconditionCheckPrimitive.MASK_POPULATION_COUNT,
                }
                if not required_mask_primitives.issubset(
                    condition.check_primitives
                ):
                    raise ValueError(
                        "masked indexed-memory check plan lacks mask primitives"
                    )
                active_setup = (
                    "            auto const __tsl_lane_mask = "
                    "::tsl::set_mask_lane<Vec>(",
                    "                ::tsl::mask_false<Vec>(), __tsl_lane, 1);",
                    "            auto const __tsl_active = "
                    "::tsl::mask_population_count<Vec>(",
                    "                ::tsl::mask_binary_and<Vec>("
                    f"{condition.mask_parameter_name}, __tsl_lane_mask)) != 0;",
                )
                active = "__tsl_active"
            return "\n".join(
                (
                    "    {",
                    "        auto const __tsl_indices = "
                    f"::tsl::to_array<IndicesType>({condition.index_parameter_name});",
                    "        for (std::size_t __tsl_lane = 0; "
                    "__tsl_lane < IndicesType::lane_count(); ++__tsl_lane) {",
                    *active_setup,
                    f"            if ({active}) {{",
                    "                auto const __tsl_error = "
                    "::tsl::detail::indexed_memory_address_error<"
                    "typename Vec::base_type>(",
                    "                    __tsl_indices[__tsl_lane], "
                    f"{condition.scale_parameter_name}, "
                    f"{plan.memory_parameter_name}.size());",
                    "                if (__tsl_error != "
                    "::tsl::precondition_error::none) {",
                    _cpp_checked_failure(
                        condition,
                        plan,
                        indent="                    ",
                        error_expression="__tsl_error",
                    ),
                    "                }",
                    "            }",
                    "        }",
                    "    }",
                )
            )
        if condition.kind is PreconditionKind.COMPACTED_MEMORY_EXTENT:
            if (
                plan.memory_parameter_name is None
                or condition.mask_parameter_name is None
            ):
                raise ValueError("C++ checked compacted memory plan is incomplete")
            if (
                PreconditionCheckPrimitive.MASK_POPULATION_COUNT
                not in condition.check_primitives
            ):
                raise ValueError(
                    "compacted-memory check plan has no mask population primitive"
                )
            return (
                f"    if ({plan.memory_parameter_name}.size() < "
                f"::tsl::mask_population_count<Vec>("
                f"{condition.mask_parameter_name})) {{\n"
                f"{_cpp_checked_failure(condition, plan, indent='        ')}\n"
                "    }"
            )
        raise ValueError(f"unsupported C++ checked condition {condition.kind.value!r}")
    required = {
        PreconditionCheckPrimitive.ZERO_VECTOR,
        PreconditionCheckPrimitive.EQUAL,
        PreconditionCheckPrimitive.MASK_POPULATION_COUNT,
    }
    if not required.issubset(condition.check_primitives):
        raise ValueError("zero-divisor check plan is missing support primitives")
    lines = [
        "    if constexpr (std::is_integral_v<typename Vec::base_type>) {",
        "        auto zero_divisors = ::tsl::equal<Vec>(",
        f"            {condition.parameter_name}, ::tsl::set_zero<Vec>());",
    ]
    checked_mask = "zero_divisors"
    if condition.mask_parameter_name is not None:
        if PreconditionCheckPrimitive.MASK_AND not in condition.check_primitives:
            raise ValueError("masked zero-divisor check plan has no mask-and primitive")
        lines.extend(
            (
                "        auto active_zero_divisors = ::tsl::mask_binary_and<Vec>(",
                f"            {condition.mask_parameter_name}, zero_divisors);",
            )
        )
        checked_mask = "active_zero_divisors"
    lines.extend(
        (
            f"        if (::tsl::mask_population_count<Vec>({checked_mask}) != 0) {{",
            _cpp_checked_failure(condition, plan, indent="            "),
            "        }",
            "    }",
        )
    )
    return "\n".join(lines)


def _cpp_body_text(
    specialization: LoweredSpecialization,
    variant_name: str | None,
) -> str | None:
    branches = specialization.compiler_branches
    rendered = tuple(
        (branch, selected_body.render())
        for branch in branches
        if (selected_body := _body_for(branch, variant_name)) is not None
    )
    if not rendered:
        return None
    if len(rendered) == 1:
        branch, body_text = rendered[0]
        condition = _cpp_compiler_condition(branch)
        if condition is None:
            return body_text
        return (
            f"#if {condition}\n"
            f"{body_text}\n"
            "#else\n"
            f"#  error \"{_cpp_compiler_diagnostic((branch,))}\"\n"
            "#endif"
        )

    lines: list[str] = []
    has_fallback = False
    for branch, body_text in rendered:
        condition = _cpp_compiler_condition(branch)
        if condition is None:
            lines.extend(("#else", body_text))
            has_fallback = True
            break
        directive = "#if" if not lines else "#elif"
        lines.extend((f"{directive} {condition}", body_text))
    if not has_fallback:
        lines.extend(
            (
                "#else",
                f"#  error \"{_cpp_compiler_diagnostic(branches)}\"",
            )
        )
    lines.append("#endif")
    return "\n".join(lines)


class CppBackend:
    backend_id = "cpp"

    def render_primitive(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        # Declarations (impl primary template + wrapper) first, then the
        # specialization bodies — see render_declarations/render_definitions.
        return (
            self.render_declarations(primitive_name, specializations)
            + "\n\n"
            + self.render_definitions(primitive_name, specializations)
        )

    def render_declarations(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        """The impl primary template + the wrapper function template. Emitted for
        *every* primitive before any specialization body, so a body may call any
        other primitive's wrapper (``::tsl::set1<Vec>(...)``) regardless of order."""

        selectors = self.render_variant_selectors(primitive_name, specializations)
        implementations = self.render_implementation_declarations(
            primitive_name, specializations
        )
        wrappers = self.render_wrappers(primitive_name, specializations)
        return "\n\n".join(
            part for part in (selectors, implementations, wrappers) if part
        )

    def render_variant_selectors(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        """Render the stable default selector before an optional policy include."""

        variants = _cpp_variant_names(specializations)
        shape = specializations[0]
        if not variants or DEFAULT_SUPPORT_POLICY.is_free_function_signature(
            shape.result_kind,
            shape.param_kinds,
        ):
            return ""
        enum_values = ",\n".join(
            ("    default_", *(f"    {name}" for name in variants))
        )
        return (
            "namespace detail::variants {\n"
            f"enum class {variant_enum_name(primitive_name)} {{\n"
            f"{enum_values},\n"
            "};\n\n"
            f"template <{', '.join(_selector_template_params(shape, specializations))}>\n"
            f"struct {variant_selector_name(primitive_name)} {{\n"
            f"    static constexpr auto value = "
            f"{variant_enum_name(primitive_name)}::default_;\n"
            "};\n"
            "}  // namespace detail::variants"
        )

    def render_implementation_declarations(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        """Render detail implementation templates and their state query."""

        shape = specializations[0]  # all share the same signature shape + axis keys
        if DEFAULT_SUPPORT_POLICY.is_free_function_signature(
            shape.result_kind,
            shape.param_kinds,
        ):
            # A non-vector primitive: a plain prototype (the definition follows in
            # render_definitions), so a free function can still call any wrapper.
            return _free_function(shape, define=False)
        # A representation-change primitive carries a SECOND vector type (the target).
        # Its result kind projects through `ToVec`, which the caller binds.
        decl_params = "class Vec" + (
            ", class ToVec" if shape.target is not None else ""
        )
        # Free SIMD type params (gather's `IndicesType`) — a caller-bound vector type, like ToVec.
        decl_params += "".join(f", class {param.name}" for param in shape.type_params)
        decl_params += "".join(f", bool {_axis_name(k)}" for k, _ in shape.axis)
        if shape.immediate is not None:  # an `sImm` non-type template parameter
            decl_params += f", {shape.immediate[1]} {shape.immediate[0]}"
        # `generic_params` (e.g. `PreserveSign`) are free template params too (defaults go on
        # the wrapper, not the primary template).
        decl_params += "".join(f", {typ} {name}" for name, typ, _ in shape.generic_params)
        decl_params += "".join(
            f", class {_base_key_param_name(param)} = "
            f"::tsl::detail::base_type_dispatch_key_t<typename {param.name}::base_type>"
            for param in _specialized_base_type_params(shape)
        )
        variant_decls = "".join(
            f"template <{decl_params}>\nstruct {_impl_name(primitive_name, name)};\n"
            for name in _cpp_variant_names(specializations)
        )
        return (
            "namespace detail::primitives {\n"
            f"template <{decl_params}>\nstruct {_impl_name(primitive_name)};\n"
            f"{variant_decls}"
            "}  // namespace detail::primitives"
            + "\n\n"
            + _implementation_state_query(primitive_name, specializations)
        )

    def render_wrappers(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        """Render the public wrapper after policy specializations are visible."""

        shape = specializations[0]
        if DEFAULT_SUPPORT_POLICY.is_free_function_signature(
            shape.result_kind,
            shape.param_kinds,
        ):
            return ""
        ordinary = self._wrapper(primitive_name, specializations)
        checked = self._checked_wrapper(primitive_name, specializations, define=True)
        return "\n\n".join(part for part in (ordinary, checked) if part)

    def render_ordinary_wrappers(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        shape = specializations[0]
        if DEFAULT_SUPPORT_POLICY.is_free_function_signature(
            shape.result_kind, shape.param_kinds
        ):
            return ""
        return self._wrapper(primitive_name, specializations)

    def render_checked_wrappers(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        shape = specializations[0]
        if DEFAULT_SUPPORT_POLICY.is_free_function_signature(
            shape.result_kind, shape.param_kinds
        ):
            return ""
        return self._checked_wrapper(primitive_name, specializations, define=True)

    def render_definitions(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        """The `simd<>` specializations. Specs are grouped by `simd<>` + axis; an
        overloaded primitive (several signatures, e.g. store's `(ptr,v)`/`(ptr,s)`)
        emits one `apply` per signature in that group, resolved by C++ overloading."""

        shape = specializations[0]
        if DEFAULT_SUPPORT_POLICY.is_free_function_signature(
            shape.result_kind,
            shape.param_kinds,
        ):
            return _free_function(shape, define=True)
        groups: dict[tuple, list[LoweredSpecialization]] = {}
        order: list[tuple] = []
        for spec in specializations:
            # A representation-change primitive keys on the target too: same-source different-
            # target specs are distinct specializations (`si8->ui8` vs `si8->si8`), not one group.
            key = (
                spec.base_type_spelling,
                spec.extension_name,
                spec.axis,
                spec.target.vector_spelling if spec.target else None,
                _type_param_base_bindings(spec),
            )
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append(spec)
        definitions_by_group: list[str] = []
        for key in order:
            group = groups[key]
            definitions_by_group.append(self._specialization(group))
            definitions_by_group.extend(
                rendered
                for name in _cpp_variant_names(tuple(group))
                if (
                    rendered := self._specialization(group, variant_name=name)
                )
            )
        definitions = "\n\n".join(definitions_by_group)
        return (
            "namespace detail::primitives {\n"
            f"{definitions}\n"
            "}  // namespace detail::primitives"
        )

    def render_documentation_api_declaration(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        """Render the public C++ API as a documentation-only declaration."""

        shape = specializations[0]
        if DEFAULT_SUPPORT_POLICY.is_free_function_signature(
            shape.result_kind,
            shape.param_kinds,
        ):
            return _free_function(shape, define=False)
        ordinary = self._wrapper_declaration(primitive_name, specializations)
        checked = self._checked_wrapper(primitive_name, specializations, define=False)
        return "\n\n".join(part for part in (ordinary, checked) if part)

    def _checked_wrapper(
        self,
        primitive_name: str,
        specializations: tuple[LoweredSpecialization, ...],
        *,
        define: bool,
    ) -> str:
        signature = _wrapper_signature(specializations)
        plan = plan_cpp_checked_api(
            specializations,
            result_kind=signature.result_kind,
            result_type=signature.result_type,
        )
        if plan is None:
            return ""
        doc = _cpp_doc(
            specializations[0],
            context="C++ checked wrapper",
            concrete=False,
            checked=True,
            specializations=specializations,
        )
        params = _cpp_checked_parameters(specializations[0], signature, plan)
        template_params = signature.template_params + (
            (plan.template_constraint,) if plan.template_constraint is not None else ()
        )
        head = (
            f"template <{', '.join(template_params)}>\n"
            f"{plan.inline_specifier} auto {primitive_name}_checked({params}) "
            f"noexcept -> {plan.public_result_type}"
        )
        prefix = f"{doc}\n" if doc else ""
        if not define:
            return prefix + head + ";"
        checks = "\n".join(
            _cpp_checked_condition(condition, plan) for condition in plan.conditions
        )
        call = (
            f"::tsl::{primitive_name}<{signature.impl_args}>"
            f"({_cpp_checked_arguments(specializations[0], signature, plan)})"
        )
        success = (
            f"    {plan.error_parameter_name} = {plan.success_error_expression};\n"
            f"    return {call};"
            if plan.has_value_result
            else f"    {call};\n    return {plan.success_error_expression};"
        )
        return prefix + (
            f"{head} {{\n"
            f"{checks}\n"
            f"{success}\n"
            "}"
        )

    def documentation_register_type(self, spec: LoweredSpecialization) -> str:
        return _cpp_register_doc(spec)

    def documentation_target_register_type(self, spec: LoweredSpecialization) -> str:
        return _cpp_target_register_doc(spec)
    def _specialization(
        self,
        group: list[LoweredSpecialization],
        *,
        variant_name: str | None = None,
    ) -> str:
        first = group[0]
        # A sized vector is parameterized by its lane parameter, so it emits as a partial
        # specialization rather than a full specialization.
        # Free template params of the (partial) specialization: the sized vector's lane parameter
        # and an `sImm` immediate (both unbound, so they appear in the head AND the key);
        # concrete axis values are bound literals (key only).
        free: list[str] = []
        vec = _vector_type(first)
        # A monomorphized slot (numeric `lane_parameter`) is a full specialization over a concrete
        # `generic<16>`, so it adds no lane template parameter; a `LANES`-parametric sized vector
        # adds the unbound lane param to the (partial-specialization) head.
        lane_parameter = first.lane_parameter
        if (
            first.uses_sized_vector
            and lane_parameter is not None
            and not lane_parameter.isdigit()
        ):
            free.append(f"std::size_t {lane_parameter}")
        if first.immediate is not None:
            free.append(f"{first.immediate[1]} {first.immediate[0]}")
        # Free SIMD type params are unbound in the (partial) specialization — head AND key.
        free += [f"class {param.name}" for param in first.type_params]
        free += [f"{typ} {name}" for name, typ, _ in first.generic_params]
        head = f"template <{', '.join(free)}>" if free else "template <>"
        # A boolean-wildcard attribute keys the specialization so both variants coexist.
        # A representation-change primitive keys on (source, target) so each target is its
        # own specialization (`reinterpret_impl<simd<i32,avx2>, simd<u32,avx2>>`).
        key = vec
        if first.target is not None:
            key += f", {first.target.vector_spelling}"
        key += "".join(f", {param.name}" for param in first.type_params)
        key += "".join(f", {value}" for _, value in first.axis)
        if first.immediate is not None:
            key += f", {first.immediate[0]}"
        key += "".join(f", {name}" for name, _, _ in first.generic_params)
        key += "".join(
            f", {_cpp_base_dispatch_key_tag(param.base_type_binding)}"
            for param in _specialized_base_type_params(first)
            if param.base_type_binding is not None
        )
        applies: list[str] = []
        seen: set[tuple[str, ...]] = set()
        for spec in group:
            body = _cpp_body_text(spec, variant_name)
            if body is None:
                continue
            # Dedup overloads that collapse to the same parameter types (a `v` and an
            # `s` parameter are identical where register_type == base_type, i.e. scalar).
            signature = effective_param_types(spec)
            if signature in seen:
                continue
            seen.add(signature)
            index_type = spec.type_params[0].name if spec.type_params else None
            parameter_attribute = (
                "[[maybe_unused]] "
                if spec.primitive_semantics.preconditions
                else ""
            )
            params = ", ".join(
                f"{parameter_attribute}"
                f"{_param_type_for(spec, i, kind, index_type)} {name}"
                for i, (name, kind) in enumerate(
                    zip(spec.param_names, spec.param_kinds)
                )
                if kind != DEFAULT_SUPPORT_POLICY.immediate_kind
            )
            doc_context = (
                "C++ specialization"
                if variant_name is None
                else f"C++ specialization variant {variant_name}"
            )
            doc = _cpp_doc(spec, context=doc_context, indent="    ")
            prefix = f"{doc}\n" if doc else ""
            preconditions = _cpp_arithmetic_preconditions(spec)
            applies.append(
                f"{prefix}"
                f"    static inline {_apply_result_type(spec)} apply({params}) {{\n"
                f"{preconditions}"
                f"        {body}\n"
                f"    }}"
            )
        if not applies:
            return ""
        # A representation-change spec exposes `ToVec` (the target vector) in the impl so a
        # target-owned params and the result can project through it.
        to_vec = (
            f"    using ToVec = {first.target.vector_spelling};\n"
            if first.target is not None
            else ""
        )
        return (
            f"{head}\nstruct {_impl_name(first.primitive_name, variant_name)}<{key}> {{\n"
            f"    static constexpr ::tsl::implementation_state implementation_state = "
            f"{_cpp_implementation_state(_group_implementation_state(group, variant_name))};\n"
            f"    using Vec = {vec};\n" + to_vec + "\n".join(applies) + "\n};"
        )

    def _wrapper(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        signature = _wrapper_signature(specializations)
        doc = _cpp_doc(
            specializations[0],
            context="C++ wrapper",
            concrete=False,
            specializations=specializations,
        )
        prefix = f"{doc}\n" if doc else ""
        variants = _cpp_variant_names(specializations)
        selector = (
            f"    using selector = ::tsl::detail::variants::"
            f"{variant_selector_name(primitive_name)}<{signature.selector_args}>;\n"
            if variants
            else ""
        )
        variant_dispatch = "".join(
            "    if constexpr (selector::value == "
            f"::tsl::detail::variants::{variant_enum_name(primitive_name)}::{name}) {{\n"
            f"        return ::tsl::detail::primitives::{_impl_name(primitive_name, name)}"
            f"<{signature.impl_args}>::apply({signature.argument_names});\n"
            "    }\n"
            for name in variants
        )
        vector_wrapper = (
            prefix
            + f"template <{', '.join(signature.template_params)}>\n"
            f"inline {signature.result_type} {primitive_name}({signature.params}) {{\n"
            f"{selector}"
            f"{variant_dispatch}"
            f"    return ::tsl::detail::primitives::{_impl_name(primitive_name)}"
            f"<{signature.impl_args}>::apply("
            f"{signature.argument_names});\n"
            f"}}"
        )
        policy_wrapper = _dataparallel_primitive_facade_wrapper(
            primitive_name, specializations, define=True
        )
        if policy_wrapper:
            return vector_wrapper + "\n\n" + policy_wrapper
        return vector_wrapper

    def _wrapper_declaration(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        signature = _wrapper_signature(specializations)
        doc = _cpp_doc(
            specializations[0],
            context="C++ wrapper",
            concrete=False,
            specializations=specializations,
        )
        prefix = f"{doc}\n" if doc else ""
        vector_declaration = (
            prefix
            + f"template <{', '.join(signature.template_params)}>\n"
            f"{signature.result_type} {primitive_name}({signature.params});"
        )
        policy_declaration = _dataparallel_primitive_facade_wrapper(
            primitive_name, specializations, define=False
        )
        if policy_declaration:
            return vector_declaration + "\n\n" + policy_declaration
        return vector_declaration


@dataclass(frozen=True, slots=True)
class _WrapperSignature:
    template_params: tuple[str, ...]
    params: str
    argument_names: str
    parameter_declarations: tuple[str, ...]
    runtime_argument_names: tuple[str, ...]
    impl_args: str
    selector_args: str
    result_type: str
    result_kind: str


def _cpp_checked_parameters(
    shape: LoweredSpecialization,
    signature: _WrapperSignature,
    plan: CppCheckedApiPlan,
) -> str:
    runtime_indexes = tuple(
        index
        for index, kind in enumerate(shape.param_kinds)
        if kind != DEFAULT_SUPPORT_POLICY.immediate_kind
    )
    declarations: list[str] = []
    for index, declaration in zip(
        runtime_indexes, signature.parameter_declarations, strict=True
    ):
        if index != plan.memory_parameter_index:
            declarations.append(declaration)
            continue
        if plan.memory_parameter_name is None or plan.memory_access is None:
            raise ValueError("C++ checked memory parameter is incomplete")
        element = (
            "typename Vec::base_type const"
            if plan.memory_access is MemoryAccess.READ
            else "typename Vec::base_type"
        )
        declarations.append(
            f"::tsl::span<{element}> {plan.memory_parameter_name}"
        )
    if plan.error_parameter_declaration is not None:
        declarations.append(plan.error_parameter_declaration)
    return ", ".join(declarations)


def _cpp_checked_arguments(
    shape: LoweredSpecialization,
    signature: _WrapperSignature,
    plan: CppCheckedApiPlan,
) -> str:
    runtime_indexes = tuple(
        index
        for index, kind in enumerate(shape.param_kinds)
        if kind != DEFAULT_SUPPORT_POLICY.immediate_kind
    )
    return ", ".join(
        f"{name}.data()" if index == plan.memory_parameter_index else name
        for index, name in zip(
            runtime_indexes, signature.runtime_argument_names, strict=True
        )
    )


def _wrapper_signature(
    specializations: tuple[LoweredSpecialization, ...],
) -> _WrapperSignature:
    shape = specializations[0]
    # Positions whose parameter kind differs across signatures are the overload's
    # dispatch points: they become generic template params so C++ resolves the call.
    varying = varying_positions(specializations)
    immediate_params = (
        [f"{shape.immediate[1]} {shape.immediate[0]}"]
        if shape.immediate is not None
        else []
    )
    has_target = shape.target is not None
    index_type = shape.type_params[0].name if shape.type_params else None
    axis_defaults = {
        key: (
            "false"
            if "false"
            in {
                dict(specialization.axis)[key]
                for specialization in specializations
                if key in dict(specialization.axis)
            }
            else value
        )
        for key, value in shape.axis
    }
    template_params = (
        ["class Vec"]
        + (["class ToVec"] if has_target else [])
        + [f"class {param.name}" for param in shape.type_params]
        + [
            f"bool {_axis_name(key)} = {axis_defaults[key]}"
            for key, _ in shape.axis
        ]
        + immediate_params
        + [f"{typ} {name} = {default}" for name, typ, default in shape.generic_params]
        + [f"class Arg{i}" for i in varying]
    )
    parameter_declarations = tuple(
        (
            f"Arg{i} {name}"
            if i in varying
            else f"{_param_type_for(shape, i, kind, index_type)} {name}"
        )
        for i, (name, kind) in enumerate(zip(shape.param_names, shape.param_kinds))
        if kind != DEFAULT_SUPPORT_POLICY.immediate_kind
    )
    runtime_argument_names = tuple(
        name
        for name, kind in zip(shape.param_names, shape.param_kinds)
        if kind != DEFAULT_SUPPORT_POLICY.immediate_kind
    )
    params = ", ".join(parameter_declarations)
    names = ", ".join(runtime_argument_names)
    impl_args = (
        "Vec"
        + (", ToVec" if has_target else "")
        + "".join(f", {param.name}" for param in shape.type_params)
        + "".join(f", {_axis_name(k)}" for k, _ in shape.axis)
        + (f", {shape.immediate[0]}" if shape.immediate is not None else "")
        + "".join(f", {name}" for name, _, _ in shape.generic_params)
    )
    selector_parameter_types = tuple(f"Arg{i}" for i in varying)
    selector_args = impl_args + "".join(
        f", {parameter_type}" for parameter_type in selector_parameter_types
    )
    # The result projects through either the concrete target axis or a source-declared
    # caller-bound SIMD type parameter.
    result_owner = "ToVec" if has_target else shape.result_vector_param
    result_type = (
        CPP_SIGNATURE_TYPES.member_type(shape.result_kind, vector=result_owner)
        if result_owner is not None
        else _result_type(shape.result_kind)
    )
    return _WrapperSignature(
        template_params=tuple(template_params),
        params=params,
        argument_names=names,
        parameter_declarations=parameter_declarations,
        runtime_argument_names=runtime_argument_names,
        impl_args=impl_args,
        selector_args=selector_args,
        result_type=result_type,
        result_kind=shape.result_kind,
    )


def _selector_template_params(
    shape: LoweredSpecialization,
    specializations: tuple[LoweredSpecialization, ...],
) -> tuple[str, ...]:
    params = ["class Vec"]
    if shape.target is not None:
        params.append("class ToVec")
    params.extend(f"class {param.name}" for param in shape.type_params)
    params.extend(f"bool {_axis_name(key)}" for key, _ in shape.axis)
    if shape.immediate is not None:
        params.append(f"{shape.immediate[1]} {shape.immediate[0]}")
    params.extend(f"{typ} {name}" for name, typ, _ in shape.generic_params)
    params.extend(f"class Arg{index}" for index in varying_positions(specializations))
    return tuple(params)


def _dataparallel_primitive_facade_wrapper(
    primitive_name: str,
    specializations: tuple[LoweredSpecialization, ...],
    *,
    define: bool,
) -> str:
    facade = classify_dataparallel_primitive_facade(primitive_name, specializations)
    if facade is None:
        return ""
    if facade.kind is DataparallelPrimitiveFacadeKind.CONTIGUOUS_MEMORY:
        return _dataparallel_memory_facade_wrapper(facade, define=define)

    shape = facade.shape
    source_type = "FromT" if shape.target is not None else "T"
    vec = f"::tsl::dataparallel::simd_for_t<Policy, {source_type}>"
    target_vec = (
        f"::tsl::dataparallel::rebind_base_t<{vec}, ToT>"
        if shape.target is not None
        else None
    )
    result_type = _dataparallel_facade_result_type(
        shape.result_kind, target_vec or vec
    )
    params = ", ".join(
        f"{_dataparallel_facade_param_type(kind, vec, target_vec)} {name}"
        for name, kind in zip(shape.param_names, shape.param_kinds)
    )
    template_params = (
        "class Policy, class FromT, class ToT"
        if shape.target is not None
        else "class Policy, class T"
    )
    impl_args = vec + (f", {target_vec}" if target_vec is not None else "")
    signature = (
        f"template <{template_params}>\n"
        f"inline {result_type} {primitive_name}({params})"
    )
    if not define:
        return signature + ";"
    return (
        signature
        + " {\n"
        f"    return ::tsl::{primitive_name}<{impl_args}>({', '.join(shape.param_names)});\n"
        "}"
    )


def _dataparallel_memory_facade_wrapper(
    facade: DataparallelPrimitiveFacade,
    *,
    define: bool,
) -> str:
    shape = facade.shape
    primitive_name = facade.primitive_name
    vec = "::tsl::dataparallel::simd_for_t<Policy, T>"
    if facade.alignment_axis_name is None:
        raise ValueError("contiguous-memory facade has no alignment axis")
    axis_name = _axis_name(facade.alignment_axis_name)
    result_type = _dataparallel_facade_result_type(shape.result_kind, vec)
    params = ", ".join(
        f"{_dataparallel_facade_param_type(kind, vec, None)} {name}"
        for name, kind in zip(shape.param_names, shape.param_kinds)
    )
    signature = (
        f"template <class Policy, class T, bool {axis_name} = false>\n"
        f"inline {result_type} {primitive_name}({params})"
    )
    if not define:
        return signature + ";"
    call = (
        f"::tsl::{primitive_name}<{vec}, {axis_name}>"
        f"({', '.join(shape.param_names)})"
    )
    if shape.result_kind == "void":
        return signature + " {\n" f"    {call};\n" "}"
    return signature + " {\n" f"    return {call};\n" "}"


def _dataparallel_facade_result_type(result_kind: str, vec: str) -> str:
    return CPP_SIGNATURE_TYPES.member_type(result_kind, vector=vec)


def _dataparallel_facade_param_type(
    param_kind: str, vec: str, target_vec: str | None
) -> str:
    vector = (
        target_vec
        if DEFAULT_SUPPORT_POLICY.is_target_vector_parameter_kind(param_kind)
        and target_vec is not None
        else vec
    )
    return CPP_SIGNATURE_TYPES.member_parameter_type(param_kind, vector=vector)


def _free_function(spec: LoweredSpecialization, *, define: bool) -> str:
    """A non-vector primitive (`allocate`/`deallocate`): a plain `inline` function in the `tsl`
    namespace, not a `simd<>`-templated wrapper. `define=False` emits just the prototype (so a
    free function may call any wrapper regardless of emission order); `define=True` adds the body."""

    params = ", ".join(
        f"{_free_kind_type(kind, spec)} {name}"
        for name, kind in zip(spec.param_names, spec.param_kinds)
    )
    signature = (
        f"inline {_free_kind_type(spec.result_kind, spec)} "
        f"{spec.primitive_name}({params})"
    )
    doc = _cpp_doc(spec, context="C++ free function")
    if not define:
        prefix = f"{doc}\n" if doc else ""
        return f"{prefix}{signature};"
    return f"{signature} {{\n    {_cpp_body_text(spec, None) or ''}\n}}"


def _implementation_state_query(
    primitive_name: str,
    specializations: tuple[LoweredSpecialization, ...],
) -> str:
    shape = specializations[0]
    params = ["class Vec"]
    query_args = [f"primitive::{primitive_name}", "Vec"]
    impl_args = ["Vec"]
    if shape.target is not None:
        params.append("class ToVec")
        query_args.append("ToVec")
        impl_args.append("ToVec")
    for param in shape.type_params:
        params.append(f"class {param.name}")
        query_args.append(param.name)
        impl_args.append(param.name)
    for key, _value in shape.axis:
        name = _axis_name(key)
        params.append(f"bool {name}")
        query_args.append(f"value_arg<{name}>")
        impl_args.append(name)
    if shape.immediate is not None:
        name, typ = shape.immediate
        params.append(f"{typ} {name}")
        query_args.append(f"value_arg<{name}>")
        impl_args.append(name)
    for name, typ, _default in shape.generic_params:
        params.append(f"{typ} {name}")
        query_args.append(f"value_arg<{name}>")
        impl_args.append(name)
    variants = _cpp_variant_names(specializations)
    varying = varying_positions(specializations)
    if variants:
        selector_params = tuple(f"Arg{index}" for index in varying)
        selector = (
            f"detail::variants::{variant_selector_name(primitive_name)}"
            f"<{', '.join((*impl_args, *selector_params))}>"
        )
        variant_states = "".join(
            f"        if constexpr ({selector}::value == "
            f"detail::variants::{variant_enum_name(primitive_name)}::{name}) {{\n"
            f"            return detail::primitives::{_impl_name(primitive_name, name)}"
            f"<{', '.join(impl_args)}>::implementation_state;\n"
            "        }\n"
            for name in variants
        )
        value_body = (
            "    static constexpr implementation_state selected_value() {\n"
            f"{variant_states}"
            f"        return detail::primitives::{_impl_name(primitive_name)}"
            f"<{', '.join(impl_args)}>::implementation_state;\n"
            "    }\n"
            "    static constexpr implementation_state value = selected_value();\n"
        )
    else:
        value_body = (
            "    static constexpr implementation_state value = "
            f"detail::primitives::{_impl_name(primitive_name)}"
            f"<{', '.join(impl_args)}>::implementation_state;\n"
        )
    query = (
        f"template <{', '.join(params)}>\n"
        f"struct implementation_state_of<{', '.join(query_args)}> {{\n"
        f"{value_body}"
        f"}};"
    )
    if not variants or not varying:
        return query
    default_query = (
        f"template <{', '.join(params)}>\n"
        f"struct implementation_state_of<{', '.join(query_args)}> {{\n"
        "    static constexpr implementation_state value = "
        f"detail::primitives::{_impl_name(primitive_name)}"
        f"<{', '.join(impl_args)}>::implementation_state;\n"
        "};"
    )
    overload_params = (*params, *(f"class {name}" for name in selector_params))
    overload_query_args = (*query_args, *selector_params)
    overload_query = (
        f"template <{', '.join(overload_params)}>\n"
        f"struct implementation_state_of<{', '.join(overload_query_args)}> {{\n"
        f"{value_body}"
        "};"
    )
    return default_query + "\n\n" + overload_query


def _group_implementation_state(
    group: list[LoweredSpecialization],
    variant_name: str | None,
) -> ImplementationState:
    states: list[ImplementationState] = []
    for spec in group:
        if variant_name is None:
            states.append(spec.implementation_state)
            continue
        for variant in spec.variant_bodies:
            if variant.name == variant_name:
                states.append(variant.implementation_state)
    return combine_implementation_states(states)


def _cpp_implementation_state(state: ImplementationState) -> str:
    return f"::tsl::implementation_state::{state.value}"


def _impl_name(primitive_name: str, variant_name: str | None = None) -> str:
    return implementation_name(primitive_name, variant_name)


def implementation_name(
    primitive_name: str, variant_name: str | None = None
) -> str:
    if variant_name is None:
        return f"{primitive_name}_impl"
    return f"{primitive_name}_impl_{variant_name}"


def variant_enum_name(primitive_name: str) -> str:
    return f"{primitive_name}_variant"


def variant_selector_name(primitive_name: str) -> str:
    return f"{primitive_name}_selector"


def _specialized_base_type_params(
    spec: LoweredSpecialization,
) -> tuple[LoweredTypeParam, ...]:
    return tuple(param for param in spec.type_params if param.specialize_base)


def _type_param_base_bindings(spec: LoweredSpecialization) -> tuple[tuple[str, str | None], ...]:
    return tuple(
        (param.name, param.base_type_binding)
        for param in _specialized_base_type_params(spec)
    )


def _base_key_param_name(param: LoweredTypeParam) -> str:
    return f"{param.name}BaseKey"


def _cpp_base_dispatch_key_tag(base_tag: str | None) -> str:
    if base_tag is None:
        return "void"
    return f"::tsl::detail::base_{base_tag}_tag"


def _free_kind_type(kind: str, spec: LoweredSpecialization) -> str:
    """A free function's kind -> concrete type (no `Vec` projection). Pointer spellings
    carry their own mutability; `usize` is a size; `void` is no value."""

    return CPP_SIGNATURE_TYPES.free_type(
        kind,
        base=spec.base_type_spelling,
        base_type_tag=spec.type_tag,
    )


def _vector_type(spec: LoweredSpecialization) -> str:
    if spec.vector_spelling is not None:
        return spec.vector_spelling
    if spec.uses_sized_vector:
        lane_parameter = spec.lane_parameter
        return (
            f"tsl::simd<{spec.base_type_spelling}, "
            f"tsl::{spec.extension_name}<{lane_parameter}>>"
        )
    return f"tsl::simd<{spec.base_type_spelling}, tsl::{spec.extension_name}>"


def _axis_name(key: str) -> str:
    """An axis attribute key as a C++ template-parameter name (`aligned` -> `Aligned`)."""

    return key[:1].upper() + key[1:]


def _apply_result_type(spec: LoweredSpecialization) -> str:
    """The `apply` result type, projected through the source or target vector."""

    if spec.target is not None:
        return CPP_SIGNATURE_TYPES.member_type(
            spec.result_kind,
            vector=spec.target.vector_spelling,
        )
    if spec.result_vector_param is not None:
        return CPP_SIGNATURE_TYPES.member_type(
            spec.result_kind,
            vector=spec.result_vector_param,
        )
    return _result_type(spec.result_kind)


def _cpp_arithmetic_preconditions(spec: LoweredSpecialization) -> str:
    return "".join(
        f"        {_cpp_arithmetic_precondition(precondition)}\n"
        for precondition in spec.arithmetic_preconditions
    )


def _cpp_arithmetic_precondition(
    precondition: LoweredArithmeticPrecondition,
) -> str:
    if (
        precondition.kind
        is LoweredArithmeticPreconditionKind.INTEGER_IMMEDIATE_NONZERO
    ):
        unsigned_type = f"std::uint{precondition.lane_bit_width}_t"
        return (
            f"static_assert(static_cast<{unsigned_type}>("
            f"{precondition.parameter_name}) != {unsigned_type}{{0}}, "
            f'"{precondition.marker}");'
        )
    raise AssertionError(f"unhandled arithmetic precondition {precondition.kind!r}")


def _result_type(kind: str) -> str:
    return CPP_SIGNATURE_TYPES.result_type(kind)


def _param_type(kind: str, index_type: str | None = None) -> str:
    return CPP_SIGNATURE_TYPES.parameter_type(
        kind,
        index_type=index_type,
        target_vector="ToVec",
    )


def _param_type_for(
    spec: LoweredSpecialization,
    index: int,
    kind: str,
    index_type: str | None = None,
) -> str:
    override = spec.effective_param_type_overrides[index]
    return override if override is not None else _param_type(kind, index_type)
