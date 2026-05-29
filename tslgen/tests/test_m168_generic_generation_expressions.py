from pathlib import Path

from tslgen.analysis.selection import SelectedImplementation, Target
from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.catalog import (
    Catalog,
    Extension,
    ExtensionBackendMetadata,
    ExtensionCatalog,
    ExtensionSizeParameter,
    Implementation,
    ImplementationBody,
    LowerableDirective,
    Primitive,
)
from tslgen.lowering import LoweredGenerationValue, Lowerer


_SOURCE = Path("m168.tsl")


def test_m168_lowers_direct_generic_length_for_current_vector() -> None:
    selected = _selected_implementation(extension="avx2", type_tag="si32")
    catalog = _catalog(_extension_fact("avx2", vector_bits=256))

    result = Lowerer().lower_generation_expression(
        selected,
        "generic::length(Vec)",
        _location(4, 7),
        catalog=catalog,
    )

    assert result.diagnostics == ()
    assert result.value == LoweredGenerationValue(
        kind="generic.length",
        value=8,
        source_text="generic::length(Vec)",
        source=_location(4, 7),
    )


def test_m168_lowers_generic_length_through_type_alias() -> None:
    body = ImplementationBody(
        tokens=(
            LowerableDirective(
                name="let",
                arguments=(
                    "type",
                    (
                        "OutVec, type<generation>("
                        "vector::transform_extension(scalar::f64))"
                    ),
                ),
                source=_location(4, 7),
            ),
        ),
        source=_location(3, 5),
    )
    selected = _selected_implementation(
        body=body,
        extension="avx2",
        type_tag="si32",
    )
    lowerer = Lowerer()
    environment = lowerer.type_environment_for(selected)
    catalog = _catalog(_extension_fact("avx2", vector_bits=256))

    result = lowerer.lower_generation_expression(
        selected,
        "generic::length(OutVec)",
        _location(5, 7),
        catalog=catalog,
        environment=environment,
    )

    assert environment.diagnostics == ()
    assert result.diagnostics == ()
    assert result.value == LoweredGenerationValue(
        kind="generic.length",
        value=4,
        source_text="generic::length(OutVec)",
        source=_location(5, 7),
    )


def test_m168_materializes_generic_length_and_runtime_length_from_value_query() -> None:
    selected = _selected_implementation(extension="avx2", type_tag="si32")
    catalog = _catalog(_extension_fact("avx2", vector_bits=256))
    lowerer = Lowerer()

    length = lowerer.lower_generation_value_query(
        selected,
        "value<generation>(generic::length(Vec))",
        _location(4, 7),
        catalog=catalog,
    )
    runtime_length = lowerer.lower_generation_value_query(
        selected,
        "value<generation>(generic::runtime_length(Vec))",
        _location(5, 7),
        catalog=catalog,
    )

    assert length.diagnostics == ()
    assert length.value == LoweredGenerationValue(
        kind="generic.length",
        value=8,
        source_text="value<generation>(generic::length(Vec))",
        source=_location(4, 7),
    )
    assert runtime_length.diagnostics == ()
    assert runtime_length.value == LoweredGenerationValue(
        kind="generic.runtime_length",
        value=8,
        source_text="value<generation>(generic::runtime_length(Vec))",
        source=_location(5, 7),
    )


def test_m168_generic_length_participates_in_recursive_generation_values() -> None:
    selected = _selected_implementation(extension="avx2", type_tag="si32")
    catalog = _catalog(_extension_fact("avx2", vector_bits=256))
    query = "value<generation>(arith<generation>::mul(generic::length(Vec), 2))"

    result = Lowerer().lower_generation_value_query(
        selected,
        query,
        _location(4, 7),
        catalog=catalog,
    )

    assert result.diagnostics == ()
    assert result.value == LoweredGenerationValue(
        kind="generation.arithmetic.mul",
        value=16,
        source_text=query,
        source=_location(4, 7),
    )


def test_m168_reports_unknown_and_malformed_generic_operations() -> None:
    selected = _selected_implementation(extension="avx2", type_tag="si32")
    catalog = _catalog(_extension_fact("avx2", vector_bits=256))
    lowerer = Lowerer()

    unknown = lowerer.lower_generation_expression(
        selected,
        "generic::lanes(Vec)",
        _location(4, 7),
        catalog=catalog,
    )
    malformed = lowerer.lower_generation_expression(
        selected,
        "generic::length(Vec, scalar::ui32)",
        _location(5, 7),
        catalog=catalog,
    )

    assert [diagnostic.code for diagnostic in unknown.diagnostics] == [
        "TSL-LOWER-UNSUPPORTED-GENERIC-GENERATION-EXPRESSION",
    ]
    assert [diagnostic.code for diagnostic in malformed.diagnostics] == [
        "TSL-LOWER-MALFORMED-GENERIC-GENERATION-EXPRESSION",
    ]
    assert unknown.value is None
    assert malformed.value is None


def test_m168_reports_unresolved_alias_and_specialization() -> None:
    alias_body = ImplementationBody(
        tokens=(
            LowerableDirective(
                name="let",
                arguments=(
                    "type",
                    "OutVec, type<generation>(vector::transform_extension(ToBase))",
                ),
                source=_location(4, 7),
            ),
        ),
        source=_location(3, 5),
    )
    lowerer = Lowerer()
    selected = _selected_implementation(
        body=alias_body,
        extension="avx2",
        type_tag="si32",
    )
    environment = lowerer.type_environment_for(selected)
    catalog = _catalog(_extension_fact("avx2", vector_bits=256))

    unbound_alias = lowerer.lower_generation_expression(
        _selected_implementation(extension="avx2", type_tag="si32"),
        "generic::length(OutVec)",
        _location(5, 7),
        catalog=catalog,
    )
    unresolved_specialization = lowerer.lower_generation_expression(
        selected,
        "generic::length(OutVec)",
        _location(5, 7),
        catalog=catalog,
        environment=environment,
    )

    assert environment.diagnostics == ()
    assert [diagnostic.code for diagnostic in unbound_alias.diagnostics] == [
        "TSL-LOWER-UNBOUND-TYPE-ALIAS",
    ]
    assert [
        diagnostic.code for diagnostic in unresolved_specialization.diagnostics
    ] == [
        "TSL-LOWER-UNRESOLVED-GENERIC-VECTOR-TYPE",
    ]


def test_m168_reports_scalar_and_metadata_boundaries() -> None:
    lowerer = Lowerer()
    selected = _selected_implementation(extension="avx2", type_tag="si32")

    scalar_argument = lowerer.lower_generation_expression(
        selected,
        "generic::length(scalar::ui32)",
        _location(4, 7),
        catalog=_catalog(_extension_fact("avx2", vector_bits=256)),
    )
    missing_metadata = lowerer.lower_generation_expression(
        selected,
        "generic::length(Vec)",
        _location(5, 7),
        catalog=_catalog(),
    )
    scalable_metadata = lowerer.lower_generation_expression(
        _selected_implementation(extension="sve", type_tag="si32"),
        "generic::runtime_length(Vec)",
        _location(6, 7),
        catalog=_catalog(
            _extension_fact("sve", vector_bits="scalable", runtime_lanes=True),
        ),
    )
    size_parameter_metadata = lowerer.lower_generation_expression(
        _selected_implementation(extension="generic", type_tag="si32"),
        "generic::length(Vec)",
        _location(7, 7),
        catalog=_catalog(
            _extension_fact("generic", vector_bits=None, size_parameter=True),
        ),
    )

    assert [diagnostic.code for diagnostic in scalar_argument.diagnostics] == [
        "TSL-LOWER-UNSUPPORTED-GENERIC-VECTOR-TYPE",
    ]
    assert [diagnostic.code for diagnostic in missing_metadata.diagnostics] == [
        "TSL-LOWER-MISSING-GENERIC-VECTOR-METADATA",
    ]
    assert [diagnostic.code for diagnostic in scalable_metadata.diagnostics] == [
        "TSL-LOWER-MISSING-GENERIC-VECTOR-METADATA",
    ]
    assert [
        diagnostic.code for diagnostic in size_parameter_metadata.diagnostics
    ] == [
        "TSL-LOWER-MISSING-GENERIC-VECTOR-METADATA",
    ]


def test_m168_generic_generation_lowering_is_deterministic() -> None:
    selected = _selected_implementation(extension="avx2", type_tag="si32")
    catalog = _catalog(_extension_fact("avx2", vector_bits=256))
    lowerer = Lowerer()

    first_value = lowerer.lower_generation_expression(
        selected,
        "generic::length(Vec)",
        _location(4, 7),
        catalog=catalog,
    )
    second_value = lowerer.lower_generation_expression(
        selected,
        "generic::length(Vec)",
        _location(4, 7),
        catalog=catalog,
    )
    first_diagnostics = lowerer.lower_generation_expression(
        selected,
        "generic::lanes(Vec)",
        _location(5, 7),
        catalog=catalog,
    )
    second_diagnostics = lowerer.lower_generation_expression(
        selected,
        "generic::lanes(Vec)",
        _location(5, 7),
        catalog=catalog,
    )

    assert first_value == second_value
    assert first_diagnostics == second_diagnostics


def _selected_implementation(
    *,
    body: ImplementationBody | None = None,
    backend: str = "cpp",
    operation_id: str = "add",
    extension: str = "scalar",
    type_tag: str = "si32",
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
    )
    target = Target(
        backend=backend,
        primitive_name=operation_id,
        extension=extension,
        type_tag=type_tag,
        attributes=(),
    )
    return SelectedImplementation(
        target=target,
        primitive=primitive,
        implementation=implementation,
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
