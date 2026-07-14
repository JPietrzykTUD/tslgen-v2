---
name: add-tslc-backend
description: Add a backend or backend capability to tslc. Use when Codex is asked to introduce a new generated language/backend, register backend IDs or capabilities, add backend-specific type/value/intrinsic translation, add backend render assets, or make backend support additive and validated.
---

# Add TSLC Backend

## Workflow

1. Read `AGENTS.md`, `CHARTER.md`, `PLANS.md`, `tslc/AGENTS.md`,
   `tslc/CHARTER.md`, and the existing `tslc/src/tslc/backend/`, `render/`,
   `output/`, relevant `tsldata/detail/`, and `supplementary/` patterns.
2. Define the backend ID, supported profiles/extensions, type spellings, intrinsic/value translations, generated project layout, and verification story.
3. Add backend capabilities through the existing backend registry/support-policy boundary. Do not scatter hardcoded backend ID lists.
4. Add typed translation/render values before templates. Templates may format decided values only.
5. Place packaged backend static files, templates, and helpers under
   `tslc/src/tslc/backend/assets/`. Keep generated-documentation inputs under
   `supplementary/docs/` and machine-profile configuration under
   `supplementary/buildsystem/`.
6. Diagnose unsupported capability combinations before rendering or artifact writing.
7. Add focused tests for registration, capability validation, rendering, deterministic artifacts, and verifier configuration.

## Checks

- Adding a future backend should mostly add a backend module/assets/tests, not edit unrelated schema, lowering, or renderer dispatch code.
- Missing backend support should produce structured diagnostics, not late template errors.
- Backend-specific syntax must not be inferred from raw TSIL text unless the accepted source form is already typed and tested.
- Keep build/test verification injectable and skip-safe for unavailable toolchains.

## Useful Commands

```bash
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_support_policy.py tslc/tests/test_backend_target_capability.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_render_model.py tslc/tests/test_output_format.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_build_verify_config.py
./dev.sh generate --primitives add --profiles scalar --backends BACKEND
```
