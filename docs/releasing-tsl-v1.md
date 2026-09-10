# Producing a TSL v1 release

The generated C++/Rust library is the `1.0.0` product. `tslc` and the VS Code
extension keep independent `0.x` versions. The release tooling verifies and
records all three identities; it does not force the tools onto the library's
version line.

## One publication owner

`.github/workflows/release.yml` is the only tag-triggered publication path.
The Python/PIVOT, coverage, generated C++/Rust, generated package/docs, and
editor/runtime workflows are reusable required gates. They still run directly
for pull requests, `main`, and manual diagnostics, but no longer react to a tag
or create a release independently.

For a tag, the release workflow:

1. resolves the tag to the checked-out commit and validates product, Cargo,
   compiler, editor, MSRV, status, and changelog metadata;
2. waits for all five required reusable workflows;
3. downloads the deployment-bundled generated library, generated documentation,
   and five native VSIX artifacts from that same workflow run;
4. assembles the exact asset set, checks every digest and embedded component
   identity, and writes `release-manifest.json` plus `SHA256SUMS`;
5. uploads that verified directory as an Actions artifact;
6. creates a new draft GitHub release and uploads without `--clobber`;
7. downloads every release asset and byte-compares it with the staged set; and
8. promotes the draft only after the comparison succeeds.

The workflow refuses to touch an existing release. A failed upload therefore
leaves an unpublished draft for inspection. Delete that draft explicitly only
after deciding to retry the same immutable tag. Never replace an asset on a
published release; use a new RC tag when product bytes or behavior change.

## Deterministic archives

`.github/scripts/release_production.py archive` writes the generated library
and documentation tarballs with:

- one versioned root directory;
- lexical entry order;
- the source commit timestamp for every entry and the gzip header;
- numeric owner/group zero and stable `root` names;
- directory/executable mode `0755` and regular-file mode `0644`; and
- no symbolic links or special files.

The package workflow builds each release archive twice and requires `cmp` to
report byte identity. Release assembly verifies the normalized metadata again,
validates the root bundle manifest against the checked-in release-contract
snapshot, and checks every declared bundle path, inner artifact inventory and
file digest, artifact-manifest digest, and extracted size. It then checks the
combined Rust bundle's `Cargo.toml` version and `rust-version` against the
release contract. The full all-profile tree used to build documentation is an
internal CI artifact, not the release payload.

Each VSIX is already built and smoke-tested on its native OS/architecture. The
release assembler additionally verifies its sidecar digest and embedded
runtime manifest: target, compiler version, extension version, clean-tree flag,
and source commit must match the release being staged.

## Release-candidate dry run

A manual run of `TSL Generated Library Release` is non-publishing. Its `tag`
input selects candidate metadata such as `v1.0.0-rc.1`; the run executes all
required gates and produces `tsl-release-staged-v1.0.0-rc.1`. It does not need
the tag to exist and cannot call the publish job.

The local metadata and archive primitives can be checked with:

```bash
python .github/scripts/release_production.py metadata --tag v1.0.0-rc.1
python .github/scripts/build_release_bundles.py \
  ./tslctmp/ci-release-bundles
python .github/scripts/release_production.py archive \
  --kind generated \
  --source ./tslctmp/ci-release-bundles \
  --output ./tslctmp/tsl-generated-test.tar.gz \
  --epoch "$(git show -s --format=%ct HEAD)"
```

The generated archive contains one standalone C++ project per release profile
and one combined Rust release crate. This keeps the public asset set small while
allowing a consumer to extract only its deployment bundle; extracting the whole
archive remains possible for auditing.

The first real candidate is created by pushing an immutable
`v1.0.0-rc.1` tag. Candidate tags require the product status
`release-candidate`; the final `v1.0.0` tag requires `stable`. This prevents a
candidate policy from being presented as a final release.

## Native evidence and the final tag

Candidate staging can run before native evidence is available. A final release
cannot. Its exact native evidence filenames and IDs are owned by
`supplementary/release/tsl-v1-production.json`; release assembly requires both
the SVE and RVV records and verifies that they name the generated bundle
index shipped in the release and the exact target bundle's artifact manifest.

The evidence files are deliberately separate from compiler semantics. They are
execution attestations, not inputs that affect selection or lowering. The
release manifest links their hashes, compiler-input identity, generated
manifest identity, and reviewer to the source commit and product asset set.

Start from the non-accepted examples in
`supplementary/release/attestation-templates/`. Copy them to the exact filenames
configured by `supplementary/release/tsl-v1-production.json` only after replacing
every placeholder with observed evidence. The release validator requires:

- the exact generated bundle-index digest and one shared compiler-input digest
  across the SVE and RVV records, plus the exact `cpp-sve` or `cpp-rvv` inner
  artifact-manifest digest used by each run;
- native machine identity, feature report, OS, compiler version, exact flags,
  and observed vector length(s);
- non-empty generated-value and differential suites with every planned case
  passed and no failure or skip;
- the filter/gather/transform showcase, its binary digest, scalar-oracle and
  canary results, and one exact run record for every observed vector length.

The checked-in RVV downstream-consumer fixture is a portability regression
test. It complements but does not substitute for execution on native RVV
hardware.

The evidence does not contain the final Git commit: doing so would be circular,
because committing that evidence changes the commit. Instead, the compiler-
input digest proves that both native runs used the same generation inputs, the
bundle-index and inner-manifest digests prove that they used the packaged target
project, and the release manifest hashes both evidence files alongside the final
source commit. Adding the completed attestations must not change either tested
digest.

The showcase is a generated-library consumer rather than compiler semantics:

```bash
PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds \
  tslc/tests/test_scalable_release_showcase.py
```

It cross-builds one SVE binary and one RVV binary, then reuses each binary at
the three vector lengths owned by the machine-profile catalog. On native
hardware, run the same fixture against the release-candidate archive, record
the executable SHA-256 before every invocation, and report the observed vector
length in the corresponding native evidence file.

The generated package archive itself is consumed after extraction by clean
CMake and Cargo projects in the package workflow. This tests the bytes that are
staged for release rather than relying only on the pre-archive generation tree.

Until the native evidence exists and the product status is changed to
`stable`, `v1.0.0` fails before publication. Do not weaken that gate to turn
QEMU evidence into a native claim.
