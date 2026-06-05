# M234 Pairwise Lowering Path Cleanup Execution-Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M233 as accepted.

This prompt selects a lowering implementation milestone. Use the
executor-review loop specified below. M233 established the recursive
source-body fragment tree. M234 must now remove, replace, or explicitly
quarantine the old context-combination paths before any new keyword-specific
semantic consumer milestone is selected.

## Accepted State

Accepted through:

```text
Milestone 230: Source Body Lexical Region Boundary
Milestone 231: Emit Return Lexical Region Lowering
Milestone 232: Return Payload Region Rescan Adapter
Milestone 233: Recursive TSIL Keyword Region Lowering
```

M233 added a recursive fragment boundary over M230 lexical regions:
raw source fragments remain raw, keyword regions become nested keyword
fragments, and `intrin_compose` requests can be extracted anywhere in the tree
without caring about ancestor context.

The known remaining smell is the older body-token path that encodes pairwise
context combinations, especially `emit_return + call`.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/implementation-roadmap.md`
- `tslgen/src/tslgen/lowering/source_body_fragments.py`
- `tslgen/src/tslgen/pipeline/catalog_builder.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/src/tslgen/lowering/primitive_calls.py`
- `tslgen/src/tslgen/pipeline/_tsil_directives.py`
- `tslgen/src/tslgen/pipeline/_tsil_primitive_calls.py`
- `tslgen/tests/test_m233_recursive_tsil_keyword_region_lowering.py`
- Primitive-call and generated-project regression tests relevant to the exact
  old path:
  - `tslgen/tests/test_m150_primitive_call_expression.py`
  - `tslgen/tests/test_m151_primitive_call_consolidation.py`
  - `tslgen/tests/test_m224_parsed_tiny_tsl_to_generated_project.py`

## Goal

Remove the normal lowering dependency on pairwise context-combination handling.
After M234, accepted behavior must flow through either:

```text
M230 lexical regions
-> M233 recursive fragment tree
-> keyword-specific semantic consumer over matching fragments
```

or, for legacy compatibility that cannot be deleted in this slice, through an
explicitly named quarantined compatibility boundary with tests and comments
that prevent future work from extending it.

## Executor Task

Use a single write-capable executor.

Implement the smallest maintainable slice that:

1. Audits and updates the known pairwise paths:
   - `CatalogBuilder._classify_emit_return_payload_tokens`;
   - `Lowerer._primitive_call_expression_result_from_exact_emit_return_body`;
   - the `emit_return` special branch in
     `Lowerer._exact_add_primitive_call_fragment_from_body`;
   - tests whose only purpose is protecting `emit_return + call` or
     `emit_return + intrin_compose` as a special combination.
2. Prefer deleting those paths and replacing accepted behavior with recursive
   fragment-tree consumers.
3. If deleting a path would force broad primitive-call semantic rewrites beyond
   this milestone, quarantine that path in a narrowly named compatibility
   helper/module and add a documented TODO pointing to the exact future
   replacement. Quarantine means:
   - the function/module name includes `legacy` or `compat`;
   - new M230/M233 recursive lowering code does not call it;
   - tests assert it is not the extension point for future keyword nesting;
   - the next semantic consumer prompt still targets the recursive fragment
     tree, not the quarantined helper.
4. Add regression tests proving M233-style recursive fragments are the
   preferred path for nested keywords and that no new production function/class
   encodes a pairwise context name such as `EmitReturnCall`,
   `EmitReturnIntrinCompose`, or `ReturnPayloadCall`.
5. Preserve accepted tiny generated-project behavior unless the active review
   returns `Return To Planner` because the old path is too entangled to cleanly
   replace in one slice.
6. Do not add backend intrinsic handoff lowering, primitive-call dependency
   closure, argument splitting, rendering changes, generated-project expansion,
   broad TSIL parsing, or source repair.

## Out Of Scope

- New keyword semantic consumers beyond what is required to replace/quarantine
  the old pairwise path.
- Full primitive-call selector/argument semantic expansion.
- Intrinsic modifier translation or backend handoff lowering.
- Backend rendering, generated artifact writing, build verification changes,
  or fixture expansion.
- Changes to `outer_parser.py`, `parser.py`, or
  `generated_primitive_pipeline.py` except for tests demonstrating the old path
  is no longer a normal extension point.
- Runtime dependency on `frozen/` or `tslgenold`.

## Required Anti-Regression Checks

The executor and reviewers must explicitly verify:

- No new pairwise parent/child context handler was added.
- The old `emit_return + call` path is deleted, replaced, or quarantined with
  clear naming and tests.
- M233 recursive fragments remain the documented extension point.
- Existing generated-project behavior still passes, or a `Return To Planner`
  prompt is created with exact blockers.

## Review Loop

After the executor finishes, run read-only review/audit subagents:

1. Lowering-boundary reviewer: checks that M234 removes/replaces/quarantines
   the pairwise lowering paths and keeps recursive fragments as the extension
   point.
2. Regression auditor: checks primitive-call and generated-project behavior
   still passes or that a planner return is justified.
3. Complexity reviewer: checks no broad TSIL parser, registry/worklist
   machinery, or new compatibility monolith was added.
4. Documentation reviewer: checks roadmap/state/design docs accurately record
   the cleanup and any explicit quarantine.

Use `docs/agent/review-checklist.md`. If review returns `Needs Revision`, run
one focused revision executor and re-review only the blocking findings. If
review returns `Return To Planner` or `Reject`, stop implementation and create
the appropriate planner/rollback prompt instead of continuing.

The orchestrator owns final verdict consolidation, state update, and next
prompt creation.

## Required Validation

Run exactly:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m150_primitive_call_expression.py tslgen/tests/test_m151_primitive_call_consolidation.py tslgen/tests/test_m1625_tsil_lexical.py tslgen/tests/test_m224_parsed_tiny_tsl_to_generated_project.py tslgen/tests/test_m230_source_body_lexical_region_boundary.py tslgen/tests/test_m233_recursive_tsil_keyword_region_lowering.py tslgen/tests/test_m234_pairwise_lowering_path_cleanup.py
find tslgen -type d -name __pycache__ -print
```

If the expected M234 test file has a different final name, the executor may
use that path, but the final report must state the exact command actually run
and why it differs.

## Expected Output

Before finishing:

- Update `docs/redesign/implementation-roadmap.md` with the M234 result.
- Update `docs/redesign/design-decisions.md` if a compatibility quarantine is
  accepted or if the recursive fragment contract is revised.
- Update `docs/redesign/open-questions.md` if cleanup cannot be completed from
  current evidence.
- Create the next concrete prompt under `docs/agent/runs/`.
- Update `docs/agent/current-redesign-state.md` to point at the next prompt.

The likely next milestone after accepted M234 is the first keyword-specific
semantic consumer over the recursive fragment tree. Do not start it in M234.

## Final Report

Report:

1. Implementation summary.
2. Review verdict and any follow-ups.
3. Exact files changed.
4. Validation commands and exact results.
5. Next active prompt path.
