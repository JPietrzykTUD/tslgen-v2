"""Rust public-surface planning over finalized facade and profile facts."""

from __future__ import annotations

from collections.abc import Mapping
import json

from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.public_api_manifest import BackendPublicApiManifest
from tslc.backend.public_declarations import (
    PublicDeclarationClassificationScope,
    PublicDeclarationKind,
    PublicDeclarationStability,
)
from tslc.backend.rust import RustBackend
from tslc.backend.rust_algorithm_plan import RustAlgorithmPlan
from tslc.backend.rust_algorithm_contracts import (
    rust_profile_scaled_checked_algorithm_declarations,
)
from tslc.backend.rust_algorithm_public_declarations import (
    rust_profile_algorithm_module_declaration,
    rust_profile_algorithm_public_declarations,
    rust_profile_algorithm_support_reexports,
)
from tslc.backend.rust_api_model import RustFacadePlan
from tslc.backend.rust_dispatch import RustDispatchPlan
from tslc.backend.rust_facade_public_declarations import (
    rust_comprehensive_public_declarations,
    rust_curated_public_declarations,
    rust_facade_core_public_declarations,
    rust_facade_type_public_declarations,
)
from tslc.backend.rust_names import rust_profile_module_name
from tslc.backend.rust_public_declarations import (
    RustPublicDeclaration,
    rust_const_parameter,
)
from tslc.backend.rust_static_selection import (
    RustStaticProfileSelection,
    RustStaticSelectionPlan,
)
from tslc.backend.rust_static_public_declarations import (
    rust_precondition_error_declaration,
)
from tslc.backend.rust_vectors import rust_extension_tag_registrations
from tslc.catalog.model import Extension
from tslc.lower.lowerer import LoweredSpecialization
from tslc.names import identifier_slug


RUST_ROOT_PUBLIC_IDENTITIES = (
    "crate::Mask",
    "crate::NativeMask",
    "crate::NativeSimd",
    "crate::PreconditionError",
    "crate::Simd",
    "crate::SimdElement",
    "crate::SupportedSimd",
    "crate::profile",
)


def _classified_item(
    identity: str,
    *,
    name: str,
    owner: str,
    reachability: tuple[str, ...],
    stability: PublicDeclarationStability,
    kind: PublicDeclarationKind,
    overload: str,
    visibility: str = "pub",
    classification_scope: PublicDeclarationClassificationScope = (
        PublicDeclarationClassificationScope.EXACT
    ),
) -> RustPublicDeclaration:
    return RustPublicDeclaration(
        identity=identity,
        name=name,
        owner=owner,
        reachability=reachability,
        stability=stability,
        kind=kind,
        overload=overload,
        visibility=visibility,
        classification_scope=classification_scope,
    )


def rust_static_public_declarations(
    facade_plan: RustFacadePlan,
) -> tuple[RustPublicDeclaration, ...]:
    """Classify non-profile exports and stable opaque-facade callable sets."""

    root = rust_root_public_declarations()
    core_methods = rust_facade_core_public_declarations()
    comprehensive = rust_comprehensive_public_declarations(facade_plan)
    comprehensive_reexports = rust_facade_function_root_reexports(facade_plan)
    curated = rust_curated_public_declarations(facade_plan)
    classified_exports = (
        _classified_item(
            "crate::tsl_core#module",
            name="tsl_core",
            owner="crate",
            reachability=("crate",),
            stability=PublicDeclarationStability.UNSTABLE,
            kind=PublicDeclarationKind.MODULE,
            overload="advanced-generated-substrate",
            classification_scope=PublicDeclarationClassificationScope.DESCENDANTS,
        ),
        _classified_item(
            "crate::tsl_algorithm#module",
            name="tsl_algorithm",
            owner="crate",
            reachability=("crate",),
            stability=PublicDeclarationStability.UNSTABLE,
            kind=PublicDeclarationKind.MODULE,
            overload="advanced-generated-substrate",
            classification_scope=PublicDeclarationClassificationScope.DESCENDANTS,
        ),
        _classified_item(
            "crate::profile::detail#module",
            name="detail",
            owner="crate::profile",
            reachability=("crate", "profile"),
            stability=PublicDeclarationStability.IMPLEMENTATION_DETAIL,
            kind=PublicDeclarationKind.MODULE,
            overload="primitive-dispatch-traits",
            classification_scope=PublicDeclarationClassificationScope.DESCENDANTS,
        ),
        _classified_item(
            "crate::tsl_facade::private#module",
            name="private",
            owner="crate::tsl_facade",
            reachability=("crate", "opaque-facade"),
            stability=PublicDeclarationStability.IMPLEMENTATION_DETAIL,
            kind=PublicDeclarationKind.MODULE,
            overload="representation-and-dispatch-traits",
            classification_scope=PublicDeclarationClassificationScope.DESCENDANTS,
        ),
        *(
            _classified_item(
                f"crate::{name}#module",
                name=name,
                owner="crate",
                reachability=("crate", "cfg:tsl_variant_benchmarks"),
                stability=PublicDeclarationStability.IMPLEMENTATION_DETAIL,
                kind=PublicDeclarationKind.MODULE,
                overload="benchmark-support",
                classification_scope=(
                    PublicDeclarationClassificationScope.DESCENDANTS
                ),
            )
            for name in (
                "tsl_benchmark_core",
                "tsl_benchmark_reducer",
                "tsl_benchmark_policy",
                "tsl_benchmark_self_test",
            )
        ),
        _classified_item(
            "crate::tsl_test_core#module",
            name="tsl_test_core",
            owner="crate",
            reachability=("crate",),
            stability=PublicDeclarationStability.IMPLEMENTATION_DETAIL,
            kind=PublicDeclarationKind.MODULE,
            overload="generated-test-support",
            classification_scope=PublicDeclarationClassificationScope.DESCENDANTS,
        ),
        _classified_item(
            "crate::primitive#module",
            name="primitive",
            owner="crate",
            reachability=("crate",),
            stability=PublicDeclarationStability.IMPLEMENTATION_DETAIL,
            kind=PublicDeclarationKind.MODULE,
            overload="generated-primitive-tags",
            classification_scope=PublicDeclarationClassificationScope.DESCENDANTS,
        ),
        _classified_item(
            "crate::tsl_documentation#module",
            name="tsl_documentation",
            owner="crate",
            reachability=("crate", "cfg:doc"),
            stability=PublicDeclarationStability.IMPLEMENTATION_DETAIL,
            kind=PublicDeclarationKind.MODULE,
            overload="documentation-only-profile-union",
            classification_scope=PublicDeclarationClassificationScope.DESCENDANTS,
        ),
        rust_documentation_profile_reexport_declaration(),
        rust_dataparallel_reexport_declaration(),
    )
    return (
        *root,
        *core_methods,
        *comprehensive,
        *comprehensive_reexports,
        *curated,
        *classified_exports,
    )


def rust_root_public_declarations() -> tuple[RustPublicDeclaration, ...]:
    """Return exact stable definitions and crate-root reexports."""

    facade_types = rust_facade_type_public_declarations()
    facade_reexports = tuple(
        RustPublicDeclaration(
            identity=f"crate::{declaration.name}",
            name=declaration.name,
            owner="crate",
            reachability=("crate",),
            stability=PublicDeclarationStability.STABLE,
            kind=PublicDeclarationKind.REEXPORT,
            overload="opaque-root-reexport",
            visibility="pub",
            reexport_target=f"tsl_facade::{declaration.name}",
            reexport_of=declaration.identity,
        )
        for declaration in facade_types
    )
    precondition_error = rust_precondition_error_declaration()
    return (
        *facade_types,
        *facade_reexports,
        precondition_error,
        RustPublicDeclaration(
            identity="crate::PreconditionError",
            name="PreconditionError",
            owner="crate",
            reachability=("crate",),
            stability=PublicDeclarationStability.STABLE,
            kind=PublicDeclarationKind.REEXPORT,
            overload="checked-error-root-reexport",
            visibility="pub",
            reexport_target="tsl_core::PreconditionError",
            reexport_of=precondition_error.identity,
        ),
    )


def rust_dataparallel_reexport_declaration() -> RustPublicDeclaration:
    return RustPublicDeclaration(
        identity="crate::dataparallel#reexport",
        name="dataparallel",
        owner="crate",
        reachability=("crate",),
        stability=PublicDeclarationStability.UNSTABLE,
        kind=PublicDeclarationKind.REEXPORT,
        overload="advanced-policy-substrate-reexport",
        visibility="pub",
        reexport_target="tsl_algorithm::dataparallel",
        reexport_of="crate::tsl_algorithm#module",
    )


def rust_selected_profile_reexport_declaration(
    selection: RustStaticProfileSelection,
) -> RustPublicDeclaration:
    """Return the exact crate-root alias for one selected physical profile."""

    physical_module = rust_profile_module_name(selection.profile_name)
    return _rust_profile_reexport_declaration(
        physical_module,
        reachability=("crate", *_rust_profile_selection_reachability(selection)),
        stability=PublicDeclarationStability.STABLE,
    )


def rust_fallback_profile_reexport_declaration(
    plan: RustStaticSelectionPlan,
) -> RustPublicDeclaration:
    """Return the exact crate-root alias for the generic fallback profile."""

    return _rust_profile_reexport_declaration(
        "tsl_target_fallback",
        reachability=("crate", *_rust_fallback_selection_reachability(plan)),
        stability=PublicDeclarationStability.STABLE,
    )


def rust_documentation_profile_reexport_declaration() -> RustPublicDeclaration:
    """Classify the documentation-only union exposed as ``crate::profile``."""

    return _rust_profile_reexport_declaration(
        "tsl_documentation",
        reachability=("crate", "cfg:doc"),
        stability=PublicDeclarationStability.IMPLEMENTATION_DETAIL,
        overload="documentation-profile-reexport",
    )


def _rust_profile_reexport_declaration(
    physical_module: str,
    *,
    reachability: tuple[str, ...],
    stability: PublicDeclarationStability,
    overload: str = "compile-target-selected-profile",
) -> RustPublicDeclaration:
    return RustPublicDeclaration(
        identity="crate::profile",
        name="profile",
        owner="crate",
        reachability=reachability,
        stability=stability,
        kind=PublicDeclarationKind.REEXPORT,
        overload=overload,
        visibility="pub",
        reexport_target=f"crate::{physical_module}",
        reexport_of=f"crate::{physical_module}#module",
    )


def rust_facade_function_root_reexports(
    facade_plan: RustFacadePlan,
) -> tuple[RustPublicDeclaration, ...]:
    """Return exact crate-root aliases for opaque-facade free functions."""

    definitions = tuple(
        declaration
        for declaration in rust_comprehensive_public_declarations(facade_plan)
        if declaration.kind is PublicDeclarationKind.FUNCTION
    )
    root_identity_by_definition = {
        declaration.identity: declaration.identity.replace(
            "crate::tsl_facade::", "crate::", 1
        )
        for declaration in definitions
    }
    if len(root_identity_by_definition) != len(definitions):
        raise ValueError("opaque facade free functions require unique identities")
    return tuple(
        RustPublicDeclaration(
            identity=root_identity_by_definition[declaration.identity],
            name=declaration.name,
            owner="crate",
            reachability=("crate",),
            stability=PublicDeclarationStability.STABLE,
            kind=PublicDeclarationKind.REEXPORT,
            overload=declaration.overload,
            visibility="pub",
            reexport_target=f"tsl_facade::{declaration.name}",
            reexport_of=declaration.identity,
            checked_of=(
                root_identity_by_definition[declaration.checked_of]
                if declaration.checked_of is not None
                else None
            ),
            error_form=declaration.error_form,
        )
        for declaration in definitions
    )


def rust_root_declaration_holes(
    facade_plan: RustFacadePlan,
) -> dict[str, str]:
    """Format root reexports from the records used by the public manifest."""

    root = rust_root_public_declarations()
    precondition_error = next(
        declaration
        for declaration in root
        if declaration.identity == "crate::PreconditionError"
    )
    facade_exports = tuple(
        declaration
        for declaration in root
        if declaration.overload == "opaque-root-reexport"
    )
    facade_functions = rust_facade_function_root_reexports(facade_plan)
    return {
        "precondition_error_export": precondition_error.render_head() + ";",
        "dataparallel_export": rust_dataparallel_reexport_declaration().render_head()
        + ";",
        "facade_type_exports": "\n".join(
            declaration.render_head() + ";" for declaration in facade_exports
        ),
        "facade_function_exports": "\n".join(
            declaration.render_head() + ";"
            for declaration in facade_functions
        ),
        "documentation_profile_export": (
            rust_documentation_profile_reexport_declaration().render_head() + ";"
        ),
    }


def rust_public_api_manifest(
    profiles: tuple[EmittedProfile, ...],
    static_selection_plan: RustStaticSelectionPlan,
    algorithm_plan: RustAlgorithmPlan,
    facade_plan: RustFacadePlan,
    dispatch_plan: RustDispatchPlan,
) -> BackendPublicApiManifest:
    """Plan exact Rust profile declarations plus classified static exports."""

    backend = RustBackend(emit_target_features=False)
    declarations: list[RustPublicDeclaration] = list(
        rust_static_public_declarations(facade_plan)
    )
    declarations.extend(
        _rust_benchmark_module_declarations(profiles, static_selection_plan)
    )
    if dispatch_plan.slots:
        declarations.extend(_rust_runtime_dispatch_declarations())
    profiles_by_name = {profile.profile.name: profile for profile in profiles}
    selection_names = tuple(
        selection.profile_name for selection in static_selection_plan.profiles
    )
    if any(name not in profiles_by_name for name in selection_names):
        raise ValueError("Rust public manifest selection is foreign to the profiles")
    for selection in static_selection_plan.profiles:
        emitted_profile = profiles_by_name[selection.profile_name]
        algorithm_profile = algorithm_plan.profile(selection.profile_name)
        if algorithm_profile is None:
            raise ValueError("Rust public manifest requires algorithm profile facts")
        reachability = (
            "crate",
            "profile",
            *_rust_profile_selection_reachability(selection),
        )
        declarations.extend(
            _rust_profile_classification_declarations(
                selection.profile_name,
                profile_family=emitted_profile.profile.family,
                physical_module=rust_profile_module_name(selection.profile_name),
                reachability=reachability,
            )
        )
        declarations.append(rust_selected_profile_reexport_declaration(selection))
        by_primitive = emitted_profile.specializations("rust")
        declarations.extend(
            _rust_extension_tag_declarations(
                selection.profile_name,
                reachability,
                by_primitive,
                emitted_profile.extensions,
            )
        )
        for name, specializations in sorted(by_primitive.items()):
            declarations.extend(
                backend.public_declarations(
                    name, specializations, reachability=reachability
                )
            )
        if algorithm_profile.supported:
            algorithm_reachability = (*reachability, "algo")
            declarations.append(
                rust_profile_algorithm_module_declaration(reachability)
            )
            declarations.append(
                _rust_profile_algorithm_marker(
                    selection.profile_name,
                    algorithm_reachability,
                )
            )
            declarations.extend(
                rust_profile_algorithm_support_reexports(
                    algorithm_reachability
                )
            )
            declarations.extend(
                rust_profile_algorithm_public_declarations(
                    algorithm_reachability,
                    admitted_form_names=frozenset(
                        algorithm_profile.admitted_form_names
                    ),
                )
            )
            declarations.extend(
                rust_profile_scaled_checked_algorithm_declarations(
                    algorithm_reachability,
                    admitted_form_names=frozenset(
                        algorithm_profile.admitted_form_names
                    ),
                )
            )
    fallback = static_selection_plan.fallback_module.specializations_by_primitive()
    fallback_reachability = _rust_fallback_selection_reachability(
        static_selection_plan,
        prefix=("crate", "profile"),
    )
    declarations.extend(
        _rust_profile_classification_declarations(
            static_selection_plan.fallback_module.metadata_profile_name,
            profile_family=static_selection_plan.fallback_module.metadata_profile_family,
            physical_module="tsl_target_fallback",
            reachability=fallback_reachability,
        )
    )
    declarations.append(
        rust_fallback_profile_reexport_declaration(static_selection_plan)
    )
    fallback_extensions = static_selection_plan.fallback_module.extensions_by_name()
    declarations.extend(
        _rust_extension_tag_declarations(
            static_selection_plan.fallback_module.metadata_profile_name,
            fallback_reachability,
            fallback,
            fallback_extensions,
        )
    )
    for name, specializations in sorted(fallback.items()):
        declarations.extend(
            backend.public_declarations(
                name,
                specializations,
                reachability=fallback_reachability,
            )
        )
    if algorithm_plan.fallback.supported:
        fallback_algorithm_reachability = (*fallback_reachability, "algo")
        declarations.append(
            rust_profile_algorithm_module_declaration(fallback_reachability)
        )
        declarations.append(
            _rust_profile_algorithm_marker(
                static_selection_plan.fallback_module.metadata_profile_name,
                fallback_algorithm_reachability,
            )
        )
        declarations.extend(
            rust_profile_algorithm_support_reexports(
                fallback_algorithm_reachability
            )
        )
        declarations.extend(
            rust_profile_algorithm_public_declarations(
                fallback_algorithm_reachability,
                admitted_form_names=frozenset(
                    algorithm_plan.fallback.admitted_form_names
                ),
            )
        )
        declarations.extend(
            rust_profile_scaled_checked_algorithm_declarations(
                fallback_algorithm_reachability,
                admitted_form_names=frozenset(
                    algorithm_plan.fallback.admitted_form_names
                ),
            )
        )
    return BackendPublicApiManifest(
        backend="rust",
        scope=(*selection_names, "fallback"),
        declarations=tuple(declarations),
    )


def _rust_benchmark_module_declarations(
    profiles: tuple[EmittedProfile, ...],
    static_selection_plan: RustStaticSelectionPlan,
) -> tuple[RustPublicDeclaration, ...]:
    selections_by_name = {
        selection.profile_name: selection
        for selection in static_selection_plan.profiles
    }
    declarations: list[RustPublicDeclaration] = []
    for profile in profiles:
        profile_name = profile.profile.name
        module_name = f"tsl_variant_bench_{identifier_slug(profile_name)}"
        selection = selections_by_name.get(profile_name)
        selection_reachability = (
            _rust_profile_selection_reachability(selection)
            if selection is not None
            else _rust_fallback_selection_reachability(static_selection_plan)
        )
        declarations.append(
            _classified_item(
                f"crate::{module_name}#module",
                name=module_name,
                owner="crate",
                reachability=(
                    "crate",
                    "cfg:tsl_variant_benchmarks",
                    f"profile:{profile_name}",
                    *selection_reachability,
                ),
                stability=PublicDeclarationStability.IMPLEMENTATION_DETAIL,
                kind=PublicDeclarationKind.MODULE,
                overload="generated-profile-benchmark",
                classification_scope=(
                    PublicDeclarationClassificationScope.DESCENDANTS
                ),
            )
        )
    return tuple(declarations)


def _rust_runtime_dispatch_declarations() -> tuple[RustPublicDeclaration, ...]:
    reachability = ("crate", "feature:runtime-dispatch")
    return (
        _classified_item(
            "crate::Dispatcher#runtime-dispatch",
            name="Dispatcher",
            owner="crate",
            reachability=reachability,
            stability=PublicDeclarationStability.UNSTABLE,
            kind=PublicDeclarationKind.TYPE,
            overload="runtime-dispatch-reexport",
            classification_scope=PublicDeclarationClassificationScope.DESCENDANTS,
        ),
        *(
            _classified_item(
                f"crate::{name}#runtime-dispatch",
                name=name,
                owner="crate",
                reachability=reachability,
                stability=PublicDeclarationStability.UNSTABLE,
                kind=PublicDeclarationKind.MODULE,
                overload="runtime-dispatch-reexport",
                classification_scope=(
                    PublicDeclarationClassificationScope.DESCENDANTS
                ),
            )
            for name in ("algorithms", "ops")
        ),
    )


def _rust_extension_tag_declarations(
    profile_name: str,
    reachability: tuple[str, ...],
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    extensions: Mapping[str, Extension],
) -> tuple[RustPublicDeclaration, ...]:
    """Classify tag structs reexported through the selected profile alias."""

    return tuple(
        RustPublicDeclaration(
            identity=f"crate::profile::{registration.tag_name}#{profile_name}",
            name=registration.tag_name,
            owner="crate::profile",
            reachability=reachability,
            stability=PublicDeclarationStability.UNSTABLE,
            kind=PublicDeclarationKind.TYPE,
            overload="generated-extension-tag",
            visibility="pub",
            generic_parameters=(
                (rust_const_parameter("LANES", "usize"),)
                if registration.sized
                else ()
            ),
            type_form="struct",
        )
        for registration in rust_extension_tag_registrations(
            by_primitive,
            extensions,
        )
    )


def _rust_profile_algorithm_marker(
    profile_name: str,
    reachability: tuple[str, ...],
) -> RustPublicDeclaration:
    return _classified_item(
        f"crate::profile::algo::Profile#{profile_name}",
        name="Profile",
        owner="crate::profile::algo",
        reachability=reachability,
        stability=PublicDeclarationStability.UNSTABLE,
        kind=PublicDeclarationKind.TYPE,
        overload="profile-algorithm-backend-marker",
    )


def _rust_profile_classification_declarations(
    profile_name: str,
    *,
    profile_family: str,
    physical_module: str,
    reachability: tuple[str, ...],
) -> tuple[RustPublicDeclaration, ...]:
    """Classify generated metadata outside the stable callable projection."""

    return (
        _classified_item(
            f"crate::{physical_module}#module",
            name=physical_module,
            owner="crate",
            reachability=("crate", f"physical:{profile_name}"),
            stability=PublicDeclarationStability.IMPLEMENTATION_DETAIL,
            kind=PublicDeclarationKind.MODULE,
            overload="physical-profile-module",
            classification_scope=PublicDeclarationClassificationScope.DESCENDANTS,
        ),
        _classified_item(
            f"crate::profile::Profile#{profile_name}",
            name="Profile",
            owner="crate::profile",
            reachability=reachability,
            stability=PublicDeclarationStability.UNSTABLE,
            kind=PublicDeclarationKind.TYPE,
            overload="profile-backend-marker",
        ),
        RustPublicDeclaration(
            identity=f"crate::profile::ACTIVE_PROFILE#{profile_name}",
            name="ACTIVE_PROFILE",
            owner="crate::profile",
            reachability=reachability,
            stability=PublicDeclarationStability.UNSTABLE,
            kind=PublicDeclarationKind.CONSTANT,
            overload="profile-metadata",
            visibility="pub",
            type_spelling="&str",
            value=json.dumps(identifier_slug(profile_name)),
        ),
        RustPublicDeclaration(
            identity=f"crate::profile::ACTIVE_PROFILE_FAMILY#{profile_name}",
            name="ACTIVE_PROFILE_FAMILY",
            owner="crate::profile",
            reachability=reachability,
            stability=PublicDeclarationStability.UNSTABLE,
            kind=PublicDeclarationKind.CONSTANT,
            overload="profile-metadata",
            visibility="pub",
            type_spelling="&str",
            value=json.dumps(profile_family),
        ),
    )


def _rust_profile_selection_reachability(
    selection: RustStaticProfileSelection,
) -> tuple[str, ...]:
    requirement = selection.requirement
    return (
        f"selection:{selection.profile_name}",
        f"target-arch:{requirement.target_arch}",
        "target-features:" + ",".join(requirement.target_features),
        *(
            "excludes:"
            + higher_priority.target_arch
            + ":"
            + ",".join(higher_priority.target_features)
            for higher_priority in selection.higher_priority_requirements
        ),
    )


def _rust_fallback_selection_reachability(
    plan: RustStaticSelectionPlan,
    *,
    prefix: tuple[str, ...] = (),
) -> tuple[str, ...]:
    return (
        *prefix,
        "selection:fallback",
        *(
            "excludes:"
            + selection.requirement.target_arch
            + ":"
            + ",".join(selection.requirement.target_features)
            for selection in plan.profiles
        ),
    )


__all__ = (
    "RUST_ROOT_PUBLIC_IDENTITIES",
    "rust_dataparallel_reexport_declaration",
    "rust_fallback_profile_reexport_declaration",
    "rust_facade_function_root_reexports",
    "rust_documentation_profile_reexport_declaration",
    "rust_public_api_manifest",
    "rust_root_declaration_holes",
    "rust_root_public_declarations",
    "rust_selected_profile_reexport_declaration",
    "rust_static_public_declarations",
)
