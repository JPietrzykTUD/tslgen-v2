"""C++ compiler capabilities recognized by TSL specialization selection."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tslc.backend.capability import (
    CompilerCapability,
    CompilerCapabilityRegistry,
)

if TYPE_CHECKING:
    from tslc.backend.emitted_profile import EmittedProfile
    from tslc.catalog.model import Extension


@dataclass(frozen=True, slots=True)
class CppCompilerCapability(CompilerCapability):
    """C++ spelling and probes for one semantic compiler capability."""

    condition_macro: str
    preprocessor_probe: str
    compile_probe_source: str | None
    diagnostic: str


_CPP_COMPILER_CAPABILITIES = (
    CppCompilerCapability(
        capability_id="clang_vector_types",
        condition_macro="TSL_COMPILER_HAS_CLANG_VECTOR_TYPES",
        preprocessor_probe="defined(__clang__)",
        compile_probe_source=None,
        diagnostic="TSL Clang vector extensions require clang++",
        header_group="clang",
        compiler_ids=("Clang", "AppleClang"),
    ),
    CppCompilerCapability(
        capability_id="ext_vector_type_boolean",
        condition_macro="TSL_COMPILER_HAS_EXT_VECTOR_TYPE_BOOLEAN",
        preprocessor_probe=(
            "defined(__has_feature) && "
            "__has_feature(ext_vector_type_boolean)"
        ),
        compile_probe_source=None,
        diagnostic="Clang Boolean extended vectors are unavailable",
    ),
    CppCompilerCapability(
        capability_id="riscv_vector",
        condition_macro="TSL_COMPILER_HAS_RISCV_VECTOR",
        preprocessor_probe="defined(__riscv_vector) && (__riscv_vector == 1)",
        compile_probe_source=None,
        diagnostic="TSL rvv profile requires the RISC-V V extension",
    ),
    *(
        CppCompilerCapability(
            capability_id=f"sve_vector_bits_{bits}",
            condition_macro=f"TSL_COMPILER_HAS_SVE_VECTOR_BITS_{bits}",
            preprocessor_probe=(
                "defined(__ARM_FEATURE_SVE_BITS) && "
                f"(__ARM_FEATURE_SVE_BITS == {bits})"
            ),
            compile_probe_source=None,
            diagnostic=(
                f"TSL sve{bits} profile requires -msve-vector-bits={bits}"
            ),
        )
        for bits in (128, 256, 512)
    ),
    CppCompilerCapability(
        capability_id="reduce_in_order_fadd",
        condition_macro="TSL_COMPILER_HAS_REDUCE_IN_ORDER_FADD",
        preprocessor_probe=(
            "__has_builtin(__builtin_reduce_in_order_fadd)"
        ),
        compile_probe_source="""\
using tsl_probe_vector = float __attribute__((ext_vector_type(4)));

float tsl_probe(tsl_probe_vector value) {
    return __builtin_reduce_in_order_fadd(value, 0.0f);
}

int main() { return 0; }
""",
        diagnostic="compiler capability reduce_in_order_fadd is unavailable",
    ),
    CppCompilerCapability(
        capability_id="ext_vector_boolean_mask_bridge",
        condition_macro="TSL_COMPILER_HAS_EXT_VECTOR_BOOLEAN_MASK_BRIDGE",
        preprocessor_probe=(
            "__has_feature(ext_vector_type_boolean) && "
            "__has_builtin(__builtin_convertvector) && "
            "(__ORDER_LITTLE_ENDIAN__ != 0) && "
            "(__BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__)"
        ),
        compile_probe_source="""\
#include <cstdint>
#include <cstring>

#ifndef __has_feature
#  define __has_feature(name) 0
#endif
#ifndef __has_builtin
#  define __has_builtin(name) 0
#endif

#if !__has_feature(ext_vector_type_boolean)
#  error "Clang Boolean extended vectors are unavailable"
#endif
#if !__has_builtin(__builtin_convertvector)
#  error "__builtin_convertvector is unavailable"
#endif
#if (__ORDER_LITTLE_ENDIAN__ == 0) || (__BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__)
#  error "the compact Boolean-mask bridge requires little-endian lane order"
#endif

using tsl_probe_data = std::int32_t __attribute__((ext_vector_type(4)));
using tsl_probe_comparison = decltype(tsl_probe_data{} == tsl_probe_data{});
using tsl_probe_boolean = bool __attribute__((ext_vector_type(4)));

static_assert(sizeof(tsl_probe_boolean) == sizeof(std::uint8_t));

std::uint8_t tsl_probe_pack(tsl_probe_comparison mask) {
    const tsl_probe_boolean packed =
        __builtin_convertvector(mask, tsl_probe_boolean);
    std::uint8_t result{};
    std::memcpy(&result, &packed, sizeof(result));
    return result;
}

tsl_probe_comparison tsl_probe_expand(std::uint8_t bits) {
    tsl_probe_boolean packed{};
    std::memcpy(&packed, &bits, sizeof(bits));
    return -__builtin_convertvector(packed, tsl_probe_comparison);
}

int main() { return 0; }
""",
        diagnostic=(
            "compiler capability ext_vector_boolean_mask_bridge is unavailable"
        ),
    ),
    CppCompilerCapability(
        capability_id="elementwise_clzg",
        condition_macro="TSL_COMPILER_HAS_ELEMENTWISE_CLZG",
        preprocessor_probe="__has_builtin(__builtin_elementwise_clzg)",
        compile_probe_source="""\
using tsl_probe_vector = unsigned int __attribute__((ext_vector_type(4)));

tsl_probe_vector tsl_probe(tsl_probe_vector value) {
    return __builtin_elementwise_clzg(
        value,
        tsl_probe_vector{32u, 32u, 32u, 32u}
    );
}

int main() { return 0; }
""",
        diagnostic="compiler capability elementwise_clzg is unavailable",
    ),
)


CPP_COMPILER_CAPABILITIES = CompilerCapabilityRegistry(
    _CPP_COMPILER_CAPABILITIES
)


def cpp_compiler_capability(capability_id: str) -> CppCompilerCapability:
    """Return one registered C++ capability probe record."""

    return CPP_COMPILER_CAPABILITIES.require(capability_id)


def cpp_extension_compiler_capabilities(
    extension: Extension | None,
) -> tuple[CppCompilerCapability, ...]:
    if extension is None:
        return ()
    metadata = extension.metadata.backend.get("cpp")
    if metadata is None:
        return ()
    return CPP_COMPILER_CAPABILITIES.require_all(metadata.compiler_capabilities)


def cpp_extensions_compiler_capabilities(
    extension_names: tuple[str, ...],
    extensions: Mapping[str, Extension],
) -> tuple[CppCompilerCapability, ...]:
    capability_ids = {
        capability.capability_id
        for extension_name in extension_names
        for capability in cpp_extension_compiler_capabilities(
            extensions.get(extension_name)
        )
    }
    return tuple(
        cpp_compiler_capability(capability_id)
        for capability_id in sorted(capability_ids)
    )


def cpp_extension_header_groups(extension: Extension | None) -> tuple[str, ...]:
    if extension is None:
        return ()
    metadata = extension.metadata.backend.get("cpp")
    if metadata is None:
        return ()
    return CPP_COMPILER_CAPABILITIES.header_groups(
        metadata.compiler_capabilities
    )


def cpp_extension_header_group(extension: Extension | None) -> str | None:
    groups = cpp_extension_header_groups(extension)
    return groups[0] if len(groups) == 1 else None


def cpp_extension_compiler_ids(extension: Extension | None) -> tuple[str, ...]:
    if extension is None:
        return ()
    metadata = extension.metadata.backend.get("cpp")
    if metadata is None:
        return ()
    return CPP_COMPILER_CAPABILITIES.compiler_ids(
        metadata.compiler_capabilities
    )


def used_cpp_compiler_capability_ids(
    profiles: tuple[EmittedProfile, ...],
) -> tuple[str, ...]:
    capability_ids: set[str] = set()
    for profile in profiles:
        for extension_name in profile.used_extensions("cpp"):
            extension = profile.extensions.get(extension_name)
            metadata = (
                None if extension is None else extension.metadata.backend.get("cpp")
            )
            if metadata is not None:
                capability_ids.update(metadata.compiler_capabilities)
        for specializations in profile.specializations("cpp").values():
            for specialization in specializations:
                for branch in specialization.compiler_branches:
                    capability_ids.update(branch.required_compiler_capabilities)
    return tuple(sorted(capability_ids))


def cpp_compiler_capability_header_defaults(
    capability_ids: tuple[str, ...],
) -> str:
    if not capability_ids:
        return ""
    lines = [
        "#ifndef __has_builtin",
        "#  define __has_builtin(name) 0",
        "#endif",
        "#ifndef __has_feature",
        "#  define __has_feature(name) 0",
        "#endif",
    ]
    for capability_id in capability_ids:
        capability = cpp_compiler_capability(capability_id)
        lines.extend(
            (
                f"#ifndef {capability.condition_macro}",
                f"#  define {capability.condition_macro} "
                f"({capability.preprocessor_probe})",
                "#endif",
            )
        )
    return "\n".join(lines) + "\n"


def cpp_compiler_capability_cmake_probes(
    capability_ids: tuple[str, ...],
) -> str:
    if not capability_ids:
        return ""
    blocks: list[str] = []
    for capability_id in capability_ids:
        capability = cpp_compiler_capability(capability_id)
        if capability.compile_probe_source is None:
            continue
        blocks.append(
            "\n".join(
                (
                    "check_cxx_source_compiles([=[",
                    capability.compile_probe_source.rstrip(),
                    f"]=] {capability.condition_macro})",
                    f'message(STATUS "TSL compiler capability '
                    f'{capability_id} = ${{{capability.condition_macro}}}")',
                )
            )
        )
    if not blocks:
        return ""
    return "include(CheckCXXSourceCompiles)\n\n" + "\n\n".join(blocks) + "\n\n"


def cpp_compiler_capability_compile_definitions(
    capability_ids: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(
        f"{capability.condition_macro}="
        f"$<BOOL:${{{capability.condition_macro}}}>"
        for capability_id in capability_ids
        for capability in (cpp_compiler_capability(capability_id),)
        if capability.compile_probe_source is not None
    )


__all__ = (
    "CPP_COMPILER_CAPABILITIES",
    "CppCompilerCapability",
    "cpp_compiler_capability",
    "cpp_compiler_capability_cmake_probes",
    "cpp_compiler_capability_compile_definitions",
    "cpp_compiler_capability_header_defaults",
    "cpp_extension_compiler_capabilities",
    "cpp_extension_compiler_ids",
    "cpp_extension_header_group",
    "cpp_extension_header_groups",
    "cpp_extensions_compiler_capabilities",
    "used_cpp_compiler_capability_ids",
)
