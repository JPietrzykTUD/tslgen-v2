// Mask-lane and compact integral-mask runtime for the tsl_core facade.

use super::StaticSimdVector;

// Mask lane values (`mask<lane_true>()` / `mask<lane_false>()`): the all-bits-set / all-bits-clear
// value of a lane, broadcast by `set1` to build an all-true / all-false lane-bitmask mask.
// Counterpart to C++ `tsl::mask_lane_all_true`; int is `!0`, float the all-ones-bit NaN.
pub trait TslMaskLaneValue: Copy + Default + 'static {
    fn all_true() -> Self;
    fn all_false() -> Self {
        Self::default()
    }
}
macro_rules! impl_tsl_mask_lane_value_int {
    ($ty:ty) => {
        impl TslMaskLaneValue for $ty {
            #[inline]
            fn all_true() -> Self {
                !0
            }
        }
    };
}
macro_rules! impl_tsl_mask_lane_value_float {
    ($ty:ty, $bits:ty) => {
        impl TslMaskLaneValue for $ty {
            #[inline]
            fn all_true() -> Self {
                <$ty>::from_bits(<$bits>::MAX)
            }
        }
    };
}
impl_tsl_mask_lane_value_int!(i8);
impl_tsl_mask_lane_value_int!(i16);
impl_tsl_mask_lane_value_int!(i32);
impl_tsl_mask_lane_value_int!(i64);
impl_tsl_mask_lane_value_int!(u8);
impl_tsl_mask_lane_value_int!(u16);
impl_tsl_mask_lane_value_int!(u32);
impl_tsl_mask_lane_value_int!(u64);
impl_tsl_mask_lane_value_float!(f32, u32);
impl_tsl_mask_lane_value_float!(f64, u64);

// Population count of an integer mask: the number of set bits, as an unsigned count (not the
// input type). Counterpart to C++ `tsl::detail::helpers::popcount`; `count_ones` is already `u32`.
pub trait TslPopCount: Copy {
    fn popcount(self) -> u32;
}
macro_rules! impl_tsl_popcount {
    ($ty:ty) => {
        impl TslPopCount for $ty {
            #[inline]
            fn popcount(self) -> u32 {
                self.count_ones()
            }
        }
    };
}
impl_tsl_popcount!(i8);
impl_tsl_popcount!(i16);
impl_tsl_popcount!(i32);
impl_tsl_popcount!(i64);
impl_tsl_popcount!(u8);
impl_tsl_popcount!(u16);
impl_tsl_popcount!(u32);
impl_tsl_popcount!(u64);

// Trailing-zero count of an integer mask (used by `tzc`). Counterpart to C++
// `tsl::detail::helpers::ctz`; Rust's `trailing_zeros` already returns the bit-width for a zero input.
pub trait TslCtz: Copy {
    fn ctz(self) -> u32;
}
macro_rules! impl_tsl_ctz {
    ($ty:ty) => {
        impl TslCtz for $ty {
            #[inline]
            fn ctz(self) -> u32 {
                self.trailing_zeros()
            }
        }
    };
}
impl_tsl_ctz!(i8);
impl_tsl_ctz!(i16);
impl_tsl_ctz!(i32);
impl_tsl_ctz!(i64);
impl_tsl_ctz!(u8);
impl_tsl_ctz!(u16);
impl_tsl_ctz!(u32);
impl_tsl_ctz!(u64);

// Leading-zero count of an integer (used by `lzc`/`lzc_imask`). Counterpart to C++
// `tsl::detail::helpers::clz`; Rust's `leading_zeros` is already width-aware (a `u8` counts in 8 bits)
// and returns the bit-width for a zero input.
pub trait TslClz: Copy {
    fn clz(self) -> u32;
}
macro_rules! impl_tsl_clz {
    ($ty:ty) => {
        impl TslClz for $ty {
            #[inline]
            fn clz(self) -> u32 {
                self.leading_zeros()
            }
        }
    };
}
impl_tsl_clz!(i8);
impl_tsl_clz!(i16);
impl_tsl_clz!(i32);
impl_tsl_clz!(i64);
impl_tsl_clz!(u8);
impl_tsl_clz!(u16);
impl_tsl_clz!(u32);
impl_tsl_clz!(u64);

// Compact integral masks are always represented by one of these unsigned
// storage types. The trait lets a target-vector-associated ImaskType receive a
// normalized u64 result without target-language type inspection in the compiler.
pub trait TslImask: Copy {
    fn from_u64(value: u64) -> Self;
}
macro_rules! impl_tsl_imask {
    ($($ty:ty),*) => {
        $( impl TslImask for $ty {
            #[inline]
            fn from_u64(value: u64) -> Self {
                value as Self
            }
        } )*
    };
}
impl_tsl_imask!(u8, u16, u32, u64);

pub fn popcount<T: TslPopCount>(v: T) -> u32 {
    v.popcount()
}
pub fn ctz<T: TslCtz>(v: T) -> u32 {
    v.ctz()
}
pub fn clz<T: TslClz>(v: T) -> u32 {
    v.clz()
}
fn imask_low_bits(count: usize) -> u64 {
    if count >= 64 {
        u64::MAX
    } else if count == 0 {
        0
    } else {
        (1u64 << count) - 1u64
    }
}
pub fn imask_insert<ToVec: StaticSimdVector>(
    orig: u64,
    data: u64,
    position: usize,
    source_lanes: usize,
    target_lanes: usize,
) -> ToVec::ImaskType
where
    ToVec::ImaskType: TslImask,
{
    let normalized_orig = orig & imask_low_bits(target_lanes);
    if position >= target_lanes || position >= 64 {
        return ToVec::ImaskType::from_u64(normalized_orig);
    }
    let copied = source_lanes.min(target_lanes - position);
    let window = imask_low_bits(copied) << position;
    let inserted = (data & imask_low_bits(copied)) << position;
    ToVec::ImaskType::from_u64((normalized_orig & !window) | inserted)
}
pub fn imask_extract<ToVec: StaticSimdVector>(
    data: u64,
    position: usize,
    source_lanes: usize,
    target_lanes: usize,
) -> ToVec::ImaskType
where
    ToVec::ImaskType: TslImask,
{
    if position >= source_lanes || position >= 64 {
        return ToVec::ImaskType::from_u64(0);
    }
    let copied = target_lanes.min(source_lanes - position);
    ToVec::ImaskType::from_u64((data >> position) & imask_low_bits(copied))
}
