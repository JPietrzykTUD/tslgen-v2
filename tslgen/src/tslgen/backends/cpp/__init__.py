"""C++ backend emitter."""

from tslgen.backends.cpp.backend import CppBackend
from tslgen.backends.cpp.intrinsic_calls import (
    CppIntrinsicCallRenderResult,
    CppIntrinsicCallText,
    CppRenderedIntrinsicCall,
    render_cpp_intrinsic_invocation_call,
)

__all__ = [
    "CppBackend",
    "CppIntrinsicCallRenderResult",
    "CppIntrinsicCallText",
    "CppRenderedIntrinsicCall",
    "render_cpp_intrinsic_invocation_call",
]
