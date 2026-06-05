"""Rust backend emitter."""

from tslgen.backends.rust.backend import RustBackend
from tslgen.backends.rust.body_tokens import (
    RustBodyText,
    RustBodyTokenRenderResult,
    RustRenderedBodyTokens,
    RustRenderedTypeQueryBodyTokens,
    RustRenderedValueQueryBodyTokens,
    RustTypeQueryBodyTokenRenderResult,
    RustValueQueryBodyTokenRenderResult,
    render_rust_body_tokens_from_intrinsic_handoff,
    render_rust_body_tokens_from_type_query_handoff,
    render_rust_body_tokens_from_value_query_handoff,
)
from tslgen.backends.rust.intrinsic_calls import (
    RustArchitectureModule,
    RustIntrinsicCallRenderResult,
    RustIntrinsicCallText,
    RustIntrinsicNameQualification,
    RustRenderedIntrinsicCall,
    render_rust_intrinsic_invocation_call,
)

__all__ = [
    "RustArchitectureModule",
    "RustBodyText",
    "RustBodyTokenRenderResult",
    "RustBackend",
    "RustIntrinsicCallRenderResult",
    "RustIntrinsicCallText",
    "RustIntrinsicNameQualification",
    "RustRenderedBodyTokens",
    "RustRenderedIntrinsicCall",
    "RustRenderedTypeQueryBodyTokens",
    "RustRenderedValueQueryBodyTokens",
    "RustTypeQueryBodyTokenRenderResult",
    "RustValueQueryBodyTokenRenderResult",
    "render_rust_body_tokens_from_intrinsic_handoff",
    "render_rust_body_tokens_from_type_query_handoff",
    "render_rust_body_tokens_from_value_query_handoff",
    "render_rust_intrinsic_invocation_call",
]
