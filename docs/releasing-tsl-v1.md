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
3. downloads the generated library, generated documentation, and five native
   VSIX artifacts from that same workflow run;
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

The package workflow builds each archive twice and requires `cmp` to report
byte identity. Release assembly verifies the normalized metadata again, then
checks the generated `rust/Cargo.toml` version and `rust-version` against the
release contract.

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
python .github/scripts/release_production.py archive \
  --kind generated \
  --source ./tslctmp/ci-generated \
  --output ./tslctmp/tsl-generated-test.tar.gz \
  --epoch "$(git show -s --format=%ct HEAD)"
```

The first real candidate is created by pushing an immutable
`v1.0.0-rc.1` tag. Candidate tags require the product status
`release-candidate`; the final `v1.0.0` tag requires `stable`. This prevents a
candidate policy from being presented as a final release.

## Native evidence and the final tag

Candidate staging can run before native evidence is available. A final release
cannot. Its exact native evidence filenames and IDs are owned by
`supplementary/release/tsl-v1-production.json`; release assembly requires both
the SVE and RVV/CHORYS records and verifies that they name the generated
manifest shipped in the release.

The evidence files are deliberately separate from compiler semantics. They are
execution attestations, not inputs that affect selection or lowering. The
release manifest links their hashes, compiler-input identity, generated
manifest identity, and reviewer to the source commit and product asset set.

Until the native evidence exists and the product status is changed to
`stable`, `v1.0.0` fails before publication. Do not weaken that gate to turn
QEMU evidence into a native claim.
