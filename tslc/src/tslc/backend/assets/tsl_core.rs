// tslc static substrate (profile-independent). The SimdVector/StaticSimdVector
// traits, the Simd<BaseType, Extension> type, and the scalar registration.
// Per-profile modules add the extension tags + vector impls for the
// (type, ext) pairs they use.
#![allow(dead_code)]
#![allow(non_camel_case_types)]

use core::marker::PhantomData;
use core::ops::{Index, IndexMut};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ImplementationState {
    Native,
    Composed,
    Fallback,
    Unknown,
}

pub trait ImplementationStateOf<Primitive, Vec, Args = ()> {
    const VALUE: ImplementationState;
}

pub struct BoolArg<const VALUE: bool>;
pub struct I8Arg<const VALUE: i8>;
pub struct I16Arg<const VALUE: i16>;
pub struct I32Arg<const VALUE: i32>;
pub struct I64Arg<const VALUE: i64>;
pub struct ISizeArg<const VALUE: isize>;
pub struct U8Arg<const VALUE: u8>;
pub struct U16Arg<const VALUE: u16>;
pub struct U32Arg<const VALUE: u32>;
pub struct U64Arg<const VALUE: u64>;
pub struct USizeArg<const VALUE: usize>;

// Public because generated lower-level APIs use these traits as bounds. The
// private supertraits keep their representation contracts compiler-owned.
pub(crate) mod representation_sealed {
    pub trait SimdVector {}
    pub trait StaticSimdVector {}
}

#[allow(private_bounds)] // intentional sealed-trait boundary
pub trait SimdVector: representation_sealed::SimdVector {
    type BaseType;
    type Extension;
    type RegisterType;
    type MaskType;
    // The integral mask (to_integral's result): the mask packed into an unsigned integer,
    // one bit per lane (the native __mmaskN, or a lane-sized uint on lane-bitmask ISAs).
    type ImaskType;
    // The array type this vector lowers to (the `s[]` kind: to_array's owned result /
    // from_array's read-only input), one element per lane. Indexable (yielding a lane's base
    // value) so an element-wise loop body in a *generic* context — e.g. gather's `idx_array[i]`
    // over a free `IndicesType` — can read/write lanes; concrete `array_type` already satisfies
    // this.
    type Array: Index<usize, Output = Self::BaseType> + IndexMut<usize>;
    type WithBaseType<ToBase>;
    type WithExtension<ToExtension>;
    const ALIGN: usize;

    fn lane_count() -> usize;

    // Test lane `index` of a register-backed lane mask (sse/avx2): the mask IS a data register
    // whose lanes are all-ones (set) or all-zeros (clear), so lane `index` is a BaseType-sized
    // byte chunk and nonzero means set. Counterpart to the register branch of C++
    // `tsl::detail::helpers::mask_test`. `mask<test>` calls this only for register reprs; the integer
    // bitset repr (generic `u64`, native `__mmaskN`) uses the inline shift template, so the
    // default body is never reached for those.
    fn mask_lane_test(mask: Self::MaskType, index: usize) -> bool {
        let lane_bytes = core::mem::size_of::<Self::BaseType>();
        let bytes = unsafe {
            core::slice::from_raw_parts(
                (&mask as *const Self::MaskType) as *const u8,
                core::mem::size_of::<Self::MaskType>(),
            )
        };
        bytes[index * lane_bytes..(index + 1) * lane_bytes]
            .iter()
            .any(|&b| b != 0)
    }
}

#[allow(private_bounds)] // intentional sealed-trait boundary
pub trait StaticSimdVector: SimdVector + representation_sealed::StaticSimdVector {
    const ELEMENT_COUNT: usize;
}

// scalar is always available and needs no SIMD substrate.
pub struct Scalar;

pub struct Simd<T, Ext>(PhantomData<(T, Ext)>);

impl<T> representation_sealed::SimdVector for Simd<T, Scalar> {}

impl<T> SimdVector for Simd<T, Scalar> {
    type BaseType = T;
    type Extension = Scalar;
    type RegisterType = T;
    type MaskType = bool;
    type ImaskType = u64;
    type Array = array_type<T, 1>;
    type WithBaseType<ToBase> = Simd<ToBase, Scalar>;
    type WithExtension<ToExtension> = Simd<T, ToExtension>;
    const ALIGN: usize = core::mem::align_of::<T>();

    fn lane_count() -> usize {
        1
    }
}

impl<T> representation_sealed::StaticSimdVector for Simd<T, Scalar> {}

impl<T> StaticSimdVector for Simd<T, Scalar> {
    const ELEMENT_COUNT: usize = 1;
}

// The `generic` portable vector: a sized, array-backed register parameterized by its lane
// count (a const generic on the tag), counterpart to the C++ `simd<T, generic<LANES>>`. Its
// register is the indexable `[T; LANES]`, so emulated bodies `result[i] = ...` and delegate
// per lane to scalar. Always available, so defined in the static core.
pub struct Generic<const LANES: usize>;

// Width invariant: a generic vector models a whole number of 128-bit registers, so
// `LANES * size_of::<T>()` must be a multiple of 16 bytes. The C++ counterpart enforces this with
// a `static_assert` in `simd<T, generic<LANES>>`; stable Rust cannot assert on a generic const in
// type position without nightly `generic_const_exprs`, so it is not a hard check here. It holds by
// CONSTRUCTION for everything tslc emits: size-changing bodies are monomorphized over the 128-bit
// `size_bits` ladder, and the smoke/value harnesses instantiate the `LANES`-parametric bodies at a
// 128-bit-multiple lane count. Only a hand-written `Simd<u8, Generic<3>>` would violate it, unchecked.
impl<T, const LANES: usize> representation_sealed::SimdVector for Simd<T, Generic<LANES>> {}

impl<T, const LANES: usize> SimdVector for Simd<T, Generic<LANES>> {
    type BaseType = T;
    type Extension = Generic<LANES>;
    type RegisterType = array_type<T, LANES>;
    // Emulated mask: a bitset, one bit per lane (≤64 lanes covers all real widths).
    type MaskType = u64;
    // Integral mask: the same 64-bit bitset (LANES can't size a smaller integer here).
    type ImaskType = u64;
    type Array = array_type<T, LANES>;
    type WithBaseType<ToBase> = Simd<ToBase, Generic<LANES>>;
    type WithExtension<ToExtension> = Simd<T, ToExtension>;
    const ALIGN: usize = core::mem::align_of::<array_type<T, LANES>>();

    fn lane_count() -> usize {
        LANES
    }
}

impl<T, const LANES: usize> representation_sealed::StaticSimdVector
    for Simd<T, Generic<LANES>>
{
}

impl<T, const LANES: usize> StaticSimdVector for Simd<T, Generic<LANES>> {
    const ELEMENT_COUNT: usize = LANES;
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
        self.as_mut_ptr()
    }

    pub fn as_ptr(&self) -> *const T {
        self.storage.as_ptr()
    }

    pub fn as_mut_ptr(&mut self) -> *mut T {
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

// Scalar-core helpers used by emulated (loop) bodies, counterpart to C++ `tsl::detail::helpers`.
// In scope via `use crate::tsl_core::*`. Grows one function at a time with the primitives
// that call `helper<...>`; `arith_add` is the reductions' accumulate step.
// Pointer-offset helpers used by the generic vector's element-wise load/store loops. Our
// pointer kind is `*mut`, so both take it; callers deref inside an `unsafe`-framed body.
// Implemented only for compiler-known scalar, array, and generated register
// representations where every bit pattern is a valid value. Concrete register
// impls are appended from the typed Rust vector-registration plan.
/// # Safety
///
/// Implementors must accept every possible bit pattern of their size as a
/// valid value.
pub(crate) unsafe trait ValidBitPattern: Copy {}

macro_rules! valid_scalar_bit_patterns {
    ($($ty:ty),* $(,)?) => {
        // SAFETY: the admitted numeric scalar types have no invalid bit patterns.
        $(unsafe impl ValidBitPattern for $ty {})*
    };
}

valid_scalar_bit_patterns!(i8, i16, i32, i64, u8, u16, u32, u64, f32, f64);

// SAFETY: an array is valid for every element representation admitted by its
// `ValidBitPattern` element bound.
unsafe impl<T: ValidBitPattern, const N: usize> ValidBitPattern for ArrayStorage<T, N> {}

// Safe only because the destination marker proves that every copied bit
// pattern is valid. Lowering separately proves the source and destination
// sizes from typed scalar/register facts; the assertion is a defense in depth.
pub(crate) fn bit_cast<From: Copy, To: ValidBitPattern>(value: From) -> To {
    assert_eq!(core::mem::size_of::<From>(), core::mem::size_of::<To>());
    // SAFETY: sizes are equal and `To: ValidBitPattern` admits every possible
    // source representation. `From: Copy` excludes ownership duplication.
    unsafe { core::mem::transmute_copy(&value) }
}

// Explicit internal boundary for source-authored value `cast<reinterpret>`.
// The selected implementation must prove that the concrete destination accepts
// the source representation; lowering always frames calls in an unsafe block.
/// # Safety
///
/// The selected implementation must provide a source value with exactly the
/// destination size. `To: ValidBitPattern` supplies the validity proof.
pub(crate) unsafe fn reinterpret_unchecked<From: Copy, To: ValidBitPattern>(value: From) -> To {
    assert_eq!(core::mem::size_of::<From>(), core::mem::size_of::<To>());
    // SAFETY: this function's contract requires the compiler-selected pair to
    // have equal size and a valid destination representation.
    unsafe { core::mem::transmute_copy(&value) }
}

// Lane arithmetic for the `op<add|sub|mul>` operators and normalized division/remainder. SIMD lane
// add/sub/mul arithmetic WRAPS (modular,
// matching the hardware and C++). Rust's `+`/`-`/`*` panic on overflow in debug builds, so the
// integer lanes use the `wrapping_*` ops. Integer division and remainder reject zero before
// `wrapping_div`/`wrapping_rem`, which define the signed overflow pairs; float lanes use ordinary
// arithmetic. The generated per-type impls are monomorphized, so these resolve on the concrete
// lane type with no bound.
pub trait LaneArith: Copy {
    fn tsl_add(self, rhs: Self) -> Self;
    fn tsl_sub(self, rhs: Self) -> Self;
    fn tsl_mul(self, rhs: Self) -> Self;
    fn tsl_div(self, rhs: Self) -> Self;
    fn tsl_rem(self, rhs: Self) -> Self;
}

macro_rules! wrapping_lane_arith {
    ($($t:ty),*) => {
        $( impl LaneArith for $t {
            #[inline] fn tsl_add(self, rhs: Self) -> Self { self.wrapping_add(rhs) }
            #[inline] fn tsl_sub(self, rhs: Self) -> Self { self.wrapping_sub(rhs) }
            #[inline] fn tsl_mul(self, rhs: Self) -> Self { self.wrapping_mul(rhs) }
            #[inline] fn tsl_div(self, rhs: Self) -> Self {
                if rhs == 0 {
                    crate::tsl_core::detail::helpers::arith_zero_divisor_fail();
                }
                self.wrapping_div(rhs)
            }
            #[inline] fn tsl_rem(self, rhs: Self) -> Self {
                if rhs == 0 {
                    crate::tsl_core::detail::helpers::arith_zero_divisor_fail();
                }
                self.wrapping_rem(rhs)
            }
        } )*
    };
}
wrapping_lane_arith!(i8, i16, i32, i64, u8, u16, u32, u64);

macro_rules! float_lane_arith {
    ($($t:ty),*) => {
        $( impl LaneArith for $t {
            #[inline] fn tsl_add(self, rhs: Self) -> Self { self + rhs }
            #[inline] fn tsl_sub(self, rhs: Self) -> Self { self - rhs }
            #[inline] fn tsl_mul(self, rhs: Self) -> Self { self * rhs }
            #[inline] fn tsl_div(self, rhs: Self) -> Self { self / rhs }
            #[inline] fn tsl_rem(self, rhs: Self) -> Self { self % rhs }
        } )*
    };
}
float_lane_arith!(f32, f64);

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

pub fn ptr_add<T>(p: *const T, i: usize) -> *const T {
    p.wrapping_add(i)
}
pub fn ptr_add_mut<T>(p: *mut T, i: usize) -> *mut T {
    p.wrapping_add(i)
}

/// A value usable as a gather/scatter index or scale — an integer lane that converts to a byte
/// offset. Implemented for the integer bases only (floats can't index memory), so a free
/// `IndicesType: IndexVector` guarantees its lanes are valid indices.
pub trait IndexBase: Copy {
    fn as_offset(self) -> usize;
}

macro_rules! impl_index_base {
    ($($t:ty),*) => { $(impl IndexBase for $t { fn as_offset(self) -> usize { self as usize } })* };
}
impl_index_base!(i8, i16, i32, i64, u8, u16, u32, u64, isize, usize);

pub enum BaseSi8 {}
pub enum BaseSi16 {}
pub enum BaseSi32 {}
pub enum BaseSi64 {}
pub enum BaseUi8 {}
pub enum BaseUi16 {}
pub enum BaseUi32 {}
pub enum BaseUi64 {}
pub enum BaseF32 {}
pub enum BaseF64 {}

pub trait BaseTypeDispatch {
    type Key;
}

macro_rules! impl_base_type_dispatch {
    ($($type:ty => $key:ty),* $(,)?) => {
        $(impl BaseTypeDispatch for $type { type Key = $key; })*
    };
}

impl_base_type_dispatch!(
    i8 => BaseSi8,
    i16 => BaseSi16,
    i32 => BaseSi32,
    i64 => BaseSi64,
    u8 => BaseUi8,
    u16 => BaseUi16,
    u32 => BaseUi32,
    u64 => BaseUi64,
    f32 => BaseF32,
    f64 => BaseF64,
);

#[cfg(target_pointer_width = "32")]
impl_base_type_dispatch!(isize => BaseSi32, usize => BaseUi32);

#[cfg(target_pointer_width = "64")]
impl_base_type_dispatch!(isize => BaseSi64, usize => BaseUi64);

/// The byte offset of a gather/scatter index: `index * scale` (scale in {1,2,4,8}). Used by the
/// fallback loops over a byte-reinterpreted base pointer.
pub fn idx_offset<I: IndexBase, S: IndexBase>(index: I, scale: S) -> usize {
    index.as_offset() * scale.as_offset()
}

/// A `mem<copy>` byte-count argument. The corpus types `count_bytes` as the vector's base
/// type, so this normalizes any base (integer or float) to a `usize` byte count — the
/// counterpart to the implicit `size_t` conversion C++ gets for free at the `std::memcpy` call.
pub trait TslByteCount: Copy {
    fn tsl_byte_count(self) -> usize;
}
macro_rules! impl_tsl_byte_count {
    ($($t:ty),*) => { $(impl TslByteCount for $t {
        #[inline]
        fn tsl_byte_count(self) -> usize {
            self as usize
        }
    })* };
}
impl_tsl_byte_count!(i8, i16, i32, i64, u8, u16, u32, u64, f32, f64);

/// `std::memcpy` counterpart: copy `count` bytes from `src` to `dst`. Byte-addressed
/// (`*const u8`/`*mut u8`), so a `void`-cast source/dest plus a base-typed byte count lower
/// identically to the C++ `mem_copy` translate template.
#[inline]
pub unsafe fn mem_copy<C: TslByteCount>(dst: *mut u8, src: *const u8, count: C) {
    core::ptr::copy_nonoverlapping(src, dst, count.tsl_byte_count());
}

// The C allocator, declared directly (no `libc` crate dependency): every Rust `std` binary
// links the C runtime, so these symbols resolve. Using malloc/aligned_alloc/free here — rather
// than Rust's `Layout`-based global allocator — lets `deallocate(ptr)` free with only the
// pointer (the C contract), and mirrors the C++ `std::malloc`/`std::aligned_alloc`/`std::free`
// lowering exactly. Alloc and free MUST share an allocator, so all three go through libc.
extern "C" {
    fn malloc(size: usize) -> *mut core::ffi::c_void;
    fn aligned_alloc(alignment: usize, size: usize) -> *mut core::ffi::c_void;
    fn free(ptr: *mut core::ffi::c_void);
}

/// `std::malloc` counterpart for the `allocate` free function: a `count_bytes` block as an
/// untyped pointer (null on failure, per the C contract).
#[inline]
pub unsafe fn mem_alloc(count_bytes: usize) -> *mut core::ffi::c_void {
    malloc(count_bytes)
}

/// `std::aligned_alloc` counterpart for `allocate_aligned`. Argument order mirrors the
/// translate template (`alignment` then `count_bytes`); `aligned_alloc` requires the size be a
/// multiple of the alignment.
#[inline]
pub unsafe fn mem_alloc_aligned(alignment: usize, count_bytes: usize) -> *mut core::ffi::c_void {
    aligned_alloc(alignment, count_bytes)
}

/// `std::free` counterpart for `deallocate`: frees a malloc/aligned_alloc block by pointer
/// alone, so no `Layout` reconstruction is needed. (`free` reclaims `aligned_alloc` memory on
/// conforming platforms.)
#[inline]
pub unsafe fn mem_free(ptr: *mut core::ffi::c_void) {
    free(ptr);
}

/// A lane value reduced to its 64-bit pattern for `to_ostream` formatting (`self as u64`,
/// matching the C++ `static_cast<std::uint64_t>`). Implemented for every base, incl. floats.
pub trait TslBits: Copy {
    fn tsl_as_u64(self) -> u64;
}
macro_rules! impl_tsl_bits {
    ($($t:ty),*) => { $(impl TslBits for $t {
        #[inline]
        fn tsl_as_u64(self) -> u64 {
            self as u64
        }
    })* };
}
impl_tsl_bits!(i8, i16, i32, i64, u8, u16, u32, u64, f32, f64);

/// Format a lane array into a text buffer (the `to_ostream` body). `modifier` selects the base
/// (0 = binary, 16 = hex, 8 = octal, else decimal); the C++ `tsl::ostream_write` counterpart.
pub fn ostream_write<T: TslBits, const N: usize>(
    out: &mut String,
    arr: &ArrayStorage<T, N>,
    modifier: i32,
) {
    let bits = core::mem::size_of::<T>() * 8;
    let base: u64 = match modifier {
        16 => 16,
        8 => 8,
        0 => 2,
        _ => 10,
    };
    for lane in 0..N {
        let value = arr[N - 1 - lane].tsl_as_u64();
        let masked = if bits >= 64 { value } else { value & ((1u64 << bits) - 1) };
        if base == 2 {
            for b in (0..bits).rev() {
                out.push(if (masked >> b) & 1 == 1 { '1' } else { '0' });
            }
        } else {
            let mut digits = [0u8; 64];
            let mut count = 0usize;
            let mut remaining = masked;
            if remaining == 0 {
                digits[count] = b'0';
                count += 1;
            }
            while remaining > 0 {
                let digit = (remaining % base) as u32;
                digits[count] = char::from_digit(digit, base as u32).unwrap() as u8;
                count += 1;
                remaining /= base;
            }
            while count > 0 {
                count -= 1;
                out.push(digits[count] as char);
            }
        }
        out.push('|');
    }
    out.push('\n');
}

pub mod detail {
    pub mod helpers {
    use super::super::*;

    #[cfg(target_arch = "x86_64")]
    #[target_feature(enable = "rdrand")]
    pub unsafe fn random_step_u64(out: *mut u64) -> usize {
        let mut value = 0u64;
        let status = core::arch::x86_64::_rdrand64_step(&mut value);
        if status != 0 {
            unsafe { *out = value };
        }
        if status != 0 { 1 } else { 0 }
    }

    pub fn arith_add<T: LaneArith>(a: T, b: T) -> T {
        a.tsl_add(b)
    }
    #[cold]
    #[inline(never)]
    pub fn arith_zero_divisor_fail() -> ! {
        panic!("TSL_ARITH_INTEGER_ZERO_DIVISOR")
    }
    pub fn arith_div<T: LaneArith>(a: T, b: T) -> T {
        a.tsl_div(b)
    }
    pub fn arith_mul<T: LaneArith>(a: T, b: T) -> T {
        a.tsl_mul(b)
    }
    // Normalized remainder for emulated `mod` loops. Integer lanes reject zero before
    // `wrapping_rem`, which defines MIN%-1 as zero; float lanes retain fmod semantics.
    pub fn arith_rem<T: LaneArith>(a: T, b: T) -> T {
        a.tsl_rem(b)
    }
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

    // Saturating numeric cast for `convert_down` (`cast<saturating>`). Narrowing a lane that does
    // not fit the destination range CLAMPS to the nearest bound (i16 30000 -> i8 127), matching the
    // primitive's saturating contract and the hardware narrowing intrinsics. Rust `as` truncates
    // int->int (30000 as i8 == 48), so it cannot express this — hence an explicit clamp. Dispatch
    // is by runtime TypeId over the concrete monomorphized types; the guarded `transmute_copy` only
    // runs in the matching branch (so sizes always agree). Counterpart to C++ `tsl::saturating_cast`.
    fn type_is_same<T: 'static, U: 'static>() -> bool {
        core::any::TypeId::of::<T>() == core::any::TypeId::of::<U>()
    }
    fn saturating_from_i128<U: Copy + 'static>(v: i128) -> U {
        if type_is_same::<U, i8>() {
            let r = v.clamp(i8::MIN as i128, i8::MAX as i128) as i8;
            return unsafe { core::mem::transmute_copy(&r) };
        }
        if type_is_same::<U, u8>() {
            let r = v.clamp(0, u8::MAX as i128) as u8;
            return unsafe { core::mem::transmute_copy(&r) };
        }
        if type_is_same::<U, i16>() {
            let r = v.clamp(i16::MIN as i128, i16::MAX as i128) as i16;
            return unsafe { core::mem::transmute_copy(&r) };
        }
        if type_is_same::<U, u16>() {
            let r = v.clamp(0, u16::MAX as i128) as u16;
            return unsafe { core::mem::transmute_copy(&r) };
        }
        if type_is_same::<U, i32>() {
            let r = v.clamp(i32::MIN as i128, i32::MAX as i128) as i32;
            return unsafe { core::mem::transmute_copy(&r) };
        }
        if type_is_same::<U, u32>() {
            let r = v.clamp(0, u32::MAX as i128) as u32;
            return unsafe { core::mem::transmute_copy(&r) };
        }
        if type_is_same::<U, i64>() {
            let r = v.clamp(i64::MIN as i128, i64::MAX as i128) as i64;
            return unsafe { core::mem::transmute_copy(&r) };
        }
        if type_is_same::<U, u64>() {
            let r = v.clamp(0, u64::MAX as i128) as u64;
            return unsafe { core::mem::transmute_copy(&r) };
        }
        if type_is_same::<U, f32>() {
            let r = v as f32;
            return unsafe { core::mem::transmute_copy(&r) };
        }
        if type_is_same::<U, f64>() {
            let r = v as f64;
            return unsafe { core::mem::transmute_copy(&r) };
        }
        panic!("unsupported saturating cast")
    }
    fn saturating_from_u128<U: Copy + 'static>(v: u128) -> U {
        if type_is_same::<U, i8>() {
            let r = if v > i8::MAX as u128 { i8::MAX } else { v as i8 };
            return unsafe { core::mem::transmute_copy(&r) };
        }
        if type_is_same::<U, u8>() {
            let r = if v > u8::MAX as u128 { u8::MAX } else { v as u8 };
            return unsafe { core::mem::transmute_copy(&r) };
        }
        if type_is_same::<U, i16>() {
            let r = if v > i16::MAX as u128 { i16::MAX } else { v as i16 };
            return unsafe { core::mem::transmute_copy(&r) };
        }
        if type_is_same::<U, u16>() {
            let r = if v > u16::MAX as u128 { u16::MAX } else { v as u16 };
            return unsafe { core::mem::transmute_copy(&r) };
        }
        if type_is_same::<U, i32>() {
            let r = if v > i32::MAX as u128 { i32::MAX } else { v as i32 };
            return unsafe { core::mem::transmute_copy(&r) };
        }
        if type_is_same::<U, u32>() {
            let r = if v > u32::MAX as u128 { u32::MAX } else { v as u32 };
            return unsafe { core::mem::transmute_copy(&r) };
        }
        if type_is_same::<U, i64>() {
            let r = if v > i64::MAX as u128 { i64::MAX } else { v as i64 };
            return unsafe { core::mem::transmute_copy(&r) };
        }
        if type_is_same::<U, u64>() {
            let r = if v > u64::MAX as u128 { u64::MAX } else { v as u64 };
            return unsafe { core::mem::transmute_copy(&r) };
        }
        if type_is_same::<U, f32>() {
            let r = v as f32;
            return unsafe { core::mem::transmute_copy(&r) };
        }
        if type_is_same::<U, f64>() {
            let r = v as f64;
            return unsafe { core::mem::transmute_copy(&r) };
        }
        panic!("unsupported saturating cast")
    }
    fn saturating_from_f64<U: Copy + 'static>(v: f64) -> U {
        if type_is_same::<U, i8>() {
            let r = if v.is_nan() { 0 } else if v < i8::MIN as f64 { i8::MIN } else if v > i8::MAX as f64 { i8::MAX } else { v as i8 };
            return unsafe { core::mem::transmute_copy(&r) };
        }
        if type_is_same::<U, u8>() {
            let r = if v.is_nan() || v < 0.0 { 0 } else if v > u8::MAX as f64 { u8::MAX } else { v as u8 };
            return unsafe { core::mem::transmute_copy(&r) };
        }
        if type_is_same::<U, i16>() {
            let r = if v.is_nan() { 0 } else if v < i16::MIN as f64 { i16::MIN } else if v > i16::MAX as f64 { i16::MAX } else { v as i16 };
            return unsafe { core::mem::transmute_copy(&r) };
        }
        if type_is_same::<U, u16>() {
            let r = if v.is_nan() || v < 0.0 { 0 } else if v > u16::MAX as f64 { u16::MAX } else { v as u16 };
            return unsafe { core::mem::transmute_copy(&r) };
        }
        if type_is_same::<U, i32>() {
            let r = if v.is_nan() { 0 } else if v < i32::MIN as f64 { i32::MIN } else if v > i32::MAX as f64 { i32::MAX } else { v as i32 };
            return unsafe { core::mem::transmute_copy(&r) };
        }
        if type_is_same::<U, u32>() {
            let r = if v.is_nan() || v < 0.0 { 0 } else if v > u32::MAX as f64 { u32::MAX } else { v as u32 };
            return unsafe { core::mem::transmute_copy(&r) };
        }
        if type_is_same::<U, i64>() {
            let r = if v.is_nan() { 0 } else if v < i64::MIN as f64 { i64::MIN } else if v > i64::MAX as f64 { i64::MAX } else { v as i64 };
            return unsafe { core::mem::transmute_copy(&r) };
        }
        if type_is_same::<U, u64>() {
            let r = if v.is_nan() || v < 0.0 { 0 } else if v > u64::MAX as f64 { u64::MAX } else { v as u64 };
            return unsafe { core::mem::transmute_copy(&r) };
        }
        if type_is_same::<U, f32>() {
            let r = if v.is_nan() { f32::NAN } else if v > f32::MAX as f64 { f32::MAX } else if v < -(f32::MAX as f64) { -f32::MAX } else { v as f32 };
            return unsafe { core::mem::transmute_copy(&r) };
        }
        if type_is_same::<U, f64>() {
            return unsafe { core::mem::transmute_copy(&v) };
        }
        panic!("unsupported saturating cast")
    }
    pub fn saturating_cast_value<T: Copy + 'static, U: Copy + 'static>(value: T) -> U {
        if type_is_same::<T, i8>() {
            let v = unsafe { core::mem::transmute_copy::<T, i8>(&value) };
            return saturating_from_i128::<U>(v as i128);
        }
        if type_is_same::<T, u8>() {
            let v = unsafe { core::mem::transmute_copy::<T, u8>(&value) };
            return saturating_from_u128::<U>(v as u128);
        }
        if type_is_same::<T, i16>() {
            let v = unsafe { core::mem::transmute_copy::<T, i16>(&value) };
            return saturating_from_i128::<U>(v as i128);
        }
        if type_is_same::<T, u16>() {
            let v = unsafe { core::mem::transmute_copy::<T, u16>(&value) };
            return saturating_from_u128::<U>(v as u128);
        }
        if type_is_same::<T, i32>() {
            let v = unsafe { core::mem::transmute_copy::<T, i32>(&value) };
            return saturating_from_i128::<U>(v as i128);
        }
        if type_is_same::<T, u32>() {
            let v = unsafe { core::mem::transmute_copy::<T, u32>(&value) };
            return saturating_from_u128::<U>(v as u128);
        }
        if type_is_same::<T, i64>() {
            let v = unsafe { core::mem::transmute_copy::<T, i64>(&value) };
            return saturating_from_i128::<U>(v as i128);
        }
        if type_is_same::<T, u64>() {
            let v = unsafe { core::mem::transmute_copy::<T, u64>(&value) };
            return saturating_from_u128::<U>(v as u128);
        }
        if type_is_same::<T, f32>() {
            let v = unsafe { core::mem::transmute_copy::<T, f32>(&value) };
            return saturating_from_f64::<U>(v as f64);
        }
        if type_is_same::<T, f64>() {
            let v = unsafe { core::mem::transmute_copy::<T, f64>(&value) };
            return saturating_from_f64::<U>(v);
        }
        panic!("unsupported saturating cast")
    }
    }
}
