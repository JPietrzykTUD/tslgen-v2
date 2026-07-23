//! Shared helpers for the generated value-correctness tests (mirror of tsl_test_core.hpp).
//!
//! Integers compare exactly; floats compare BITWISE with a NaN carve-out — any NaN equals any
//! NaN (INF-INF yields differing NaN signs across paths), but -0.0 and the infinities stay
//! exact. Source cases can request exact bitwise comparison when sign or payload preservation is
//! part of the primitive contract. The same expected data drives both backends, so the semantics
//! match the C++ helper.

pub trait LaneEq: Copy {
    fn lane_eq(self, expected: Self) -> bool;
    fn lane_bitwise_eq(self, expected: Self) -> bool;
}

macro_rules! int_lane_eq {
    ($($t:ty),*) => {
        $( impl LaneEq for $t {
            #[inline]
            fn lane_eq(self, expected: Self) -> bool { self == expected }
            #[inline]
            fn lane_bitwise_eq(self, expected: Self) -> bool { self == expected }
        } )*
    };
}
int_lane_eq!(i8, i16, i32, i64, u8, u16, u32, u64, usize);

impl LaneEq for f32 {
    #[inline]
    fn lane_eq(self, expected: Self) -> bool {
        (self.is_nan() && expected.is_nan()) || self.to_bits() == expected.to_bits()
    }
    #[inline]
    fn lane_bitwise_eq(self, expected: Self) -> bool {
        self.to_bits() == expected.to_bits()
    }
}
impl LaneEq for f64 {
    #[inline]
    fn lane_eq(self, expected: Self) -> bool {
        (self.is_nan() && expected.is_nan()) || self.to_bits() == expected.to_bits()
    }
    #[inline]
    fn lane_bitwise_eq(self, expected: Self) -> bool {
        self.to_bits() == expected.to_bits()
    }
}

/// Whether lane `index` is set in an integer-bitset mask (the generic reference's `u64`, or a
/// hardware mask normalized via `to_integral`). Representation-neutral: only set/clear matters.
#[inline]
pub fn mask_bit(mask: u64, index: usize) -> bool {
    (mask >> index) & 1 != 0
}
