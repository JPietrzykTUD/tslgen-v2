from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Self

from tslgen.core.frozen_map import FrozenMap
from tslgen.domain.signatures import Signature, parse_signature
from tslgen.domain.values import CatalogValue


type ConditionValue = str | bool


@dataclass(frozen=True, slots=True)
class AttributeCondition:
    key: str
    value: ConditionValue

    def __post_init__(self) -> None:
        if not self.key:
            raise ValueError("attribute condition key must be non-empty")

    def matches(self, attributes: Mapping[str, CatalogValue]) -> bool:
        return attributes.get(self.key) == self.value


@dataclass(frozen=True, slots=True)
class SignatureCase:
    template: str
    conditions: tuple[AttributeCondition, ...] = ()

    def __post_init__(self) -> None:
        if not self.template:
            raise ValueError("signature case template must be non-empty")
        object.__setattr__(self, "conditions", tuple(self.conditions))

    def matches(self, attributes: Mapping[str, CatalogValue]) -> bool:
        return all(condition.matches(attributes) for condition in self.conditions)


@dataclass(frozen=True, slots=True)
class SignatureRule:
    signature: Signature
    cases: tuple[SignatureCase, ...]

    def __post_init__(self) -> None:
        if not self.cases:
            raise ValueError("signature rule must have at least one case")
        object.__setattr__(self, "cases", tuple(self.cases))


@dataclass(frozen=True, slots=True)
class TemplateResolution:
    signature: Signature
    template_name: str
    conditions: tuple[AttributeCondition, ...]


def resolve_template(
    signature: Signature,
    attributes: Mapping[str, CatalogValue],
) -> TemplateResolution | None:
    rule = rule_for_signature(signature)
    if rule is None:
        return None
    for case in rule.cases:
        if case.matches(attributes):
            return TemplateResolution(
                signature=signature,
                template_name=case.template,
                conditions=case.conditions,
            )
    return None


def rule_for_signature(signature: Signature) -> SignatureRule | None:
    return _RULES_BY_SIGNATURE.get(signature.normalized)


def candidate_template_names(signature: Signature) -> frozenset[str]:
    rule = rule_for_signature(signature)
    if rule is None:
        return frozenset()
    return frozenset(case.template for case in rule.cases)


def condition_attribute_keys(signature: Signature) -> frozenset[str]:
    rule = rule_for_signature(signature)
    if rule is None:
        return frozenset()
    return frozenset(
        condition.key for case in rule.cases for condition in case.conditions
    )


def condition_values_for_attribute(
    signature: Signature,
    attribute_name: str,
) -> frozenset[ConditionValue]:
    rule = rule_for_signature(signature)
    if rule is None:
        return frozenset()
    return frozenset(
        condition.value
        for case in rule.cases
        for condition in case.conditions
        if condition.key == attribute_name
    )


def _rule(signature: str, *cases: SignatureCase) -> SignatureRule:
    parsed = parse_signature(signature)
    if not parsed.is_ok:
        raise ValueError(f"invalid built-in signature rule {signature!r}")
    return SignatureRule(parsed.unwrap(), cases)


def _case(template: str, **conditions: ConditionValue) -> SignatureCase:
    return SignatureCase(
        template=template,
        conditions=tuple(
            AttributeCondition(key=key, value=value)
            for key, value in conditions.items()
        ),
    )


def _rule_map(rules: tuple[SignatureRule, ...]) -> FrozenMap[str, SignatureRule]:
    return FrozenMap((rule.signature.normalized, rule) for rule in rules)


class _RuleListBuilder:
    def __init__(self) -> None:
        self._rules: list[SignatureRule] = []

    def add(self, signature: str, *cases: SignatureCase) -> Self:
        self._rules.append(_rule(signature, *cases))
        return self

    def build(self) -> tuple[SignatureRule, ...]:
        return tuple(self._rules)


DEFAULT_SIGNATURE_RULES: tuple[SignatureRule, ...] = (
    _RuleListBuilder()
    .add("v:=(v,v)", _case("binary"))
    .add("v:=(v,v,sImm)", _case("insert", cast="reinterpret"))
    .add("m:=(v,v)", _case("compare"))
    .add("v:=(m,v,v)", _case("masked_binary"))
    .add("v:=(m,v,v,v)", _case("masked_ternary"))
    .add("m:=(m,v,v)", _case("masked_compare"))
    .add(
        "m:=(m,v,v,v)",
        _case("masked_between", mask="zero"),
        _case("masked_between", mask="pass_through"),
        _case("masked_between"),
    )
    .add(
        "v:=v",
        _case("convert", cast="convert"),
        _case("reinterpret", cast="reinterpret"),
        _case("unary"),
    )
    .add(
        "v:=(m,v)",
        _case("masked_unary", mask="pass_through"),
        _case("expand", mask="zero", op="expand"),
        _case("pack", mask="zero", op="pack"),
        _case("masked_unary", mask="zero", op="keep"),
        _case("masked_unary", mask="zero"),
    )
    .add("s:=m", _case("mask_to_scalar"))
    .add("m:=s", _case("scalar_to_mask"))
    .add("v:=m", _case("mask_to_vector"))
    .add("m:=(m,m)", _case("mask_binary"))
    .add("m:=()", _case("mask_set", value="zero"), _case("mask_set", value="all"))
    .add("m:=v", _case("compare_zero", value="zero"))
    .add("m:=(v,v,v)", _case("between_inclusive"))
    .add("s:=(v,s)", _case("binary_scalar_reduce"))
    .add("s:=s", _case("unary_scalar"))
    .add("m:=m", _case("mask_unary"))
    .add("v:=(m,v,s)", _case("masked_binary_scalar"))
    .add("s:=(s,s)", _case("imask_binary"))
    .add("s:=(s,s,s)", _case("imask_ternary"))
    .add("m:=(m,s)", _case("binary_scalar_imask"))
    .add("m:=(m,v)", _case("masked_reduce"))
    .add("s:=v", _case("reduce"))
    .add("s:=(m,v)", _case("masked_reduce_scalar"))
    .add("v:=s", _case("set1"))
    .add("v:=s...", _case("set"))
    .add(
        "v:=()",
        _case("set_undef", value="undef"),
        _case("set_zero", value="zero"),
        _case("set_zero"),
    )
    .add("v:=ptr", _case("load"))
    .add("m:=ptr", _case("load_mask"))
    .add("s:=ptr", _case("load_scalar"))
    .add("void:=(ptr,v)", _case("store"))
    .add("void:=(ptr,m)", _case("store_mask"))
    .add("void:=(ptr,s)", _case("store_scalar"))
    .add("v:=(m,ptr)", _case("expand_load", op="expand"), _case("masked_load"))
    .add(
        "v:=(m,ptr,v)",
        _case("expand_load_merge", op="expand"),
        _case("masked_load_merge"),
    )
    .add("void:=(m,ptr,v)", _case("compress_store", op="pack"), _case("masked_store"))
    .add("v:=(ptr,vidx,sImm)", _case("gather"))
    .add("v:=(m,ptr,vidx,sImm)", _case("masked_gather"))
    .add("v:=(m,ptr,vidx,v,sImm)", _case("masked_gather_merge"))
    .add("void:=(ptr,vidx,v,sImm)", _case("scatter"))
    .add("void:=(m,ptr,vidx,v,sImm)", _case("masked_scatter"))
    .add("s[]:=v", _case("to_array"))
    .add("v:=s[]", _case("from_array"))
    .add("s:=v[idx]", _case("extract_value"))
    .add("v:=sequence", _case("sequence"))
    .add("v:=(s,s)", _case("custom_sequence"))
    .add("v:=ptr+", _case("load_convert_up"))
    .add("v:=(v,v,vidx)", _case("shuffle"))
    .add(
        "v:=(v,sImm)",
        _case("convert_up", cast="convert", direction="up"),
        _case("convert_down", cast="convert", direction="down"),
        _case("extract", cast="reinterpret"),
        _case("binary_scalar"),
    )
    .add("v:=(v,s)", _case("extract", cast="reinterpret"), _case("binary_scalar"))
    .add("v:=(m,v,sImm)", _case("masked_binary_scalar"))
    .add("ptr:=(s)", _case("alloc"))
    .add("ptr:=(s,s)", _case("alloc_aligned"))
    .add("void:=(ptr)", _case("dealloc"))
    .add("void:=(ptr,ptr,s,s)", _case("memcpy"))
    .add("o:=(o,v,s)", _case("ostream"))
    .build()
)

_RULES_BY_SIGNATURE = _rule_map(DEFAULT_SIGNATURE_RULES)
