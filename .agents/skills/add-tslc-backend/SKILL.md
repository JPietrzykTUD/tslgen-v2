---
name: add-tslc-backend
description: Add a backend or backend capability to tslc. Use when asked to introduce a new generated language/backend, register backend IDs or capabilities, add backend-specific type/value/intrinsic translation, add backend render assets, or make backend support additive and validated.
---

# Add TSLC Backend

## Workflow

1. Read `AGENTS.md`, `CHARTER.md`, `PLANS.md`, `tslc/AGENTS.md`,
   `tslc/CHARTER.md`, and the existing `tslc/src/tslc/backend/`,
   `tslc/src/tslc/render/`, `tslc/src/tslc/output/`, relevant
   `tsldata/detail/`, `tslc.toml`, `tslc/src/tslc/project_config.py`,
   compiler-owned asset manifests, and `supplementary/` patterns.
2. Define the backend ID, supported profiles/extensions, signature and value
   spellings, intrinsic/query translations, generated project layout, and
   verification story.
3. Add backend capabilities through the live backend registry/support-policy
   boundary. Keep default backend choice explicit in requests/configuration and
   do not scatter hardcoded backend ID lists or import-time registry snapshots.
4. Add typed translation/render values before templates. Templates may format decided values only.
5. Place packaged backend static files, templates, and helpers under
   `tslc/src/tslc/backend/assets/`. Keep generated-documentation inputs under
   `supplementary/docs/` and machine-profile configuration under
   `supplementary/buildsystem/`. Put compiler-owned static symbol manifests next
   to their backend owner and test exact parity with the packaged asset.
6. Diagnose unsupported capability combinations before rendering or artifact writing.
7. Add focused tests for registration, capability validation, signature/query
   projection, rendering, compiler assets, deterministic artifacts, and verifier
   configuration. Use a fake third backend to prove generic pipeline, doctor,
   authoring, and verification consumers dispatch through capabilities.

## Checks

- Adding a future backend should mostly add a backend module/assets/tests, not edit unrelated schema, lowering, or renderer dispatch code.
- Missing backend support should produce structured diagnostics, not late template errors.
- Backend-specific syntax must not be inferred from raw TSIL text unless the accepted source form is already typed and tested.
- Keep build/test verification injectable and skip-safe for unavailable toolchains.

## Useful Commands

```bash
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_support_policy.py tslc/tests/test_backend_target_capability.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_backend_signature_types.py tslc/tests/test_backend_validation.py tslc/tests/test_render_model.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_generation_conditionals.py tslc/tests/test_query_authoring.py tslc/tests/test_compiler_assets.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_build_verify_config.py tslc/tests/test_authoring_tools.py tslc/tests/test_pipeline_structure.py
PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds tslc/tests/test_build_verify.py tslc/tests/test_value_tests.py
./dev.sh build --primitives add --profiles scalar --backends BACKEND
./dev.sh test --primitives add --profiles scalar --backends BACKEND
```
