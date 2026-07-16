"""Compatibility exports for compiler-owned authoring completion vocabulary."""

from __future__ import annotations

from tslc.authoring_completion import (
    AuthoringCompletion,
    AuthoringCompletionKind,
    VAR_SELECTORS,
    authoring_completions,
)


__all__ = (
    "AuthoringCompletion",
    "AuthoringCompletionKind",
    "VAR_SELECTORS",
    "authoring_completions",
)
