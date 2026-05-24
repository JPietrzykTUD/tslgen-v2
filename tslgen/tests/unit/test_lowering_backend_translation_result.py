from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any, cast, get_args
import unittest

from _helpers import assert_diagnostic
import tslgen.lowering._lowering_backend_translation_result as translation_result
import tslgen.lowering._lowering_backend_translation_result_diagnostics as translation_result_diagnostics
import tslgen.lowering._lowering_backend_translation_result_sources as translation_result_sources
import tslgen.lowering._lowering_ir_contracts as lowering_ir_contracts
import tslgen.lowering._lowering_backend_translation_request_inventory as request_inventory_lowering
import tslgen.lowering._lowering_completion_gap_inventory as gap_inventory_lowering
import tslgen.lowering._lowering_completion_manifest as completion_manifest_lowering
import tslgen.lowering._lowering_stage_assembly as stage_assembly
import tslgen.lowering._stage_contracts as lowering_stage_contracts
import tslgen.lowering.boundary as lowering_boundary
import test_lowering_boundary as _lowering_boundary_fixtures
from tslgen.core.diagnostics import SourceLocation
from tslgen.lowering import (
    ExactArrayBackendUninitTranslationRecordIr,
    ExactArrayBackendUninitTranslationRule,
    GenerationContext,
    GenerationLoweringStage,
    LoweringRequest,
    TsilBinaryExpression,
    TsilParameterReference,
    TsilReturnStatement,
    lower_candidates,
    lower_exact_array_backend_uninit_translation_result,
    lower_lowering_operation_package,
)


_HELPER_METHOD = "test_m99_backend_translation_request_inventory_no_request_state"


def _helper() -> _lowering_boundary_fixtures.LoweringBoundaryTests:
    return _lowering_boundary_fixtures.LoweringBoundaryTests(_HELPER_METHOD)


def _cpp_rule(
    translated_value: str = "{}",
    *,
    backend_id: str = "cpp",
    rule_name: str = "value_array_uninit",
) -> ExactArrayBackendUninitTranslationRule:
    return ExactArrayBackendUninitTranslationRule(
        backend_id=backend_id,
        rule_name=rule_name,
        translated_value=translated_value,
        source_location=SourceLocation(Path("translate_cpp_fixture.tsl"), 9, 13),
    )


def _mini_package():
    return lower_lowering_operation_package(
        TsilReturnStatement(
            TsilBinaryExpression(
                operator="+",
                left=TsilParameterReference("left"),
                right=TsilParameterReference("right"),
            )
        ),
        candidate_id="candidate-1",
        source_location=SourceLocation(Path("mini.tsl"), 3, 5),
    ).unwrap()


def _request_inventory(
    *,
    include_exact: bool = True,
    include_selected: bool = True,
    include_mini: bool = True,
):
    fixture = _helper()
    packages = []
    if include_selected:
        packages.append(
            lower_lowering_operation_package(
                fixture.selected_body_envelope(selected_type_tag="si32")
            ).unwrap()
        )
    if include_mini:
        packages.append(_mini_package())
    if include_exact:
        packages.append(
            lower_lowering_operation_package(
                fixture.exact_array_backend_handoff_request()
            ).unwrap()
        )
    return _inventory_from_packages(tuple(packages))


def _inventory_from_packages(packages: tuple[object, ...]):
    manifest = completion_manifest_lowering.lower_stage8_lowering_completion_manifest(
        packages,
        candidate_id="candidate-1",
    ).unwrap()
    gap_inventory = (
        gap_inventory_lowering.lower_stage8_lowering_completion_gap_inventory(
            manifest,
        ).unwrap()
    )
    inventory = (
        request_inventory_lowering.lower_stage8_backend_translation_request_inventory(
            gap_inventory,
        ).unwrap()
    )
    return manifest, gap_inventory, inventory


class LoweringBackendTranslationResultTests(unittest.TestCase):
    def test_m100_exact_array_cpp_uninit_result_preserves_request_provenance(
        self,
    ) -> None:
        manifest, gap_inventory, inventory = _request_inventory()
        rule = _cpp_rule()

        result = lower_exact_array_backend_uninit_translation_result(
            inventory,
            cpp_value_array_uninit_rules=(rule,),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        lowered = result.unwrap()
        self.assertEqual(
            lowered.result_state,
            "has_exact_array_backend_uninit_translation_result",
        )
        self.assertIs(lowered.source_request_inventory, inventory)
        self.assertEqual(len(lowered.result_records), 1)
        self.assertEqual(len(lowered.deferred_request_records), 1)
        record = lowered.result_records[0]
        exact_request = inventory.request_records[0]
        self.assertEqual(exact_request.kind, "exact_array_backend_value_uninit_array")
        self.assertIs(record.source_request_inventory, inventory)
        self.assertIs(record.source_request_record, exact_request)
        self.assertIs(record.source_rule, rule)
        self.assertEqual(record.backend_id, "cpp")
        self.assertEqual(record.value_key, "value_array_uninit")
        self.assertEqual(record.translated_value, "{}")
        self.assertIs(exact_request.source_manifest, manifest)
        self.assertIs(exact_request.source_gap_inventory, gap_inventory)
        self.assertIs(exact_request.source_gap_record, gap_inventory.gap_records[0])
        self.assertIs(
            exact_request.source_unresolved_dependency_record,
            gap_inventory.gap_records[0].source_unresolved_dependency_record,
        )
        self.assertIs(
            exact_request.source_dependency_request,
            gap_inventory.gap_records[0].source_dependency_request,
        )
        assert exact_request.source_dependency_request is not None
        completion_dependency = (
            exact_request.source_dependency_request.source_completion_dependency
        )
        self.assertIs(
            exact_request.source_dependency_request.source_request_record,
            completion_dependency.source_request_record,
        )
        self.assertEqual(
            lowered.key,
            lower_exact_array_backend_uninit_translation_result(
                inventory,
                cpp_value_array_uninit_rules=(rule,),
            )
            .unwrap()
            .key,
        )

    def test_m100_exact_array_no_result_state_for_no_request_inventory(
        self,
    ) -> None:
        _manifest, _gap_inventory, inventory = _request_inventory(
            include_exact=False,
            include_selected=False,
            include_mini=True,
        )

        result = lower_exact_array_backend_uninit_translation_result(
            inventory,
            cpp_value_array_uninit_rules=(_cpp_rule(),),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        lowered = result.unwrap()
        self.assertEqual(
            lowered.result_state,
            "no_exact_array_backend_uninit_translation_result",
        )
        self.assertEqual(lowered.result_records, ())
        self.assertEqual(lowered.deferred_request_records, ())

    def test_m100_exact_array_result_stage_integrates_after_request_inventory(
        self,
    ) -> None:
        fixture = _helper()
        selection = fixture.selection_for("lower_generation_size_byte_branch_chain")
        item, envelope = fixture.size_byte_branch_chain_item_and_envelope("si32")
        request = LoweringRequest(
            array_body_envelope_skeletons=(
                fixture.exact_array_body_skeleton_for_envelope(envelope),
            ),
            generation_context=GenerationContext(
                array_initialization_vector_length_metadata=(
                    fixture.vector_length_metadata_for_item(item),
                ),
                array_initialization_vector_alignment_metadata=(
                    fixture.vector_alignment_metadata_for_item(item),
                ),
            ),
            exact_array_backend_uninit_translation_rules=(_cpp_rule(),),
        )

        result = lower_candidates(selection, request)

        self.assertTrue(result.is_ok, result.diagnostics)
        implementation = next(
            implementation
            for implementation in result.unwrap().implementations
            if implementation.exact_array_backend_uninit_translation_results
        )
        stages = tuple(stage.stage for stage in implementation.generation_stages)
        request_index = stages.index("lowering_backend_translation_request_inventory")
        self.assertEqual(
            stages[request_index + 1],
            "exact_array_backend_uninit_translation_result",
        )
        self.assertIs(
            implementation.generation_stages[request_index + 1].output,
            implementation.exact_array_backend_uninit_translation_results[0],
        )
        self.assertIs(
            implementation.exact_array_backend_uninit_translation_results[
                0
            ].source_request_inventory,
            implementation.lowering_backend_translation_request_inventories[0],
        )
        self.assertIn(
            "exact_array_backend_uninit_translation_result",
            get_args(lowering_stage_contracts.GenerationLoweringStageName.__value__),
        )

    def test_m100_exact_array_result_reports_boundary_diagnostics(self) -> None:
        _manifest, _gap_inventory, inventory = _request_inventory()
        selected_manifest, selected_gap_inventory, selected_inventory = (
            _request_inventory(
                include_exact=False,
                include_selected=True,
                include_mini=False,
            )
        )
        _other_manifest, _other_gap_inventory, other_inventory = _request_inventory()
        cases: tuple[tuple[str, object, dict[str, Any], str], ...] = (
            (
                "unsupported_source",
                object(),
                {},
                "TSL-LOWER-BACKEND-TRANSLATION-RESULT-SOURCE-UNSUPPORTED",
            ),
            (
                "wrong_stage",
                GenerationLoweringStage(
                    stage="lowering_completion_gap_inventory",
                    output=selected_gap_inventory,
                ),
                {},
                "TSL-LOWER-BACKEND-TRANSLATION-RESULT-SOURCE-UNSUPPORTED",
            ),
            (
                "malformed_stage_output",
                type(
                    "BadM100Stage",
                    (),
                    {
                        "stage": "lowering_backend_translation_request_inventory",
                        "output": object(),
                    },
                )(),
                {},
                "TSL-LOWER-BACKEND-TRANSLATION-RESULT-MALFORMED",
            ),
            (
                "missing_container_inventory",
                type(
                    "EmptyM100Container",
                    (),
                    {"lowering_backend_translation_request_inventories": ()},
                )(),
                {},
                "TSL-LOWER-BACKEND-TRANSLATION-RESULT-VALUE-MISSING",
            ),
            (
                "duplicate_container_inventory",
                type(
                    "DuplicateM100Container",
                    (),
                    {
                        "lowering_backend_translation_request_inventories": (
                            inventory,
                            other_inventory,
                        )
                    },
                )(),
                {},
                "TSL-LOWER-BACKEND-TRANSLATION-RESULT-VALUE-MULTIPLE",
            ),
            (
                "malformed_container_inventory",
                type(
                    "MalformedM100Container",
                    (),
                    {"lowering_backend_translation_request_inventories": (object(),)},
                )(),
                {},
                "TSL-LOWER-BACKEND-TRANSLATION-RESULT-MALFORMED",
            ),
            (
                "manifest_mismatch",
                type(
                    "M100ManifestMismatch",
                    (),
                    {
                        "lowering_backend_translation_request_inventories": (
                            inventory,
                        ),
                        "lowering_completion_manifests": (selected_manifest,),
                    },
                )(),
                {},
                "TSL-LOWER-BACKEND-TRANSLATION-RESULT-PROVENANCE-MISMATCH",
            ),
            (
                "gap_inventory_mismatch",
                type(
                    "M100GapMismatch",
                    (),
                    {
                        "lowering_backend_translation_request_inventories": (
                            inventory,
                        ),
                        "lowering_completion_gap_inventories": (
                            selected_gap_inventory,
                        ),
                    },
                )(),
                {},
                "TSL-LOWER-BACKEND-TRANSLATION-RESULT-PROVENANCE-MISMATCH",
            ),
            (
                "missing_rule",
                inventory,
                {},
                "TSL-LOWER-BACKEND-TRANSLATION-RESULT-VALUE-MISSING",
            ),
            (
                "duplicate_rule",
                inventory,
                {"cpp_value_array_uninit_rules": (_cpp_rule(), _cpp_rule())},
                "TSL-LOWER-BACKEND-TRANSLATION-RESULT-VALUE-MULTIPLE",
            ),
            (
                "conflicting_rule",
                inventory,
                {
                    "cpp_value_array_uninit_rules": (
                        _cpp_rule("{}"),
                        _cpp_rule("/* typed fixture */"),
                    )
                },
                "TSL-LOWER-BACKEND-TRANSLATION-RESULT-RULE-CONFLICT",
            ),
            (
                "unsupported_backend",
                inventory,
                {"cpp_value_array_uninit_rules": (_cpp_rule(backend_id="rust"),)},
                "TSL-LOWER-BACKEND-TRANSLATION-RESULT-BACKEND-UNSUPPORTED",
            ),
            (
                "unsupported_backend_with_cpp_rule",
                inventory,
                {
                    "cpp_value_array_uninit_rules": (
                        _cpp_rule(),
                        _cpp_rule(backend_id="rust"),
                    )
                },
                "TSL-LOWER-BACKEND-TRANSLATION-RESULT-BACKEND-UNSUPPORTED",
            ),
            (
                "malformed_rule_name_with_cpp_rule",
                inventory,
                {
                    "cpp_value_array_uninit_rules": (
                        _cpp_rule(),
                        _cpp_rule(rule_name="value_other"),
                    )
                },
                "TSL-LOWER-BACKEND-TRANSLATION-RESULT-MALFORMED",
            ),
            (
                "wrong_request_kind",
                selected_inventory,
                {
                    "cpp_value_array_uninit_rules": (_cpp_rule(),),
                    "require_result": True,
                },
                "TSL-LOWER-BACKEND-TRANSLATION-RESULT-REQUEST-UNSUPPORTED",
            ),
            (
                "candidate_mismatch",
                inventory,
                {
                    "cpp_value_array_uninit_rules": (_cpp_rule(),),
                    "candidate_id": "candidate-other",
                },
                "TSL-LOWER-BACKEND-TRANSLATION-RESULT-CONTEXT-MISMATCH",
            ),
            (
                "source_location_mismatch",
                inventory,
                {
                    "cpp_value_array_uninit_rules": (_cpp_rule(),),
                    "source_location": SourceLocation(Path("other.tsl"), 1, 1),
                },
                "TSL-LOWER-BACKEND-TRANSLATION-RESULT-SOURCE-LOCATION-MISMATCH",
            ),
        )

        for name, source, kwargs, code in cases:
            with self.subTest(name=name):
                result = lower_exact_array_backend_uninit_translation_result(
                    source,
                    **kwargs,
                )
                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code=code,
                    severity="error",
                )

    def test_m100_result_keys_are_deterministic_for_reordered_inputs(self) -> None:
        fixture = _helper()
        selected_package = lower_lowering_operation_package(
            fixture.selected_body_envelope(selected_type_tag="si32")
        ).unwrap()
        mini_package = _mini_package()
        exact_package = lower_lowering_operation_package(
            fixture.exact_array_backend_handoff_request()
        ).unwrap()
        _first_manifest, _first_gap_inventory, first_inventory = (
            _inventory_from_packages((selected_package, mini_package, exact_package))
        )
        _second_manifest, _second_gap_inventory, second_inventory = (
            _inventory_from_packages((exact_package, selected_package, mini_package))
        )
        rule = _cpp_rule()
        first = lower_exact_array_backend_uninit_translation_result(
            first_inventory,
            cpp_value_array_uninit_rules=(rule,),
        ).unwrap()
        second = lower_exact_array_backend_uninit_translation_result(
            second_inventory,
            cpp_value_array_uninit_rules=(rule,),
        ).unwrap()

        self.assertEqual(first_inventory.key, second_inventory.key)
        self.assertEqual(first.key, second.key)
        self.assertEqual(
            tuple(record.key for record in first.result_records),
            tuple(record.key for record in second.result_records),
        )
        self.assertEqual(
            tuple(record.key for record in first.deferred_request_records),
            tuple(record.key for record in second.deferred_request_records),
        )

    def test_m101_ir_taxonomy_contracts_are_attached_to_m99_m100_path(
        self,
    ) -> None:
        _manifest, _gap_inventory, inventory = _request_inventory()
        rule = _cpp_rule()
        result = lower_exact_array_backend_uninit_translation_result(
            inventory,
            cpp_value_array_uninit_rules=(rule,),
        ).unwrap()

        self.assertEqual(
            lowering_ir_contracts.LOWERING_IR_CATEGORIES,
            (
                "semantic_fact",
                "request",
                "result",
                "inventory",
                "provenance",
                "rule_input",
                "stage_envelope",
            ),
        )
        self.assertIs(
            request_inventory_lowering.Stage8BackendTranslationRequestRecordIr.ir_contract,
            lowering_ir_contracts.STAGE8_BACKEND_TRANSLATION_REQUEST_RECORD_CONTRACT,
        )
        self.assertIs(
            inventory.request_records[0].ir_contract,
            lowering_ir_contracts.STAGE8_BACKEND_TRANSLATION_REQUEST_RECORD_CONTRACT,
        )
        self.assertIs(
            inventory.no_request_records[0].ir_contract,
            lowering_ir_contracts.STAGE8_BACKEND_TRANSLATION_NO_REQUEST_RECORD_CONTRACT,
        )
        self.assertIs(
            inventory.ir_contract,
            lowering_ir_contracts.STAGE8_BACKEND_TRANSLATION_REQUEST_INVENTORY_CONTRACT,
        )
        self.assertIs(
            rule.ir_contract,
            lowering_ir_contracts.EXACT_ARRAY_BACKEND_UNINIT_TRANSLATION_RULE_CONTRACT,
        )
        self.assertIs(
            result.result_records[0].ir_contract,
            lowering_ir_contracts.EXACT_ARRAY_BACKEND_UNINIT_TRANSLATION_RECORD_CONTRACT,
        )
        self.assertIs(
            result.ir_contract,
            lowering_ir_contracts.EXACT_ARRAY_BACKEND_UNINIT_TRANSLATION_RESULT_CONTRACT,
        )
        self.assertEqual(inventory.ir_contract.category, "inventory")
        self.assertEqual(inventory.request_records[0].ir_contract.category, "request")
        self.assertEqual(inventory.no_request_records[0].ir_contract.category, "provenance")
        self.assertEqual(rule.ir_contract.category, "rule_input")
        self.assertEqual(result.ir_contract.category, "result")

    def test_m101_provenance_identity_contract_reports_first_mismatch(
        self,
    ) -> None:
        shared = object()
        other = object()

        self.assertIsNone(
            lowering_ir_contracts.first_provenance_identity_mismatch(
                (
                    lowering_ir_contracts.LoweringProvenanceIdentity(
                        shared,
                        shared,
                        "shared object identity",
                    ),
                )
            )
        )
        self.assertEqual(
            lowering_ir_contracts.first_provenance_identity_mismatch(
                (
                    lowering_ir_contracts.LoweringProvenanceIdentity(
                        shared,
                        shared,
                        "shared object identity",
                    ),
                    lowering_ir_contracts.LoweringProvenanceIdentity(
                        other,
                        shared,
                        "mismatched object identity",
                    ),
                )
            ),
            "mismatched object identity",
        )

    def test_m102_ir_category_protocol_surface_classifies_m99_m100_path(
        self,
    ) -> None:
        _manifest, _gap_inventory, inventory = _request_inventory()
        rule = _cpp_rule()
        result = lower_exact_array_backend_uninit_translation_result(
            inventory,
            cpp_value_array_uninit_rules=(rule,),
        ).unwrap()
        request_record = inventory.request_records[0]
        no_request_record = inventory.no_request_records[0]
        result_record = result.result_records[0]

        self.assertTrue(
            lowering_ir_contracts.is_lowering_request_ir(request_record)
        )
        self.assertTrue(
            lowering_ir_contracts.is_translation_request_ir(request_record)
        )
        self.assertTrue(lowering_ir_contracts.is_lowering_provenance(no_request_record))
        self.assertTrue(lowering_ir_contracts.is_lowering_inventory(inventory))
        self.assertTrue(lowering_ir_contracts.is_lowering_rule_input(rule))
        self.assertTrue(lowering_ir_contracts.is_translation_result_ir(result_record))
        self.assertTrue(lowering_ir_contracts.is_translation_result_ir(result))
        for value in (
            request_record,
            no_request_record,
            inventory,
            rule,
            result_record,
            result,
        ):
            with self.subTest(value=type(value).__name__):
                self.assertFalse(lowering_ir_contracts.is_lowering_stage_output(value))
                self.assertIsNotNone(lowering_ir_contracts.lowering_ir_contract(value))
                self.assertIsInstance(lowering_ir_contracts.lowering_ir_key(value), tuple)

        class StageEnvelope:
            ir_contract = lowering_ir_contracts.LoweringIrContract(
                name="stage_envelope_fixture",
                category="stage_envelope",
                owner="lowering.stage",
            )

            @property
            def key(self) -> tuple[object, ...]:
                return ("stage-envelope",)

        self.assertTrue(lowering_ir_contracts.is_lowering_stage_output(StageEnvelope()))

        self.assertFalse(lowering_ir_contracts.is_lowering_fact(request_record))
        self.assertFalse(lowering_ir_contracts.is_translation_request_ir(rule))
        self.assertIs(
            lowering_ir_contracts.require_translation_request_ir(
                request_record,
                label="request record",
            ),
            request_record.ir_contract,
        )
        self.assertIs(
            lowering_ir_contracts.require_translation_result_ir(
                result,
                label="result",
            ),
            result.ir_contract,
        )

    def test_m102_ir_category_protocol_surface_rejects_bad_shapes(self) -> None:
        class MissingContract:
            @property
            def key(self) -> tuple[object, ...]:
                return ("missing",)

        class UntypedContract:
            ir_contract = object()

            @property
            def key(self) -> tuple[object, ...]:
                return ("untyped",)

        class MissingKey:
            ir_contract = lowering_ir_contracts.LoweringIrContract(
                name="missing_key_request",
                category="request",
                owner="lowering.backend_translation.request_inventory",
            )

        class NonTupleKey:
            ir_contract = lowering_ir_contracts.LoweringIrContract(
                name="non_tuple_key_request",
                category="request",
                owner="lowering.backend_translation.request_inventory",
            )

            @property
            def key(self) -> str:
                return "not-a-tuple"

        class EmptyTupleKey:
            ir_contract = lowering_ir_contracts.LoweringIrContract(
                name="empty_tuple_key_request",
                category="request",
                owner="lowering.backend_translation.request_inventory",
            )

            @property
            def key(self) -> tuple[object, ...]:
                return ()

        class NonTranslationRequest:
            ir_contract = lowering_ir_contracts.LoweringIrContract(
                name="non_translation_request",
                category="request",
                owner="lowering.other",
            )

            @property
            def key(self) -> tuple[object, ...]:
                return ("non-translation",)

        class FakeBackendTranslationNamespace:
            ir_contract = lowering_ir_contracts.LoweringIrContract(
                name="fake_backend_translation_request",
                category="request",
                owner="lowering.backend_translation_fake",
            )

            @property
            def key(self) -> tuple[object, ...]:
                return ("fake-backend-translation",)

        rule = _cpp_rule()

        bad_cases: tuple[tuple[str, object, str, str], ...] = (
            (
                "missing_contract",
                MissingContract(),
                "request",
                "typed LoweringIrContract",
            ),
            (
                "untyped_contract",
                UntypedContract(),
                "request",
                "typed LoweringIrContract",
            ),
            (
                "missing_key",
                MissingKey(),
                "request",
                "non-empty tuple key",
            ),
            (
                "non_tuple_key",
                NonTupleKey(),
                "request",
                "non-empty tuple key",
            ),
            (
                "empty_tuple_key",
                EmptyTupleKey(),
                "request",
                "non-empty tuple key",
            ),
            (
                "wrong_category",
                rule,
                "request",
                "got 'rule_input'",
            ),
        )
        for name, value, category, message in bad_cases:
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, message):
                    lowering_ir_contracts.require_lowering_ir_category(
                        value,
                        category,  # type: ignore[arg-type]
                        label=name,
                    )

        with self.assertRaisesRegex(ValueError, "backend-translation lowering"):
            lowering_ir_contracts.require_translation_request_ir(
                NonTranslationRequest(),
                label="non-translation request",
            )

        self.assertFalse(
            lowering_ir_contracts.is_translation_request_ir(
                FakeBackendTranslationNamespace()
            )
        )
        with self.assertRaisesRegex(ValueError, "backend-translation lowering"):
            lowering_ir_contracts.require_translation_request_ir(
                FakeBackendTranslationNamespace(),
                label="fake backend translation request",
            )

        with self.assertRaisesRegex(ValueError, "got 'rule_input'"):
            lowering_ir_contracts.require_translation_result_ir(
                rule,
                label="rule",
            )
        for value in (MissingKey(), NonTupleKey(), EmptyTupleKey()):
            with self.subTest(value=type(value).__name__):
                self.assertFalse(lowering_ir_contracts.is_lowering_request_ir(value))
                self.assertFalse(lowering_ir_contracts.is_translation_request_ir(value))
                self.assertIsNone(lowering_ir_contracts.lowering_ir_key(value))

    def test_m102_diagnostic_boundary_requires_stable_identity(self) -> None:
        boundary = lowering_ir_contracts.DiagnosticBoundary(
            name="backend_translation_result",
            code_prefix="TSL-LOWER-BACKEND-TRANSLATION-RESULT",
        )

        self.assertEqual(
            boundary.key,
            (
                "backend_translation_result",
                "TSL-LOWER-BACKEND-TRANSLATION-RESULT",
            ),
        )
        for kwargs in (
            {"name": "", "code_prefix": "TSL"},
            {"name": "boundary", "code_prefix": ""},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaisesRegex(ValueError, "must be non-empty"):
                    lowering_ir_contracts.DiagnosticBoundary(**kwargs)

    def test_m100_existing_result_rejects_copied_request_record(
        self,
    ) -> None:
        _manifest, _gap_inventory, inventory = _request_inventory()
        rule = _cpp_rule()
        valid = lower_exact_array_backend_uninit_translation_result(
            inventory,
            cpp_value_array_uninit_rules=(rule,),
        ).unwrap()
        copied_request = request_inventory_lowering.Stage8BackendTranslationRequestRecordIr(
            source_manifest=inventory.request_records[0].source_manifest,
            source_package_record=(
                inventory.request_records[0].source_package_record
            ),
            source_package=inventory.request_records[0].source_package,
            kind=inventory.request_records[0].kind,
            source_gap_inventory=inventory.request_records[0].source_gap_inventory,
            source_gap_record=inventory.request_records[0].source_gap_record,
            source_unresolved_dependency_record=(
                inventory.request_records[0].source_unresolved_dependency_record
            ),
            source_dependency_request=(
                inventory.request_records[0].source_dependency_request
            ),
        )
        copied_record = object.__new__(ExactArrayBackendUninitTranslationRecordIr)
        object.__setattr__(
            copied_record,
            "source_request_inventory",
            inventory,
        )
        object.__setattr__(copied_record, "source_request_record", copied_request)
        object.__setattr__(copied_record, "source_rule", rule)
        malformed_result = object.__new__(
            translation_result.ExactArrayBackendUninitTranslationResultIr
        )
        object.__setattr__(malformed_result, "candidate_id", valid.candidate_id)
        object.__setattr__(malformed_result, "source_location", valid.source_location)
        object.__setattr__(
            malformed_result,
            "result_state",
            "has_exact_array_backend_uninit_translation_result",
        )
        object.__setattr__(
            malformed_result,
            "source_request_inventory",
            inventory,
        )
        object.__setattr__(malformed_result, "result_records", (copied_record,))
        object.__setattr__(
            malformed_result,
            "deferred_request_records",
            valid.deferred_request_records,
        )

        result = lower_exact_array_backend_uninit_translation_result(malformed_result)

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-LOWER-BACKEND-TRANSLATION-RESULT-PROVENANCE-MISMATCH",
            severity="error",
        )

    def test_m100_result_import_boundary_forbidden_behavior_and_line_counts(
        self,
    ) -> None:
        result_modules = (
            lowering_ir_contracts,
            translation_result,
            translation_result_diagnostics,
            translation_result_sources,
        )
        forbidden_exact_modules = {
            "tslgen.lowering.boundary",
            "tslgen.lowering",
        }
        forbidden_prefixes = (
            "tslgen.backends",
            "tslgen.rendering",
            "tsldata",
            "frozen",
        )
        imported_forbidden: list[str] = []
        for module in result_modules:
            tree = ast.parse(inspect.getsource(module))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if (
                            alias.name in forbidden_exact_modules
                            or alias.name.startswith(forbidden_prefixes)
                        ):
                            imported_forbidden.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    imported = node.module or ""
                    if imported in forbidden_exact_modules or imported.startswith(
                        forbidden_prefixes,
                    ):
                        imported_forbidden.append(imported)

        self.assertEqual(imported_forbidden, [])
        for forbidden in (
            "backend_map",
            "backend_catalog",
            "tsldata/detail/lang",
            "value<backend>",
            "type<backend>",
            "Stage9",
            "renderer",
            "rendering",
            "generated output",
            "registry",
            "dispatcher",
            "callback",
            "fixpoint",
            "backfeed",
            "repair",
            "parse_",
            "scheduler",
            "open(",
            "svptrue",
            "sve",
        ):
            for module in result_modules:
                with self.subTest(module=module.__name__, forbidden=forbidden):
                    self.assertNotIn(forbidden, inspect.getsource(module))

        line_counts = {
            path.name: len(path.read_text(encoding="utf-8").splitlines())
            for path in (
                Path(cast(str, lowering_boundary.__file__)),
                Path(cast(str, stage_assembly.__file__)),
                Path(cast(str, lowering_ir_contracts.__file__)),
                Path(cast(str, request_inventory_lowering.__file__)),
                Path(cast(str, translation_result.__file__)),
                Path(cast(str, translation_result_sources.__file__)),
                Path(cast(str, translation_result_diagnostics.__file__)),
            )
        }
        self.assertLessEqual(line_counts["boundary.py"], 1300)
        self.assertLess(line_counts["_lowering_stage_assembly.py"], 1000)
        self.assertLess(line_counts["_lowering_ir_contracts.py"], 300)
        self.assertLess(
            line_counts["_lowering_backend_translation_request_inventory.py"],
            1000,
        )
        self.assertLess(line_counts["_lowering_backend_translation_result.py"], 1000)
        self.assertLess(
            line_counts["_lowering_backend_translation_result_sources.py"],
            400,
        )
        self.assertLess(
            line_counts["_lowering_backend_translation_result_diagnostics.py"],
            200,
        )


if __name__ == "__main__":
    unittest.main()
