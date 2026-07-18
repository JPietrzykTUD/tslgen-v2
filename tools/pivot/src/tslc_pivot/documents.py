"""Assemble deterministic PIVOT documents and their body evidence."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.scalar_types import SCALAR_TYPE_ORDER
from tslc.diagnostics import Diagnostic
from tslc.select.selector import SelectedImplementation
from tslc_pivot.body_ir import (
    PivotBodyBuildResult,
    PivotBodyCategory,
    PivotBodyCensus,
    PivotBodyEntry,
    PivotBodyOrigin,
    classify_body_trace,
    pivot_body_trace_semantic_digest,
)
from tslc_pivot.model import PivotDefinition, PivotDocument, PivotLanguage, PivotSkip


_OUTPUT_NAME = "res"
_DTYPE = {
    "si8": "int8",
    "si16": "int16",
    "si32": "int32",
    "si64": "int64",
    "ui8": "uint8",
    "ui16": "uint16",
    "ui32": "uint32",
    "ui64": "uint64",
    "f32": "float32",
    "f64": "float64",
}


@dataclass(frozen=True, slots=True)
class PlannedDefinition:
    definition: PivotDefinition
    body: PivotBodyBuildResult
    origin: PivotBodyOrigin
    category: PivotBodyCategory | None
    semantic_digest: str
    inlined_bodies: tuple[PivotBodyBuildResult, ...] = ()


@dataclass(frozen=True, slots=True)
class PivotDocumentPlan:
    documents: tuple[PivotDocument, ...]
    skipped: tuple[PivotSkip, ...]
    body_census: PivotBodyCensus
    diagnostics: tuple[Diagnostic, ...]


class PivotDocumentAssembly:
    """Own schema conflicts, definition deduplication, and body association."""

    def __init__(self, language: PivotLanguage) -> None:
        self.language = language
        self._documents: dict[
            str,
            tuple[tuple[str, ...], dict[PivotDefinition, PlannedDefinition]],
        ] = {}
        self._skipped: dict[tuple[object, ...], PivotSkip] = {}
        self._diagnostics: list[Diagnostic] = []

    def record_skip(self, skip: PivotSkip) -> None:
        self._skipped.setdefault(_skip_identity(skip), skip)

    def add_candidates(
        self,
        profile: MachineProfile,
        slot: SelectedImplementation,
        callable_name: str,
        candidates: tuple[PlannedDefinition, ...],
    ) -> None:
        if not candidates:
            return
        inputs = tuple(slot.primitive.parameters)
        existing = self._documents.get(callable_name)
        if existing is not None and existing[0] != inputs:
            self.record_skip(
                PivotSkip(
                    language=self.language,
                    profile=profile.name,
                    primitive=callable_name,
                    extension=slot.extension.isa_name,
                    type_tag=slot.type_tag,
                    reason=(
                        "PIVOT schema cannot combine callable overloads with "
                        "different input names"
                    ),
                    source=slot.primitive.signature_source,
                )
            )
            return
        if existing is None:
            definitions: dict[PivotDefinition, PlannedDefinition] = {}
            self._documents[callable_name] = (inputs, definitions)
        else:
            definitions = existing[1]
        for candidate in candidates:
            previous = definitions.get(candidate.definition)
            if (
                previous is not None
                and previous.semantic_digest != candidate.semantic_digest
            ):
                self._diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code="TSL-PIVOT-BODY-DEFINITION-CONFLICT",
                        message=(
                            "the same emitted PIVOT definition has different "
                            "body facts"
                        ),
                        span=slot.implementation.body_source,
                    )
                )
                continue
            definitions.setdefault(candidate.definition, candidate)

    def finish(self) -> PivotDocumentPlan:
        documents = tuple(
            PivotDocument(
                name=name,
                inputs=inputs,
                output=_OUTPUT_NAME,
                definitions=tuple(sorted(definitions, key=_definition_key)),
            )
            for name, (inputs, definitions) in sorted(self._documents.items())
            if definitions
        )
        return PivotDocumentPlan(
            documents=documents,
            skipped=tuple(sorted(self._skipped.values(), key=_skip_key)),
            body_census=_body_census(self.language, documents, self._documents),
            diagnostics=tuple(self._diagnostics),
        )


def planned_definition(
    definition: PivotDefinition,
    body_result: PivotBodyBuildResult,
    *,
    origin: PivotBodyOrigin = PivotBodyOrigin.LOWERED_SOURCE,
    category: PivotBodyCategory | None = None,
    inlined_bodies: tuple[PivotBodyBuildResult, ...] = (),
) -> PlannedDefinition:
    body = body_result.body
    failed = body is None or any(result.body is None for result in inlined_bodies)
    return PlannedDefinition(
        definition=definition,
        body=body_result,
        origin=origin,
        category=(
            None
            if failed or body is None
            else category or classify_body_trace(body, inlined_bodies)
        ),
        semantic_digest=pivot_body_trace_semantic_digest(
            body_result,
            inlined_bodies,
        ),
        inlined_bodies=inlined_bodies,
    )


def pivot_dtype(type_tag: str) -> str:
    return _DTYPE.get(type_tag, type_tag)


def _body_census(
    language: PivotLanguage,
    planned_documents: tuple[PivotDocument, ...],
    candidates: dict[
        str,
        tuple[tuple[str, ...], dict[PivotDefinition, PlannedDefinition]],
    ],
) -> PivotBodyCensus:
    occurrences: dict[tuple[object, ...], int] = {}
    entries: list[PivotBodyEntry] = []
    for document in planned_documents:
        by_definition = candidates[document.name][1]
        for definition in document.definitions:
            key = (
                document.name,
                definition.isa,
                definition.dtype,
                definition.signature,
            )
            occurrence = occurrences.get(key, 0)
            occurrences[key] = occurrence + 1
            candidate = by_definition[definition]
            entries.append(
                PivotBodyEntry(
                    document=document.name,
                    definition=definition,
                    occurrence=occurrence,
                    origin=candidate.origin,
                    category=candidate.category,
                    body=candidate.body,
                    inlined_bodies=candidate.inlined_bodies,
                )
            )
    return PivotBodyCensus(language, tuple(entries))


def _definition_key(definition: PivotDefinition) -> tuple[object, ...]:
    return (
        definition.isa,
        _dtype_order(definition.dtype),
        definition.dtype,
        definition.signature,
        definition.direct,
    )


def _dtype_order(dtype: str) -> int:
    for type_tag, name in _DTYPE.items():
        if name == dtype:
            return SCALAR_TYPE_ORDER.get(type_tag, 99)
    return 99


def _skip_key(skip: PivotSkip) -> tuple[object, ...]:
    source = skip.source
    return (
        skip.language.value,
        skip.primitive,
        skip.profile,
        skip.extension,
        SCALAR_TYPE_ORDER.get(skip.type_tag, 99),
        skip.type_tag,
        skip.reason,
        source.path.as_posix() if source is not None else "",
        source.line if source is not None else 0,
    )


def _skip_identity(skip: PivotSkip) -> tuple[object, ...]:
    """Identify one unsupported specialization independent of profile aliases."""

    return (
        skip.language.value,
        skip.primitive,
        skip.extension,
        skip.type_tag,
        skip.reason,
        skip.source,
    )


__all__ = (
    "PivotDocumentAssembly",
    "PivotDocumentPlan",
    "PlannedDefinition",
    "pivot_dtype",
    "planned_definition",
)
