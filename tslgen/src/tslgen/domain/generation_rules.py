from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Literal

from tslgen.core.diagnostics import (
    Diagnostic,
    SourceLocation,
    has_errors,
    sort_diagnostics,
)
from tslgen.core.frozen_map import FrozenMap
from tslgen.core.ordering import stable_sorted
from tslgen.core.result import Result
from tslgen.domain.types import TypeGroup


type ConcreteIntegerGenerationTagStatus = Literal["selected", "unsupported", "unknown"]

SELECTED_CONCRETE_INTEGER_GENERATION_TYPE_TAGS: tuple[str, ...] = (
    "si8",
    "ui8",
    "si16",
    "ui16",
    "si32",
    "ui32",
    "si64",
    "ui64",
)
CONCRETE_INTEGER_GENERATION_COMPANION_PAIRS: tuple[tuple[str, str], ...] = (
    ("si8", "ui8"),
    ("si16", "ui16"),
    ("si32", "ui32"),
    ("si64", "ui64"),
)

_SELECTED_TAGS = frozenset(SELECTED_CONCRETE_INTEGER_GENERATION_TYPE_TAGS)
_CONCRETE_INTEGER_TAG_RE = re.compile(r"\A[su]i\d+\Z")
_FLOAT_TAG_RE = re.compile(r"\Af\d+\Z")
_WILDCARD_TYPE_TAG_RE = re.compile(r"\A(?:\?i\?|\?i\d+|[su]i\?|f\?)\Z")
_TYPE_GROUP_TAGS = frozenset(
    {
        "bword",
        "idqword",
        "fdqword",
        "arith",
        "dqword",
        "dword",
        "qword",
    }
)
_NON_INTEGER_TYPE_TAGS = frozenset({"ptr", "mask", "imask"})
_TSDATA_TYPES_LINE_BY_SELECTED_TAG = FrozenMap(
    {
        "si8": 2,
        "si16": 3,
        "si32": 4,
        "si64": 5,
        "ui8": 6,
        "ui16": 7,
        "ui32": 8,
        "ui64": 9,
    }
)


@dataclass(frozen=True, slots=True)
class ConcreteIntegerGenerationTypeRule:
    type_tag: str
    signed_type_tag: str
    unsigned_type_tag: str
    is_signed: bool

    def __post_init__(self) -> None:
        for field_name in ("type_tag", "signed_type_tag", "unsigned_type_tag"):
            if not getattr(self, field_name):
                raise ValueError(f"concrete integer generation {field_name} is required")

    @property
    def key(self) -> tuple[str, str, str, bool]:
        return (
            self.type_tag,
            self.signed_type_tag,
            self.unsigned_type_tag,
            self.is_signed,
        )


@dataclass(frozen=True, slots=True)
class ConcreteIntegerGenerationRuleSet:
    rules: tuple[ConcreteIntegerGenerationTypeRule, ...]
    rules_by_type_tag: FrozenMap[str, ConcreteIntegerGenerationTypeRule] = field(
        init=False
    )

    def __post_init__(self) -> None:
        rules = tuple(
            sorted(
                self.rules,
                key=lambda rule: _selected_tag_sort_key(rule.type_tag),
            )
        )
        object.__setattr__(self, "rules", rules)
        object.__setattr__(
            self,
            "rules_by_type_tag",
            FrozenMap((rule.type_tag, rule) for rule in rules),
        )

    @property
    def supported_type_tags(self) -> tuple[str, ...]:
        return tuple(rule.type_tag for rule in self.rules)

    def rule_for(self, type_tag: str) -> ConcreteIntegerGenerationTypeRule | None:
        return self.rules_by_type_tag.get(type_tag)


def build_concrete_integer_generation_rule_set(
    type_groups: tuple[TypeGroup, ...],
    *,
    selected_type_tags: tuple[str, ...] = SELECTED_CONCRETE_INTEGER_GENERATION_TYPE_TAGS,
) -> Result[ConcreteIntegerGenerationRuleSet]:
    groups_by_name = FrozenMap((group.name, group) for group in type_groups)
    selected_tags = _normalize_selected_tags(selected_type_tags)
    diagnostics: list[Diagnostic] = []

    for type_tag in selected_tags:
        status = classify_concrete_integer_generation_type_tag(type_tag)
        if status == "selected":
            continue
        diagnostics.append(_unsupported_or_unknown_selected_tag_diagnostic(type_tag, status))

    valid_singletons: set[str] = set()
    for type_tag in selected_tags:
        if type_tag not in _SELECTED_TAGS:
            continue
        group = groups_by_name.get(type_tag)
        if group is None:
            diagnostics.append(_missing_singleton_diagnostic(type_tag))
            continue
        if group.members != (type_tag,):
            diagnostics.append(_inconsistent_singleton_diagnostic(group, type_tag))
            continue
        valid_singletons.add(type_tag)

    selected_tag_set = frozenset(selected_tags)
    for signed_tag, unsigned_tag in CONCRETE_INTEGER_GENERATION_COMPANION_PAIRS:
        if not ({signed_tag, unsigned_tag} & selected_tag_set):
            continue
        if signed_tag not in valid_singletons or unsigned_tag not in valid_singletons:
            diagnostics.append(
                _missing_companion_pair_diagnostic(signed_tag, unsigned_tag)
            )

    ordered_diagnostics = sort_diagnostics(diagnostics)
    if has_errors(ordered_diagnostics):
        return Result.failure(ordered_diagnostics)

    rules: list[ConcreteIntegerGenerationTypeRule] = []
    for signed_tag, unsigned_tag in CONCRETE_INTEGER_GENERATION_COMPANION_PAIRS:
        if signed_tag in selected_tag_set:
            rules.append(
                ConcreteIntegerGenerationTypeRule(
                    type_tag=signed_tag,
                    signed_type_tag=signed_tag,
                    unsigned_type_tag=unsigned_tag,
                    is_signed=True,
                )
            )
        if unsigned_tag in selected_tag_set:
            rules.append(
                ConcreteIntegerGenerationTypeRule(
                    type_tag=unsigned_tag,
                    signed_type_tag=signed_tag,
                    unsigned_type_tag=unsigned_tag,
                    is_signed=False,
                )
            )
    return Result.ok(ConcreteIntegerGenerationRuleSet(tuple(rules)))


def default_concrete_integer_generation_rule_set() -> ConcreteIntegerGenerationRuleSet:
    result = build_concrete_integer_generation_rule_set(
        _default_concrete_integer_type_groups()
    )
    if not result.is_ok:
        raise AssertionError(result.diagnostics)
    return result.unwrap()


def classify_concrete_integer_generation_type_tag(
    type_tag: str,
) -> ConcreteIntegerGenerationTagStatus:
    if type_tag in _SELECTED_TAGS:
        return "selected"
    if (
        bool(_CONCRETE_INTEGER_TAG_RE.fullmatch(type_tag))
        or bool(_FLOAT_TAG_RE.fullmatch(type_tag))
        or bool(_WILDCARD_TYPE_TAG_RE.fullmatch(type_tag))
        or type_tag in _TYPE_GROUP_TAGS
        or type_tag in _NON_INTEGER_TYPE_TAGS
    ):
        return "unsupported"
    return "unknown"


def is_non_integer_generation_type_tag(type_tag: str) -> bool:
    return bool(_FLOAT_TAG_RE.fullmatch(type_tag)) or type_tag in _NON_INTEGER_TYPE_TAGS


def _default_concrete_integer_type_groups() -> tuple[TypeGroup, ...]:
    from pathlib import Path

    from tslgen.core.diagnostics import SourceSpan

    return tuple(
        TypeGroup(
            name=type_tag,
            members=(type_tag,),
            fields=FrozenMap({"types": (type_tag,)}),
            source_span=SourceSpan(
                SourceLocation(
                    Path("tsldata/detail/types.tsl"),
                    _TSDATA_TYPES_LINE_BY_SELECTED_TAG[type_tag],
                    3,
                )
            ),
        )
        for type_tag in SELECTED_CONCRETE_INTEGER_GENERATION_TYPE_TAGS
    )


def _normalize_selected_tags(type_tags: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        stable_sorted(
            tuple(dict.fromkeys(type_tags)),
            key=_selected_tag_sort_key,
        )
    )


def _selected_tag_sort_key(type_tag: str) -> tuple[int, int | str]:
    try:
        return (
            0,
            SELECTED_CONCRETE_INTEGER_GENERATION_TYPE_TAGS.index(type_tag),
        )
    except ValueError:
        return (1, type_tag)


def _unsupported_or_unknown_selected_tag_diagnostic(
    type_tag: str,
    status: ConcreteIntegerGenerationTagStatus,
) -> Diagnostic:
    if status == "unknown":
        return Diagnostic.error(
            "TSL-DOMAIN-GEN-RULE-TAG-UNKNOWN",
            "concrete integer generation rule source received unknown selected "
            f"type tag {type_tag!r}",
        )
    return Diagnostic.error(
        "TSL-DOMAIN-GEN-RULE-TAG-UNSUPPORTED",
        "concrete integer generation rule source supports only selected "
        f"singleton tags {_quoted_join(SELECTED_CONCRETE_INTEGER_GENERATION_TYPE_TAGS)}; "
        f"got {type_tag!r}",
    )


def _missing_singleton_diagnostic(type_tag: str) -> Diagnostic:
    return Diagnostic.error(
        "TSL-DOMAIN-GEN-RULE-SINGLETON-MISSING",
        "concrete integer generation rule source requires singleton type group "
        f"{type_tag!r}",
    )


def _inconsistent_singleton_diagnostic(
    group: TypeGroup,
    expected_type_tag: str,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-DOMAIN-GEN-RULE-SINGLETON-INCONSISTENT",
        "concrete integer generation rule source requires type group "
        f"{group.name!r} to contain exactly ({expected_type_tag!r},); got "
        f"{group.members!r}",
        location=group.source_span.location,
    )


def _missing_companion_pair_diagnostic(
    signed_tag: str,
    unsigned_tag: str,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-DOMAIN-GEN-RULE-COMPANION-MISSING",
        "concrete integer generation rule source requires signed/unsigned "
        f"companion pair {signed_tag!r} <-> {unsigned_tag!r}",
    )


def _quoted_join(values: tuple[str, ...]) -> str:
    return ", ".join(repr(value) for value in values)
