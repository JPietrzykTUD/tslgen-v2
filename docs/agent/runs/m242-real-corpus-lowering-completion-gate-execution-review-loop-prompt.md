# M242 Real Corpus Lowering Completion Gate Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M241 as accepted.

This is an implementation task focused on lowering confidence and closure. Use
the executor-review loop:

```text
single write-capable executor
-> read-only reviewer/auditor subagents
-> focused revision executor if `Needs Revision`
-> focused re-review
-> next-run prompt generation
```

The orchestrator owns final state and next-prompt updates.

## Accepted State

Accepted through:

```text
Milestone 241: Primitive Profile Artifact Presentation Boundary
```

M187 declared lowering complete by the then-current contract. M188-M241 moved
into backend/output infrastructure. Before backend rendering grows further,
M242 must make the lowering completion claim airtight against the real
`tsldata/primitives/**/*.tsl` corpus, in one capstone milestone. If this gate
passes, the next milestone must pivot to backend/rendering. If this gate finds
a real missing generation-relevant TSIL family, record it precisely and select
one focused follow-up before backend expansion.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/tsil-surface-inventory.md`
- `docs/agent/runs/m229-outer-tsl-declaration-parser-boundary-execution-review-loop-prompt.md`
- `docs/agent/runs/m230-source-body-lexical-region-boundary-execution-review-loop-prompt.md`
- `docs/agent/runs/m231-emit-return-lexical-region-lowering-execution-review-loop-prompt.md`
- `docs/agent/runs/m233-recursive-tsil-keyword-region-lowering-execution-review-loop-prompt.md`
- `docs/agent/runs/m236-recursive-payload-fragment-diagnostic-propagation-execution-review-loop-prompt.md`
- `docs/agent/runs/m187-post-m186-lowering-completion-gate-execution-review-loop-prompt.md`
- `tsldata/primitives/**/*.tsl`
- `tslgen/src/tslgen/syntax/parser.py`
- `tslgen/src/tslgen/syntax/ast.py`
- `tslgen/src/tslgen/pipeline/catalog_builder.py`
- `tslgen/src/tslgen/lowering/`
- `tslgen/tests/test_m229_outer_tsl_declaration_parser_boundary.py`
- `tslgen/tests/test_m231_emit_return_lexical_region_lowering.py`
- `tslgen/tests/test_m233_recursive_tsil_keyword_region_lowering.py`
- `tslgen/tests/test_m236_recursive_payload_fragment_diagnostic_propagation.py`

## Goal

Prove, in one real-corpus lowering capstone, that accepted lowering supports
the generation-relevant TSIL keyword surface currently observed in
`tsldata/primitives/**/*.tsl`, or produce a precise bounded list of remaining
unsupported generation-relevant families.

This milestone is not one primitive and not one observed combination. It is a
lowering completion gate:

```text
real .tsl primitive files
-> parsed outer TSL declarations
-> implementation body lexical regions
-> accepted recursive TSIL keyword/token lowering
-> typed lowering facts, typed backend/source handoff requests, or diagnostics
-> deterministic corpus characterization
```

## Scope

Implement the smallest real-corpus audit/fixture boundary that proves:

- Every `tsldata/primitives/**/*.tsl` file is considered.
- Implementation body regions are obtained through accepted parser/body
  boundaries, not regex ladders over outer TSL declarations.
- All observed generation-relevant TSIL keyword islands in primitive
  implementation bodies are discovered through the accepted lexical region and
  recursive token machinery.
- Supported islands lower into accepted typed lowering facts, typed handoff
  requests, or typed diagnostics.
- Unsupported islands are classified by TSIL keyword family and exact source
  shape, with source path, line, and column provenance.
- The characterization is deterministic and can be used as an exit gate for
  backend/rendering progress.

Generation-relevant TSIL keyword families include, at minimum, the families
already accepted in the lowering contract and surface inventory:

- `emit_return(...)`
- `intrin<...>(...)`
- `intrin_compose<...>(...)`
- `call<primitive=...>(...)`
- `type<generation>(...)`
- `type<backend>(...)`
- `value<generation>(...)`
- `value<backend>(...)`
- `let<type>(...)`
- `if<generation>(...)`, `else<generation>`
- backend/control handoff forms such as `if<runtime>`, `else<runtime>`,
  `if<compile>`, `else<compile>`, `switch<...>`, and `loop<...>`
- source-operation handoff families such as `cast<...>(...)`,
  `mem<...>(...)`, and `io<...>(...)`
- generic/source helper families already accepted as backend/source handoff,
  such as `generic::*`

If the actual inventory contains an additional generation-relevant TSIL family,
record it and classify it. If it is already handled by accepted recursive
lowering, include it in the supported characterization. If not, stop short of
implementing a broad new lowering feature and report it as the reason the gate
cannot declare closure.

## Required Output Of The Milestone

Add a focused test and, if useful, a small typed characterization helper that
answers:

- number of primitive `.tsl` files considered;
- number of implementation body regions considered;
- observed TSIL keyword families and counts;
- supported lowered families and counts;
- unsupported or malformed families and representative source locations;
- confirmation that nested keywords are handled recursively, not through
  pairwise combinations such as `emit_return + intrin_compose`;
- confirmation that raw target-language text remains raw text unless it is a
  documented TSIL keyword island.

This output may live in a test helper or deterministic test assertions. Do not
write persistent report artifacts in M242.

## Guardrails

- Do not render generated artifacts.
- Do not call C++ or Rust backend renderers.
- Do not assemble intrinsic names or translate intrinsic suffix/prefix values
  beyond already accepted typed backend handoff/lowering behavior.
- Do not write files, run build verification, or touch generated-project
  composition.
- Do not implement primitive selection, dependency closure, wildcard expansion
  for generation, or full backend output.
- Do not parse target-language expressions, statements, returns, assignments,
  braces, semicolons, or operators.
- Do not introduce pairwise keyword-combination lowering. Nested TSIL keywords
  must continue to use the accepted recursive token/lowering boundary.
- Do not add regex ladders to parse outer TSL declaration structure.
- Do not treat source-data flaws as syntax to support. Preserve diagnostic
  boundaries for malformed or unsupported source.
- Do not make `frozen/` or `tslgenold/` runtime dependencies.

## Exit Criteria

M242 may declare lowering complete enough to proceed to backend/rendering only
if the real-corpus characterization shows one of these:

1. All observed generation-relevant TSIL keyword islands lower through accepted
   typed lowering/handoff paths; or
2. Remaining unsupported islands are explicitly non-generation-relevant raw
   target-language text or recorded source-data flaws/deferred backend-only
   helpers, not missing lowering capability.

If M242 finds an unsupported generation-relevant TSIL keyword family that
prevents real generation, the next prompt must be one focused lowering
follow-up for that family. Otherwise the next prompt must pivot to
backend/rendering, preferably the next primitive-template-backed C++/Rust
function rendering slice.

## Expected Tests

Add focused tests, likely in:

```text
tslgen/tests/test_m242_real_corpus_lowering_completion_gate.py
```

Cover:

- The real `tsldata/primitives/**/*.tsl` corpus is scanned deterministically.
- All primitive files parse through accepted parser/catalog/body boundaries.
- Observed TSIL keyword families are counted deterministically.
- Supported families lower into typed facts/handoffs/diagnostics without raw
  target-language interpretation.
- At least one real nested body, such as a real
  `emit_return(intrin_compose<...>(...));` occurrence, is proven to lower via
  recursive token lowering rather than a pairwise combination special case.
- Unsupported families, if any, have stable classification and source
  provenance.
- Guards prove the slice does not render artifacts, call backend renderers,
  write files, run build verification, or inspect `frozen/` / `tslgenold`.

Keep implementation proportional: a typed characterization helper is welcome;
a new pipeline stage, new broad IR family, generated report system, or backend
renderer is not.

## Out Of Scope

- Primitive profile rendering.
- Backend intrinsic invocation assembly.
- C++/Rust intrinsic call rendering.
- Function-shape rendering.
- Artifact writing.
- Build verification.
- Full real x86 fixture output.
- Dependency closure and primitive selection.
- Repairing malformed `.tsl` source.
- Adding new TSIL language features not observed in the real corpus.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m229_outer_tsl_declaration_parser_boundary.py tslgen/tests/test_m231_emit_return_lexical_region_lowering.py tslgen/tests/test_m233_recursive_tsil_keyword_region_lowering.py tslgen/tests/test_m236_recursive_payload_fragment_diagnostic_propagation.py tslgen/tests/test_m242_real_corpus_lowering_completion_gate.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Lowering/boundary reviewer: the capstone reuses recursive token lowering
   and does not introduce pairwise keyword-combination special cases.
2. Evidence reviewer: the characterization uses the real
   `tsldata/primitives/**/*.tsl` corpus and records accurate source
   provenance without synthetic body construction.
3. Test reviewer: coverage is enough to make the lowering completion claim
   credible and does not broaden into output generation.
4. Documentation reviewer: roadmap/state/design-doc consistency, exit
   criteria, and follow-ups are accurate.
5. Validation auditor: exact validation results and workspace hygiene.

If any reviewer returns `Needs Revision`, make only focused fixes for the
blocking issues and rerun the relevant focused review. If any returns
`Return To Planner` or `Reject`, stop implementation and create the
appropriate next prompt.

## Completion Rules

Before finishing:

- update `docs/redesign/implementation-roadmap.md` with the execution result;
- update `docs/redesign/behavioral-spec.md` or
  `docs/redesign/design-decisions.md` if behavior or architecture changes;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- if the exit criteria pass, make that next prompt a backend/rendering prompt,
  not another lowering-confidence prompt;
- do not start the next milestone inside M242.

## Final Report

Report:

1. Implementation summary.
2. Corpus characterization summary.
3. Lowering completion verdict: pass to backend/rendering, or blocked by a
   named missing generation-relevant TSIL family.
4. Review/audit verdicts.
5. Validation commands and exact results.
6. Any follow-ups.
7. Next active prompt path.
