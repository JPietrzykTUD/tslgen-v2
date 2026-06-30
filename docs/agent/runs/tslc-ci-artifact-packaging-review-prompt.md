# TSLc CI Split Verification And Packaging Review Prompt

You are reviewing the first split GitHub CI verification/packaging slice.

## Scope

Review:

- `.github/workflows/ci.yml`
- `supplementary/ci/verify_generated_consumers.sh`
- documentation updates in `docs/redesign/design-decisions.md`
- workflow-state updates in `docs/agent/current-redesign-state.md`

Related context from the previous slice:

- generated C++ exposes `tsl::tsl` and profile interface targets;
- Rust is consumed through Cargo, not through CMake;
- generated package publishing is not implemented yet.

## Intended Behavior

- The workflow runs on pull requests, pushes to `main`, release tags matching
  `v*`, and manual dispatch.
- It builds the existing `.devcontainer/Dockerfile` image rather than
  duplicating toolchain setup in YAML.
- Pull requests run Python compile/tests, a focused generated build
  verification through `dev.sh`, and tiny downstream consumer checks.
- Pull requests do not package or upload artifacts.
- Pushes to `main`, release tags, and manual dispatch run Python
  compile/tests, then full generated value-test verification through
  `./dev.sh test --backends cpp,rust`.
- Main/tag/manual runs verify public downstream consumption from the tested
  generated tree:
  - C++ through CMake `FetchContent_MakeAvailable` and `tsl::tsl`;
  - Rust through Cargo path dependency on `tsl_generated`.
- Main/tag/manual runs upload the tested generated output as a workflow
  artifact.
- It does not publish a GitHub Release, crates.io package, or GitHub Pages
  site.

## Review Questions

- Does the workflow keep CI orchestration separate from generator semantics?
- Does it rely on project-owned entry points (`dev.sh`, generated CMake/Cargo)
  rather than duplicating hidden generation/build logic?
- Does the PR gate avoid package/upload steps?
- Does the artifact gate run full generated value tests before uploading?
- Is the CI artifact a dry-run package, not a release contract?
- Is the C++ consumer test checking the public `FetchContent` surface?
- Is the Rust consumer test checking the Cargo surface without introducing
  CMake/Rust coupling?
- Are scratch paths safely constrained under `tslctmp` or `/tmp`?
- Is the workflow likely to be stable in a fresh GitHub Actions runner, given
  the repo's devcontainer Dockerfile?

## Validation To Run

```bash
python -m compileall -q tslc/src/tslc
bash -n dev.sh
bash -n supplementary/ci/verify_generated_consumers.sh
./dev.sh test --primitives add --profiles scalar --backends cpp,rust --output-root ./tslctmp/ci-test-smoke
./dev.sh generate --primitives add --profiles scalar --backends cpp,rust --output-root ./tslctmp/ci-consumer-smoke
bash supplementary/ci/verify_generated_consumers.sh ./tslctmp/ci-consumer-smoke ./tslctmp/ci-consumer-checks
./dev.sh generate --output-root ./tslctmp/ci-generated
bash supplementary/ci/verify_generated_consumers.sh ./tslctmp/ci-generated ./tslctmp/ci-full-consumer-checks
mkdir -p tslctmp/artifacts
tar -C ./tslctmp/ci-generated -czf ./tslctmp/artifacts/tsl-generated-local.tar.gz .
test -s ./tslctmp/artifacts/tsl-generated-local.tar.gz
git diff --check
```

If Docker is available locally, optionally run a workflow-like container smoke
with the devcontainer image. Do not require release publishing for this review.

## Verdict

Return one of:

- `Accept`
- `Needs Revision`
- `Return To Planner`

List findings first, ordered by severity, with file/line references.
