"""C++ backend emitter."""

from tslgen.backends.cpp.backend import CppBackend
from tslgen.backends.cpp.body_tokens import (
    CppBodyText,
    CppBodyTokenRenderResult,
    CppRenderedBodyTokens,
    CppRenderedTypeQueryBodyTokens,
    CppRenderedValueQueryBodyTokens,
    CppTypeQueryBodyTokenRenderResult,
    CppValueQueryBodyTokenRenderResult,
    render_cpp_body_tokens_from_intrinsic_handoff,
    render_cpp_body_tokens_from_type_query_handoff,
    render_cpp_body_tokens_from_value_query_handoff,
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
    "CppRenderedTypeQueryBodyTokens",
    "CppRenderedValueQueryBodyTokens",
    "CppTypeQueryBodyTokenRenderResult",
    "CppValueQueryBodyTokenRenderResult",
    "render_cpp_body_tokens_from_intrinsic_handoff",
    "render_cpp_body_tokens_from_type_query_handoff",
    "render_cpp_body_tokens_from_value_query_handoff",
    "render_cpp_intrinsic_invocation_call",
]
