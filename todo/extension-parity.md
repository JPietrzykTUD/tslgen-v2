• Complete C++ semantic parity for RVV and SVE—excluding random_step—is achievable. The work should proceed in dependency order, with Rust treated separately because its scalable-vector toolchain support is
  not yet equivalent.


  ## Definition of done


  For every public primitive/signature/type/mask/attribute combination except random_step:


  - RVV, scalable SVE, and SVE128/256/512 have a selected target specialization.
  - Every specialization lowers as native or composed; no fallback, unknown, absent, coverage-gap, or policy-deferred slots.
  - Portable free functions such as allocation may remain target-neutral.
  - Generated C++ builds and value tests pass on the target toolchains/emulators.
  - Exact parity identities are committed to a ratchet, so aggregate counts cannot conceal missing variants.


  ## Recommended sequence


   Phase    Work                                           Completion criterion
  ━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   1        Add a target-parity inventory and ratchet      Every exact target slot is classified, including absent candidates
  ───────  ─────────────────────────────────────────────  ─────────────────────────────────────────────────────────────────────────────────
   2        Fix scalable-vector representation blockers    Arrays, lane lists, width changes, and register grouping are representable
  ───────  ─────────────────────────────────────────────  ─────────────────────────────────────────────────────────────────────────────────
   3        Complete foundational target primitives        Construction, lane access, masks, loads/stores and conversions need no fallback
  ───────  ─────────────────────────────────────────────  ─────────────────────────────────────────────────────────────────────────────────
   4        Complete RVV specializations                   All RVV slots are native/composed
  ───────  ─────────────────────────────────────────────  ─────────────────────────────────────────────────────────────────────────────────
   5        Complete SVE specializations                   Scalable and fixed SVE have no gaps/fallbacks
  ───────  ─────────────────────────────────────────────  ─────────────────────────────────────────────────────────────────────────────────
   6        Add exhaustive generated verification          Full corpus builds and value tests run for every target profile
  ───────  ─────────────────────────────────────────────  ─────────────────────────────────────────────────────────────────────────────────
   7        Add optional ISA and performance tiers         Optional extensions improve code without becoming parity prerequisites
  ───────  ─────────────────────────────────────────────  ─────────────────────────────────────────────────────────────────────────────────
   8        Address Rust separately                        Experimental/nightly first; stable only when toolchain support permits


    ### 1. Build a real parity ratchet


  The current coverage inventory is insufficient: RVV can report 100% because it measures attempted slots; a primitive with no RVV candidate is absent from the denominator. The existing ratchet also collapses
  some mask/axis identities.


  Add a compiler-owned parity projection using:


  - Catalog and the real Selector for the expected candidate universe.
  - GenerationResult.emitted_profiles.
  - LoweredSpecialization.implementation_state, which already distinguishes native, composed, fallback, and unknown (tslc/src/tslc/lower/implementation_facts.py:13).
  - Full logical identity: profile, backend, primitive declaration, signature, mask policy, attributes, variant, source/target extension, and type.


  Keep random_step as the only explicit allowlisted absence, with its x86-only contract recorded.


  ### 2. Solve scalable representation once


  This is the architectural prerequisite. Adding 70 isolated RVV bodies first would duplicate work and preserve the main limitations.


  Required slices:


  - Define scalable s[] and lanes<s> behavior so to_array, from_array, and set no longer remain policy-deferred.
  - Add a typed register-group/multiplicity model:
      - RVV needs LMUL-aware results, not only the current m1 types.
      - SVE may need tuple/grouped representations for lane-preserving width changes.


  - Make convert_lanes work without pretending scalable vectors have a compile-time vector::length.
  - Use the same model for concat, extract, insert, resize_down, resize_up_zero, and resize_up_undef.
  - Resolve the closure failures in extract_value_at, insert_value_at, and fixed-SVE extract.


  This should be a focused compiler/source-data slice with owner-equivalence and additive-family tests before primitive implementations depend on it.


   ### 3. Establish the dependency foundation


  Implement these before higher-level operations because many composed bodies depend on them:


  - Construction: set, set_undef, masked_set1.
  - Lane access: extract_value, extract_value_at, insert_value, insert_value_at.
  - Storage bridges: to_array, from_array, load_scalar.
  - Mask bridges: to_integral, to_mask, to_vector, integral-mask manipulation.
  - Mask storage: load_mask_repr, store_mask_repr.
  - Width conversion: convert_up, convert_down, convert_lanes, load_convert_up.


  Every body should use an exact intrinsic where semantics match; otherwise compose existing primitives through typed call<...> dependencies.


  ### 4. Close RVV by operation family


  Recommended order:


  1. Reductions and counts:
     hadd, hmin, hmax, hand, hor, popcnt, lzc, tzc.


  2. Indexed memory:
     gather, scatter, narrow gathers, masked forms.


  3. Permutation:
     table_lookup, permute_lanes, align_right_lanes, representation changes.


  4. Compression:
     compress, compress_store, expand, expand_load.


  5. Higher-level composition:
     range comparisons, count_matches, conflict, conflict_free, blend_add, mov.


  6. Target-neutral functions:
     allocation, copying, sequences, and output should use honest portable implementations; they do not need fake RVV intrinsics.


  For bit counts, baseline V should have composed implementations. Add an optional V+Zvbb extension/profile for direct vclz, vctz, and vcpop, but do not make semantic parity depend on optional hardware.


  ### 5. Close SVE gaps and fallback states


  Prioritize:


  - Existing lowering gaps and policy deferrals.
  - unknown storage operations: load_scalar, store, store_mask_repr, plus fixed-SVE array/lane mutations.
  - Existing fallback-heavy families: gather/scatter, compress/expand, conflict, conversions, permutations/table lookup, modulo and to_ostream.
  - The remaining integral-mask and representation-change primitives without direct SVE selectors.
  - Verify inherited bodies independently on SVE128, SVE256 and SVE512; inheritance must not substitute for width-specific evidence.


  ### 6. Make verification exhaustive


  The generated-build workflow currently uses add as the general profile smoke test. Parity needs stronger target gates:


  - Full-corpus C++ cross-builds for RVV, SVE and all fixed-SVE profiles.
  - Generated value tests against the generic oracle for every authored target case.
  - RVV runs with at least two VLEN values, such as 128 and 256, to catch hidden fixed-length assumptions.
  - SVE runs at 128/256/512 and one genuinely scalable configuration.
  - Edge coverage for masks, inactive/tail lanes, zero vl, indices, signed overflow, floating conversion/rounding/NaNs, alignment and aliasing.
  - Fail if any requested target slot or value case is skipped.
  - Run performance comparisons on real hardware; QEMU is correctness evidence, not performance evidence.


  ### 7. Treat Rust as a separate product milestone


  SVE intrinsics now exist in nightly Rust but remain unstable under stdarch_aarch64_sve (official nightly source
  (https://doc.rust-lang.org/nightly/src/core/stdarch/crates/core_arch/src/aarch64/sve/generated.rs.html)). Current nightly core::arch::riscv64 remains experimental and does not expose a comparable RVV
  intrinsic surface (official Rust documentation (https://doc.rust-lang.org/nightly/core/arch/riscv64/index.html)).


  Therefore:


  - Finish C++ parity first.
  - Add an explicitly experimental nightly SVE Rust capability afterward.
  - Do not claim stable Rust parity using private LLVM intrinsics or scattered inline assembly.
  - RVV Rust should wait for a supported intrinsic surface or become a separately approved backend/capability project with its own contract and verification.


  The most valuable first implementation slice is the target-parity ratchet, followed by the scalable array/register-group model. Without those, individual RVV/SVE bodies can improve counts but cannot prove
  complete parity.

    There is also relevant uncommitted lzc composition work in the current worktree; that should be preserved and treated as an input to the reduction/bit-count slice. No files were changed during this review.