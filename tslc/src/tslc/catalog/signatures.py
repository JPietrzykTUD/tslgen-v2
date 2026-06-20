"""Primitive signature shapes.

A signature like ``v:=(v,v)`` or ``s:=v`` describes the *kinds* of a primitive's
result and parameters in semantic terms — vector (``v``), scalar (``s``), mask
(``m``), pointer (``ptr``), etc. The backend turns each kind into a concrete type
spelling; this module only recovers the shape.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

# A ``[name]`` index annotation on a param kind (``v[idx]`` = a vector indexed by a compile-time
# index, the lane `extract_value` returns). Decorative — the index itself is a `generic_params`
# entry (`Index {kind int}`), so the param's kind is just the bare ``v``. Empty ``[]`` is NOT
# matched: that is the array kind ``s[]``, which must be preserved.
_INDEX_ANNOTATION = re.compile(r"\[[A-Za-z_]\w*\]$")

# Kinds that do NOT project through a SIMD vector: a raw pointer (`ptr`), a size/count
# (`usize`), or no value (`void`). A primitive whose result and every parameter are one of
# these has no vector axis, so it is emitted as a plain free function in the `tsl` namespace
# (e.g. `allocate`/`deallocate`) rather than a `simd<>`-templated wrapper. `s` (scalar) is
# deliberately excluded: it projects through the vector's `base_type` (so `memory_cp`'s
# `void:=(ptr,ptr,s,s)` stays a per-type templated primitive).
_FREE_FUNCTION_KINDS = frozenset({"ptr", "usize", "void"})


def is_free_function_signature(result_kind: str, param_kinds: tuple[str, ...]) -> bool:
    """Whether a signature shape has no SIMD-vector axis (-> emitted as a free function)."""

    return result_kind in _FREE_FUNCTION_KINDS and all(
        kind in _FREE_FUNCTION_KINDS for kind in param_kinds
    )


@dataclass(frozen=True, slots=True)
class SignatureShape:
    result_kind: str
    param_kinds: tuple[str, ...]

    @property
    def is_free_function(self) -> bool:
        """A non-vector primitive (``ptr``/``usize``/``void`` only): emitted as a free function."""

        return is_free_function_signature(self.result_kind, self.param_kinds)


@lru_cache(maxsize=None)
def parse_signature(text: str) -> SignatureShape | None:
    """Parse ``RESULT:=PARAMS`` into a :class:`SignatureShape`.

    ``PARAMS`` is either a single kind (``s:=v``) or a parenthesized,
    comma-separated list (``v:=(v,v)``). Returns ``None`` if it does not match.
    """

    result_text, separator, params_text = text.partition(":=")
    if not separator:
        return None
    params_text = params_text.strip()
    if params_text.startswith("(") and params_text.endswith(")"):
        params_text = params_text[1:-1]
    param_kinds = tuple(
        _INDEX_ANNOTATION.sub("", part.strip())
        for part in params_text.split(",")
        if part.strip()
    )
    return SignatureShape(result_kind=result_text.strip(), param_kinds=param_kinds)
