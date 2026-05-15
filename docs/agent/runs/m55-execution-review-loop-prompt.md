# Milestone 55 Execution Review Loop Prompt

You are the Codex orchestrator for Milestone 55.

Milestones 1 through 54 are accepted. Post-M54 planning is accepted and
selected:

```text
Milestone 55: Base Scalar Size-Bytes Generation Value Query Slice
```

This prompt runs the milestone through the executor -> reviewer -> focused
revision -> next-prompt loop.

Do not start Milestone 56.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/codex-workflow.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/agent/subagents/executor.md`
- `docs/agent/subagents/reviewer.md`
- `docs/agent/subagents/validation-auditor.md`
- `docs/agent/subagents/boundary-auditor.md`
- `docs/agent/subagents/docs-auditor.md`
- `docs/agent/subagents/evidence-auditor.md`
- `docs/agent/subagents/next-prompt-generator.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/open-questions.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/frozen-parity-baselines.md`

## Milestone Scope

M55 implements exactly one generation-time semantic lowering value-query slice:

```text
value<generation>(type::size_bytes(type<generation>(base::in)))
```

The slice must:

- Produce typed integer generation values for exactly these selected scalar
  base tags and byte values:

  ```text
  si8/ui8 -> 1
  si16/ui16 -> 2
  si32/ui32/f32 -> 4
  si64/ui64/f64 -> 8
  ```

- Introduce explicit typed scalar size-byte rule/value records, or equivalent
  immutable typed values.
- Build or expose scalar size-byte rules from typed catalog/type-group data
  before lowering evaluation, following the M54 lowering-input pattern.
- Resolve the exact nested helper through the existing selected type-tag
  context precedence: explicit override, context selected tag, then selected
  candidate tag when enabled.
- Carry the lowered result as a typed generation value, such as
  `GenerationValue(kind="type.size_bytes", value=<int>, type_tag=<tag>)`, or an
  equivalent immutable value object.
- Preserve all accepted M52-M54 concrete-integer type-query, signedness branch,
  rule-source, and catalog-wiring behavior.
- Accept `f32` and `f64` only for this exact size-bytes value query.
- Preserve backend-translation rejection of raw unresolved generation helpers
  and renderer non-evaluation.

## Out Of Scope

- Milestone 56 or any later milestone.
- Reusing or mutating `ConcreteIntegerGenerationRuleSet` for float size
  semantics.
- Broadening standalone `type<generation>(base::in)` or
  `base::signed_of` / `base::unsigned_of` behavior to floats.
- Inferring byte sizes from regex, tag spelling, wildcard/group selectors, or
  unselected concrete-looking tags such as `si128`.
- Treating `arith`, `f?`, `?i?`, `?i64`, `si?`, `ui?`, `dword`, `qword`,
  `idqword`, `dqword`, or other group selectors as selected scalar tags during
  lowering.
- `type::size_bytes(...)` over `base::signed_of`, `base::unsigned_of`,
  `vector::imask`, `vector::register`, backend types, aliases, casts, arrays,
  generics, pointers, masks, or vector metadata.
- Generation-value arithmetic or comparisons such as `* 8`, `== 2`,
  `else if<generation>`, or branch pruning based on size-byte values.
- Lowering enclosing IO, memory-copy, array, bit-count, conflict, conversion,
  load/store, loop, cast, call, direct `intrin<...>`, `switch<compile>`, or
  `if<compile>` bodies.
- Backend suffix/type-spelling expansion, backend type/value translation,
  C++ or Rust rendering, generated output, generated test sources,
  CLI/reporting, writer behavior, compiler execution, generated-test
  execution, broad TSIL parsing, or runtime dependency on `frozen/`.
- Lowering reading files, parsing raw TSL, or querying the catalog during
  evaluation.
- Renderer-side semantic inference or evaluation of generation-time helpers.
- Backend translation parsing raw generation helper text.

## Evidence

- `tsldata/detail/types.tsl:2-9` for integer singleton tags.
- `tsldata/detail/types.tsl:17-19` for `f32` and `f64` singleton tags plus the
  `f?` group that remains unsupported as a selected tag.
- `tsldata/detail/types.tsl:10-16`, `:20-26` for wildcard/group selectors that
  must remain unsupported as selected scalar tags.
- `tsldata/primitives/io/out.tsl:7` and `:43-52` for `arith` IO evidence with
  integer and float tests using the exact helper.
- `tsldata/primitives/bitwise/bit_counts.tsl:91-99` for float bit-count
  evidence using the exact helper.
- `tsldata/primitives/load_store/array.tsl:101-109` for array/SVE comparison
  evidence. M55 selects only the nested value query, not the comparisons or
  branch bodies.
- `tsldata/primitives/misc/conflict.tsl:59-79` for integer conflict evidence.
- Existing M52-M54 tests in `tslgen/tests/unit/test_lowering_boundary.py` and
  `tslgen/tests/unit/test_concrete_integer_generation_rules.py`.
- `frozen/` remains evidence only and is not needed for the selected M55 slice.

## Required Tests

- Focused unit tests proving the exact size-bytes query returns `1`, `2`, `4`,
  or `8` for every selected scalar tag.
- Tests proving `f32` and `f64` are accepted only for the exact size-bytes
  query and do not broaden standalone `base.in` or signed/unsigned companion
  behavior.
- Context precedence tests for type-tag override, context-selected tag, and
  selected candidate default.
- Diagnostics for missing type context, malformed value query syntax, wrong
  arity, unsupported nested operands, unsupported wildcard/group tags,
  pointers, masks, unknown tags, and concrete-looking unselected tags such as
  `si128`.
- Tests proving malformed or incomplete explicit scalar size rule data is not
  hidden by a synthetic fallback.
- Regression tests proving all accepted M52-M54 type-query, signedness branch,
  rule-source, and catalog-wiring behavior remains unchanged.
- Boundary tests proving backend translation still rejects raw unresolved
  generation helpers and renderers remain non-evaluating.
- Determinism tests for repeated query and rule construction.

Golden fixtures required:

- None. M55 is a lowering/value-query slice and must not change generated C++
  or Rust output.

## Phase 1: Executor

If M55 has not already been implemented in the current worktree, spawn exactly
one write-capable executor subagent to implement it.

The executor is not alone in the codebase: it must not revert edits made by
others, and it must adjust its implementation to accommodate existing changes.
The executor owns only the M55 implementation, tests, fixtures, and necessary
documentation updates. It must not modify workflow state or create the next run
prompt unless the orchestrator explicitly delegates that final workflow step.

If M55 has already been implemented and `docs/agent/current-redesign-state.md`
says it is awaiting review, skip implementation and proceed to Phase 2.

The executor must produce a review packet and run required validation.

## Phase 2: Review/Audit Subagents

Spawn these read-only subagents and wait for all results:

1. Reviewer subagent:
   Review the M55 implementation using `docs/agent/review-checklist.md` and the
   scope in this prompt. Return exactly one verdict.
2. Validation auditor subagent:
   Run or verify the relevant validation commands and summarize exact results.
   Do not edit files.
3. Boundary auditor subagent:
   Verify M55 remains a generation-time semantic lowering value-query slice and
   does not leak into standalone float `base.in` behavior, signed/unsigned
   float companion semantics, size inference from tag spelling, arithmetic or
   comparisons over generation values, surrounding body lowering, backend
   translation expansion, backend rendering, generated output, generated test
   sources, Rust, CLI/reporting, writer behavior, compiler execution,
   generated-test execution, vector/register metadata, broad TSIL parsing,
   generalized branch semantics, renderer-side helper evaluation, backend
   parsing of raw helper text, lowering-time file/catalog/raw-TSL reads, or
   runtime reads from `frozen/`. Do not edit files.
4. Documentation auditor subagent:
   Check M55 docs/state for stale wording, overclaims, missing deferrals, and
   consistency with the roadmap, behavioral spec, testing strategy,
   generation-time semantic lowering spec, target architecture, pipeline
   design, design decisions, open questions, and frozen parity baselines. Do
   not edit files.
5. Evidence auditor subagent:
   Check evidence/provenance claims for the selected scalar size-bytes query
   and confirm `frozen/` remains evidence only. Do not edit files.

## Phase 3: Consolidated Verdict

The orchestrator consolidates the subagent results into one verdict:

- `Accept`
- `Accept With Follow-Ups`
- `Needs Revision`
- `Return To Planner`
- `Reject`

## Phase 4: Revision Loop If Needed

If the consolidated verdict is `Needs Revision`:

1. Identify only blocking issues.
2. Spawn exactly one focused revision executor subagent.
3. The revision executor may edit only files required to fix blocking issues.
4. Run focused validation.
5. Spawn read-only focused re-review subagents for the changed scope.
6. Repeat only if issues remain local and bounded.
7. Stop after two revision loops and return the remaining blocking issues if
   still unresolved.

If the verdict is `Return To Planner` or `Reject`, do not revise. Create the
appropriate planner, redesign, rollback, or stop prompt under
`docs/agent/runs/` and update `docs/agent/current-redesign-state.md`.

## Phase 5: Next Prompt Generation

If the final verdict is `Accept` or `Accept With Follow-Ups`:

1. Record follow-ups in `docs/agent/current-redesign-state.md` if needed.
2. Mark accepted through Milestone 55.
3. Create the next concrete prompt under `docs/agent/runs/`.
4. Update `docs/agent/current-redesign-state.md` to point at the next prompt.

If no Milestone 56 is already selected by an accepted planning result, create a
post-M55 planning-plus-review prompt. Do not start Milestone 56 from this
execution-review loop.

## Required Validation

At minimum, ensure these have been run or verified:

```bash
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_concrete_integer_generation_rules.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

Run the new focused scalar size-byte rule/value test command selected by the
executor. Use compileall, ruff, and mypy for changed Python files if
implementation or revision touched code/tests. If implementation discovers a
narrower or renamed targeted command, record the exact command and reason in
the review packet.

## Final Output Format

Return:

1. Executor status.
2. Review subagents spawned.
3. Consolidated verdict.
4. Revision loop count.
5. Files changed.
6. Validation commands and exact results.
7. Follow-ups recorded.
8. Next run prompt created.
9. Current state updated: yes/no.
