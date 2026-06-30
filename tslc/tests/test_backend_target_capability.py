from __future__ import annotations

from tslc.backend.target_capability import (
    X86_REGISTER_BITS,
    cpp_x86_register_helper,
    is_x86_register_extension,
    rust_arch_module,
    rust_extension_tag,
    rust_register_type,
    x86_register_bits,
)


def test_x86_register_capabilities_are_shared_target_facts() -> None:
    assert dict(X86_REGISTER_BITS) == {"sse": 128, "avx2": 256, "avx512": 512}
    assert is_x86_register_extension("avx2")
    assert not is_x86_register_extension("neon")
    assert x86_register_bits("avx2") == 256
    assert cpp_x86_register_helper("avx2") == "reg256"


def test_rust_target_presentation_capabilities_are_shared() -> None:
    assert rust_arch_module("x86") == "x86_64"
    assert rust_arch_module("arm") == "aarch64"
    assert rust_arch_module("generic_like") is None
    assert rust_extension_tag(None) == "Generic<1>"
    assert rust_extension_tag("avx2") == "Avx2"
    assert rust_extension_tag("avx2_vl") == "Avx2Vl"
    assert rust_extension_tag("oneAPIfpga") == "OneAPIfpga"


def test_rust_register_spelling_uses_x86_capabilities() -> None:
    assert rust_register_type("avx2", "i32") == "core::arch::x86_64::__m256i"
    assert rust_register_type("avx2", "f32") == "core::arch::x86_64::__m256"
    assert rust_register_type("avx2", "f64") == "core::arch::x86_64::__m256d"
    assert rust_register_type("scalar", "i32") == "i32"
    assert (
        rust_register_type("generic", "i32", uses_sized_vector=True, lane_parameter="LANES")
        == "array_type<i32, LANES>"
    )
