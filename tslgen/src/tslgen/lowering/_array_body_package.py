from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.core.result import Result
from tslgen.lowering._array_body_models import (
    ExactArrayBodyEnvelopeIr,
    ExactArrayBodyStructuralRoleLabel,
    ExactArrayBodyStructuralSequenceIr,
    ExactArrayInitializationDeclarationShellIr,
    ExactArrayInitializationHelperSetCompletionIr,
    ExactPostBranchIntrinsicCallSiteStructuralRequestIr,
    ExactPredicatePathStructuralRequestIr,
    ExactReturnEmissionStructuralRequestIr,
)


type ExactArrayBodyStructuralPackageMemberKind = Literal[
    "declaration_shell",
    "predicate_path",
    "selected_update",
    "post_branch_call_site",
    "return_emission",
]
type ExactArrayBodyStructuralPackageMemberFact = (
    ExactArrayInitializationDeclarationShellIr
    | ExactPredicatePathStructuralRequestIr
    | ExactPostBranchIntrinsicCallSiteStructuralRequestIr
    | ExactReturnEmissionStructuralRequestIr
)


class _ArrayBodyPackageGenerationContext(Protocol):
    @property
    def selected_candidate_id(self) -> str | None: ...

    @property
    def selected_type_tag(self) -> str | None: ...


@dataclass(frozen=True, slots=True)
class _DefaultArrayBodyPackageGenerationContext:
    selected_candidate_id: str | None = None
    selected_type_tag: str | None = None


@runtime_checkable
class _ArrayBodyPackageReturnEmissionSource(Protocol):
    @property
    def return_emission_structural_requests(
        self,
    ) -> tuple[ExactReturnEmissionStructuralRequestIr, ...]: ...


@dataclass(frozen=True, slots=True)
class ExactArrayBodyStructuralPackageMember:
    kind: ExactArrayBodyStructuralPackageMemberKind
    role_label: ExactArrayBodyStructuralRoleLabel
    role_ordinal: int
    source_location: SourceLocation
    fact: ExactArrayBodyStructuralPackageMemberFact

    def __post_init__(self) -> None:
        if self.role_ordinal not in (0, 1, 2, 3, 4):
            raise ValueError("array-body package member ordinal is unsupported")
        if self.source_location is None:
            raise ValueError("array-body package member requires source location")
        expected_type: type[object]
        if self.kind == "declaration_shell":
            expected_type = ExactArrayInitializationDeclarationShellIr
        elif self.kind in ("predicate_path", "selected_update"):
            expected_type = ExactPredicatePathStructuralRequestIr
        elif self.kind == "post_branch_call_site":
            expected_type = ExactPostBranchIntrinsicCallSiteStructuralRequestIr
        elif self.kind == "return_emission":
            expected_type = ExactReturnEmissionStructuralRequestIr
        else:
            raise ValueError("array-body package member kind is unsupported")
        if not isinstance(self.fact, expected_type):
            raise TypeError(
                "array-body package member fact type must match its member kind"
            )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "exact_array_body_structural_package_member",
            self.kind,
            self.role_label,
            self.role_ordinal,
            self.source_location.sort_key(),
            self.fact.key,
        )


@dataclass(frozen=True, slots=True)
class ExactArrayBodyStructuralPackageIr:
    source_envelope: ExactArrayBodyEnvelopeIr
    helper_set_completion: ExactArrayInitializationHelperSetCompletionIr
    declaration_shell: ExactArrayInitializationDeclarationShellIr
    source_sequence: ExactArrayBodyStructuralSequenceIr
    predicate_path: ExactPredicatePathStructuralRequestIr
    post_branch_call_site: ExactPostBranchIntrinsicCallSiteStructuralRequestIr
    return_emission: ExactReturnEmissionStructuralRequestIr
    members: tuple[ExactArrayBodyStructuralPackageMember, ...]
    source_location: SourceLocation
    candidate_id: str
    target_extension: str
    source_extension: str
    selected_type_tag: str
    originating_branch_chain_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "members", tuple(self.members))
        _raise_first_package_validation_error(self)

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "exact_array_body_structural_package_ir",
            self.source_envelope.key,
            self.helper_set_completion.key,
            self.declaration_shell.key,
            self.source_sequence.key,
            self.predicate_path.key,
            self.post_branch_call_site.key,
            self.return_emission.key,
            tuple(member.key for member in self.members),
            self.source_location.sort_key(),
            self.candidate_id,
            self.target_extension,
            self.source_extension,
            self.selected_type_tag,
            self.originating_branch_chain_id,
        )


def lower_exact_array_body_structural_package(
    source: object,
    context: _ArrayBodyPackageGenerationContext | None = None,
    *,
    selected_candidate_id: str | None = None,
    target_extension: str | None = None,
    source_extension: str | None = None,
    selected_type_tag: str | None = None,
) -> Result[ExactArrayBodyStructuralPackageIr]:
    source_result = _array_body_package_return_emission_source(source)
    if not source_result.is_ok:
        return Result.failure(source_result.diagnostics)
    return_emission = source_result.unwrap()

    generation_context = context or _DefaultArrayBodyPackageGenerationContext()
    effective_candidate_id = (
        selected_candidate_id
        or generation_context.selected_candidate_id
        or return_emission.candidate_id
    )
    effective_target_extension = target_extension or return_emission.target_extension
    effective_source_extension = source_extension or return_emission.source_extension
    effective_type_tag = (
        selected_type_tag
        or generation_context.selected_type_tag
        or return_emission.selected_type_tag
    )
    if (
        effective_candidate_id != return_emission.candidate_id
        or effective_target_extension != return_emission.target_extension
        or effective_source_extension != return_emission.source_extension
        or effective_type_tag != return_emission.selected_type_tag
    ):
        return Result.failure(
            (
                _array_body_package_context_mismatch_diagnostic(
                    "array-body structural package assembly requires the "
                    "typed selected candidate context to match the M87 "
                    "return-emission request candidate id, target extension, "
                    "source extension, and selected type tag",
                    return_emission.source_location,
                ),
            )
        )

    diagnostics = _validate_return_emission_package_chain(return_emission)
    if diagnostics:
        return Result.failure(diagnostics)

    sequence = return_emission.source_sequence
    declaration_shell = sequence.declaration_shell
    helper_set_completion = declaration_shell.source_helper_set_completion
    predicate_path = return_emission.source_post_branch_call_site.source_predicate_path
    post_branch_call_site = return_emission.source_post_branch_call_site
    members = _structural_package_members(
        declaration_shell,
        predicate_path,
        post_branch_call_site,
        return_emission,
    )
    try:
        return Result.ok(
            ExactArrayBodyStructuralPackageIr(
                source_envelope=sequence.source_envelope,
                helper_set_completion=helper_set_completion,
                declaration_shell=declaration_shell,
                source_sequence=sequence,
                predicate_path=predicate_path,
                post_branch_call_site=post_branch_call_site,
                return_emission=return_emission,
                members=members,
                source_location=sequence.source_location,
                candidate_id=return_emission.candidate_id,
                target_extension=return_emission.target_extension,
                source_extension=return_emission.source_extension,
                selected_type_tag=return_emission.selected_type_tag,
                originating_branch_chain_id=(
                    return_emission.originating_branch_chain_id
                ),
            )
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _array_body_package_provenance_mismatch_diagnostic(
                    str(exc),
                    return_emission.source_location,
                ),
            )
        )


def _array_body_package_return_emission_source(
    source: object,
) -> Result[ExactReturnEmissionStructuralRequestIr]:
    if isinstance(source, ExactReturnEmissionStructuralRequestIr):
        return Result.ok(source)

    if _is_generation_stage_like(source):
        stage = getattr(source, "stage")
        output = getattr(source, "output")
        if (
            stage == "return_emission_structural_request_lowering"
            and isinstance(output, ExactReturnEmissionStructuralRequestIr)
        ):
            return Result.ok(output)
        return Result.failure(
            (
                _array_body_package_source_unsupported_diagnostic(
                    "array-body structural package assembly consumes accepted "
                    "M87 ExactReturnEmissionStructuralRequestIr values, the "
                    "return_emission_structural_request_lowering stage output, "
                    "or a source carrying exactly one accepted M87 value",
                    _source_location_from_object(output),
                ),
            )
        )

    if isinstance(source, _ArrayBodyPackageReturnEmissionSource):
        raw_requests = source.return_emission_structural_requests
        if not isinstance(raw_requests, tuple):
            return Result.failure(
                (
                    _array_body_package_source_unsupported_diagnostic(
                        "array-body structural package assembly requires "
                        "return_emission_structural_requests to be a tuple "
                        "carrying exactly one accepted M87 "
                        "ExactReturnEmissionStructuralRequestIr value",
                        _source_location_from_object(raw_requests),
                    ),
                )
            )
        requests: tuple[object, ...] = raw_requests
        location = _source_location_from_return_emission_requests(requests)
        if len(requests) == 0:
            return Result.failure(
                (
                    _array_body_package_missing_ir_diagnostic(
                        "array-body structural package assembly requires a "
                        "source carrying one accepted M87 "
                        "return_emission_structural_requests entry",
                        location,
                    ),
                )
            )
        if len(requests) > 1:
            return Result.failure(
                (
                    _array_body_package_multiple_ir_diagnostic(
                        "array-body structural package assembly requires "
                        "exactly one M87 return_emission_structural_requests "
                        f"entry; got {len(requests)}",
                        location,
                    ),
                )
            )
        request = requests[0]
        if not isinstance(request, ExactReturnEmissionStructuralRequestIr):
            return Result.failure(
                (
                    _array_body_package_source_unsupported_diagnostic(
                        "array-body structural package assembly requires the "
                        "single return_emission_structural_requests entry to "
                        "be an accepted M87 "
                        "ExactReturnEmissionStructuralRequestIr value",
                        location or _source_location_from_object(request),
                    ),
                )
            )
        return Result.ok(request)

    return Result.failure(
        (
            _array_body_package_source_unsupported_diagnostic(
                "array-body structural package assembly consumes only "
                "accepted M87 return-emission typed sources",
                None,
            ),
        )
    )


def _is_generation_stage_like(source: object) -> bool:
    return hasattr(source, "stage") and hasattr(source, "output")


def _source_location_from_return_emission_requests(
    requests: tuple[object, ...],
) -> SourceLocation | None:
    for request in requests:
        if isinstance(request, ExactReturnEmissionStructuralRequestIr):
            return request.source_location
        location = _source_location_from_object(request)
        if location is not None:
            return location
    return None


def _source_location_from_object(source: object) -> SourceLocation | None:
    location = getattr(source, "source_location", None)
    if isinstance(location, SourceLocation):
        return location
    return None


def _validate_return_emission_package_chain(
    return_emission: ExactReturnEmissionStructuralRequestIr,
) -> tuple[Diagnostic, ...]:
    post_branch_call_site = return_emission.source_post_branch_call_site
    if not isinstance(
        post_branch_call_site,
        ExactPostBranchIntrinsicCallSiteStructuralRequestIr,
    ):
        return (
            _array_body_package_missing_member_diagnostic(
                "array-body structural package assembly requires the M87 "
                "request to carry its accepted M76 post-branch call-site member",
                return_emission.source_location,
            ),
        )

    sequence = return_emission.source_sequence
    if not isinstance(sequence, ExactArrayBodyStructuralSequenceIr):
        return (
            _array_body_package_missing_member_diagnostic(
                "array-body structural package assembly requires the M87 "
                "request to carry its accepted M74 structural sequence member",
                return_emission.source_location,
            ),
        )
    if len(sequence.roles) != 5:
        return (
            _array_body_package_missing_member_diagnostic(
                "array-body structural package assembly requires the exact "
                "five-slot M74 source sequence",
                sequence.source_location,
            ),
        )

    expected_role_order = (
        "first_slot_declaration_shell",
        "opaque_predicate_init_shaped_slot",
        "selected_body_envelope_slot",
        "opaque_post_branch_store_call_shaped_slot",
        "opaque_return_emission_shaped_slot",
    )
    if (
        tuple(role.role_label for role in sequence.roles) != expected_role_order
        or tuple(role.role_ordinal for role in sequence.roles) != (0, 1, 2, 3, 4)
    ):
        return (
            _array_body_package_source_order_mismatch_diagnostic(
                "array-body structural package assembly requires the accepted "
                "M74 source-ordered role sequence",
                sequence.source_location,
            ),
        )

    declaration_shell = sequence.declaration_shell
    if not isinstance(declaration_shell, ExactArrayInitializationDeclarationShellIr):
        return (
            _array_body_package_missing_member_diagnostic(
                "array-body structural package assembly requires the accepted "
                "M73 declaration-shell member",
                sequence.source_location,
            ),
        )
    helper_set_completion = declaration_shell.source_helper_set_completion
    if not isinstance(
        helper_set_completion,
        ExactArrayInitializationHelperSetCompletionIr,
    ):
        return (
            _array_body_package_missing_member_diagnostic(
                "array-body structural package assembly requires the accepted "
                "M72 helper-set completion member",
                declaration_shell.source_location,
            ),
        )

    predicate_path = post_branch_call_site.source_predicate_path
    if not isinstance(predicate_path, ExactPredicatePathStructuralRequestIr):
        return (
            _array_body_package_missing_member_diagnostic(
                "array-body structural package assembly requires the accepted "
                "M75 predicate-path member",
                post_branch_call_site.source_location,
            ),
        )
    if (
        declaration_shell.source_helper_set_completion is not helper_set_completion
        or declaration_shell.source_envelope is not sequence.source_envelope
        or sequence.declaration_shell is not declaration_shell
        or predicate_path.source_sequence is not sequence
        or post_branch_call_site.source_sequence is not sequence
        or post_branch_call_site.source_predicate_path is not predicate_path
        or return_emission.source_sequence is not sequence
        or return_emission.source_post_branch_call_site is not post_branch_call_site
    ):
        return (
            _array_body_package_provenance_mismatch_diagnostic(
                "array-body structural package assembly preserves only the "
                "accepted M64-M87 member identity chain",
                return_emission.source_location,
            ),
        )

    expected_context = (
        return_emission.candidate_id,
        return_emission.target_extension,
        return_emission.source_extension,
        return_emission.selected_type_tag,
        return_emission.originating_branch_chain_id,
    )
    for label, value in (
        ("M73 declaration shell", declaration_shell),
        ("M74 structural sequence", sequence),
        ("M75 predicate path", predicate_path),
        ("M76 post-branch call-site", post_branch_call_site),
    ):
        actual_context = (
            value.candidate_id,
            value.target_extension,
            value.source_extension,
            value.selected_type_tag,
            value.originating_branch_chain_id,
        )
        if actual_context != expected_context:
            return (
                _array_body_package_provenance_mismatch_diagnostic(
                    "array-body structural package assembly requires the "
                    f"{label} context to match the M87 request context",
                    value.source_location,
                ),
            )

    return ()


def _structural_package_members(
    declaration_shell: ExactArrayInitializationDeclarationShellIr,
    predicate_path: ExactPredicatePathStructuralRequestIr,
    post_branch_call_site: ExactPostBranchIntrinsicCallSiteStructuralRequestIr,
    return_emission: ExactReturnEmissionStructuralRequestIr,
) -> tuple[ExactArrayBodyStructuralPackageMember, ...]:
    sequence = return_emission.source_sequence
    return (
        ExactArrayBodyStructuralPackageMember(
            kind="declaration_shell",
            role_label=sequence.roles[0].role_label,
            role_ordinal=0,
            source_location=sequence.roles[0].source_location,
            fact=declaration_shell,
        ),
        ExactArrayBodyStructuralPackageMember(
            kind="predicate_path",
            role_label=sequence.roles[1].role_label,
            role_ordinal=1,
            source_location=predicate_path.predicate_init_source_location,
            fact=predicate_path,
        ),
        ExactArrayBodyStructuralPackageMember(
            kind="selected_update",
            role_label=sequence.roles[2].role_label,
            role_ordinal=2,
            source_location=predicate_path.selected_update_source_location,
            fact=predicate_path,
        ),
        ExactArrayBodyStructuralPackageMember(
            kind="post_branch_call_site",
            role_label=sequence.roles[3].role_label,
            role_ordinal=3,
            source_location=post_branch_call_site.source_location,
            fact=post_branch_call_site,
        ),
        ExactArrayBodyStructuralPackageMember(
            kind="return_emission",
            role_label=sequence.roles[4].role_label,
            role_ordinal=4,
            source_location=return_emission.source_location,
            fact=return_emission,
        ),
    )


def _raise_first_package_validation_error(
    package: ExactArrayBodyStructuralPackageIr,
) -> None:
    if not isinstance(package.source_envelope, ExactArrayBodyEnvelopeIr):
        raise TypeError("array-body structural package requires an M65 envelope")
    if not isinstance(
        package.helper_set_completion,
        ExactArrayInitializationHelperSetCompletionIr,
    ):
        raise TypeError(
            "array-body structural package requires an M72 helper-set completion"
        )
    if not isinstance(
        package.declaration_shell,
        ExactArrayInitializationDeclarationShellIr,
    ):
        raise TypeError(
            "array-body structural package requires an M73 declaration shell"
        )
    if not isinstance(package.source_sequence, ExactArrayBodyStructuralSequenceIr):
        raise TypeError(
            "array-body structural package requires an M74 structural sequence"
        )
    if not isinstance(package.predicate_path, ExactPredicatePathStructuralRequestIr):
        raise TypeError(
            "array-body structural package requires an M75 predicate-path request"
        )
    if not isinstance(
        package.post_branch_call_site,
        ExactPostBranchIntrinsicCallSiteStructuralRequestIr,
    ):
        raise TypeError(
            "array-body structural package requires an M76 post-branch call-site"
        )
    if not isinstance(package.return_emission, ExactReturnEmissionStructuralRequestIr):
        raise TypeError(
            "array-body structural package requires an M87 return-emission request"
        )
    if package.source_location is None:
        raise ValueError("array-body structural package requires source location")
    if (
        package.declaration_shell.source_helper_set_completion
        is not package.helper_set_completion
        or package.declaration_shell.source_envelope is not package.source_envelope
        or package.source_sequence.source_envelope is not package.source_envelope
        or package.source_sequence.declaration_shell is not package.declaration_shell
        or package.predicate_path.source_sequence is not package.source_sequence
        or package.post_branch_call_site.source_predicate_path
        is not package.predicate_path
        or package.post_branch_call_site.source_sequence is not package.source_sequence
        or package.return_emission.source_post_branch_call_site
        is not package.post_branch_call_site
        or package.return_emission.source_sequence is not package.source_sequence
    ):
        raise ValueError(
            "array-body structural package must preserve accepted M64-M87 "
            "member identity"
        )
    if tuple(member.kind for member in package.members) != (
        "declaration_shell",
        "predicate_path",
        "selected_update",
        "post_branch_call_site",
        "return_emission",
    ):
        raise ValueError(
            "array-body structural package members must use the exact M88 order"
        )
    if tuple(member.role_ordinal for member in package.members) != (0, 1, 2, 3, 4):
        raise ValueError(
            "array-body structural package members must preserve source order"
        )
    if (
        package.members[0].fact is not package.declaration_shell
        or package.members[1].fact is not package.predicate_path
        or package.members[2].fact is not package.predicate_path
        or package.members[3].fact is not package.post_branch_call_site
        or package.members[4].fact is not package.return_emission
    ):
        raise ValueError(
            "array-body structural package members must reference accepted facts"
        )
    expected_context = (
        package.candidate_id,
        package.target_extension,
        package.source_extension,
        package.selected_type_tag,
        package.originating_branch_chain_id,
    )
    for value in (
        package.declaration_shell,
        package.source_sequence,
        package.predicate_path,
        package.post_branch_call_site,
        package.return_emission,
    ):
        actual_context = (
            value.candidate_id,
            value.target_extension,
            value.source_extension,
            value.selected_type_tag,
            value.originating_branch_chain_id,
        )
        if actual_context != expected_context:
            raise ValueError(
                "array-body structural package context must match all members"
            )


def _array_body_package_source_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BODY-PACKAGE-SOURCE-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_body_package_missing_ir_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BODY-PACKAGE-IR-MISSING",
        detail,
        location=location,
    )


def _array_body_package_multiple_ir_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BODY-PACKAGE-IR-MULTIPLE",
        detail,
        location=location,
    )


def _array_body_package_missing_member_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BODY-PACKAGE-MEMBER-MISSING",
        detail,
        location=location,
    )


def _array_body_package_context_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BODY-PACKAGE-CONTEXT-MISMATCH",
        detail,
        location=location,
    )


def _array_body_package_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BODY-PACKAGE-PROVENANCE-MISMATCH",
        detail,
        location=location,
    )


def _array_body_package_source_order_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BODY-PACKAGE-SOURCE-ORDER-MISMATCH",
        detail,
        location=location,
    )
