from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from tslgen.analysis.expansion import PrimitiveVariant
from tslgen.analysis.requirements import FeatureFlag, RequirementConstraint
from tslgen.analysis.selection import SelectionPlan, VariantImplementationPlan
from tslgen.core.diagnostics import Diagnostic, has_errors, sort_diagnostics
from tslgen.core.frozen_map import FrozenMap
from tslgen.core.result import Result
from tslgen.domain.catalog import Catalog
from tslgen.domain.values import CatalogMap, CatalogValue


@dataclass(frozen=True, slots=True)
class OpaqueImplementationBody:
    kind: str
    payload: CatalogValue

    def __post_init__(self) -> None:
        if not self.kind:
            raise ValueError("implementation body kind must be non-empty")


@dataclass(frozen=True, slots=True)
class ImplementationMetadata:
    extension_selector: str
    type_selector: str
    fields: CatalogMap
    body: OpaqueImplementationBody

    def __post_init__(self) -> None:
        if not self.extension_selector:
            raise ValueError("implementation extension selector must be non-empty")
        if not self.type_selector:
            raise ValueError("implementation type selector must be non-empty")


@dataclass(frozen=True, slots=True)
class ImplementationCandidate:
    candidate_id: str
    variant: PrimitiveVariant
    emitted_primitive_name: str
    source_primitive_name: str
    template_name: str
    backend: str | None
    target_extension: str
    source_extension: str
    type_tag: str
    required_flags: tuple[FeatureFlag, ...]
    implementation: ImplementationMetadata

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("candidate id must be non-empty")
        if not self.target_extension:
            raise ValueError("target extension must be non-empty")
        if not self.source_extension:
            raise ValueError("source extension must be non-empty")
        if not self.type_tag:
            raise ValueError("candidate type tag must be non-empty")
        object.__setattr__(
            self,
            "required_flags",
            tuple(sorted(self.required_flags, key=lambda flag: flag.name)),
        )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.emitted_primitive_name,
            self.source_primitive_name,
            self.template_name,
            self.backend or "",
            self.target_extension,
            self.source_extension,
            self.type_tag,
            tuple(flag.name for flag in self.required_flags),
            self.variant.variant_id,
            self.implementation.extension_selector,
            self.implementation.type_selector,
            self.implementation.body.kind,
        )


@dataclass(frozen=True, slots=True)
class CandidateSelection:
    plan: SelectionPlan
    candidates: tuple[ImplementationCandidate, ...]
    candidates_by_id: FrozenMap[str, ImplementationCandidate] = field(init=False)

    def __post_init__(self) -> None:
        candidates = tuple(sorted(self.candidates, key=lambda candidate: candidate.key))
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(
            self,
            "candidates_by_id",
            FrozenMap((candidate.candidate_id, candidate) for candidate in candidates),
        )


def select_implementation_candidates(
    plan: SelectionPlan,
    catalog: Catalog,
) -> Result[CandidateSelection]:
    diagnostics: list[Diagnostic] = []
    if plan.request.backend is not None and not _known_backend(catalog, plan.request.backend):
        diagnostics.append(
            Diagnostic.error(
                "TSL-CANDIDATE-UNKNOWN-BACKEND",
                f"selection request references unknown backend {plan.request.backend!r}",
            )
        )

    implementation_plans = {
        _implementation_plan_key(implementation_plan): implementation_plan
        for implementation_plan in plan.implementation_plans
    }
    candidates: list[ImplementationCandidate] = []
    for variant in plan.variants:
        selected = _candidates_for_variant(
            variant,
            catalog,
            plan,
            implementation_plans,
        )
        diagnostics.extend(selected.diagnostics)
        if selected.is_ok:
            candidates.extend(selected.unwrap())

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    return Result.ok(
        CandidateSelection(plan=plan, candidates=tuple(candidates)),
        diagnostics=ordered,
    )


def _candidates_for_variant(
    variant: PrimitiveVariant,
    catalog: Catalog,
    plan: SelectionPlan,
    implementation_plans: dict[tuple[str, str, str], VariantImplementationPlan],
) -> Result[tuple[ImplementationCandidate, ...]]:
    impls = _as_map(variant.source.declaration.fields.get("impls"))
    if impls is None:
        return Result.ok(())

    diagnostics: list[Diagnostic] = []
    candidates: list[ImplementationCandidate] = []
    for extension_selector, extension_value in impls.items():
        source_extensions = _source_extensions_by_target(
            catalog,
            _selector_items(extension_selector),
            plan.allowed_extensions,
        )
        if not source_extensions:
            continue

        type_map = _as_map(extension_value)
        if type_map is None:
            diagnostics.append(
                _implementation_shape_diagnostic(
                    variant,
                    "implementation extension selector",
                    extension_selector,
                )
            )
            continue

        for type_selector, implementation_value in type_map.items():
            implementation_map = _as_map(implementation_value)
            if implementation_map is None:
                diagnostics.append(
                    _ambiguous_or_shape_diagnostic(
                        variant,
                        implementation_value,
                        type_selector,
                    )
                )
                continue

            implementation_plan = implementation_plans.get(
                (variant.variant_id, extension_selector, type_selector)
            )
            if implementation_plan is None:
                continue

            metadata = _implementation_metadata(
                variant,
                extension_selector,
                type_selector,
                implementation_map,
            )
            diagnostics.extend(metadata.diagnostics)
            if not metadata.is_ok:
                continue

            for target_extension, source_extension in source_extensions:
                if not _supports_backend(catalog, target_extension, plan.request.backend):
                    continue
                type_tags = _expand_selector_type_tags(
                    catalog,
                    implementation_plan.type_selector.names,
                )
                for type_tag in type_tags:
                    required_flags = _matching_required_flags(
                        catalog,
                        implementation_plan.requirements,
                        target_extension=target_extension,
                        source_extension=source_extension,
                        type_tag=type_tag,
                    )
                    if not _supports_required_flags(plan, required_flags):
                        continue
                    candidates.append(
                        _candidate(
                            variant=variant,
                            plan=plan,
                            target_extension=target_extension,
                            source_extension=source_extension,
                            type_tag=type_tag,
                            required_flags=required_flags,
                            metadata=metadata.unwrap(),
                        )
                    )

    if plan.allowed_extensions and not candidates and not diagnostics:
        diagnostics.append(
            Diagnostic.error(
                "TSL-CANDIDATE-NONE",
                f"primitive variant {variant.variant_id!r} has no implementation "
                "candidate for the requested selector constraints",
                location=variant.source.declaration.source_span.location,
            )
        )

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    return Result.ok(tuple(candidates), diagnostics=ordered)


def _candidate(
    *,
    variant: PrimitiveVariant,
    plan: SelectionPlan,
    target_extension: str,
    source_extension: str,
    type_tag: str,
    required_flags: tuple[FeatureFlag, ...],
    metadata: ImplementationMetadata,
) -> ImplementationCandidate:
    emitted_primitive_name = variant.primitive_name
    source_primitive_name = variant.primitive_name
    candidate_id = _candidate_id(
        variant=variant,
        backend=plan.request.backend,
        target_extension=target_extension,
        source_extension=source_extension,
        type_tag=type_tag,
        required_flags=required_flags,
        metadata=metadata,
    )
    return ImplementationCandidate(
        candidate_id=candidate_id,
        variant=variant,
        emitted_primitive_name=emitted_primitive_name,
        source_primitive_name=source_primitive_name,
        template_name=variant.template_name,
        backend=plan.request.backend,
        target_extension=target_extension,
        source_extension=source_extension,
        type_tag=type_tag,
        required_flags=required_flags,
        implementation=metadata,
    )


def _candidate_id(
    *,
    variant: PrimitiveVariant,
    backend: str | None,
    target_extension: str,
    source_extension: str,
    type_tag: str,
    required_flags: tuple[FeatureFlag, ...],
    metadata: ImplementationMetadata,
) -> str:
    flags = "+".join(flag.name for flag in required_flags) or "none"
    backend_name = backend if backend is not None else "any"
    return (
        f"{variant.variant_id}|backend={backend_name}|target={target_extension}"
        f"|source={source_extension}|type={type_tag}|flags={flags}"
        f"|impl={metadata.extension_selector}/{metadata.type_selector}"
        f"/{metadata.body.kind}"
    )


def _implementation_metadata(
    variant: PrimitiveVariant,
    extension_selector: str,
    type_selector: str,
    implementation_map: CatalogMap,
) -> Result[ImplementationMetadata]:
    body_result = _implementation_body(variant, implementation_map)
    if not body_result.is_ok:
        return Result.failure(body_result.diagnostics)
    return Result.ok(
        ImplementationMetadata(
            extension_selector=extension_selector,
            type_selector=type_selector,
            fields=implementation_map,
            body=body_result.unwrap(),
        ),
        diagnostics=body_result.diagnostics,
    )


def _implementation_body(
    variant: PrimitiveVariant,
    implementation_map: CatalogMap,
) -> Result[OpaqueImplementationBody]:
    body_value = implementation_map.get("implementation")
    if body_value is None:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-CANDIDATE-BODY-MISSING",
                    f"primitive {variant.primitive_name!r} implementation is missing "
                    "an 'implementation' body",
                    location=variant.source.declaration.source_span.location,
                ),
            )
        )

    body_map = _as_map(body_value)
    if body_map is None or len(body_map) == 0:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-CANDIDATE-BODY-SHAPE",
                    f"primitive {variant.primitive_name!r} implementation body must "
                    "be a non-empty field map",
                    location=variant.source.declaration.source_span.location,
                ),
            )
        )
    if len(body_map) > 1:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-CANDIDATE-BODY-AMBIGUOUS",
                    f"primitive {variant.primitive_name!r} implementation body has "
                    "multiple payload fields",
                    location=variant.source.declaration.source_span.location,
                ),
            )
        )

    kind, payload = next(iter(body_map.items()))
    return Result.ok(OpaqueImplementationBody(kind=kind, payload=payload))


def _source_extensions_by_target(
    catalog: Catalog,
    selector_names: tuple[str, ...],
    allowed_extensions: tuple[str, ...],
) -> tuple[tuple[str, str], ...]:
    selector_set = frozenset(selector_names)
    pairs: list[tuple[str, str]] = []
    for target_extension in allowed_extensions:
        for source_extension in _extension_fallback_chain(catalog, target_extension):
            if source_extension in selector_set:
                pairs.append((target_extension, source_extension))
                break
    return tuple(pairs)


def _extension_fallback_chain(catalog: Catalog, extension_name: str) -> tuple[str, ...]:
    chain: list[str] = []
    seen: set[str] = set()
    current_name: str | None = extension_name
    while current_name is not None and current_name not in seen:
        seen.add(current_name)
        extension = catalog.extensions_by_name.get(current_name)
        if extension is None:
            break
        chain.append(current_name)
        inherited = extension.fields.get("inherits")
        current_name = inherited if isinstance(inherited, str) else None
    return tuple(chain)


def _expand_selector_type_tags(
    catalog: Catalog,
    type_group_names: tuple[str, ...],
) -> tuple[str, ...]:
    tags: list[str] = []
    seen: set[str] = set()
    for type_group_name in type_group_names:
        for type_tag in _expand_type_group(catalog, type_group_name, ()):
            if type_tag not in seen:
                seen.add(type_tag)
                tags.append(type_tag)
    return tuple(tags)


def _expand_type_group(
    catalog: Catalog,
    type_group_name: str,
    stack: tuple[str, ...],
) -> tuple[str, ...]:
    if type_group_name in stack:
        return ()
    type_group = catalog.type_groups_by_name.get(type_group_name)
    if type_group is None:
        return ()

    tags: list[str] = []
    seen: set[str] = set()
    next_stack = (*stack, type_group_name)
    for member in type_group.members:
        member_tags: tuple[str, ...]
        if member == type_group_name:
            member_tags = (member,)
        elif member in catalog.type_groups_by_name:
            member_tags = _expand_type_group(catalog, member, next_stack)
        else:
            member_tags = (member,)
        for member_tag in member_tags:
            if member_tag not in seen:
                seen.add(member_tag)
                tags.append(member_tag)
    return tuple(tags)


def _matching_required_flags(
    catalog: Catalog,
    requirements: tuple[RequirementConstraint, ...],
    *,
    target_extension: str,
    source_extension: str,
    type_tag: str,
) -> tuple[FeatureFlag, ...]:
    flags: set[FeatureFlag] = set()
    for requirement in requirements:
        if not _extension_requirement_matches(
            catalog,
            requirement,
            target_extension=target_extension,
            source_extension=source_extension,
        ):
            continue
        if not _type_requirement_matches(catalog, requirement, type_tag):
            continue
        flags.update(requirement.required_flags)
    return tuple(sorted(flags, key=lambda flag: flag.name))


def _extension_requirement_matches(
    catalog: Catalog,
    requirement: RequirementConstraint,
    *,
    target_extension: str,
    source_extension: str,
) -> bool:
    if not requirement.extension_names:
        return True
    allowed_context = frozenset(
        extension
        for requirement_extension in requirement.extension_names
        for extension in _extension_fallback_chain(catalog, requirement_extension)
    )
    return target_extension in allowed_context or source_extension in allowed_context


def _type_requirement_matches(
    catalog: Catalog,
    requirement: RequirementConstraint,
    type_tag: str,
) -> bool:
    if not requirement.type_group_names:
        return True
    return any(
        type_tag in _expand_type_group(catalog, type_group_name, ())
        for type_group_name in requirement.type_group_names
    )


def _supports_required_flags(
    plan: SelectionPlan,
    required_flags: tuple[FeatureFlag, ...],
) -> bool:
    if not plan.request.cpu_flags:
        return True
    available = frozenset(flag.name for flag in plan.normalized_cpu_flags)
    return frozenset(flag.name for flag in required_flags) <= available


def _supports_backend(
    catalog: Catalog,
    extension_name: str,
    backend: str | None,
) -> bool:
    if backend is None:
        return True

    saw_backend_metadata = False
    for fallback_name in _extension_fallback_chain(catalog, extension_name):
        extension = catalog.extensions_by_name.get(fallback_name)
        if extension is None:
            continue
        backend_fields = _as_map(extension.fields.get(backend))
        if backend_fields is None:
            continue
        saw_backend_metadata = True
        supported = backend_fields.get("supported")
        if supported is False:
            return False
        if supported is True:
            return True
    return not saw_backend_metadata


def _known_backend(catalog: Catalog, backend: str) -> bool:
    return any(
        isinstance(extension.fields.get(backend), FrozenMap)
        for extension in catalog.extensions
    )


def _implementation_plan_key(
    implementation_plan: VariantImplementationPlan,
) -> tuple[str, str, str]:
    return (
        implementation_plan.variant_id,
        implementation_plan.extension_selector.raw,
        implementation_plan.type_selector.raw,
    )


def _selector_items(selector: str) -> tuple[str, ...]:
    stripped = selector.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        inner = stripped[1:-1].strip()
        if not inner:
            return ()
        raw_items = tuple(item.strip() for item in inner.split(",") if item.strip())
    else:
        raw_items = (stripped,)
    return tuple(_selector_base_name(item) for item in raw_items)


def _selector_base_name(selector_item: str) -> str:
    if "<" in selector_item and selector_item.endswith(">"):
        return selector_item.split("<", 1)[0]
    return selector_item


def _ambiguous_or_shape_diagnostic(
    variant: PrimitiveVariant,
    value: CatalogValue,
    selector: str,
) -> Diagnostic:
    if isinstance(value, tuple):
        return Diagnostic.error(
            "TSL-CANDIDATE-AMBIGUOUS-IMPLEMENTATION",
            f"primitive {variant.primitive_name!r} has list-backed implementation "
            f"variants for selector {selector!r}; selection policy is unresolved",
            location=variant.source.declaration.source_span.location,
        )
    return _implementation_shape_diagnostic(
        variant,
        "implementation type selector",
        selector,
    )


def _implementation_shape_diagnostic(
    variant: PrimitiveVariant,
    context: str,
    selector: str,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-CANDIDATE-IMPLEMENTATION-SHAPE",
        f"primitive {variant.primitive_name!r} has unsupported {context} "
        f"shape for selector {selector!r}",
        location=variant.source.declaration.source_span.location,
    )


def _as_map(value: CatalogValue | None) -> CatalogMap | None:
    if isinstance(value, FrozenMap):
        return cast(CatalogMap, value)
    return None
