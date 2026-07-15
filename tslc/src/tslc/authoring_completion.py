"""Compiler-owned catalog completion records and closed authoring vocabularies."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from tslc.backend.registry import registered_backend_ids
from tslc.catalog.model import Catalog, Primitive
from tslc.catalog.scalar_types import KNOWN_SCALAR_TYPE_TAGS
from tslc.catalog.validation._schema_benchmarks import (
    KNOWN_BENCHMARK_FIELDS,
    KNOWN_OPERAND_DOMAINS,
)
from tslc.catalog.validation._schema_common import KNOWN_BOOLEAN_VALUES
from tslc.catalog.validation._schema_extensions import (
    KNOWN_ACTIVE_WHEN_FIELDS,
    KNOWN_COMPILE_GUARD_FIELDS,
    KNOWN_EXTENSION_BACKEND_FIELDS,
    KNOWN_EXTENSION_FIELDS,
    KNOWN_IMASK_POLICY_FIELDS,
    KNOWN_IMASK_POLICY_KINDS,
    KNOWN_INTRINSIC_COMPOSE_FIELDS,
    KNOWN_INTRINSIC_SUFFIX_FIELDS,
    KNOWN_MASK_POLICY_FIELDS,
    KNOWN_MASK_POLICY_KINDS,
    KNOWN_SIZE_PARAMETER_FIELDS,
    KNOWN_TEST_FILTER_FIELDS,
    KNOWN_VECTOR_REGISTER_POLICY_FIELDS,
)
from tslc.catalog.validation._schema_implementation import (
    KNOWN_SAFETY_FIELDS,
    KNOWN_SELECTOR_METADATA_FIELDS,
    KNOWN_TARGET_CONSTRAINT_FIELDS,
    KNOWN_TARGET_FAMILY_RELATIONS,
    KNOWN_TARGET_WIDTH_RELATIONS,
    KNOWN_VARIANT_FIELDS,
    KNOWN_VARIANT_SAFETY_FIELDS,
)
from tslc.catalog.validation._schema_primitives import (
    KNOWN_GENERIC_PARAM_FIELDS,
    KNOWN_GENERIC_PARAM_KINDS,
    KNOWN_IMMEDIATE_DISPATCH,
    KNOWN_IMMEDIATE_PARAM_FIELDS,
    KNOWN_PRIMITIVE_FIELDS,
    KNOWN_RETURN_TYPE_FIELDS,
)
from tslc.catalog.validation._schema_target_families import (
    KNOWN_BACKEND_PROFILE_FIELDS,
    KNOWN_EXTENSION_FAMILY_FIELDS,
    KNOWN_PROFILE_FAMILY_FIELDS,
    KNOWN_TARGET_FAMILIES_FIELDS,
)
from tslc.catalog.validation._schema_tests import (
    KNOWN_TEST_CASE_FIELDS,
    KNOWN_TEST_FIELDS,
    KNOWN_TEST_ROLES,
)
from tslc.catalog.validation.schema_validation import (
    KNOWN_LANGUAGE_TYPE_FIELDS,
    KNOWN_TYPE_GROUP_FIELDS,
)
from tslc.ir.region_registry import TSIL_REGION_KEYWORDS
from tslc.syntax.authoring import AuthoringCursorContext, AuthoringTextRange


AuthoringCompletionKind = Literal[
    "field",
    "keyword",
    "value",
    "function",
    "class",
    "type",
]

VAR_SELECTORS = (
    "infer",
    "const_infer",
    "typed",
    "const_typed",
    "init_register",
    "const_init_register",
    "runtime_array",
)

_IMPLEMENTATION_BODY_FIELDS = frozenset({"tsil", "tsl"})
_GENERIC_CONSTRAINT_FIELDS = frozenset({"base_types"})
_BOOLEAN_FIELDS = frozenset(
    {
        "caller_unsafe",
        "cross_lane",
        "dataparallel_inference",
        "default_test_target",
        "feature_flags",
        "free_function_owner",
        "implementation_fallback",
        "index_vector_register",
        "internal_unsafe",
        "native_without_runner",
        "requires_declared_vector_register",
        "specialize_base",
        "supported",
        "unroll_variants",
    }
)
_BACKEND_MAP_FIELDS = frozenset(
    {
        "backend_spelling",
        "runtime_lane_count",
        "test_mask_check",
        "test_mask_from_bits",
        "test_runtime_lanes",
        "test_support_headers",
    }
)
_TOP_LEVEL_SNIPPETS = (
    ("prim", "prim<${1:v:=v}> ${2:name}(${3:value}):\n  ${0}"),
    ("template", "template ${1:name}:\n  ${0}"),
    ("extension", "extension ${1:name}:\n  ${0}"),
    ("types", "types:\n  ${0}"),
    ("flags", "flags:\n  ${0}"),
    ("language", "language ${1:backend}:\n  ${0}"),
    ("translation", "translation ${1:backend}:\n  ${0}"),
    ("lane_set", "lane_set ${1:name}:\n  ${0}"),
    ("description", 'description "${1}"'),
    ("target_families", "target_families:\n  ${0}"),
)


@dataclass(frozen=True, slots=True)
class AuthoringCompletion:
    """Editor-neutral completion information returned by compiler semantics."""

    label: str
    kind: AuthoringCompletionKind
    replacement_range: AuthoringTextRange
    insert_text: str
    detail: str
    documentation: str | None = None
    snippet: bool = False
    sort_group: int = 0
    commit_characters: tuple[str, ...] = ()


def authoring_completions(
    context: AuthoringCursorContext,
    catalog: Catalog,
    *,
    target_features: Iterable[str] = (),
) -> tuple[AuthoringCompletion, ...]:
    """Return deterministic schema/catalog completion records for one cursor."""

    if context.current_field == "$primitive-call":
        return _values(
            context,
            (primitive.name for primitive in catalog.primitives),
            kind="function",
            detail="TSL primitive",
        )
    if context.current_field == "$cast-selector":
        variants = {
            key[len("cast_") :]
            for templates in catalog.translations.values()
            for key in templates
            if key.startswith("cast_")
        }
        return _values(
            context,
            variants | {"type=value", "type=ptr", "type=const_ptr"},
            detail="cast selector",
        )
    if context.current_field == "$var-selector":
        return _values(context, VAR_SELECTORS, detail="variable selector")
    if context.current_field == "$region-keyword":
        return _values(
            context,
            TSIL_REGION_KEYWORDS,
            kind="keyword",
            detail="TSIL region",
        )
    if context.current_field == "$primitive_signature":
        return _values(
            context,
            {primitive.signature for primitive in catalog.primitives},
            detail="primitive signature shape",
            commit_characters=(">",),
        )

    if context.declaration_kind is None:
        return _top_level(context)

    if context.position_kind in {"scalar-value", "list-value"}:
        return _value_completions(context, catalog, target_features)
    if context.position_kind != "field-name":
        return ()

    fields, kind, detail = _field_candidates(context, catalog)
    present = set(context.existing_fields) if kind not in {"class", "type"} else set()
    if context.current_field is not None:
        present.discard(context.current_field)
    return _values(
        context,
        (field for field in fields if field not in present),
        kind=kind,
        detail=detail,
        commit_characters=(":",) if kind == "field" else (),
    )


def _top_level(context: AuthoringCursorContext) -> tuple[AuthoringCompletion, ...]:
    completions = (
        AuthoringCompletion(
            label=label,
            kind="keyword",
            replacement_range=context.replacement_range,
            insert_text=snippet,
            detail="TSL top-level declaration",
            snippet=True,
            sort_group=0,
        )
        for label, snippet in _TOP_LEVEL_SNIPPETS
        if label.startswith(context.prefix)
    )
    return tuple(sorted(completions, key=_completion_key))


def _field_candidates(
    context: AuthoringCursorContext, catalog: Catalog
) -> tuple[Iterable[str], AuthoringCompletionKind, str]:
    path = context.block_path
    backends = _backend_ids(catalog)
    if path == ("primitive",):
        return KNOWN_PRIMITIVE_FIELDS, "field", "primitive field"
    if path[:2] == ("primitive", "impls"):
        return _implementation_fields(context, catalog)
    if path[:2] == ("primitive", "generic_params"):
        if len(path) == 2:
            return (), "field", "generic parameter"
        if path[-1] == "constraints":
            return _GENERIC_CONSTRAINT_FIELDS, "field", "generic constraint"
        return KNOWN_GENERIC_PARAM_FIELDS, "field", "generic parameter field"
    if path[:2] == ("primitive", "params"):
        if len(path) == 2:
            return context.primitive_parameters, "field", "primitive parameter"
        if path[-1] == "dispatch":
            return backends, "keyword", "backend ID"
        return KNOWN_IMMEDIATE_PARAM_FIELDS, "field", "immediate parameter field"
    if path[:2] == ("primitive", "param_types"):
        if len(path) == 2:
            return context.primitive_parameters, "field", "primitive parameter"
        return _param_type_rules(context, catalog), "field", "parameter type rule"
    if path == ("primitive", "return_type"):
        return KNOWN_RETURN_TYPE_FIELDS, "field", "return type axis"
    if path == ("primitive", "benchmarks"):
        return KNOWN_BENCHMARK_FIELDS, "field", "benchmark field"
    if path == ("primitive", "benchmarks", "operand_domains"):
        return context.primitive_parameters, "field", "benchmark operand"
    if path[-2:] == ("tests", "$item"):
        return KNOWN_TEST_FIELDS, "field", "test metadata field"
    if path[-1:] == ("case",) and "$item" in path:
        return KNOWN_TEST_CASE_FIELDS, "field", "test case field"

    if path == ("extension",):
        return (*KNOWN_EXTENSION_FIELDS, *backends), "field", "extension field"
    if path[:1] == ("extension",):
        return _extension_fields(path, catalog, backends)
    if path == ("types",):
        return (), "field", "type group"
    if path[:1] == ("types",) and len(path) == 2:
        return KNOWN_TYPE_GROUP_FIELDS, "field", "type-group field"
    if path == ("language",):
        return (), "field", "language type"
    if path[:1] == ("language",) and len(path) == 2:
        return KNOWN_LANGUAGE_TYPE_FIELDS, "field", "language type field"
    if path[:1] == ("target_families",):
        return _target_family_fields(path, catalog, backends)
    return (), "field", "TSL field"


def _implementation_fields(
    context: AuthoringCursorContext, catalog: Catalog
) -> tuple[Iterable[str], AuthoringCompletionKind, str]:
    path = context.block_path
    tail = path[2:]
    if not tail:
        return catalog.extensions, "class", "extension selector"
    if len(tail) == 1:
        return catalog.type_groups, "type", "type-group selector"
    if "requires" in tail:
        requires_index = tail.index("requires")
        scoped = tail[requires_index + 1 :]
        if not scoped:
            return catalog.extensions, "class", "required extension selector"
        if len(scoped) == 1:
            return catalog.type_groups, "type", "required type-group selector"
        return (), "field", "requires feature list"
    if path[-1] == "safety":
        variant = "variants" in path
        return (
            KNOWN_VARIANT_SAFETY_FIELDS if variant else KNOWN_SAFETY_FIELDS,
            "field",
            "implementation safety field",
        )
    if path[-1] == "implementation":
        return _IMPLEMENTATION_BODY_FIELDS, "field", "implementation body field"
    if path[-1] == "variants":
        return (), "field", "implementation variant"
    if "variants" in path and path[-2] == "variants":
        return KNOWN_VARIANT_FIELDS, "field", "implementation variant field"
    primitive = _primitive(catalog, context.declaration_name)
    target_axis = primitive.result_target[1] if primitive and primitive.result_target else None
    selector_tail = tail[2:]
    if not selector_tail:
        values: set[str] = set(KNOWN_SELECTOR_METADATA_FIELDS)
        if target_axis is not None:
            values.add(target_axis)
        return values, "field", "implementation selector field"
    if target_axis is not None and selector_tail == (target_axis,):
        if primitive is not None and primitive.result_target is not None:
            if primitive.result_target[0] == "extension":
                return (*catalog.extensions, "where"), "class", "target extension selector"
            return (
                (*catalog.type_groups, *KNOWN_SCALAR_TYPE_TAGS),
                "type",
                "target base selector",
            )
    if path[-1] == "where":
        return KNOWN_TARGET_CONSTRAINT_FIELDS, "field", "target constraint field"
    return KNOWN_SELECTOR_METADATA_FIELDS, "field", "implementation selector field"


def _extension_fields(
    path: tuple[str, ...],
    catalog: Catalog,
    backends: tuple[str, ...],
) -> tuple[Iterable[str], AuthoringCompletionKind, str]:
    name = path[-1]
    if name == "active_when":
        return KNOWN_ACTIVE_WHEN_FIELDS, "field", "activation field"
    if name == "size_parameter":
        return KNOWN_SIZE_PARAMETER_FIELDS, "field", "size parameter field"
    if name == "vector_register_type_policy":
        return KNOWN_VECTOR_REGISTER_POLICY_FIELDS, "field", "register policy field"
    if name == "mask_type_policy":
        return KNOWN_MASK_POLICY_FIELDS, "field", "mask policy field"
    if name == "integral_mask_type_policy":
        return KNOWN_IMASK_POLICY_FIELDS, "field", "integral-mask policy field"
    if name == "intrinsic_compose":
        return KNOWN_INTRINSIC_COMPOSE_FIELDS, "field", "intrinsic composition field"
    if name == "suffix" and "intrinsic_compose" in path:
        return KNOWN_INTRINSIC_SUFFIX_FIELDS, "field", "intrinsic suffix field"
    if name == "prefix" and "intrinsic_compose" in path:
        return backends, "keyword", "backend ID"
    if name == "by_type" and "intrinsic_compose" in path:
        return (*catalog.type_groups, *KNOWN_SCALAR_TYPE_TAGS), "type", "type selector"
    if name == "test_filter":
        return KNOWN_TEST_FILTER_FIELDS, "field", "test-filter field"
    if name in _BACKEND_MAP_FIELDS:
        return backends, "keyword", "backend ID"
    if name == "vector_register_types":
        return (*catalog.type_groups, *KNOWN_SCALAR_TYPE_TAGS), "type", "type selector"
    if "vector_register_types" in path and path[-2] == "vector_register_types":
        return backends, "keyword", "backend ID"
    if name == "backend_spelling_by_lanes":
        return backends, "keyword", "backend ID"
    if name == "compile_guards":
        return (), "field", "compile guard"
    if "compile_guards" in path and path[-2] == "compile_guards":
        return KNOWN_COMPILE_GUARD_FIELDS, "field", "compile guard field"
    if len(path) == 2 and name in backends:
        return KNOWN_EXTENSION_BACKEND_FIELDS, "field", "extension backend field"
    return (), "field", "extension field"


def _target_family_fields(
    path: tuple[str, ...],
    catalog: Catalog,
    backends: tuple[str, ...],
) -> tuple[Iterable[str], AuthoringCompletionKind, str]:
    if path == ("target_families",):
        return KNOWN_TARGET_FAMILIES_FIELDS, "field", "target-family field"
    if path[-1] == "extension_family_capabilities":
        return (
            catalog.target_families.known_extension_families,
            "class",
            "extension family",
        )
    if "extension_family_capabilities" in path and path[-2] == "extension_family_capabilities":
        return KNOWN_EXTENSION_FAMILY_FIELDS, "field", "extension-family capability"
    if path[-1] == "profile_families":
        return catalog.target_families.profile_family_names, "class", "profile family"
    if "profile_families" in path and path[-2] == "profile_families":
        return KNOWN_PROFILE_FAMILY_FIELDS, "field", "profile-family field"
    if path[-1] == "backends" and "profile_families" in path:
        return backends, "keyword", "backend ID"
    if len(path) >= 2 and path[-2] == "backends":
        return KNOWN_BACKEND_PROFILE_FIELDS, "field", "backend profile field"
    return (), "field", "target-family field"


def _value_completions(
    context: AuthoringCursorContext,
    catalog: Catalog,
    target_features: Iterable[str],
) -> tuple[AuthoringCompletion, ...]:
    field = context.current_field
    if field is None:
        return ()
    values: Iterable[str] = ()
    detail = f"value for {field}"
    if field in _BOOLEAN_FIELDS:
        values = KNOWN_BOOLEAN_VALUES
        detail = "boolean"
    elif field == "requires" or (
        context.position_kind == "list-value" and "requires" in context.block_path
    ):
        values = {*target_features, *_catalog_target_features(catalog)}
        detail = "target feature"
    elif field == "target_features":
        values = {*target_features, *_catalog_target_features(catalog)}
        detail = "target feature"
    elif field == "compile_modes":
        values = {
            mode
            for extension in catalog.extensions.values()
            for mode in extension.active_when.compile_modes
        }
        detail = "compile mode"
    elif field in {"type", "to_type", "index_type", "base_types", "types"}:
        values = (*KNOWN_SCALAR_TYPE_TAGS, *catalog.type_groups)
        detail = "TSL datatype"
    elif field in {"extension", "to_extension", "inherits", "supersedes"}:
        values = catalog.extensions
        detail = "extension"
    elif field == "family":
        if context.block_path[-1:] == ("where",):
            values = KNOWN_TARGET_FAMILY_RELATIONS
            detail = "target-family relation"
        else:
            values = catalog.target_families.known_extension_families
            detail = "extension family"
    elif field == "width" and context.block_path[-1:] == ("where",):
        values = KNOWN_TARGET_WIDTH_RELATIONS
        detail = "target-width relation"
    elif field == "kind":
        values, detail = _kind_values(context, catalog)
    elif field == "role":
        values = KNOWN_TEST_ROLES
        detail = "test role"
    elif field == "latency_chain":
        values = context.primitive_parameters
        detail = "primitive parameter"
    elif context.block_path[-1:] == ("operand_domains",):
        values = KNOWN_OPERAND_DOMAINS
        detail = "benchmark operand domain"
    elif "dispatch" in context.block_path:
        values = KNOWN_IMMEDIATE_DISPATCH
        detail = "dispatch strategy"
    elif field == "backends":
        values = _backend_ids(catalog)
        detail = "backend ID"
    elif field in {
        "known_extension_families",
        "universal_extension_families",
        "extension_families",
    }:
        values = catalog.target_families.known_extension_families
        detail = "extension family"
    elif field == "runner_kinds":
        values = {
            runner
            for family in catalog.target_families.profile_families.values()
            for runner in family.runner_kinds
        }
        detail = "runner kind"
    return _values(context, values, detail=detail)


def _kind_values(
    context: AuthoringCursorContext, catalog: Catalog
) -> tuple[Iterable[str], str]:
    path = context.block_path
    if "generic_params" in path:
        return KNOWN_GENERIC_PARAM_KINDS, "generic parameter kind"
    if path[-1:] == ("mask_type_policy",):
        return KNOWN_MASK_POLICY_KINDS, "mask policy kind"
    if path[-1:] == ("integral_mask_type_policy",):
        return KNOWN_IMASK_POLICY_KINDS, "integral-mask policy kind"
    if path[-1:] == ("vector_register_type_policy",):
        return {
            extension.vector_register_type_policy
            for extension in catalog.extensions.values()
            if extension.vector_register_type_policy
        }, "register policy kind"
    return (), "kind"


def _param_type_rules(
    context: AuthoringCursorContext, catalog: Catalog
) -> tuple[str, ...]:
    rules = {"default"}
    for primitive in _primitives(catalog, context.declaration_name):
        for name, value in primitive.attributes.items():
            rules.add(f'"if {name}={value}"')
    return tuple(sorted(rules))


def _primitive(catalog: Catalog, name: str | None) -> Primitive | None:
    return None if name is None else catalog.primitive(name, unmasked=False)


def _primitives(catalog: Catalog, name: str | None) -> tuple[Primitive, ...]:
    return () if name is None else catalog.primitives_named(name, unmasked=False)


def _backend_ids(catalog: Catalog) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                *registered_backend_ids(),
                *catalog.type_spellings,
                *catalog.target_families.backend_ids,
            }
        )
    )


def _catalog_target_features(catalog: Catalog) -> frozenset[str]:
    activation = {
        feature
        for extension in catalog.extensions.values()
        for feature in extension.active_when.target_features
    }
    requirements = {
        feature
        for primitive in catalog.primitives
        for implementation in primitive.implementations
        for clause in implementation.requirements
        for feature in clause.flags
    }
    return frozenset(activation | requirements)


def _values(
    context: AuthoringCursorContext,
    values: Iterable[str],
    *,
    kind: AuthoringCompletionKind = "value",
    detail: str,
    commit_characters: tuple[str, ...] = (),
) -> tuple[AuthoringCompletion, ...]:
    unique = sorted({value for value in values if value.startswith(context.prefix)})
    return tuple(
        AuthoringCompletion(
            label=value,
            kind=kind,
            replacement_range=context.replacement_range,
            insert_text=value,
            detail=detail,
            sort_group=0,
            commit_characters=commit_characters,
        )
        for value in unique
    )


def _completion_key(completion: AuthoringCompletion) -> tuple[int, str, str]:
    return completion.sort_group, completion.label, completion.insert_text


__all__ = (
    "AuthoringCompletion",
    "AuthoringCompletionKind",
    "VAR_SELECTORS",
    "authoring_completions",
)
