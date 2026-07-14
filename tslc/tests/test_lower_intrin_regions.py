"""Intrinsic-building TSIL region lowering regressions."""

from __future__ import annotations

from _select_lower_backend_support import (
    Catalog,
    create_backend_dialect,
    Extension,
    Implementation,
    Lowerer,
    Primitive,
    SelectedImplementation,
)


def test_consumed_tsil_statement_terminators_render_once() -> None:
    ext = Extension(
        name="scalar",
        isa_name="scalar",
        family="scalar",
        compose_prefix={},
        compose_suffix_by_type={},
        backend_supported={"cpp": True},
    )
    impl = Implementation(
        ("scalar", "ints"),
        "scalar",
        "ints",
        (
            "let<type>(Alias, type(base::in)); "
            "var<infer>(tmp, a); intrin<side_effect>(tmp); complete(tmp);"
        ),
        source_order=0,
    )
    prim = Primitive(
        name="semicolon_once",
        signature="v:=v",
        parameters=("a",),
        attribute_keys=(),
        implementations=(impl,),
    )
    catalog = Catalog(
        primitives=(prim,),
        type_groups={"ints": ("si32",)},
        extensions={"scalar": ext},
        type_spellings={"cpp": {"s32": "int32_t"}},
        translations={
            "cpp": {
                "complete": "return {value}",
                "var_infer": "auto {name} = {value};",
            }
        },
    )
    slot = SelectedImplementation(
        primitive=prim,
        implementation=impl,
        extension=ext,
        type_tag="si32",
    )

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert cpp.body_text == "auto tmp = a; side_effect(tmp); return tmp;"
    assert ";;" not in cpp.body_text


def test_intrin_build_supports_explicit_prefix_and_suffix() -> None:
    ext = Extension(
        name="custom",
        isa_name="custom",
        family="x86",
        compose_prefix={},
        compose_suffix_by_type={},
        backend_supported={"cpp": True},
    )
    impl = Implementation(
        ("custom", "ints"),
        "custom",
        "ints",
        'complete(intrin<foo, build[prefix="_custom_", suffix="bar"]>(a));',
        source_order=0,
    )
    prim = Primitive(
        name="explicit_intrin_build",
        signature="v:=v",
        parameters=("a",),
        attribute_keys=(),
        implementations=(impl,),
    )
    catalog = Catalog(
        primitives=(prim,),
        type_groups={"ints": ("si32",)},
        extensions={"custom": ext},
        type_spellings={"cpp": {"s32": "int32_t"}},
        translations={"cpp": {"complete": "return {value}"}},
    )
    slot = SelectedImplementation(
        primitive=prim,
        implementation=impl,
        extension=ext,
        type_tag="si32",
    )

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert cpp.body_text == "return _custom_foo_bar(a);"


def test_wasm_intrin_build_requires_lane_suffix_for_typed_ops() -> None:
    ext = Extension(
        name="wasm128",
        isa_name="wasm128",
        family="wasm",
        intrinsic_style="wasm",
        compose_prefix={"cpp": "wasm_"},
        compose_suffix_by_type={},
        backend_supported={"cpp": True},
    )
    impl = Implementation(
        ("wasm128", "ints"),
        "wasm128",
        "ints",
        "complete(intrin<add, build>(a, b));",
        source_order=0,
    )
    prim = Primitive(
        name="bad_wasm_intrin_build",
        signature="v:=(v,v)",
        parameters=("a", "b"),
        attribute_keys=(),
        implementations=(impl,),
    )
    catalog = Catalog(
        primitives=(prim,),
        type_groups={"ints": ("si32",)},
        extensions={"wasm128": ext},
        type_spellings={"cpp": {"s32": "int32_t"}},
        translations={"cpp": {"complete": "return {value}"}},
    )
    slot = SelectedImplementation(
        primitive=prim,
        implementation=impl,
        extension=ext,
        type_tag="si32",
    )

    lowered = Lowerer().lower(slot, catalog, create_backend_dialect(catalog, "cpp"))

    assert lowered.specialization is None
    assert lowered.diagnostics[0].code == "TSL-LOWER-WASM-INTRIN-MISSING-LANE-SUFFIX"


def test_wasm_intrin_build_accepts_explicit_empty_suffix_for_v128_ops() -> None:
    ext = Extension(
        name="wasm128",
        isa_name="wasm128",
        family="wasm",
        intrinsic_style="wasm",
        compose_prefix={"cpp": "wasm_"},
        compose_suffix_by_type={},
        backend_supported={"cpp": True},
    )
    impl = Implementation(
        ("wasm128", "ints"),
        "wasm128",
        "ints",
        'complete(intrin<v128_load, build[suffix=""]>(a));',
        source_order=0,
    )
    prim = Primitive(
        name="wasm_v128_intrin_build",
        signature="v:=v",
        parameters=("a",),
        attribute_keys=(),
        implementations=(impl,),
    )
    catalog = Catalog(
        primitives=(prim,),
        type_groups={"ints": ("si32",)},
        extensions={"wasm128": ext},
        type_spellings={"cpp": {"s32": "int32_t"}},
        translations={"cpp": {"complete": "return {value}"}},
    )
    slot = SelectedImplementation(
        primitive=prim,
        implementation=impl,
        extension=ext,
        type_tag="si32",
    )

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert cpp.body_text == "return wasm_v128_load(a);"


def test_intrin_build_suffix_and_infix_accept_type_values() -> None:
    ext = Extension(
        name="custom",
        isa_name="custom",
        family="x86",
        compose_prefix={"cpp": "_custom_"},
        compose_suffix_by_type={"si32": "epi32"},
        backend_supported={"cpp": True},
    )
    impl = Implementation(
        ("custom", "ints"),
        "custom",
        "ints",
        "complete("
        "intrin<foo, build[infix=base::signed_of(base::in), "
        'infix_sep="", suffix=base::signed_of(base::in)]>(a)'
        ");",
        source_order=0,
    )
    prim = Primitive(
        name="typed_intrin_build",
        signature="v:=v",
        parameters=("a",),
        attribute_keys=(),
        implementations=(impl,),
    )
    catalog = Catalog(
        primitives=(prim,),
        type_groups={"ints": ("si32",)},
        extensions={"custom": ext},
        type_spellings={"cpp": {"s32": "int32_t"}},
        translations={"cpp": {"complete": "return {value}"}},
    )
    slot = SelectedImplementation(
        primitive=prim,
        implementation=impl,
        extension=ext,
        type_tag="si32",
    )

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert cpp.body_text == "return _custom_fooepi32_epi32(a);"


def test_intrin_build_appends_literal_post_fragment() -> None:
    ext = Extension(
        name="custom",
        isa_name="custom",
        family="x86",
        compose_prefix={"cpp": ""},
        compose_suffix_by_type={"si32": "s32"},
        backend_supported={"cpp": True},
    )
    impl = Implementation(
        ("custom", "ints"),
        "custom",
        "ints",
        "complete(intrin<foo, build[post=x]>(a));",
        source_order=0,
    )
    prim = Primitive(
        name="post_intrin_build",
        signature="v:=v",
        parameters=("a",),
        attribute_keys=(),
        implementations=(impl,),
    )
    catalog = Catalog(
        primitives=(prim,),
        type_groups={"ints": ("si32",)},
        extensions={"custom": ext},
        type_spellings={"cpp": {"s32": "int32_t"}},
        translations={"cpp": {"complete": "return {value}"}},
    )
    slot = SelectedImplementation(
        primitive=prim,
        implementation=impl,
        extension=ext,
        type_tag="si32",
    )

    cpp = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert cpp is not None
    assert cpp.body_text == "return foo_s32_x(a);"


def test_intrin_build_prefix_remains_text_only() -> None:
    ext = Extension(
        name="custom",
        isa_name="custom",
        family="x86",
        compose_prefix={"cpp": "_custom_"},
        compose_suffix_by_type={"si32": "epi32"},
        backend_supported={"cpp": True},
    )
    impl = Implementation(
        ("custom", "ints"),
        "custom",
        "ints",
        "complete(intrin<foo, build[prefix=base::in, suffix=base::in]>(a));",
        source_order=0,
    )
    prim = Primitive(
        name="bad_prefix_intrin_build",
        signature="v:=v",
        parameters=("a",),
        attribute_keys=(),
        implementations=(impl,),
    )
    catalog = Catalog(
        primitives=(prim,),
        type_groups={"ints": ("si32",)},
        extensions={"custom": ext},
        type_spellings={"cpp": {"s32": "int32_t"}},
        translations={"cpp": {"complete": "return {value}"}},
    )
    slot = SelectedImplementation(
        primitive=prim,
        implementation=impl,
        extension=ext,
        type_tag="si32",
    )

    lowered = Lowerer().lower(slot, catalog, create_backend_dialect(catalog, "cpp"))

    assert lowered.specialization is None
    assert lowered.diagnostics[0].code == "TSL-LOWER-UNRESOLVED-PREFIX"


def test_intrin_build_rejects_whitespace_separated_selector_terms() -> None:
    ext = Extension(
        name="custom",
        isa_name="custom",
        family="x86",
        compose_prefix={"cpp": "_custom_"},
        compose_suffix_by_type={"si32": "epi32"},
        backend_supported={"cpp": True},
    )
    impl = Implementation(
        ("custom", "ints"),
        "custom",
        "ints",
        "complete(intrin<foo build[suffix=base::in]>(a));",
        source_order=0,
    )
    prim = Primitive(
        name="bad_intrin_build_separator",
        signature="v:=v",
        parameters=("a",),
        attribute_keys=(),
        implementations=(impl,),
    )
    catalog = Catalog(
        primitives=(prim,),
        type_groups={"ints": ("si32",)},
        extensions={"custom": ext},
        type_spellings={"cpp": {"s32": "int32_t"}},
        translations={"cpp": {"complete": "return {value}"}},
    )
    slot = SelectedImplementation(
        primitive=prim,
        implementation=impl,
        extension=ext,
        type_tag="si32",
    )

    lowered = Lowerer().lower(slot, catalog, create_backend_dialect(catalog, "cpp"))

    assert lowered.specialization is None
    assert lowered.diagnostics[0].code == "TSL-LOWER-UNSUPPORTED-INTRIN-SELECTOR"
