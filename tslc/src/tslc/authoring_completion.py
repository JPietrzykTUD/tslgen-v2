"""Compiler-owned catalog completion records and closed authoring vocabularies."""

from __future__ import annotations

from collections.abc import Iterable

from tslc.authoring_completion_model import (
    AuthoringCompletion,
    AuthoringCompletionKind,
    completion_key as _completion_key,
)
from tslc.authoring_tsil_completion import (
    merge_completions as _merge_completions,
    tsil_argument_completions as _tsil_argument_completions,
    tsil_shell_completions as _tsil_shell_completions,
)
from tslc.backend.registry import (
    registered_backend_ids,
    registered_compiler_capabilities,
)
from tslc.catalog.arithmetic import (
    arithmetic_guarantee_values,
    arithmetic_operand_role_values,
    arithmetic_operation_values,
)
from tslc.catalog.arithmetic_promotion import KNOWN_ARITHMETIC_FIELDS
from tslc.catalog.conversion import (
    conversion_kind_values,
    lane_count_relation_values,
    numeric_conversion_mode_values,
)
from tslc.catalog.conversion_promotion import KNOWN_CONVERSION_FIELDS
from tslc.catalog.memory import memory_access_values, memory_addressing_values
from tslc.catalog.memory_promotion import KNOWN_MEMORY_FIELDS
from tslc.catalog.model import (
    Catalog,
    IntrinsicNameOrder,
    Primitive,
    RESULT_DIM_VECTOR,
)
from tslc.catalog.semantics import operand_role_values, primitive_operation_values
from tslc.catalog.scalar_types import KNOWN_SCALAR_TYPE_TAGS
from tslc.catalog.shift import shift_count_rule_values, shift_lane_rule_values
from tslc.catalog.shift_promotion import KNOWN_SHIFT_FIELDS
from tslc.catalog.signature_kinds import DEFAULT_SIGNATURE_KINDS
from tslc.catalog.validation._schema_benchmarks import (
    KNOWN_BENCHMARK_FIELDS,
    KNOWN_OPERAND_DOMAINS,
)
from tslc.catalog.validation._schema_common import KNOWN_BOOLEAN_VALUES
from tslc.catalog.validation._schema_extensions import (
    KNOWN_ACTIVE_WHEN_FIELDS,
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
    KNOWN_PRIMITIVE_OVERLOAD_FIELDS,
    KNOWN_RETURN_TYPE_FIELDS,
)
from tslc.catalog.validation._schema_overloads import (
    KNOWN_OVERLOAD_AXIS_FIELDS,
    KNOWN_OVERLOAD_VALUE_FIELDS,
)
from tslc.catalog.validation._schema_target_families import (
    KNOWN_BACKEND_PROFILE_FIELDS,
    KNOWN_EXTENSION_FAMILY_FIELDS,
    KNOWN_PROFILE_FAMILY_FIELDS,
    KNOWN_TARGET_FAMILIES_FIELDS,
)
from tslc.catalog.validation._schema_tests import (
    KNOWN_TEST_COMPARISONS,
    KNOWN_TEST_CASE_FIELDS,
    KNOWN_TEST_FIELDS,
    KNOWN_TEST_ROLES,
)
from tslc.catalog.validation.schema_validation import (
    KNOWN_LANGUAGE_TYPE_FIELDS,
    KNOWN_TYPE_GROUP_FIELDS,
)
from tslc.ir.region_registry import (
    TSIL_REGION_BY_KEYWORD,
    TSIL_REGION_KEYWORDS,
)
from tslc.lower.query_authoring import query_authoring_index
from tslc.syntax.authoring import AuthoringCursorContext


VAR_SELECTORS = tuple(
    sorted(
        {
            value
            for form in TSIL_REGION_BY_KEYWORD["var"].authoring.selector_forms
            for term in form
            for value in term.values
        }
    )
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
        "pass_target_to_compiler",
        "primary",
        "require_explicit_suffix",
        "requires_declared_vector_register",
        "specialize_base",
        "supported",
        "unroll_variants",
        "width_indexed_registers",
    }
)
_BACKEND_MAP_FIELDS = frozenset(
    {
        "backend_spelling",
        "backend_spelling_by_type",
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
    ("overload_axes", "overload_axes:\n  ${0}"),
)


def authoring_completions(
    context: AuthoringCursorContext,
    catalog: Catalog,
    *,
    target_features: Iterable[str] = (),
) -> tuple[AuthoringCompletion, ...]:
    """Return deterministic schema/catalog completion records for one cursor."""

    if context.current_field == "$region-shell":
        return _tsil_shell_completions(context, catalog)
    if context.current_field == "$region-keyword":
        queries = _tsil_argument_completions(context, catalog)
        query_index = query_authoring_index(catalog)
        query_cursor = (
            None
            if context.tsil_argument_prefix is None
            else query_index.cursor(context.tsil_argument_prefix)
        )
        if query_cursor is not None and "::" in query_cursor.prefix:
            return queries
        regions = _values(
            context,
            TSIL_REGION_KEYWORDS,
            kind="keyword",
            detail="TSIL region",
        )
        return _merge_completions((*regions, *queries))
    if context.current_field == "$primitive_signature":
        return _values(
            context,
            {primitive.signature for primitive in catalog.primitives},
            detail="primitive signature shape",
            commit_characters=(">",),
        )

    if context.declaration_kind is None:
        return _top_level(context)

    if context.position_kind == "tsil-raw":
        return _tsil_argument_completions(context, catalog)

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
    if path == ("primitive", "overload"):
        return KNOWN_PRIMITIVE_OVERLOAD_FIELDS, "field", "primitive overload field"
    if path == ("primitive", "arithmetic"):
        return KNOWN_ARITHMETIC_FIELDS, "field", "arithmetic contract field"
    if path == ("primitive", "arithmetic", "operand_roles"):
        return arithmetic_operand_role_values(), "field", "arithmetic operand role"
    if path == ("primitive", "operand_roles"):
        return operand_role_values(), "field", "primitive operand role"
    if path == ("primitive", "memory"):
        return KNOWN_MEMORY_FIELDS, "field", "memory contract field"
    if path == ("primitive", "conversion"):
        return KNOWN_CONVERSION_FIELDS, "field", "conversion contract field"
    if path == ("primitive", "shift"):
        return KNOWN_SHIFT_FIELDS, "field", "shift contract field"
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
    if path[:1] == ("overload_axes",):
        return _overload_registry_fields(path, catalog)
    return (), "field", "TSL field"


def _overload_registry_fields(
    path: tuple[str, ...],
    catalog: Catalog,
) -> tuple[Iterable[str], AuthoringCompletionKind, str]:
    if path == ("overload_axes",):
        return catalog.overload_registry.axes, "class", "overload axis"
    if len(path) == 2:
        return KNOWN_OVERLOAD_AXIS_FIELDS, "field", "overload axis field"
    if len(path) == 3 and path[-1] == "values":
        axis = catalog.overload_registry.axis(path[-2])
        return (
            () if axis is None else axis.values,
            "value",
            "overload value",
        )
    if len(path) == 4 and path[-2] == "values":
        return KNOWN_OVERLOAD_VALUE_FIELDS, "field", "overload value field"
    return (), "field", "overload registry field"


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
            return (
                (*catalog.extensions, "target_features", "compiler"),
                "field",
                "requires axis",
            )
        if scoped == ("target_features",):
            return (), "field", "target feature list"
        if scoped == ("compiler",):
            return registered_backend_ids(), "class", "compiler backend"
        if len(scoped) == 2 and scoped[0] == "compiler":
            return ("capabilities",), "field", "compiler requirement field"
        if len(scoped) == 3 and scoped[0] == "compiler":
            return (), "field", "compiler capability list"
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
    target_axis = (
        primitive.result_target[1]
        if primitive
        and primitive.result_target
        and primitive.result_target[0] != RESULT_DIM_VECTOR
        else None
    )
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
    if "backend_spelling_by_type" in path and path[-2] == "backend_spelling_by_type":
        return (*catalog.type_groups, *KNOWN_SCALAR_TYPE_TAGS), "type", "scalar type"
    if name == "vector_register_types":
        return (*catalog.type_groups, *KNOWN_SCALAR_TYPE_TAGS), "type", "type selector"
    if "vector_register_types" in path and path[-2] == "vector_register_types":
        return backends, "keyword", "backend ID"
    if name == "backend_spelling_by_lanes":
        return backends, "keyword", "backend ID"
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
    if (
        context.block_path == ("primitive", "operand_roles")
        and field in operand_role_values()
    ):
        values = context.primitive_parameters
        detail = "primitive parameter"
    elif field in _BOOLEAN_FIELDS:
        values = KNOWN_BOOLEAN_VALUES
        detail = "boolean"
    elif (
        field == "order"
        and context.block_path[-1:] == ("intrinsic_compose",)
    ):
        values = tuple(item.value for item in IntrinsicNameOrder)
        detail = "intrinsic name order"
    elif field == "operation" and context.block_path == ("primitive",):
        values = primitive_operation_values()
        detail = "primitive operation"
    elif field == "access" and context.block_path == ("primitive", "memory"):
        values = memory_access_values()
        detail = "memory access"
    elif field == "addressing" and context.block_path == ("primitive", "memory"):
        values = memory_addressing_values()
        detail = "memory addressing"
    elif field == "kind" and context.block_path == ("primitive", "conversion"):
        values = conversion_kind_values()
        detail = "conversion kind"
    elif field == "lane_count" and context.block_path == ("primitive", "conversion"):
        values = lane_count_relation_values()
        detail = "conversion lane-count relation"
    elif field == "numeric_mode" and context.block_path == ("primitive", "conversion"):
        values = numeric_conversion_mode_values()
        detail = "numeric conversion mode"
    elif field == "count_rule" and context.block_path == ("primitive", "shift"):
        values = shift_count_rule_values()
        detail = "shift count rule"
    elif field == "lane_rule" and context.block_path == ("primitive", "shift"):
        values = shift_lane_rule_values()
        detail = "shift lane rule"
    elif field == "scalar_count_types" and context.block_path == (
        "primitive",
        "shift",
    ):
        values = KNOWN_SCALAR_TYPE_TAGS
        detail = "shift scalar count type"
    elif field == "operations" and context.block_path == ("primitive", "arithmetic"):
        values = arithmetic_operation_values()
        detail = "arithmetic operation"
    elif field == "guarantees" and context.block_path == ("primitive", "arithmetic"):
        values = arithmetic_guarantee_values()
        detail = "arithmetic guarantee"
    elif (
        context.block_path == ("primitive", "arithmetic", "operand_roles")
        and field in arithmetic_operand_role_values()
    ):
        values = context.primitive_parameters
        detail = "primitive parameter"
    elif field == "axis" and context.block_path == ("primitive", "overload"):
        values = catalog.overload_registry.axes
        detail = "overload axis"
    elif field == "value" and context.block_path == ("primitive", "overload"):
        sibling_scalars = dict(context.sibling_scalars)
        axis = catalog.overload_registry.axis(sibling_scalars.get("axis", ""))
        values = () if axis is None else axis.values
        detail = "overload value"
    elif field == "operand_kinds" and "overload_axes" in context.block_path:
        values = DEFAULT_SIGNATURE_KINDS.supported_kinds
        detail = "signature kind"
    elif (
        field == "capabilities"
        and "compiler" in context.block_path
    ):
        compiler_index = context.block_path.index("compiler")
        backend_id = (
            context.block_path[compiler_index + 1]
            if len(context.block_path) > compiler_index + 1
            else ""
        )
        values = registered_compiler_capabilities().get(backend_id, ())
        detail = "compiler capability"
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
    elif field == "comparison":
        values = KNOWN_TEST_COMPARISONS
        detail = "test comparison"
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


__all__ = (
    "AuthoringCompletion",
    "AuthoringCompletionKind",
    "VAR_SELECTORS",
    "authoring_completions",
)
