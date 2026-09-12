# Maintainer Guides

This directory contains human-authored guides.

Generated documentation inputs live in `supplementary/docs/`.

## Choose A Guide

| Goal | Guide |
| --- | --- |
| Use the generated TSL v1 C++ or Rust library | [TSL v1 user guide](tsl-v1-user-guide.md) |
| Move a pre-v1 generated consumer to v1 | [Migrating to TSL v1](migrating-to-tsl-v1.md) |
| Review generated-library release changes | [Changelog](../CHANGELOG.md) |
| Produce and verify a v1 release | [TSL v1 release production](releasing-tsl-v1.md) |
| Check the exact v1 backend/profile/type contract | [TSL v1 support contract](tsl-v1-support.md) |
| Use `tslc` validation, discovery, generation, and doctor commands | [TSLC command-line tools](tslc-cli.md) |
| Configure, use, build, or troubleshoot the editor extension | [TSL editor support](tsl-editor.md) |
| Add or change a primitive | [Adding a primitive](add-primitive.md) |
| Add a target extension or profile | [Adding an extension](add-extension.md) |
| Read the TSIL region reference | [TSIL keyword regions](tsil-keywords.md) |
| Add a TSIL region | [Adding a TSIL keyword region](add-keyword.md) |
| Benchmark implementation variants | [Variant benchmarking and autotuning](variant-benchmarking.md) |

## Compiler Connection

The guides follow the compiler pipeline:

```text
TSL source
  -> parsed syntax
  -> typed catalog
  -> selected implementations
  -> lowered TSIL
  -> backend render models
  -> generated C++ and Rust
```

Use source data for source facts.

Use typed compiler objects after parsing.

Use backend assets for target-language structure.

Use templates only to format decided values.

## Repository Contracts

- [`CHARTER.md`](../CHARTER.md) defines the product contract.
- [`PLANS.md`](../PLANS.md) defines the change workflow.
- [`tslc/DESCRIPTION.md`](../tslc/DESCRIPTION.md) describes the compiler.
- [`AGENTS.md`](../AGENTS.md) defines repository rules.
