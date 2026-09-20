// tslc static substrate (profile-independent). The SimdVector/StaticSimdVector
// traits, the Simd<BaseType, Extension> type, and the scalar registration.
// Per-profile modules add the extension tags + vector impls for the
// (type, ext) pairs they use.
#![allow(dead_code)]
#![allow(non_camel_case_types)]

use core::marker::PhantomData;
use core::ops::{Index, IndexMut};

/// How a selected primitive specialization is implemented.
///
/// This is a coarse structural classification, not an instruction-count or
/// performance guarantee. `Unknown` means typed evidence is incomplete.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ImplementationState {
    /// One direct expression or one target intrinsic.
    Native,
    /// Typed calls, control flow, or multiple direct operations are composed.
    Composed,
    /// The extension family or lowered body explicitly uses a portable fallback.
    Fallback,
    /// Typed evidence is incomplete, so no stronger claim is valid.
    Unknown,
}

/// A failure reported before a checked operation invokes its ordinary twin.
@{precondition_error_declaration}
{
    /// A runtime lane or memory index is outside the represented extent.
    @{precondition_error_variant_index_out_of_bounds},
    /// An active integer divisor lane is zero.
    @{precondition_error_variant_zero_divisor},
    /// A memory view is shorter than the operation's required payload.
    @{precondition_error_variant_insufficient_extent},
    /// A secondary input or mask range is shorter than the driving range.
    @{precondition_error_variant_insufficient_input},
    /// An output range cannot hold every result selected by the contract.
    @{precondition_error_variant_insufficient_output},
    /// An aligned operation received an address with insufficient alignment.
    @{precondition_error_variant_misaligned},
    /// Ranges overlap where the operation requires them to be disjoint.
    @{precondition_error_variant_overlapping_ranges},
    /// A scaled or offset address cannot be represented.
    @{precondition_error_variant_address_overflow},
    /// Source and target SIMD types have different logical lane counts.
    @{precondition_error_variant_lane_count_mismatch},
}

mod checked_integer_lane_sealed {
    pub trait Sealed {}
}

#[doc(hidden)]
#[allow(private_bounds)]
pub trait CheckedIntegerLane: Copy + checked_integer_lane_sealed::Sealed {}

macro_rules! impl_checked_integer_lane {
    ($($type:ty),* $(,)?) => { $(
        impl checked_integer_lane_sealed::Sealed for $type {}
        impl CheckedIntegerLane for $type {}
    )* };
}
impl_checked_integer_lane!(i8, i16, i32, i64, u8, u16, u32, u64);

/// Compile-time implementation-state query implemented by generated profiles.
///
/// `Args` carries target-vector, overload, and const-generic identity where the
/// callable needs it. Unsupported query shapes intentionally have no impl.
pub trait ImplementationStateOf<Primitive, Vec, Args = ()> {
    /// Propagated implementation state for this profile and callable identity.
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
    type RegisterType: Copy;
    type MaskType: Copy;
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
    const MASK_IS_BITSET: bool = false;

    fn lane_count() -> usize;

    // Test lane `index` for either an integer bitset or a register-backed lane mask. Compact
    // bitsets use one bit per lane. Register masks use an all-zero/all-one BaseType-sized byte
    // chunk per lane. The generated registrations project which representation is selected.
    fn mask_lane_test(mask: Self::MaskType, index: usize) -> bool {
        let bytes = unsafe {
            core::slice::from_raw_parts(
                (&mask as *const Self::MaskType) as *const u8,
                core::mem::size_of::<Self::MaskType>(),
            )
        };
        if Self::MASK_IS_BITSET {
            let logical_byte = index / 8;
            let storage_byte = if cfg!(target_endian = "little") {
                logical_byte
            } else {
                bytes.len() - logical_byte - 1
            };
            return ((bytes[storage_byte] >> (index % 8)) & 1) != 0;
        }
        let lane_bytes = core::mem::size_of::<Self::BaseType>();
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

impl<T: Copy> SimdVector for Simd<T, Scalar> {
    type BaseType = T;
    type Extension = Scalar;
    type RegisterType = T;
    type MaskType = bool;
    type ImaskType = u64;
    type Array = array_type<T, 1>;
    type WithBaseType<ToBase> = Simd<ToBase, Scalar>;
    type WithExtension<ToExtension> = Simd<T, ToExtension>;
    const ALIGN: usize = core::mem::align_of::<T>();
    const MASK_IS_BITSET: bool = true;

    fn lane_count() -> usize {
        1
    }
}

impl<T> representation_sealed::StaticSimdVector for Simd<T, Scalar> {}

impl<T: Copy> StaticSimdVector for Simd<T, Scalar> {
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

impl<T: Copy, const LANES: usize> SimdVector for Simd<T, Generic<LANES>> {
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
    const MASK_IS_BITSET: bool = true;

    fn lane_count() -> usize {
        LANES
    }
}

impl<T, const LANES: usize> representation_sealed::StaticSimdVector
    for Simd<T, Generic<LANES>>
{
}

impl<T: Copy, const LANES: usize> StaticSimdVector for Simd<T, Generic<LANES>> {
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
    pub(crate) fn from_array(storage: [T; N]) -> Self {
        Self { storage }
    }

    pub(crate) fn into_array(self) -> [T; N] {
        self.storage
    }

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

// Focused runtime implementation modules remain private. These re-exports
// preserve the established tsl_core and tsl_core::detail::helpers paths.
mod memory;
mod scalar;
mod mask;
mod io;

pub use io::{ostream_write, TslBits};
pub use mask::{TslClz, TslCtz, TslImask, TslMaskLaneValue, TslPopCount};
pub use memory::{
    idx_offset, mem_alloc, mem_alloc_aligned, mem_copy, mem_free, ptr_add, ptr_add_mut, IndexBase,
    TslByteCount,
};
pub use scalar::{
    BaseF32, BaseF64, BaseSi16, BaseSi32, BaseSi64, BaseSi8, BaseTypeDispatch, BaseUi16, BaseUi32,
    BaseUi64, BaseUi8, LaneArith,
};

#[allow(unused_imports)] // exact crate-visible compatibility paths
pub(crate) use memory::indexed_memory_address_error;
#[allow(unused_imports)] // exact crate-visible compatibility paths
pub(crate) use scalar::{bit_cast, reinterpret_unchecked, ValidBitPattern};

pub mod detail {
    pub mod helpers {
        pub use super::super::mask::{clz, ctz, imask_extract, imask_insert, popcount};
        pub use super::super::scalar::{
            arith_add, arith_div, arith_mul, arith_rem, arith_sub, lane_get_unchecked,
            lane_set_unchecked, saturating_cast_value, scalar_as_cast_value,
        };
        #[cfg(target_arch = "x86_64")]
        pub use super::super::scalar::random_step_u64;
    }
}
