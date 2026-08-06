"""C++ compiler capabilities recognized by TSL specialization selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tslc.backend.capability import CompilerCapability

if TYPE_CHECKING:
    from tslc.backend.emitted_profile import EmittedProfile


@dataclass(frozen=True, slots=True)
class CppCompilerCapability(CompilerCapability):
    """C++ spelling and probes for one semantic compiler capability."""

    condition_macro: str
    preprocessor_probe: str
    compile_probe_source: str
    diagnostic: str


CPP_COMPILER_CAPABILITIES = (
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


_CPP_COMPILER_CAPABILITY_BY_ID = {
    capability.capability_id: capability
    for capability in CPP_COMPILER_CAPABILITIES
}


def cpp_compiler_capability(capability_id: str) -> CppCompilerCapability:
    """Return one registered C++ capability probe record."""

    return _CPP_COMPILER_CAPABILITY_BY_ID[capability_id]


def used_cpp_compiler_capability_ids(
    profiles: tuple[EmittedProfile, ...],
) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                capability_id
                for profile in profiles
                for specializations in profile.specializations("cpp").values()
                for specialization in specializations
                for branch in specialization.compiler_branches
                for capability_id in branch.required_compiler_capabilities
            }
        )
    )


def cpp_compiler_capability_header_defaults(
    capability_ids: tuple[str, ...],
) -> str:
    if not capability_ids:
        return ""
    lines = [
        "#ifndef __has_builtin",
        "#  define __has_builtin(name) 0",
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
    blocks = ["include(CheckCXXSourceCompiles)"]
    for capability_id in capability_ids:
        capability = cpp_compiler_capability(capability_id)
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
    return "\n\n".join(blocks) + "\n\n"


def cpp_compiler_capability_compile_definitions(
    capability_ids: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(
        f"{capability.condition_macro}="
        f"$<BOOL:${{{capability.condition_macro}}}>"
        for capability_id in capability_ids
        for capability in (cpp_compiler_capability(capability_id),)
    )


__all__ = (
    "CPP_COMPILER_CAPABILITIES",
    "CppCompilerCapability",
    "cpp_compiler_capability",
    "cpp_compiler_capability_cmake_probes",
    "cpp_compiler_capability_compile_definitions",
    "cpp_compiler_capability_header_defaults",
    "used_cpp_compiler_capability_ids",
)
