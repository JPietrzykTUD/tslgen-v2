"""Parser-to-domain catalog promotion for the tiny clean source form."""

from dataclasses import dataclass

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import (
    BodyToken,
    Catalog,
    ImplementationBody,
    Implementation,
    LowerableDirective,
    LowerableOperationFragment,
    Primitive,
    PrimitiveAttribute,
    RawStringToken,
)
from tslgen.pipeline.extension_catalog import build_extension_catalog, build_type_groups
from tslgen.pipeline._tsil_directives import classify_tsil_directive_line
from tslgen.pipeline._tsil_primitive_calls import (
    classify_tsil_primitive_call_tokens,
)
from tslgen.syntax.ast import (
    PARSED_TSIL_BODY_ENVELOPE,
    ParsedBodySegment,
    ParsedDocument,
    ParsedImplementation,
    ParsedImplementationBody,
    ParsedLowerableDirective,
    ParsedLowerableOperationFragment,
    ParsedPrimitive,
    ParsedPrimitiveAttribute,
    ParsedRawStringLine,
    ParsedRawStringToken,
    ParsedSegmentedLine,
    ParsedTypeGroup,
)

M107_SIGNATURE = "v:=(v,v)"
M107_PARAMETERS = ("left", "right")
M107_TEMPLATE = "binary"
M121_SIGNATURE = "m:=(v,v)"
M121_PARAMETERS = ("left", "right")
M121_TEMPLATE = "compare"
M118_SIGNATURE = "v:=(v)"
M118_PARAMETERS = ("value",)
M118_TEMPLATE = "unary"
SUPPORTED_EXTENSION = "scalar"
_EMIT_RETURN_DIRECTIVE = "emit_return"
_EMIT_RETURN_PREFIX = f"{_EMIT_RETURN_DIRECTIVE}("
_BOOLEAN_WILDCARD_ATTRIBUTE_VALUES = ("true", "false")
_SUPPORTED_BOOLEAN_WILDCARD_ATTRIBUTES = frozenset(("aligned", "packed"))


@dataclass(frozen=True, slots=True)
class _SourceShape:
    signature: str
    parameters: tuple[str, ...]
    template: str


_SUPPORTED_SOURCE_SHAPES: tuple[_SourceShape, ...] = (
    _SourceShape(
        signature=M107_SIGNATURE,
        parameters=M107_PARAMETERS,
        template=M107_TEMPLATE,
    ),
    _SourceShape(
        signature=M121_SIGNATURE,
        parameters=M121_PARAMETERS,
        template=M121_TEMPLATE,
    ),
    _SourceShape(
        signature=M118_SIGNATURE,
        parameters=M118_PARAMETERS,
        template=M118_TEMPLATE,
    ),
)


@dataclass(frozen=True, slots=True)
class CatalogBuildResult:
    catalog: Catalog | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class _ConcretePrimitiveVariant:
    parsed: ParsedPrimitive
    attributes: tuple[PrimitiveAttribute, ...]
    declared_attributes: tuple[PrimitiveAttribute, ...]


class CatalogBuilder:
    """Promote parsed tiny clean syntax into validated domain values."""

    def build(self, documents: tuple[ParsedDocument, ...]) -> CatalogBuildResult:
        diagnostics: list[Diagnostic] = []
        parsed_primitives: list[ParsedPrimitive] = []
        parsed_extensions: list[ParsedExtension] = []
        parsed_type_groups: list[ParsedTypeGroup] = []

        for document in sorted(documents, key=lambda item: item.path):
            parsed_extensions.extend(document.extensions)
            parsed_type_groups.extend(document.type_groups)
            if not document.primitives:
                continue
            if len(document.primitives) != 1:
                location = (
                    document.primitives[0].source
                    if document.primitives
                    else None
                )
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code="TSL-CATALOG-UNSUPPORTED-PRIMITIVE-COUNT",
                        message=(
                            f"source document {document.path!r} contains "
                            f"{len(document.primitives)} primitives; expected "
                            "exactly 1"
                        ),
                        location=location,
                    )
                )
                continue
            parsed_primitives.append(document.primitives[0])

        if not parsed_primitives and not parsed_extensions and not parsed_type_groups:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-CATALOG-UNSUPPORTED-PRIMITIVE-COUNT",
                    message="source set contains no parsed catalog declarations",
                )
            )
            return CatalogBuildResult(catalog=None, diagnostics=tuple(diagnostics))

        type_groups = build_type_groups(tuple(parsed_type_groups), diagnostics)
        extension_catalog = build_extension_catalog(
            tuple(parsed_extensions),
            type_groups,
            diagnostics,
        )

        concrete_variants = tuple(
            variant
            for parsed in parsed_primitives
            for variant in _concrete_primitive_variants(parsed, diagnostics)
        )

        diagnostics.extend(_duplicate_primitive_name_diagnostics(concrete_variants))

        primitives = tuple(
            self._build_primitive(variant, diagnostics)
            for variant in concrete_variants
        )
        if diagnostics:
            return CatalogBuildResult(catalog=None, diagnostics=tuple(diagnostics))
        return CatalogBuildResult(
            catalog=Catalog(
                primitives=primitives,
                type_groups=type_groups,
                extensions=extension_catalog,
            ),
            diagnostics=(),
        )

    def _build_primitive(
        self,
        variant: _ConcretePrimitiveVariant,
        diagnostics: list[Diagnostic],
    ) -> Primitive:
        parsed = variant.parsed
        signature_shape = _shape_for_signature(parsed.signature)
        if signature_shape is None:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-CATALOG-UNSUPPORTED-SIGNATURE",
                    message=(
                        f"primitive {parsed.name!r} uses signature "
                        f"{parsed.signature!r}; expected one of: "
                        f"{_supported_signatures_text()}"
                    ),
                    location=parsed.source,
                )
            )

        shape = signature_shape or _SUPPORTED_SOURCE_SHAPES[0]
        if parsed.parameters != shape.parameters:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-CATALOG-UNSUPPORTED-PARAMETERS",
                    message=(
                        f"primitive {parsed.name!r} uses parameters "
                        f"{parsed.parameters!r}; expected exactly "
                        f"{shape.parameters!r}"
                    ),
                    location=parsed.source,
                )
            )

        if not parsed.implementations:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-CATALOG-IMPLEMENTATION-COUNT",
                    message=(
                        f"primitive {parsed.name!r} has "
                        f"{len(parsed.implementations)} implementations; "
                        "expected at least 1"
                    ),
                    location=parsed.source,
                )
            )
        diagnostics.extend(_duplicate_implementation_key_diagnostics(parsed))

        implementations = tuple(
            self._build_implementation(parsed, implementation, shape, diagnostics)
            for implementation in parsed.implementations
        )
        return Primitive(
            name=parsed.name,
            signature=parsed.signature,
            parameters=parsed.parameters,
            template=shape.template,
            implementations=implementations,
            source=parsed.source,
            attributes=variant.attributes,
            declared_attributes=variant.declared_attributes,
        )

    def _build_implementation(
        self,
        primitive: ParsedPrimitive,
        parsed: ParsedImplementation,
        shape: _SourceShape,
        diagnostics: list[Diagnostic],
    ) -> Implementation:
        if parsed.extension != SUPPORTED_EXTENSION:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-CATALOG-UNSUPPORTED-EXTENSION",
                    message=(
                        f"implementation extension {parsed.extension!r} is "
                        f"unsupported; expected {SUPPORTED_EXTENSION!r}"
                    ),
                    location=parsed.source,
                )
            )

        body_fragment = _single_operation_fragment(parsed.body)
        expected_body = _expected_body_text(body_fragment, shape.parameters)
        if body_fragment is None:
            if not _is_parsed_tsil_raw_body(parsed.body):
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code="TSL-CATALOG-UNSUPPORTED-BODY",
                        message=(
                            "implementation body is unsupported; expected exactly "
                            "one lowerable operation token"
                        ),
                        location=parsed.body.source,
                    )
                )
        elif body_fragment.arguments != shape.parameters:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-CATALOG-UNSUPPORTED-BODY",
                    message=(
                        f"implementation body {_body_text(body_fragment)!r} "
                        "is unsupported; "
                        f"expected exactly {expected_body!r}"
                    ),
                    location=body_fragment.source,
                )
            )

        return Implementation(
            extension=parsed.extension,
            type_tag=parsed.type_tag,
            body=_build_body(parsed, shape),
            source=parsed.source,
        )


def _body_text(fragment: ParsedLowerableOperationFragment) -> str:
    return f"{fragment.operation}({', '.join(fragment.arguments)})"


def _expected_body_text(
    fragment: ParsedLowerableOperationFragment | None,
    parameters: tuple[str, ...],
) -> str:
    operation = fragment.operation if fragment is not None else "<operation>"
    return f"{operation}({', '.join(parameters)})"


def _duplicate_primitive_name_diagnostics(
    variants: tuple[_ConcretePrimitiveVariant, ...],
) -> tuple[Diagnostic, ...]:
    first_by_key: dict[tuple[str, str, tuple[tuple[str, str | None, str], ...]], ParsedPrimitive] = {}
    diagnostics: list[Diagnostic] = []
    for variant in sorted(
        variants,
        key=lambda item: (
            item.parsed.name,
            item.parsed.signature,
            _attribute_key(item.attributes),
            item.parsed.source.path.as_posix(),
        ),
    ):
        primitive = variant.parsed
        key = (primitive.name, primitive.signature, _attribute_key(variant.attributes))
        first = first_by_key.get(key)
        if first is None:
            first_by_key[key] = primitive
            continue
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-CATALOG-DUPLICATE-PRIMITIVE-NAME",
                message=(
                    f"primitive name {primitive.name!r} is declared more than "
                    "once in the explicit source set; first declaration is at "
                    f"{first.source.path}:{first.source.line}:{first.source.column}"
                ),
                location=primitive.source,
            )
        )
    return tuple(diagnostics)


def _concrete_primitive_variants(
    parsed: ParsedPrimitive,
    diagnostics: list[Diagnostic],
) -> tuple[_ConcretePrimitiveVariant, ...]:
    declared_attributes = tuple(
        _domain_attribute(
            attribute,
            attribute.value,
            declared_value=attribute.value,
        )
        for attribute in parsed.attributes
    )
    if not parsed.attributes:
        return (
            _ConcretePrimitiveVariant(
                parsed=parsed,
                attributes=(),
                declared_attributes=(),
            ),
        )

    variants: tuple[tuple[PrimitiveAttribute, ...], ...] = ((),)
    for attribute in parsed.attributes:
        concrete_values = _concrete_attribute_values(attribute, diagnostics)
        variants = tuple(
            (*variant, _domain_attribute(attribute, concrete_value))
            for variant in variants
            for concrete_value in concrete_values
        )

    return tuple(
        _ConcretePrimitiveVariant(
            parsed=parsed,
            attributes=variant,
            declared_attributes=declared_attributes,
        )
        for variant in variants
    )


def _concrete_attribute_values(
    attribute: ParsedPrimitiveAttribute,
    diagnostics: list[Diagnostic],
) -> tuple[str, ...]:
    if attribute.value != "*":
        return (attribute.value,)

    if attribute.key in _SUPPORTED_BOOLEAN_WILDCARD_ATTRIBUTES:
        return _BOOLEAN_WILDCARD_ATTRIBUTE_VALUES

    diagnostics.append(
        Diagnostic(
            severity="error",
            code="TSL-CATALOG-UNSUPPORTED-WILDCARD-ATTRIBUTE",
            message=(
                f"attribute {attribute.key!r} uses wildcard value '*'; "
                "supported wildcard attributes are: aligned, packed"
            ),
            location=attribute.source,
        )
    )
    return ()


def _domain_attribute(
    attribute: ParsedPrimitiveAttribute,
    value: str,
    *,
    declared_value: str | None = None,
) -> PrimitiveAttribute:
    return PrimitiveAttribute(
        key=attribute.key,
        key_argument=attribute.key_argument,
        value=value,
        source=attribute.source,
        declared_value=declared_value or attribute.value,
    )


def _attribute_key(
    attributes: tuple[PrimitiveAttribute, ...],
) -> tuple[tuple[str, str | None, str], ...]:
    return tuple(
        (attribute.key, attribute.key_argument, attribute.value)
        for attribute in attributes
    )


def _duplicate_implementation_key_diagnostics(
    primitive: ParsedPrimitive,
) -> tuple[Diagnostic, ...]:
    first_by_key: dict[tuple[str, str], ParsedImplementation] = {}
    diagnostics: list[Diagnostic] = []
    for implementation in primitive.implementations:
        key = (implementation.extension, implementation.type_tag)
        first = first_by_key.get(key)
        if first is None:
            first_by_key[key] = implementation
            continue
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-CATALOG-DUPLICATE-IMPLEMENTATION-KEY",
                message=(
                    f"primitive {primitive.name!r} declares implementation "
                    f"extension {implementation.extension!r} and type "
                    f"{implementation.type_tag!r} more than once; first "
                    "declaration is at "
                    f"{first.source.path}:{first.source.line}:{first.source.column}"
                ),
                location=implementation.source,
            )
        )
    return tuple(diagnostics)


def _build_body(
    parsed: ParsedImplementation,
    shape: _SourceShape,
) -> ImplementationBody:
    del shape
    return _build_implementation_body(parsed.body)


def _single_operation_fragment(
    body: ParsedImplementationBody,
) -> ParsedLowerableOperationFragment | None:
    if len(body.lines) != 1:
        return None
    line = body.lines[0]
    if not isinstance(line, ParsedSegmentedLine):
        return None
    if len(line.segments) != 1:
        return None
    segment = line.segments[0]
    if not isinstance(segment, ParsedLowerableOperationFragment):
        return None
    return segment


def _is_parsed_tsil_raw_body(body: ParsedImplementationBody) -> bool:
    return (
        body.envelope == PARSED_TSIL_BODY_ENVELOPE
        and all(isinstance(line, ParsedRawStringLine) for line in body.lines)
    )


def _build_implementation_body(body: ParsedImplementationBody) -> ImplementationBody:
    tokens = tuple(
        token
        for line in body.lines
        for token in _build_body_tokens(
            line,
            classify_tsil_directives=(
                body.envelope == PARSED_TSIL_BODY_ENVELOPE
            ),
        )
    )
    if body.envelope == PARSED_TSIL_BODY_ENVELOPE:
        tokens = classify_tsil_primitive_call_tokens(tokens)
        tokens = _classify_emit_return_payload_tokens(tokens)

    return ImplementationBody(
        tokens=tokens,
        source=body.source,
    )


def _classify_emit_return_payload_tokens(
    tokens: tuple[BodyToken, ...],
) -> tuple[BodyToken, ...]:
    return tuple(_classify_emit_return_payload_token(token) for token in tokens)


def _classify_emit_return_payload_token(token: BodyToken) -> BodyToken:
    if not isinstance(token, LowerableDirective):
        return token
    if token.name != _EMIT_RETURN_DIRECTIVE:
        return token
    if len(token.arguments) != 1:
        return token

    payload = token.arguments[0]
    payload_source = SourceLocation(
        token.source.path,
        token.source.line,
        token.source.column + len(_EMIT_RETURN_PREFIX),
    )
    payload_tokens = classify_tsil_primitive_call_tokens(
        (RawStringToken(text=payload, source=payload_source),)
    )
    return LowerableDirective(
        name=token.name,
        arguments=token.arguments,
        source=token.source,
        payload_tokens=payload_tokens,
    )


def _build_body_tokens(
    line: ParsedRawStringLine | ParsedSegmentedLine,
    *,
    classify_tsil_directives: bool = False,
) -> tuple[BodyToken, ...]:
    if isinstance(line, ParsedRawStringLine):
        if classify_tsil_directives:
            directive_tokens = classify_tsil_directive_line(line)
            if directive_tokens is not None:
                return directive_tokens
        return (RawStringToken(text=line.text, source=line.source),)
    return tuple(_build_body_segment(segment) for segment in line.segments)


def _build_body_segment(segment: ParsedBodySegment) -> BodyToken:
    if isinstance(segment, ParsedLowerableOperationFragment):
        return LowerableOperationFragment(
            operation=segment.operation,
            arguments=segment.arguments,
            source=segment.source,
        )
    if isinstance(segment, ParsedLowerableDirective):
        return LowerableDirective(
            name=segment.name,
            arguments=segment.arguments,
            source=segment.source,
        )
    if isinstance(segment, ParsedRawStringToken):
        return RawStringToken(text=segment.text, source=segment.source)
    raise TypeError(f"unsupported parsed body segment {segment!r}")


def _shape_for_signature(signature: str) -> _SourceShape | None:
    for shape in _SUPPORTED_SOURCE_SHAPES:
        if shape.signature == signature:
            return shape
    return None


def _supported_signatures_text() -> str:
    return ", ".join(shape.signature for shape in _SUPPORTED_SOURCE_SHAPES)
