# TSL Source-Data Instructions

## Scope

These instructions apply to `tsldata/`. The root `AGENTS.md`, `CHARTER.md`, and
`PLANS.md` also apply. Compiler changes made to support source data must also
follow `tslc/AGENTS.md`.

`tsldata/` is authored input and a source of product behavior. It is not
generated output.

## Directory Ownership

- `detail/` owns type groups, target-language spellings/translations, primitive
  templates, lane sets, flags, and target/profile family declarations.
- `extensions/` owns extension capabilities, inheritance, required features,
  backend support, and register declarations.
- `primitives/` owns primitive contracts, documentation, authored tests,
  benchmark metadata, and implementation bodies.

Machine-profile instances are configuration under
`supplementary/buildsystem/machine_profiles.json`, not TSL source data.

Use the closest existing source file in the same primitive or extension family
as the style and shape reference.

## Source Authoring Rules

- Keep source forms explicit. Do not rely on the compiler to repair malformed
  declarations, ambiguous attributes, or nearly valid TSIL.
- Treat primitive names and signatures as public domain vocabulary. Name
  observable semantics rather than an intrinsic, ISA recipe, register shape, or
  implementation trick.
- Declare behavioral roles through source data and typed capabilities. Do not
  compensate for missing data by adding compiler branches for primitive,
  extension, or profile names.
- Keep extension inheritance, superseding, required features, backend support,
  type groups, masks, and immediates consistent with the closest established
  declarations.
- Implementation bodies are raw target text plus recognized TSIL regions.
  Express shared semantics through typed regions and primitive calls; do not
  duplicate another primitive's intrinsic recipe or depend on compiler-side
  raw-string rewrites.
- Keep primitive-call dependencies acyclic. Do not rely on profile, type, or
  backend conditions to make a source-level cycle harmless.
- Authored value tests should cover the actual contract, including relevant
  width, sign, floating, mask, immediate, lane-order, alignment, and aliasing
  edges.
- Benchmark metadata describes target-independent workload semantics. Do not
  embed benchmark C++ or renderer policy in source data.
- Unsupported combinations should remain explicit and diagnosable. Do not add
  placeholder bodies that merely make coverage appear complete.

## Cross-Tree Workflows

- New target extension or machine profile:
  `.agents/skills/add-tsl-extension/SKILL.md`; also use
  `.agents/skills/extend-tslc-verification/SKILL.md` when it needs a new
  compiler, target, runner, or emulator path.
- New primitive or source-data shape:
  `.agents/skills/add-tsl-primitive/SKILL.md`.
- New specialization of an existing primitive:
  `.agents/skills/add-tsl-primitive-implementation/SKILL.md`.
- New authored value-test shape:
  `.agents/skills/add-value-test-shape/SKILL.md`.
- New TSIL region required by source bodies:
  `.agents/skills/add-tsil-region/SKILL.md` and `tslc/AGENTS.md`.
- New backend language/detail data:
  `.agents/skills/add-tslc-backend/SKILL.md` and `tslc/AGENTS.md`.

Start primitive work in source data. If the parser, catalog, selection,
lowering, backend, or value-test planner cannot represent the required
contract, add typed compiler support at that owned boundary rather than
changing the data to exploit an accident of current rendering.

## Validation

Choose checks for the affected source behavior and run them from the repository
root:

```bash
PYTHONPATH=tslc/src python -m tslc check
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_catalog.py tslc/tests/test_catalog_validation.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_select_and_lower*.py tslc/tests/test_lower_*.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_test_planning.py
git diff --check
```

Use a slot-aware check while iterating on one implementation without rendering
a project:

```bash
PYTHONPATH=tslc/src python -m tslc check \
  --primitive add --profile avx2 --backend cpp --type si32
```

Positional paths filter displayed diagnostics but never narrow the loaded
corpus; shared definitions must remain available during validation.

Broaden to `./dev.sh build` or `./dev.sh test` with the smallest useful
primitive/profile/backend matrix when source changes affect emitted code or
executable value tests. Report unsupported or skipped slots explicitly.
