"""Backend-decided C++ profile render model.

Everything decision-shaped about a generated C++ profile — header
partitioning, includes, SIMD registrations, compile guards, capability
grouping of definitions, and the smoke-test instantiation plan — is decided
here from ``EmittedProfile`` facts. ``tslc.render.cpp_project`` consumes the
resulting frozen values and only formats them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from tslc.backend.cpp_compiler_capabilities import (
    cpp_compiler_capability_header_defaults,
    cpp_extension_header_group,
    cpp_extensions_compiler_capabilities,
    used_cpp_compiler_capability_ids,
)
from tslc.backend.cpp_profile import (
    _cpp_compiler_builtin_fixed_registrations,
    _cpp_includes,
    _cpp_inferred_simd_registrations,
    _cpp_native_registration,
    _cpp_registration,
    _cpp_sized_registration,
    cpp_compiler_capability_condition,
    cpp_compiler_capability_diagnostic,
    cpp_extension_availability_condition,
    cpp_profiles_support_algorithm,
)
from tslc.backend.emitted_profile import EmittedProfile, used_extensions
from tslc.backend.target_capability import is_x86_register_extension
from tslc.catalog.model import Extension
from tslc.lower.lowerer import (
    LoweredArithmeticPreconditionKind,
    LoweredSpecialization,
    LoweredTypeParam,
    varying_positions,
)
from tslc.support_policy import DEFAULT_SUPPORT_POLICY


@dataclass(frozen=True, slots=True)
class CppProfileCompileGuard:
    """A decided profile-wide compile guard: condition plus author diagnostic."""

    condition: str
    diagnostic: str

    def guard(self, content: str) -> str:
        """Wrap finalized header content in this guard's preprocessor check."""

        return (
            f"#if {self.condition}\n"
            f"{content}"
            "#else\n"
            f'#  error "{self.diagnostic}"\n'
            "#endif\n"
        )


@dataclass(frozen=True, slots=True)
class CppDeclaredPrimitive:
    """One primitive whose selectors/declarations/wrappers a header declares."""

    name: str
    specializations: tuple[LoweredSpecialization, ...]


@dataclass(frozen=True, slots=True)
class CppDefinitionGroup:
    """Specialization definitions grouped under one availability condition."""

    primitive: str
    condition: str | None
    specializations: tuple[LoweredSpecialization, ...]


@dataclass(frozen=True, slots=True)
class CppSmokeInstantiation:
    """One decided smoke-test address-take.

    ``template_arguments`` is empty exactly for free functions (``allocate``/
    ``deallocate``), which are address-taken without a template argument list.
    ``lane_count`` (and ``target_lane_count`` for sized representation-change
    targets) records the concrete lane decision behind the argument spellings.
    """

    symbol: str
    template_arguments: tuple[str, ...]
    condition: str | None
    lane_count: int | None
    target_lane_count: int | None


@dataclass(frozen=True, slots=True)
class CppProfileHeader:
    """Decided content of one generated profile header and its smoke test."""

    header_group: str | None
    includes: str | None
    registrations: str
    declarations: tuple[CppDeclaredPrimitive, ...]
    definition_groups: tuple[CppDefinitionGroup, ...]
    guard: CppProfileCompileGuard | None
    smoke: tuple[CppSmokeInstantiation, ...]


@dataclass(frozen=True, slots=True)
class CppProfileRenderModel:
    """One profile's decided C++ headers: the base header, then overlay groups."""

    profile_name: str
    profile_family: str
    headers: tuple[CppProfileHeader, ...]

    @property
    def base_header(self) -> CppProfileHeader:
        return self.headers[0]

    @property
    def overlay_headers(self) -> tuple[CppProfileHeader, ...]:
        return self.headers[1:]


@dataclass(frozen=True, slots=True)
class CppProjectRenderModel:
    """All decided C++ project facts the profile/dispatch renderers format."""

    profiles: tuple[CppProfileRenderModel, ...]
    primitive_tag_declarations: str
    compiler_capability_defaults: str
    dispatch_header_groups: tuple[str, ...]
    supports_algorithm: bool


def cpp_project_render_model(
    profiles: tuple[EmittedProfile, ...],
) -> CppProjectRenderModel:
    """Decide every C++ profile-content fact from emitted backend profiles."""

    capability_ids = used_cpp_compiler_capability_ids(profiles)
    tag_names = sorted(
        {
            primitive
            for emitted_profile in profiles
            for primitive in emitted_profile.specializations("cpp")
        }
    )
    return CppProjectRenderModel(
        profiles=tuple(_cpp_profile_model(profile) for profile in profiles),
        primitive_tag_declarations="\n".join(
            f"struct {name} {{}};" for name in tag_names
        ),
        compiler_capability_defaults=(
            cpp_compiler_capability_header_defaults(capability_ids)
        ),
        dispatch_header_groups=tuple(
            sorted(
                {
                    group
                    for profile in profiles
                    for extension in profile.extensions.values()
                    if (group := cpp_extension_header_group(extension)) is not None
                }
            )
        ),
        supports_algorithm=cpp_profiles_support_algorithm(profiles),
    )


def _cpp_profile_model(emitted_profile: EmittedProfile) -> CppProfileRenderModel:
    all_specializations = emitted_profile.specializations("cpp")
    base = _cpp_specializations_for_group(
        all_specializations,
        emitted_profile.extensions,
        None,
    )
    headers = [_cpp_base_header(emitted_profile, all_specializations, base)]
    header_groups = sorted(
        {
            group
            for extension in emitted_profile.extensions.values()
            if (group := cpp_extension_header_group(extension)) is not None
        }
    )
    for header_group in header_groups:
        grouped = _cpp_specializations_for_group(
            all_specializations,
            emitted_profile.extensions,
            header_group,
        )
        if not grouped:
            continue
        headers.append(_cpp_overlay_header(emitted_profile, base, grouped, header_group))
    return CppProfileRenderModel(
        profile_name=emitted_profile.profile.name,
        profile_family=emitted_profile.profile.family,
        headers=tuple(headers),
    )


def _cpp_base_header(
    emitted_profile: EmittedProfile,
    all_specializations: Mapping[str, tuple[LoweredSpecialization, ...]],
    base: Mapping[str, tuple[LoweredSpecialization, ...]],
) -> CppProfileHeader:
    emitted_exts = used_extensions(base)
    x86_exts = [
        ext
        for ext in emitted_exts
        if is_x86_register_extension(emitted_profile.extensions.get(ext))
    ]
    registrations = "".join(
        _cpp_registration(ext, emitted_profile.extensions.get(ext))
        for ext in x86_exts
    )
    registrations += _cpp_sized_registration(emitted_exts, emitted_profile.extensions)
    registrations += _cpp_native_registration(base, emitted_profile.extensions)
    registrations += _cpp_inferred_simd_registrations(
        base, emitted_profile.extensions
    )
    return CppProfileHeader(
        header_group=None,
        includes=_cpp_includes(emitted_exts, emitted_profile.extensions),
        registrations=registrations,
        # The base header declares selectors/wrappers over EVERY specialization
        # of a base-declared primitive so overlay definitions bind to them.
        declarations=tuple(
            CppDeclaredPrimitive(name, all_specializations[name])
            for name in sorted(base)
        ),
        definition_groups=_cpp_definition_groups(base, emitted_profile.extensions),
        guard=_cpp_profile_compile_guard(
            emitted_exts,
            emitted_profile.extensions,
            header_group=None,
        ),
        smoke=_cpp_smoke_instantiations(emitted_profile, base),
    )


def _cpp_overlay_header(
    emitted_profile: EmittedProfile,
    base: Mapping[str, tuple[LoweredSpecialization, ...]],
    grouped: Mapping[str, tuple[LoweredSpecialization, ...]],
    header_group: str,
) -> CppProfileHeader:
    registrations = _cpp_native_registration(grouped, emitted_profile.extensions)
    registrations += _cpp_compiler_builtin_fixed_registrations(
        grouped,
        emitted_profile.extensions,
        header_group,
    )
    return CppProfileHeader(
        header_group=header_group,
        includes=None,
        registrations=registrations,
        declarations=tuple(
            CppDeclaredPrimitive(name, grouped[name])
            for name in sorted(grouped)
            if name not in base
        ),
        definition_groups=_cpp_definition_groups(
            grouped, emitted_profile.extensions
        ),
        guard=_cpp_profile_compile_guard(
            used_extensions(grouped),
            emitted_profile.extensions,
            header_group=header_group,
        ),
        smoke=_cpp_smoke_instantiations(emitted_profile, grouped),
    )


def _cpp_profile_compile_guard(
    emitted_exts: tuple[str, ...],
    extensions: Mapping[str, Extension],
    *,
    header_group: str | None,
) -> CppProfileCompileGuard | None:
    guards = tuple(
        capability
        for capability in cpp_extensions_compiler_capabilities(
            emitted_exts, extensions
        )
        if capability.header_group == header_group
    )
    if not guards:
        return None
    return CppProfileCompileGuard(
        condition=cpp_compiler_capability_condition(guards),
        diagnostic="; ".join(
            cpp_compiler_capability_diagnostic(guard) for guard in guards
        ),
    )


def _cpp_definition_groups(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    extensions: Mapping[str, Extension],
) -> tuple[CppDefinitionGroup, ...]:
    """Group primitive definitions under target-extension conditions."""

    groups: list[CppDefinitionGroup] = []
    for name in sorted(by_primitive):
        by_condition: dict[str | None, list[LoweredSpecialization]] = {}
        for specialization in by_primitive[name]:
            condition = _cpp_specialization_availability_condition(
                specialization,
                extensions,
            )
            by_condition.setdefault(condition, []).append(specialization)
        groups.extend(
            CppDefinitionGroup(name, condition, tuple(by_condition[condition]))
            for condition in sorted(by_condition, key=lambda value: value or "")
        )
    return tuple(groups)


def _cpp_specialization_availability_condition(
    specialization: LoweredSpecialization,
    extensions: Mapping[str, Extension],
) -> str | None:
    names = [specialization.extension_name]
    if specialization.target is not None:
        names.append(specialization.target.extension_isa)
    conditions = sorted(
        {
            condition
            for name in names
            for condition in (
                cpp_extension_availability_condition(extensions.get(name)),
            )
            if condition is not None
        }
    )
    return " && ".join(conditions) if conditions else None


def _cpp_smoke_instantiations(
    emitted_profile: EmittedProfile,
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
) -> tuple[CppSmokeInstantiation, ...]:
    """Address-take every emitted wrapper instantiation so the profile's bodies
    are fully compiled (with the profile's ISA flags), not merely parsed."""

    instantiations: list[CppSmokeInstantiation] = []
    available_specializations = frozenset(
        (
            specialization.source_primitive_name,
            specialization.extension_name,
            specialization.type_tag,
        )
        for specializations in by_primitive.values()
        for specialization in specializations
    )
    for name in sorted(by_primitive):
        specs = by_primitive[name]
        first = specs[0]
        if DEFAULT_SUPPORT_POLICY.is_free_function_signature(
            first.result_kind,
            first.param_kinds,
        ):
            # A free function (`allocate`/`deallocate`) is not a template — address-take it
            # directly (once), so its body is compiled under the profile's flags.
            instantiations.append(
                CppSmokeInstantiation(
                    symbol=f"tsl::{name}",
                    template_arguments=(),
                    condition=None,
                    lane_count=None,
                    target_lane_count=None,
                )
            )
            continue
        varying = varying_positions(specs)
        for spec in specs:
            if spec.uses_sized_vector:
                # A MONOMORPHIZED sized slot (numeric `lane_parameter`) only has that one concrete
                # instantiation — exercise it there. A `LANES`-parametric slot is exercised at 16
                # lanes: the sized substrate requires every vector's total width be a multiple of
                # 128 bits, and 16 * 8 (the narrowest lane type) = 128 — so 16 keeps BOTH the source
                # AND a width-changing lane-preserving target (e.g. a `cast` i16->i8) a whole number
                # of 128-bit registers, where a per-type `128 / typebits` would not.
                smoke_lanes = (
                    int(spec.lane_parameter)
                    if spec.lane_parameter and spec.lane_parameter.isdigit()
                    else 16
                )
                vec = _cpp_sized_vector_type(
                    spec.base_type_spelling,
                    spec.extension_name,
                    smoke_lanes,
                )
            else:
                smoke_lanes = 8
                vec = f"tsl::simd<{spec.base_type_spelling}, tsl::{spec.extension_name}>"
            # A sized-vector representation-change target is instantiated at a concrete lane count
            # matching the source's. A lane-PRESERVING target (cast/reinterpret, load_convert_up)
            # keeps the same count; a WINDOWING convert's count scales by the byte ratio — computed
            # from the source/target type widths (e.g. i8->i16 at 8 lanes -> 4), matching the impl
            # that deduces LANES from the source. Computed from typed widths, not a string rewrite.
            target_lanes: int | None = None
            if spec.target is None:
                target_spelling = None
            elif spec.target.uses_sized_vector:
                target_lanes = (
                    DEFAULT_SUPPORT_POLICY.windowed_lane_count(
                        spec.type_tag, spec.target.base_tag, smoke_lanes
                    )
                    if spec.target.windowed
                    else smoke_lanes
                )
                target_spelling = _cpp_sized_vector_type(
                    spec.target.base_spelling,
                    spec.target.extension_isa,
                    target_lanes,
                )
            else:
                target_spelling = spec.target.vector_spelling
            targs = (
                [vec]
                + ([target_spelling] if target_spelling else [])
                + [
                    _cpp_type_param_smoke_vector(
                        emitted_profile,
                        spec,
                        param,
                        smoke_lanes,
                        available_specializations,
                    )
                    for param in spec.type_params
                ]
                + [value for _, value in spec.axis]
                + ([_cpp_smoke_immediate(spec)] if spec.immediate is not None else [])
                + [default for _, _, default in spec.generic_params]
                + [_cpp_concrete_arg_type(vec, spec.param_kinds[i]) for i in varying]
            )
            instantiations.append(
                CppSmokeInstantiation(
                    symbol=f"tsl::{name}",
                    template_arguments=tuple(targs),
                    condition=_cpp_specialization_availability_condition(
                        spec,
                        emitted_profile.extensions,
                    ),
                    lane_count=smoke_lanes,
                    target_lane_count=target_lanes,
                )
            )
    return tuple(instantiations)


def _cpp_smoke_immediate(spec: LoweredSpecialization) -> str:
    if any(
        precondition.kind
        is LoweredArithmeticPreconditionKind.INTEGER_IMMEDIATE_NONZERO
        for precondition in spec.arithmetic_preconditions
    ):
        return "1"
    return "0"


def _cpp_specializations_for_group(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    extensions: Mapping[str, Extension],
    header_group: str | None,
) -> dict[str, tuple[LoweredSpecialization, ...]]:
    grouped: dict[str, tuple[LoweredSpecialization, ...]] = {}
    for primitive, specializations in by_primitive.items():
        selected = tuple(
            specialization
            for specialization in specializations
            if cpp_extension_header_group(extensions.get(specialization.extension_name))
            == header_group
        )
        if selected:
            grouped[primitive] = selected
    return grouped


def _cpp_type_param_smoke_vector(
    emitted_profile: EmittedProfile,
    spec: LoweredSpecialization,
    param: LoweredTypeParam,
    smoke_lanes: int,
    available_specializations: frozenset[tuple[str, str, str]],
) -> str:
    base = param.base_type_binding_spelling or spec.base_type_spelling
    base_tag = param.base_type_binding or spec.type_tag
    extensions_by_isa = {
        extension.isa_name: extension
        for extension in sorted(
            emitted_profile.extensions.values(),
            key=lambda extension: extension.name,
        )
    }
    source_extension = extensions_by_isa.get(spec.extension_name)
    candidates = sorted(
        extensions_by_isa.values(),
        key=lambda extension: (
            extension.isa_name != spec.extension_name,
            not (
                extension.is_unconditional_implementation_fallback
                and DEFAULT_SUPPORT_POLICY.uses_sized_vector(extension)
            ),
            not extension.is_unconditional_implementation_fallback,
            extension.isa_name,
        ),
    )
    extension = next(
        (
            candidate
            for candidate in candidates
            if all(
                (bound, candidate.isa_name, base_tag)
                in available_specializations
                for bound in param.bounds
            )
        ),
        source_extension,
    )
    if extension is None:
        return f"tsl::simd<{base}, tsl::{spec.extension_name}>"
    if DEFAULT_SUPPORT_POLICY.uses_sized_vector(extension):
        lanes = (
            DEFAULT_SUPPORT_POLICY.lane_count(source_extension, spec.type_tag)
            if source_extension is not None
            else None
        )
        return _cpp_sized_vector_type(
            base,
            extension.isa_name,
            max(16, smoke_lanes if lanes is None else lanes),
        )
    return f"tsl::simd<{base}, tsl::{extension.isa_name}>"


def _cpp_concrete_arg_type(vec: str, kind: str) -> str:
    """The concrete dispatch-argument type for an overloaded wrapper instantiation."""

    if kind == "v":
        return f"{vec}::register_type"
    if kind == "m":
        return f"{vec}::mask_type"
    if DEFAULT_SUPPORT_POLICY.is_const_pointer_kind(kind):
        return f"{vec}::base_type const *"
    if DEFAULT_SUPPORT_POLICY.is_mutable_pointer_kind(kind):
        return f"{vec}::base_type *"
    if kind in {"s[]", DEFAULT_SUPPORT_POLICY.lane_list_kind}:
        return f"::tsl::array_param<{vec}>::type"
    return f"{vec}::base_type"


def _cpp_sized_vector_type(base_spelling: str, extension_name: str, lanes: int) -> str:
    return f"tsl::simd<{base_spelling}, tsl::{extension_name}<{lanes}>>"


__all__ = (
    "CppDeclaredPrimitive",
    "CppDefinitionGroup",
    "CppProfileCompileGuard",
    "CppProfileHeader",
    "CppProfileRenderModel",
    "CppProjectRenderModel",
    "CppSmokeInstantiation",
    "cpp_project_render_model",
)
