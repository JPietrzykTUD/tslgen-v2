from __future__ import annotations

from dataclasses import dataclass

from tslgen.core.diagnostics import SourceLocation
from tslgen.core.result import Result
import tslgen.lowering._lowering_completion_gap_inventory as _completion_gap_inventory
import tslgen.lowering._lowering_completion_manifest as _completion_manifest
import tslgen.lowering._lowering_backend_translation_request_inventory as _backend_request_inventory
import tslgen.lowering._lowering_backend_translation_result as _translation_result
from tslgen.lowering._generation_models import (
    GenerationExpressionRecognition,
    GenerationPredicate,
    GenerationRecognitionKind,
    GenerationSizeByteBranchChainPruning,
    GenerationValue,
    PrunedGenerationBranch,
)
from tslgen.lowering._operation_package import LoweringOperationPackageIr
from tslgen.lowering._selected_body_models import (
    GenerationSelectedBodyEnvelopeIr,
    GenerationSelectedBranchBodyAssignmentRecognition,
    GenerationSelectedBranchBodyHandoff,
    GenerationSelectedBranchBodyIr,
)
from tslgen.lowering._stage_contracts import (
    GenerationLoweringStage,
    TsilStatement,
)


@dataclass(frozen=True, slots=True)
class _Stage8CompletionTailAssembly:
    operation_packages: tuple[LoweringOperationPackageIr, ...] = ()
    lowering_completion_manifests: tuple[
        _completion_manifest.Stage8LoweringCompletionManifestIr,
        ...,
    ] = ()
    lowering_completion_gap_inventories: tuple[
        _completion_gap_inventory.Stage8LoweringCompletionGapInventoryIr,
        ...,
    ] = ()
    lowering_backend_translation_request_inventories: tuple[
        _backend_request_inventory.Stage8BackendTranslationRequestInventoryIr,
        ...,
    ] = ()
    exact_array_backend_uninit_translation_results: tuple[
        _translation_result.ExactArrayBackendUninitTranslationResultIr,
        ...,
    ] = ()
    stages: tuple[GenerationLoweringStage, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "operation_packages",
            tuple(self.operation_packages),
        )
        object.__setattr__(
            self,
            "lowering_completion_manifests",
            tuple(self.lowering_completion_manifests),
        )
        object.__setattr__(
            self,
            "lowering_completion_gap_inventories",
            tuple(self.lowering_completion_gap_inventories),
        )
        object.__setattr__(
            self,
            "lowering_backend_translation_request_inventories",
            tuple(self.lowering_backend_translation_request_inventories),
        )
        object.__setattr__(
            self,
            "exact_array_backend_uninit_translation_results",
            tuple(self.exact_array_backend_uninit_translation_results),
        )
        object.__setattr__(self, "stages", tuple(self.stages))


def _recognition_stage(
    kind: GenerationRecognitionKind,
    source_text: str,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="helper_expression_recognition",
        output=GenerationExpressionRecognition(
            kind=kind,
            source_text=source_text.strip(),
        ),
    )


def _generation_value_stage(value: GenerationValue) -> GenerationLoweringStage:
    return GenerationLoweringStage(stage="typed_generation_value", output=value)


def _generation_predicate_stage(
    predicate: GenerationPredicate,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="typed_generation_predicate",
        output=predicate,
    )


def _generation_control_flow_stage(
    branch: PrunedGenerationBranch | GenerationSizeByteBranchChainPruning,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="generation_control_flow_pruning",
        output=branch,
    )


def _selected_body_stage(
    output: TsilStatement | GenerationSelectedBranchBodyHandoff,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(stage="selected_body_lowering", output=output)


def _selected_body_form_recognition_stage(
    output: GenerationSelectedBranchBodyAssignmentRecognition,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="selected_body_form_recognition",
        output=output,
    )


def _selected_body_ir_stage(
    output: GenerationSelectedBranchBodyIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(stage="selected_body_ir_lowering", output=output)


def _selected_body_envelope_stage(
    output: GenerationSelectedBodyEnvelopeIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="selected_body_envelope_lowering",
        output=output,
    )


def _lowering_operation_package_stage(
    output: LoweringOperationPackageIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(stage="lowering_operation_package", output=output)


def _lowering_completion_manifest_stage(
    output: _completion_manifest.Stage8LoweringCompletionManifestIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="lowering_completion_manifest",
        output=output,
    )


def _lowering_completion_gap_inventory_stage(
    output: _completion_gap_inventory.Stage8LoweringCompletionGapInventoryIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="lowering_completion_gap_inventory",
        output=output,
    )


def _lowering_backend_translation_request_inventory_stage(
    output: _backend_request_inventory.Stage8BackendTranslationRequestInventoryIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="lowering_backend_translation_request_inventory",
        output=output,
    )


def _exact_array_backend_uninit_translation_result_stage(
    output: _translation_result.ExactArrayBackendUninitTranslationResultIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="exact_array_backend_uninit_translation_result",
        output=output,
    )


def _assemble_stage8_completion_tail(
    operation_packages: tuple[LoweringOperationPackageIr, ...],
    *,
    candidate_id: str,
    source_location: SourceLocation | None = None,
    exact_array_backend_uninit_translation_rules: tuple[
        _translation_result.ExactArrayBackendUninitTranslationRule,
        ...,
    ] = (),
) -> Result[_Stage8CompletionTailAssembly]:
    packages = tuple(operation_packages)
    if not packages:
        return Result.ok(_Stage8CompletionTailAssembly())

    manifest_result = _completion_manifest.lower_stage8_lowering_completion_manifest(
        packages,
        candidate_id=candidate_id,
        source_location=source_location,
    )
    if not manifest_result.is_ok:
        return Result.failure(manifest_result.diagnostics)
    manifest = manifest_result.unwrap()

    inventory_result = (
        _completion_gap_inventory.lower_stage8_lowering_completion_gap_inventory(
            manifest,
        )
    )
    if not inventory_result.is_ok:
        return Result.failure(inventory_result.diagnostics)
    inventory = inventory_result.unwrap()

    request_inventory_result = (
        _backend_request_inventory.lower_stage8_backend_translation_request_inventory(
            inventory,
        )
    )
    if not request_inventory_result.is_ok:
        return Result.failure(request_inventory_result.diagnostics)
    request_inventory = request_inventory_result.unwrap()
    exact_array_backend_uninit_translation_results: tuple[
        _translation_result.ExactArrayBackendUninitTranslationResultIr,
        ...,
    ] = ()
    exact_array_backend_uninit_translation_stages: tuple[
        GenerationLoweringStage,
        ...,
    ] = ()
    if exact_array_backend_uninit_translation_rules:
        translation_result = (
            _translation_result.lower_exact_array_backend_uninit_translation_result(
                request_inventory,
                cpp_value_array_uninit_rules=(
                    exact_array_backend_uninit_translation_rules
                ),
            )
        )
        if not translation_result.is_ok:
            return Result.failure(translation_result.diagnostics)
        uninit_result = translation_result.unwrap()
        exact_array_backend_uninit_translation_results = (uninit_result,)
        exact_array_backend_uninit_translation_stages = (
            _exact_array_backend_uninit_translation_result_stage(uninit_result),
        )

    return Result.ok(
        _Stage8CompletionTailAssembly(
            operation_packages=packages,
            lowering_completion_manifests=(manifest,),
            lowering_completion_gap_inventories=(inventory,),
            lowering_backend_translation_request_inventories=(
                request_inventory,
            ),
            exact_array_backend_uninit_translation_results=(
                exact_array_backend_uninit_translation_results
            ),
            stages=(
                _lowering_completion_manifest_stage(manifest),
                _lowering_completion_gap_inventory_stage(inventory),
                _lowering_backend_translation_request_inventory_stage(
                    request_inventory,
                ),
                *exact_array_backend_uninit_translation_stages,
            ),
        )
    )
