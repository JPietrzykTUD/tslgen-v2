# PIVOT Export Rework Plan

## Status and decision record

Status: architecture approved; slices 27A, 27B, and 27C are implemented and verified.
Slice 27C has not started.

This plan replaces the original in-compiler direction for audit fix-plan slice
27. The historical audit remains unchanged as evidence. The agreed decisions
are:

- PIVOT export is an independently packaged downstream tool under
  `tools/pivot/`, not a `tslc` backend, compiler stage, installed subcommand, or
  compiler-owned semantic projection.
- The distribution is `tslc-pivot`, the Python package is `tslc_pivot`, and the
  executable is `tslc-pivot`.
- `tslc export pivot` is removed without a permanent compatibility shim or a
  generic plugin-discovery framework.
- Dependencies point from `tslc_pivot` to `tslc`, never in the other direction.
  The first extracted version is deliberately lockstep with the repository's
  `tslc` revision; it is not a promised stable third-party compiler API.
- PIVOT may configure and instantiate compiler objects and may own a bounded,
  fail-closed interpretation of lowered C++ and Rust text. It must not
  monkey-patch compiler registries, mutate compiler defaults, or feed PIVOT
  interpretations back into compiler semantics.
- PIVOT-driven changes to `tsldata/`, normal TSIL semantics, compiler lowering,
  backend output, generated-value-test behavior, or benchmark behavior are out
  of scope. A genuinely useful projection-neutral compiler seam requires a
  separately justified compiler slice.
- The output contract remains a completely flattened, deterministic list of
  straight-line instructions. Runtime branches and loops are unsupported.
- Every definition entry emitted by the canonical full-corpus baseline must
  remain emitted. Coverage may increase, but an entry disappearing or a
  pre-existing nominal-identity multiplicity shrinking is not accepted merely
  because the aggregate count is unchanged.

The latest measured canonical full-corpus evidence is:

| Language | Documents | Definitions | Skips |
|---|---:|---:|---:|
| C++ | 94 | 10,291 | 18,568 |
| Rust | 94 | 6,769 | 9,255 |
| Combined | 188 | 17,060 | 27,823 |

Those 17,060 entries represent 16,732 nominal identities under the planned
`(language, document, isa, dtype, signature)` key. There are 328 two-entry
collision groups, and every group contains two different `direct` hashes. This
is existing output behavior, not an extraction regression. Slice 27A preserves
the exact entry multiset and records the collision census; deduplicating or
changing those definitions would require a separate product decision.

The 27A pre-extraction run reproduced those counts. Concatenating the 188 YAML
files in sorted relative-path order produced SHA-256
`846ffd8955e3b7860f1bc7c2980d4fc2bd8618efa259fbe1824923c3293dc747`.
The durable manifest defined below remains authoritative rather than this prose
summary. Earlier analysis also identified 4,730 definitions as the coverage at
risk under the rejected leaf-only design. The baseline census must explain
that scope; neither number should survive as an unexplained constant in code or
a charter.

## Goal

Deliver a separately installable PIVOT exporter that reuses compiler-owned
facts but owns its target-text interpretation, recursive flattening, YAML
contract, diagnostics, compatibility, and coverage evidence. Remove every
PIVOT runtime/package dependency from core `tslc`, then replace the current
regex rewrite engine with a typed, binding-aware PIVOT-local pipeline without
losing an existing emitted definition.

## Boundaries and ownership

```text
tsldata ──authored input──> tslc compiler
                              ^
                              |
                    imports/uses (one way)
                              |
                    tools/pivot / tslc_pivot

tslc and tsldata ───────────X──────────> tslc_pivot
```

`tools/pivot` is external to the compiler product, not external to repository
governance. Root instructions, determinism, diagnostics, test, and review rules
still apply.

| Fact or decision | Owner |
|---|---|
| Source discovery and validation | `tslc` |
| Typed catalog and machine profiles | `tslc` |
| Implementation selection and call dependency identity | `tslc` |
| Target capabilities, intrinsics, signature types, and fixed-vector spellings | `tslc` backends |
| Ordinary TSIL scan/lowering semantics | `tslc` |
| Profile feature-set cover used only for PIVOT export | `tslc_pivot` |
| PIVOT admissibility and residual target-text interpretation | `tslc_pivot` |
| Binding identity, local allocation, recursive flattening, and cycle reporting | `tslc_pivot` |
| PIVOT YAML schema, paths, diagnostics, skips, and coverage baseline | `tslc_pivot` |
| Normal generated C++/Rust projects, tests, and benchmarks | `tslc` |

Public compiler APIs are preferred. Direct imports of typed compiler classes
are acceptable for the initial lockstep package. Private compiler entry points
must be inventoried in one compatibility-focused module or test; do not create
wrapper objects around every public type merely to hide imports. Replace the
current private `tslc.api._expand_sources` use with
`tslc.sources.expand_source_paths`. The existing
`tslc._pipeline_inputs.load_catalog_inputs` dependency may remain explicitly
lockstep during extraction. Promoting it or another service to a public API is
not part of this plan.

## Intended package shape

The extraction first preserves the current module layout. The final layout
should converge on literal responsibilities similar to:

```text
tools/pivot/
  AGENTS.md
  CLAUDE.md
  CHARTER.md
  README.md
  LICENSE
  NOTICE
  pyproject.toml
  src/tslc_pivot/
    __init__.py
    __main__.py
    cli.py
    exporter.py
    model.py
    compiler_compat.py
    profiles.py
    selection.py
    lowering.py
    body_ir.py
    render_stream.py
    parse_cpp.py
    parse_rust.py
    inline.py
    documents.py
    render_yaml.py
  tests/
    conftest.py
    baselines/
    test_boundary.py
    test_cli.py
    test_export.py
    test_body_parser.py
    test_inline.py
```

The names are not a mandate to manufacture one module per noun. Combine small
stateless pieces when that is clearer. The required outcome is that no new
catch-all planner replaces the current one.

## Out of scope

- A generic compiler plugin framework or dynamic CLI registration.
- A compatibility implementation of `tslc export pivot`.
- PIVOT annotations or workaround bodies in `tsldata`.
- PIVOT-specific hooks, types, branches, or registries in `tslc`.
- A stable independently versioned compiler-extension API in the first release.
- Parsing or supporting runtime branches, loops, arbitrary blocks, exceptions,
  or other control flow that cannot become a plain instruction list.
- Unrelated cleanup in compiler selection, lowering, backends, tests, or docs.
- Renaming existing PIVOT diagnostic codes during the mechanical extraction.

## Governance changes required by the extraction

These changes belong in the extraction slice so documentation never describes
an exception that the package boundary does not yet enforce:

1. **Root `CHARTER.md`**
   - Clarify that the coordinated compiler product is `tslc`, `tsldata`, normal
     testing, benchmarking, generated artifacts, and their evidence.
   - Scope the existing authoring/analysis projection rule to compiler-owned
     projections.
   - Add a narrow downstream-tool contract: one-way dependency, independently
     owned target interpretation, no claims that PIVOT-local facts are compiler
     guarantees, and no tool-motivated compiler changes without separate
     justification.

2. **Root `AGENTS.md`**
   - Add `tools/` to ownership/navigation and route PIVOT work to
     `tools/pivot/AGENTS.md` plus `design-review`.
   - Keep opaque target text inviolate in `tslc`, `tsldata`, and compiler-owned
     projections while permitting a declared downstream tool to parse it only
     inside its package.
   - State that downstream-tool needs alone do not authorize `tslc/` or
     `tsldata/` edits.

3. **`PLANS.md` and `.agents/skills/design-review/SKILL.md`**
   - Classify work as compiler behavior, compiler-owned projection, or
     independently packaged downstream tooling before review.
   - For downstream tools, inventory every compiler fact/API consumed and
     every local decision.
   - Add isolation, package, parser edge, fail-closed, golden/differential,
     determinism, and coverage-ratchet checks.
   - Preserve the existing raw-target-text prohibition for compiler-owned
     projections. Do not turn the PIVOT exception into a general exporter
     loophole.

4. **`tools/pivot/CHARTER.md` and `tools/pivot/AGENTS.md`**
   - Declare PIVOT external to the compiler pipeline and CLI.
   - Require one-way imports, independent packaging, no global mutation, and
     explicit lockstep treatment of compiler internals.
   - Make complete straight-line flattening, deterministic output, fail-closed
     parsing, structured skips, and coverage preservation hard requirements.
   - Keep selection, capabilities, target spelling, source validation, and
     ordinary lowering compiler-owned.
   - Put tool-specific commands and validation here rather than weakening
     `tslc/AGENTS.md` or `tslc/CHARTER.md`; those compiler documents remain
     strict.

No new task skill is justified for one downstream prototype. The updated
`design-review` skill plus the PIVOT-local instructions are the routing path.
Reconsider a dedicated skill only if repeated PIVOT work develops a stable
workflow not captured by those files.

## Pre-extraction evidence

Before the first extraction edit, generate a canonical baseline from the same
clean source snapshot:

- all primitives;
- all configured machine profiles;
- all default scalar types;
- both `cpp` and `rust` languages;
- current deterministic profile-cover behavior;
- skips and diagnostics captured alongside emitted artifacts.

Store the temporary pre-move tree under `tslctmp/pivot-rework/before/`. Record a
durable tool-owned manifest containing:

- the exact command and input digest;
- document and definition counts per language;
- skip counts grouped by stable reason/category;
- every definition entry's nominal identity
  `(language, document, isa, dtype, signature)` and multiplicity;
- a hash of each definition's `direct` list;
- the nominal-identity collision census and per-hash multiplicities;
- a hash of every YAML artifact and of the ordered artifact set.

The extracted tool records both exact skip messages/inventory and a
manifest-only `reason-prefix-v1` category census. Runtime structured skip
categories remain part of the typed-model work; the evidence classifier must
not be presented as compiler or planner semantics. Baseline regeneration is
guarded by default: additions are allowed, while removed entries, reduced
multiplicity, or replaced `direct` hashes require an explicit reviewed
incompatibility override.

Counts are summary evidence, not the ratchet key. The exact multiset of nominal
identities and `direct` hashes proves that one definition was not silently
exchanged for another and accounts for the schema's existing collisions.
Extraction requires byte-identical artifacts. Later correctness fixes may
change a `direct` hash only with a focused reproduction and an explicitly
reviewed baseline change; they still may not remove an entry or reduce its
multiplicity without a new product decision.

## Implementation slices

Implement and review one slice at a time. Do not combine the mechanical move
with the parser/inliner redesign.

### 27A. Establish the downstream-tool boundary and extract current behavior

**Goal:** installing and running core `tslc` has no knowledge of PIVOT, while
the separately installed `tslc-pivot` produces byte-identical YAML and the same
definition/skip inventory.

**Work:**

- Apply the governance changes above.
- Create `tools/pivot/` as its own Python distribution with package metadata,
  console entry point, licensing, README, pytest configuration, and strict mypy
  configuration.
- Move the eight current `tslc/src/tslc/pivot/` modules mechanically to
  `tools/pivot/src/tslc_pivot/`; change package imports without redesigning the
  planner.
- Give the standalone CLI direct, testable configuration resolution using the
  public `tslc.project_config.load_project_config` and
  `tslc.sources.expand_source_paths`. Preserve explicit CLI options and output
  layout. Multiple configured source roots must not be collapsed to the old
  one-root maintenance helper limitation.
- Remove the `export` route, help entry, `_export_group`, and lazy PIVOT import
  from `tslc/src/tslc/cli.py`. Do not replace them with a shim or plugin hook.
- Move `test_pivot_export.py`, its fixtures, the PIVOT/backend projection
  equivalence assertion, and the PIVOT planner architecture assertion into the
  tool test suite. Keep genuinely backend-owned spelling tests in core.
- Remove the PIVOT section and command examples from `tslc/DESCRIPTION.md`,
  `tslc/README.md`, and `docs/tslc-cli.md`. Put the command, schema, subset, and
  compatibility contract in `tools/pivot/README.md`. Add `tools/` and PIVOT to
  the root project map only.
- Generalize compiler comments that name PIVOT while retaining generic backend
  helpers owned by `tslc`.
- Add a dedicated `pivot-tests` job to `.github/workflows/python.yml`. Leave
  core test sharding focused on `tslc/tests`; otherwise the moved tests would
  silently disappear from CI.
- Add boundary tests for package contents, CLI separation, reverse imports,
  registry/default immutability, exact compiler-version compatibility, and
  ordinary-generation independence.
- Move the durable full-export manifest into tool-owned baselines and compare
  the post-move tree with `tslctmp/pivot-rework/before/`.

**Acceptance:**

- `tslc --help` neither advertises PIVOT nor an empty `export` group;
  `tslc-pivot --help` and project-config discovery work independently.
- The `tslc` wheel contains no `tslc.pivot`, `tslc_pivot`, PIVOT command, or
  PIVOT dependency. No source or test under `tslc/` imports the tool.
- Importing or using `tslc_pivot` does not mutate compiler registries, defaults,
  or normal generated artifacts.
- The complete pre/post PIVOT artifact trees are byte-identical, definition
  identities and skips are identical, and the recorded full-corpus count is
  reproduced.
- Core compileall, mypy, full pytest, and corpus checking pass. Tool compileall,
  mypy, full pytest, package-isolation, and full-export tests pass independently.

### 27B. Retain statement semantics as PIVOT-owned typed nodes in shadow mode

**Goal:** retain calls, admitted locals, and the final result as typed PIVOT
values through lowering instead of flattening them and rediscovering statement
structure from target text. Production output remains unchanged.

**Data model:** use immutable values for at least:

- `PivotBody` with ordered statements and one final result;
- binding identities distinct from their rendered names;
- local binding/assignment statements;
- residual target-expression pieces not yet parsed;
- typed primitive-call sites carrying the compiler's `CallDependency`, attrs,
  arguments, and source span;
- structured unsupported reasons with source context.

The model does not yet need to understand target arithmetic semantics. It must
separate statement/dataflow structure owned by PIVOT from residual expression
text that the following slice will interpret.

**Work:**

- Reuse normal compiler scanning, selection, lowering, backend translation, and
  generation-time control expansion. PIVOT owns only the residual body
  interpretation after those stages.
- Replace shared reset-then-collect state with fresh immutable or
  lowering-local capture state for each specialization.
- Add PIVOT-local lowerer overrides/render nodes for `call`, admitted `var`
  declarations, and `complete`, carrying typed dependency, binding, argument,
  result, and source facts. Reuse every other normal region lowerer.
- Add a tool-local render-stream adapter that walks the compiler's current
  `RenderText` values while retaining PIVOT nodes and treating compiler-added
  Rust unsafe framing structurally. Do not add a visitor or PIVOT node to core.
- If a concrete compiler render value necessarily flattens a PIVOT node before
  the adapter can consume it, use a reserved non-source token tied to a typed
  capture record. Validate source collisions and decode the exact token in the
  render-stream adapter; do not rediscover markers with regex or parenthesis
  surgery.
- Inventory every currently emitted top-level statement that does not originate
  in these typed regions. It must receive an explicit PIVOT-local model before
  cutover; it may not be silently rejected if that removes a baseline entry.
- Run typed body construction in shadow mode beside the legacy exporter and
  record a corpus census by statement/dataflow feature, including the 4,730
  definitions previously at risk.
- Add focused tests for nested typed calls, multiple locals/statements, local
  shadowing, final-result placement, unsafe Rust framing, malformed capture
  tokens, and fresh-state/reentrancy behavior.

**Acceptance:**

- Shadow `PivotBody` construction succeeds for every entry in the current
  full-export baseline, including colliding nominal identities; no new skip is
  hidden by the legacy production path.
- Calls, locals, final results, and their source/dependency facts remain typed
  from the PIVOT lowerer through `PivotBody`.
- Body construction and unsupported diagnostics are deterministic across hash
  seeds and lowering operations are reentrant.
- Production YAML remains byte-identical because the legacy engine is still the
  active renderer in this slice.
- No `tslc/` or `tsldata/` file changes are needed. If one appears necessary,
  stop and propose a separate projection-neutral compiler decision.

**Implemented evidence (2026-07-18):**

- `body_ir.py`, `shadow_lowering.py`, and `render_stream.py` now own immutable
  body, binding, call, local, residual-sequence, final-result, fixed-wrapper,
  unsupported, and shadow-census values. Production `direct` rendering remains
  on the legacy planner path.
- Both legacy marker capture and typed capture use fresh operation-local
  `ContextVar` scopes. The shadow configuration overrides only `call`, admitted
  `var`, and `complete`; all other TSIL lowering remains compiler-owned. A
  locked process-local nonce makes only the private fallback-token namespace
  unique, so flattened tokens from another operation fail closed; the nonce is
  absent from typed bodies, evidence digests, diagnostics, and output.
- Both PIVOT call overrides reuse the compiler's vector-selector resolver, so an
  unresolvable explicit call vector cannot bypass ordinary compiler rejection.
- The lockstep render adapter preserves known compiler `RenderText` structures,
  records unsafe framing, rejects unknown structures, and decodes only exact
  collision-checked NUL-delimited tokens where eager rendering is unavoidable.
  Alternative implementation variants are identified by their declared source
  spans rather than mistaken for lost default-body captures.
- The canonical census constructs all 17,060 emitted definition occurrences
  with zero failures: 5,552 synthetic fixed wrappers, 6,778 native leaves,
  4,616 call-only definitions, 20 local-only definitions, and 94 definitions
  with calls plus reachable locals. It accounts for all 4,730 multi-statement
  definitions and all 328 nominal-identity collision groups (656 entries).
- `tests/baselines/shadow_census.json` pins the source-normalized typed-body
  digest
  `543092ed759bd8d313d137bc381514f8eaf72a72db93ea6edf7dda5cfb1ba5ea`,
  origins, feature combinations, and zero-failure requirement across two hash
  seeds. The production artifact digest remains
  `846ffd8955e3b7860f1bc7c2980d4fc2bd8618efa259fbe1824923c3293dc747`.
- The existing guarded baseline command now builds and validates the production
  and shadow manifests before writing either one. Any typed-shadow fact change
  requires the explicit reviewed-incompatibility flag, preventing a manual or
  partial evidence refresh.
- Focused tests cover nested and generated-loop calls, same-named bindings,
  inferred/const locals, raw residual assignments, final-result invariants,
  synthetic wrappers, caller-unsafe facts, template compatibility, source and
  token corruption, alternative variants, immutability, and failure-safe
  reentrancy. The complete tool suite passes 58 tests; tool mypy passes 15
  files. Core isolation passes 1,988 tests with 70 skips, mypy on 247 files,
  and corpus checking on 42 TSL files. There are no `tslc/` or `tsldata/`
  changes.

### 27C. Add bounded expression parsers, structured inlining, and differential export

**Goal:** generate complete `direct` lists from the PIVOT IR while retaining the
legacy engine only as a differential oracle.

**Work:**

- Add small language-specific C++ and Rust tokenizers/parsers for residual
  expressions plus shared binding-aware expression values. Use deterministic
  character/token parsing; regex is acceptable for recognizing one token or
  rejecting a form, never for context-blind substitution or statement repair.
- Distinguish binding references from qualified/path names, member positions,
  literals, comments, callables, and delimiter groups. Reject residual control
  flow, unsupported blocks/casts/pragmas/literals, and malformed syntax with a
  stable PIVOT skip.
- Resolve callees from compiler-owned selected slots and typed dependency
  identities; do not duplicate selector, feature, mask, overload, target, or
  backend-spelling rules.
- Bind arguments to callee parameter identities as expression nodes. Parenthesize
  inserted expressions according to a single renderer rule instead of editing
  text tokens.
- Allocate local and call-result temporaries deterministically. Rename locals
  by binding identity, never by searching identifier text.
- Inline nested primitive calls by composing statement and expression nodes.
  Preserve left-to-right deterministic order and emit one completely flattened
  instruction list.
- Detect recursive cycles, arity mismatches, unresolved overload/target axes,
  malformed results, and unsupported constructs as structured PIVOT skips with
  the best available source span.
- Render the new plan in parallel with the legacy engine for the entire corpus.
  Compare definition identities, signatures, direct lists, YAML artifacts,
  skips, and ordering. Classify every difference; never refresh a golden merely
  to make the comparison pass.
- Add adversarial tests for `std::min`/parameter collisions, C++ `::`, `.` and
  `->`, Rust paths/raw identifiers, nested delimiters/calls, comments and
  strings, parameter expressions, unsafe wrappers, and unsupported control
  flow.

**Acceptance:**

- The new engine emits every baseline entry with its required multiplicity and
  introduces no unexplained new skip. Additional safe definitions are allowed
  and recorded as a ratchet increase.
- Every definition shared with the legacy exporter has byte-identical
  signature/direct serialization unless a focused test proves the old text was
  wrong. The complete artifact tree is byte-identical when no safe definitions
  are added; additions are reviewed and recorded as an explicit ratchet
  increase rather than hidden in a golden refresh.
- Nested calls, multiple statements, inferred locals, parameter reuse,
  qualified-name collisions, cycle detection, and both languages have focused
  tests.
- The new engine contains no context-blind identifier replacement, regex
  statement splitting, marker parenthesis scanning, or raw-text alpha-renaming.

**Implemented evidence (2026-07-18):**

- `target_expression.py` now owns deterministic, token-preserving C++ and Rust
  residual-expression parsing. Binding uses become body-local identity nodes;
  qualified/path names, members, callables, Rust raw identifiers and macros,
  literals, trivia, delimiter groups, and retained calls remain distinct.
  Comments, strings, control flow, blocks, pragmas, casts, unresolved generated
  library names, malformed delimiters, and forward local references fail
  closed with PIVOT-owned source context.
- `structured_inliner.py` binds arguments by `PivotBindingId`, preallocates
  locals in deterministic legacy-compatible order, expands typed calls
  left-to-right through the existing compiler-selected dependency resolver,
  detects cycles and arity/resolution failures, and emits one flattened list.
  Parenthesization and Rust return-group normalization are typed renderer rules;
  compiler backend syntax remains the sole renderer for synthetic fixed calls.
- The planner runs the structured lowering/parser/inliner independently beside
  the legacy production engine. A structured failure, including a synthetic
  fixed-wrapper failure, cannot remove a legacy production definition. Safe
  qualified/member collision fixtures demonstrate coverage that the old text
  rewriter could not prove, without changing the canonical production corpus.
- The canonical structured projection reproduces all 17,060 legacy definition
  occurrences, including all 328 nominal-identity collision groups, with zero
  missing or additional canonical entries, zero `direct` mismatches, identical
  definition order, and byte-identical YAML artifacts. The production artifact
  digest remains
  `846ffd8955e3b7860f1bc7c2980d4fc2bd8618efa259fbe1824923c3293dc747`.
- `tests/baselines/differential_census.json` pins the complete structured
  projection and classified comparison with digest
  `1afaa193cd567b0b7b1e48581f8e915569a86b8dabc4c92a5aaf5a852d102b1b`.
  Of 27,823 skip records, 20,571 are exact, 4,582 retain the same reason with a
  different typed source span, and 2,670 have a different fail-closed typed
  reason; neither side has an unmatched skip specialization. The guarded
  updater validates production, shadow, and differential candidates before
  writing any of them, and two hash seeds reproduce all three digests.
- Focused tests cover qualified/member/callable collisions, C++ `::`, `.` and
  `->`, Rust paths/raw identifiers/macros, nested delimiters and calls, lexical
  shadowing and forward references, parameter-expression parentheses, comments,
  strings, casts, unresolved constructs, control flow, cycles, arity failures,
  fixed-wrapper isolation, exact recursive output, collision ordering, and skip
  fact classification. The complete tool suite passes 84 tests in 297.34
  seconds; tool mypy passes 18 files. Core isolation
  passes 1,988 tests with 70 skips, mypy on 247 files, and corpus checking on
  42 TSL files. There are no `tslc/` or `tsldata/` changes.

### 27D. Cut over, delete the rewrite engine, and finish module ownership

**Goal:** make the typed PIVOT pipeline the only exporter implementation and
remove transitional complexity.

**Work:**

- Switch `export_pivot` to the new parser/IR/inliner path.
- Delete marker rediscovery, `_replace_identifiers`, `_split_statements`, unsafe
  block stripping by text surgery, shared reset-then-collect capture state, and
  the legacy differential path.
- Split the old planner responsibilities into profile cover, selection,
  lowering capture, target parsing, recursive inlining, document assembly, and
  YAML formatting only where those responsibilities remain substantive.
- Re-run the `design-review` playbook against the finished tool and the compiler
  isolation boundary.
- Update the PIVOT README and local architecture notes to describe only the
  implemented pipeline. Update the audit fix plan status only after acceptance
  has actually passed.
- Validate the generated YAML with the external PIVOT prototype when an
  executable or authoritative parser fixture is available. If it is not
  available, report that as an explicit external verification gap; do not
  compensate by weakening parser or compiler checks.

**Acceptance:**

- No production path contains the legacy rewrite utilities or regex marker
  rediscovery. Any reserved capture token required by the tool-local lowering
  adapter is converted directly into a typed lexer node, cannot collide with
  source text, and cannot reach emitted YAML.
- The complete baseline entry multiset remains contained in the new result and
  all approved direct-list hashes/schema checks pass.
- `tslc` remains PIVOT-free and normal C++/Rust generation is unchanged.
- Tool and core validation below pass; external-consumer validation passes or
  is reported as the sole explicit verification gap.

## Validation matrix

Run focused tests for each slice, then the relevant independent suites.

### Core compiler isolation

```bash
python -m compileall -q tslc/src/tslc
(cd tslc && python -m mypy)
PYTHONPATH=tslc/src python -m pytest -q tslc/tests
PYTHONPATH=tslc/src python -m tslc check
```

Generated build/value gates are not required for a move that leaves compiler
codegen untouched. If implementation pressure creates a proposed generic core
seam, treat it as a separate compiler slice and select its validation under
`tslc/AGENTS.md` before continuing PIVOT work.

### PIVOT tool

```bash
python -m compileall -q tools/pivot/src/tslc_pivot
PYTHONPATH=tslc/src:tools/pivot/src python -m pytest -q tools/pivot/tests
(cd tools/pivot && python -m mypy)
```

The tool suite must include the canonical full export, manifest ratchet,
cross-`PYTHONHASHSEED` determinism, adversarial parser cases, recursive inliner
cases, YAML schema/golden checks, and ordinary-generation non-mutation check.

### Packaging and commands

```bash
python -m pip install --no-deps -e ./tslc
python -m pip install --no-deps -e ./tools/pivot
tslc --help
tslc-pivot --help
git diff --check
```

CI additionally builds or inspects both distributions independently and proves
that the `tslc` wheel has no PIVOT package, command, or dependency. Scratch
artifacts stay below `tslctmp/pivot-rework/`.

## Risks and controls

| Risk | Control |
|---|---|
| A directory move leaves reverse awareness in core | Separate package/CLI, import and wheel boundary tests, no shim |
| Moved tests silently disappear from CI | Dedicated PIVOT job; core shard discovery remains intentionally core-only |
| Count stays constant while definitions change | Ratchet the exact nominal-identity/direct-hash multiset and collision multiplicities |
| Private `tslc` imports break | Explicit lockstep compatibility, exact version test, tool owns adaptation |
| A parser becomes another rewrite ladder | Typed token/statement/binding model, fail-closed tests, no global substitution |
| Coverage is sacrificed for architectural cleanliness | Shadow/differential gates require every baseline entry and multiplicity before cutover |
| PIVOT policy leaks into compiler facts | Ownership table, one-way imports, no global mutation, post-change design review |
| The downstream exception weakens ordinary projections | Scope root guidance and design-review checks to declared independently packaged tools |
| Corpus changes race the redesign | Rebase and refresh evidence in an isolated baseline change before continuing |

## Stop conditions

Stop the active PIVOT slice and request a separate decision when:

- preserving an existing definition appears to require editing `tsldata` or
  changing normal compiler semantics;
- a proposed `tslc` API exists only for PIVOT rather than a separately justified
  compiler capability;
- CLI compatibility would require restoring a core shim or plugin framework;
- the new parser/inliner cannot reproduce every baseline entry and no safe
  PIVOT-local interpretation is known;
- an output difference cannot be classified as byte-preserving or a proven
  correctness repair;
- a new third-party parser/runtime dependency creates an unreviewed packaging,
  licensing, native-build, or Python-version constraint.

## Completion criteria

The rework is complete only when:

- `tools/pivot` is a separately installable and tested distribution with the
  only PIVOT command and implementation;
- core `tslc` and `tsldata` contain no PIVOT dependency, command registration,
  source accommodation, or semantic exception;
- root and PIVOT-local guidance describe the real ownership boundary without
  relaxing the compiler charter;
- every canonical baseline definition is still emitted, with additional
  coverage recorded rather than replacing old identities;
- target-text parsing, binding substitution, recursive inlining, and complete
  flattening operate on typed PIVOT values and fail closed;
- the old regex rewrite/marker engine and shared mutable capture state are gone;
- core, tool, packaging, determinism, full-export, and design-review gates pass;
- external PIVOT consumer validation passes or its unavailability is explicitly
  reported as a remaining verification gap.
