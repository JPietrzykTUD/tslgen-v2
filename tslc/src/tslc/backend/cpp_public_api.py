"""C++ public-surface planning over finalized generated profile facts."""

from __future__ import annotations

from tslc.backend.cpp import CppBackend
from tslc.backend.cpp_algorithm_contracts import cpp_checked_algorithm_declarations
from tslc.backend.cpp_algorithm_public_declarations import (
    cpp_algorithm_public_declarations,
)
from tslc.backend.cpp_profile_model import (
    CppProfileHeader,
    CppProfileRenderModel,
    CppProjectRenderModel,
    cpp_project_render_model,
)
from tslc.backend.helper_requirements import BackendHelperPlan
from tslc.backend.cpp_public_declarations import CppPublicDeclaration
from tslc.backend.cpp_static_public_declarations import (
    CPP_CORE_PUBLIC_IDENTITIES,
    cpp_static_public_declarations as cpp_exact_static_public_declarations,
)
from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.public_api_manifest import BackendPublicApiManifest
from tslc.backend.public_declarations import (
    PublicDeclarationClassificationScope,
    PublicDeclarationKind,
    PublicDeclarationStability,
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
    classification_scope: PublicDeclarationClassificationScope = (
        PublicDeclarationClassificationScope.EXACT
    ),
) -> CppPublicDeclaration:
    return CppPublicDeclaration(
        identity=identity,
        name=name,
        owner=owner,
        reachability=reachability,
        stability=stability,
        kind=kind,
        overload=overload,
        classification_scope=classification_scope,
    )


def cpp_static_public_declarations(
    *,
    supports_algorithm: bool,
    admitted_algorithm_forms: frozenset[str] | None = None,
) -> tuple[CppPublicDeclaration, ...]:
    """Classify static exported surfaces that are not lowered primitives."""

    core = cpp_exact_static_public_declarations()
    algorithm_declarations = cpp_algorithm_public_declarations()
    algorithm_aliases = tuple(
        declaration
        for declaration in algorithm_declarations
        if declaration.kind is PublicDeclarationKind.TYPE_ALIAS
    )
    algorithm_functions = tuple(
        declaration
        for declaration in algorithm_declarations
        if declaration.kind is PublicDeclarationKind.FUNCTION
        and (
            admitted_algorithm_forms is None
            or declaration.name in admitted_algorithm_forms
        )
    )
    checked_functions = tuple(
        declaration
        for declaration in cpp_checked_algorithm_declarations()
        if admitted_algorithm_forms is None
        or declaration.name.removesuffix("_checked") in admitted_algorithm_forms
    )
    algorithms = (
        (*algorithm_aliases, *algorithm_functions, *checked_functions)
        if supports_algorithm
        else ()
    )
    unstable_support = tuple(
        _classified_item(
            f"tsl::{name}#static-support",
            name=name,
            owner="tsl",
            reachability=("tsl.hpp", "tsl_core.hpp"),
            stability=PublicDeclarationStability.UNSTABLE,
            kind=kind,
            overload="advanced-static-substrate",
            classification_scope=(
                PublicDeclarationClassificationScope.DESCENDANTS
                if kind is PublicDeclarationKind.TYPE
                else PublicDeclarationClassificationScope.EXACT
            ),
        )
        for name, kind in (
            ("value_arg", PublicDeclarationKind.TYPE),
            ("implementation_state_v", PublicDeclarationKind.CONSTANT),
            ("scalar", PublicDeclarationKind.TYPE),
            ("generic", PublicDeclarationKind.TYPE),
            ("array_for", PublicDeclarationKind.TYPE),
            ("array_param", PublicDeclarationKind.TYPE),
            ("bit_cast", PublicDeclarationKind.OVERLOAD_SET),
            ("saturating_cast", PublicDeclarationKind.OVERLOAD_SET),
            ("scalar_as_cast", PublicDeclarationKind.OVERLOAD_SET),
            ("mask_lane_all_true", PublicDeclarationKind.OVERLOAD_SET),
            ("mask_lane_all_false", PublicDeclarationKind.OVERLOAD_SET),
            ("assume_aligned", PublicDeclarationKind.OVERLOAD_SET),
            ("ptr_add_mut", PublicDeclarationKind.OVERLOAD_SET),
            ("ptr_add", PublicDeclarationKind.OVERLOAD_SET),
            ("idx_offset", PublicDeclarationKind.OVERLOAD_SET),
            ("indexed_memory_address_error", PublicDeclarationKind.OVERLOAD_SET),
            ("ostream_write", PublicDeclarationKind.OVERLOAD_SET),
        )
    )
    support_macros = tuple(
        _classified_item(
            f"{name}#macro",
            name=name,
            owner="preprocessor",
            reachability=("tsl.hpp", "tsl_core.hpp"),
            stability=PublicDeclarationStability.IMPLEMENTATION_DETAIL,
            kind=PublicDeclarationKind.MACRO,
            overload="backend-support-macro",
        )
        for name in ("TSL_FORCE_INLINE", "TSL_UNROLL")
    )
    static_registrations = (
        _classified_item(
            "tsl::simd#scalar-registration",
            name="simd",
            owner="tsl",
            reachability=("tsl.hpp", "tsl_core.hpp"),
            stability=PublicDeclarationStability.UNSTABLE,
            kind=PublicDeclarationKind.TYPE,
            overload="static-scalar-specialization",
            classification_scope=PublicDeclarationClassificationScope.DESCENDANTS,
        ),
        _classified_item(
            "tsl::simd#generic-registration",
            name="simd",
            owner="tsl",
            reachability=("tsl.hpp", "tsl_core.hpp"),
            stability=PublicDeclarationStability.UNSTABLE,
            kind=PublicDeclarationKind.TYPE,
            overload="static-generic-specialization",
            classification_scope=PublicDeclarationClassificationScope.DESCENDANTS,
        ),
        _classified_item(
            "tsl::reg_param#generic-registration",
            name="reg_param",
            owner="tsl",
            reachability=("tsl.hpp", "tsl_core.hpp"),
            stability=PublicDeclarationStability.UNSTABLE,
            kind=PublicDeclarationKind.TYPE,
            overload="static-generic-specialization",
            classification_scope=PublicDeclarationClassificationScope.DESCENDANTS,
        ),
        _classified_item(
            "tsl::dataparallel::simd_for#static-registrations",
            name="simd_for",
            owner="tsl::dataparallel",
            reachability=("tsl.hpp", "tsl_dataparallel.hpp"),
            stability=PublicDeclarationStability.UNSTABLE,
            kind=PublicDeclarationKind.TYPE,
            overload="static-policy-mappings",
            classification_scope=PublicDeclarationClassificationScope.DESCENDANTS,
        ),
    )
    classified_exports = (
        _classified_item(
            "tsl::detail#namespace",
            name="detail",
            owner="tsl",
            reachability=("tsl.hpp", "tsl_core.hpp", "physical-profile-header"),
            stability=PublicDeclarationStability.IMPLEMENTATION_DETAIL,
            kind=PublicDeclarationKind.MODULE,
            overload="implementation-templates-and-variant-selectors",
            classification_scope=PublicDeclarationClassificationScope.DESCENDANTS,
        ),
        _classified_item(
            "tsl::implementation_state_of#template",
            name="implementation_state_of",
            owner="tsl",
            reachability=("tsl.hpp", "tsl_core.hpp"),
            stability=PublicDeclarationStability.UNSTABLE,
            kind=PublicDeclarationKind.TYPE,
            overload="diagnostic-query-template",
            classification_scope=PublicDeclarationClassificationScope.DESCENDANTS,
        ),
        _classified_item(
            "tsl::primitive#tags",
            name="primitive",
            owner="tsl",
            reachability=("tsl.hpp", "tsl_primitives.hpp"),
            stability=PublicDeclarationStability.IMPLEMENTATION_DETAIL,
            kind=PublicDeclarationKind.MODULE,
            overload="generated-primitive-tags",
            classification_scope=PublicDeclarationClassificationScope.DESCENDANTS,
        ),
        _classified_item(
            "tsl::algo::detail#namespace",
            name="detail",
            owner="tsl::algo",
            reachability=(
                "tsl.hpp",
                "tsl_algorithm.hpp",
                "tsl_algorithm_checked.hpp",
            ),
            stability=PublicDeclarationStability.IMPLEMENTATION_DETAIL,
            kind=PublicDeclarationKind.MODULE,
            overload="algorithm-kernels",
            classification_scope=PublicDeclarationClassificationScope.DESCENDANTS,
        ),
    )
    return (
        *core,
        *algorithms,
        *unstable_support,
        *support_macros,
        *static_registrations,
        *classified_exports,
    )


def cpp_public_api_manifest(
    profiles: tuple[EmittedProfile, ...],
    *,
    model: CppProjectRenderModel | None = None,
    helper_plan: BackendHelperPlan | None = None,
) -> BackendPublicApiManifest:
    """Plan the exact C++ manifest from the same primitive declaration planner."""

    backend = CppBackend()
    if model is None:
        if helper_plan is None:
            raise ValueError("C++ public API planning requires a backend helper plan")
        model = cpp_project_render_model(profiles, helper_plan)
    declarations: list[CppPublicDeclaration] = list(
        cpp_static_public_declarations(
            supports_algorithm=model.algorithm.supported,
            admitted_algorithm_forms=frozenset(
                model.algorithm.admitted_form_names
            ),
        )
    )
    for profile in model.profiles:
        declarations.extend(_cpp_profile_classifications(profile))
        for header in profile.headers:
            reachability = _cpp_header_reachability(profile, header)
            for primitive in header.declarations:
                declarations.extend(
                    backend.public_declarations(
                        primitive.name,
                        primitive.specializations,
                        reachability=reachability,
                    )
                )
    return BackendPublicApiManifest(
        backend="cpp",
        scope=tuple(profile.profile_name for profile in model.profiles),
        declarations=tuple(declarations),
    )


def _cpp_profile_classifications(
    profile: CppProfileRenderModel,
) -> tuple[CppPublicDeclaration, ...]:
    """Classify public generated profile support outside stable wrappers."""

    reachability = ("tsl.hpp", f"profile:{profile.profile_name}")
    declarations = [
        _classified_item(
            f"tsl::profiles::{profile.profile_namespace}#namespace",
            name=profile.profile_namespace,
            owner="tsl::profiles",
            reachability=reachability,
            stability=PublicDeclarationStability.UNSTABLE,
            kind=PublicDeclarationKind.MODULE,
            overload="generated-profile-metadata",
            classification_scope=PublicDeclarationClassificationScope.DESCENDANTS,
        ),
        _classified_item(
            "tsl::active_profile#constant",
            name="active_profile",
            owner="tsl",
            reachability=reachability,
            stability=PublicDeclarationStability.UNSTABLE,
            kind=PublicDeclarationKind.CONSTANT,
            overload="selected-profile-metadata",
        ),
        _classified_item(
            "tsl::active_profile_family#constant",
            name="active_profile_family",
            owner="tsl",
            reachability=reachability,
            stability=PublicDeclarationStability.UNSTABLE,
            kind=PublicDeclarationKind.CONSTANT,
            overload="selected-profile-metadata",
        ),
    ]
    for header in profile.headers:
        header_name = header.header_group or "base"
        header_reachability = _cpp_header_reachability(profile, header)
        for extension_name in header.public_support.extension_names:
            declarations.extend(
                (
                    _classified_item(
                        f"tsl::{extension_name}#extension-tag",
                        name=extension_name,
                        owner="tsl",
                        reachability=header_reachability,
                        stability=PublicDeclarationStability.UNSTABLE,
                        kind=PublicDeclarationKind.TYPE,
                        overload="generated-extension-tag",
                        classification_scope=(
                            PublicDeclarationClassificationScope.DESCENDANTS
                        ),
                    ),
                    _classified_item(
                        f"tsl::simd#{extension_name}-registration",
                        name="simd",
                        owner="tsl",
                        reachability=header_reachability,
                        stability=PublicDeclarationStability.UNSTABLE,
                        kind=PublicDeclarationKind.TYPE,
                        overload=f"generated-{extension_name}-specialization",
                        classification_scope=(
                            PublicDeclarationClassificationScope.DESCENDANTS
                        ),
                    ),
                )
            )
        declarations.extend(
            _classified_item(
                f"tsl::reg_param#{extension_name}-registration",
                name="reg_param",
                owner="tsl",
                reachability=header_reachability,
                stability=PublicDeclarationStability.UNSTABLE,
                kind=PublicDeclarationKind.TYPE,
                overload=f"generated-{extension_name}-specialization",
                classification_scope=(
                    PublicDeclarationClassificationScope.DESCENDANTS
                ),
            )
            for extension_name in header.public_support.sized_reg_param_extensions
        )
        if header.public_support.has_dataparallel_mappings:
            declarations.append(
                _classified_item(
                    "tsl::dataparallel::simd_for#"
                    f"{profile.profile_name}-{header_name}-mappings",
                    name="simd_for",
                    owner="tsl::dataparallel",
                    reachability=header_reachability,
                    stability=PublicDeclarationStability.UNSTABLE,
                    kind=PublicDeclarationKind.TYPE,
                    overload="generated-profile-policy-mappings",
                    classification_scope=(
                        PublicDeclarationClassificationScope.DESCENDANTS
                    ),
                )
            )
        policy_name = header.public_support.dataparallel_policy_name
        mask_namespace = header.public_support.dataparallel_mask_namespace
        if policy_name is not None and mask_namespace is not None:
            declarations.extend(
                (
                    _classified_item(
                        f"tsl::dataparallel::{policy_name}#{profile.profile_name}",
                        name=policy_name,
                        owner="tsl::dataparallel",
                        reachability=header_reachability,
                        stability=PublicDeclarationStability.UNSTABLE,
                        kind=PublicDeclarationKind.TYPE,
                        overload="generated-overlay-policy",
                        classification_scope=(
                            PublicDeclarationClassificationScope.DESCENDANTS
                        ),
                    ),
                    _classified_item(
                        f"tsl::dataparallel::{mask_namespace}#{profile.profile_name}",
                        name=mask_namespace,
                        owner="tsl::dataparallel",
                        reachability=header_reachability,
                        stability=PublicDeclarationStability.UNSTABLE,
                        kind=PublicDeclarationKind.MODULE,
                        overload="generated-overlay-mask-policies",
                        classification_scope=(
                            PublicDeclarationClassificationScope.DESCENDANTS
                        ),
                    ),
                )
            )
    return tuple(declarations)


def _cpp_header_reachability(
    profile: CppProfileRenderModel,
    header: CppProfileHeader,
) -> tuple[str, ...]:
    """Return exact include, opt-in, compiler, and feature reachability facts."""

    header_name = header.header_group or "base"
    facts = [
        "tsl.hpp",
        f"profile:{profile.profile_name}",
        f"header:{header_name}",
    ]
    if header.enable_macro is not None:
        facts.append(f"enable-macro:{header.enable_macro}")
    if header.compiler_ids:
        facts.append("compiler-ids:" + ",".join(header.compiler_ids))
    if header.guard is not None:
        facts.append(f"guard:{header.guard.condition}")
    return tuple(facts)


__all__ = (
    "CPP_CORE_PUBLIC_IDENTITIES",
    "cpp_public_api_manifest",
    "cpp_static_public_declarations",
)
