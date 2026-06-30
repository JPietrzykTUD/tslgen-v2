"""Source-owned value-test case naming and lane-count policy."""

from __future__ import annotations

from tslc.catalog.model import TestArg
from tslc.catalog.signatures import SignatureShape


def derive_test_case_name(
    *,
    primitive_name: str,
    type_tag: str,
    tags: tuple[str, ...],
    case_id: str | None = None,
    extension: str | None = None,
    to_type: str | None = None,
    to_extension: str | None = None,
    index: int | None = None,
    attrs: dict[str, str] | None = None,
) -> str:
    """Stable case id from semantic axes and tags.

    Source tests should not carry renderer-facing names. The generated case id is derived from
    the primitive plus typed axes. ``case_id`` is a rare disambiguator; when present it replaces
    the tag suffix rather than duplicating it.
    """

    parts = [_piece(primitive_name), _piece(type_tag)]
    if extension:
        parts.append(_piece(extension))
    if to_type:
        parts.extend(("to", _piece(to_type)))
    if to_extension:
        parts.extend(("to", _piece(to_extension)))
    if index is not None:
        parts.append(f"idx{index}")
    for key, value in sorted((attrs or {}).items()):
        parts.extend((_piece(key), _piece(value)))
    if case_id:
        parts.append(_piece(case_id))
    else:
        parts.extend(_piece(tag) for tag in tags)
    return "_".join(part for part in parts if part)


def infer_test_lane_count(
    *,
    shape: SignatureShape | None,
    inputs: tuple[TestArg, ...],
    expected: tuple[str, ...],
    explicit_lane_count: int | None = None,
    has_target_axis: bool = False,
) -> int | None:
    """Infer the source vector lane count for one test case.

    The common case is a vector result whose expected list length is the lane count. For
    representation-changing tests the source vector length is authoritative instead; for
    mask-only/scalar-only cases a source ``lane_count`` may still be required.
    """

    if explicit_lane_count is not None:
        return explicit_lane_count
    vector_lengths = tuple(len(arg.values) for arg in inputs if arg.kind == "vector")
    if has_target_axis:
        return _unique_length(vector_lengths)
    if shape is None:
        return _unique_length(vector_lengths)
    if shape.result_kind in {"v", "m", "s[]"} and len(expected) > 1:
        return len(expected)
    if shape.result_kind in {"s", "void"}:
        return _unique_length(vector_lengths)
    return _unique_length(vector_lengths)


def _unique_length(lengths: tuple[int, ...]) -> int | None:
    non_zero = {length for length in lengths if length > 0}
    if len(non_zero) == 1:
        return next(iter(non_zero))
    return None


def _piece(value: str) -> str:
    stripped = value.strip().strip('"')
    return "".join(char if char.isalnum() else "_" for char in stripped).strip("_")


__all__ = ("derive_test_case_name", "infer_test_lane_count")
