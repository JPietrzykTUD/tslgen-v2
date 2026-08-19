"""TSIL query and region-shell completion projection."""

from __future__ import annotations

from collections.abc import Iterable

from tslc.authoring_completion_model import (
    AuthoringCompletion,
    AuthoringCompletionKind,
    completion_key as _completion_key,
)
from tslc.catalog.model import Catalog, RESULT_DIM_VECTOR
from tslc.ir.region_registry import (
    TSIL_REGION_BY_KEYWORD,
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


def tsil_argument_completions(
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
                (
                    frozenset({"type"})
                    if dimension == "base"
                    else frozenset({"simd_type"})
                    if dimension == RESULT_DIM_VECTOR
                    else frozenset({"text"})
                ),
                (
                    "primitive result vector type parameter"
                    if dimension == RESULT_DIM_VECTOR
                    else f"primitive {dimension} selector axis"
                ),
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


def merge_completions(
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


def tsil_shell_completions(
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
    descriptor = next(
        (option for option in options if option.name == key.strip()),
        None,
    )
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
            tuple(
                sorted({"@self", *(primitive.name for primitive in catalog.primitives)})
            ),
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


__all__ = (
    "merge_completions",
    "tsil_argument_completions",
    "tsil_shell_completions",
)
