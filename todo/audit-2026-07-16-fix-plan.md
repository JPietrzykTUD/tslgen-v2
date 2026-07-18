# tslc Audit Fix Plan — 2026-07-16

## Status and basis

Status: Phases 1 and 2 implemented (slices 1–19); Phase 3 implemented through
slice 26. The architecture for slice 27 is now approved and replanned as an
independently packaged downstream PIVOT tool; slice 27A is implemented and
verified, slice 27B is implemented and verified, and slice 27C has not started.
See [`pivot-export-rework-plan.md`](pivot-export-rework-plan.md).

Phase 3 implementation notes (one commit per slice):

- Slice 20 (6ada3f0): one catalog condition parser and syntax accessor layer;
  typed catalog vocabularies keep validators and promotion aligned.
- Slice 21 (704e349): typed boolean/query/loop syntax, exact generic scope
  symbols, and construction-time width-relation diagnostics.
- Slice 22: `target_families:` owns accepted target features, shared compiler
  spellings, and documentation family/order facts; scalar type metadata owns
  documentation labels/order; profile alternatives are profile-only overrides;
  backend `query_value::<namespace>::<name>` translations add query leaves
  without generic resolver branches.
- Slice 23: Rust algorithm Scalar/Generic/concrete impls share one typed target
  projection and one registration discovery; a compiler-owned reserved-name
  manifest replaces production regex discovery and is checked exactly against
  the static wrapper asset; generated Rust stays hash-identical.
- Slice 24: benchmark correctness/scenario values own validation and canonical
  identity; candidate-set checks are family-generic; one planner helper owns
  harness discovery/closure and one C++ timing skeleton owns measurement flow.
  Seven-family consistency and render-hash tests pin the additive boundary and
  byte-identical output. Only the backend render dispatch remains, so a
  scenario registry is not justified by the plan's three-owner threshold.
- Slice 25: all compiler diagnostic producers use full `SourceSpan` values and
  the transitional `Diagnostic(location=...)` initializer is gone; strict-mode,
  variant, value-test, and snapshot projections preserve end ranges (snapshot
  schema version 2). Fully typed query/PIVOT dependencies use direct access,
  with mypy and AST inventories guarding both boundaries.
- Slice 26: selection literally enumerates typed extension/type/target slots and
  free functions return after the first declaration-owning slot; lowering owns
  its policy-deferred diagnostic code; emitted and skipped slots share one
  ordering projection. Generation defaults resolve from the live backend
  registry at request construction, while rendering requires an explicit
  backend tuple. A representative selection/coverage/skip/trace digest stayed
  byte-identical across the refactor.
- Slice 27A: PIVOT is extracted to the separately packaged `tslc-pivot` tool;
  core CLI/package/docs no longer know it. Wheel, reverse-import, mutation,
  exact-version, full-corpus multiset/hash, and two-hash-seed tests enforce the
  one-way boundary. The pre/post export remains byte-identical at 188 documents,
  17,060 definitions, and 27,823 skips.
- Slice 27B: a PIVOT-owned immutable body model retains bindings, typed calls,
  admitted locals, residual statement sequences, final results, fixed-wrapper
  calls, unsafe facts, and structured failures beside the unchanged legacy
  renderer. Fresh lowering scopes and a fail-closed render adapter construct all
  17,060 baseline occurrences, including 4,730 multi-statement definitions and
  328 nominal collision groups, with zero shadow failures across two hash
  seeds. Production YAML remains byte-identical; no compiler or source-data file
  changed. One guarded maintenance command validates both production and shadow
  manifests before writing either; shadow semantic changes require explicit
  review.

Phase 2 implementation notes (one commit per slice):

- Slice 9 (af85c56): TSL-BACKEND-RUST-UNSUPPORTED-MULTI-POSITION-OVERLOAD in
  pre-render validation; C++ keeps general handling.
- Slice 14 (67f3a2a): maintenance/_repo_context.py replaces six repo-root
  copies; lazy resolution, argparse exit 2 outside a checkout; meta-test
  forbids module-level probing.
- Slice 13 (b2ebf7c): doctor consumes BackendCapability
  verify_machine_profile/toolchain_commands hooks (fake third backend now
  reports instead of raising); driver callbacks return frozen
  BackendPreparation/CommandFollowUp; oneAPI/WASI paths live in the committed
  [tslc.tools] role table with PATH-based fallbacks.
- Slice 15 (752f1f9): metadata_audit loads via check_documents and derives
  suggestions from pipeline.generate(render_artifacts=False) trace slots
  (declared selection features + selector spans added to the public trace);
  benchmark_coverage loads via check_catalog; audit output byte-identical.
- Slice 11 (7a110a1): typed storage/index_style plan facts (no fabricated
  result_kind); registry-required memory facts; renderer fallbacks deleted;
  typed case-drop causes incl. suppressed fuzz cases; protocol-declared
  pattern hooks. Full-corpus output byte-identical.
- Slice 12 (777fe00): ValueTestScalable carries typed facts (no tsl::/ull/
  quoting in plans); one shared scalable-facts builder; case_kinds pre-filters
  removed (backend_unsupported, not authored_unplanned); value_tests/
  lane_math.py owns shared lane/tiling/cross-lane/seed-mix invariants for
  value tests and benchmarks. Output byte-identical (sve + fixed profiles).
- Slice 16 (c1ca3f5): SignatureTypeForms member/member_parameter/
  concrete_integral_mask forms; PIVOT, benchmark C++, and facade ladders
  consume the shared tables; Rust VectorFor spelling has one owner. Projects
  and PIVOT YAML byte-identical.
- Slice 17 (8f67473): backend-owned CppProjectRenderModel decides headers,
  guards, registrations, and the typed smoke plan; render/ formats public
  accessors only (AST meta-test). Output byte-identical (scalar,avx2,sve).
- Slice 10 (eac988b): explorer status from Selector.evaluate_candidates with
  verbatim rejection reasons; catalog/selector_paths.py is the one selector-
  path owner (builder, index, specialization context); where levels no longer
  indexed as type groups (only observable index change: 7 corpus refs);
  explain on public emitted_extensions; AST guards added.
- Slice 18 (14795a6): env-through-CommandRunner (no os.environ mutation);
  serializer completeness guard (caught two unserialized slice-11 facts);
  cross-PYTHONHASHSEED subprocess determinism test; build-verified evidence
  from maintenance/build_verified.py instead of AST-sniffing test source.
- Slice 19 (c4a811b): generation_command.py core behind typed settings and a
  pipeline seam; _cli_options.py owns CSV/assignment/toolchain-merge parsing
  for cli, doctor, and maintenance CLIs; args mutation replaced by derived
  settings.

Follow-up: the byte-stability golden omitted by commit f0379f4 ("Refactor
conditional expressions...") is refreshed. Direct generation at f0379f4's
parent reproduced the old hash, while generation at f0379f4 reproduced the
current hash; the associated conditional and lane-mask tests prove the changed
parentheses fix C++ operator precedence.

Phase 1 implementation notes:

- Slice 1 (F1): `TSL-OUTER-PARSE-BAD-STRING` spanned diagnostic; parsing
  continues with other documents; the parser's `UnexpectedInput` producer moved
  to the `span=` API.
- Slice 2 (F2, F17a, F17c): `TSL-CATALOG-DUPLICATE-PRIMITIVE` keyed on
  name + parsed overload shape + attribute items (overloads and
  boolean/mask variants stay legal); `TSL-CATALOG-TYPE-GROUP-MALFORMED` for
  missing/scalar/empty `types`; empty groups are no longer promoted; direct
  wildcard-expansion coverage added.
- Slice 3 (F17b): leading-dash SDE runner profiles diagnose instead of being
  normalized; the diagnostics-dropping `load_machine_profiles` was removed and
  all callers use the checked loader.
- Slice 4 (F3, F4): `var<typed>` uninit routing is structural
  (`value(uninit::array)` / `value(uninit::scalar)`; other `uninit::*`
  diagnose; ordinary initializers are never substring-classified — note
  `uninit::scalar` now correctly uses `var_uninit`, changing `set_undef` C++
  scalar output from `{name}{};` to `{name};`); switch-arm scanning skips
  comments when locating labels/arrows and excludes them from labels.
- Slice 5 (F18h): `Region.statement_blocks()` / `Region.child_sequences()` are
  the single traversal owner, consumed by body validation, implementation
  state, `_type_param_bound_names`, and `_find_region`; `complete` inside a
  `loop` block now satisfies the pre-check.
- Slice 6 (F6): `PointerCastOperand` typed fact decided in the cast lowerer;
  Rust/C++ dialects render from it; `&&x`/bare-`&` operands diagnose; the
  anti-string-surgery meta-test now covers the translation dialect modules.
- Slice 7 (F22a, F22b-part): a raised workspace check releases
  `initial_check_complete` for the current generation, logs the traceback, and
  shows one actionable message while retaining the last snapshot;
  `_same_source` is typed.
- Slice 8 (F7 containment): qualified/member collisions with substituted
  parameter/local names are rejected (`_reject_qualified_substitution_uses`)
  before any rewrite; full-corpus export shows zero new skips (17,060
  definitions), so containment costs no coverage today.

Phase 1 validation: full pytest suite (1911 passed / 70 gated skips), mypy
clean (247 files), compileall, `tslc check` (42 files ok), `git diff --check`,
and generated build/test gates for the changed-codegen matrix
(`set_undef,to_array,store,load,from_array` × scalar/avx2 × cpp,rust — build
and scalar-cpp value tests verified).

This plan evaluates `todo/tslc-audit-2026-07-16.md` against the current tree at
`8df4fea`, the repository and compiler charters, `PLANS.md`, the applicable
`AGENTS.md` files, `tslc/DESCRIPTION.md`, and the cited implementation and test
paths. The audit's preliminary `MAJOR-1`…`MINOR-7` section duplicates F7, F13,
F12, F24a, F22b, F18d, and F22a; those entries are planned only once under the
consolidated F-numbers.

The audit says it inspected `e5a4b74`, but the current branch contains twelve
later commits. The cited defects were therefore checked against current code,
not accepted only from the old line references.

## Assessment

The audit's overall conclusion is sound: the compiler's main typed pipeline is
healthy, while the reported drift is concentrated at input-validation edges,
target-text leaf code, and tools that re-derive compiler-owned facts.

All sixteen near-blocker/major findings are relevant. Some need a different
repair than the audit proposes:

| Finding | Decision | Planning adjustment |
|---|---|---|
| F1 | Relevant, urgent correctness | Convert invalid string decoding into one spanned parser diagnostic; no transformer exception may escape. |
| F2 | Relevant, urgent correctness | Duplicate identity must include the callable overload identity as well as attributes. A name-plus-attributes key would incorrectly reject legitimate overloads such as `store(ptr, v)` and `store(ptr, s)`. |
| F3 | Relevant, urgent correctness | Match the exact typed `value(uninit::array)` / `value(uninit::scalar)` forms and diagnose unsupported `uninit::*`; never classify an arbitrary initializer by substring. |
| F4 | Relevant, urgent correctness | Make switch-arm scanning use the scanner's opaque-text rules and preserve clean label spans. |
| F5 | Relevant preventive guard | This is not a currently exercised corpus failure, but unsupported Rust multi-position overloads must fail during backend validation before rendering. |
| F6 | Relevant, urgent correctness | Carry address-of and mutability as typed cast facts; backend rendering must not infer them from rendered text. |
| F7 | Relevant, highest PIVOT risk | The immediate reject-not-corrupt containment remains valid. The product decision now moves PIVOT outside core `tslc`: the downstream tool owns a typed straight-line IR and bounded, fail-closed target parser/inliner, with no loss of an existing emitted definition and no PIVOT-driven source/compiler changes. |
| F8 | Relevant extensibility | `doctor` must consume backend-owned verification/profile/toolchain projections rather than backend IDs. |
| F9 | Relevant boundary drift | Replace private cross-package imports with a small backend-owned C++ profile render model/API; merely removing leading underscores would not move decisions to their owner. |
| F10 | Relevant robustness | Repository-only maintenance commands need not magically gain packaged corpus data, but importing the installed package must be safe and a missing checkout context must produce an argparse error rather than an import-time exception. |
| F11 | Relevant correctness and DRY | Reuse catalog validation and the real non-rendering pipeline through a public analysis boundary. Do not make another maintenance command depend permanently on private `_generate_loaded`. |
| F12 | Relevant, high-priority drift | Project explorer status from `Selector.evaluate_candidates` and retain its typed rejection reasons. |
| F13 | Relevant DRY/boundary drift | Backend signature/fixed-vector spelling must have one backend-owned projection used by PIVOT and benchmark code. |
| F14 | Relevant typed-plan defect | Add explicit storage/index/call-shape facts and make invalid plans fail construction; renderers must not recover missing semantics. |
| F15 | Relevant backend-boundary defect | Scalable plans should contain typed source facts, not C++ expressions, quoting, or literal suffixes. |
| F16 | Relevant coverage-honesty defect | Preserve a typed drop cause for every planned or synthetic case and report the actual unsupported/closure/conflict reason. |

The minor findings are also mostly relevant:

| Findings | Decision |
|---|---|
| F17a, F17c | Relevant and cheap catalog-boundary work. |
| F17b | Relevant, with a compatibility-aware repair: reject a leading SDE dash rather than normalizing it, replace callers of the unchecked loader, then remove or make that API explicitly fail on diagnostics. |
| F18a, F18b | Relevant duplicated parser/catalog knowledge. |
| F18c | Partly fixed since the audit: `selector_items` now indexes bracket-list items with sub-spans. It remains relevant because `where` levels are still interpreted by depth and can be indexed as type groups, while builder/index/context still do not share one selector-path projection. |
| F18d–F18h | Relevant. F18h includes a real correctness failure for `complete` nested in `loop`. |
| F18i | Relevant safety-related duplication; consolidate only lane/tiling invariants, not unrelated benchmark and value-test policy. |
| F19a | Relevant duplication, but use focused helpers for the demonstrably identical generic/concrete impl skeletons instead of forcing every trait family through one speculative mega-table. |
| F19b–F19f | Relevant. F19e is low urgency; F19f should distinguish forbidden semantic text inspection from legitimate final formatting. |
| F20a | Relevant extension friction, but a full registry is not automatically justified. First make scenario/correctness types own validation and canonical fields and add a consistency test; add a registry only if that leaves multi-file dispatch knowledge. |
| F20b–F20e | Relevant focused simplifications. |
| F21a | Relevant but partly prepared: public `Selector.emitted_extensions()` already exists. Switch the caller and add the boundary test; do not add another API. |
| F21b–F21i | Relevant. Keep each as a focused maintenance/CLI slice rather than one broad rewrite. |
| F22a, F22b | Relevant. |
| F22c | Not scheduled. It is a latency hypothesis, not a demonstrated defect; profile request latency first. If it becomes material, retain source text in the immutable workspace snapshot or move the read off-loop. |
| F23a–F23d | Relevant typed-model and extensibility cleanup, split by owning boundary. |
| F24a, F24b, F24d | Relevant after the behavior fixes that shrink or clarify those modules. |
| F24c | No standalone change. Naming normalization has no user-visible or architectural payoff while the current split is coherent and meta-tested; normalize only when an affected module is otherwise touched. |

Thus 41 of the 43 minor subfindings are actionable. F22c is evidence-gated and
F24c is intentionally not an independent work item. The audit's separate nits
are outside this plan; a nit may be fixed only when it is in the same ownership
boundary and does not expand a planned slice.

## Execution rules

- Implement one numbered slice at a time. Do not combine unrelated cleanup
  merely because the same file is open.
- Preserve current emitted C++/Rust/PIVOT text unless a slice explicitly fixes
  incorrect behavior. Use golden/hash comparisons for behavior-preserving
  refactors.
- Add the focused failing test before or with each correction. Unsupported
  forms must become structured diagnostics or explicit coverage entries, not
  silent fallback.
- Prefer an existing typed owner over a new registry or handoff object. Add a
  type only when it carries an invariant or a decided compiler fact.
- Update the documentation owned by the changed component. After extraction,
  PIVOT behavior belongs in `tools/pivot/`; `tslc/DESCRIPTION.md` must not retain
  an external-tool architecture contract.
- Keep the audit report unchanged as evidence. Record implementation status in
  this plan only if work on a slice actually begins.

## Phase 1 — Eliminate crashes and silent corruption

### 1. Invalid outer-string diagnostics (F1)

Goal: `tslc check` and the LSP always return a located diagnostic for a
grammar-accepted but Python-invalid string escape.

Work:

- make document transformation return/accumulate diagnostics or raise a
  parser-owned exception carrying the token span;
- catch both `ValueError` and `SyntaxError` from literal decoding;
- emit `TSL-OUTER-PARSE-BAD-STRING` at the offending string and continue with
  other source documents;
- use the canonical `span=` diagnostic API while touching this producer.

Acceptance: parser and authoring tests cover `"\x"`, multiple documents, stable
diagnostic ordering, and no escaped exception.

### 2. Primitive and type-group input honesty (F2, F17a, F17c)

Goal: malformed or conflicting catalog declarations cannot be promoted into an
order-dependent catalog.

Work:

- define one primitive declaration identity that preserves legal overloads and
  boolean/mask variants while rejecting a repeated callable declaration;
- report the duplicate at the second declaration with a related location for
  the first;
- require every `types` entry to contain a non-empty scalar list before
  promotion;
- add direct catalog coverage for `[aligned=*, packed=*]` producing four
  variants.

Acceptance: duplicate identical overloads fail; distinct signatures, mask
policies, and concrete wildcard variants remain legal; malformed/missing/empty
type groups all diagnose and are absent from the catalog.

### 3. Machine-profile runner honesty (F17b)

Goal: profile loading never repairs malformed authored runner data or discards
structural diagnostics.

Work:

- reject SDE profile values beginning with `-` using
  `TSL-PROFILE-MALFORMED-RUNNER` and retain the canonical no-dash form in source
  data;
- migrate tests and helpers to `load_machine_profiles_checked`;
- remove `load_machine_profiles`, or rename/redefine it as an explicit
  raise-on-diagnostics convenience so failure cannot be ignored.

Acceptance: leading-dash, malformed runner, and valid SDE/QEMU/wasmtime cases
are pinned; production and tests exercise the same checked path.

### 4. Exact TSIL declarations and comment-aware switch arms (F3, F4)

Goal: nearby raw text cannot change TSIL semantics accidentally.

Work:

- classify uninitialized `var<typed>` forms from the recursive segment shape,
  with distinct scalar and array templates;
- preserve ordinary initializers such as `my_uninit_count` verbatim;
- make `_scan_switch_arms` skip line/block comments through the shared opaque
  scanner logic while finding labels, arrows, and braces;
- capture labels without surrounding comment text.

Acceptance: declaration lowering tests pin scalar/array/ordinary initializers;
scanner tests cover `=>` inside block comments and line comments before labels.

### 5. Complete recursive Region traversal (F18h)

Goal: every compiler walker sees the same recursive TSIL region tree.

Work:

- add one literal child-sequence iterator on `Region` covering body, block,
  else-block, and switch arms;
- use it in body validation, implementation-state analysis, lowering helpers,
  and `body_rendering` searches;
- retain behavior-specific traversal order explicitly.

Acceptance: one structural-body fixture containing every block shape produces
the same region sequence for all walkers, and `complete` inside a loop no longer
causes `TSL-LOWER-NO-COMPLETE`.

### 6. Typed Rust pointer casts (F6, F19f-part)

Goal: Rust pointer-cast semantics are decided before target text exists.

Work:

- represent pointer source form and address mutability in the cast lowering
  value/API;
- have Rust rendering select `addr_of!`, `addr_of_mut!`, or `as *const/*mut`
  from that typed fact;
- reject unsupported raw address forms at lowering instead of guessing;
- extend the anti-string-surgery tests to the translation modules and assert
  against semantic inspection of rendered expressions.

Acceptance: `&mut buf`, `& mut buf`, `&(buf)`, and non-address pointer values
have an explicit typed result or a structured diagnostic; generated Rust value
tests/builds cover the supported paths.

### 7. LSP initial-check failure release (F22a, F22b-part)

Goal: an unexpected workspace-check exception cannot wedge index-backed
requests.

Work:

- set `initial_check_complete` in a `finally` path for the current initial
  generation;
- log and show one actionable failure without replacing a prior valid snapshot;
- make subsequent requests return the available/empty projection promptly;
- type the source-span comparison directly while this boundary is touched.

Acceptance: a raised `AuthoringWorkspace.check` is visible, definition/hover/
explorer requests complete, shutdown remains idempotent, and normal debounce/
supersession behavior is unchanged.

### 8. PIVOT corruption containment (F7)

Goal: no currently accepted PIVOT export can silently rewrite a qualified,
member, or callable identifier because it collides with a parameter/local.

Work:

- add the `min`/`std::min` reproduction and equivalent Rust qualified-name
  coverage;
- until Phase 3 removes rewriting, reject every identifier-collision context
  that the exporter cannot prove is a standalone binding use;
- use regex only to reject unsupported text, never to repair it;
- report the source span and reason as a normal PIVOT unsupported entry.

Acceptance: the reproduction is either emitted correctly without rewriting
the qualified name or, for the containment slice, rejected deterministically;
corrupt YAML is impossible.

## Phase 2 — Restore single owners and honest planning

### 9. Rust unsupported-overload validation (F5)

Add the multi-position check to Rust pre-render validation, use a dedicated
diagnostic code, and prove that validation prevents artifact construction while
C++ retains its general behavior.

Focused tests: `test_render_model.py`, `test_select_and_lower_backends.py`, and
the Rust profile validation tests nearest `validate_rust_profiles`.

### 10. Selector-owned explorer and selector-path projection (F12, F18c, F18d, F21a)

Goal: selector candidates and implementation selector syntax each have one
compiler owner.

Work:

- replace explorer `_authored_candidates` with `evaluate_candidates` and map
  typed rejection reasons to `SlotStatus`/detail;
- define one parsed selector-path projection for extension lists, source type
  groups, target axes/groups, and `where` constraints, including element spans;
- consume it from catalog promotion, catalog indexing, and specialization
  context;
- change `explain` to the existing public `Selector.emitted_extensions()`;
- add AST/import guards against private selector use and second selector walks.

Acceptance: unsatisfied `requires`, target constraints, masking variants, and
list selector heads report the same facts in selector, explorer, references,
and specialization context; `where` is never indexed as a type group.

### 11. Typed value-test plan facts and drop causes (F14, F16, F20e)

Goal: a case plan completely and honestly describes what renderers execute.

Work:

- add typed storage, index/call style, and masking facts without overloading
  `result_kind`;
- make required memory length and related facts mandatory in the case
  capability registry, including `mask_pointer_load`;
- remove renderer `or` fallbacks and signature/mask inference;
- return a typed case-drop result for unsupported kind, missing differential
  closure, and header-group conflict;
- account for suppressed synthetic fuzz cases;
- declare optional pattern hooks on protocols instead of `getattr`.

Acceptance: malformed plans fail construction; C++ and Rust render the same
buffer/call facts; every authored and synthetic case has an emitted or
actionable coverage outcome.

### 12. Backend-neutral scalable test facts and lane invariants (F15, F18i, F20c)

Goal: scalable planners carry behavior, and C++ renderers own C++ spelling.

Work:

- replace `runtime_lanes_expr`, prequoted names, `tsl::...`, and `ull` values
  with raw extension/template substitutions, lane counts, mask bits, and typed
  literal values;
- introduce a focused reusable scalable-expression input builder;
- centralize only shared lane-count, tiling, cross-lane-safety, and mix-constant
  invariants used by value tests and benchmarks;
- render all final C++ expressions and suffixes in the C++ renderer.

Acceptance: planned scalable values contain no C++ namespace or literal-suffix
text; C++ output is golden-identical except for intentional fixes; unsupported
backend cases report `backend_unsupported` rather than `authored_unplanned`.

### 13. Doctor and verifier capability ownership (F8, F21e, F21f)

Goal: a registered backend supplies everything `doctor` needs without string
dispatch, and verification callbacks return substantive typed outcomes.

Work:

- add backend capability hooks for machine-profile verification projection and
  toolchain reporting;
- replace mutable prepare/after callback out-parameters with small frozen
  outcome values containing the prepared backend, commands, diagnostics, and
  skips;
- move oneAPI/WASI defaults out of compiler source into explicit repository or
  project configuration, retaining command-line overrides;
- have `doctor` fold capability outcomes only.

Acceptance: a fake third backend produces a report; missing tools/configuration
are structured; no C++/Rust ID branch or host-version path remains in
`doctor.py`/compiler defaults.

### 14. Import-safe maintenance context (F10)

Goal: maintenance modules are importable without a repository checkout and
resolve checkout defaults only when a command needs them.

Work:

- add one lazy repository-context helper, separate from `tslc.toml` project
  configuration discovery;
- remove module-level root/path probing and cross-module private constants;
- make each repo-only CLI resolve defaults after argument parsing and use
  `parser.error` when context is unavailable.

Acceptance: importing every `tslc.maintenance.*` module succeeds with root
discovery forced to fail; `--help` succeeds; repo-dependent execution exits 2
with a readable message.

### 15. Metadata audit through public compiler boundaries (F11)

Goal: metadata suggestions use the same validated catalog, selection,
dependency closure, and coverage facts as generation.

Work:

- expose a public non-rendering loaded-input analysis entry point, or extend an
  existing public result without leaking `_PipelineInputs`;
- load source paths through `expand_source_paths` and `check_catalog`;
- replace the primitive-name-only worklist with pipeline coverage/trace facts;
- migrate `benchmark_coverage` off hand-rolled parse/build as part of the same
  loading-boundary correction.

Acceptance: catalog errors stop the audit with original diagnostics; a callee
available for only one backend yields suggestions matching pipeline facts; one
immutable source snapshot is used.

### 16. Backend-owned type projection (F13, F19b)

Goal: every generated backend spelling of signature/facade/fixed-vector types
comes from `BackendSignatureTypes` or the owning backend dialect.

Work:

- add the missing vector-member, facade, and fixed-vector forms to the backend
  type projection;
- migrate PIVOT, benchmark C++, C++ facades, and Rust facades;
- keep documentation prose labels documentation-owned while sourcing the
  actual type classification from typed scalar/signature data.

Acceptance: projection-equivalence tests cover every supported kind for C++ and
Rust; no duplicate size/member/fixed-vector spelling ladders remain.

### 17. C++ profile render model (F9, F19e, F24d-part)

Goal: backend code decides profile registrations, compile guards, extension
preference, and smoke instantiations; `render/` formats a finalized model.

Work:

- introduce one cohesive backend-owned `CppProfileRenderModel` (or equivalent
  public value/API) built from `EmittedProfile`;
- move smoke lane/argument planning and render-extension preference into that
  model construction;
- remove private backend imports from `render/` and add an import-boundary
  meta-test;
- preserve templates as formatting-only consumers.

Acceptance: profile-rendering hashes remain stable, render imports no private
backend names, and a model invariant test proves all smoke/guard facts are
decided before formatting.

### 18. Maintenance determinism and side-effect hygiene (F21b, F21c, F21d, F21i)

Goal: maintenance evidence is deterministic, complete, and independent of
process-global mutation or test-source syntax.

Work:

- pass an environment mapping through `CommandRunner` instead of mutating
  `os.environ`;
- add a dataclass-field completeness test for generation snapshot semantics
  with an explicit omission allowlist;
- compare full snapshot documents in subprocesses with different
  `PYTHONHASHSEED` values;
- replace AST-sniffed build-verification facts with one shared typed constant or
  manifest consumed by tests and inventory.

Acceptance: concurrent/failing documentation runs cannot leak environment;
new semantic fields fail the completeness test; cross-hash-seed snapshots are
byte-identical; pytest refactoring cannot erase inventory facts.

### 19. Focused CLI command core and option parsing (F21g, F21h)

Extract the generate/build/test command core from `cli.py`, share CSV and
toolchain merge parsing through a small CLI-owned helper, and keep legacy flat
generation routing in `cli.py`. Prove direct core tests plus existing CLI
end-to-end behavior; do not mix this with maintenance semantics changes.

## Phase 3 — Consolidate extension points after behavior is pinned

### 20. Catalog grammar/accessor ownership and typed catalog kinds (F18a, F18b, F23a-part)

Create one catalog-owned parser for `param_types` conditions and base-width
relations, one syntax AST accessor module for child/scalar/list/span access,
and typed aliases/enums for the catalog kind fields already constrained by
validators. Derive allowed-value sets from those types where practical. Table
tests must prove validator and promotion agreement for accepted and rejected
forms.

### 21. Typed control/query syntax (F18e, F18f, F18g, F23a-part)

Parse `if` boolean terms once into typed `Or`/`And`/`Leaf` values, resolve
generic parameters as exact first-class scope symbols, and parse loop selectors
through `ir/region_syntax.py`. Make width relations exhaustive and diagnosed at
catalog construction. Pin exact identifier/negation acceptance and reject
expressions such as `foo(PreserveSign)`.

### 22. Source-owned target/documentation capabilities (F19c, F19d, F23d)

Move documentation target family/order/type labels and target-feature spelling
to typed catalog/source capabilities. Extend backend/template-owned query value
namespaces so adding NEON/SVE constants does not edit the generic query leaf
resolver. Do not duplicate feature alternatives across every profile; prefer a
single source-owned feature-spelling catalog consumed by profile-specific
overrides.

Acceptance: documentation sorting/classification uses typed family/scalar
owners, all current feature spellings are unchanged, unknown source spellings
diagnose, and a synthetic non-x86 value namespace is additive.

### 23. Rust algorithm renderer consolidation (F19a, F19f-part)

Factor only byte-identical generic/concrete impl skeletons and repeated
registration discovery into focused helpers. Replace regex discovery of public
functions in the static Rust asset with a compiler-owned reserved-name
manifest, checked against the asset in tests. Preserve generated Rust via
golden hashes and generated build/value gates.

### 24. Benchmark scenario ownership (F20a, F20b, F20d)

Make each scenario/correctness type own its validation and canonical fields,
factor the repeated harness-closure check, and factor one timing skeleton over
typed rendered parts. Add a consistency test for every supported scenario
family. Introduce a registry only if the resulting code still requires a
parallel family list in three or more owners.

### 25. Finish typed diagnostic/query migration (F23b, F23c, F22b-part)

Convert remaining compiler diagnostic producers from `location=` to full
`span=`, then remove the compatibility initializer unless it is deliberately
declared permanent. Replace defensive `getattr` at fully typed lowering and
PIVOT dependency boundaries with direct typed access. Mypy and a producer
inventory test should prevent regression.

### 26. Selector and pipeline cohesion (F24b, F24d-remainder)

After selector behavior is pinned, extract literal slot enumeration and an
early-returning free-function path from `select_profile`. Move the deferred
lowering diagnostic code to its lowering owner, share coverage/skipped sort-key
projection, and make default-backend behavior an explicit request/configuration
decision rather than an import-time registry snapshot. Preserve selection,
coverage, skip, and trace ordering byte-for-byte.

### 27. Extract and rework PIVOT as a downstream tool (F7, F24a, F22b-part)

The product gate is resolved: PIVOT is external to the coordinated `tslc` and
`tsldata` compiler product. It will move to a separately packaged
`tools/pivot/` distribution with one-way `tslc_pivot -> tslc` dependencies and
its own command, charter, instructions, tests, CI, target-text interpretation,
flattening, YAML contract, diagnostics, and coverage ratchet. Core `tslc` will
remove the PIVOT subcommand, package, tests, and architecture contract without
adding a compatibility shim or plugin framework.

The extraction must preserve the complete current artifact tree and definition
entry multiset, including nominal-identity collisions, before any inliner
redesign. Subsequent PIVOT-only slices retain
statement semantics as typed nodes, add bounded C++/Rust expression parsing and
binding-aware recursive inlining in differential mode, then delete the legacy
marker/regex rewrite engine only after the full-corpus gate shows no definition
loss. No PIVOT-driven `tsldata`, TSIL, lowering, backend, or public compiler API
change is authorized.

The detailed ownership, slices, baseline, stop conditions, and validation gates
are in [`pivot-export-rework-plan.md`](pivot-export-rework-plan.md).

## Validation gates

Every slice runs its focused tests plus:

```bash
python -m compileall -q tslc/src/tslc
(cd tslc && python -m mypy)
git diff --check
```

At the end of each phase:

```bash
PYTHONPATH=tslc/src python -m tslc check
PYTHONPATH=tslc/src python -m pytest -q tslc/tests
```

Slices that change backend codegen, project rendering, value-test rendering,
verification, or Rust algorithm output also run the smallest useful generated
matrix and then, where toolchains are available:

```bash
PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds \
  tslc/tests/test_build_verify.py tslc/tests/test_value_tests.py
```

Relevant focused suites include:

- parser/catalog/profile: `test_catalog.py`, `test_catalog_validation.py`;
- TSIL/lowering: `test_tsil_scan.py`, `test_select_and_lower*.py`,
  `test_lower_*.py`;
- backend/render: `test_render_model.py`, `test_profile_rendering.py`,
  `test_generation_conditionals.py`;
- value tests/benchmarks: `test_value_test_planning.py`,
  `test_fuzz_value_tests.py`, `test_benchmark_variants.py`;
- maintenance/CLI: `test_authoring_tools.py`, `test_metadata_audit.py`,
  `test_coverage_inventory.py`, `test_generation_snapshot.py`, `test_cli.py`;
- editor: `test_lsp_workspace.py`, `test_lsp_protocol.py`,
  `test_catalog_index_authoring.py`;
- PIVOT: `tools/pivot/tests`.

A skipped generated gate is a reported verification gap, not a pass.

## Completion criteria

The audit remediation is complete only when:

- every actionable finding above is closed by its acceptance test or explicitly
  reclassified here with new evidence;
- F1–F7 cannot crash, silently corrupt, or render unsupported output;
- selector, backend, value-test, maintenance, and editor projections use their
  compiler-owned typed sources rather than parallel walks/string classifiers;
- full Python tests, mypy, compileall, corpus checking, and diff checks pass;
- affected generated C++/Rust gates pass, or unavailable toolchain gaps are
  listed in the final review packet;
- compiler documentation contains no PIVOT command or architecture contract,
  while `tools/pivot/` documentation matches its standalone command, package,
  parser/inliner, and compatibility contract.
