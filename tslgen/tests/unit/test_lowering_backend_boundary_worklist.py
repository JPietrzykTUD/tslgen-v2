from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any, cast
import unittest

from _helpers import assert_diagnostic
import tslgen.lowering._lowering_backend_boundary_worklist as worklist
import tslgen.lowering._lowering_backend_boundary_worklist_diagnostics as worklist_diagnostics
import tslgen.lowering._lowering_backend_boundary_worklist_entries as worklist_entries
import tslgen.lowering._lowering_backend_boundary_worklist_models as worklist_models
import tslgen.lowering._lowering_backend_boundary_worklist_sources as worklist_sources
import tslgen.lowering._lowering_backend_boundary_worklist_validation as worklist_validation
import tslgen.lowering._lowering_backend_translation_request_inventory as request_inventory_lowering
import tslgen.lowering._lowering_backend_translation_request_sources as request_inventory_sources
import tslgen.lowering._lowering_backend_translation_request_diagnostics as request_inventory_diagnostics
import tslgen.lowering._lowering_backend_translation_result as translation_result
import tslgen.lowering._lowering_backend_translation_result_sources as translation_result_sources
import tslgen.lowering._lowering_backend_translation_result_diagnostics as translation_result_diagnostics
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


def _m100_result(inventory):
    return translation_result.lower_exact_array_backend_uninit_translation_result(
        inventory,
        cpp_value_array_uninit_rules=(m100_fixtures._cpp_rule(),),
    ).unwrap()


def _unchecked_worklist(valid, inventory, entries):
    unchecked = object.__new__(worklist.Stage8BackendBoundaryWorklistInventoryIr)
    object.__setattr__(unchecked, "candidate_id", valid.candidate_id)
    object.__setattr__(unchecked, "source_location", valid.source_location)
    object.__setattr__(unchecked, "source_request_inventory", inventory)
    object.__setattr__(
        unchecked,
        "source_exact_array_backend_uninit_translation_result",
        valid.source_exact_array_backend_uninit_translation_result,
    )
    object.__setattr__(unchecked, "entries", entries)
    return unchecked


class LoweringBackendBoundaryWorklistTests(unittest.TestCase):
    def test_m103_worklist_classifies_m99_request_and_no_request_records(
        self,
    ) -> None:
        _manifest, _gap_inventory, inventory = _inventory()

        result = worklist.lower_stage8_backend_boundary_worklist_inventory(inventory)

        self.assertTrue(result.is_ok, result.diagnostics)
        lowered = result.unwrap()
        self.assertEqual(lowered.candidate_id, inventory.candidate_id)
        self.assertIs(lowered.source_request_inventory, inventory)
        self.assertIsNone(lowered.source_exact_array_backend_uninit_translation_result)
        self.assertEqual(
            tuple(entry.classification for entry in lowered.entries),
            (
                "exact_array_backend_uninit_unresolved",
                "selected_body_direct_intrinsic_deferred",
                "no_accepted_backend_boundary_fact",
            ),
        )
        exact_entry, selected_entry, no_request_entry = lowered.entries
        self.assertIs(exact_entry.source_request_record, inventory.request_records[0])
        self.assertIsNone(selected_entry.source_deferred_request_record)
        self.assertIs(selected_entry.source_request_record, inventory.request_records[1])
        self.assertIs(no_request_entry.source_no_request_record, inventory.no_request_records[0])
        self.assertIs(
            selected_entry.ir_contract,
            worklist.STAGE8_BACKEND_BOUNDARY_WORKLIST_ENTRY_CONTRACT,
        )
        self.assertEqual(selected_entry.ir_contract.category, "provenance")
        self.assertIs(
            lowered.ir_contract,
            worklist.STAGE8_BACKEND_BOUNDARY_WORKLIST_INVENTORY_CONTRACT,
        )
        self.assertEqual(lowered.ir_contract.category, "inventory")
        self.assertEqual(
            lowered.key,
            worklist.lower_stage8_backend_boundary_worklist_inventory(
                inventory,
            ).unwrap().key,
        )

    def test_m103_worklist_preserves_m100_result_and_deferred_identities(
        self,
    ) -> None:
        _manifest, _gap_inventory, inventory = _inventory()
        exact_result = _m100_result(inventory)

        result = worklist.lower_stage8_backend_boundary_worklist_inventory(
            inventory,
            exact_array_backend_uninit_translation_result=exact_result,
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        lowered = result.unwrap()
        self.assertIs(
            lowered.source_exact_array_backend_uninit_translation_result,
            exact_result,
        )
        exact_entry, selected_entry, no_request_entry = lowered.entries
        self.assertEqual(
            exact_entry.classification,
            "exact_array_backend_uninit_translated",
        )
        self.assertIs(exact_entry.source_request_record, inventory.request_records[0])
        self.assertIs(
            exact_entry.source_exact_array_backend_uninit_translation_result,
            exact_result,
        )
        self.assertIs(
            exact_entry.source_exact_array_backend_uninit_translation_record,
            exact_result.result_records[0],
        )
        assert exact_entry.source_exact_array_backend_uninit_translation_record is not None
        self.assertIs(
            exact_entry.source_exact_array_backend_uninit_translation_record.source_request_record,
            inventory.request_records[0],
        )
        self.assertEqual(
            selected_entry.classification,
            "selected_body_direct_intrinsic_deferred",
        )
        self.assertIs(
            selected_entry.source_exact_array_backend_uninit_translation_result,
            exact_result,
        )
        self.assertIs(
            selected_entry.source_deferred_request_record,
            exact_result.deferred_request_records[0],
        )
        self.assertIs(
            selected_entry.source_deferred_request_record,
            inventory.request_records[1],
        )
        self.assertEqual(
            no_request_entry.classification,
            "no_accepted_backend_boundary_fact",
        )

    def test_m103_worklist_accepts_container_with_concrete_inventory_and_result(
        self,
    ) -> None:
        _manifest, _gap_inventory, inventory = _inventory()
        exact_result = _m100_result(inventory)
        source = type(
            "M103Container",
            (),
            {
                "lowering_backend_translation_request_inventories": (inventory,),
                "exact_array_backend_uninit_translation_results": (exact_result,),
            },
        )()

        result = worklist.lower_stage8_backend_boundary_worklist_inventory(source)

        self.assertTrue(result.is_ok, result.diagnostics)
        lowered = result.unwrap()
        self.assertIs(lowered.source_request_inventory, inventory)
        self.assertIs(
            lowered.source_exact_array_backend_uninit_translation_result,
            exact_result,
        )

    def test_m103_worklist_rejects_protocol_fakes_and_bad_sources(self) -> None:
        class FakeInventory:
            ir_contract = lowering_ir_contracts.LoweringIrContract(
                name="fake_inventory",
                category="inventory",
                owner="lowering.backend_translation.request_inventory",
            )

            @property
            def key(self) -> tuple[object, ...]:
                return ("fake-inventory",)

        class FakeResult:
            ir_contract = lowering_ir_contracts.LoweringIrContract(
                name="fake_result",
                category="result",
                owner="lowering.backend_translation.exact_array_result",
            )

            @property
            def key(self) -> tuple[object, ...]:
                return ("fake-result",)

        _manifest, _gap_inventory, inventory = _inventory()
        cases = (
            (
                "fake_explicit_result",
                inventory,
                FakeResult(),
                "TSL-LOWER-BACKEND-BOUNDARY-WORKLIST-MALFORMED",
            ),
            (
                "fake_inventory",
                FakeInventory(),
                None,
                "TSL-LOWER-BACKEND-BOUNDARY-WORKLIST-SOURCE-UNSUPPORTED",
            ),
            (
                "fake_result_container",
                type(
                    "FakeResultContainer",
                    (),
                    {
                        "lowering_backend_translation_request_inventories": (
                            inventory,
                        ),
                        "exact_array_backend_uninit_translation_results": (
                            FakeResult(),
                        ),
                    },
                )(),
                None,
                "TSL-LOWER-BACKEND-BOUNDARY-WORKLIST-MALFORMED",
            ),
            (
                "unsupported_stage_like",
                type(
                    "StageLike",
                    (),
                    {
                        "stage": "lowering_backend_translation_request_inventory",
                        "output": inventory,
                    },
                )(),
                None,
                "TSL-LOWER-BACKEND-BOUNDARY-WORKLIST-SOURCE-UNSUPPORTED",
            ),
            (
                "missing_inventory",
                type(
                    "MissingInventoryContainer",
                    (),
                    {"lowering_backend_translation_request_inventories": ()},
                )(),
                None,
                "TSL-LOWER-BACKEND-BOUNDARY-WORKLIST-VALUE-MISSING",
            ),
            (
                "malformed_inventory_container",
                type(
                    "MalformedInventoryContainer",
                    (),
                    {"lowering_backend_translation_request_inventories": [inventory]},
                )(),
                None,
                "TSL-LOWER-BACKEND-BOUNDARY-WORKLIST-MALFORMED",
            ),
        )
        for name, source, exact_result, code in cases:
            with self.subTest(name=name):
                result = worklist.lower_stage8_backend_boundary_worklist_inventory(
                    source,
                    exact_array_backend_uninit_translation_result=cast(Any, exact_result),
                )
                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code=code,
                    severity="error",
                )

    def test_m103_worklist_reports_mismatched_result_context(self) -> None:
        _manifest, _gap_inventory, inventory = _inventory()
        _other_manifest, _other_gap_inventory, other_inventory = _inventory()
        other_result = _m100_result(other_inventory)

        mismatched_candidate = object.__new__(
            translation_result.ExactArrayBackendUninitTranslationResultIr,
        )
        object.__setattr__(mismatched_candidate, "candidate_id", "other-candidate")
        object.__setattr__(
            mismatched_candidate,
            "source_location",
            inventory.source_location,
        )
        object.__setattr__(
            mismatched_candidate,
            "result_state",
            other_result.result_state,
        )
        object.__setattr__(
            mismatched_candidate,
            "source_request_inventory",
            other_result.source_request_inventory,
        )
        object.__setattr__(
            mismatched_candidate,
            "result_records",
            other_result.result_records,
        )
        object.__setattr__(
            mismatched_candidate,
            "deferred_request_records",
            other_result.deferred_request_records,
        )

        mismatched_location = object.__new__(
            translation_result.ExactArrayBackendUninitTranslationResultIr,
        )
        object.__setattr__(mismatched_location, "candidate_id", inventory.candidate_id)
        object.__setattr__(
            mismatched_location,
            "source_location",
            SourceLocation(Path("other.tsl"), 1, 1),
        )
        object.__setattr__(
            mismatched_location,
            "result_state",
            other_result.result_state,
        )
        object.__setattr__(
            mismatched_location,
            "source_request_inventory",
            other_result.source_request_inventory,
        )
        object.__setattr__(
            mismatched_location,
            "result_records",
            other_result.result_records,
        )
        object.__setattr__(
            mismatched_location,
            "deferred_request_records",
            other_result.deferred_request_records,
        )

        cases = (
            (
                "source_inventory",
                other_result,
                "TSL-LOWER-BACKEND-BOUNDARY-WORKLIST-PROVENANCE-MISMATCH",
            ),
            (
                "candidate",
                mismatched_candidate,
                "TSL-LOWER-BACKEND-BOUNDARY-WORKLIST-CONTEXT-MISMATCH",
            ),
            (
                "source_location",
                mismatched_location,
                "TSL-LOWER-BACKEND-BOUNDARY-WORKLIST-SOURCE-LOCATION-MISMATCH",
            ),
        )
        for name, exact_result, code in cases:
            with self.subTest(name=name):
                result = worklist.lower_stage8_backend_boundary_worklist_inventory(
                    inventory,
                    exact_array_backend_uninit_translation_result=exact_result,
                )
                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code=code,
                    severity="error",
                )

    def test_m103_worklist_reports_duplicate_conflicting_and_malformed_entries(
        self,
    ) -> None:
        _manifest, _gap_inventory, inventory = _inventory()
        valid = worklist.lower_stage8_backend_boundary_worklist_inventory(
            inventory,
        ).unwrap()
        duplicate_entries = object.__new__(
            worklist.Stage8BackendBoundaryWorklistInventoryIr,
        )
        object.__setattr__(duplicate_entries, "candidate_id", valid.candidate_id)
        object.__setattr__(duplicate_entries, "source_location", valid.source_location)
        object.__setattr__(
            duplicate_entries,
            "source_request_inventory",
            inventory,
        )
        object.__setattr__(
            duplicate_entries,
            "source_exact_array_backend_uninit_translation_result",
            None,
        )
        object.__setattr__(
            duplicate_entries,
            "entries",
            (valid.entries[0], valid.entries[0], valid.entries[2]),
        )

        conflicting_entry = object.__new__(worklist.Stage8BackendBoundaryWorklistEntryIr)
        object.__setattr__(conflicting_entry, "source_request_inventory", inventory)
        object.__setattr__(
            conflicting_entry,
            "classification",
            "exact_array_backend_uninit_unresolved",
        )
        object.__setattr__(
            conflicting_entry,
            "source_request_record",
            valid.entries[1].source_request_record,
        )
        object.__setattr__(
            conflicting_entry,
            "source_no_request_record",
            valid.entries[2].source_no_request_record,
        )
        object.__setattr__(
            conflicting_entry,
            "source_exact_array_backend_uninit_translation_result",
            None,
        )
        object.__setattr__(
            conflicting_entry,
            "source_exact_array_backend_uninit_translation_record",
            None,
        )
        object.__setattr__(conflicting_entry, "source_deferred_request_record", None)

        malformed_entries = object.__new__(
            worklist.Stage8BackendBoundaryWorklistInventoryIr,
        )
        object.__setattr__(malformed_entries, "candidate_id", valid.candidate_id)
        object.__setattr__(malformed_entries, "source_location", valid.source_location)
        object.__setattr__(malformed_entries, "source_request_inventory", inventory)
        object.__setattr__(
            malformed_entries,
            "source_exact_array_backend_uninit_translation_result",
            None,
        )
        object.__setattr__(
            malformed_entries,
            "entries",
            (valid.entries[0], object(), *valid.entries[2:]),
        )
        malformed_source_inventory = object.__new__(
            worklist.Stage8BackendBoundaryWorklistInventoryIr,
        )
        object.__setattr__(malformed_source_inventory, "candidate_id", valid.candidate_id)
        object.__setattr__(
            malformed_source_inventory,
            "source_location",
            valid.source_location,
        )
        object.__setattr__(
            malformed_source_inventory,
            "source_request_inventory",
            object(),
        )
        object.__setattr__(
            malformed_source_inventory,
            "source_exact_array_backend_uninit_translation_result",
            None,
        )
        object.__setattr__(
            malformed_source_inventory,
            "entries",
            valid.entries,
        )

        cases = (
            (
                "duplicate",
                duplicate_entries,
                "TSL-LOWER-BACKEND-BOUNDARY-WORKLIST-VALUE-MULTIPLE",
            ),
            (
                "conflict",
                _unchecked_worklist(
                    valid,
                    inventory,
                    (valid.entries[0], conflicting_entry, valid.entries[2]),
                ),
                "TSL-LOWER-BACKEND-BOUNDARY-WORKLIST-ENTRY-CONFLICT",
            ),
            (
                "malformed_key",
                malformed_entries,
                "TSL-LOWER-BACKEND-BOUNDARY-WORKLIST-MALFORMED",
            ),
            (
                "malformed_source_inventory",
                malformed_source_inventory,
                "TSL-LOWER-BACKEND-BOUNDARY-WORKLIST-MALFORMED",
            ),
        )
        for name, malformed, code in cases:
            with self.subTest(name=name):
                diagnostics = worklist.validate_stage8_backend_boundary_worklist_inventory(
                    malformed,
                )
                self.assertGreaterEqual(len(diagnostics), 1)
                assert_diagnostic(
                    self,
                    diagnostics[0],
                    code=code,
                    severity="error",
                )

    def test_m103_worklist_import_boundary_forbidden_behavior_and_line_counts(
        self,
    ) -> None:
        modules = (
            worklist,
            worklist_diagnostics,
            worklist_entries,
            worklist_models,
            worklist_sources,
            worklist_validation,
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
                Path(cast(str, request_inventory_sources.__file__)),
                Path(cast(str, request_inventory_diagnostics.__file__)),
                Path(cast(str, translation_result.__file__)),
                Path(cast(str, translation_result_sources.__file__)),
                Path(cast(str, translation_result_diagnostics.__file__)),
                Path(cast(str, worklist.__file__)),
                Path(cast(str, worklist_diagnostics.__file__)),
                Path(cast(str, worklist_entries.__file__)),
                Path(cast(str, worklist_models.__file__)),
                Path(cast(str, worklist_sources.__file__)),
                Path(cast(str, worklist_validation.__file__)),
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
        self.assertLess(
            line_counts["_lowering_backend_boundary_worklist.py"],
            400,
        )
        self.assertLess(
            line_counts["_lowering_backend_boundary_worklist_diagnostics.py"],
            150,
        )
        self.assertLess(
            line_counts["_lowering_backend_boundary_worklist_entries.py"],
            400,
        )
        self.assertLess(
            line_counts["_lowering_backend_boundary_worklist_models.py"],
            250,
        )
        self.assertLess(
            line_counts["_lowering_backend_boundary_worklist_sources.py"],
            300,
        )
        self.assertLess(
            line_counts["_lowering_backend_boundary_worklist_validation.py"],
            250,
        )
        self.assertLess(line_counts[Path(__file__).name], 650)


if __name__ == "__main__":
    unittest.main()
