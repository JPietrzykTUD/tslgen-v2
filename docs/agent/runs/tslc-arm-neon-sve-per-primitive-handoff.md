# Handoff — ARM NEON + SVE per-primitive bring-up

Starting point: branch `claude`, commit `d0280fe`
("value-tests: unify renderer architecture, gate scalable tiling, unblock SVE generation").

## What this branch is

Partial ARM NEON + SVE bring-up. The value-test **renderer architecture is now
consolidated and clean** — that work is done. The remaining work is **per-primitive
corpus coverage, not architecture.**

## Architecture you are inheriting (do not re-litigate)

- `value_tests/lane_model.py` is the **single** renderer path for every value-/mask-result
  case shape. One `bind_call_args` + two verifiers (`append_result_check`, `verify_mask`)
  serve golden, masked, mask_result, mask_logic, masked_mask_result and mask_constant —
  fixed `generic<N>` **and** scalable SVE alike. There is no `_render_cpp_scalable.py`.
- Scalable tiling (`expected[i] = authored[i % authored_lanes]`) is gated on the
  corpus-declared fact **`Primitive.cross_lane`** (opt-out: the elementwise default is
  tiling-safe; a cross-lane op sets `cross_lane true`). Enforced uniformly via
  `_case_scalable_common.tiling_is_safe` across all five tiling kinds.
- Per-backend support is the corpus fact **`Extension.backend_supported`**
  (`rust: supported false` ⇒ clean skip, not error). **SVE is C++-only.**

## Verified working (spot-checked primitives only — NOT the full corpus)

- x86/avx2: generate + build + value tests pass under Intel SDE (cpp).
- aarch64 neon & sve: generate + build + value tests pass via `zig c++` + musl + qemu
  (cortex-a76 / a64fx), cpp.

## Honest gaps you must close

- **NEON Rust build+run is UNVERIFIED.** Only cpp was run on ARM. The Rust aarch64
  cross-toolchain (cargo target + linker + qemu) is not established. `verify_project` has
  `rust_target`/`rust_linker` hooks and the CLI exposes `--rust-target`/`--rust-linker`,
  but no Rust aarch64 value test has actually executed. **Establish this before claiming
  NEON rust green.**
- Full-corpus coverage is incomplete; only a handful of primitives are confirmed.

## The green bar (current baseline — protect it)

Fast gate = `260 passed, 3 failed`. The 3 failures
(`test_value_tests` full-corpus avx2 coverage `46 authored_unplanned` + rust parity,
`test_safety_contract` corpus safety) are **pre-existing**, pass at `HEAD`, and reflect the
larger in-progress corpus — not these changes. **A NEW failure, or a different number,
means you broke something — stop and fix.** Do not "fix" the 3 known ones unless that is
your task.

## Railguards (to prevent another design blow-up)

1. **No renderer-architecture changes.** Add primitives by editing `tsldata/` + (only if
   unavoidable) thin support — never by forking renderers or adding `_scalable_*` / per-shape
   modules. If you believe the architecture must change, **stop and ask**, do not refactor.
2. **No TSL-data leakage:** no primitive/extension/intrinsic names hardcoded in `tslc/src`.
3. **One primitive at a time.** generate → build → value tests green for the target profiles
   → only then move on. Re-run the fast gate after each; keep it at `260/3`.
4. **Verify, don't assert.** Never report "green" without running generate+build+test. Rust
   must compile on **stable**.
5. **Minimal blast radius.** Prefer corpus + existing patterns; if you touch a generator,
   keep the change local and re-verify the whole gate.
6. **Commit per milestone** (each primitive or small batch), honest messages, trailer
   `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

## Toolchain (exact)

- x86: `--test --sde /opt/intel-sde/sde64`
- neon/sve (cpp): prepend `PATH=/opt/zig:$PATH`, then
  `--test --qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl`
  (musl ⇒ static ⇒ qemu-user runs it directly; qemu auto-selects `-cpu cortex-a76` / `a64fx`).
- Fast gate: `PYTHONPATH=tslc/src python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests`

---

## Prompt for the next agent

> **Context:** Start from branch `claude`, commit `d0280fe`. Read this handoff first. The
> value-test renderer architecture is finalized — your job is **corpus coverage, not redesign.**
>
> **Phase 1 — NEON, C++ *and* Rust.** One primitive (or small related batch) at a time, make
> ARM NEON support **green**: the primitive *generates* (exit 0), *builds*, and its *value tests
> pass* for both backends.
> - C++ neon:
>   `PATH=/opt/zig:$PATH … --backends cpp --profiles neon --primitives <name> --test
>   --qemu-aarch64 --cpp-compiler "zig c++" --cpp-target aarch64-linux-musl`
> - **Rust neon is currently unproven** — first establish the Rust aarch64 cross-build+run path
>   (cargo `aarch64-unknown-linux-musl` target, zig as linker, qemu) on one trivial primitive,
>   then proceed. If you cannot make Rust aarch64 execute, **stop and report** rather than faking it.
> - Mark genuinely cross-lane primitives `cross_lane true` in the corpus; elementwise need nothing.
> - After each primitive: re-run the fast gate; it must stay `260 passed, 3 failed` (the documented
>   pre-existing failures). Any new failure means stop and fix.
>
> **Checkpoint:** when NEON (cpp+rust) is green across the targeted primitives, **commit**
> (honest message, standard trailer).
>
> **Phase 2 — SVE, C++ only** (Rust is `supported false` for SVE — do not attempt it). Same
> per-primitive loop, `--profiles sve`, same green bar. For cross-lane ops, either provide a
> scalable-valid body or leave them `cross_lane true` so they are skipped rather than mistiled.
>
> **Hard rules:** (1) don't change the renderer/lane-model architecture — add via `tsldata` +
> thin support; if you think it needs changing, ask. (2) No primitive/extension/intrinsic names
> in `tslc/src`. (3) Never claim green without running generate+build+test. (4) Keep the fast
> gate green; don't "fix" the 3 known WIP failures. (5) Commit per milestone. (6) Report honestly
> what is verified vs assumed.
>
> **Definition of done per primitive:** generate exit 0 + build exit 0 + value tests pass under
> the emulator, for the required backends, with the fast gate still at baseline.
