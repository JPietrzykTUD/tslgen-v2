"""Stateful target-support tracing for one generation request."""

from __future__ import annotations

from tslc.lower.implementation_facts import ImplementationState
from tslc.select.selector import (
    SelectionSlotDisposition,
    SelectionSlotResult,
    SelectedImplementation,
)
from tslc.target_support import (
    TargetSupportEntry,
    TargetSupportKey,
    TargetSupportRealizationKey,
    TargetSupportStatus,
    TargetSupportTrace,
    realization_key,
    target_support_key,
)

TargetSupportIdentity = tuple[TargetSupportKey, TargetSupportRealizationKey]

_ALLOWED_TRANSITIONS = {
    TargetSupportStatus.SELECTED: frozenset(
        {
            TargetSupportStatus.SELECTED,
            TargetSupportStatus.LOWERED,
            TargetSupportStatus.POLICY_DEFERRED,
        }
    ),
    TargetSupportStatus.LOWERED: frozenset(
        {TargetSupportStatus.PRUNED, TargetSupportStatus.EMITTED}
    ),
}


class TargetSupportRecorder:
    """Own target-support entries and their valid generation-stage transitions."""

    def __init__(self, *, enabled: bool) -> None:
        self._entries: (
            dict[
                tuple[TargetSupportKey, TargetSupportRealizationKey | None],
                TargetSupportEntry,
            ]
            | None
        ) = {} if enabled else None
        self._lowered: dict[int, TargetSupportIdentity] | None = (
            {} if enabled else None
        )

    @property
    def enabled(self) -> bool:
        return self._entries is not None

    def trace(self) -> TargetSupportTrace | None:
        if self._entries is None:
            return None
        return TargetSupportTrace(
            entries=tuple(
                sorted(self._entries.values(), key=TargetSupportEntry.sort_key)
            )
        )

    def record_selection(
        self,
        profile: str,
        backend: str,
        slots: tuple[SelectionSlotResult, ...],
        extensions: tuple[str, ...] | None,
    ) -> None:
        if self._entries is None:
            return
        for slot in slots:
            if (
                extensions is not None
                and slot.extension.name not in extensions
                and slot.extension.isa_name not in extensions
            ):
                continue
            key = target_support_key(
                profile,
                backend,
                slot.primitive,
                slot.extension.name,
                slot.type_tag,
                slot.to_target,
            )
            if slot.disposition is SelectionSlotDisposition.FIXED_SHAPE_ONLY:
                self._entries[(key, None)] = TargetSupportEntry(
                    key=key,
                    realization=None,
                    status=TargetSupportStatus.POLICY_DEFERRED,
                    reason_id="TSL-SELECT-FIXED-SHAPE-ONLY",
                )
                continue
            if slot.disposition is SelectionSlotDisposition.NOT_APPLICABLE:
                assert slot.inapplicability_reason is not None
                self._entries[(key, None)] = TargetSupportEntry(
                    key=key,
                    realization=None,
                    status=TargetSupportStatus.NOT_APPLICABLE,
                    reason_id=slot.inapplicability_reason.value,
                )
                continue
            if not slot.selected:
                self._entries[(key, None)] = TargetSupportEntry(
                    key=key,
                    realization=None,
                    status=TargetSupportStatus.ABSENT,
                    reason_id="TSL-SELECT-NO-CANDIDATE",
                )
                continue
            self._entries.pop((key, None), None)
            for selected in slot.selected:
                realization = realization_key(selected)
                identity = (key, realization)
                self._entries[identity] = TargetSupportEntry(
                    key=key,
                    realization=realization,
                    status=TargetSupportStatus.SELECTED,
                )

    def identity(
        self,
        profile: str,
        backend: str,
        selected: SelectedImplementation,
    ) -> TargetSupportIdentity | None:
        if self._entries is None:
            return None
        return (
            target_support_key(
                profile,
                backend,
                selected.primitive,
                selected.extension.name,
                selected.type_tag,
                selected.to_target,
            ),
            realization_key(selected),
        )

    def mark_lowering_failed(
        self,
        identity: TargetSupportIdentity | None,
        *,
        policy_deferred: bool,
        reason_id: str,
    ) -> None:
        self._advance(
            identity,
            (
                TargetSupportStatus.POLICY_DEFERRED
                if policy_deferred
                else TargetSupportStatus.SELECTED
            ),
            reason_id=reason_id,
        )

    def mark_lowered(self, identity: TargetSupportIdentity | None) -> None:
        self._advance(identity, TargetSupportStatus.LOWERED)

    def remember_lowered(
        self,
        slot: object,
        identity: TargetSupportIdentity | None,
    ) -> None:
        if self._lowered is not None and identity is not None:
            self._lowered[id(slot)] = identity

    def mark_pruned(self, slot: object, *, reason_id: str) -> None:
        self._advance(
            self._remembered_identity(slot),
            TargetSupportStatus.PRUNED,
            reason_id=reason_id,
        )

    def mark_emitted(
        self,
        slot: object,
        *,
        implementation_state: ImplementationState,
    ) -> None:
        self._advance(
            self._remembered_identity(slot),
            TargetSupportStatus.EMITTED,
            implementation_state=implementation_state,
        )

    def _remembered_identity(
        self,
        slot: object,
    ) -> TargetSupportIdentity | None:
        return None if self._lowered is None else self._lowered.get(id(slot))

    def _advance(
        self,
        identity: TargetSupportIdentity | None,
        status: TargetSupportStatus,
        *,
        reason_id: str | None = None,
        implementation_state: ImplementationState | None = None,
    ) -> None:
        if identity is None:
            return
        assert self._entries is not None
        current = self._entries.get(identity)
        if current is None:
            raise ValueError("target-support transition has no selected realization")
        allowed = _ALLOWED_TRANSITIONS.get(current.status, frozenset())
        if status not in allowed:
            raise ValueError(
                "invalid target-support transition "
                f"{current.status.value!r} -> {status.value!r}"
            )
        key, realization = identity
        self._entries[identity] = TargetSupportEntry(
            key=key,
            realization=realization,
            status=status,
            reason_id=reason_id,
            implementation_state=implementation_state,
        )


__all__ = ("TargetSupportIdentity", "TargetSupportRecorder")
