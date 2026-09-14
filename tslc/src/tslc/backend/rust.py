"""Rust backend: render a primitive as a trait + Simd<> impls + generic wrapper fn."""

from __future__ import annotations

from collections.abc import Mapping

from tslc.backend.checked_api import public_call_requires_unsafe
from tslc.backend.rust_checked_primitives import (
    render_checked_wrapper as _render_checked_wrapper,
    render_overloaded_checked_wrapper as _render_overloaded_checked_wrapper,
)
from tslc.backend.rust_direct_calls import (
    checked_free_function as _checked_free_function,
    checked_free_function_declaration as _checked_free_function_declaration,
    free_function as _free_function,
    free_function_declaration as _free_function_declaration,
)
from tslc.backend.rust_documentation_api import (
    documentation_checked_wrapper as _documentation_checked_wrapper,
    documentation_free_function as _documentation_free_function,
    documentation_overloaded_checked_wrapper as _documentation_overloaded_checked_wrapper,
    documentation_overloaded_wrapper as _documentation_overloaded_wrapper,
    documentation_wrapper as _documentation_wrapper,
)
from tslc.backend.rust_implementation_state import (
    render_implementation_state_queries as _implementation_state_queries,
)
from tslc.backend.rust_policy_selection import (
    RustPolicySelection,
    RustPolicySelectionProfile,
)
from tslc.backend.rust_primitive_implementations import (
    RustPrimitiveImplementationRenderer,
)
from tslc.backend.rust_primitive_wrappers import (
    render_overloaded_wrapper as _render_overloaded_wrapper,
    render_wrapper as _render_wrapper,
)
from tslc.backend.rust_primitive_declarations import (
    rust_checked_wrapper_declaration as _rust_checked_wrapper_declaration,
    rust_overloaded_wrapper_declaration as _rust_overloaded_wrapper_declaration,
    rust_wrapper_declaration as _rust_wrapper_declaration,
)
from tslc.backend.rust_public_declarations import RustPublicDeclaration
from tslc.backend.rust_type_params import (
    with_consistent_type_param_bounds as _with_consistent_type_param_bounds,
)
from tslc.benchmark.model import SpecializationKey
from tslc.lower.lowerer import LoweredSpecialization, varying_positions
from tslc.support_policy import DEFAULT_SUPPORT_POLICY


class RustBackend:
    backend_id = "rust"

    def __init__(
        self,
        *,
        feature_spellings: Mapping[str, str] | None = None,
        emit_target_features: bool = True,
        policy_selection: RustPolicySelectionProfile | None = None,
        deferred_policy_mapping_file: str | None = None,
    ) -> None:
        self._primitive_implementations = RustPrimitiveImplementationRenderer(
            feature_spellings=feature_spellings,
            emit_target_features=emit_target_features,
            policy_selection=policy_selection,
            deferred_policy_mapping_file=deferred_policy_mapping_file,
        )

    def render_primitive(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        internal = self.render_primitive_internal(primitive_name, specializations)
        public = self.render_primitive_public(primitive_name, specializations)
        if not internal:
            return public
        return "\n\n".join([self.render_primitive_module(internal), public])

    def render_primitive_module(self, internal: str) -> str:
        return self._primitive_implementations.render_primitive_module(internal)

    def render_policy_selection_impl(
        self,
        selection: RustPolicySelection,
    ) -> str:
        """Render one trusted mapping fragment from typed backend facts."""

        return self._primitive_implementations.render_policy_selection_impl(
            selection
        )

    def render_primitive_internal(
        self,
        primitive_name: str,
        specializations: tuple[LoweredSpecialization, ...],
    ) -> str:
        return self._primitive_implementations.render_primitive_internal(
            primitive_name, specializations
        )

    def render_primitive_public(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        specializations = _with_consistent_type_param_bounds(specializations)
        shape = specializations[0]
        if DEFAULT_SUPPORT_POLICY.is_free_function_signature(
            shape.result_kind,
            shape.param_kinds,
        ):
            # A non-vector primitive (`allocate`/`deallocate`): a plain `pub fn` in the module,
            # not a `SimdVector`-bound trait/impl/wrapper.
            return "\n\n".join(
                part
                for part in (
                    _free_function(
                        shape,
                        backend=self._primitive_implementations,
                    ),
                    _checked_free_function(shape),
                )
                if part
            )
        caller_unsafe = public_call_requires_unsafe(specializations)
        if varying_positions(specializations):
            ordinary = _render_overloaded_wrapper(
                primitive_name, specializations, caller_unsafe=caller_unsafe
            )
            checked = _render_overloaded_checked_wrapper(
                primitive_name, specializations
            )
            return "\n\n".join(part for part in (ordinary, checked) if part)
        ordinary = _render_wrapper(
            primitive_name, shape, caller_unsafe=caller_unsafe
        )
        checked = _render_checked_wrapper(primitive_name, specializations)
        return "\n\n".join(part for part in (ordinary, checked) if part)

    def public_declarations(
        self,
        primitive_name: str,
        specializations: tuple[LoweredSpecialization, ...],
        *,
        reachability: tuple[str, ...],
    ) -> tuple[RustPublicDeclaration, ...]:
        """Finalize the stable profile-callable declarations for one group."""

        specializations = _with_consistent_type_param_bounds(specializations)
        shape = specializations[0]
        if DEFAULT_SUPPORT_POLICY.is_free_function_signature(
            shape.result_kind, shape.param_kinds
        ):
            ordinary = _free_function_declaration(
                shape, reachability=reachability
            )
            checked = _checked_free_function_declaration(
                shape, reachability=reachability
            )
            return (ordinary,) if checked is None else (ordinary, checked)
        caller_unsafe = public_call_requires_unsafe(specializations)
        if varying_positions(specializations):
            overloaded_ordinary = _rust_overloaded_wrapper_declaration(
                primitive_name,
                specializations,
                checked=False,
                caller_unsafe=caller_unsafe,
                reachability=reachability,
            )
            overloaded_checked = _rust_overloaded_wrapper_declaration(
                primitive_name,
                specializations,
                checked=True,
                caller_unsafe=caller_unsafe,
                reachability=reachability,
            )
            assert overloaded_ordinary is not None
            return (
                (overloaded_ordinary,)
                if overloaded_checked is None
                else (overloaded_ordinary, overloaded_checked)
            )
        ordinary = _rust_wrapper_declaration(
            primitive_name,
            shape,
            caller_unsafe=caller_unsafe,
            reachability=reachability,
        )
        checked = _rust_checked_wrapper_declaration(
            primitive_name,
            specializations,
            reachability=reachability,
        )
        return (ordinary,) if checked is None else (ordinary, checked)

    def render_documentation_api(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        """Render one profile-neutral public API stub for rustdoc.

        The generated function preserves the public parameter, result, generic,
        safety, and documentation shape without depending on a profile-local
        dispatch trait or implementation body.
        """

        specializations = _with_consistent_type_param_bounds(specializations)
        shape = specializations[0]
        if DEFAULT_SUPPORT_POLICY.is_free_function_signature(
            shape.result_kind,
            shape.param_kinds,
        ):
            return "\n\n".join(
                part
                for part in (
                    _documentation_free_function(shape),
                    _checked_free_function(shape),
                )
                if part
            )
        caller_unsafe = public_call_requires_unsafe(specializations)
        if varying_positions(specializations):
            ordinary = _documentation_overloaded_wrapper(
                primitive_name,
                specializations,
                caller_unsafe=caller_unsafe,
            )
            checked = _documentation_overloaded_checked_wrapper(
                primitive_name, specializations
            )
            return "\n\n".join(part for part in (ordinary, checked) if part)
        ordinary = _documentation_wrapper(
            primitive_name,
            shape,
            caller_unsafe=caller_unsafe,
        )
        checked = _documentation_checked_wrapper(primitive_name, specializations)
        return "\n\n".join(part for part in (ordinary, checked) if part)

    def render_implementation_state_queries(
        self,
        by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    ) -> str:
        return _implementation_state_queries(
            {
                primitive_name: _with_consistent_type_param_bounds(specializations)
                for primitive_name, specializations in by_primitive.items()
            }
        )

    def concrete_vector_type(self, spec: LoweredSpecialization) -> str:
        """Spell the concrete Rust SIMD type selected for one specialization."""

        return self._primitive_implementations.concrete_vector_type(spec)

    def render_direct_implementation_call(
        self,
        spec: LoweredSpecialization,
        variant_name: str | None,
        arguments: tuple[str, ...],
        *,
        module_prefix: str = "",
        immediate_value: str | None = None,
        overload_parameter_positions: tuple[int, ...] = (),
        selection_key: SpecializationKey | None = None,
    ) -> str:
        """Render a direct call to one already-emitted implementation trait."""

        return self._primitive_implementations.render_direct_implementation_call(
            spec,
            variant_name,
            arguments,
            module_prefix=module_prefix,
            immediate_value=immediate_value,
            overload_parameter_positions=overload_parameter_positions,
            selection_key=selection_key,
        )
