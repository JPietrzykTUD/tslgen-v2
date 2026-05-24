from __future__ import annotations

from dataclasses import dataclass, field

from tslgen.core.diagnostics import Diagnostic, has_errors, sort_diagnostics
from tslgen.core.frozen_map import FrozenMap
from tslgen.core.result import Result
from tslgen.domain.catalog import Catalog
from tslgen.domain.primitives import PrimitiveDeclaration
from tslgen.domain.signatures import Signature, parse_signature
from tslgen.validation.attribute_rules import (
    validate_primitive_attributes,
    validate_template_required_fields,
)
from tslgen.validation.signature_rules import TemplateResolution, resolve_template, rule_for_signature


@dataclass(frozen=True, slots=True)
class ValidatedPrimitive:
    declaration: PrimitiveDeclaration
    signature: Signature
    template_name: str


@dataclass(frozen=True, slots=True)
class ValidatedCatalog:
    catalog: Catalog
    primitives: tuple[ValidatedPrimitive, ...]
    primitives_by_id: FrozenMap[str, ValidatedPrimitive] = field(init=False)

    def __post_init__(self) -> None:
        primitives = tuple(
            sorted(self.primitives, key=lambda item: item.declaration.catalog_id)
        )
        object.__setattr__(self, "primitives", primitives)
        object.__setattr__(
            self,
            "primitives_by_id",
            FrozenMap((item.declaration.catalog_id, item) for item in primitives),
        )

    def primitive_declarations(self, name: str) -> tuple[ValidatedPrimitive, ...]:
        return tuple(
            primitive for primitive in self.primitives if primitive.declaration.name == name
        )


def validate_catalog(catalog: Catalog) -> Result[ValidatedCatalog]:
    diagnostics: list[Diagnostic] = []
    validated_primitives: list[ValidatedPrimitive] = []

    for primitive in catalog.primitives:
        validated = _validate_primitive(primitive, catalog)
        diagnostics.extend(validated.diagnostics)
        if validated.value is not None:
            validated_primitives.append(validated.value)

    diagnostics = list(sort_diagnostics(diagnostics))
    if has_errors(diagnostics):
        return Result.failure(diagnostics)

    return Result.ok(
        ValidatedCatalog(
            catalog=catalog,
            primitives=tuple(validated_primitives),
        ),
        diagnostics=diagnostics,
    )


@dataclass(frozen=True, slots=True)
class _PrimitiveValidation:
    value: ValidatedPrimitive | None
    diagnostics: tuple[Diagnostic, ...]


def _validate_primitive(
    primitive: PrimitiveDeclaration,
    catalog: Catalog,
) -> _PrimitiveValidation:
    diagnostics: list[Diagnostic] = []
    signature_result = parse_signature(
        primitive.signature,
        location=primitive.source_span.location,
    )
    diagnostics.extend(signature_result.diagnostics)
    if not signature_result.is_ok:
        return _PrimitiveValidation(None, tuple(diagnostics))

    signature = signature_result.unwrap()
    diagnostics.extend(_validate_parameters(primitive, signature))
    attribute_validation = validate_primitive_attributes(
        primitive,
        signature,
        catalog.templates_by_name,
    )
    diagnostics.extend(attribute_validation.diagnostics)
    if has_errors(diagnostics):
        return _PrimitiveValidation(None, tuple(diagnostics))

    resolution = resolve_template(signature, attribute_validation.values)
    if resolution is None:
        diagnostics.append(_unresolved_template_diagnostic(primitive, signature))
        return _PrimitiveValidation(None, tuple(diagnostics))

    template = catalog.templates_by_name.get(resolution.template_name)
    if template is None:
        diagnostics.append(_unknown_template_diagnostic(primitive, resolution))
        return _PrimitiveValidation(None, tuple(diagnostics))

    diagnostics.extend(
        validate_template_required_fields(
            primitive,
            template,
            attribute_validation.values,
        )
    )
    if has_errors(diagnostics):
        return _PrimitiveValidation(None, tuple(diagnostics))

    return _PrimitiveValidation(
        ValidatedPrimitive(
            declaration=primitive,
            signature=signature,
            template_name=resolution.template_name,
        ),
        tuple(diagnostics),
    )


def _validate_parameters(
    primitive: PrimitiveDeclaration,
    signature: Signature,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    expected_count = _expected_declaration_parameter_count(signature)
    if len(primitive.parameters) != expected_count:
        diagnostics.append(
            Diagnostic.error(
                "TSL-SIG-PARAM-COUNT",
                f"primitive {primitive.name!r} signature {signature.normalized!r} "
                f"expects {expected_count} parameter(s) but declaration has "
                f"{len(primitive.parameters)}",
                location=primitive.source_span.location,
            )
        )

    seen: set[str] = set()
    for parameter in primitive.parameters:
        if parameter.name in seen:
            diagnostics.append(
                Diagnostic.error(
                    "TSL-SIG-PARAM-DUPLICATE",
                    f"primitive {primitive.name!r} has duplicate parameter "
                    f"{parameter.name!r}",
                    location=parameter.source_span.location,
                )
            )
        seen.add(parameter.name)
    return tuple(diagnostics)


def _expected_declaration_parameter_count(signature: Signature) -> int:
    if signature.normalized == "v:=sequence":
        return 0
    return len(signature.parameters)


def _unresolved_template_diagnostic(
    primitive: PrimitiveDeclaration,
    signature: Signature,
) -> Diagnostic:
    if rule_for_signature(signature) is None:
        return Diagnostic.error(
            "TSL-SIG-RULE-MISSING",
            f"primitive {primitive.name!r} has unsupported signature "
            f"{signature.normalized!r}",
            location=primitive.source_span.location,
        )
    attrs = ", ".join(
        f"{attribute.key}={attribute.value!r}" for attribute in primitive.attributes
    )
    return Diagnostic.error(
        "TSL-SIG-TEMPLATE-UNRESOLVED",
        f"primitive {primitive.name!r} signature {signature.normalized!r} "
        f"does not match a template rule for attributes [{attrs}]",
        location=primitive.source_span.location,
    )


def _unknown_template_diagnostic(
    primitive: PrimitiveDeclaration,
    resolution: TemplateResolution,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-SIG-TEMPLATE-UNKNOWN",
        f"primitive {primitive.name!r} resolved to unknown template "
        f"{resolution.template_name!r}",
        location=primitive.source_span.location,
    )
