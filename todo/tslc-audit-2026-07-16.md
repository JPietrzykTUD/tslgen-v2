# tslc Design & Code Audit — 2026-07-16

**Audited state:** commit `e5a4b74` on branch `editor`, clean working tree.
Transient uncommitted editor edits appeared and were reverted during the audit;
all findings reference the committed tree.

**Method:** six parallel subsystem reviews (syntax/catalog, select/ir/lower,
backend/render, value_tests/benchmark, orchestration/output/maintenance/CLI,
LSP/PIVOT) audited against `CHARTER.md`, `tslc/CHARTER.md`, the applicable
`AGENTS.md` files, and `tslc/DESCRIPTION.md`, following
`.agents/skills/design-review/SKILL.md`. Every major finding below was
independently re-verified against the cited lines (10 sampled, 10 confirmed);
three were reproduced by execution (F1, F2, and the empty-type-group
promotion in F17a).

**Validation evidence:**

- `python -m compileall -q tslc/src/tslc` — clean.
- `(cd tslc && python -m mypy)` — clean, 238 source files.
- `PYTHONPATH=tslc/src python -m pytest -q tslc/tests` — 1740 passed,
  70 skipped (the skips are the opt-in `--run-generated-builds` gates).
- `git diff --check` — clean.
- The generated C++/Rust build/value gates were **not** executed (read-only
  audit).

**Verdict:** the architecture is in genuinely good shape — the charters are
enforced, not aspirational, with rare meta-tests that AST-check boundary
rules. No finding blocks ongoing work. Drift concentrates in three places:
input-honesty holes at the parse/catalog boundary, string-shaped semantics at
the leaf renderers and the PIVOT exporter, and parallel compiler knowledge
accreting in `doctor`/maintenance and the newest explorer code.

---

## Part I — Consolidated findings (ordered by severity)

### Near-blocker

**F1. One bad string escape crashes `tslc check` and the language server with
a raw `SyntaxError`.**
`tslc/src/tslc/syntax/parser.py:424` feeds grammar-accepted strings to
`ast.literal_eval`; only Lark's `UnexpectedInput` is caught
(`parser.py:76-91`). The grammar's `ESCAPED_STRING` accepts any backslash
escape. Reproduced end-to-end: a valid extension block containing
`"bad \x escape"` raises an uncaught `SyntaxError` through
`authoring.check_catalog` — the boundary behind `tslc check` and the LSP —
with no diagnostic and no source location.
*Rule:* `tslc/CHARTER.md` §5 (diagnostics are structured values; pure logic
returns diagnostics).
*Repair:* wrap the literal evaluation in `try/except (ValueError,
SyntaxError)` and emit a spanned `TSL-OUTER-PARSE-BAD-STRING`.
*Prove:* parse a document containing `x "\x"`; assert one located error
diagnostic and no escaping exception.

### Major — correctness defects

**F2. Duplicate primitive declarations are silently accepted; the first
silently wins.**
`tslc/src/tslc/catalog/validation/schema_validation.py:84-99` covers only
`extension`/`language`/`translation` blocks; `Catalog.primitive`
(`catalog/model.py:661-670`) returns the first name match. Verified by
execution: two conflicting `add` declarations produce zero diagnostics and
which body wins depends on document sort order.
*Rule:* root `AGENTS.md` — clear diagnostics for malformed source; no silent
declaration-order-dependent conflict resolution.
*Repair:* extend the duplicate-block validator to primitives (name +
attribute identity) with a `RelatedLocation` to the first definition.
*Prove:* two same-name/same-attribute primitives yield a duplicate
diagnostic; masked/unmasked and `[aligned=true]`/`[aligned=false]` pairs
remain accepted.

**F3. `var<typed>` routes on a raw substring: `"uninit" in <payload text>`.**
`tslc/src/tslc/lower/region_handlers/declarations.py:117`:
`key = "var_array_uninit" if "uninit" in segments_text(groups[2]) else …`.
Any initializer merely containing "uninit" (e.g. `count_uninit`) silently
drops the value expression and renders an uninitialized declaration; the
corpus's `value(uninit::scalar)`
(`tsldata/primitives/load_store/construct.tsl:459`) is routed through the
*array* template while the separate `var_uninit` template
(`translate_cpp.tsl:64`) is unreachable from this path (C++ semantics differ:
value-init `{}` vs none).
*Rule:* TSIL boundary — recognize exact documented forms; no substring
classification of raw text.
*Repair:* structural check — groups[2] must be exactly one `value` region
whose body is `uninit::array` (route `uninit::scalar` to `var_uninit`);
diagnose other `uninit::*` spellings.
*Prove:* lower `var<typed>(type(base::in), x, my_uninit_count)` and assert
the initializer survives; pin `value(uninit::scalar)` → `var_uninit`.

**F4. The switch-arm scanner is comment-blind, unlike every other scanner
path.**
`tslc/src/tslc/ir/scan.py:766-781` (`_scan_switch_arms`) uses `_skip_ws` +
`inner.find("=>", i)` and never calls `_skip_opaque` (contrast `_scan` at
line 160 and `_match_bracket` at line 846). A block comment containing `=>`
between arms turns valid input into a hard
`TSL-BODY-MALFORMED-REGION: malformed switch arms` error
(`body_validation.py:62-73`); a line comment before a label folds into the
label string, so `_selected_switch_label` (`control.py:551-557`) mismatches
and comment text leaks into the emitted `if constexpr(sel == …)` label.
*Rule:* `tslc/AGENTS.md` — scanning owns delimiters, nesting, spans,
**comments**.
*Repair:* skip opaque text while locating labels and arrows; exclude comment
spans from captured labels.
*Prove:* scan a switch with a line comment before an arm and a block comment
containing `=>` between arms; assert clean labels and no malformed regions.

**F5. Rust backend silently assumes one varying overload position; C++
handles the general case.**
`tslc/src/tslc/backend/rust.py:183` — `vi = varying_positions(specs)[0]  #
one varying position in scope` (also `rust.py:319`, `rust.py:674`); contrast
`backend/cpp.py:383,398,422` which handles arbitrary positions.
`rust_validation.py` checks extensions and const-arg types but not this. A
future two-position overload renders correct C++ and broken Rust with no
diagnostic.
*Rule:* diagnose unsupported capabilities before rendering.
*Repair:* emit `TSL-BACKEND-RUST-UNSUPPORTED-MULTI-POSITION-OVERLOAD` in
`validate_rust_profiles` when `len(varying_positions(specs)) > 1`.
*Prove:* two synthetic specializations varying at positions 0 and 1 → error
diagnostic, no Rust artifact.

**F6. Rust pointer-cast semantics decided by sniffing rendered text.**
`tslc/src/tslc/backend/rust_translation.py:250-288` — `render_pointer_cast`
renders the expression to a string, then branches on
`expr_text.startswith("&mut ")` / `startswith("&")` to choose
`core::ptr::addr_of_mut!`/`addr_of!` vs `expr as *const T`. `& mut x`
(double space), `&(x)`, or macro output starting with `&` silently takes the
wrong branch and changes generated-code semantics.
*Rule:* TSIL boundary — shared semantics become typed lowering values, not
raw-string ladders; templates format decided values.
*Repair:* add `is_address_of` (and mutability) to the pointer-cast lowering
value; diagnose unclassifiable raw text instead of rewriting.
*Prove:* dialect unit tests: `&mut buf` → `addr_of_mut!`; `& mut buf` /
`&(x)` lower via the typed flag or are diagnosed — never mis-rendered.

**F7. The PIVOT planner is a regex rewrite engine over lowered target text,
and it can corrupt output.**
`tslc/src/tslc/pivot/planner.py:45-70` (regex inventory), `378-473`
(`_emit_slot`), `790-804` (strips Rust `unsafe { }`), `864-889`
(`_split_statements`), `892-919` (`_local_renames`, `_replace_identifiers`),
`931-953` (marker re-discovery). `_replace_identifiers` substitutes *every*
identifier token context-blind: a parameter named `min` in a body calling
`std::min(...)` rewrites the qualified call itself → silently corrupt YAML.
Typed call sites captured by `PivotCallLowerer` (`pivot/_lowering.py:99-101`)
are flattened into `__tslc_pivot_call_N(` string markers and re-found by
regex — a typed boundary deliberately created and then thrown away.
`tslc/DESCRIPTION.md:96-98` blesses *validating* lowered bodies and
rejecting; this rewrites.
*Rule:* TSIL boundary — no ad-hoc C/C++/Rust parsers or raw-string rewrite
ladders.
*Repair:* keep call sites typed end-to-end (return the body as a
segment/`RenderField` sequence with typed call nodes); inline by composing
typed pieces; restrict regexes to rejection.
*Prove:* pivot-export a primitive whose parameter name collides with an
identifier in a qualified call (parameter `min`, body
`complete(std::min(a, b))`); assert the emitted `direct:` statement is not
corrupted.

### Major — boundary and extensibility drift

**F8. `doctor.py` hard-dispatches on backend-id strings and crashes on
backend #3.** (Found independently by two reviewers.)
`tslc/src/tslc/doctor.py:281-285` (`if backend_id == "cpp": … if "rust": …
raise ValueError`) and `:297-304` (compiler/target/linker chosen the same
way). `BackendCapability` already owns `verify_driver()`/`verify_profiles`;
the rest of the pipeline is proven backend-agnostic by the fake-backend test
(`test_pipeline_structure.py:175-199` pattern, `test_output_format.py:33-61`).
*Rule:* register backend IDs/capabilities at the registry boundary; do not
scatter backend string lists.
*Repair:* add `verify_profile(machine_profile, family)` and
`toolchain_report(config, profile)` hooks on `BackendCapability`; doctor
consumes the capability.
*Prove:* monkeypatched third backend → doctor report entry, not `ValueError`.

**F9. `render/` imports eight underscore-private functions from
`backend/cpp_profile`.**
`tslc/src/tslc/render/cpp_project.py:9-21` (`_cpp_registration`,
`_cpp_includes`, `_cpp_native_registration`, `_cpp_sized_registration`,
`_cpp_inferred_simd_registrations`,
`_cpp_compiler_builtin_fixed_registrations`, `_cpp_primitive_tags`,
`_guard_cpp_profile`); `render/cpp_build.py:17`
(`_cpp_compile_guard_condition`). Header-group partitioning, guard grouping
(`cpp_project.py:368-392`), and registration assembly are decision-shaped
work executing inside the render stage.
*Rule:* pipeline ownership — `backend/` owns translation/emitted profiles;
`render/` formats finalized values; no private names across a package
boundary.
*Repair:* promote the real API to public names, or better, expose one typed
`CppProfileRenderModel` built from `EmittedProfile` that `cpp_project.py`
only formats.
*Prove:* an import-boundary meta-test asserting `render/` imports no
`_`-prefixed names from `tslc.backend.*`.

**F10. Installed-wheel maintenance commands crash at import time; six
divergent copies of repo-root discovery.**
`_find_repo_root`/`_repo_root` duplicated in `maintenance/explain.py:60-67`,
`maintenance/render_preview.py:17-24`,
`maintenance/coverage_inventory.py:37-44`,
`maintenance/generation_snapshot.py:32-39`,
`maintenance/performance_benchmark.py:27-34`,
`maintenance/documentation.py:808-812`. Behavior diverges (fallback vs
`RuntimeError`); `coverage_inventory.py:44` and `generation_snapshot.py:39`
evaluate **at module import** (verified), so on an installed wheel `tslc
inspect`, `tslc coverage ratchet`, and `tslc coverage inventory` crash with a
raw `RuntimeError` before argparse. `stage_dump.py:41`,
`coverage_ratchet.py:36-42`, `benchmark_coverage.py:43-47` import the
resulting private constants cross-module. Also a second, parallel
default-discovery mechanism next to `project_config.py`.
*Rule:* DRY (duplicated compiler knowledge); no import-time filesystem
probing; CLI owns exit behavior.
*Repair:* one lazy helper (or reuse `project_config.discover_config`) called
inside each `main()`, converting failure to `parser.error(...)`; delete the
module-level constants.
*Prove:* import every `tslc.maintenance.*` module with the root probe
monkeypatched to fail; assert import succeeds and `main([...])` exits 2 with
a readable message.

**F11. `metadata_audit.py` re-implements the pipeline's dependency-closure
walk and skips catalog validation.**
`tslc/src/tslc/maintenance/metadata_audit.py:389-449` rebuilds
select→scan→lower→worklist with weaker dedup (keyed by primitive name only,
lines 395/398) than `pipeline.py:330-374` (`(primitive, type, scope) →
backend`); `:273-310` re-implements loading without `validate_catalog`;
`:757-772` re-implements `sources.expand_source_paths`.
`benchmark_coverage.py:44-51` similarly hand-rolls parse+build.
*Rule:* DRY — maintenance tools reuse pipeline knowledge, not fork it.
*Repair:* drive `_generate_loaded(request, inputs, render_artifacts=False)`
as `explain.py`/`render_preview.py` already do; load via
`authoring.check_catalog` + `expand_source_paths`.
*Prove:* (a) a corpus with a `validate_catalog` error makes `audit_metadata`
return that error; (b) suggestions match the pipeline's `result.coverage`
facts when a callee lowers for only one backend.

**F12. The new explorer re-implements selector candidate discovery.**
`tslc/src/tslc/lsp/primitive_explorer.py:407-444` (status ladder) and
`:469-500` (`_authored_candidates`, the same walk as
`select/selector.py:446-453`) ignore selector admission rules
(masking-variant expansion, `requires` clauses, `where` target constraints,
arity/overload filtering). `Selector.evaluate_candidates` already exposes
typed per-candidate rejections (consumed by `maintenance/explain.py:230,378`).
Freshest code in the repo; precisely the second-selector drift `CHARTER.md`
§8 exists to prevent, one layer below the (clean) TypeScript client.
*Rule:* CHARTER §8 — live features are projections of compiler-owned
selection; one owner for shared knowledge.
*Repair:* for empty slots, call `selector.evaluate_candidates(...)` and
project typed rejections into `SlotStatus`/`detail`; delete the chain walk.
*Prove:* an implementation on the extension chain rejected by a
selector-only rule (unsatisfied `requires`) shows the selector's rejection
reason, not "missing".

**F13. PIVOT carries a third copy of backend type-spelling knowledge.**
`tslc/src/tslc/pivot/planner.py:662-695` (`_concrete_type`:
`std::size_t`/`usize`, `std::uint{w}_t`/`u{w}`), `:698-730` (`_fixed_type`:
member-type spellings), `:770-781` (`_fixed_vector_spelling`: Rust
`VectorFor<…>::Vec` built inline while the C++ arm correctly reuses
`dialect.types.fixed_vector_spelling`). Owners:
`backend/signature_types.py:102-254`, `backend/rust_algorithm.py:669`.
`benchmark/render_cpp.py:279-290` is a pre-existing second copy; pivot adds
a third.
*Repair:* add member/fixed forms to `SignatureTypeForms`; route pivot through
`BackendSignatureTypes`; move the Rust fixed spelling beside its owner.
*Prove:* unit test asserting pivot's kind→type projection equals the
registry's per kind.

**F14. Value-test plans smuggle semantics as magic strings, and renderers
re-decide plan facts (duplicated per backend).**
(a) `mask_store` overwrites the real result kind with `result_kind="packed"`
(`value_tests/_case_memory.py:161-186`), decoded by
`_render_cpp_memory.py:67` and `_render_rust_core.py:256`.
(b) Renderers re-derive facts the plan already guarantees with silent `or`
fallbacks (`_render_cpp_memory.py:25, 50, 80, 122, 144, 211-213, 274, 347`;
`_render_rust_memory.py:46, 75, 105, 157, 188, 266-268, 331-333`;
`_render_rust_conversion.py:16, 46, 74, 105`; `_render_rust_core.py:272-275`).
(c) A call-convention decision is made from raw signature tuples in both
backends: `pointer_indices = tuple(case.invocation.param_kinds) == ("cptr",
"cptr", "sImm")` at `_render_cpp_memory.py:214` and
`_render_rust_memory.py:269`, plus masked/unmasked branching on
`case.inputs.masks` in both.
*Rule:* backend/render boundary — renderers format decided values; typed
plans.
*Repair:* typed `storage: Literal["packed","unpacked"]` and `index_style:
Literal["register","pointer"]` facts decided once at planning; remove
fallbacks (fail loudly); add `MEMORY_LENGTH` to `mask_pointer_load`
requirements (its planner always sets it, `_case_memory.py:143`).
*Prove:* construct plans missing the facts and assert the renderer raises
rather than inventing values; assert cpp and rust agree on buffer length for
a fixed plan; packed plan keeps `result_kind == "void"` plus the typed
storage fact.

**F15. Scalable value-test planners embed C++ spellings into typed plans.**
`_case_scalable.py:135-144`, `_case_scalable_masks.py:73-84, 161-181,
255-278, 347-358, 431-451`, `_case_scalable_memory.py:81-90` — planning
builds `f"tsl::simd<{...}, tsl::{ext}>"`, appends `"…ull"` suffixes, and
pre-quotes case names into
`ValueTestScalable.runtime_lanes_expr/mask_from_bits_exprs/mask_check_expr`.
The renderer already owns this spelling
(`render_cpp_helpers.scalable_header`, `render_cpp_helpers.py:138-147`).
*Rule:* value_tests plan typed behavior before rendering; planning stays
backend-neutral until renderer capability is declared.
*Repair:* store the raw extension template plus typed substitution values
(mask bits, authored lanes, base spelling, extension name); do the final
fill and `tsl::simd` spelling in the C++ renderer.
*Prove:* planned `ValueTestScalable` fields contain no `"tsl::"`/`"ull"` for
an SVE case; golden-compare rendered output before/after.

**F16. Value-test coverage honesty gaps.**
(a) Three distinct drop causes share one wrong reason:
`ValueTestPlanner._supported_cases` drops for kind-unsupported
(`planner.py:245-246`), missing differential harness closure (`:247-248`),
and header-group conflict (`:249-251`), but `case_coverage`
(`coverage.py:57-66`) reports all as `backend_unsupported` with "planned case
kind is not supported by this backend renderer" — a missing harness
specialization is a selection/closure problem, and the message is not
actionable.
(b) Scalable builders pre-filter on `backend.case_kinds`
(`_case_scalable.py:37,103`; `_case_scalable_masks.py:39,123,222,318,396`;
`_case_scalable_memory.py:42`), so a scalable-only case misreports as
`authored_unplanned` instead of `backend_unsupported`.
(c) Synthetic fuzz cases dropped by `_supported_cases` get no coverage entry
or diagnostic (`planner.py:116-128`); `fuzz=True` against Rust (registry
lacks `differential_fuzz`, `render_rust.py:83-118`) silently yields nothing.
*Rule:* coverage, not fantasy completeness; deterministic actionable skip
reasons.
*Repair:* a typed drop cause from `_supported_cases` threaded into
`case_coverage`; remove the `case_kinds` pre-check from scalable builders;
coverage status or warning for suppressed fuzz cases.
*Prove:* harness-absent differential case names the harness in its reason;
scalable-only case against a non-scalable support reports
`backend_unsupported`.

### Minor findings, grouped by theme

**Catalog input honesty**

- **F17a.** Malformed `types` blocks silently promote empty/missing groups
  (`catalog/_builder_blocks.py:14-21`; validation checks only
  unknown/duplicate fields, `schema_validation.py:144-152`). Verified by
  execution: `types "notalist"` → group with zero members, no diagnostics.
  Aggravated: `type_group_specificity = len(members)`
  (`model.py:717-723`) makes an empty group the *most specific* selector
  while matching nothing. Repair: require a non-empty scalar list
  (`TSL-CATALOG-TYPE-GROUP-MALFORMED`).
- **F17b.** `machine_profiles._runner` silently rewrites authored data
  (`catalog/machine_profiles.py:587` — `lstrip("-")` on SDE profile values);
  the unchecked `load_machine_profiles` (`:94-100`) drops structural
  diagnostics (production uses `..._checked`; tests still use it). Repair:
  diagnose the leading dash (`TSL-PROFILE-MALFORMED-RUNNER`); delete the
  unchecked loader.
- **F17c.** No catalog-boundary test for boolean-wildcard expansion
  (`_builder_primitives.py:113-125`); only indirect coverage, partly behind
  the generated gate. Repair: direct `test_catalog.py` case for
  `[aligned=*, packed=*]` → 4 variants.

**Duplicated compiler knowledge**

- **F18a.** The `param_types` condition grammar and base-width-constraint
  grammar exist twice — builder (`_builder_primitives.py:37-40, 158-174,
  213`) vs validator (`validation/_schema_primitives.py:38-40, 68, 277,
  483-492`; `_schema_common.py:139-142`) — and the builder *silently drops*
  entries its regex rejects (`_builder_primitives.py:143-145`), trusting the
  validator's identical copy. Repair: one shared parsing module imported by
  both. Prove: table-driven test that promotion and validation agree
  case-by-case.
- **F18b.** Three copies of the parse-tree accessor helpers
  (`catalog/_builder_common.py:38-92`,
  `catalog/validation/source_spans.py:17-63`,
  `catalog/test_promotion.py:185-236`) encode "children = explicit children
  OR inline `{}` map entries" three times. Repair: one shared accessor
  module; delete the dead aliases `_entry`/`_field_text`.
- **F18c.** `catalog_index.py:291-320` re-interprets implementation
  selectors with rules that already diverge from the builder
  (`_builder_implementations.py:146-178`): bracket heads like `[sse, avx2]`
  are indexed as one literal reference (never resolving), and `where`/target
  levels are missed — find-references silently under-reports. Repair: share
  `_selector_extensions`; split bracket heads with sub-spans.
- **F18d.** `lsp/specialization_context.py:159-178` re-parses the same
  selector-head list syntax. Repair: same shared helper.
- **F18e.** `IfLowerer` parses boolean conditions twice
  (`lower/region_handlers/control.py:228-247` evaluate vs `:249-277`
  render, plus `:25-73` helpers) — the accepted grammar is defined twice and
  can drift. Repair: parse once into a typed Or/And/Leaf term; both walks
  consume it.
- **F18f.** Regex `\b name \b` classification of raw text as "symbolic
  generic-param expression", duplicated (`control.py:272-276`,
  `calls.py:210-214`): `foo(PreserveSign)` passes through verbatim as if a
  valid symbolic predicate. Repair: resolve generic-param names as
  first-class scope symbols in `resolve_query_leaf`; restrict pass-through
  to exact `ident`/`!ident` via one shared helper.
- **F18g.** Loop-selector semantics parsed twice with different tokenizers
  (`lower/implementation_state.py:98-101` vs `control.py:347-362`). Repair:
  `parse_loop_selector` in `ir/region_syntax.py`.
- **F18h.** Four hand-rolled recursive segment walkers;
  `lower/body_rendering.py:212-232` (`_find_region`) hardcodes `if`/`switch`
  and omits `loop` blocks, so `complete` inside a `loop` block is invisible
  to the pre-check (`TSL-LOWER-NO-COMPLETE` on a valid body). Other walkers:
  `catalog/validation/body_validation.py:78-94`,
  `lower/implementation_state.py:61-77`, `lower/lowerer.py:731-757`.
  Repair: one child-iteration helper on `Region` in `ir/segments.py` used by
  all four. Prove: the walkers visit the same region set for a body using
  every structural keyword; pin complete-inside-loop.
- **F18i.** Lane/tiling knowledge duplicated between value_tests and
  benchmark: lanes-from-width math (`_case_conversion.py:257-262` vs
  `benchmark/planner.py:172-176`); tiling (`benchmark/correctness.py:346-349`
  vs `render_cpp_helpers.py:150-176`); the cross-lane tiling guard in two
  homes (`_case_scalable_common.py:16-30` vs `benchmark/planner.py:417-421`);
  a shared mix constant duplicated (`_case_conversion.py:214`,
  `benchmark/scenarios.py:19`). The tiling-soundness invariant is
  safety-relevant (`lane_model.py:25-31`). Repair: shared lane-math/tiling
  helper in `value_tests`.

**Backend and render leaf drift**

- **F19a.** `backend/rust_algorithm.py:94-635` is six copy-pasted impl
  families (~100 lines each; near-duplicate triplets at 117-134/137-154,
  368-384/387-403, 431-447/450-466, 494-506/509-521, 549-562/565-578,
  606-619/622-635). One typed
  `HelperImplSpec(trait, method_signature, forwarded_call, feature)` table
  plus a single renderer; prove byte-identical output via the golden-hash
  style of `test_profile_rendering.py`.
- **F19b.** Facade kind→type ladders duplicate `signature_types.py` in three
  places (`backend/cpp.py:534-563`, `backend/rust_facades.py:125-148`,
  `render/documentation_project.py:555-572`). Repair: add facade forms to
  `SignatureTypeForms`; keep the doc-phrase table doc-owned.
- **F19c.** `render/documentation_project.py` hardcodes domain knowledge:
  `_target_class_parts` (`:367-384`, incl. `extension.name.startswith("sve")`
  at 377), `_public_target_family` (`:387-388`, `"arm" -> "aarch64"`),
  `_target_class_sort_key` (`:408-425`, hardcoded family ranks),
  `_type_short_label`/`_type_sort_key` (`:579-616`, reparsing `si`/`ui`
  prefixes). Typed owners exist
  (`catalog.target_families.ProfileFamilyCapability.sort_order` — used
  correctly by `render/cpp_build.py:401-404` — and `catalog.scalar_types`).
- **F19d.** Feature-name spelling repairs hardcoded in Python
  (`backend/target_capability.py:9-32`: `{"cpp": {"rdrand": "rdrnd"}}` plus
  `sse4_`/`avx512_` prefix rewrites) while the machine-profile
  `alternatives` mechanism already exists for exactly this. Repair: move to
  source data; diagnose unknown spellings.
- **F19e.** C++ smoke-test instantiation decided at render time
  (`render/cpp_project.py:415-521`: lane-count literals, windowed counts via
  `DEFAULT_SUPPORT_POLICY.windowed_lane_count`, per-kind concrete arg
  types). The value-test subsystem exists to avoid exactly this pattern.
  Repair (low urgency): typed `SmokeInstantiation` list emitted beside
  `validate_cpp_profiles`.
- **F19f.** The anti-string-surgery guard test
  (`tslc/tests/test_render_model.py:210-236`) checks only
  `cpp.py`/`rust.py`/`cpp_project.py`/`rust_project.py` and only
  `.replace()` on `body`/`body_text` receivers — it misses
  `rust_translation.py:250-288, 354-391` (where F6 lives),
  `signature_types.py:265-267` (`"*mut "` prefix strip), and
  `rust_facades.py:122` (regex-parsing a 122 KB static Rust asset for
  public fn names). Repair: extend the guard; replace the asset regex scan
  with a compiler-owned manifest of reserved names.

**Benchmark extensibility**

- **F20a.** Scenario families are switch-ladders, not a registry — one new
  family touches ≥6 files: `benchmark/model.py:402-539` (~140-line
  isinstance validation ladder), `benchmark/planner.py:200-386` (shape
  ladder) and `:548-622` (`_correctness_canonical_fields` isinstance ladder,
  inconsistent with scenarios owning `canonical_fields()` as methods),
  `render_cpp_scenarios.py:40-58`, `render_cpp.py:138-213`. The value-test
  case-kind registry (`case_capabilities.py` + `renderer_capability.py`) is
  the in-repo pattern to copy. Prove: a registry-consistency test mirroring
  `test_value_test_planning.py:2254-2260`.
- **F20b.** The harness-discovery/closure guard is copy-pasted six times in
  `benchmark/planner.py:213-241, 257-265, 282-291, 309-318, 330-343,
  352-377`. Repair: one `_require_harness` helper.
- **F20c.** Five near-identical scalable case builders (~50 duplicated lines
  each) across `_case_scalable_masks.py:29-478`, `_case_scalable.py:27-172`,
  `_case_scalable_memory.py:30-125`. Repair: shared
  `ScalableTestExprs` helper (natural companion to F15).
- **F20d.** The C++ benchmark timing skeleton is restated five times
  (`render_cpp_scenarios.py:117-148, 203-243, 282-319, 338-389, 407-445,
  464-499`). Repair: one skeleton builder taking typed parts; prove with a
  golden comparison.
- **F20e.** Optional pattern hooks are duck-typed via `getattr`
  (`planner.py:116` `fuzz_cases`; `_pattern_base.py:103-111`
  `unplanned_reason`) outside the declared `ValueTestPattern` protocol.
  Repair: declare them on the protocol / a `FuzzCapablePattern`.

**Maintenance and CLI robustness**

- **F21a.** `tslc explain` calls the private
  `selector._emit_extensions` (`maintenance/explain.py:174` →
  `select/selector.py:361`). Repair: public `Selector.emitted_extensions()`
  (it already has a second internal caller at `selector.py:418`); add an AST
  guard forbidding `._` access into `tslc.select` from `tslc.maintenance`.
- **F21b.** `maintenance/documentation.py:700-711` mutates process-global
  `os.environ` to pass env to a runner because `CommandRunner` (line 35)
  has no env parameter. Repair: extend the runner signature; merge in
  `_run_subprocess` (already copies `os.environ` at line 750).
- **F21c.** `maintenance/_generation_snapshot_semantics.py` (579 lines)
  hand-mirrors ~25 domain types with no drift guard — a new field on
  `LoweredSpecialization`/`ValueTestCasePlan` silently stops being covered.
  Repair: a `dataclasses.fields()`-walking completeness test with an
  explicit omission allowlist.
- **F21d.** `tslc/tests/test_determinism.py:19-24` runs generation twice in
  one process (shared `PYTHONHASHSEED`) comparing only
  `artifacts.digest_manifest()` — hash-order nondeterminism is invisible to
  it; the committed sha256 goldens in `test_profile_rendering.py:71-101` are
  the real net. Repair: a subprocess-based double run under different
  `PYTHONHASHSEED` values comparing the full snapshot document including
  diagnostics/coverage/skips.
- **F21e.** Host-specific absolute toolchain paths in
  `output/_verify_cpp_config.py:18` (`/opt/intel/oneapi/compiler/2025.0/bin/icpx`),
  `:53`, `:77` (`/opt/wasi-sdk/bin/clang++`). Gated and overridable, but
  devcontainer knowledge inside compiler source that will silently rot.
  Repair: move defaults into configuration data.
- **F21f.** Verify/documentation driver callbacks accumulate outputs via
  mutable out-params (`output/verify_drivers.py:27-53`; `doctor.py:214-225`;
  `maintenance/documentation.py:57-69`). Repair: drivers return a frozen
  result object; the orchestrator folds.
- **F21g.** CLI option-parsing/toolchain-merge logic duplicated
  (`cli.py:392-420` vs `doctor.py:133-145, 382-391`; `_split` re-implemented
  at `cli.py:388`, `doctor.py:394`, `documentation.py:804`,
  `metadata_audit.py:775`). Repair: small shared `_cli_options.py`.
- **F21h.** `cli.py:121-385` (`_generation_main`, 265 lines) keeps the
  generate/build/test command core inside the router, against
  `tslc/AGENTS.md`'s "focused commands keep testable cores outside the
  router" (mitigated: cli.py owns legacy flat-generation compatibility and
  is covered end-to-end). Repair: extract a `generation_command.py` core.
- **F21i.** `maintenance/coverage_inventory.py:63-83` derives
  "build-verified" facts by AST-sniffing `test_build_verify.py` for
  `primitives=[...]` keywords — a pytest refactor silently zeroes the
  verified column of the committed report. Repair: export the list as a
  shared constant both sides import.

**LSP resilience and typing**

- **F22a.** An unexpected exception in the first corpus check wedges the
  server: `lsp/server.py:410-415` awaits `initial_check_complete` with no
  timeout; `_check_and_publish` (`:418-435`) has no try/except, so a raise
  inside `asyncio.to_thread(workspace.check, …)` leaves the event unset and
  every index-backed request hangs silently. Defect-triggered only
  (`check_catalog` is designed to return diagnostics), but the failure mode
  is a silently wedged server. Repair: `try/finally` setting the event plus
  a `window/showMessage`/log. Prove: monkeypatch `AuthoringWorkspace.check`
  to raise; a subsequent definition request completes empty instead of
  hanging.
- **F22b.** Untyped duck-typing at internal typed boundaries:
  `pivot/planner.py:969-974` (`getattr(target, "base_tag", …)` on the typed
  `VectorIdentity`); `lsp/specialization_context.py:206-212` (getattr span
  comparison). Repair: type the parameters; compare fields directly.
- **F22c.** Disk reads inside request handlers on the event loop
  (`lsp/features.py` `_locations` / `server.py:599-608` via
  `workspace.document_text` → `path.read_text`, `workspace.py:146-155`).
  Latency-only today; fix only if profiling warrants.

**Typed-model consistency and migrations**

- **F23a.** Stringly-typed classification in the frozen catalog model where
  `Literal` is the established local pattern: `catalog/model.py:307`
  (`TestArg.kind`), `:337` (`TestCase.role`), `:380` (`MaskPolicy.kind`),
  `:421` (`ImaskPolicy.kind`), `:262` (`GenericParam.kind`), `:530`
  (`vector_bits_kind`); allowed-value sets maintained a second time in
  validators (`_schema_extensions.py:58-71`, `_schema_primitives.py:36`).
  Repair: `Literal` aliases with validator frozensets derived via
  `typing.get_args`. Similarly `lower/lowerer.py:110, 156` (result_kind /
  mask_policy comments instead of Literals) and `selector.py:708-715`
  (width-constraint relation as a raw string — unknown relations silently
  select nothing; make it an enum validated at catalog build, exhaustive
  with `assert_never`).
- **F23b.** The `Diagnostic(location=...)` compatibility shim
  (`diagnostics.py:55-62`, "accepted while compiler producers migrate")
  still has ~15 producer call sites across 10 files (`pipeline.py`,
  `authoring.py`, `sources.py`, `lower/body_rendering.py`,
  `catalog/machine_profiles.py`, `lsp/features.py`, `value_tests/planner.py`,
  `value_tests/coverage.py`, `syntax/parser.py`). Finish the span migration
  or declare the parameter permanent — an open-ended "while producers
  migrate" shim is the compatibility-layer shape the charter budgets
  against.
- **F23c.** Defensive `getattr` on the fully typed frozen lowering env
  (`lower/_query_leaf.py:39, 49-50, 57-58`). Repair: direct attribute
  access; mypy then guards renames.
- **F23d.** `x86::` value-constant namespace hardcoded in the shared query
  leaf resolver (`lower/_query_leaf.py:56-63`) — the first `neon::`/`sve::`
  constant requires editing the generic evaluator. Repair: registered
  namespace prefixes resolved through backend templates.

**Module cohesion**

- **F24a.** `pivot/planner.py` (1116 lines, largest module in the repo) is a
  catch-all mixing profile cover-set optimization (`:1023-1068`), selection
  orchestration (`:136-249`), the recursive inline engine (`:378-516`),
  callee resolution (`:518-569`), the straight-line body law (`:807-889`),
  type projection (`:662-758`), and text utilities (`:927-966`). Split along
  those seams (F7/F13 shrink it substantially first).
- **F24b.** `select/selector.py:174-286` (`select_profile`) is 7-level
  nesting steered by an `emitted_free` flag with two woven `break`s; extract
  a slot-enumeration generator and an early-returning free-function path
  (behavior-preserving; existing suites prove it).
- **F24c.** Value-test private-module naming is inconsistent
  (`render_cpp_helpers.py` public vs `_render_rust_helpers.py` private;
  `case_helpers.py` vs 22-line `_case_common.py`), blurring which helpers
  are contract. The split itself is coherent and meta-tested
  (`test_value_test_planning.py:2098-2226`); just normalize the convention.
- **F24d.** `pipeline.py` cohesion nits: `_record_render_extensions`
  (`:541-582`) encodes render-preference policy inside orchestration;
  `_skip_status` (`:643-646`) couples to the string
  `"TSL-LOWER-POLICY-DEFERRED-SIGNATURE"` (export the code constant from
  `lower/`); `_coverage_key`/`_skipped_key` (`:763-794`) are byte-identical
  over the twin 11-field `CoverageEntry`/`SkippedEntry` dataclasses;
  `_DEFAULT_BACKENDS` (`:52`) is captured at import time as a dataclass
  default, so registry monkeypatching cannot affect it.

### Nits

- `ir/scan.py:176-186` — manual 9-field `Region` reconstruction instead of
  `dataclasses.replace(...)`; a future field silently resets.
- `ir/scan.py:861-874` — `_skip_opaque` doesn't treat char literals as
  opaque; a raw `'"'` starts string-skipping and can swallow a following
  region.
- `lower/region_handlers/helpers.py:50` — `"<" + ", ".join(args) + ">"`
  hardcodes C++ template-argument syntax in the lowerer; the backend should
  spell it.
- `lower/target_vectors.py:251` — `windowing = "direction" in
  …attributes` infers semantics from attribute presence.
- `select/selector.py:577-581` — load-bearing ranking comment placed after
  the `return`.
- `ir/region_syntax.py:34-65` — `split_arg_groups` counts a bare `<`
  comparison as nesting; failure mode is a diagnosed arity skip, but the
  docstring should state the limitation.
- `backend/cpp_profile.py:143-145, 322-324` and
  `backend/rust_implementation_state.py:154-157` — assert-based render
  backstops vanish under `python -O`; raise explicitly.
- `backend/rust_translation.py:344-391` — cosmetic paren-stripping ladder on
  return values; largely redundant given rustfmt; candidate for deletion.
- `syntax/parser.py:43-54, 161-166` / `syntax/ast.py:33-45, 121-124` —
  `ParsedPrimitiveField.kind` is dead speculative typing (no consumer reads
  it) that also drifts from `KNOWN_PRIMITIVE_FIELDS`.
- `syntax/parser.py:422-428` — inline TSIL body spans misalign under string
  escapes (decoded text vs raw span): body diagnostics drift one column per
  escape.
- `catalog_index.py:392-399, 68-74, 113-121` — redundant per-span
  `Path.resolve()` syscalls inside pure index building; `SourceLoader`
  already resolves (`sources.py:32`).
- `value_tests/planner.py:405, 428` — stale `# noqa: ANN001` on annotated
  functions.
- `value_tests/case_helpers.py:316-319` — `function_name` `del`s two of its
  three parameters.
- `value_tests/_render_cpp_memory.py:91-95` — `lines.insert(5, call)`
  index-based splicing.
- `benchmark/planner.py:84` — `backend_id = "cpp"` local literal; hoist to a
  class constant.
- `pivot/cli.py:9` — imports private `tslc.api._expand_sources`; public
  `sources.expand_source_paths` exists (`sources.py:88`).
- `pivot/planner.py:986-993` — `_isa_label` infers feature implication by
  string prefix ("sse" ⊂ "sse42" by naming accident); affects only the YAML
  `isa` label today.
- `pivot/planner.py:119-121, 587` / `pivot/_lowering.py:34-49` — shared
  mutable `PivotCallCapture` with reset-then-collect; breaks under
  reentrancy. Fresh capture per lowering.

---

## Part II — Open questions / assumptions

1. Is the PIVOT exporter accepted as prototype scope? `tslc/DESCRIPTION.md`
   sanctions validate-and-reject; the rewrite engine (F7) goes beyond that,
   so either the doc or the code should move.
2. Is the "installed `tslc` command exposes the same tools" claim intended to
   cover the maintenance subcommands? If yes, F10 is user-facing; if not,
   the docs overstate.
3. Is the `Diagnostic(location=...)` shim (F23b) a live migration or a
   permanent API?
4. Rust + `value_test_fuzz` silently producing nothing (F16c): intended gap
   or oversight?

## Part III — Design health summary

**Strengths (verified across all six reviews):**

1. **The stage-ordering contract is real and machine-checked.** `pipeline.run`
   demonstrably sequences per-profile closure + prune + emitted-name
   finalization → backend validation → strict gate → value-test planning →
   benchmark planning → error gate → render; `render_artifacts=False` stops
   exactly where `tslc/AGENTS.md` claims. `test_pipeline_structure.py`
   AST-checks that no backend literals reach the pipeline, `lower/` never
   imports `tslc.render`, and the renderer cannot finalize names or plan.
2. **Registry integrity is enforced, not hoped for.** Region keywords flow
   from `ir/region_registry.py` with import-time cross-checks
   (`scan.py:706-719`, `body_validation.py:430-442`) and tests equating
   descriptors == scanner keywords == lowerer registrations == shell
   validators, plus a docs-sync test pinning `docs/tsl-keywords.md`. A new
   call-shaped keyword is genuinely additive.
3. **Determinism is engineered, not incidental.** Sorted freezes at every
   mapping boundary, sorted source loading/diagnostics/artifacts, double-run
   digest tests plus committed sha256 goldens, name-derived fuzz seeds,
   protocol-versioned benchmark manifest hashes.
4. **The frozen-model discipline is real and tested** —
   `@dataclass(frozen=True, slots=True)` throughout with `__post_init__`
   freezing, and `test_catalog.py:409-446` asserting read-only behavior
   across the model surface.
5. **Charter §8 is structurally enforced for the editor.** Live features are
   pure projections of an immutable `WorkspaceSnapshot`; tests monkeypatch
   `Lowerer.lower` to prove the explorer never lowers, that caches never
   re-select, and that navigation never triggers a corpus check. The
   TypeScript client contains no compiler semantics; the TextMate keyword
   inventory is generated from `tslc list regions` with a staleness gate.
6. **The value-test plan/render boundary is self-defending** — per-kind
   invariants validated at plan construction against one requirements
   registry, renderer capabilities validated against the same registry, and
   source-level meta-tests enforcing the boundary for both backends.
7. **Boundary claims in `tslc/AGENTS.md` match the code** (authoring loads no
   machine profiles or render assets; check stops before planning;
   render_preview writes nothing and invokes no toolchains) — no doc/code
   drift found on those claims. `SystemExit` hygiene is perfect (entrypoints
   only); the `./tslctmp` scratch rule holds everywhere.

**Weakness pattern:** the failures are consistent in kind — semantics
traveling as strings (F3, F6, F7, F14, F15) and tools or new features
re-deriving what an owned stage already computes (F8, F11, F12, F13, most
minors). There is no framework rot or speculative abstraction; the charter's
plumbing budget is respected. It is the opposite failure mode: leaf code
taking shortcuts past the typed spine the project already built.

## Part IV — Suggested next slices

Each is one reviewable slice per `PLANS.md`:

1. **Parse/catalog honesty:** F1 + F2 + F17a — three small diagnostics at one
   boundary, highest author-facing payoff.
2. **TSIL correctness pair:** F4 (comment-aware switch arms) + F3
   (structural uninit check), both with pinning tests.
3. **Rust backend guards:** F5 validation error + F6 typed pointer-cast
   fact; extend the string-surgery guard test (F19f) in the same slice.
4. **Doctor through the registry:** F8 via `BackendCapability` hooks, proven
   by the existing fake-backend test pattern.
5. **Maintenance CLI hardening:** F10's shared lazy repo-root helper.
6. **Explorer status via `evaluate_candidates`:** F12, before the explorer
   grows more verdict logic on the forked walk.
7. **Value-test typed facts:** F14 (+F16's typed drop causes) — one slice per
   the add-value-test-shape skill.
8. **PIVOT typed inlining (F7/F13/F24a):** the one item needing a written
   plan first — a redesign of the inline engine, not a patch.

## Part V — Audit coverage limits

Not inspected (union of the six reviews' declared gaps):

- The generated C++/Rust build/value gates were not executed; no compilers,
  SDE/QEMU, or generated binaries were run.
- The embedded C++/Rust content of the large static assets
  (`tsl_algorithm.hpp/.rs`, `tsl_core.*`, `rust_algo_wrappers.rs`,
  value-test/benchmark `.tmpl` files) — verified shipped verbatim, not
  reviewed line-by-line.
- The `tsldata/` corpus content itself and
  `supplementary/buildsystem/machine_profiles.json` (shapes checked via
  tests, not data review).
- VS Code integration tests were not run (`npm test` / xvfb integration);
  `extension.test.ts` content unreviewed.
- Several large test files were reviewed by name inventory + samples rather
  than line-by-line (noted per subsystem in the source reports).
- `authoring_completion.py` / `syntax/authoring.py` logic after commit
  `418057e` beyond ordering determinism.
