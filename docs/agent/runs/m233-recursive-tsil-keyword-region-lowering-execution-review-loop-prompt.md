# M233 Recursive TSIL Keyword Region Lowering Execution-Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M232 as accepted.

This prompt selects a lowering implementation milestone. Use the
executor-review loop specified below. The purpose of this milestone is to
correct the active lowering direction: composed TSIL keywords are not special
case pairs such as `emit_return + intrin_compose`. They are recursively nested
source-owned lexical regions. A future keyword should need one keyword handler,
not one handler per possible surrounding context.

## Accepted State

Accepted through:

```text
Milestone 230: Source Body Lexical Region Boundary
Milestone 231: Emit Return Lexical Region Lowering
Milestone 232: Return Payload Region Rescan Adapter
```

M230 can scan source-owned TSIL body text for balanced keyword-shaped lexical
regions and raw segments. M231 lowers only `emit_return` lexical regions into
source-owned return directives. M232 can rescan a return payload span and wrap
the resulting M230 raw segments and lexical regions with return provenance.

M233 must not continue the context-combination pattern. In particular,
`intrin_compose` inside `emit_return` is not a special case. The same
recursive keyword-region logic must work for `intrin_compose` inside
`emit_return`, inside `call`, inside a control body, or inside any other raw
span that the accepted scanner recognizes.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/tsil-surface-inventory.md`
- `tslgen/src/tslgen/syntax/source_body_regions.py`
- `tslgen/src/tslgen/lowering/emit_return_regions.py`
- `tslgen/src/tslgen/lowering/backend_intrinsics.py`
- `tslgen/src/tslgen/lowering/backend_intrinsic_handoff.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/tests/test_m230_source_body_lexical_region_boundary.py`
- `tslgen/tests/test_m231_emit_return_lexical_region_lowering.py`
- `tslgen/tests/test_m232_return_payload_region_rescan_adapter.py`
- Representative source evidence:
  - `tsldata/primitives/arithmetic/fundamental.tsl`
  - `tsldata/primitives/conversion/cast.tsl`
  - `tsldata/primitives/memory/load.tsl`

## Goal

Add a small recursive lowering boundary over M230 lexical regions:

```text
SourceBodyFragmentSequence
  fragments: tuple[SourceBodyFragment, ...]

SourceBodyFragment =
  RawSourceFragment
  KeywordRegionFragment

KeywordRegionFragment
  source_region: SourceBodyLexicalRegionCandidate
  keyword: SourceBodyKeyword
  selector_fragments: SourceBodyFragmentSequence | None
  payload_fragments: SourceBodyFragmentSequence | None
  body_fragments: SourceBodyFragmentSequence | None
```

Names may differ if the executor finds better local names, but the shape must
stay conceptually this small: raw source fragments plus keyword-region
fragments, recursively nested only through spans already owned by M230
lexical regions.

This is not a full TSIL parser. It is a recursive scanner/lowering shell over
recognized keyword islands. Raw C++/Rust-looking text, operators, assignments,
array accesses, helper calls such as `details::*`, and unknown text remain raw
source fragments.

## Executor Task

Use a single write-capable executor.

Implement the smallest maintainable slice that:

1. Adds a shared recursive function that consumes `SourceBodyText` or an M230
   `SourceBodyLexicalScanResult` and returns a typed fragment sequence plus
   diagnostics.
2. Reuses M230 `scan_source_body_text` for each recursively scanned child
   span. Do not duplicate delimiter matching or create keyword-specific regex
   rescanners.
3. Converts every M230 `SourceBodyRawSegment` into a raw fragment preserving
   source text and source location exactly.
4. Converts every M230 `SourceBodyLexicalRegionCandidate` into a keyword
   region fragment preserving the original M230 region as provenance.
5. Recursively scans every present child span that M230 has already identified:
   selector payload, parenthesized payload, and braced body. If a child span
   has no recognized keyword regions, it remains a raw fragment sequence.
6. Propagates M230 diagnostics from the root scan or any recursive child scan.
   Malformed regions are diagnostics and raw/source-owned boundaries, not
   source repair opportunities.
7. Adds a context-independent extraction/adaptation helper for
   `SourceBodyKeyword.INTRIN_COMPOSE` keyword fragments that builds existing
   `BackendIntrinsicRequest(intrinsic_kind="intrin_compose", ...)` values
   directly from the preserved M230 spans:
   - `angle_payload_text` from `region.selector.payload_span.text`;
   - `angle_payload_source` from `region.selector.payload_span.start`;
   - `argument_text` from `region.payload.payload_span.text`;
   - `argument_source` from `region.payload.payload_span.start`;
   - `source_text` from `region.full_span.text`;
   - `source` from `region.full_span.start`.
8. Finds/adapts `intrin_compose` requests anywhere in the recursive fragment
   tree, independent of ancestor context. Positive coverage must include at
   least:
   - `emit_return(intrin_compose<add>(left, right))`;
   - `call<primitive=foo>(intrin_compose<bar>(value))`;
   - an `intrin_compose` region inside a braced body such as
     `if<generation>(...){ emit_return(intrin_compose<...>(...)) }`.
9. Rejects malformed `intrin_compose` fragments missing selector or payload
   with diagnostics. Do not repair source or infer missing delimiters.
10. Does not call `discover_backend_intrinsic_requests_in_text`,
    `lower_backend_intrinsic_discovery`, or any previous raw-text island
    discovery path for this adapter. M230 already owns lexical discovery.

## Out Of Scope

- Full TSIL statement or expression parsing.
- Operator parsing, precedence, associativity, assignment parsing, array-access
  parsing, or target-language semantic interpretation.
- Argument splitting for `call`, `intrin_compose`, `cast`, `mem`, `io`, or
  control keywords.
- Modifier semantic lowering.
- Backend intrinsic handoff lowering.
- Backend value/type query lowering.
- Primitive-call resolution or dependency closure.
- Generation/control-flow evaluation.
- Adding new keyword heads beyond the already accepted M230 lexical region
  heads unless a tiny test fixture needs a custom head only to prove scanner
  configurability.
- Rendering, generated project writing, fixture resumption, or build
  verification.
- Runtime dependency on `frozen/` or `tslgenold`.
- Growing `outer_parser.py`, `parser.py`, `lowerer.py`, or
  `generated_primitive_pipeline.py`.

## Required Anti-Regression Checks

The executor and reviewers must explicitly verify:

- No class or function name encodes a pairwise context combination such as
  `EmitReturnIntrinCompose`.
- No tests prove only `emit_return + intrin_compose` while ignoring the same
  nested keyword under another parent.
- No helper assumes a fixed ancestor keyword when adapting `intrin_compose`.
- No raw source text is reparsed through the older intrinsic text-discovery
  path after M230 has already produced a region.
- The resulting API makes adding one future keyword a matter of adding one
  keyword-specific semantic consumer, not adding consumers for every possible
  surrounding TSIL construct.

## Review Loop

After the executor finishes, run read-only review/audit subagents:

1. Lowering-boundary reviewer: checks that M233 implements recursive
   keyword-region lowering over M230 regions and does not special-case
   `emit_return + intrin_compose`.
2. Evidence auditor: checks real `tsldata` coverage and synthetic minimal
   coverage for nested `intrin_compose` under at least two distinct parents.
3. Complexity reviewer: checks no new broad TSIL parser, no payload-token
   taxonomy beyond raw fragments plus keyword fragments, no registry/worklist
   machinery, no backend handoff/rendering creep, and module-size guardrails.
4. Diagnostics reviewer: checks malformed child-region diagnostics, source
   locations, and no source repair.

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
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m1625_tsil_lexical.py tslgen/tests/test_m230_source_body_lexical_region_boundary.py tslgen/tests/test_m231_emit_return_lexical_region_lowering.py tslgen/tests/test_m232_return_payload_region_rescan_adapter.py tslgen/tests/test_m233_recursive_tsil_keyword_region_lowering.py
find tslgen -type d -name __pycache__ -print
```

If the expected M233 test file has a different final name, the executor may
use that path, but the final report must state the exact command actually run
and why it differs.

## Expected Output

Before finishing:

- Update `docs/redesign/implementation-roadmap.md` with the M233 result.
- Update `docs/redesign/design-decisions.md` only if implementation revises
  the accepted parser/body/lowering boundary.
- Update `docs/redesign/open-questions.md` if a lowering issue cannot be
  resolved from evidence.
- Create the next concrete prompt under `docs/agent/runs/`. If M233 is
  accepted, that prompt must be M234 pairwise lowering path cleanup/refactor.
- Update `docs/agent/current-redesign-state.md` to point at the next prompt.

The required next milestone after accepted M233 is M234 pairwise lowering path
cleanup/refactor. M234 must remove, quarantine, or replace the old
context-combination paths with consumers over the recursive fragment tree,
including at least:

- `CatalogBuilder._classify_emit_return_payload_tokens`;
- `Lowerer._primitive_call_expression_result_from_exact_emit_return_body`;
- the `emit_return` special branch in
  `Lowerer._exact_add_primitive_call_fragment_from_body`;
- any tests that only protect `emit_return + call` or
  `emit_return + intrin_compose` instead of context-independent keyword
  traversal.

Do not select a keyword-specific semantic consumer milestone after M233 until
M234 has removed or explicitly quarantined those pairwise paths.
Do not start M234 in M233.

## Final Report

Report:

1. Implementation summary.
2. Review verdict and any follow-ups.
3. Exact files changed.
4. Validation commands and exact results.
5. Next active prompt path.
