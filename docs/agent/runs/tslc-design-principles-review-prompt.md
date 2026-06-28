# Review Prompt: TSLc Design Principles Review

You are a senior software designer and engineer performing a thorough design review of the current active `tslc` line.
This is a read-only review task. Do not implement fixes. Produce a verdict,
concrete findings, and follow-up recommendations.

## Scope

Review whether the current `tslc` implementation, tests, and active handoff
state remain aligned with the project's main design principles after the recent
changes.

Focus on the active `tslc/` codebase and `tsldata/` source corpus. Treat older
`tslgen` milestone history as historical evidence only unless it is explicitly
referenced by the active `tslc` handoff.

## Required Reading

Inspect the implementation areas most relevant to the recent changes:

- `tslc/src/tslc/pipeline.py`
- `tslc/src/tslc/catalog/validation/`
- `tslc/src/tslc/support_policy.py`
- `tslc/src/tslc/support_policy_views.py`
- `tslc/src/tslc/ir/scan.py`
- `tslc/src/tslc/lower/`
- `tslc/src/tslc/backend/`
- `tslc/src/tslc/render/`
- `tslc/src/tslc/value_tests/`
- focused tests under `tslc/tests/`

## Design Principles To Check

Evaluate the design against each principle below.

### Primitive- And Extension-Agnostic

`tslc` should not know that source primitive or extension names such as `add`,
`from_array`, `avx2`, `neon`, or `generic` are semantically special. Those facts
must come from typed catalog data, profiles, signatures, support policy facts,
and lowered metadata.

Acceptable:

- resolving a source-authored primitive or extension name from catalog data;
- using backend presentation names in backend renderers or static generated
  runtime mappings;
- tests that intentionally use concrete fixture names.

Potential violations:

- production branches such as `primitive_name == "add"` or
  `extension_name == "scalar"` deciding compiler behavior;
- renderer-local source primitive classifiers;
- hard-coded harness primitive names instead of signature/capability discovery.

### KISS / Prototype-First

Prefer the smallest direct design that works. Do not introduce plugin
registries, broad IR families, generic worklists, or DSL machinery until at
least two accepted slices need them.

Check whether new abstractions are justified by current repeated needs, or
whether a simple typed function/class would be clearer.

### Typed Boundaries

Raw parsed data may be loose at the edge. After parsing/catalog building,
downstream code should consume typed objects such as `Catalog`, `Primitive`,
`Extension`, `LoweredSpecialization`, value-test plans, diagnostics, and render
models.

Look for downstream dictionary-shaped domain objects, raw selector/body text
being interpreted too late, or typed facts duplicated as strings across layers.

### DRY Through Ownership

A fact should live in one place:

- support policy facts belong in `SupportPolicy`;
- catalog-derived scans belong in support-policy views or a similarly explicit
  owner;
- renderers should consume decided render models/plans, not rediscover semantic
  facts;
- diagnostics and validation should have a clear owning boundary.

Call out duplicated policy tables, repeated source-shape classifiers, or
backend/render code that reimplements selection/lowering decisions.

### Object-Oriented Where Ownership Exists

Use classes when a concept owns invariants or behavior: planner, policy,
backend dialect, renderer, artifact writer. Use pure functions for simple
stateless transformations.

Check whether classes are cohesive owners or merely static namespaces. Also
check whether procedural hubs should become small objects because they own
stateful or extensible behavior.

### Clear Side-Effect Boundaries

Parsing, validation, selection, lowering, and rendering should be mostly pure.
Filesystem writes belong to the artifact writer. Build verification happens
after artifacts exist.

Look for hidden file I/O, environment reads, subprocesses, mutable global state,
or verification/build actions inside semantic compiler phases.

### Semantic Logic Before Rendering

Renderers format already-decided values. They should not perform primitive
selection, backend semantic inference, source repair, TSIL parsing, or
capability discovery.

Inspect C++/Rust project renderers, value-test renderers, and backend renderers
for semantic decisions that should have happened in selection/lowering/planning.

### Diagnostics Over Silent Behavior

Unsupported or malformed input should produce structured diagnostics. Silent
skips are acceptable only when deliberately modeled as deferred support and
surfaced clearly.

Check that malformed source forms are rejected or diagnosed, not repaired or
accepted by permissive parsing. Check that known unsupported authored test
shapes, ambiguous harness discovery, duplicate test function names, validation
failures, and unsupported TSIL forms are visible in diagnostics.

### Determinism

Selection order, diagnostics, generated plans, artifacts, and tests should be
stable and repeatable.

Look for unsorted iteration over unordered maps/sets in emitted artifacts,
diagnostics, plans, or coverage. Check whether tests cover determinism where the
output is important.

### Maintainability Over Cleverness

Prefer small cohesive modules, explicit names, narrow public APIs, and split
files before they become catch-all hubs.

Check module sizes, dependency direction, public/private boundaries, and whether
recent splitups stayed split. Flag modules approaching catch-all status, even if
they are currently correct.

### Extensibility By Typed Data

New primitives, extensions, backend spellings, masks, intrinsics, and value-test
cases should usually be added through `tsldata` plus typed compiler support, not
by adding more name-specific branches.

Call out places where adding a new extension/backend/value-test shape would
require editing an unrelated renderer or special-case list instead of extending
the proper typed boundary.

## Suggested Evidence Searches

Run searches like these and interpret the results carefully. Test fixtures and
historical docs may mention concrete names legitimately; production behavior
branches are the main concern.

```bash
rg -n 'primitive_name\s*(==|!=)|source_primitive_name\s*(==|!=)|extension_name\s*(==|!=)|isa_name\s*(==|!=)' tslc/src/tslc -g '*.py'
rg -n '"(add|sub|mul|from_array|to_array|to_integral|set|convert_down|extract|insert|avx2|neon|sse|generic|scalar)"' tslc/src/tslc -g '*.py'
rg -n 'intrin_compose|loop<range>|loop<unroll>|call<primitive=[^,>]+\s+attrs|intrin<[^,>]+\s+build' tslc/src tsldata/primitives tsldata/detail/lang -g '*.*'
find tslc/src/tslc -type f -name '*.py' -print0 | xargs -0 wc -l | sort -n | tail -30
rg -n 'Catalog|LoweredSpecialization|parse_signature|_is_' tslc/src/tslc/render tslc/src/tslc/value_tests/render_*.py -g '*.py'
```

These searches are prompts, not proof. Explain whether each hit is acceptable
source lookup, backend presentation, test fixture code, historical text, or a
real design problem.

## Validation

This is primarily a design review, but run enough validation to ground the
verdict if the environment allows it.

Preferred:

```bash
git diff --check
python -m compileall -q tslc/src/tslc tslc/tests
python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_support_policy.py tslc/tests/test_support_policy_views.py tslc/tests/test_tsil_scan.py tslc/tests/test_masks_and_calls.py tslc/tests/test_generation_conditionals.py tslc/tests/test_select_and_lower.py
```

Run `./verify.sh` only if time and environment permit. If you do not run it,
state that clearly and rely on the latest recorded verification in
`docs/agent/current-redesign-state.md`.

## Output Format

Start with findings, ordered by severity.

For each finding include:

- severity: `Blocker`, `High`, `Medium`, or `Low`;
- file and line reference;
- violated or stressed design principle;
- why it matters;
- concrete recommended follow-up.

Then provide:

- `Verdict`: one of `Accept`, `Accept With Follow-Ups`, `Needs Revision`, or
  `Return To Planner`;
- `Principle Scorecard`: one short bullet per design principle, marking
  `Aligned`, `Mostly Aligned`, or `At Risk`;
- `Residual Risks`: concise notes on acceptable prototype debt;
- `Validation Run`: commands run and results, or why validation was skipped.

Do not implement fixes during this review. If fixes are needed, propose a
single focused follow-up prompt or milestone.
