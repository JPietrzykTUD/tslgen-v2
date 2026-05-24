from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any, cast
import unittest

from _helpers import assert_diagnostic
import tslgen.lowering._lowering_backend_boundary_worklist as worklist
import tslgen.lowering._lowering_backend_boundary_worklist_models as worklist_models
import tslgen.lowering._lowering_backend_translation_expansion as expansion
import tslgen.lowering._lowering_backend_translation_expansion_diagnostics as expansion_diagnostics
import tslgen.lowering._lowering_backend_translation_expansion_models as expansion_models
import tslgen.lowering._lowering_backend_translation_expansion_sources as expansion_sources
import tslgen.lowering._lowering_backend_translation_expansion_validation as expansion_validation
import tslgen.lowering._lowering_backend_translation_request_inventory as request_inventory_lowering
import tslgen.lowering._lowering_backend_translation_result as translation_result
import tslgen.lowering._lowering_ir_contracts as lowering_ir_contracts
import tslgen.lowering.boundary as lowering_boundary
import test_lowering_backend_translation_result as m100_fixtures
from tslgen.core.diagnostics import SourceLocation


def _inventory(
    *,
    include_exact: bool = True,
    include_selected: bool = True,
    include_mini: bool = True,
):
    return m100_fixtures._request_inventory(
        include_exact=include_exact,
        include_selected=include_selected,
        include_mini=include_mini,
    )


def _worklist_inventory(
    *,
    include_exact: bool = True,
    include_selected: bool = True,
    include_mini: bool = True,
    include_m100_result: bool = False,
):
    _manifest, _gap_inventory, inventory = _inventory(
        include_exact=include_exact,
        include_selected=include_selected,
        include_mini=include_mini,
    )
    exact_result = (
        translation_result.lower_exact_array_backend_uninit_translation_result(
            inventory,
            cpp_value_array_uninit_rules=(m100_fixtures._cpp_rule(),),
        ).unwrap()
        if include_m100_result
        else None
    )
    lowered = worklist.lower_stage8_backend_boundary_worklist_inventory(
        inventory,
        exact_array_backend_uninit_translation_result=exact_result,
    ).unwrap()
    return inventory, exact_result, lowered


def _selected_worklist_with_token(
    *,
    token_text: str,
    selected_type_tag: str,
):
    fixture = m100_fixtures._helper()
    package = m100_fixtures.lower_lowering_operation_package(
        fixture.selected_body_envelope(
            selected_type_tag=selected_type_tag,
            token_text=token_text,
            rhs_text=f"intrin<{token_text}>()",
            original_body_text=f"pg = intrin<{token_text}>();",
        )
    ).unwrap()
    _manifest, _gap_inventory, inventory = m100_fixtures._inventory_from_packages(
        (package,)
    )
    lowered = worklist.lower_stage8_backend_boundary_worklist_inventory(
        inventory,
    ).unwrap()
    return lowered


def _entry(
    lowered: worklist.Stage8BackendBoundaryWorklistInventoryIr,
    classification: str,
) -> worklist.Stage8BackendBoundaryWorklistEntryIr:
    return next(entry for entry in lowered.entries if entry.classification == classification)


def _rule(
    entry: worklist.Stage8BackendBoundaryWorklistEntryIr,
    *,
    backend_id: str = "cpp",
    result_name: str | None = None,
    rule_kind: str | None = None,
    translated_value: str = "typed-expansion-value",
    source_request_record: object | None = None,
) -> expansion.Stage8BackendTranslationExpansionRule:
    assert entry.source_request_record is not None
    if entry.source_request_record.kind == "exact_array_backend_value_uninit_array":
        default_kind = "exact_array_backend_uninit"
        default_result_name = expansion.EXACT_ARRAY_BACKEND_UNINIT_EXPANSION_RESULT_NAME
    else:
        default_kind = "selected_body_direct_intrinsic"
        default_result_name = (
            expansion.SELECTED_BODY_DIRECT_INTRINSIC_EXPANSION_RESULT_NAME
        )
    request = entry.source_request_record
    if source_request_record is not None:
        request = cast(Any, source_request_record)
    return expansion.Stage8BackendTranslationExpansionRule(
        source_worklist_entry=entry,
        source_request_record=request,
        rule_kind=rule_kind or default_kind,
        backend_id=backend_id,
        result_name=result_name or default_result_name,
        translated_value=translated_value,
        source_location=SourceLocation(Path("translation_expansion_rules.tsl"), 7, 11),
    )


class LoweringBackendTranslationExpansionTests(unittest.TestCase):
    def test_m104_exact_array_unresolved_resolves_from_explicit_rule(self) -> None:
        inventory, _exact_result, lowered = _worklist_inventory(
            include_exact=True,
            include_selected=False,
            include_mini=False,
        )
        exact_entry = _entry(lowered, "exact_array_backend_uninit_unresolved")
        rule = _rule(
            exact_entry,
            backend_id="rust",
            translated_value="typed-rust-uninit-value",
        )

        result = expansion.lower_stage8_backend_translation_expansion_result(
            lowered,
            rules=(rule,),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        expanded = result.unwrap()
        self.assertEqual(
            expanded.result_state,
            "has_backend_translation_expansion_records",
        )
        self.assertIs(expanded.source_worklist_inventory, lowered)
        self.assertEqual(len(expanded.records), 1)
        record = expanded.records[0]
        self.assertEqual(record.record_state, "resolved")
        self.assertEqual(record.record_kind, "exact_array_backend_uninit")
        self.assertEqual(record.backend_id, "rust")
        self.assertEqual(record.result_name, "value_array_uninit")
        self.assertEqual(record.translated_value, "typed-rust-uninit-value")
        self.assertIs(record.source_worklist_entry, exact_entry)
        self.assertIs(record.source_request_record, inventory.request_records[0])
        self.assertIs(record.source_rule, rule)
        self.assertEqual(record.diagnostics, ())
        self.assertIs(
            rule.ir_contract,
            expansion.STAGE8_BACKEND_TRANSLATION_EXPANSION_RULE_CONTRACT,
        )
        self.assertEqual(rule.ir_contract.category, "rule_input")
        self.assertIs(
            record.ir_contract,
            expansion.STAGE8_BACKEND_TRANSLATION_EXPANSION_RECORD_CONTRACT,
        )
        self.assertEqual(record.ir_contract.category, "result")
        self.assertIs(
            expanded.ir_contract,
            expansion.STAGE8_BACKEND_TRANSLATION_EXPANSION_RESULT_CONTRACT,
        )
        self.assertEqual(expanded.ir_contract.category, "result")

    def test_m104_selected_body_deferred_resolves_from_explicit_rule(self) -> None:
        inventory, exact_result, lowered = _worklist_inventory(
            include_exact=True,
            include_selected=True,
            include_mini=False,
            include_m100_result=True,
        )
        selected_entry = _entry(lowered, "selected_body_direct_intrinsic_deferred")
        rule = _rule(
            selected_entry,
            backend_id="cpp",
            translated_value="typed-selected-body-result",
        )

        result = expansion.lower_stage8_backend_translation_expansion_result(
            lowered,
            rules=(rule,),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        expanded = result.unwrap()
        self.assertEqual(len(expanded.records), 1)
        record = expanded.records[0]
        self.assertEqual(record.record_state, "resolved")
        self.assertEqual(record.record_kind, "selected_body_direct_intrinsic")
        self.assertEqual(record.result_name, "direct_intrinsic_call")
        self.assertIs(record.source_worklist_inventory, lowered)
        self.assertIs(record.source_worklist_entry, selected_entry)
        self.assertIs(record.source_request_record, inventory.request_records[1])
        self.assertIs(record.source_rule, rule)
        self.assertIs(
            selected_entry.source_exact_array_backend_uninit_translation_result,
            exact_result,
        )
        assert exact_result is not None
        self.assertIs(
            selected_entry.source_deferred_request_record,
            exact_result.deferred_request_records[0],
        )
        self.assertIs(
            selected_entry.source_deferred_request_record,
            selected_entry.source_request_record,
        )
        self.assertEqual(record.translated_value, "typed-selected-body-result")

    def test_m104_missing_rules_create_deferred_records_with_diagnostics(self) -> None:
        _inventory, _exact_result, lowered = _worklist_inventory(
            include_exact=True,
            include_selected=True,
            include_mini=True,
        )

        result = expansion.lower_stage8_backend_translation_expansion_result(lowered)

        self.assertTrue(result.is_ok, result.diagnostics)
        expanded = result.unwrap()
        self.assertEqual(
            tuple(record.record_state for record in expanded.records),
            ("deferred", "deferred"),
        )
        self.assertEqual(
            tuple(record.record_kind for record in expanded.records),
            ("exact_array_backend_uninit", "selected_body_direct_intrinsic"),
        )
        self.assertNotIn(
            "no_accepted_backend_boundary_fact",
            tuple(record.record_kind for record in expanded.records),
        )
        for record in expanded.records:
            with self.subTest(record=record.record_kind):
                self.assertIsNone(record.backend_id)
                self.assertIsNone(record.result_name)
                self.assertIsNone(record.translated_value)
                self.assertEqual(record.source_rules, ())
                assert_diagnostic(
                    self,
                    record.diagnostics[0],
                    code="TSL-LOWER-BACKEND-TRANSLATION-EXPANSION-RULE-MISSING",
                    severity="error",
                )

    def test_m104_rule_mismatch_duplicate_and_conflict_are_typed_unsupported(
        self,
    ) -> None:
        _inventory, _exact_result, lowered = _worklist_inventory(
            include_exact=True,
            include_selected=False,
            include_mini=False,
        )
        exact_entry = _entry(lowered, "exact_array_backend_uninit_unresolved")
        cases = (
            (
                "wrong_kind",
                (_rule(exact_entry, rule_kind="selected_body_direct_intrinsic"),),
                "TSL-LOWER-BACKEND-TRANSLATION-EXPANSION-RULE-MISMATCH",
            ),
            (
                "wrong_result_name",
                (_rule(exact_entry, result_name="other_result"),),
                "TSL-LOWER-BACKEND-TRANSLATION-EXPANSION-REQUEST-UNSUPPORTED",
            ),
            (
                "duplicate",
                (
                    _rule(exact_entry, translated_value="same"),
                    _rule(exact_entry, translated_value="same"),
                ),
                "TSL-LOWER-BACKEND-TRANSLATION-EXPANSION-VALUE-MULTIPLE",
            ),
            (
                "conflict",
                (
                    _rule(exact_entry, translated_value="first"),
                    _rule(exact_entry, translated_value="second"),
                ),
                "TSL-LOWER-BACKEND-TRANSLATION-EXPANSION-RULE-CONFLICT",
            ),
        )

        for name, rules, code in cases:
            with self.subTest(name=name):
                result = expansion.lower_stage8_backend_translation_expansion_result(
                    lowered,
                    rules=rules,
                )
                self.assertTrue(result.is_ok, result.diagnostics)
                record = result.unwrap().records[0]
                self.assertEqual(record.record_state, "unsupported")
                self.assertIsNone(record.translated_value)
                assert_diagnostic(
                    self,
                    record.diagnostics[0],
                    code=code,
                    severity="error",
                )

    def test_m104_rejects_protocol_fakes_and_malformed_source_containers(self) -> None:
        class FakeWorklistInventory:
            ir_contract = lowering_ir_contracts.LoweringIrContract(
                name="fake_worklist_inventory",
                category="inventory",
                owner="lowering.backend_translation.boundary_worklist",
            )

            @property
            def key(self) -> tuple[object, ...]:
                return ("fake-worklist",)

        class FakeRule:
            ir_contract = lowering_ir_contracts.LoweringIrContract(
                name="fake_translation_expansion_rule",
                category="rule_input",
                owner="lowering.backend_translation.expansion",
            )

            @property
            def key(self) -> tuple[object, ...]:
                return ("fake-rule",)

        class FakeResult:
            ir_contract = lowering_ir_contracts.LoweringIrContract(
                name="fake_translation_expansion_result",
                category="result",
                owner="lowering.backend_translation.expansion",
            )

            @property
            def key(self) -> tuple[object, ...]:
                return ("fake-result",)

        _inventory, _exact_result, lowered = _worklist_inventory(
            include_exact=True,
            include_selected=False,
            include_mini=False,
        )
        cases = (
            (
                "fake_direct_worklist",
                FakeWorklistInventory(),
                (),
                "TSL-LOWER-BACKEND-TRANSLATION-EXPANSION-SOURCE-UNSUPPORTED",
            ),
            (
                "fake_container_worklist",
                type(
                    "FakeM104Container",
                    (),
                    {
                        "lowering_backend_boundary_worklist_inventories": (
                            FakeWorklistInventory(),
                        )
                    },
                )(),
                (),
                "TSL-LOWER-BACKEND-TRANSLATION-EXPANSION-MALFORMED",
            ),
            (
                "malformed_container_tuple",
                type(
                    "MalformedM104Container",
                    (),
                    {"lowering_backend_boundary_worklist_inventories": [lowered]},
                )(),
                (),
                "TSL-LOWER-BACKEND-TRANSLATION-EXPANSION-MALFORMED",
            ),
            (
                "missing_container_worklist",
                type(
                    "MissingM104Container",
                    (),
                    {"lowering_backend_boundary_worklist_inventories": ()},
                )(),
                (),
                "TSL-LOWER-BACKEND-TRANSLATION-EXPANSION-VALUE-MISSING",
            ),
            (
                "duplicate_container_worklist",
                type(
                    "DuplicateM104Container",
                    (),
                    {"lowering_backend_boundary_worklist_inventories": (lowered, lowered)},
                )(),
                (),
                "TSL-LOWER-BACKEND-TRANSLATION-EXPANSION-VALUE-MULTIPLE",
            ),
            (
                "fake_rule",
                lowered,
                (FakeRule(),),
                "TSL-LOWER-BACKEND-TRANSLATION-EXPANSION-MALFORMED",
            ),
        )
        for name, source, rules, code in cases:
            with self.subTest(name=name):
                result = expansion.lower_stage8_backend_translation_expansion_result(
                    source,
                    rules=cast(Any, rules),
                )
                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code=code,
                    severity="error",
                )

        diagnostics = expansion.validate_stage8_backend_translation_expansion_result(
            FakeResult()
        )
        assert_diagnostic(
            self,
            diagnostics[0],
            code="TSL-LOWER-BACKEND-TRANSLATION-EXPANSION-MALFORMED",
            severity="error",
        )

    def test_m104_reports_provenance_mismatch_and_malformed_keys(self) -> None:
        inventory, _exact_result, lowered = _worklist_inventory(
            include_exact=True,
            include_selected=True,
            include_mini=False,
        )
        exact_entry = _entry(lowered, "exact_array_backend_uninit_unresolved")
        selected_entry = _entry(lowered, "selected_body_direct_intrinsic_deferred")
        wrong_request_rule = _rule(
            exact_entry,
            source_request_record=selected_entry.source_request_record,
        )

        result = expansion.lower_stage8_backend_translation_expansion_result(
            lowered,
            rules=(wrong_request_rule,),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        record = result.unwrap().records[0]
        self.assertEqual(record.record_state, "unsupported")
        assert_diagnostic(
            self,
            record.diagnostics[0],
            code="TSL-LOWER-BACKEND-TRANSLATION-EXPANSION-PROVENANCE-MISMATCH",
            severity="error",
        )

        _other_inventory, _other_exact_result, other_lowered = _worklist_inventory(
            include_exact=True,
            include_selected=False,
            include_mini=False,
        )
        other_entry = _entry(other_lowered, "exact_array_backend_uninit_unresolved")
        unmatched_result = expansion.lower_stage8_backend_translation_expansion_result(
            lowered,
            rules=(_rule(other_entry),),
        )
        self.assertFalse(unmatched_result.is_ok)
        assert_diagnostic(
            self,
            unmatched_result.diagnostics[0],
            code="TSL-LOWER-BACKEND-TRANSLATION-EXPANSION-PROVENANCE-MISMATCH",
            severity="error",
        )

        valid = expansion.lower_stage8_backend_translation_expansion_result(
            lowered
        ).unwrap()
        bad_record = object.__new__(
            expansion.Stage8BackendTranslationExpansionRecordIr
        )
        object.__setattr__(bad_record, "source_worklist_inventory", lowered)
        object.__setattr__(bad_record, "source_worklist_entry", object())
        object.__setattr__(
            bad_record,
            "source_request_record",
            inventory.request_records[0],
        )
        object.__setattr__(bad_record, "record_kind", "exact_array_backend_uninit")
        object.__setattr__(bad_record, "record_state", "deferred")
        object.__setattr__(bad_record, "backend_id", None)
        object.__setattr__(bad_record, "result_name", None)
        object.__setattr__(bad_record, "translated_value", None)
        object.__setattr__(bad_record, "source_rules", ())
        object.__setattr__(bad_record, "diagnostics", valid.records[0].diagnostics)
        malformed_result = object.__new__(
            expansion.Stage8BackendTranslationExpansionResultIr
        )
        object.__setattr__(malformed_result, "candidate_id", valid.candidate_id)
        object.__setattr__(
            malformed_result,
            "source_location",
            valid.source_location,
        )
        object.__setattr__(
            malformed_result,
            "result_state",
            valid.result_state,
        )
        object.__setattr__(
            malformed_result,
            "source_worklist_inventory",
            lowered,
        )
        object.__setattr__(malformed_result, "records", (bad_record,))

        diagnostics = expansion.validate_stage8_backend_translation_expansion_result(
            malformed_result,
        )

        assert_diagnostic(
            self,
            diagnostics[0],
            code="TSL-LOWER-BACKEND-TRANSLATION-EXPANSION-MALFORMED",
            severity="error",
        )

    def test_m104_does_not_resolve_selected_body_from_tokens_or_context(self) -> None:
        cases = (
            ("svptrue_b16", "si16"),
            ("svptrue_b32", "si32"),
            ("avx512_mask_token", "ui64"),
        )
        for token_text, selected_type_tag in cases:
            with self.subTest(token_text=token_text, selected_type_tag=selected_type_tag):
                lowered = _selected_worklist_with_token(
                    token_text=token_text,
                    selected_type_tag=selected_type_tag,
                )
                result = expansion.lower_stage8_backend_translation_expansion_result(
                    lowered,
                )

                self.assertTrue(result.is_ok, result.diagnostics)
                self.assertEqual(len(result.unwrap().records), 1)
                record = result.unwrap().records[0]
                self.assertEqual(record.record_state, "deferred")
                self.assertIsNone(record.translated_value)
                assert_diagnostic(
                    self,
                    record.diagnostics[0],
                    code="TSL-LOWER-BACKEND-TRANSLATION-EXPANSION-RULE-MISSING",
                    severity="error",
                )

    def test_m104_deterministic_keys_for_reordered_inputs(self) -> None:
        fixture = m100_fixtures._helper()
        selected_package = m100_fixtures.lower_lowering_operation_package(
            fixture.selected_body_envelope(selected_type_tag="si32")
        ).unwrap()
        mini_package = m100_fixtures._mini_package()
        exact_package = m100_fixtures.lower_lowering_operation_package(
            fixture.exact_array_backend_handoff_request()
        ).unwrap()
        _first_manifest, _first_gap_inventory, first_inventory = (
            m100_fixtures._inventory_from_packages(
                (selected_package, mini_package, exact_package)
            )
        )
        _second_manifest, _second_gap_inventory, second_inventory = (
            m100_fixtures._inventory_from_packages(
                (exact_package, selected_package, mini_package)
            )
        )
        first_worklist = worklist.lower_stage8_backend_boundary_worklist_inventory(
            first_inventory,
        ).unwrap()
        second_worklist = worklist.lower_stage8_backend_boundary_worklist_inventory(
            second_inventory,
        ).unwrap()
        first_rules = tuple(
            _rule(entry, translated_value=f"typed-value-{index}")
            for index, entry in enumerate(first_worklist.entries)
            if entry.classification
            in (
                "exact_array_backend_uninit_unresolved",
                "selected_body_direct_intrinsic_deferred",
            )
        )
        second_rules = tuple(
            _rule(entry, translated_value=f"typed-value-{index}")
            for index, entry in enumerate(second_worklist.entries)
            if entry.classification
            in (
                "exact_array_backend_uninit_unresolved",
                "selected_body_direct_intrinsic_deferred",
            )
        )

        first = expansion.lower_stage8_backend_translation_expansion_result(
            first_worklist,
            rules=first_rules,
        ).unwrap()
        second = expansion.lower_stage8_backend_translation_expansion_result(
            second_worklist,
            rules=second_rules,
        ).unwrap()

        self.assertEqual(first_worklist.key, second_worklist.key)
        self.assertEqual(first.key, second.key)
        self.assertEqual(
            tuple(record.key for record in first.records),
            tuple(record.key for record in second.records),
        )
        self.assertEqual(
            expansion.lower_stage8_backend_translation_expansion_result(
                first_worklist,
                rules=first_rules,
            ).unwrap().key,
            first.key,
        )

    def test_m104_context_mismatch_reports_boundary_diagnostics(self) -> None:
        _inventory, _exact_result, lowered = _worklist_inventory(
            include_exact=True,
            include_selected=False,
            include_mini=False,
        )
        cases: tuple[tuple[str, dict[str, object], str], ...] = (
            (
                "candidate",
                {"candidate_id": "candidate-other"},
                "TSL-LOWER-BACKEND-TRANSLATION-EXPANSION-CONTEXT-MISMATCH",
            ),
            (
                "source_location",
                {"source_location": SourceLocation(Path("other.tsl"), 1, 1)},
                "TSL-LOWER-BACKEND-TRANSLATION-EXPANSION-SOURCE-LOCATION-MISMATCH",
            ),
            (
                "rule_container",
                {"rules": [_rule(_entry(lowered, "exact_array_backend_uninit_unresolved"))]},
                "TSL-LOWER-BACKEND-TRANSLATION-EXPANSION-MALFORMED",
            ),
        )
        for name, kwargs, code in cases:
            with self.subTest(name=name):
                result = expansion.lower_stage8_backend_translation_expansion_result(
                    lowered,
                    **cast(Any, kwargs),
                )
                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code=code,
                    severity="error",
                )

    def test_m104_import_boundary_forbidden_behavior_and_line_counts(self) -> None:
        modules = (
            expansion,
            expansion_diagnostics,
            expansion_models,
            expansion_sources,
            expansion_validation,
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
        for module in modules:
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
            "Stage9",
            "renderer",
            "rendering",
            "generated output",
            "scheduler",
            "readiness",
            "backend_map",
            "backend_catalog",
            "manifest read",
            "tsldata/detail/lang",
            "value<backend>",
            "type<backend>",
            "registry",
            "dispatcher",
            "callback",
            "plugin",
            "fixpoint",
            "backfeed",
            "repair",
            "parse_",
            "extension_id",
            "primitive_name",
            "svptrue",
            "sve",
        ):
            for module in modules:
                with self.subTest(module=module.__name__, forbidden=forbidden):
                    self.assertNotIn(forbidden, inspect.getsource(module))

        line_counts = {
            path.name: len(path.read_text(encoding="utf-8").splitlines())
            for path in (
                Path(cast(str, lowering_boundary.__file__)),
                Path(cast(str, lowering_ir_contracts.__file__)),
                Path(cast(str, request_inventory_lowering.__file__)),
                Path(cast(str, translation_result.__file__)),
                Path(cast(str, worklist.__file__)),
                Path(cast(str, worklist_models.__file__)),
                Path(cast(str, expansion.__file__)),
                Path(cast(str, expansion_diagnostics.__file__)),
                Path(cast(str, expansion_models.__file__)),
                Path(cast(str, expansion_sources.__file__)),
                Path(cast(str, expansion_validation.__file__)),
                Path(__file__),
            )
        }
        self.assertEqual(line_counts["boundary.py"], 1284)
        self.assertEqual(line_counts["_lowering_ir_contracts.py"], 278)
        self.assertEqual(
            line_counts["_lowering_backend_translation_request_inventory.py"],
            792,
        )
        self.assertEqual(line_counts["_lowering_backend_translation_result.py"], 614)
        self.assertLess(line_counts["_lowering_backend_boundary_worklist.py"], 400)
        self.assertLess(
            line_counts["_lowering_backend_boundary_worklist_models.py"],
            250,
        )
        self.assertLess(
            line_counts["_lowering_backend_translation_expansion.py"],
            400,
        )
        self.assertLess(
            line_counts["_lowering_backend_translation_expansion_diagnostics.py"],
            150,
        )
        self.assertLess(
            line_counts["_lowering_backend_translation_expansion_models.py"],
            300,
        )
        self.assertLess(
            line_counts["_lowering_backend_translation_expansion_sources.py"],
            200,
        )
        self.assertLess(
            line_counts["_lowering_backend_translation_expansion_validation.py"],
            550,
        )
        self.assertLess(line_counts[Path(__file__).name], 850)


if __name__ == "__main__":
    unittest.main()
