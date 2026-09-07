use core::arch::x86_64::{__m256i, _mm256_set1_epi64x};
use tsl::profile::{
    compress_store_checked, expand_load_checked, gather_checked, gather_mask_checked,
    gather_narrow_partial_checked, mask_false, scatter_checked, scatter_maskz_checked,
    set_mask_lane_checked, Avx2,
};
use tsl::tsl_core::{Generic, Simd, SimdVector};
use tsl::PreconditionError;

type Vec32 = Simd<i32, Avx2>;
type Vec64 = Simd<i64, Avx2>;
type Generic32 = Simd<i32, Generic<4>>;

#[repr(align(32))]
struct AlignedI32([i32; 8]);

fn reg32(values: [i32; 8]) -> __m256i {
    unsafe { core::mem::transmute(values) }
}

fn lanes32(value: __m256i) -> [i32; 8] {
    unsafe { core::mem::transmute(value) }
}

fn reg64(values: [i64; 4]) -> __m256i {
    unsafe { core::mem::transmute(values) }
}

fn two_lane_mask() -> <Vec32 as tsl::tsl_core::SimdVector>::MaskType {
    let mask = mask_false::<Vec32>();
    let mask = set_mask_lane_checked::<Vec32>(mask, 1, 1).unwrap();
    set_mask_lane_checked::<Vec32>(mask, 3, 1).unwrap()
}

fn check_indexed() {
    let input = [10_i32, 11, 12, 13, 14, 15, 16, 17];
    let ordered = reg32([0, 1, 2, 3, 4, 5, 6, 7]);
    let gathered = gather_checked::<Vec32, Vec32, 4, 1>(&input, ordered).unwrap();
    assert_eq!(lanes32(gathered), input);

    let partial_indices = reg64([1, 3, 5, 7]);
    let partial = gather_narrow_partial_checked::<Vec32, Vec64, 4, 1>(
        &input,
        partial_indices,
    )
    .unwrap();
    assert_eq!(lanes32(partial), [11, 13, 15, 17, 0, 0, 0, 0]);

    assert!(matches!(
        gather_checked::<Vec32, Vec64, 4, 1>(&input, partial_indices),
        Err(PreconditionError::IndexOutOfBounds)
    ));

    let negative = reg32([-1, 0, 0, 0, 0, 0, 0, 0]);
    assert!(matches!(
        gather_checked::<Vec32, Vec32, 4, 1>(&input, negative),
        Err(PreconditionError::IndexOutOfBounds)
    ));
    let one = reg32([1, 0, 0, 0, 0, 0, 0, 0]);
    assert!(matches!(
        gather_checked::<Vec32, Vec32, 2, 1>(&input, one),
        Err(PreconditionError::Misaligned)
    ));

    let huge = unsafe { _mm256_set1_epi64x(i64::MAX) };
    assert!(matches!(
        gather_checked::<Vec64, Vec64, { u32::MAX }, 1>(&[42_i64], huge),
        Err(PreconditionError::AddressOverflow)
    ));

    let inactive = mask_false::<Vec32>();
    let pass = reg32([20, 21, 22, 23, 24, 25, 26, 27]);
    let preserved = gather_mask_checked::<Vec32, Vec32, 4, 1>(
        inactive,
        &[],
        negative,
        pass,
    )
    .unwrap();
    assert_eq!(lanes32(preserved), [20, 21, 22, 23, 24, 25, 26, 27]);

    let mut output = [-7_i32; 10];
    assert_eq!(
        scatter_checked::<Vec32, Vec32, 4, 1>(&mut output[1..9], negative, pass),
        Err(PreconditionError::IndexOutOfBounds)
    );
    assert_eq!(output, [-7; 10]);
    scatter_maskz_checked::<Vec32, Vec32, 4, 1>(inactive, &mut [], negative, pass)
        .unwrap();
}

fn check_compacted() {
    let value = reg32([10, 11, 12, 13, 14, 15, 16, 17]);
    let mask = two_lane_mask();
    let mut output = AlignedI32([-7_i32; 8]);
    assert_eq!(
        compress_store_checked::<Vec32, true>(mask, &mut output.0[0..1], value),
        Err(PreconditionError::InsufficientExtent)
    );
    assert_eq!(output.0, [-7; 8]);
    assert_eq!(
        compress_store_checked::<Vec32, true>(mask, &mut output.0[1..3], value),
        Err(PreconditionError::Misaligned)
    );
    assert_eq!(output.0, [-7; 8]);
    compress_store_checked::<Vec32, true>(mask, &mut output.0[0..2], value).unwrap();
    assert_eq!(output.0, [11, 13, -7, -7, -7, -7, -7, -7]);

    let packed = AlignedI32([31, 33, 0, 0, 0, 0, 0, 0]);
    assert!(matches!(
        expand_load_checked::<Vec32, true>(mask, &packed.0[0..1]),
        Err(PreconditionError::InsufficientExtent)
    ));
    assert!(matches!(
        expand_load_checked::<Vec32, true>(mask, &packed.0[1..3]),
        Err(PreconditionError::Misaligned)
    ));
    let expanded = expand_load_checked::<Vec32, true>(mask, &packed.0[0..2]).unwrap();
    assert_eq!(lanes32(expanded), [0, 31, 0, 33, 0, 0, 0, 0]);

    let inactive = mask_false::<Vec32>();
    compress_store_checked::<Vec32, true>(inactive, &mut output.0[1..1], value)
        .unwrap();
    let zero = expand_load_checked::<Vec32, true>(inactive, &packed.0[1..1]).unwrap();
    assert_eq!(lanes32(zero), [0; 8]);
}

fn check_compact_mask_representation() {
    assert!(Generic32::mask_lane_test(0b0101, 0));
    assert!(!Generic32::mask_lane_test(0b0101, 1));
    assert!(Generic32::mask_lane_test(0b0101, 2));
}

fn main() {
    check_indexed();
    check_compacted();
    check_compact_mask_representation();
}
