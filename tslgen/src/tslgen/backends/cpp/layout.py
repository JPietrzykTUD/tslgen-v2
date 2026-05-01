from __future__ import annotations

from pathlib import PurePosixPath

from tslgen.core.diagnostics import Diagnostic
from tslgen.io.artifacts import ArtifactDescriptor


CPP_LAYOUT_METADATA_KEY = "cpp_layout"
CPP_NATIVE_HEADER_LAYOUT = "native_header"
CPP_NATIVE_HEADER_PATH = PurePosixPath("tsl/tsl_native.hpp")
SUPPORTED_CPP_LAYOUTS = frozenset({CPP_NATIVE_HEADER_LAYOUT})


def cpp_layout_name(descriptor: ArtifactDescriptor) -> str | None:
    """Return the selected C++ layout name, if the descriptor requests one."""
    explicit_value = descriptor.metadata.get(CPP_LAYOUT_METADATA_KEY)
    if isinstance(explicit_value, str):
        return explicit_value
    if explicit_value is None and descriptor.logical_path == CPP_NATIVE_HEADER_PATH:
        return CPP_NATIVE_HEADER_LAYOUT
    return None


def is_cpp_native_header_layout(descriptor: ArtifactDescriptor) -> bool:
    return cpp_layout_name(descriptor) == CPP_NATIVE_HEADER_LAYOUT


def cpp_layout_diagnostics(descriptor: ArtifactDescriptor) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    explicit_value = descriptor.metadata.get(CPP_LAYOUT_METADATA_KEY)
    if explicit_value is not None and not isinstance(explicit_value, str):
        diagnostics.append(
            Diagnostic.error(
                "TSL-CPP-RENDER-LAYOUT-UNSUPPORTED",
                f"C++ layout metadata {CPP_LAYOUT_METADATA_KEY!r} must be a "
                f"string; got {type(explicit_value).__name__}",
            )
        )
        return tuple(diagnostics)

    layout_name = cpp_layout_name(descriptor)
    if layout_name is None:
        return tuple(diagnostics)
    if layout_name not in SUPPORTED_CPP_LAYOUTS:
        diagnostics.append(
            Diagnostic.error(
                "TSL-CPP-RENDER-LAYOUT-UNSUPPORTED",
                f"C++ renderer does not support layout {layout_name!r}; "
                f"expected one of {_supported_layout_list()}",
            )
        )
        return tuple(diagnostics)
    if layout_name == CPP_NATIVE_HEADER_LAYOUT and (
        descriptor.logical_path != CPP_NATIVE_HEADER_PATH
    ):
        diagnostics.append(
            Diagnostic.error(
                "TSL-CPP-RENDER-LAYOUT-PATH",
                f"C++ layout {CPP_NATIVE_HEADER_LAYOUT!r} must render to "
                f"{CPP_NATIVE_HEADER_PATH.as_posix()!r}; got "
                f"{descriptor.logical_path.as_posix()!r}",
            )
        )
    return tuple(diagnostics)


def render_cpp_native_header_preamble() -> str:
    return render_cpp_native_header()


def render_cpp_native_header(
    *,
    detail_lines: tuple[str, ...] = (),
    wrapper_lines: tuple[str, ...] = (),
) -> str:
    lines = list(_CPP_NATIVE_HEADER_PREFIX_LINES)
    if detail_lines:
        lines.extend(("", *detail_lines))
    lines.extend(("", "}  // namespace detail"))
    if wrapper_lines:
        lines.extend(("", *wrapper_lines))
    lines.extend(("}  // namespace tsl", ""))
    return "\n".join(lines)


def _supported_layout_list() -> str:
    return ", ".join(repr(layout) for layout in sorted(SUPPORTED_CPP_LAYOUTS))


_CPP_NATIVE_HEADER_PREFIX_LINES = (
    "#include <algorithm>",
    "#include <array>",
    "#include <bit>",
    "#include <bitset>",
    "#include <cmath>",
    "#include <cstddef>",
    "#include <cstdint>",
    "#include <cstring>",
    "#include <iomanip>",
    "#include <limits>",
    "#include <ostream>",
    "#include <tuple>",
    "#include <type_traits>",
    "#include <utility>",
    "#include <vector>",
    "#include <immintrin.h>",
    "",
    "#ifndef TSL_FORCE_INLINE",
    "#define TSL_FORCE_INLINE inline",
    "#endif",
    "",
    "#ifndef TSL_UNROLL",
    "#define TSL_UNROLL(x)",
    "#endif",
    "",
    "#ifndef VectorProcessingStyle",
    "#define VectorProcessingStyle typename",
    "#endif",
    "",
    "namespace tsl {",
    "",
    "struct scalar;",
    "struct avx2;",
    "",
    "template <typename T, typename Ext>",
    "struct simd;",
    "",
    "namespace detail {",
    "",
    "template <typename Vec>",
    "struct reg_param {",
    "  using type = const typename Vec::register_type;",
    "};",
)
