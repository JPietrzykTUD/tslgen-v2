// tslc static substrate (profile-independent). The SimdVector trait, the
// Simd<BaseType, Extension> type, and the scalar registration. Per-profile modules
// add the extension tags + SimdVector impls for the (type, ext) pairs they use.
#![allow(dead_code)]
#![allow(non_camel_case_types)]

use core::marker::PhantomData;
use core::ops::{Index, IndexMut};

pub trait SimdVector {
    type BaseType;
    type RegisterType;
    type MaskType;
    // The integral mask (to_integral's result): the mask packed into an unsigned integer,
    // one bit per lane (the native __mmaskN, or a lane-sized uint on lane-bitmask ISAs).
    type ImaskType;
    // The array type this vector lowers to (the `s[]` kind: to_array's result /
    // from_array's argument), one element per lane.
    type Array;
}

// scalar is always available and needs no SIMD substrate.
pub struct Scalar;

pub struct Simd<T, Ext>(PhantomData<(T, Ext)>);

impl<T> SimdVector for Simd<T, Scalar> {
    type BaseType = T;
    type RegisterType = T;
    type MaskType = bool;
    type ImaskType = u64;
    type Array = array_type<T, 1>;
}

// The `generic` portable vector: a sized, array-backed register parameterized by its lane
// count (a const generic on the tag), counterpart to the C++ `simd<T, generic<LANES>>`. Its
// register is the indexable `[T; LANES]`, so emulated bodies `result[i] = ...` and delegate
// per lane to scalar. Always available, so defined in the static core.
pub struct Generic<const LANES: usize>;

impl<T, const LANES: usize> SimdVector for Simd<T, Generic<LANES>> {
    type BaseType = T;
    type RegisterType = array_type<T, LANES>;
    // Emulated mask: a bitset, one bit per lane (≤64 lanes covers all real widths).
    type MaskType = u64;
    // Integral mask: the same 64-bit bitset (LANES can't size a smaller integer here).
    type ImaskType = u64;
    type Array = array_type<T, LANES>;
}

// A fixed-size array buffer (the `s[]` kind), counterpart to the C++ `tsl::array_type`.
// `array_type<T, N, ALIGN>` is a type *alias* over `ArrayStorage<T, N>`: the load/store calls
// it feeds are unaligned (Rust has no stable `assume_aligned`), so `ALIGN` is cosmetic — and
// making it alias-only means `array_type<T, N, a>` is the *same* type for every `a` (C++ uses
// `a` for `alignas`, where the value matters). Named lowercase to match the corpus token.
#[allow(type_alias_bounds)]
pub type array_type<T, const N: usize, const ALIGN: usize = 1> = ArrayStorage<T, N>;

#[derive(Clone, Copy)]
pub struct ArrayStorage<T, const N: usize> {
    storage: [T; N],
}

impl<T, const N: usize> ArrayStorage<T, N> {
    pub fn data(&mut self) -> *mut T {
        self.storage.as_mut_ptr()
    }
}

impl<T: Copy, const N: usize> ArrayStorage<T, N> {
    pub fn fill(&mut self, value: T) {
        self.storage = [value; N];
    }
}

impl<T, const N: usize> Index<usize> for ArrayStorage<T, N> {
    type Output = T;
    fn index(&self, i: usize) -> &T {
        &self.storage[i]
    }
}

impl<T, const N: usize> IndexMut<usize> for ArrayStorage<T, N> {
    fn index_mut(&mut self, i: usize) -> &mut T {
        &mut self.storage[i]
    }
}

// Zero/default register for `var<init_register>`. A manual impl (not derived) so it works
// for any `N` (std's `[T; N]: Default` is limited to small N).
impl<T: Copy + Default, const N: usize> Default for ArrayStorage<T, N> {
    fn default() -> Self {
        Self { storage: [T::default(); N] }
    }
}

// Scalar-core helpers used by emulated (loop) bodies, counterpart to C++ `tsl::details`.
// In scope via `use crate::tsl_core::*`. Grows one function at a time with the primitives
// that call `details::*`; `arith_add` is the reductions' accumulate step.
// Pointer-offset helpers used by the generic vector's element-wise load/store loops. Our
// pointer kind is `*mut`, so both take it; callers deref inside an `unsafe`-framed body.
// Type-punning bit reinterpret (`cast<bitcast>` / value `cast<reinterpret>`): reinterpret
// the object representation as a same-sized type. Counterpart to C++ `tsl::bit_cast`; the
// `assert_eq!` makes the size precondition a hard error rather than UB.
pub fn bit_cast<From, To>(value: From) -> To {
    assert_eq!(core::mem::size_of::<From>(), core::mem::size_of::<To>());
    unsafe { core::mem::transmute_copy(&value) }
}

// Mask lane values (`mask::lane::all_true` / `all_false`): the all-bits-set / all-bits-clear
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

pub fn ptr_add<T>(p: *mut T, i: usize) -> *mut T {
    p.wrapping_add(i)
}
pub fn ptr_add_mut<T>(p: *mut T, i: usize) -> *mut T {
    p.wrapping_add(i)
}

pub mod details {
    pub fn arith_add<T: core::ops::Add<Output = T>>(a: T, b: T) -> T {
        a + b
    }
    pub fn arith_mul<T: core::ops::Mul<Output = T>>(a: T, b: T) -> T {
        a * b
    }
}
