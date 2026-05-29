from pathlib import Path

from tslgen.analysis.selection import (
    SelectedImplementation,
    Target,
    TargetReturnTypeBaseBinding,
    TargetReturnTypeExtensionBinding,
    TargetSpecializationBinding,
    TargetVectorTypeBinding,
)
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import (
    Catalog,
    Extension,
    ExtensionBackendMetadata,
    ExtensionCatalog,
    ExtensionName,
    ExtensionSizeParameter,
    Implementation,
    ImplementationBody,
    LowerableDirective,
    Primitive,
    ReturnTypeBindingDeclaration,
    TypeTag,
)
from tslgen.lowering import (
    CurrentVector,
    LoweredCurrentScalarType,
    LoweredGenerationValue,
    LoweredGenericRegisterType,
    LoweredScalarTypeIdentity,
    LoweredTypeAliasBinding,
    LoweredTypeValue,
    LoweredVectorAsExtensionType,
    LoweredVectorTransformType,
    Lowerer,
)

_SOURCE = Path("m169.tsl")


def test_m169_lowers_declared_base_binding_with_arbitrary_name() -> None:
    selected = _selected_implementation(
        return_type_binding=ReturnTypeBindingDeclaration(
            kind="base",
            name="ResultBase",
            source=_location(2, 5),
        ),
        specialization_bindings=(
            TargetReturnTypeBaseBinding(
                name="ResultBase",
                type_tag=TypeTag("f64"),
            ),
        ),
    )

    result = Lowerer().lower_generation_type_query(
        selected,
        "type<generation>(ResultBase)",
        _location(5, 7),
    )

    assert result.diagnostics == ()
    assert result.value == LoweredScalarTypeIdentity(type_tag=TypeTag("f64"))


def test_m169_lowers_declared_extension_binding_with_arbitrary_name() -> None:
    selected = _selected_implementation(
        return_type_binding=ReturnTypeBindingDeclaration(
            kind="extension",
            name="TargetExtension",
            source=_location(2, 5),
        ),
        specialization_bindings=(
            TargetReturnTypeExtensionBinding(
                name="TargetExtension",
                extension=ExtensionName("avx2"),
            ),
        ),
    )

    result = Lowerer().lower_generation_type_query(
        selected,
        "type<generation>(vector::as_extension(TargetExtension))",
        _location(5, 7),
    )

    assert result.diagnostics == ()
    assert result.value == LoweredVectorAsExtensionType(
        base_type=LoweredCurrentScalarType(type_tag=TypeTag("si32")),
        extension=ExtensionName("avx2"),
    )


def test_m169_bound_base_alias_feeds_generic_length_without_hardwired_name() -> None:
    selected = _selected_implementation(
        body=_body_with_type_alias(
            "OutVec, type<generation>(vector::transform_extension(ResultBase))"
        ),
        extension="avx2",
        type_tag="si32",
        return_type_binding=ReturnTypeBindingDeclaration(
            kind="base",
            name="ResultBase",
            source=_location(2, 5),
        ),
        specialization_bindings=(
            TargetReturnTypeBaseBinding(
                name="ResultBase",
                type_tag=TypeTag("f64"),
            ),
        ),
    )
    lowerer = Lowerer()
    environment = lowerer.type_environment_for(selected)
    catalog = _catalog(_extension_fact("avx2", vector_bits=256))

    result = lowerer.lower_generation_expression(
        selected,
        "generic::length(OutVec)",
        _location(6, 7),
        catalog=catalog,
        environment=environment,
    )

    assert environment.diagnostics == ()
    assert environment.alias_bindings == (
        _alias_binding(
            alias_name="OutVec",
            value=LoweredVectorTransformType(
                transform="transform_extension",
                base_type=LoweredScalarTypeIdentity(type_tag=TypeTag("f64")),
                extension=ExtensionName("avx2"),
            ),
            source_text="type<generation>(vector::transform_extension(ResultBase))",
        ),
    )
    assert result.diagnostics == ()
    assert result.value == LoweredGenerationValue(
        kind="generic.length",
        value=4,
        source_text="generic::length(OutVec)",
        source=_location(6, 7),
    )


def test_m169_bound_extension_alias_feeds_generic_length_without_hardwired_name() -> None:
    selected = _selected_implementation(
        body=_body_with_type_alias(
            "OutVec, type<generation>(vector::as_extension(TargetExtension))"
        ),
        extension="sse",
        type_tag="si32",
        return_type_binding=ReturnTypeBindingDeclaration(
            kind="extension",
            name="TargetExtension",
            source=_location(2, 5),
        ),
        specialization_bindings=(
            TargetReturnTypeExtensionBinding(
                name="TargetExtension",
                extension=ExtensionName("avx2"),
            ),
        ),
    )
    lowerer = Lowerer()
    environment = lowerer.type_environment_for(selected)
    catalog = _catalog(_extension_fact("avx2", vector_bits=256))

    result = lowerer.lower_generation_expression(
        selected,
        "generic::length(OutVec)",
        _location(6, 7),
        catalog=catalog,
        environment=environment,
    )

    assert environment.diagnostics == ()
    assert result.diagnostics == ()
    assert result.value == LoweredGenerationValue(
        kind="generic.length",
        value=8,
        source_text="generic::length(OutVec)",
        source=_location(6, 7),
    )


def test_m169_unbound_symbol_keeps_existing_unresolved_specialization_boundary() -> None:
    selected = _selected_implementation(
        body=_body_with_type_alias(
            "OutVec, type<generation>(vector::transform_extension(ToBase))"
        ),
        extension="avx2",
        type_tag="si32",
    )
    lowerer = Lowerer()
    environment = lowerer.type_environment_for(selected)

    result = lowerer.lower_generation_expression(
        selected,
        "generic::length(OutVec)",
        _location(6, 7),
        catalog=_catalog(_extension_fact("avx2", vector_bits=256)),
        environment=environment,
    )

    assert environment.diagnostics == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-LOWER-UNRESOLVED-GENERIC-VECTOR-TYPE",
    ]
    assert result.value is None


def test_m169_unbound_declared_extension_symbol_is_not_treated_as_raw_extension() -> None:
    selected = _selected_implementation(
        body=_body_with_type_alias(
            "OutVec, type<generation>(vector::as_extension(TargetExtension))"
        ),
        return_type_binding=ReturnTypeBindingDeclaration(
            kind="extension",
            name="TargetExtension",
            source=_location(2, 5),
        ),
    )

    environment = Lowerer().type_environment_for(selected)

    _assert_single_diagnostic(
        environment.diagnostics,
        "TSL-LOWER-UNBOUND-SELECTED-SPECIALIZATION-BINDING",
        _location(4, 7),
    )
    assert environment.alias_bindings == ()


def test_m169_rejects_binding_that_does_not_match_return_type_declaration() -> None:
    selected = _selected_implementation(
        return_type_binding=ReturnTypeBindingDeclaration(
            kind="base",
            name="ResultBase",
            source=_location(2, 5),
        ),
        specialization_bindings=(
            TargetReturnTypeExtensionBinding(
                name="ResultBase",
                extension=ExtensionName("avx2"),
            ),
        ),
    )

    environment = Lowerer().type_environment_for(selected)
    result_location = _location(5, 7)
    result = Lowerer().lower_generation_type_query(
        selected,
        "type<generation>(ResultBase)",
        result_location,
    )

    _assert_single_diagnostic(
        environment.diagnostics,
        "TSL-LOWER-SELECTED-SPECIALIZATION-BINDING-MISMATCH",
        _location(1, 1),
    )
    _assert_single_diagnostic(
        result.diagnostics,
        "TSL-LOWER-SELECTED-SPECIALIZATION-BINDING-MISMATCH",
        result_location,
    )
    assert result.value is None


def test_m169_rejects_extension_binding_used_as_type_expression() -> None:
    selected = _selected_implementation(
        return_type_binding=ReturnTypeBindingDeclaration(
            kind="extension",
            name="TargetExtension",
            source=_location(2, 5),
        ),
        specialization_bindings=(
            TargetReturnTypeExtensionBinding(
                name="TargetExtension",
                extension=ExtensionName("avx2"),
            ),
        ),
    )

    result = Lowerer().lower_generation_type_query(
        selected,
        "type<generation>(TargetExtension)",
        _location(5, 7),
    )

    _assert_single_diagnostic(
        result.diagnostics,
        "TSL-LOWER-SELECTED-SPECIALIZATION-BINDING-KIND-MISMATCH",
        _location(5, 7),
    )
    assert result.value is None


def test_m169_rejects_duplicate_selected_specialization_bindings() -> None:
    selected = _selected_implementation(
        return_type_binding=ReturnTypeBindingDeclaration(
            kind="base",
            name="ResultBase",
            source=_location(2, 5),
        ),
        specialization_bindings=(
            TargetReturnTypeBaseBinding(
                name="ResultBase",
                type_tag=TypeTag("f32"),
            ),
            TargetReturnTypeBaseBinding(
                name="ResultBase",
                type_tag=TypeTag("f64"),
            ),
        ),
    )

    environment = Lowerer().type_environment_for(selected)
    result_location = _location(5, 7)
    result = Lowerer().lower_generation_type_query(
        selected,
        "type<generation>(ResultBase)",
        result_location,
    )

    _assert_single_diagnostic(
        environment.diagnostics,
        "TSL-LOWER-DUPLICATE-SELECTED-SPECIALIZATION-BINDING",
        _location(1, 1),
    )
    _assert_single_diagnostic(
        result.diagnostics,
        "TSL-LOWER-DUPLICATE-SELECTED-SPECIALIZATION-BINDING",
        _location(1, 1),
    )
    assert result.value is None


def test_m169_rejects_malformed_selected_specialization_binding_name() -> None:
    selected = _selected_implementation(
        specialization_bindings=(
            TargetVectorTypeBinding(
                name="Bad Name",
                extension=ExtensionName("avx2"),
                type_tag=TypeTag("f64"),
            ),
        ),
    )

    environment = Lowerer().type_environment_for(selected)

    _assert_single_diagnostic(
        environment.diagnostics,
        "TSL-LOWER-MALFORMED-SELECTED-SPECIALIZATION-BINDING",
        _location(1, 1),
    )


def test_m169_rejects_return_type_binding_without_declaration() -> None:
    selected = _selected_implementation(
        specialization_bindings=(
            TargetReturnTypeBaseBinding(
                name="ResultBase",
                type_tag=TypeTag("f64"),
            ),
        ),
    )

    environment = Lowerer().type_environment_for(selected)
    result_location = _location(5, 7)
    result = Lowerer().lower_generation_type_query(
        selected,
        "type<generation>(ResultBase)",
        result_location,
    )

    _assert_single_diagnostic(
        environment.diagnostics,
        "TSL-LOWER-UNDECLARED-SELECTED-SPECIALIZATION-BINDING",
        _location(1, 1),
    )
    _assert_single_diagnostic(
        result.diagnostics,
        "TSL-LOWER-UNDECLARED-SELECTED-SPECIALIZATION-BINDING",
        result_location,
    )
    assert result.value is None


def test_m169_resolves_explicit_vector_type_binding_for_totype_style_queries() -> None:
    selected = _selected_implementation(
        specialization_bindings=(
            TargetVectorTypeBinding(
                name="ToType",
                extension=ExtensionName("avx2"),
                type_tag=TypeTag("f64"),
            ),
        ),
    )

    result = Lowerer().lower_generation_type_query(
        selected,
        "type<generation>(register::generic(ToType))",
        _location(5, 7),
    )

    assert result.diagnostics == ()
    assert result.value == LoweredGenericRegisterType(
        vector_type=CurrentVector(
            extension=ExtensionName("avx2"),
            type_tag=TypeTag("f64"),
        )
    )


def test_m169_binding_sort_key_and_lowering_results_are_deterministic() -> None:
    base_binding = TargetReturnTypeBaseBinding(
        name="ResultBase",
        type_tag=TypeTag("f64"),
    )
    vector_binding = TargetVectorTypeBinding(
        name="ToType",
        extension=ExtensionName("avx2"),
        type_tag=TypeTag("f64"),
    )
    first = _target(specialization_bindings=(base_binding, vector_binding))
    second = _target(specialization_bindings=(vector_binding, base_binding))

    assert first.sort_key() == second.sort_key()

    selected = _selected_implementation(
        return_type_binding=ReturnTypeBindingDeclaration(
            kind="base",
            name="ResultBase",
            source=_location(2, 5),
        ),
        specialization_bindings=(base_binding,),
    )
    lowerer = Lowerer()

    first_result = lowerer.lower_generation_type_query(
        selected,
        "type<generation>(ResultBase)",
        _location(5, 7),
    )
    second_result = lowerer.lower_generation_type_query(
        selected,
        "type<generation>(ResultBase)",
        _location(5, 7),
    )

    assert first_result == second_result


def _assert_single_diagnostic(
    diagnostics: tuple[Diagnostic, ...],
    code: str,
    location: SourceLocation,
) -> None:
    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.code == code
    assert diagnostic.severity == "error"
    assert diagnostic.location == location


def _alias_binding(
    *,
    alias_name: str,
    value: LoweredTypeValue,
    source_text: str,
) -> LoweredTypeAliasBinding:
    return LoweredTypeAliasBinding(
        alias_name=alias_name,
        value=value,
        source_text=source_text,
        source=_location(4, 7),
    )


def _body_with_type_alias(payload: str) -> ImplementationBody:
    return ImplementationBody(
        tokens=(
            LowerableDirective(
                name="let",
                arguments=("type", payload),
                source=_location(4, 7),
            ),
        ),
        source=_location(3, 5),
    )


def _selected_implementation(
    *,
    body: ImplementationBody | None = None,
    backend: str = "cpp",
    operation_id: str = "add",
    extension: str = "scalar",
    type_tag: str = "si32",
    return_type_binding: ReturnTypeBindingDeclaration | None = None,
    specialization_bindings: tuple[TargetSpecializationBinding, ...] = (),
) -> SelectedImplementation:
    selected_body = body or ImplementationBody(tokens=(), source=_location(3, 5))
    implementation = Implementation(
        extension=extension,
        type_tag=type_tag,
        body=selected_body,
        source=_location(2, 3),
    )
    primitive = Primitive(
        name=operation_id,
        signature="v:=(v,v)",
        parameters=("left", "right"),
        template="binary",
        implementations=(implementation,),
        source=_location(1, 1),
        return_type_binding=return_type_binding,
    )
    target = _target(
        backend=backend,
        operation_id=operation_id,
        extension=extension,
        type_tag=type_tag,
        specialization_bindings=specialization_bindings,
    )
    return SelectedImplementation(
        target=target,
        primitive=primitive,
        implementation=implementation,
    )


def _target(
    *,
    backend: str = "cpp",
    operation_id: str = "add",
    extension: str = "scalar",
    type_tag: str = "si32",
    specialization_bindings: tuple[TargetSpecializationBinding, ...] = (),
) -> Target:
    return Target(
        backend=backend,
        primitive_name=operation_id,
        extension=extension,
        type_tag=type_tag,
        attributes=(),
        specialization_bindings=specialization_bindings,
    )


def _catalog(*extensions: Extension) -> Catalog:
    return Catalog(
        primitives=(),
        extensions=ExtensionCatalog(extensions),
    )


def _extension_fact(
    name: str,
    *,
    vector_bits: int | str | None,
    runtime_lanes: bool | None = None,
    size_parameter: bool = False,
) -> Extension:
    metadata = ExtensionBackendMetadata(
        supported=True,
        type_name=None,
        generation_support=(),
        headers=(),
        header_guard=None,
        test_suite_name=None,
        test_support_header=None,
        source=_location(1, 1),
    )
    return Extension(
        name=name,
        extension_name=name,
        vendor=None,
        inherits=None,
        family=None,
        intrinsic_style=None,
        vector_bits=vector_bits,
        native_sort_order=None,
        autodetect=None,
        lscpu_flags=(),
        mask_repr=None,
        mask_width=None,
        mask_vector_loadable=None,
        runtime_lanes=runtime_lanes,
        default_test_target=None,
        cpp=metadata,
        rust=metadata,
        signature_support_exclude=(),
        test_filter_exclude_templates=(),
        test_sizes_bits=(),
        vector_register_types=(),
        resolved_vector_register_types=(),
        vector_register_type_policy=None,
        size_parameter=ExtensionSizeParameter(
            kind="generic",
            name="N",
            source=_location(1, 1),
        )
        if size_parameter
        else None,
        mask_type_policy=None,
        integral_mask_type_policy=None,
        source=_location(1, 1),
    )


def _location(line: int, column: int) -> SourceLocation:
    return SourceLocation(path=_SOURCE, line=line, column=column)
