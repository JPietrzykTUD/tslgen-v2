# Adding A TSIL Keyword Region

Use this guide for a new recognized TSIL region.

Use [TSIL keyword regions](tsil-keywords.md) for the current reference.

## The TSIL Model

TSIL is not a C++ or Rust AST.

The scanner produces two segment kinds:

```text
implementation body
  -> RawText
  -> Region(keyword, selector, child segments)
```

Raw target text passes through.

A recognized region receives typed validation and focused lowering.

## When To Add A Region

Add a region when source intent needs shared compiler semantics.

Good reasons:

- C++ and Rust need different spellings;
- several primitives repeat the same semantic pattern;
- malformed source needs an early diagnostic;
- a future backend should add one translation rule.

Keep raw text when it is portable and needs no compiler knowledge.

Do not add a region only to rename target syntax.

## The Three Owned Layers

| Layer | Owner | Responsibility |
| --- | --- | --- |
| Recognition | `ir/region_registry.py` and scanner | Find region boundaries. |
| Shell validation | `catalog/validation/body_validation.py` | Reject malformed source shape. |
| Lowering | `lower/region_handlers/` | Resolve semantics and backend spelling. |

The layers connect in one direction:

```text
descriptor
  -> scanner Region
  -> shell validator
  -> RegionLowerer
  -> backend translation or syntax dialect
  -> render-ready text
```

The scanner must not resolve types.

Validation must not emit backend code.

Renderers must not scan TSIL again.

## Running Example: `helper`

Source:

```tsil
helper<arith_add>(left, right)
```

The selector is a semantic helper ID.

It is not a C++ namespace.

It is not a Rust module path.

Lowered C++:

```cpp
::tsl::detail::helpers::arith_add(left, right)
```

Lowered Rust:

```rust
crate::tsl_core::detail::helpers::arith_add(left, right)
```

## 1. Define The Source Contract

Write exact accepted forms.

For a call region, define:

- keyword;
- selector grammar;
- argument grammar;
- arity;
- expression or statement behavior;
- nested-region behavior;
- malformed nearby forms.

For a block region, also define:

- block shape;
- body structure;
- optional branches or arms.

Example contract:

```text
helper<IDENTIFIER>(ARGUMENTS)
helper<IDENTIFIER, TEMPLATE_ARGUMENT, ...>(ARGUMENTS)
```

Prefer one spelling.

Do not add aliases without a compatibility requirement.

## 2. Register The Descriptor

Edit:

```text
tslc/src/tslc/ir/region_registry.py
```

Add one descriptor:

```python
TsilRegionDescriptor(
    "helper",
    "Invoke a compiler-owned helper.",
    (
        "helper<name>(args)",
        "helper<name, template_arg, ...>(args)",
    ),
    shell_validator="helper_selector",
)
```

Use a body shape only for structural regions:

```python
TsilRegionDescriptor(
    "loop",
    "Emit or expand a loop.",
    ("loop<backend>(var, start, end, step) { body }",),
    body_shape="loop_block",
)
TsilRegionDescriptor(
    "switch",
    "Emit compile-time selection.",
    ("switch<compile>(selector) { arms }",),
    body_shape="switch_block",
)
```

The purpose and accepted forms are required author-facing facts. Hover and
future shell completion consume them directly, so describe source syntax rather
than validator or lowering implementation names.

The descriptor tuple is the closed keyword vocabulary.

It drives:

- `TSIL_REGION_KEYWORDS`;
- scanner recognition;
- shell-validator lookup;
- author-facing hover forms and purpose;
- lowerer registration checks;
- documentation tests.

The descriptor owns lexical and author-facing syntax facts only.

It must not import catalog or backend code.

## 3. Add Shell Validation

Edit:

```text
tslc/src/tslc/catalog/validation/body_validation.py
```

Validate source shape only.

Example:

```python
def _validate_helper_region(
    primitive_name: str,
    region: Region,
    diagnostics: list[Diagnostic],
) -> None:
    terms = split_selector_terms(region.selector_text)
    if terms and _IDENTIFIER.fullmatch(terms[0].strip()):
        return
    diagnostics.append(...)
```

Register the same validator ID:

```python
_SHELL_VALIDATORS = {
    "helper_selector": _validate_helper_region,
    # ...
}
```

A validator should:

- return structured diagnostics;
- include source location;
- name the primitive and bad selector when useful;
- reject malformed source;
- avoid source repair;
- avoid backend checks.

Backend support belongs to lowering.

## 4. Add A Focused Lowerer

Create a file under:

```text
tslc/src/tslc/lower/region_handlers/
```

Implement `RegionLowerer`:

```python
class HelperLowerer:
    keyword = "helper"

    def lower(
        self,
        region: Region,
        context: LoweringSession,
        render: RenderBody,
    ) -> RenderField:
        ...
```

The lowerer owns only its keyword contract.

Use the `render` callback for child segments.

Do not rescan the full implementation body.

Useful shared helpers:

- `split_selector_terms(...)`;
- `_split_arg_groups(...)`;
- `trimmed_text(...)`;
- `render_text(...)`.

Use `scan(...)` only for a selector fragment that explicitly allows nested TSIL.

Handle unsupported backend semantics explicitly:

```python
context.effects.skip(
    "TSL-LOWER-UNSUPPORTED-HELPER",
    f"unsupported helper<{name}> for backend {backend_id}",
    source=region.source,
)
return region.full_text
```

Keep output deterministic.

## 5. Register The Lowerer

Edit:

```text
tslc/src/tslc/lower/region_handlers/registry.py
```

```python
from tslc.lower.region_handlers.helpers import HelperLowerer

_REGION_LOWERER_FACTORIES = {
    "helper": HelperLowerer,
    # ...
}
```

Every descriptor must have one lowerer registration.

Tests compare both vocabularies.

## 6. Add Backend Spelling

Use translation data for simple spelling differences:

```text
tsldata/detail/lang/translate_cpp.tsl
tsldata/detail/lang/translate_rust.tsl
```

Example:

```tsl
translation cpp:
  helper_arith_add "::tsl::detail::helpers::arith_add({args})"

translation rust:
  helper_arith_add "crate::tsl_core::detail::helpers::arith_add({args})"
```

The lowerer maps:

```text
helper<arith_add>(...)
  -> translation key helper_arith_add
  -> backend text
```

Use a backend syntax dialect for structured syntax.

Do not embed C++ namespaces in primitive source.

Do not embed Rust module paths in primitive source.

## 7. Add Runtime Assets When Needed

Backend-owned helper code lives under:

```text
tslc/src/tslc/backend/assets/
```

Example ownership:

```cpp
namespace tsl::detail::helpers {
  // C++ helper implementation
}
```

```rust
pub mod detail {
    pub mod helpers {
        // Rust helper implementation
    }
}
```

Keep these assets as explicit files.

Do not bury them as Python string constants.

## 8. Migrate Source Data

Edit bodies under `tsldata/primitives/`.

Before:

```cpp
::tsl::detail::helpers::arith_add(left, right)
```

After:

```tsil
helper<arith_add>(left, right)
```

Use `rg` to find old raw spellings.

Migrate only forms covered by the new semantic contract.

## 9. Update The Reference

Edit [TSIL keyword regions](tsil-keywords.md).

Add the section in descriptor order.

Include:

- exact syntax;
- fixed selector vocabulary when one exists;
- validation rules;
- lowering ownership;
- one TSIL example;
- one C++ expansion;
- one Rust expansion;
- unsupported cases.

## 10. Test The Boundaries

Scanner and validation tests:

- recognize valid syntax;
- diagnose malformed syntax;
- preserve nested regions;
- preserve source locations.

Lowering tests:

- render accepted forms;
- recurse into child regions;
- diagnose unsupported forms;
- keep deterministic output.

Generated tests:

- contain the intended C++ spelling;
- contain the intended Rust spelling;
- include required runtime assets;
- build when emitted code changed.

Run focused checks:

```bash
PYTHONPATH=tslc/src python -m pytest -q \
  tslc/tests/test_tsil_scan.py \
  tslc/tests/test_lower_text.py \
  tslc/tests/test_select_and_lower.py
python -m compileall -q tslc/src/tslc
git diff --check
```

Run generated builds when code or assets changed:

```bash
PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds \
  tslc/tests/test_build_verify.py \
  tslc/tests/test_value_tests.py
```

## Review Checklist

- The source grammar is exact.
- The descriptor owns only lexical facts.
- Validation owns only source shape.
- The lowerer is keyword-specific.
- Backend spelling lives in backend-owned data or code.
- Runtime assets are explicit files.
- Primitive source stays backend-neutral.
- Unsupported forms produce diagnostics or skips.
- Renderers do not parse TSIL.
- The next similar region follows the same path.
