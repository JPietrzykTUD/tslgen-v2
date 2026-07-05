# Adding A TSIL Keyword Region

This guide describes how to add a new TSIL keyword region to `tslc`.

TSIL bodies are not parsed as C++, Rust, or a general target-language AST.
They are scanned into raw target text plus recognized keyword regions. A new
keyword should therefore have three clearly separated parts:

- lexical recognition: the scanner can identify the region boundary;
- source-shell validation: malformed source shapes become diagnostics;
- lowering: a focused handler turns the region into backend-specific text using
  typed lowering context and backend translation templates.

Keep those responsibilities separate. The scanner should not learn expression
semantics, validation should not perform backend lowering, and renderers should
not re-parse TSIL.

## When To Add A Keyword

Add a TSIL keyword when a source-body operation has shared compiler semantics
that should be typed, validated, or backend-neutral.

Good reasons:

- the same raw target-language pattern appears in several primitives;
- C++ and Rust need different spellings for the same source intent;
- the source form needs diagnostics before backend rendering;
- a future backend should add one translation rule instead of editing many
  primitive bodies.

Do not add a keyword only to rename raw syntax. If the expression is genuinely
portable target text and does not need compiler knowledge, raw text is fine.

## Running Example: `helper`

The helper region accepts:

```tsil
helper<arith_add>(left, right)
helper<clz_recursive, type(base::in), type(vector::offset_base)::apply>(data)
```

The source selector is a backend-neutral helper id, not a C++ namespace or Rust
module path. Lowering maps `helper<arith_add>` to a backend translation template
named `helper_arith_add`. C++ currently renders that template as
`::tsl::detail::helpers::arith_add(...)`; Rust renders it as
`crate::tsl_core::detail::helpers::arith_add(...)`.

That design keeps primitive source data independent from backend namespaces and
lets primitive implementation internals move under `detail::primitives`
without breaking raw helper calls.

## Step 1: Define The Source Contract

Before editing code, write down the exact accepted forms.

For a call-shaped region, decide:

- keyword name;
- selector syntax, if any;
- argument syntax and arity;
- whether nested TSIL regions are valid inside arguments;
- whether the region behaves as an expression or statement;
- malformed nearby forms that must diagnose.

For a block-shaped region, also decide:

- block shape: `if`, `loop`, or `switch`;
- selector meanings;
- required body or arm structure;
- whether else/arm blocks are allowed.

Prefer one literal, documented spelling. Avoid compatibility aliases unless the
project explicitly needs them.

## Step 2: Register The Region Descriptor

Add the keyword to:

```text
tslc/src/tslc/ir/region_registry.py
```

Use `TsilRegionDescriptor`:

```python
TsilRegionDescriptor("helper", shell_validator="helper_selector")
```

The descriptor is the lexical source of truth consumed by scanner, validation,
and lowering registry code.

Choose `body_shape` only when the region is not a normal call-shaped region:

```python
TsilRegionDescriptor("loop", body_shape="loop_block")
TsilRegionDescriptor("switch", body_shape="switch_block")
```

Keep this layer lexical. It owns keyword names, body shape, and the shell
validator id. It must not import lowering handlers, catalog values, or backend
code.

## Step 3: Add Source-Shell Validation

If the keyword has structured selector or argument syntax that can be checked
without backend semantics, add validation in:

```text
tslc/src/tslc/catalog/validation/body_validation.py
```

For `helper`, the validator checks that the first selector term is an
identifier:

```python
def _validate_helper_region(
    primitive_name: str,
    region: Region,
    diagnostics: list[Diagnostic],
) -> None:
    terms = split_selector_terms(region.selector_text)
    if terms and _IDENTIFIER.fullmatch(terms[0].strip()) is not None:
        return
    diagnostics.append(...)
```

Then register it in `_SHELL_VALIDATORS` under the same id declared in
`region_registry.py`:

```python
"helper_selector": _validate_helper_region,
```

Validation should:

- produce structured `Diagnostic` values;
- include the primitive name and bad selector text when useful;
- use `region.source` for source location;
- check source shape only, not backend support;
- avoid silently repairing malformed source.

Unsupported backend semantics belong in lowering diagnostics, not catalog
validation.

## Step 4: Add A Focused Lowerer

Create a handler under:

```text
tslc/src/tslc/lower/region_handlers/
```

For `helper`, the file is:

```text
tslc/src/tslc/lower/region_handlers/helpers.py
```

A lowerer implements the `RegionLowerer` protocol:

```python
class HelperLowerer:
    keyword = "helper"

    def lower(
        self, region: Region, context: LoweringSession, render: RenderBody
    ) -> RenderField:
        ...
```

Use the passed `render` callback to recurse into child segments. Do not scan
raw implementation bodies from scratch outside the shared segment boundary.

Common helpers:

- `split_selector_terms(...)` for comma-separated selector terms;
- `_split_arg_groups(...)` for comma-separated region arguments;
- `scan(...)` only for selector fragments that are themselves TSIL-capable
  expressions, as `helper` does for template arguments;
- `trimmed_text(...)` and `render_text(...)` for normalized render fields.

Lowering should:

- parse only the keyword's own source contract;
- ask `context.env.backend.templates` for backend spellings;
- return `region.full_text` after recording a skip when unsupported;
- use `context.effects.skip(...)` for unsupported or malformed lowered cases;
- preserve deterministic output.

For `helper`, unsupported backend templates become:

```python
context.effects.skip(
    "TSL-LOWER-UNSUPPORTED-HELPER",
    f"unsupported helper<{name}> for backend ...",
    source=region.source,
)
return region.full_text
```

## Step 5: Register The Lowerer

Add the lowerer to:

```text
tslc/src/tslc/lower/region_handlers/registry.py
```

Import the class and add it to `_REGION_LOWERER_FACTORIES`:

```python
from tslc.lower.region_handlers.helpers import HelperLowerer

_REGION_LOWERER_FACTORIES = {
    "helper": HelperLowerer,
    ...
}
```

The registry builds `DEFAULT_REGION_LOWERERS` from
`DEFAULT_TSIL_REGION_DESCRIPTORS`, so a descriptor without a lowerer means the
scanner can see the keyword but lowering will not handle it.

## Step 6: Add Backend Translation Templates

If the lowerer emits backend-specific text, add templates to the backend
translation data:

```text
tsldata/detail/lang/translate_cpp.tsl
tsldata/detail/lang/translate_rust.tsl
```

For `helper`, the lowerer turns `helper<arith_add>(...)` into the template key
`helper_arith_add`, so each backend declares:

```tsl
translation cpp:
  helper_arith_add "::tsl::detail::helpers::arith_add({args})"

translation rust:
  helper_arith_add "crate::tsl_core::detail::helpers::arith_add({args})"
```

Use translation data for spelling differences. Do not bake C++ namespaces, Rust
modules, intrinsic prefixes, or syntax details into primitive source bodies
when a backend template can own them.

## Step 7: Add Runtime Assets When Needed

If a template refers to generated-library helper code, add the helper to the
appropriate static assets under:

```text
tslc/src/tslc/backend/assets/
```

For `helper`, the slice added or moved C++ helpers under:

```cpp
namespace tsl::detail::helpers {
...
}
```

and Rust helpers under:

```rust
pub mod detail {
    pub mod helpers {
        ...
    }
}
```

Keep helper assets backend-owned. Primitive bodies should say
`helper<arith_add>(...)`, not `::tsl::detail::helpers::arith_add(...)`.

## Step 8: Migrate Source Data

Update primitive bodies under:

```text
tsldata/primitives/
```

Use the new keyword only where it captures the source intent better than raw
text. The `helper` slice replaced raw `detail::arith_mul(...)`,
`detail::arith_rem(...)`, `detail::popcount(...)`, `detail::clz(...)`, and
similar calls with backend-neutral `helper<...>(...)` forms.

This is also where architecture guards become useful. If a new keyword replaces
an old raw spelling, add or run an `rg` check proving the old spelling is gone
from production source data.

## Step 9: Update Documentation

Update:

```text
docs/tsil-keywords.md
```

Include:

- syntax;
- intended use;
- how validation works;
- how lowering chooses backend templates;
- notable unsupported cases.

Keep `docs/tsil-keywords.md` as the inventory. Use this file as the process
guide.

## Step 10: Add Tests At The Right Boundaries

A good keyword slice usually needs tests in several layers.

Scanner and validation:

- valid region is recognized;
- malformed shell produces a catalog diagnostic;
- nested regions remain nested segments;
- source locations are preserved where practical.

Lowering:

- accepted form lowers to the expected backend template output;
- unsupported selector/backend template produces a lowering skip;
- malformed lowered form does not silently pass through as if supported;
- child expressions are rendered recursively.

Backend/render:

- generated C++ and Rust output contain the intended spelling;
- backend-specific assets are shipped;
- wrappers/templates do not re-parse TSIL.

Generated build tests:

- run when the keyword affects emitted code or static assets;
- include both C++ and Rust if both backends receive templates.

For the `helper` slice, tests were updated around specialization output,
generation conditionals, safety contracts, and generated build coverage because
the keyword also moved primitive implementations into backend detail modules.

Useful focused commands:

```bash
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_tsil_scan.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_lower_text.py tslc/tests/test_select_and_lower.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_generation_conditionals.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_safety_contract.py
```

When generated code or assets changed:

```bash
PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds tslc/tests/test_build_verify.py tslc/tests/test_value_tests.py
```

Always consider:

```bash
python -m compileall -q tslc/src/tslc
git diff --check
```

## Review Checklist

Before calling the slice done, check:

- the accepted source syntax is documented and exact;
- malformed nearby source produces diagnostics;
- the scanner only owns lexical region boundaries;
- the lowerer is small and keyword-specific;
- backend spelling lives in translation data or backend assets;
- primitive source data is backend-neutral where possible;
- renderers format already-lowered values and do not parse TSIL;
- unsupported cases are explicit skips or diagnostics;
- iteration and generated output stay deterministic;
- adding the next similar keyword would follow the same owned path.

## Common Mistakes

Putting backend paths in `tsldata`:

- Bad: `::tsl::detail::helpers::arith_add(left, right)`
- Better: `helper<arith_add>(left, right)`

Doing semantic work in the scanner:

- Bad: scanner validates selector meaning or resolves types.
- Better: scanner identifies `Region`; validation checks shell; lowerer resolves
  typed context and backend support.

Skipping shell validation:

- Bad: malformed `keyword<,>(...)` reaches render as raw text.
- Better: catalog validation emits a source-located diagnostic before
  selection/lowering.

Adding renderer logic:

- Bad: C++/Rust project renderers inspect raw TSIL to decide what to emit.
- Better: lowerers and backend translation produce render-ready text before
  project rendering.

Overgeneralizing the first slice:

- Bad: create a plugin registry or broad expression IR for one keyword.
- Better: add one descriptor, one validator if needed, one lowerer, backend
  templates, focused tests, and split only when a second real slice proves the
  pressure.
