from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import ClassVar

from tslgen.analysis.candidates import CandidateSelection, ImplementationCandidate
from tslgen.core.diagnostics import Diagnostic, sort_diagnostics
from tslgen.core.frozen_map import FrozenMap
from tslgen.core.result import Result
from tslgen.domain.catalog import Catalog
from tslgen.io.artifacts import (
    ArtifactDescriptor,
    ArtifactPlan,
    artifact_plan_from_descriptors,
)
from tslgen.testgen.declarations import (
    ProductionTestDeclaration,
    normalize_test_declarations,
)


@dataclass(frozen=True, slots=True)
class TestSourcePlanningRequest:
    __test__: ClassVar[bool] = False

    backend_id: str
    primitive_names: tuple[str, ...] = ()
    test_names: tuple[str, ...] = ()
    artifact_kind: str = "production_tests"
    logical_path: PurePosixPath = PurePosixPath("tests/production_tests.plan")

    def __post_init__(self) -> None:
        if not self.backend_id:
            raise ValueError("test-source planning backend id must be non-empty")
        if not self.artifact_kind:
            raise ValueError("test-source artifact kind must be non-empty")
        object.__setattr__(self, "primitive_names", tuple(self.primitive_names))
        object.__setattr__(self, "test_names", tuple(self.test_names))
        object.__setattr__(self, "logical_path", PurePosixPath(self.logical_path))


@dataclass(frozen=True, slots=True)
class PlannedTestCase:
    declaration: ProductionTestDeclaration
    candidate_id: str
    backend_id: str
    target_extension: str
    source_extension: str
    type_tag: str

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("planned test case candidate id must be non-empty")
        if not self.backend_id:
            raise ValueError("planned test case backend id must be non-empty")
        if not self.target_extension:
            raise ValueError("planned test case target extension must be non-empty")
        if not self.type_tag:
            raise ValueError("planned test case type tag must be non-empty")

    @property
    def test_case_id(self) -> str:
        return (
            f"{self.declaration.primitive_name}:{self.declaration.test_name}:"
            f"{self.candidate_id}"
        )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.declaration.primitive_name,
            self.declaration.test_name,
            self.backend_id,
            self.target_extension,
            self.source_extension,
            self.type_tag,
            self.candidate_id,
        )


@dataclass(frozen=True, slots=True)
class TestSourcePlan:
    __test__: ClassVar[bool] = False

    request: TestSourcePlanningRequest
    declarations: tuple[ProductionTestDeclaration, ...]
    test_cases: tuple[PlannedTestCase, ...]
    artifact_plan: ArtifactPlan
    descriptors: tuple[ArtifactDescriptor, ...] = field(init=False)

    def __post_init__(self) -> None:
        declarations = tuple(sorted(self.declarations, key=lambda item: item.key))
        test_cases = tuple(sorted(self.test_cases, key=lambda item: item.key))
        object.__setattr__(self, "declarations", declarations)
        object.__setattr__(self, "test_cases", test_cases)
        object.__setattr__(self, "descriptors", self.artifact_plan.descriptors)


def plan_test_sources(
    catalog: Catalog,
    selection: CandidateSelection,
    request: TestSourcePlanningRequest,
) -> Result[TestSourcePlan]:
    declarations = normalize_test_declarations(catalog)
    if not declarations.is_ok:
        return Result.failure(declarations.diagnostics)
    return plan_test_sources_for_declarations(
        catalog,
        selection,
        declarations.unwrap(),
        request,
    )


def plan_test_sources_for_declarations(
    catalog: Catalog,
    selection: CandidateSelection,
    declarations: Iterable[ProductionTestDeclaration],
    request: TestSourcePlanningRequest,
) -> Result[TestSourcePlan]:
    diagnostics: list[Diagnostic] = []
    declaration_tuple = tuple(sorted(declarations, key=lambda item: item.key))
    _validate_requested_primitives(catalog, request, diagnostics)
    _validate_declaration_primitives(catalog, declaration_tuple, diagnostics)

    selected_declarations = tuple(
        declaration
        for declaration in declaration_tuple
        if _request_matches_declaration(request, declaration)
    )
    test_cases = _planned_cases(selection, request, selected_declarations)
    descriptor = _test_descriptor(request, test_cases)
    descriptors = () if descriptor is None else (descriptor,)
    artifact_plan = artifact_plan_from_descriptors(
        request.backend_id,
        descriptors,
        metadata=FrozenMap(
            {
                "artifact_role": "production_test_sources",
                "backend_id": request.backend_id,
                "descriptor_count": len(descriptors),
                "planned_test_count": len(test_cases),
            }
        ),
    )
    diagnostics.extend(artifact_plan.diagnostics)

    ordered = sort_diagnostics(diagnostics)
    if any(diagnostic.is_error for diagnostic in ordered):
        return Result.failure(ordered)
    if not artifact_plan.is_ok:
        return Result.failure(ordered)

    return Result.ok(
        TestSourcePlan(
            request=request,
            declarations=selected_declarations,
            test_cases=test_cases,
            artifact_plan=artifact_plan.unwrap(),
        ),
        ordered,
    )


def _planned_cases(
    selection: CandidateSelection,
    request: TestSourcePlanningRequest,
    declarations: tuple[ProductionTestDeclaration, ...],
) -> tuple[PlannedTestCase, ...]:
    cases: list[PlannedTestCase] = []
    for declaration in declarations:
        for candidate in selection.candidates:
            if _candidate_matches_declaration(candidate, declaration, request):
                cases.append(
                    PlannedTestCase(
                        declaration=declaration,
                        candidate_id=candidate.candidate_id,
                        backend_id=request.backend_id,
                        target_extension=candidate.target_extension,
                        source_extension=candidate.source_extension,
                        type_tag=candidate.type_tag,
                    )
                )
    return tuple(sorted(cases, key=lambda item: item.key))


def _candidate_matches_declaration(
    candidate: ImplementationCandidate,
    declaration: ProductionTestDeclaration,
    request: TestSourcePlanningRequest,
) -> bool:
    if candidate.backend is not None and candidate.backend != request.backend_id:
        return False
    if candidate.source_primitive_name != declaration.primitive_name:
        return False
    if candidate.type_tag != declaration.type_tag:
        return False
    if (
        declaration.extension_name is not None
        and candidate.target_extension != declaration.extension_name
    ):
        return False
    return _attributes_match(candidate, declaration)


def _attributes_match(
    candidate: ImplementationCandidate,
    declaration: ProductionTestDeclaration,
) -> bool:
    for key, expected_value in declaration.attributes.items():
        if candidate.variant.attributes.get(key) != expected_value:
            return False
    return True


def _test_descriptor(
    request: TestSourcePlanningRequest,
    test_cases: tuple[PlannedTestCase, ...],
) -> ArtifactDescriptor | None:
    if not test_cases:
        return None
    candidate_ids = tuple(sorted({case.candidate_id for case in test_cases}))
    primitive_names = tuple(
        sorted({case.declaration.primitive_name for case in test_cases})
    )
    test_names = tuple(sorted({case.declaration.test_name for case in test_cases}))
    test_case_ids = tuple(case.test_case_id for case in test_cases)
    return ArtifactDescriptor(
        backend_id=request.backend_id,
        kind=request.artifact_kind,
        logical_path=request.logical_path,
        candidate_ids=candidate_ids,
        metadata=FrozenMap(
            {
                "artifact_role": "production_test_sources",
                "backend_id": request.backend_id,
                "primitive_names": primitive_names,
                "test_case_ids": test_case_ids,
                "test_count": len(test_cases),
                "test_names": test_names,
            }
        ),
    )


def _request_matches_declaration(
    request: TestSourcePlanningRequest,
    declaration: ProductionTestDeclaration,
) -> bool:
    requested_primitives = frozenset(request.primitive_names)
    requested_tests = frozenset(request.test_names)
    if requested_primitives and declaration.primitive_name not in requested_primitives:
        return False
    return not requested_tests or declaration.test_name in requested_tests


def _validate_requested_primitives(
    catalog: Catalog,
    request: TestSourcePlanningRequest,
    diagnostics: list[Diagnostic],
) -> None:
    for primitive_name in sorted(frozenset(request.primitive_names)):
        if not catalog.primitive_declarations(primitive_name):
            diagnostics.append(
                Diagnostic.error(
                    "TSL-TEST-PLAN-UNKNOWN-PRIMITIVE",
                    f"test-source planning request references unknown primitive "
                    f"{primitive_name!r}",
                )
            )


def _validate_declaration_primitives(
    catalog: Catalog,
    declarations: tuple[ProductionTestDeclaration, ...],
    diagnostics: list[Diagnostic],
) -> None:
    for declaration in declarations:
        if catalog.primitive_declarations(declaration.primitive_name):
            continue
        diagnostics.append(
            Diagnostic.error(
                "TSL-TEST-PLAN-UNKNOWN-PRIMITIVE",
                f"test declaration {declaration.test_name!r} references unknown "
                f"primitive {declaration.primitive_name!r}",
                location=declaration.source_location,
            )
        )
