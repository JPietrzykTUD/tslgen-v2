from __future__ import annotations

from dataclasses import replace

from tslc.backend.target_capability import (
    cpp_x86_register_helper,
    is_x86_register_extension,
    rust_arch_module,
    rust_extension_tag,
    x86_register_bits,
)
from tslc.backend.translation import create_backend_dialect
from tslc.catalog.model import Catalog
from tslc.lower.lowerer import LoweredSpecialization
from tslc.render.cpp_project import _cpp_native_registration, _cpp_registration
from tslc.render.model import LoweredBody
from tslc.render.rust_project import _rust_registrations


def test_x86_register_capabilities_derive_from_extension_facts(
    catalog: Catalog,
) -> None:
    avx2 = catalog.extensions["avx2"]
    neon = catalog.extensions["neon"]
    custom = replace(avx2, name="x86_demo", isa_name="x86_demo")

    assert is_x86_register_extension(avx2)
    assert not is_x86_register_extension(neon)
    assert x86_register_bits(avx2) == 256
    assert cpp_x86_register_helper(avx2) == "reg256"
    assert cpp_x86_register_helper(custom) == "reg256"
    rendered = _cpp_registration("x86_demo", custom)
    assert "struct x86_demo" in rendered
    assert (
        "static constexpr std::size_t vector_element_count = 256 / (sizeof(T) * 8);"
        in rendered
    )
    assert "static constexpr std::size_t vector_alignment = 32;" in rendered


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
        body=LoweredBody.from_text("return left;", backend_id="cpp"),
        vector_spelling="tsl::simd<int32_t, tsl::neon>",
    )

    rendered = _cpp_native_registration({"add": (spec,)}, catalog.extensions)

    assert "struct simd<int32_t, neon>" in rendered
    assert "static constexpr std::size_t vector_element_count = 4;" in rendered
    assert "static constexpr std::size_t vector_alignment = 16;" in rendered


def test_rust_target_presentation_capabilities_derive_from_metadata(
    catalog: Catalog,
) -> None:
    avx2 = catalog.extensions["avx2"]
    neon = catalog.extensions["neon"]
    generic = catalog.extensions["generic"]
    custom = _custom_rust_extension(catalog, "x86_demo", "X86Demo")

    assert rust_arch_module(avx2) == "x86_64"
    assert rust_arch_module(neon) == "aarch64"
    assert rust_arch_module(generic) is None
    assert rust_extension_tag(None) == "Generic<1>"
    assert rust_extension_tag(avx2) == "Avx2"
    assert rust_extension_tag(custom) == "X86Demo"
    assert rust_extension_tag("oneAPIfpga") == "OneAPIfpga"


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
        body=LoweredBody.from_text("return left;", backend_id="rust"),
        vector_spelling="Simd<i32, X86Demo>",
    )

    rendered = _rust_registrations({"add": (spec,)}, {"x86_demo": extension})

    assert "pub struct X86Demo;" in rendered
    assert "impl SimdVector for Simd<i32, X86Demo>" in rendered
    assert "type RegisterType = core::arch::x86_64::__m256i;" in rendered
    assert "const ELEMENT_COUNT: usize = 8;" in rendered
    assert "const ALIGN: usize = 32;" in rendered


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
