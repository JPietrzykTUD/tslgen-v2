from __future__ import annotations

from dataclasses import replace

from tslc.backend.emitted_profile import used_vector_type_specs
from tslc.backend.target_capability import (
    cpp_width_indexed_register_helper,
    is_width_indexed_register_extension,
    rust_arch_module,
    rust_extension_tag,
    width_indexed_register_bits,
)
from tslc.backend.registry import create_backend_dialect
from tslc.catalog.model import Catalog
from tslc.lane_count import LaneCount
from tslc.lower.lowerer import LoweredSpecialization
from tslc.backend.cpp_profile import (
    _cpp_native_registration,
    _cpp_registration,
)
from tslc.target_text import LoweredBody
from tslc.backend.rust_vectors import rust_registrations


def test_backend_specific_feature_spellings_are_source_capabilities(
    catalog: Catalog,
) -> None:
    rdrand = catalog.target_families.target_feature("rdrand")
    vpclmulqdq = catalog.target_families.target_feature("avx512_vpclmulqdq")

    assert rdrand is not None
    assert rdrand.spelling("cpp") == "rdrnd"
    assert rdrand.spelling("rust") == "rdrand"
    assert vpclmulqdq is not None
    assert vpclmulqdq.spelling("cpp") == "vpclmulqdq"


def test_all_existing_feature_spellings_are_preserved(catalog: Catalog) -> None:
    shared_non_identity = {
        "avx512_bf16": "avx512bf16",
        "avx512_bitalg": "avx512bitalg",
        "avx512_fp16": "avx512fp16",
        "avx512_gfni": "gfni",
        "avx512_vaes": "vaes",
        "avx512_vbmi2": "avx512vbmi2",
        "avx512_vnni": "avx512vnni",
        "avx512_vp2intersect": "avx512vp2intersect",
        "avx512_vpclmulqdq": "vpclmulqdq",
        "avx512_vpopcntdq": "avx512vpopcntdq",
        "sse4_1": "sse4.1",
        "sse4_2": "sse4.2",
    }

    for name, capability in catalog.target_families.target_features.items():
        shared = shared_non_identity.get(name, name)
        assert capability.spelling("rust") == shared
        assert capability.spelling("cpp") == (
            "rdrnd" if name == "rdrand" else shared
        )


def test_width_indexed_register_capabilities_derive_from_family_role(
    catalog: Catalog,
) -> None:
    avx2 = catalog.extensions["avx2"]
    neon = catalog.extensions["neon"]
    custom = replace(
        avx2,
        name="width_demo",
        isa_name="width_demo",
        family="renamed_width_family",
        family_capability=replace(
            avx2.family_capability,
            name="renamed_width_family",
        ),
    )

    assert is_width_indexed_register_extension(avx2)
    assert not is_width_indexed_register_extension(neon)
    assert width_indexed_register_bits(avx2) == 256
    assert cpp_width_indexed_register_helper(avx2) == "reg256"
    assert cpp_width_indexed_register_helper(custom) == "reg256"
    rendered = _cpp_registration("width_demo", custom)
    assert "struct width_demo" in rendered
    assert (
        "static constexpr std::size_t lane_count_v = 256 / (sizeof(T) * 8);"
        in rendered
    )
    assert "static constexpr bool has_static_lane_count_v = true;" in rendered
    assert "static constexpr std::size_t vector_element_count = lane_count_v;" in rendered
    assert "static constexpr std::size_t lane_count() noexcept" in rendered
    assert "static constexpr std::size_t vector_alignment = 32;" in rendered
    assert "static constexpr std::size_t simd_register_alignment_v = vector_alignment;" in rendered


def test_cpp_native_registration_exposes_vector_metadata(catalog: Catalog) -> None:
    spec = LoweredSpecialization(
        backend_id="cpp",
        primitive_name="add",
        source_primitive_name="add",
        extension_name="neon",
        type_tag="si32",
        base_type_spelling="int32_t",
        register_spelling="int32x4_t",
        result_kind="v",
        param_names=("left", "right"),
        param_kinds=("v", "v"),
        body=LoweredBody.from_text("return left;"),
        vector_spelling="tsl::simd<int32_t, tsl::neon>",
    )

    rendered = _cpp_native_registration({"add": (spec,)}, catalog.extensions)

    assert "struct simd<int32_t, neon>" in rendered
    assert "static constexpr bool has_static_lane_count_v = true;" in rendered
    assert "static constexpr std::size_t lane_count_v = 4;" in rendered
    assert "static constexpr std::size_t vector_element_count = lane_count_v;" in rendered
    assert "static constexpr std::size_t lane_count() noexcept" in rendered
    assert "static constexpr std::size_t vector_alignment = 16;" in rendered
    assert "static constexpr std::size_t simd_register_alignment_v = vector_alignment;" in rendered


def test_rust_target_presentation_capabilities_derive_from_metadata(
    catalog: Catalog,
) -> None:
    avx2 = catalog.extensions["avx2"]
    neon = catalog.extensions["neon"]
    wasm128 = catalog.extensions["wasm128"]
    generic = catalog.extensions["generic"]
    custom = _custom_rust_extension(catalog, "x86_demo", "X86Demo")

    assert rust_arch_module(avx2) == "x86_64"
    assert rust_arch_module(neon) == "aarch64"
    assert rust_arch_module(wasm128) == "wasm32"
    assert rust_arch_module(generic) is None
    assert rust_extension_tag(None) == "Generic<1>"
    assert rust_extension_tag(avx2) == "Avx2"
    assert rust_extension_tag(wasm128) == "Wasm128"
    assert rust_extension_tag(custom) == "X86Demo"
    assert rust_extension_tag("oneapi_fpga") == "OneapiFpga"


def test_rust_register_spelling_uses_source_register_metadata(catalog: Catalog) -> None:
    rust = create_backend_dialect(catalog, "rust")

    assert rust.types.target_register_spelling("si32", "avx2") == (
        "core::arch::x86_64::__m256i"
    )
    assert rust.types.target_register_spelling("f32", "avx2") == (
        "core::arch::x86_64::__m256"
    )
    assert rust.types.target_register_spelling("f64", "avx2") == (
        "core::arch::x86_64::__m256d"
    )
    assert (
        rust.types.target_register_spelling("si32", "wasm128")
        == "core::arch::wasm32::v128"
    )
    assert rust.types.target_register_spelling("si32", "scalar") == "i32"
    assert (
        rust.types.target_register_spelling(
            "si32",
            "generic",
            uses_sized_vector=True,
            lane_parameter="LANES",
        )
        == "array_type<i32, LANES>"
    )


def test_lane_count_arithmetic_is_rendered_by_backend_dialects(
    catalog: Catalog,
) -> None:
    cpp = create_backend_dialect(catalog, "cpp")
    rust = create_backend_dialect(catalog, "rust")
    plain = LaneCount.symbolic("LANES")
    scaled = LaneCount.symbolic("LANES", multiplier=8, divisor=32)

    assert cpp.types.render_lane_count(LaneCount.fixed(4)) == "4"
    assert cpp.types.render_lane_count(plain) == "LANES"
    assert cpp.types.render_lane_count(scaled) == "(LANES * 8 / 32)"
    assert rust.types.render_lane_count(plain) == "LANES"
    assert rust.types.render_lane_count(scaled) is None


def test_wasm_intrinsic_composition_is_lane_shape_first(catalog: Catalog) -> None:
    wasm128 = catalog.extensions["wasm128"]
    cpp = create_backend_dialect(catalog, "cpp")
    rust = create_backend_dialect(catalog, "rust")

    assert cpp.intrinsics.default_suffix(wasm128, "si32") == "i32x4"
    assert cpp.intrinsics.compose_intrinsic_name(wasm128, "add", "i32x4") == (
        "wasm_i32x4_add"
    )
    assert rust.intrinsics.compose_intrinsic_name(wasm128, "add", "f32x4") == (
        "core::arch::wasm32::f32x4_add"
    )
    assert cpp.intrinsics.compose_intrinsic_name(wasm128, "v128_load", None) == (
        "wasm_v128_load"
    )


def test_rust_registration_uses_source_tag_and_lowered_register(
    catalog: Catalog,
) -> None:
    extension = _custom_rust_extension(catalog, "x86_demo", "X86Demo")
    spec = LoweredSpecialization(
        backend_id="rust",
        primitive_name="add",
        source_primitive_name="add",
        extension_name="x86_demo",
        type_tag="si32",
        base_type_spelling="i32",
        register_spelling="core::arch::x86_64::__m256i",
        result_kind="v",
        param_names=("left", "right"),
        param_kinds=("v", "v"),
        body=LoweredBody.from_text("return left;"),
        vector_spelling="Simd<i32, X86Demo>",
    )

    rendered = rust_registrations({"add": (spec,)}, {"x86_demo": extension})

    assert "pub struct X86Demo;" in rendered
    assert "impl SimdVector for Simd<i32, X86Demo>" in rendered
    assert "impl StaticSimdVector for Simd<i32, X86Demo>" in rendered
    assert "type RegisterType = core::arch::x86_64::__m256i;" in rendered
    assert "const ELEMENT_COUNT: usize = 8;" in rendered
    assert "fn lane_count() -> usize { 8 }" in rendered
    assert "const ALIGN: usize = 32;" in rendered


def test_rust_registration_ignores_free_function_scalar_register(
    catalog: Catalog,
) -> None:
    extension = _custom_rust_extension(catalog, "x86_demo", "X86Demo")
    vector = LoweredSpecialization(
        backend_id="rust",
        primitive_name="add",
        source_primitive_name="add",
        extension_name="x86_demo",
        type_tag="ui64",
        base_type_spelling="u64",
        register_spelling="core::arch::x86_64::__m256i",
        result_kind="v",
        param_names=("left", "right"),
        param_kinds=("v", "v"),
        body=LoweredBody.from_text("return left;"),
        vector_spelling="Simd<u64, X86Demo>",
    )
    free = LoweredSpecialization(
        backend_id="rust",
        primitive_name="random_step",
        source_primitive_name="random_step",
        extension_name="x86_demo",
        type_tag="ui64",
        base_type_spelling="u64",
        register_spelling="u64",
        result_kind="usize",
        param_names=("out",),
        param_kinds=("ptr",),
        body=LoweredBody.from_text("return 0;"),
    )

    rendered = rust_registrations(
        {"add": (vector,), "random_step": (free,)},
        {"x86_demo": extension},
    )

    assert rendered.count("impl SimdVector for Simd<u64, X86Demo>") == 1
    assert "type RegisterType = core::arch::x86_64::__m256i;" in rendered
    assert "type RegisterType = u64;" not in rendered
    assert used_vector_type_specs(
        {"add": (vector,), "random_step": (free,)}
    ) == (("x86_demo", "ui64", "u64"),)


def _custom_rust_extension(catalog: Catalog, name: str, type_name: str):
    avx2 = catalog.extensions["avx2"]
    metadata = replace(
        avx2.metadata,
        backend={
            **avx2.metadata.backend,
            "rust": replace(
                avx2.metadata.backend["rust"],
                type_name=type_name,
                arch_module="x86_64",
            ),
        },
    )
    return replace(avx2, name=name, isa_name=name, metadata=metadata)
