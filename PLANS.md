# Planning And Execution Protocol

This repository is in a clean redesign phase. Planning and implementation must be organized around architectural slices, observable behavior, domain concepts, and pipeline boundaries — not around legacy modules.

The legacy implementation under `frozen/` is a source of evidence, not an architectural template.

## Agent Roles

This project uses three logical agent roles.

### 1. Redesign Planner

The planner derives or updates:

- requirements
- behavioral specifications
- domain model
- target architecture
- pipeline design
- implementation roadmap
- design decisions
- open questions

The planner may inspect `frozen/`, but only to discover behavior, inputs, outputs, edge cases, and implicit requirements.

The planner must not organize the new design around legacy modules.

### 2. Redesign Executor

The executor implements exactly one milestone from `docs/redesign/implementation-roadmap.md`.

The executor may perform bounded replanning when implementation reveals that the current plan is incomplete, inconsistent, or technically infeasible.

The executor must not silently diverge from the redesign.

### 3. Redesign Reviewer

The reviewer evaluates a completed milestone.

The reviewer checks:

- whether the implementation follows the clean redesign
- whether the milestone stayed in scope
- whether legacy architecture leaked into the new design
- whether tests cover the declared validation criteria
- whether documentation and design decisions were updated when needed
- whether unresolved issues require replanning

The reviewer should not implement fixes directly. It should produce a verdict and concrete issues for the executor or planner.

## Codex Subagent Protocol

Codex may use subagents for bounded, parallel work when explicitly requested.

Allowed subagent roles:

- Orchestrator: owns task decomposition, subagent coordination, final verdict
  consolidation, and updates to `docs/agent/current-redesign-state.md`.
- Planner: documentation and roadmap planning only.
- Executor: one milestone implementation in one branch or worktree.
- Reviewer: read-only milestone review; may run validation.
- Validation auditor: test, log, and diff-check triage only.
- Evidence auditor: source/evidence/provenance inspection only.
- Documentation auditor: redesign-doc consistency checks only.
- Boundary auditor: verifies pipeline and semantic boundary preservation.

Rules:

- Do not let two write-capable agents edit the same files or branch concurrently.
- Reviewers and auditors must not implement fixes.
- Executors must implement exactly one milestone.
- The main/orchestrator thread owns final state updates to
  `docs/agent/current-redesign-state.md`.
- Subagents must return concise structured summaries, not raw logs unless needed.
- If a design inconsistency appears, stop implementation and return to planner.
- If implementation is needed, use one writer in one worktree; parallelize only
  read-only review, validation, evidence, and documentation audits.

## Orchestrated Executor Review Loop

Codex may use an orchestrated execution loop when the active run prompt requests
it. This is the preferred mode for implementation milestones once the repo-local
Codex workflow is installed.

The loop is:

1. Spawn or designate one write-capable executor for the selected milestone.
2. Run the required validation.
3. Spawn read-only reviewer/auditor subagents.
4. Consolidate the review verdict.
5. If the verdict is `Needs Revision`, spawn one focused revision executor and
   then run a focused re-review. Repeat only for tightly scoped local fixes.
6. If the verdict is `Accept` or `Accept With Follow-Ups`, update
   `docs/agent/current-redesign-state.md` and create the next prompt under
   `docs/agent/runs/`.
7. If the verdict is `Return To Planner` or `Reject`, stop implementation and
   create the appropriate planner, rollback, or redesign prompt.

Rules:

- Do not let reviewer/auditor subagents edit files.
- Do not let two write-capable agents edit the same worktree concurrently.
- Revision executors must fix only the blocking issues named by the review.
- The orchestrator owns the final state transition and next-run prompt.
- The loop must preserve the one-milestone-at-a-time rule.

## Planning Loop

1. Select one milestone from `docs/redesign/implementation-roadmap.md`.
2. Read the milestone plus the relevant sections of:
   - `docs/redesign/requirements.md`
   - `docs/redesign/behavioral-spec.md`
   - `docs/redesign/domain-model.md`
   - `docs/redesign/target-architecture.md`
   - `docs/redesign/pipeline-design.md`
   - `docs/redesign/testing-strategy.md`
   - `docs/redesign/design-decisions.md`
   - `docs/redesign/open-questions.md`
3. State:
   - goal
   - scope
   - validation criteria
   - affected architectural boundary
   - expected tests
   - out-of-scope items
4. Inspect only the repository evidence needed for that milestone.
5. Implement a thin vertical slice.
6. Add or update tests.
7. Run targeted validation.
8. Update redesign docs when behavior, decisions, or open questions change.
9. Prepare a review packet for the redesign reviewer.
10. Address reviewer feedback or document why it is deferred.

## Scope Rules

A milestone scope should be small enough that a reviewer can answer:

- Which pipeline boundary was created or changed?
- Which domain concepts became explicit?
- Which behavior is now covered by tests?
- Which side effects are owned by this slice?
- Which public API, if any, was introduced?
- Which future extension point, if any, was enabled?

Every lowering milestone must also pass an IR taxonomy pressure check:

- Is this adding a durable semantic fact, request, result, inventory,
  provenance value, rule input, or stage envelope?
- Could repeated `source_*` object chains be replaced by a smaller typed
  provenance contract without losing diagnostics or object identity?
- Is the proposed class name describing a domain boundary rather than a trail
  of previous milestones?
- Would this make future lowering stages simpler to extend, or only add another
  one-off layer?

If the honest answer is "another one-off layer", plan a consolidation slice
before adding more feature-specific IR.

Lowering milestones that recognize operator-looking source text must also pass
an operator boundary check:

- Is the accepted spelling an exact documented `.tsl` source form in a narrow
  context, not an arbitrary C, C++, Rust, or TSIL expression?
- Does it map immediately to an existing typed TSL primitive semantic
  operation or explicit semantic concept?
- Are nearby malformed forms diagnostic boundaries rather than source repair?
- Do backend renderers consume typed lowering values instead of raw source
  text?

If the milestone would require precedence, associativity, casts, temporary
variables, mixed expressions, or general target-language operator support, it
is too broad for an exact lowering slice.

## Simplicity And End-To-End Slice Guardrails

Future planning must optimize for the shortest maintainable path from source
data to generated libraries, not for extending the existing micro-IR chain.
The accepted M57-M104 lowering path proved useful requirements, but it also
showed how quickly typed request/result/worklist layers can become too
ceremonial for a research prototype.

The generator architecture should make these concepts boring and explicit:

- `.tsl` source documents and parse results;
- a validated catalog of primitives, type/lane groups, extensions, templates,
  and backend translation metadata;
- target selection over backend, extension, type, attributes, and feature
  requirements;
- a small generator service coordinating catalog, selection, backend
  translation, rendering, and artifact writing;
- backend-specific C++ and Rust emitters behind narrow protocols;
- diagnostics with source locations.

Planning and execution must apply these pressure checks:

- Can a tiny fixture generate one deterministic C++ artifact and one
  deterministic Rust artifact sooner?
- Is this abstraction needed by at least two concrete stages right now?
- Can an OO object with clear ownership replace a chain of request/result
  wrappers?
- Would a future contributor adding a primitive, extension, concept, or backend
  know where to make the change?
- Is this stage doing product work, or only preserving previous milestone
  history?

When the answer points toward ceremony, simplify the design before coding.
Current M57-M104 artifacts remain evidence and regression material, but future
milestones should not extend them by default.

## Clean Implementation Layout

Repository layout is part of the architecture contract. The pre-restart
top-level `tslgen/` tree has been moved to `tslgenold/` as quarantined
old-state evidence, and the fresh top-level `tslgen/` is reserved for the new
implementation. Future milestones must not mix clean implementation code with
the old tree under the same package path.

Do not include:

- unrelated cleanup
- generated output churn
- broad refactors
- opportunistic redesign
- speculative abstractions
- legacy compatibility wrappers
- formatting-only changes mixed with architecture changes

A milestone must implement one coherent architectural slice, not a broad subsystem.

## Evidence Rules

Use `frozen/` only to discover required behavior. Cite concrete evidence in docs or PR notes, such as:

- TSL syntax in `frozen/tsl-gen/tsl_gen/tsl_data.lark`.
- Primitive examples in `tsldata/primitives/**.tsl`.
- Extension metadata in `tsldata/extensions/extension.tsl`.
- Type and lane groups in `tsldata/detail/types.tsl` and `tsldata/detail/lane_sets.tsl`.
- Template requirements in `tsldata/detail/templates.tsl`.
- Signature resolution in `frozen/generator_specs/signatures.yaml`.
- Backend manifest behavior in `frozen/generator_specs/backend_cpp.yaml` and `frozen/generator_specs/backend_rust.yaml`.
- Output workflows in `frozen/run_all.sh`.

Avoid evidence phrased as:

> the old module does X

Prefer:

> the repository requires behavior X, evidenced by file Y

The new architecture must be justified by requirements and domain concepts, not by old file structure.

## Thin Vertical Slice

A good implementation slice crosses boundaries in a controlled way. For example:

- Load source files into `SourceDocument` values.
- Parse one TSL block type into syntax nodes.
- Convert that block type into typed domain objects.
- Validate the objects and emit diagnostics.
- Expose the result through a small API and tests.

A poor slice recreates a broad legacy subsystem without typed boundaries.

A good slice should make at least one of the following explicit:

- a domain concept
- a pipeline boundary
- a validation rule
- a diagnostic behavior
- an extension point
- a deterministic output contract

## Bounded Replanning Protocol

During implementation, the executor may discover that the redesign documents are incomplete, inconsistent, or technically infeasible.

The executor must not silently diverge from the redesign.

Every replanning event must be classified.

### 1. Local Implementation Detail

Use this classification when:

- the redesign intent is clear
- only a minor implementation detail is missing
- the decision does not affect public architecture, domain model, pipeline boundaries, or observable behavior

Allowed action:

- make the smallest reasonable local decision
- mention it in the final report

Documentation update:

- optional, unless the detail is likely to affect future milestones

### 2. Documentation Gap

Use this classification when:

- the design is likely correct
- a required detail is underspecified
- the missing detail affects implementation clarity but not the overall architecture

Allowed action:

- proceed with the smallest reasonable interpretation
- update the relevant redesign document

Documentation update:

- update one or more of:
  - `docs/redesign/requirements.md`
  - `docs/redesign/behavioral-spec.md`
  - `docs/redesign/domain-model.md`
  - `docs/redesign/pipeline-design.md`
  - `docs/redesign/testing-strategy.md`

### 3. Design Inconsistency

Use this classification when:

- two or more redesign documents conflict
- the milestone cannot be implemented cleanly without choosing between incompatible designs
- proceeding would encode an arbitrary architectural choice

Allowed action:

- stop implementation
- document the blocker
- propose one or more resolutions

Documentation update:

- update `docs/redesign/open-questions.md`
- optionally draft an ADR in `docs/redesign/design-decisions.md`

Do not continue implementation until the inconsistency is resolved.

### 4. Invalid Architecture Assumption

Use this classification when:

- the redesign requires something technically infeasible
- repository evidence contradicts the design
- the design would create poor architecture
- the design would force legacy leakage
- the design would make future extension substantially harder

Allowed action:

- stop implementation unless the correction is minimal and tightly scoped
- propose a concrete architectural correction

Documentation update:

- add or update an ADR in `docs/redesign/design-decisions.md`
- update `docs/redesign/open-questions.md` if human review is needed

If the correction changes public architecture, pipeline stages, domain model, or extension points, do not continue implementation in the same pass.

### 5. Legacy Behavior Conflict

Use this classification when:

- the redesign conflicts with behavior observed in `frozen/`
- repository evidence suggests a behavior not captured in the redesign docs

Classify the observed behavior as one of:

- required behavior
- accidental legacy behavior
- unresolved behavior

Allowed action:

- if required, update the behavioral specification and continue only if the change is local
- if accidental, document it as rejected legacy behavior
- if unresolved, stop and document the question

Documentation update:

- update `docs/redesign/behavioral-spec.md`
- update `docs/redesign/requirements.md`
- update `docs/redesign/open-questions.md` if unresolved

## Allowed Replanning Scope

The executor may:

- refine the currently selected milestone
- split the milestone into smaller milestones
- update documentation to clarify implementation-relevant details
- add a local design decision
- propose architecture changes
- add ADR entries for discovered design decisions
- stop and return work to the planner when the issue exceeds execution scope

## Forbidden Replanning Scope

The executor must not:

- replace the overall architecture during execution
- rewrite the roadmap broadly
- implement a different milestone without explicitly stating the switch
- introduce legacy-compatible architecture merely because implementation is easier
- hide design changes inside code changes
- continue after discovering a blocking design inconsistency
- change public architecture without documenting the decision
- use old module boundaries as the new package structure

## Semantic Rule And Translation Boundary

When a milestone implements lowering or backend translation semantics, the executor must model the selected behavior as typed rules or typed evaluator
functions.

A selected rule must define:

- typed input values
- typed output values
- supported cases
- unsupported cases
- diagnostics
- deterministic ordering, if collections are involved
- tests proving raw helper text and unsupported forms do not bypass the rule

Dictionary-like source metadata may be preserved at the I/O/catalog boundary, but it must be promoted into typed boundary data before semantic lowering or backend translation consumes it. A raw dictionary lookup such as `(intrinsic, extension, type) -> emitted text` is acceptable only as a temporary selected-slice fixture if explicitly documented, reviewed, and prevented from
becoming the extension path.

Renderers must not perform semantic rule evaluation. They may only format typed lowered/translated values.

## Testing Protocol

For each milestone:

- Add unit tests for pure logic.
- Add fixture files when input behavior matters.
- Add golden files only when output text is intentionally stable.
- Add diagnostic tests for invalid input.
- Add determinism tests when ordering or output artifacts are involved.
- Add integration tests when the milestone crosses pipeline stages.
- Add regression tests against selected legacy behavior only when compatibility is explicitly required.

Use host-independent tests by default.

Hardware feature detection must be injectable or mocked.

Tests should validate the new design, not the old implementation structure.

## Documentation Protocol

Before finishing a milestone:

- Record newly discovered requirements in `docs/redesign/requirements.md`.
- Record behavior changes in `docs/redesign/behavioral-spec.md`.
- Record domain model changes in `docs/redesign/domain-model.md`.
- Record pipeline changes in `docs/redesign/pipeline-design.md`.
- Record decisions in `docs/redesign/design-decisions.md`.
- Record unresolved issues in `docs/redesign/open-questions.md`.

If a question blocks a clean implementation, stop and document the blocker instead of making speculative architecture.

Documentation updates are required when implementation changes:

- observable behavior
- domain terminology
- public APIs
- pipeline stage boundaries
- validation semantics
- diagnostics
- extension points
- output determinism guarantees

## Stop Conditions

Stop implementation and update `docs/redesign/open-questions.md` when:

- required observable behavior conflicts across repository evidence
- a backend contract cannot be inferred from data or templates
- a proposed abstraction would require guessing future requirements
- test expectations depend on hardware that is unavailable and not documented
- compatibility with generated output cannot be judged without a golden baseline
- redesign documents contradict each other
- implementation would require preserving bad legacy architecture
- the selected milestone is too broad to review as one slice
- the implementation would introduce hidden global state or unclear side effects
- the executor cannot define validation criteria for the slice

Stopping is preferable to encoding speculative architecture.

## Codex Run Files

Concrete Codex tasks should be written to `docs/agent/runs/`.

No Codex task is complete until it has written the next concrete prompt under
`docs/agent/runs/` and updated `docs/agent/current-redesign-state.md` to point
at it, unless the task intentionally ends the workflow and records an explicit
stop condition. When the next action depends on human acceptance, create a
finalization prompt that converts acceptance into the next concrete run prompt.
The transition matrix and filename rules live in
`docs/agent/next-run-prompt-protocol.md`.

Each run file should declare:

- role
- accepted state
- selected milestone or planning target
- files to read
- scope and out-of-scope items
- validation commands
- expected output format
- next run prompt expected from this task, unless the workflow stops

Reusable prompts belong in `docs/agent/prompt-templates/`; role definitions
belong in `docs/agent/subagents/`.

## Review Packet

Before handing work to the redesign reviewer, the executor must provide a review packet containing:

1. Selected milestone.
2. Original milestone scope.
3. Final implemented scope.
4. Whether replanning was needed.
5. Replanning classification, if any.
6. Files changed.
7. Architectural boundary created or changed.
8. Domain concepts introduced or changed.
9. Behavior now covered by tests.
10. Tests added or changed.
11. Checks run.
12. Documentation updated.
13. Known limitations.
14. Open questions.
15. Recommended next milestone.

The review packet should make the work reviewable without requiring the reviewer to rediscover the entire context.

## Reviewer Protocol

The redesign reviewer must read:

- `AGENTS.md`
- `PLANS.md`
- the selected milestone in `docs/redesign/implementation-roadmap.md`
- relevant files in `docs/redesign/`
- `docs/agent/review-checklist.md`
- the executor's review packet
- the code diff
- the tests added or changed

The reviewer evaluates the milestone against the clean redesign.

The reviewer must answer:

- Did the executor implement exactly one milestone?
- Is the implementation organized around the new domain model rather than the legacy structure?
- Are pipeline boundaries explicit?
- Are side effects isolated?
- Are diagnostics explicit and testable?
- Are tests sufficient for the declared validation criteria?
- Were design changes documented?
- Was replanning classified correctly?
- Did the executor stop when it should have stopped?
- Is there any accidental dependency on `frozen/`?
- Is there any architectural drift from the redesign docs?

## Reviewer Verdicts

The reviewer must return one of the following verdicts.

### Accept

The milestone is complete and consistent with the redesign.

Minor issues, if any, are non-blocking.

### Accept With Follow-Ups

The milestone is acceptable, but follow-up tasks should be recorded.

Use this only when issues do not affect correctness, architecture, validation, or maintainability.

### Needs Revision

The milestone is directionally correct but requires executor fixes before it should be considered complete.

Use this for:

- missing tests
- unclear diagnostics
- incomplete documentation
- small architecture boundary issues
- local scope creep
- insufficient final report

### Return To Planner

The implementation exposed a design-level issue that should not be solved inside the execution milestone.

Use this for:

- design inconsistencies
- invalid architecture assumptions
- unclear domain concepts
- incompatible requirements
- missing backend contracts
- uncertain legacy behavior compatibility

### Reject

The milestone violates the clean redesign.

Use this for:

- line-by-line legacy porting
- copying legacy module structure
- broad unscoped rewrite
- hidden dependency on `frozen/`
- introducing compatibility wrappers around bad legacy abstractions
- major architectural drift without documentation

## Reviewer Output Format

The reviewer must produce:

1. Verdict.
2. Summary.
3. Scope assessment.
4. Architecture assessment.
5. Legacy leakage assessment.
6. Test assessment.
7. Documentation assessment.
8. Replanning assessment, if applicable.
9. Blocking issues.
10. Non-blocking issues.
11. Required fixes.
12. Suggested follow-up tasks.
13. Recommendation for the next milestone.

The reviewer should be concrete and cite files, symbols, tests, or documentation sections where possible.

## Completion Criteria

A milestone is complete when:

- the new code follows the documented dependency direction
- the implementation matches exactly one milestone or a documented split of that milestone
- the new tests cover the declared validation criteria
- relevant docs are updated
- no new runtime dependency on `frozen/` exists
- no legacy module structure leaked into the new architecture
- side effects are explicit and owned by the appropriate slice
- diagnostics are testable where relevant
- deterministic behavior is tested where relevant
- the executor produced a review packet
- the reviewer verdict is `Accept` or `Accept With Follow-Ups`

If the reviewer returns `Needs Revision`, the executor should address the issues within the same milestone.

If the reviewer returns `Return To Planner`, the planner should update the redesign docs before further implementation.

If the reviewer returns `Reject`, the milestone should be redesigned or reverted.
