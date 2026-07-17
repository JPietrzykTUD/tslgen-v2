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
from tslc.ir.region_registry import (
    TSIL_REGION_BY_KEYWORD,
    TSIL_REGION_KEYWORDS,
    TsilDynamicValueSource,
    TsilSelectorOptionDescriptor,
    TsilSelectorTermDescriptor,
)
from tslc.lower._query_model import QueryValueKind
from tslc.lower.query_authoring import (
    QueryScopeSymbol,
    query_authoring_index,
)
from tslc.syntax.authoring import AuthoringCursorContext, AuthoringTextRange


AuthoringCompletionKind = Literal[
    "field",
    "keyword",
    "value",
    "function",
    "class",
    "type",
]

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


def _tsil_argument_completions(
    context: AuthoringCursorContext,
    catalog: Catalog,
) -> tuple[AuthoringCompletion, ...]:
    argument_prefix = context.tsil_argument_prefix
    argument_start = context.tsil_argument_start
    if (
        argument_prefix is None
        or argument_start is None
        or context.tsil_in_opaque_text
    ):
        return ()
    return _query_completions(context, catalog, argument_prefix, argument_start)


def _query_completions(
    context: AuthoringCursorContext,
    catalog: Catalog,
    expression_prefix: str,
    expression_start: int,
) -> tuple[AuthoringCompletion, ...]:
    candidates = query_authoring_index(catalog).complete(
        expression_prefix,
        _query_scope_symbols(context, catalog),
    )
    kind_by_candidate: dict[str, AuthoringCompletionKind] = {
        "function": "function",
        "namespace": "class",
        "type": "type",
        "value": "value",
    }
    return tuple(
        AuthoringCompletion(
            label=candidate.label,
            kind=kind_by_candidate[candidate.kind],
            replacement_range=AuthoringTextRange(
                expression_start + candidate.replacement_start,
                context.offset,
            ),
            insert_text=candidate.insert_text,
            detail=candidate.detail,
            commit_characters=candidate.commit_characters,
        )
        for candidate in candidates
    )


def _query_scope_symbols(
    context: AuthoringCursorContext,
    catalog: Catalog,
) -> tuple[QueryScopeSymbol, ...]:
    symbols: list[QueryScopeSymbol] = [
        QueryScopeSymbol(
            parameter,
            frozenset({"text"}),
            "primitive parameter",
        )
        for parameter in context.primitive_parameters
    ]
    primitives = (
        ()
        if context.declaration_name is None
        else catalog.primitives_named(context.declaration_name, unmasked=False)
    )
    generic_kinds: dict[str, str] = {
        parameter.name: parameter.kind
        for primitive in primitives
        for parameter in primitive.generic_params
    }
    generic_kinds.update(context.generic_parameter_kinds)
    for name in context.generic_parameters:
        kind = generic_kinds.get(name)
        query_kinds: frozenset[QueryValueKind] = (
            frozenset({"simd_type"})
            if kind == "simd_type"
            else frozenset({"text"})
        )
        detail = "generic parameter" if kind is None else f"generic parameter ({kind})"
        symbols.append(QueryScopeSymbol(name, query_kinds, detail))

    attribute_names = {
        *context.primitive_attributes,
        *(key for primitive in primitives for key in primitive.attribute_keys),
        *(key for primitive in primitives for key in primitive.attributes),
    }
    symbols.extend(
        QueryScopeSymbol(
            attribute,
            frozenset({"text"}),
            "primitive selector axis",
            role="attribute",
        )
        for attribute in sorted(attribute_names)
    )
    for primitive in primitives:
        if primitive.result_target is None:
            continue
        dimension, name = primitive.result_target
        symbols.append(
            QueryScopeSymbol(
                name,
                frozenset({"type"}) if dimension == "base" else frozenset({"text"}),
                f"primitive {dimension} selector axis",
            )
        )
    for name, extension in catalog.extensions.items():
        symbols.append(
            QueryScopeSymbol(
                name,
                frozenset({"text"}),
                "extension",
                role="extension",
            )
        )
        if extension.isa_name != name:
            symbols.append(
                QueryScopeSymbol(
                    extension.isa_name,
                    frozenset({"text"}),
                    "extension ISA",
                    role="extension",
                )
            )
    unique = {
        (symbol.name, symbol.detail, symbol.role): symbol for symbol in symbols
    }
    return tuple(
        sorted(
            unique.values(),
            key=lambda symbol: (symbol.name, symbol.detail, symbol.role),
        )
    )


def _merge_completions(
    completions: Iterable[AuthoringCompletion],
) -> tuple[AuthoringCompletion, ...]:
    unique = {
        (
            completion.label,
            completion.detail,
            completion.replacement_range.start,
            completion.insert_text,
        ): completion
        for completion in completions
    }
    return tuple(sorted(unique.values(), key=_completion_key))


def _tsil_shell_completions(
    context: AuthoringCursorContext,
    catalog: Catalog,
) -> tuple[AuthoringCompletion, ...]:
    keyword = context.tsil_region_keyword
    selector_start = context.tsil_selector_start
    selector_prefix = context.tsil_selector_prefix
    if keyword is None or selector_start is None or selector_prefix is None:
        return ()
    descriptor = TSIL_REGION_BY_KEYWORD.get(keyword)
    if descriptor is None:
        return ()

    terms, starts = _selector_cursor_terms(selector_prefix)
    previous = tuple(term.strip() for term in terms[:-1])
    current = terms[-1]
    current_start = starts[-1]
    candidates: list[AuthoringCompletion] = []
    seen_specs: set[TsilSelectorTermDescriptor] = set()
    for form in descriptor.authoring.selector_forms:
        if len(previous) >= len(form):
            continue
        if not all(
            _selector_term_matches(term, spec)
            for term, spec in zip(previous, form, strict=False)
        ):
            continue
        spec = form[len(previous)]
        if spec in seen_specs:
            continue
        seen_specs.add(spec)
        candidates.extend(
            _selector_term_completions(
                context,
                catalog,
                spec,
                current,
                selector_start + current_start,
            )
        )
    unique = {
        (
            item.label,
            item.insert_text,
            item.replacement_range.start,
            item.replacement_range.end,
        ): item
        for item in candidates
    }
    return tuple(sorted(unique.values(), key=_completion_key))


def _selector_term_completions(
    context: AuthoringCursorContext,
    catalog: Catalog,
    spec: TsilSelectorTermDescriptor,
    raw_current: str,
    absolute_start: int,
) -> tuple[AuthoringCompletion, ...]:
    leading = len(raw_current) - len(raw_current.lstrip())
    current = raw_current.strip()
    token_start = absolute_start + leading
    if spec.kind == "value":
        if any(character in current for character in "[]=,"):
            return ()
        values, kind, detail = _dynamic_selector_values(spec.dynamic_values, catalog)
        return _shell_values(
            (*spec.values, *values),
            prefix=current,
            replacement=AuthoringTextRange(token_start, context.offset),
            kind=kind,
            detail=detail or "TSIL selector value",
        )
    if spec.kind == "named":
        assert spec.name is not None
        key, separator, value = current.partition("=")
        if not separator:
            return _shell_key(
                spec.name,
                prefix=current,
                replacement=AuthoringTextRange(token_start, context.offset),
                detail="TSIL selector key",
            )
        if key.strip() != spec.name or any(character in value for character in "[]"):
            return ()
        value_leading = len(value) - len(value.lstrip())
        value_prefix = value.strip()
        value_start = token_start + current.index("=") + 1 + value_leading
        values, kind, detail = _dynamic_selector_values(spec.dynamic_values, catalog)
        return _shell_values(
            (*spec.values, *values),
            prefix=value_prefix,
            replacement=AuthoringTextRange(value_start, context.offset),
            kind=kind,
            detail=detail or f"value for {spec.name}",
        )
    return _selector_bag_completions(
        context,
        catalog,
        spec,
        current,
        token_start,
    )


def _selector_bag_completions(
    context: AuthoringCursorContext,
    catalog: Catalog,
    spec: TsilSelectorTermDescriptor,
    current: str,
    token_start: int,
) -> tuple[AuthoringCompletion, ...]:
    assert spec.name is not None
    bracket = current.find("[")
    if bracket < 0:
        return _shell_key(
            spec.name,
            prefix=current,
            replacement=AuthoringTextRange(token_start, context.offset),
            detail="TSIL selector option bag",
            insert_text=spec.name,
            commit_characters=("[",),
        )
    if current[:bracket].strip() != spec.name or "]" in current[bracket + 1 :]:
        return ()
    inner = current[bracket + 1 :]
    terms, starts = _selector_cursor_terms(inner)
    if not all(_selector_option_matches(term, spec.options) for term in terms[:-1]):
        return ()
    option_current = terms[-1]
    option_leading = len(option_current) - len(option_current.lstrip())
    option = option_current.strip()
    option_start = token_start + bracket + 1 + starts[-1] + option_leading
    key, separator, value = option.partition("=")
    if not separator:
        records: list[AuthoringCompletion] = []
        for candidate in spec.options:
            records.extend(
                _shell_key(
                    candidate.name,
                    prefix=option,
                    replacement=AuthoringTextRange(option_start, context.offset),
                    detail=f"{spec.name} option",
                    insert_text=candidate.insert_text or f"{candidate.name}=",
                    snippet=candidate.insert_text is not None,
                )
            )
        return tuple(records)
    option_key = key.strip()
    option_descriptor = next(
        (candidate for candidate in spec.options if candidate.name == option_key),
        None,
    )
    if (
        option_descriptor is None
        and option_key.startswith("immediate(")
        and option_key.endswith(")")
    ):
        option_descriptor = next(
            (candidate for candidate in spec.options if candidate.name == "immediate"),
            None,
        )
    if option_descriptor is None:
        return ()
    value_leading = len(value) - len(value.lstrip())
    value_prefix = value.strip()
    value_start = option_start + option.index("=") + 1 + value_leading
    if option_descriptor.open_value:
        return _query_completions(
            context,
            catalog,
            value_prefix,
            value_start,
        )
    return _shell_values(
        option_descriptor.values,
        prefix=value_prefix,
        replacement=AuthoringTextRange(value_start, context.offset),
        detail=f"value for {spec.name}.{option_descriptor.name}",
    )


def _selector_term_matches(raw: str, spec: TsilSelectorTermDescriptor) -> bool:
    term = raw.strip()
    if not term:
        return False
    if spec.kind == "value":
        return (
            spec.open_value
            or spec.dynamic_values is not None
            or term in spec.values
        )
    if spec.kind == "named":
        assert spec.name is not None
        key, separator, value = term.partition("=")
        if not separator or key.strip() != spec.name or not value.strip():
            return False
        if spec.open_value or spec.dynamic_values is not None:
            return True
        return value.strip() in spec.values
    assert spec.name is not None
    if term == spec.name:
        return spec.allow_bare
    if not term.startswith(f"{spec.name}[") or not term.endswith("]"):
        return False
    inner = term[len(spec.name) + 1 : -1]
    return all(
        _selector_option_matches(option, spec.options)
        for option in _selector_cursor_terms(inner)[0]
    )


def _selector_option_matches(
    raw: str,
    options: tuple[TsilSelectorOptionDescriptor, ...],
) -> bool:
    key, separator, value = raw.strip().partition("=")
    if not separator or not value.strip():
        return False
    descriptor = next((option for option in options if option.name == key.strip()), None)
    if descriptor is None:
        return key.strip().startswith("immediate(") and key.strip().endswith(")")
    return descriptor.open_value or value.strip() in descriptor.values


def _selector_cursor_terms(text: str) -> tuple[tuple[str, ...], tuple[int, ...]]:
    starts = [0]
    round_depth = 0
    square_depth = 0
    angle_depth = 0
    index = 0
    while index < len(text):
        character = text[index]
        if character == '"':
            index += 1
            while index < len(text):
                if text[index] == "\\":
                    index += 2
                    continue
                if text[index] == '"':
                    index += 1
                    break
                index += 1
            continue
        if character == "(":
            round_depth += 1
        elif character == ")" and round_depth:
            round_depth -= 1
        elif character == "[":
            square_depth += 1
        elif character == "]" and square_depth:
            square_depth -= 1
        elif character == "<":
            angle_depth += 1
        elif character == ">" and angle_depth:
            angle_depth -= 1
        elif (
            character == ","
            and not round_depth
            and not square_depth
            and not angle_depth
        ):
            starts.append(index + 1)
        index += 1
    terms = tuple(
        text[start : starts[position + 1] - 1]
        if position + 1 < len(starts)
        else text[start:]
        for position, start in enumerate(starts)
    )
    return terms, tuple(starts)


def _dynamic_selector_values(
    source: TsilDynamicValueSource | None,
    catalog: Catalog,
) -> tuple[tuple[str, ...], AuthoringCompletionKind, str | None]:
    if source == "primitive":
        return (
            tuple(sorted({"@self", *(primitive.name for primitive in catalog.primitives)})),
            "function",
            "TSL primitive",
        )
    if source is None:
        return (), "value", None
    prefix = {
        "cast": "cast_",
        "helper": "helper_",
        "operator": "op_",
    }[source]
    values = {
        key[len(prefix) :]
        for templates in catalog.translations.values()
        for key in templates
        if key.startswith(prefix)
    }
    return tuple(sorted(values)), "value", f"TSIL {source} selector"


def _shell_key(
    label: str,
    *,
    prefix: str,
    replacement: AuthoringTextRange,
    detail: str,
    insert_text: str | None = None,
    snippet: bool = False,
    commit_characters: tuple[str, ...] = (),
) -> tuple[AuthoringCompletion, ...]:
    if not label.startswith(prefix):
        return ()
    return (
        AuthoringCompletion(
            label=label,
            kind="keyword",
            replacement_range=replacement,
            insert_text=insert_text or f"{label}=",
            detail=detail,
            snippet=snippet,
            commit_characters=commit_characters,
        ),
    )


def _shell_values(
    values: Iterable[str],
    *,
    prefix: str,
    replacement: AuthoringTextRange,
    detail: str,
    kind: AuthoringCompletionKind = "value",
) -> tuple[AuthoringCompletion, ...]:
    return tuple(
        AuthoringCompletion(
            label=value,
            kind=kind,
            replacement_range=replacement,
            insert_text=value,
            detail=detail,
        )
        for value in sorted({value for value in values if value.startswith(prefix)})
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
