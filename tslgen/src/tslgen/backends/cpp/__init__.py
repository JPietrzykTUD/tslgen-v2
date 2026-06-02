"""C++ backend emitter."""

from tslgen.backends.cpp.backend import CppBackend
from tslgen.backends.cpp.body_tokens import (
    CppBodyText,
    CppBodyTokenRenderResult,
    CppRenderedBodyTokens,
    render_cpp_body_tokens_from_intrinsic_handoff,
)
from tslgen.backends.cpp.intrinsic_calls import (
    CppIntrinsicCallRenderResult,
    CppIntrinsicCallText,
    CppRenderedIntrinsicCall,
    render_cpp_intrinsic_invocation_call,
)

__all__ = [
    "CppBodyText",
    "CppBodyTokenRenderResult",
    "CppBackend",
    "CppIntrinsicCallRenderResult",
    "CppIntrinsicCallText",
    "CppRenderedBodyTokens",
    "CppRenderedIntrinsicCall",
    "render_cpp_body_tokens_from_intrinsic_handoff",
    "render_cpp_intrinsic_invocation_call",
]
