# Quarantined Pre-Restart tslgen

This directory contains the pre-restart `tslgen/` implementation tree moved by
Milestone 106. It is evidence-only old state, like `../frozen/`.

The clean generator restart owns the fresh top-level `../tslgen/` path. Future
product code must not import from this directory at runtime, port its modules
for convenience, or treat this package layout as the restart architecture.
