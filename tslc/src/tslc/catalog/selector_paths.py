"""One compiler-owned interpretation of implementation selector paths.

An implementation selector path is the sequence of selector-entry keys from an
``impls:`` tree down to one entry, e.g. ``("[avx512, avx2, sse]", "f?",
"ToBase", "==")``. This module owns what each level *means*, so catalog
promotion, catalog indexing, and editor features share one classification
instead of re-guessing the syntax by nesting depth:

- level 0 names one extension, or a bracketed extension list whose elements
  each name an extension;
- the first later level matching the primitive's declared result-target name
  (its ``return_type`` selector, e.g. ``ToBase``/``ToExtension``) is the
  target axis;
- the level directly after the target axis names the concrete target, unless
  it is the literal ``where``, which introduces a constraint clause and never
  references a type group or extension;
- every other level references a source type-group.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

WHERE_KEYWORD = "where"

SelectorLevelKind = Literal[
    "extensions",
    "source-type-group",
    "target-axis",
    "target-reference",
    "where-constraint",
]


@dataclass(frozen=True, slots=True)
class SelectorPathLevel:
    """One classified selector-path level.

    ``names`` holds the individual referenced names: the split elements for a
    bracketed extension-list head, the single referenced name otherwise, and
    nothing for a ``where`` constraint level (the keyword references no
    catalog symbol).
    """

    kind: SelectorLevelKind
    text: str
    names: tuple[str, ...]


def selector_head_extensions(head: str) -> tuple[str, ...]:
    """The extension names referenced by a selector head.

    A bracketed head such as ``[sse, avx2]`` names each listed extension; any
    other head names exactly one extension.
    """

    head = head.strip()
    if head.startswith("[") and head.endswith("]"):
        return tuple(name.strip() for name in head[1:-1].split(",") if name.strip())
    return (head,)


def classify_selector_path(
    selector_path: tuple[str, ...],
    target_name: str | None,
) -> tuple[SelectorPathLevel, ...]:
    """Classify every level of one selector path.

    ``target_name`` is the primitive's declared result-target selector name
    (``None`` for primitives without a target axis). The head level is always
    the extension level, so a target axis is only recognized at level 1 or
    deeper.
    """

    marker = _target_marker(selector_path, target_name)
    levels: list[SelectorPathLevel] = []
    for position, text in enumerate(selector_path):
        if position == 0:
            levels.append(
                SelectorPathLevel("extensions", text, selector_head_extensions(text))
            )
        elif marker is not None and position == marker:
            levels.append(SelectorPathLevel("target-axis", text, (text,)))
        elif marker is not None and position == marker + 1 and text == WHERE_KEYWORD:
            levels.append(SelectorPathLevel("where-constraint", text, ()))
        elif marker is not None and position == marker + 1:
            levels.append(SelectorPathLevel("target-reference", text, (text,)))
        elif marker is not None and position > marker + 1:
            # Constraint/grouping refinements below the target reference do
            # not reference source type-groups.
            levels.append(SelectorPathLevel("where-constraint", text, ()))
        else:
            levels.append(SelectorPathLevel("source-type-group", text, (text,)))
    return tuple(levels)


def split_target_selector(
    selector_path: tuple[str, ...],
    target_name: str | None,
) -> tuple[str, str | None]:
    """The source type-group and optional concrete-target reference of a path.

    Promotion keys each implementation body by the innermost source
    type-group level (the level before the target axis for target-bearing
    paths, the last level otherwise) and by the concrete target reference, if
    the path names one (``where`` constraint levels name no target).
    """

    levels = classify_selector_path(selector_path, target_name)
    source = ""
    target: str | None = None
    for level in levels:
        if level.kind == "source-type-group":
            source = level.text
        elif level.kind == "target-reference":
            target = level.text
    if not source and levels and all(
        level.kind == "extensions" for level in levels
    ):
        # A body directly under the extension head has no type-group level;
        # promotion historically keys it by the head text.
        source = levels[-1].text
    return source, target


def _target_marker(
    selector_path: tuple[str, ...], target_name: str | None
) -> int | None:
    if target_name is None:
        return None
    for position, text in enumerate(selector_path):
        if position >= 1 and text == target_name:
            return position
    return None


__all__ = (
    "SelectorLevelKind",
    "SelectorPathLevel",
    "WHERE_KEYWORD",
    "classify_selector_path",
    "selector_head_extensions",
    "split_target_selector",
)
