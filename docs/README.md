# Project Documentation

This directory contains human-authored project documentation for maintainers and
contributors.

Use this directory for topic guides that are broader than the quick-start
overview in `README.md` and do not belong to the compiler design contract in
`tslc/CHARTER.md` or the architecture narrative in `tslc/DESCRIPTION.md`.

- [TSIL keyword regions](tsil-keywords.md) inventories the TSIL regions
  recognized by `tslc` and describes how they validate, lower, and interact
  with backends.
- [Adding a TSIL keyword region](add-keyword.md) gives maintainers a
  step-by-step guide for adding a new recognized TSIL keyword.

Do not use this directory for generated-TSL documentation assets. Those live in
`supplementary/docs/` because they are inputs used by TSL documentation
generation.
