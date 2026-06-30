# TSLc CMake Includability Review Prompt

You are reviewing the CMake includability and C++ profile auto-selection slice.

## Scope

Review the current worktree changes around generated C++ CMake output:

- `tslc/src/tslc/backend/assets/cpp_cmakelists.txt.tmpl`
- `tslc/src/tslc/render/cpp_project.py`
- `tslc/tests/test_profile_rendering.py`
- `tslc/tests/test_build_verify.py`
- related documentation updates in `docs/redesign/**` and
  `docs/agent/current-redesign-state.md`

## Intended Behavior

- Generated C++ output is consumable from a downstream CMake project using
  `FetchContent_MakeAvailable`.
- The stable downstream target is `tsl::tsl`.
- Each generated C++ profile has an interface target
  `tsl_profile_<profile>` and alias `tsl::<profile>`.
- `TSL_PROFILE=<profile>` selects one generated profile explicitly.
- Omitted `TSL_PROFILE` defaults to `auto`, which runs generated
  `CheckCXXSourceRuns` probes when not cross-compiling.
- Auto-selection chooses only among already-generated profiles and falls back
  to `scalar` when probes cannot run and scalar is present.
- Generated smoke/value-test targets default ON only for the top-level
  generated project, not for `FetchContent` consumers.
- Rust remains consumed through Cargo; this slice must not add a CMake Rust
  wrapper.

## Review Questions

Check these design boundaries carefully:

- Does CMake only choose among already-rendered profile targets, or did profile
  selection leak back into primitive/extension selection semantics?
- Are compile flags and feature spellings still derived from typed machine
  profile data before template rendering?
- Is the template limited to formatting already-decided CMake values and probe
  snippets?
- Does `TSL_PROFILE` avoid parent-project collisions better than a bare
  `PROFILE` cache variable?
- Is `TSL_BUILD_TESTS` safe for both standalone generated builds and
  downstream `FetchContent` consumption?
- Are profile aliases deterministic and valid for profile names containing
  characters such as hyphens?
- Is auto-detection deterministic enough when multiple generated profiles
  match the host?

## Validation To Run

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_profile_rendering.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_build_verify.py::test_generated_profiles_build tslc/tests/test_build_verify.py::test_cpp_fetch_content_consumer_builds tslc/tests/test_build_verify.py::test_cpp_auto_profile_configures
./dev.sh build --primitives add --profiles scalar,avx2 --backends cpp
git diff --check
```

If touching build behavior, also consider a small manual generated-project
configure/build with both explicit `-DTSL_PROFILE=scalar` and omitted
`TSL_PROFILE`.

## Verdict

Return one of:

- `Accept`
- `Needs Revision`
- `Return To Planner`

List findings first, ordered by severity, with file/line references.
