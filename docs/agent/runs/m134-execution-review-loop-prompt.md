# M134 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M133:

```text
Milestone 134: Tiny Clean Scalar Width Type Descriptor Lowering Slice
```

Milestones 1 through 133 are accepted. M106 moved the pre-restart top-level
`tslgen/` tree to `tslgenold/` as evidence-only old state. M107-M133 built the
tiny clean restart path from explicit `.tsl` source loading through
multi-document and multi-implementation catalog construction, explicit target
selection, selected-implementation lowering, backend emission, artifact
writing, focused scalar operation expansion, bootstrap-core semantic origins,
deterministic source-set generation, exact binary/unary/comparison TSIL
emit-return body spellings, exact binary operator TSIL body spellings,
declared binary parameter preservation, and exact remaining binary operator
TSIL body spellings.

M134 keeps the next task focused on lowering. It broadens the tiny clean scalar
type descriptor set beyond the current 32-bit integer baseline by adding common
8-bit, 16-bit, and 64-bit integer scalar descriptors. This makes future `.tsl`
edits to explicit scalar type tags product input rather than requiring code
changes for every ordinary integer width.

This milestone is not a broad type system or corpus type-group loader. It adds
only explicit lowering-owned scalar descriptors and backend-owned C++/Rust
type spellings for already-known scalar type tags.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/kiss-generator-restart.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/open-questions.md`
- current clean parser/catalog/selection/lowering/backend implementation under
  `tslgen/src/tslgen/`
- current tiny-pipeline tests in `tslgen/tests/test_m107_tiny_pipeline.py`

## Goal

Allow explicit tiny clean scalar implementations and targets for these new
integer type tags:

```text
si8, ui8, si16, ui16, si64, ui64
```

For example:

```text
prim<v:=(v,v)> add(left, right):
  implementation scalar si16:
    tsil "emit_return(left + right);"
```

with target:

```python
Target(backend="rust", primitive_name="add", extension="scalar", type_tag="si16")
```

should lower through a typed `ScalarTypeDescriptor(tag="si16", family="integer",
bit_width=16, signedness="signed")` and generate backend-owned Rust/C++ type
spellings from the backends, not from lowering.

## Required Executor Task

Run exactly one write-capable executor for M134. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Add lowering-owned scalar descriptors for `si8`, `ui8`, `si16`, `ui16`,
   `si64`, and `ui64`, preserving existing descriptors for `si32`, `ui32`,
   `f32`, and `f64`.
3. Preserve descriptor fields: tag, kind, family, bit width, and signedness.
   Do not put C++ or Rust spelling text in lowering descriptors.
4. Add backend-owned type spellings for the new scalar tags:
   - C++: `std::int8_t`, `std::uint8_t`, `std::int16_t`, `std::uint16_t`,
     `std::int64_t`, `std::uint64_t`;
   - Rust: `i8`, `u8`, `i16`, `u16`, `i64`, `u64`.
5. Preserve existing backend-owned spellings for `si32`, `ui32`, `f32`, and
   `f64`.
6. Preserve existing binary, unary, and comparison operation descriptors and
   exact source-body forms from M107-M133.
7. Update operation/type compatibility only as needed for the expanded scalar
   descriptor set:
   - ordinary arithmetic binary operations without an explicit restriction
     continue to support all scalar descriptors;
   - integer-only binary operations (`mod`, bitwise ops, shifts) support all
     integer descriptors and still reject floating descriptors;
   - comparison operations continue to lower for all scalar descriptors;
   - unary `bit_not` supports integer descriptors and rejects floating
     descriptors;
   - unary `neg` supports signed integer and floating descriptors and rejects
     unsigned descriptors.
8. Prove generated C++/Rust artifacts for representative new types across
   binary, unary, and comparison lowering. Include at least:
   - one signed narrow integer arithmetic case;
   - one unsigned narrow integer bitwise or shift case;
   - one 64-bit integer case;
   - one unary `bit_not` case on a new integer type;
   - one unary `neg` case on a new signed integer type;
   - one comparison case on a new integer type.
9. Prove unsupported or out-of-scope type tags, such as `si128` or vector-like
   tags, still produce structured `TSL-LOWER-UNSUPPORTED-TYPE` diagnostics and
   are not normalized or inferred.
10. Prove floating scalar descriptors remain rejected for integer-only
    operations after the descriptor expansion.
11. Preserve deterministic descriptor ordering, generated artifact ordering,
    diagnostics, and representative existing artifact bytes where the selected
    type remains unchanged.
12. Update docs only for behavior, decisions, open questions, or workflow state
    revealed by this slice.

## Out Of Scope

- Broad `tsldata` type groups, lane sets, vector/register metadata, mask
  types, immediate types, pointer/reference types, extension-specific type
  shapes, or backend manifest/YAML type-map loading.
- Parsing broad corpus layout, nested implementation maps, multiple primitive
  blocks in one document, attributes, tests, descriptions, `requires` clauses,
  type groups, extension fallback, dependency closure, or target discovery.
- Broad TSIL parsing, primitive calls, intrinsics, helper calls such as
  `details::arith_mul(...)`, casts, variables, immediates, multiple statements,
  multiline TSIL bodies, helper evaluation, branch pruning, source repair, or
  TSIL compiler behavior.
- Scalar shift-count signatures such as `v:=(v,s)` or `v:=(v,sImm)`,
  immediate parameters, runtime/immediate shift-count range policy, integer
  promotion policy, overflow/wrapping policy, arithmetic-vs-logical right
  shift policy beyond already accepted operation/type compatibility, or
  generated-code execution semantics.
- Adding operation ids, backend operator spellings, primitive aliases, target
  discovery, registries, dispatchers, callback maps, plugin systems, hidden
  backfeeds, fixpoint mechanisms, broad operation frameworks, or new lowering
  IR category/request/result families.
- Loading operation semantics, compatibility rules, type aliases, or backend
  spellings from `tsldata/`, backend manifests, YAML, `frozen`, `tslgenold`,
  plugins, or environment configuration at runtime.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M134 is a focused scalar descriptor/type
   lowering slice and does not add broad type systems, broad TSIL parsing,
   corpus loading, target discovery, aliases, backend manifests, source
   repair, scalar shift-count signatures, or IR ceremony.
2. Boundary auditor: verify `frozen/`, `tslgenold/`, and `tsldata/` remain
   evidence/source inputs only and are not runtime shortcuts for type lookup,
   compatibility evaluation, implementation selection, lowering, or backend
   spellings.
3. Documentation auditor: verify behavior, roadmap, design decisions, and
   workflow state remain coherent and do not describe M134 as broad type-group
   loading, corpus ingestion, backend manifest loading, CLI/writer work,
   vector/SIMD support, source repair, or old migration work.
4. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -c "from tslgen import Generator, Target, generate_from_paths"
python -B -m py_compile tslgen/src/tslgen/syntax/parser.py tslgen/src/tslgen/syntax/ast.py tslgen/src/tslgen/pipeline/catalog_builder.py tslgen/src/tslgen/analysis/selection.py tslgen/src/tslgen/lowering/scalar_types.py tslgen/src/tslgen/lowering/operation_type_compatibility.py tslgen/src/tslgen/lowering/lowerer.py tslgen/src/tslgen/backends/cpp/backend.py tslgen/src/tslgen/backends/rust/backend.py tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

Remove any validation-created `__pycache__` directories before the final cache
check. Do not run the old `tslgenold` validation profile as proof of the clean
product slice.

## Completion Rules

If M134 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M134 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M134 is accepted. Select exactly one concrete M135 task, prefer a
high-value research-prototype step, and create the next execution-review-loop
prompt directly. Do not create a separate post-M134 planning prompt unless
review returns `Return To Planner`, `Reject`, or an explicit stop condition is
recorded.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 135 implementation in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
