# Lowering Completeness Audit

Milestone 184 audited the generation-relevant TSIL surface after M183. This is
documentation evidence only. It is not a runtime source scanner, completeness
oracle, backend plan, or permission to implement multiple lowering lanes in
one slice.

## Method

The audit used current redesign docs plus the `tsldata/**/*.tsl` corpus as
ground truth. `frozen/` and `tslgenold/` were not needed.

Representative corpus probes:

```bash
rg -n "tsil \"" tsldata -g "*.tsl"
rg -n "emit_return\(" tsldata -g "*.tsl"
rg -o --no-filename "[A-Za-z_][A-Za-z0-9_:]*<" tsldata/primitives -g "*.tsl"
rg -o --no-filename "mask<[^>]+>" tsldata/primitives -g "*.tsl"
rg -o --no-filename "assume_aligned<|array_type<|pack<" tsldata/primitives -g "*.tsl"
rg -o --no-filename "details::[A-Za-z_][A-Za-z0-9_]*" tsldata/primitives -g "*.tsl"
rg -o --no-filename "if<runtime>|else<runtime>|switch<runtime>|if<compile>|else<compile>|switch<compile>" tsldata -g "*.tsl"
```

The broad lexical primitive-file head scan is intentionally approximate; it
was used to find families to classify, not to define accepted syntax.
Backend translation metadata under `tsldata/detail/lang` is evidence for later
translation/rendering work and was excluded from primitive-body lowering
counts unless noted explicitly.

## Summary

Most high-frequency TSIL families have accepted discovery, handoff, or
selected-context semantic lowering boundaries through M183. The strongest
remaining lowering-owned gap is `mask<...>(...)`: it appears 71 times in
primitive bodies with four exact selector payloads and is distinct from the
already accepted `value<generation>(mask::lane::...)` constants.

M184 therefore selects M185:

```text
Milestone 185: Exact Mask Keyword Request / Selector Boundary
```

M185 later accepted that request/selector boundary. Backend mask helper
translation, rendering, argument splitting, and recursive payload lowering
remain outside the accepted M185 behavior.

The selected boundary discovers balanced `mask<...>(...)` islands in
source-owned text and contiguous raw body-token runs, classifies the exact
observed selectors `zero`, `test`, `set`, and `set:1` as typed mask keyword
requests, and keeps arguments and surrounding text opaque. It does not
translate masks, render backend helpers, parse assignments/loops/expressions,
or recurse through every possible payload carrier.

## Corpus Snapshot

Approximate primitive-file lexical head counts:

| Head | Count |
| --- | ---: |
| `type<` | 1999 |
| `call<` | 1796 |
| `cast<` | 1083 |
| `value<` | 933 |
| `var<` | 831 |
| `intrin<` | 737 |
| `intrin_compose<` | 627 |
| `let<` | 382 |
| `loop<` | 291 |
| `if<` | 152 |
| `mask<` | 71 |
| `else<` | 69 |
| `switch<` | 45 |
| `mem<` | 25 |
| `array_type<` | 21 |
| `assume_aligned<` | 20 |
| `io<` | 14 |
| `pack<` | 1 |

Exact `mask<...>` selector evidence:

| Selector island | Count |
| --- | ---: |
| `mask<test>` | 33 |
| `mask<zero>` | 20 |
| `mask<set:1>` | 14 |
| `mask<set>` | 4 |

Backend-control evidence:

| Form | Count |
| --- | ---: |
| `if<compile>` | 43 |
| `else<compile>` | 24 |
| `switch<compile>` | 45 |
| `if<runtime>` / `else<runtime>` / `switch<runtime>` | 0 |

Support-helper evidence in primitive bodies:

| Helper | Count |
| --- | ---: |
| `details::mask_test` | 23 |
| `details::arith_rem` | 8 |
| `details::arith_add` | 6 |
| `details::arith_mul` | 5 |
| `details::clz_recursive` | 4 |
| `details::popcount` | 3 |
| `details::clz` | 3 |
| `details::ctz` | 1 |

## Classification

| Family | Evidence | Classification | Current boundary and next action |
| --- | --- | --- | --- |
| `tsil` payload envelopes | 1323 `tsil "` lines | accepted enough for current lowering | Existing source intake/body-token work treats implementation bodies as source-owned input. Remaining work is per-family lowering or backend rendering, not another envelope milestone. |
| `emit_return(...)` | 1585 occurrences | accepted enough for current lowering, with deferred broad forms | Exact accepted return-call/expression forms exist where selected by prior milestones. Broad return payload rendering and arbitrary expression parsing remain deferred. |
| `call<primitive=...>(...)` | 1796 `call<` heads | accepted enough for current lowering | M144-M152 and M170-M173 cover selector payload lowering, matching, bindings, dependency closure, and exact selected shapes. Recursive token-stream rendering remains later output/backend work. |
| `let<type>(...)` | 382 occurrences | accepted enough for current lowering | Type aliases feed the selected type environment. Non-type `let<...>` has no separate current evidence in the primitive-file scan. |
| `var<...>(...)` | 831 heads | accepted enough for current lowering | M163 discovers exact top-level declaration requests with opaque type/initializer payloads. Declaration rendering and recursive payload solving remain backend/output-owned. |
| `loop<range>`, `loop<unroll>` | 291 `loop<` heads | accepted enough for current lowering | M161-M162 discover exact top-level loop regions and metadata. Loop execution, substitution, and body rendering are broad/deferred until output integration needs them. |
| `if<generation>`, `else if<generation>`, `else<generation>` | 109 `if<generation>`, 45 `else<generation>` | accepted enough for current lowering | M156-M160 accept selected-branch pruning for exact generation branch chains over accepted generation predicates. Recursive branch rendering and broad raw `else` parsing remain deferred. |
| `if<compile>`, `else<compile>`, `switch<compile>` | 43, 24, and 45 occurrences | backend translation/rendering/output-owned gap | M165 discovers backend-control request facts. Lowering should not choose backend compile-control rendering, branch syntax, or switch emission. |
| `if<runtime>`, `else<runtime>`, `switch<runtime>` | no corpus evidence | no current corpus evidence | Do not implement until source data requires it. |
| `type<generation>(...)` | high-frequency `type<` evidence | accepted enough for current lowering | M141-M175.5 cover selected-context type queries, aliases, vector members, scalar descriptors, and fixed vector/member size facts. Backend spelling remains separate. |
| `type<backend>(...)` | high-frequency nested evidence | accepted enough for current lowering | M179 discovers exact islands and M180 hands them to `BackendTypeSpellingRequest` values. Translation and rendering are backend-owned. |
| `value<generation>(...)` | 933 `value<` heads | accepted enough for current lowering | M155, M158, M159, M168, M175, M175.5, and M177 cover the accepted generation-value families. Remaining raw arithmetic/operator parsing is deferred. |
| `value<backend>(...)` | high-frequency nested evidence | accepted enough for current lowering | M164 discovers islands and M181 hands the five observed payload families to typed unresolved backend-value requests. Translation/rendering remains backend-owned. |
| `intrin<...>(...)`, `intrin_compose<...>(...)` | 737 and 627 heads | backend translation/rendering/output-owned gap | M166 discovers islands and M182 classifies top-level `intrin_compose` modifiers. Backend intrinsic lookup, argument splitting, and rendering remain backend-owned. |
| `cast<...>(...)`, `mem<...>(...)`, `io<...>(...)` | 1083, 25, and 14 heads | backend translation/rendering/output-owned gap | M167 discovers islands and M183 classifies exact selectors. Type/value lowering inside arguments and operation translation are later backend/source-operation work. |
| `mask<...>(...)` | 71 heads: `zero`, `test`, `set`, `set:1` | lowering-owned gap | No accepted boundary currently discovers this TSIL-like keyword family. M185 should add exact discovery and selector classification while preserving arguments opaque. |
| `assume_aligned<...>(...)` | 20 heads, mostly around pointers and `vector::alignment` | backend translation/rendering/output-owned gap | This is a support/helper-shaped source form around pointer expressions. Inner generation alignment can already lower when selected; the outer helper spelling belongs to backend/support output integration, not semantic lowering now. |
| `array_type<...>` | 21 heads, mainly inside `var<typed>` type payloads | backend translation/rendering/output-owned gap | This is a target type-constructor spelling needed when declaration rendering starts. Inner type/value arguments can lower through accepted boundaries, but the array type spelling is renderer/backend-owned until declaration output is selected. |
| `pack<first>(args...)` | 1 head in `load_store/construct.tsl` | backend translation/rendering/output-owned gap | Single observed backend/helper-like operation. Do not spend the next lowering milestone here unless output integration selects pack rendering. |
| `details::*` support helpers | `arith_*`, `popcount`, `clz`, `ctz`, `mask_test` | source-convention flaw/follow-up | These remain source-authored backend/support helpers. Lowering must not rewrite them to operators or infer semantics from helper names. Backend support-library availability may need later explicit rules. |
| raw target-language-like text | assignments, indexing, loops, operators around islands | broad parsing/deferred | Surrounding C/C++/Rust-like syntax remains source-owned text. Narrow source-island discovery should not become a general expression or statement parser. |
| backend translation metadata | `tsldata/detail/lang/**/*.tsl` | backend translation/rendering/output-owned gap | Translation maps are not primitive-body TSIL evidence. Lowering produces typed requests/facts; backend translation consumes explicit metadata later. |

## Lowering-Owned Gaps

Only one gap is selected now:

- `mask<...>(...)` request/selector boundary. It consumes source-owned text or
  contiguous raw body-token runs and accepted source location facts. It should
  produce typed unresolved mask keyword requests for `zero`, `test`, `set`,
  and `set:1`, with arguments retained as opaque source text.

Potential later lowering work exists, but should wait for a concrete consumer:

- recursive use of accepted island discoveries inside every possible opaque
  payload carrier;
- loop execution/substitution;
- declaration type/value rendering handoff;
- broader body-token rendering policy.

Those are not safe as the next M185 step because they would either start
output integration or recreate a broad TSIL/target-language parser.

## Backend-Owned Or Deferred Gaps

Backend/rendering/output-owned work includes backend type/value translation,
intrinsic rendering, cast/memory/I/O operation translation, compile-control
emission, declaration rendering, array type spelling, alignment helper
spelling, `pack<...>` support, support-helper availability, and generated
artifact integration.

Broad parsing/deferred work includes raw assignments, array indexing,
target-language loops, raw operators, expression precedence, argument ASTs,
general recursive payload scanning, and source repair.

## Post-M185 Completion Gate Addendum

The post-M185 lowering completion gate re-ran the corpus check after M185 was
accepted. It selected one additional lowering-owned gap before declaring the
lowering surface complete by contract:

| Candidate | Evidence | Classification | Next action |
| --- | --- | --- | --- |
| bare `if<generation>(type::is_same(...))` conditions | 15 current primitive-body conditions, including 3 exact two-term top-level `type::is_same(...) || type::is_same(...)` disjunctions | lowering-owned condition-expression gap | Select M186 as a typed generation boolean condition grammar. |
| `assume_aligned<...>(...)`, `array_type<...>`, `pack<...>(...)` | same evidence as M184 | backend/output-owned or source-convention | Do not select as lowering implementation. |
| `details::*` support helpers | same helper evidence as M184 | source-authored backend/support helpers | Preserve; do not rewrite to operators. |
| recursive payload discovery, loop execution/substitution, declaration/body rendering, backend translation/rendering | required later for output, but not a missing keyword-family lowering boundary | backend/output-owned or broad/deferred | Keep out of M186. |

Interactive product review broadened M186 from a one-off matcher to a small
typed TSIL generation boolean condition grammar. M186 should accept boolean
`!`, `&&`, `||`, and parentheses only over accepted generation
expression/value leaves and accepted integer-comparison leaves. It must still
leave recursive generation-control lowering, raw target-language expression
parsing, helper-call semantics, pointer/indexing predicates, and backend
translation/rendering out of scope.

## Post-M186 Completion Gate Required

M186 accepted the typed generation boolean condition grammar selected by the
post-M185 completion gate. Before declaring the lowering surface complete or
moving to backend/output integration, run one final lowering-focused planning
gate that reconciles this audit, the current `tsldata/**/*.tsl` corpus, and
the accepted M186 behavior. That gate must either record lowering completion
by contract or select exactly one remaining lowering-owned gap; it must not
start backend implementation merely because backend/output-owned work remains.
