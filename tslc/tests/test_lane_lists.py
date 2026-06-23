"""First-class lane-list signature and lowering slice."""

from __future__ import annotations

import pytest

from tslc.backend.cpp import CppBackend
from tslc.backend.rust import RustBackend
from tslc.backend.translation import create_backend_dialect
from tslc.catalog.model import Catalog, Extension, Implementation, Primitive
from tslc.lower.lowerer import Lowerer
from tslc.select.selector import SelectedImplementation


def _lane_list_catalog(
    body: str,
    *,
    extension_name: str = "scalar",
    family: str = "scalar",
    vector_bits: int = 0,
) -> tuple[Catalog, SelectedImplementation]:
    extension = Extension(
        name=extension_name,
        isa_name=extension_name,
        family=family,
        compose_prefix={},
        compose_suffix_by_type={},
        vector_bits=vector_bits,
    )
    implementation = Implementation(
        (extension_name, "ints"),
        extension_name,
        "ints",
        body,
        source_order=0,
    )
    primitive = Primitive(
        name="lane_set",
        signature="v:=(lanes<s>)",
        parameters=("values",),
        attribute_keys=(),
        implementations=(implementation,),
    )
    catalog = Catalog(
        primitives=(primitive,),
        type_groups={"ints": ("si32",)},
        extensions={extension_name: extension},
        type_spellings={
            "cpp": {"s32": "int32_t"},
            "rust": {"s32": "i32"},
        },
        translations={},
    )
    selected = SelectedImplementation(
        primitive=primitive,
        implementation=implementation,
        extension=extension,
        type_tag="si32",
    )
    return catalog, selected


def test_lanes_at_literal_lowers_from_typed_lane_list_param() -> None:
    catalog, selected = _lane_list_catalog("emit_return(lanes<at>(values, 0));")

    cpp = Lowerer().lower(selected, catalog, create_backend_dialect(catalog, "cpp"))
    assert cpp.diagnostics == ()
    assert cpp.specialization is not None
    assert cpp.specialization.param_kinds == ("lanes<s>",)
    assert cpp.specialization.body_text == "return values[0];"
    assert len(cpp.specialization.lane_list_params) == 1
    assert cpp.specialization.lane_list_params[0].name == "values"
    assert cpp.specialization.lane_list_params[0].element_kind == "s"
    assert cpp.specialization.lane_list_params[0].lane_count == 1


def test_lanes_at_renders_array_like_cpp_and_rust_parameters() -> None:
    catalog, selected = _lane_list_catalog("emit_return(lanes<at>(values, 0));")
    cpp_spec = Lowerer().lower(
        selected, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization
    rust_spec = Lowerer().lower(
        selected, catalog, create_backend_dialect(catalog, "rust")
    ).specialization
    assert cpp_spec is not None
    assert rust_spec is not None

    cpp_text = CppBackend().render_primitive("lane_set", (cpp_spec,))
    assert "template <class... Args>" not in cpp_text
    assert "typename ::tsl::array_for<Vec>::type values" in cpp_text
    assert "return values[0];" in cpp_text

    rust_text = RustBackend().render_primitive("lane_set", (rust_spec,))
    assert "values: Self::Array" in rust_text
    assert "return values[0];" in rust_text


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ("emit_return(lanes<first>(values, 0));", "TSL-LOWER-LANES-UNSUPPORTED"),
        ("emit_return(lanes<at>(values));", "TSL-LOWER-LANES-ARITY"),
        ("emit_return(lanes<at>(args, 0));", "TSL-LOWER-LANES-UNKNOWN"),
        ("emit_return(lanes<at>(values, i));", "TSL-LOWER-LANES-NON-GENERATION-INDEX"),
    ],
)
def test_lanes_at_reports_unsupported_first_slice_shapes(body: str, code: str) -> None:
    catalog, selected = _lane_list_catalog(body)

    result = Lowerer().lower(selected, catalog, create_backend_dialect(catalog, "cpp"))

    assert result.specialization is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [code]


def test_lanes_at_reports_literal_index_out_of_range() -> None:
    catalog, selected = _lane_list_catalog("emit_return(lanes<at>(values, 1));")

    result = Lowerer().lower(selected, catalog, create_backend_dialect(catalog, "cpp"))

    assert result.specialization is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-LOWER-LANES-INDEX-OUT-OF-RANGE"
    ]


def test_generation_loop_expands_with_bound_lane_indexes() -> None:
    catalog, selected = _lane_list_catalog(
        "loop<generation>(i, 0, value<generation>(vector::length), 1) { "
        "lanes<at>(values, i); "
        "} emit_return(lanes<at>(values, value<generation>(vector::length) - 1));",
        extension_name="simd128",
        family="x86",
        vector_bits=128,
    )

    result = Lowerer().lower(selected, catalog, create_backend_dialect(catalog, "cpp"))

    assert result.diagnostics == ()
    assert result.specialization is not None
    assert result.specialization.body_text == (
        "values[0];values[1];values[2];values[3]; return values[3];"
    )


def test_generation_loop_rejects_non_integer_bounds() -> None:
    catalog, selected = _lane_list_catalog(
        "loop<generation>(i, 0, LANES, 1) { lanes<at>(values, i); } "
        "emit_return(lanes<at>(values, 0));"
    )

    result = Lowerer().lower(selected, catalog, create_backend_dialect(catalog, "cpp"))

    assert result.specialization is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-LOWER-GENERATION-LOOP-NON-INTEGER"
    ]


def test_generation_loop_rejects_zero_step() -> None:
    catalog, selected = _lane_list_catalog(
        "loop<generation>(i, 0, 1, 0) { lanes<at>(values, i); } "
        "emit_return(lanes<at>(values, 0));"
    )

    result = Lowerer().lower(selected, catalog, create_backend_dialect(catalog, "cpp"))

    assert result.specialization is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-LOWER-GENERATION-LOOP-ZERO-STEP"
    ]
