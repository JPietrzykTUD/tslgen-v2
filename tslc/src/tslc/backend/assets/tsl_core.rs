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
    // from_array's argument), one element per lane. Indexable (yielding a lane's base value) so
    // an element-wise loop body in a *generic* context — e.g. gather's `idx_array[i]` over a free
    // `IndicesType` — can read/write lanes; concrete `array_type` already satisfies this.
    type Array: Index<usize, Output = Self::BaseType> + IndexMut<usize>;

    // Test lane `index` of a register-backed lane mask (sse/avx2): the mask IS a data register
    // whose lanes are all-ones (set) or all-zeros (clear), so lane `index` is a BaseType-sized
    // byte chunk and nonzero means set. Counterpart to the register branch of C++
    // `tsl::details::mask_test`. `mask<test>` calls this only for register reprs; the integer
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

// Lane arithmetic for the `op<add|sub|mul>` operators: SIMD lane arithmetic WRAPS (modular,
// matching the hardware and C++). Rust's `+`/`-`/`*` panic on overflow in debug builds, so the
// integer lanes use the `wrapping_*` ops; float lanes use ordinary arithmetic. The generated
// per-type impls are monomorphized, so these resolve on the concrete lane type with no bound.
pub trait LaneArith: Copy {
    fn tsl_add(self, rhs: Self) -> Self;
    fn tsl_sub(self, rhs: Self) -> Self;
    fn tsl_mul(self, rhs: Self) -> Self;
}

macro_rules! wrapping_lane_arith {
    ($($t:ty),*) => {
        $( impl LaneArith for $t {
            #[inline] fn tsl_add(self, rhs: Self) -> Self { self.wrapping_add(rhs) }
            #[inline] fn tsl_sub(self, rhs: Self) -> Self { self.wrapping_sub(rhs) }
            #[inline] fn tsl_mul(self, rhs: Self) -> Self { self.wrapping_mul(rhs) }
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
        } )*
    };
}
float_lane_arith!(f32, f64);

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

// Population count of an integer mask: the number of set bits, as an unsigned count (not the
// input type). Counterpart to C++ `tsl::details::popcount`; `count_ones` is already `u32`.
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
// `tsl::details::ctz`; Rust's `trailing_zeros` already returns the bit-width for a zero input.
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
// `tsl::details::clz`; Rust's `leading_zeros` is already width-aware (a `u8` counts in 8 bits)
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

pub fn ptr_add<T>(p: *mut T, i: usize) -> *mut T {
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

pub mod details {
    pub fn arith_add<T: core::ops::Add<Output = T>>(a: T, b: T) -> T {
        a + b
    }
    pub fn arith_mul<T: core::ops::Mul<Output = T>>(a: T, b: T) -> T {
        a * b
    }
    // Remainder for emulated `mod` loops. Rust `%` is integer remainder / float fmod, so one
    // bound covers both; counterpart to C++ `tsl::details::arith_rem`.
    pub fn arith_rem<T: core::ops::Rem<Output = T>>(a: T, b: T) -> T {
        a % b
    }
    pub fn popcount<T: super::TslPopCount>(v: T) -> u32 {
        v.popcount()
    }
    pub fn ctz<T: super::TslCtz>(v: T) -> u32 {
        v.ctz()
    }
    pub fn clz<T: super::TslClz>(v: T) -> u32 {
        v.clz()
    }
}
