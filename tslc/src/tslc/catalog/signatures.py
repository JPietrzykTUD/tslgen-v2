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

# Kinds that do NOT project through a SIMD vector: a raw pointer (`ptr`/`cptr`), a size/count
# (`usize`), or no value (`void`). A primitive whose result and every parameter are one of
# these has no vector axis, so it is emitted as a plain free function in the `tsl` namespace
# (e.g. `allocate`/`deallocate`) rather than a `simd<>`-templated wrapper. `s` (scalar) is
# deliberately excluded: it projects through the vector's `base_type` (so `memory_cp`'s
# `void:=(ptr,cptr,s,s)` stays a per-type templated primitive).
_FREE_FUNCTION_KINDS = frozenset({"ptr", "cptr", "usize", "void"})


def is_free_function_signature(result_kind: str, param_kinds: tuple[str, ...]) -> bool:
    """Whether a signature shape has no SIMD-vector axis (-> emitted as a free function)."""

    return result_kind in _FREE_FUNCTION_KINDS and all(
        kind in _FREE_FUNCTION_KINDS for kind in param_kinds
    )


LANE_LIST_KIND = "lanes<s>"


@dataclass(frozen=True, slots=True)
class SignatureTerm:
    """One typed term in a primitive signature.

    ``kind`` is the normalized compatibility spelling consumed by existing
    selection/lowering/render code. Lane-list terms additionally expose their
    source element kind so validators and lowerers do not have to re-parse the
    raw string convention.
    """

    kind: str
    lane_element_kind: str | None = None

    @property
    def is_lane_list(self) -> bool:
        return self.lane_element_kind is not None

    @property
    def is_lane_list_like(self) -> bool:
        return self.is_lane_list or self.kind.startswith("lanes")


@dataclass(frozen=True, slots=True)
class SignatureShape:
    result_term: SignatureTerm
    param_terms: tuple[SignatureTerm, ...]

    @property
    def result_kind(self) -> str:
        return self.result_term.kind

    @property
    def param_kinds(self) -> tuple[str, ...]:
        return tuple(term.kind for term in self.param_terms)

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
    param_terms = tuple(
        _parse_term(part)
        for part in _split_signature_params(params_text)
        if part.strip()
    )
    return SignatureShape(
        result_term=_parse_term(result_text),
        param_terms=param_terms,
    )


def _parse_term(text: str) -> SignatureTerm:
    stripped = _INDEX_ANNOTATION.sub("", text.strip())
    if stripped.startswith("lanes<") and stripped.endswith(">"):
        element = stripped[len("lanes<") : -1].strip()
        return SignatureTerm(kind=f"lanes<{element}>", lane_element_kind=element)
    return SignatureTerm(kind=stripped)


def _split_signature_params(text: str) -> tuple[str, ...]:
    parts: list[str] = []
    start = 0
    depth = 0
    for index, char in enumerate(text):
        if char in "(<[":
            depth += 1
        elif char in ")>]":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(text[start:index])
            start = index + 1
    parts.append(text[start:])
    return tuple(parts)
