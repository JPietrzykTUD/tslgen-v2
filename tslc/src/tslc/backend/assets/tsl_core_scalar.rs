// Scalar representation, arithmetic, and conversion runtime for the tsl_core facade.

use super::ArrayStorage;

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
// integer lanes use the `wrapping_*` ops. Integer division and remainder assume the public
// nonzero-divisor precondition before `wrapping_div`/`wrapping_rem`, which define the signed
// overflow pairs; float lanes use ordinary arithmetic. The generated per-type impls are
// monomorphized, so these resolve on the concrete lane type with no bound.
pub trait LaneArith: Copy {
    fn tsl_add(self, rhs: Self) -> Self;
    fn tsl_sub(self, rhs: Self) -> Self;
    fn tsl_mul(self, rhs: Self) -> Self;
    /// # Safety
    /// Integer implementors require `rhs` to be nonzero.
    unsafe fn tsl_div(self, rhs: Self) -> Self;
    /// # Safety
    /// Integer implementors require `rhs` to be nonzero.
    unsafe fn tsl_rem(self, rhs: Self) -> Self;
}

macro_rules! wrapping_lane_arith {
    ($($t:ty),*) => {
        $( impl LaneArith for $t {
            #[inline] fn tsl_add(self, rhs: Self) -> Self { self.wrapping_add(rhs) }
            #[inline] fn tsl_sub(self, rhs: Self) -> Self { self.wrapping_sub(rhs) }
            #[inline] fn tsl_mul(self, rhs: Self) -> Self { self.wrapping_mul(rhs) }
            #[inline] unsafe fn tsl_div(self, rhs: Self) -> Self {
                unsafe { core::hint::assert_unchecked(rhs != 0) };
                self.wrapping_div(rhs)
            }
            #[inline] unsafe fn tsl_rem(self, rhs: Self) -> Self {
                unsafe { core::hint::assert_unchecked(rhs != 0) };
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
            #[inline] unsafe fn tsl_div(self, rhs: Self) -> Self { self / rhs }
            #[inline] unsafe fn tsl_rem(self, rhs: Self) -> Self { self % rhs }
        } )*
    };
}
float_lane_arith!(f32, f64);

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

pub trait BaseTypeDispatch: Copy + 'static {
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

#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "rdrand")]
/// # Safety
///
/// `out` must be non-null, properly aligned, and valid to write one `u64`.
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
/// Reads an array lane without a runtime bounds check.
///
/// # Safety
///
/// `index` must be smaller than `N`.
pub unsafe fn lane_get_unchecked<T: Copy, const N: usize>(
    value: ArrayStorage<T, N>,
    index: usize,
) -> T {
    unsafe { *value.storage.get_unchecked(index) }
}
/// Replaces an array lane without a runtime bounds check.
///
/// # Safety
///
/// `value` must point to a live `ArrayStorage`, and `index` must be smaller
/// than `N`.
pub unsafe fn lane_set_unchecked<T, const N: usize>(
    value: *mut ArrayStorage<T, N>,
    index: usize,
    lane: T,
) {
    unsafe { *(*value).storage.get_unchecked_mut(index) = lane };
}
pub fn arith_sub<T: LaneArith>(a: T, b: T) -> T {
    a.tsl_sub(b)
}
/// # Safety
/// Integer `b` must be nonzero.
pub unsafe fn arith_div<T: LaneArith>(a: T, b: T) -> T {
    unsafe { a.tsl_div(b) }
}
pub fn arith_mul<T: LaneArith>(a: T, b: T) -> T {
    a.tsl_mul(b)
}
// Normalized remainder for emulated `mod` loops. Integer lanes require nonzero `b`;
// `wrapping_rem` defines MIN%-1 as zero, while float lanes retain fmod semantics.
/// # Safety
/// Integer `b` must be nonzero.
pub unsafe fn arith_rem<T: LaneArith>(a: T, b: T) -> T {
    unsafe { a.tsl_rem(b) }
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
macro_rules! scalar_as_target {
    ($value:expr) => {{
        if type_is_same::<U, i8>() {
            let result = $value as i8;
            return unsafe { core::mem::transmute_copy(&result) };
        }
        if type_is_same::<U, u8>() {
            let result = $value as u8;
            return unsafe { core::mem::transmute_copy(&result) };
        }
        if type_is_same::<U, i16>() {
            let result = $value as i16;
            return unsafe { core::mem::transmute_copy(&result) };
        }
        if type_is_same::<U, u16>() {
            let result = $value as u16;
            return unsafe { core::mem::transmute_copy(&result) };
        }
        if type_is_same::<U, i32>() {
            let result = $value as i32;
            return unsafe { core::mem::transmute_copy(&result) };
        }
        if type_is_same::<U, u32>() {
            let result = $value as u32;
            return unsafe { core::mem::transmute_copy(&result) };
        }
        if type_is_same::<U, i64>() {
            let result = $value as i64;
            return unsafe { core::mem::transmute_copy(&result) };
        }
        if type_is_same::<U, u64>() {
            let result = $value as u64;
            return unsafe { core::mem::transmute_copy(&result) };
        }
        if type_is_same::<U, f32>() {
            let result = $value as f32;
            return unsafe { core::mem::transmute_copy(&result) };
        }
        if type_is_same::<U, f64>() {
            let result = $value as f64;
            return unsafe { core::mem::transmute_copy(&result) };
        }
    }};
}
pub fn scalar_as_cast_value<T: Copy + 'static, U: Copy + 'static>(value: T) -> U {
    if type_is_same::<T, i8>() {
        let source = unsafe { core::mem::transmute_copy::<T, i8>(&value) };
        scalar_as_target!(source);
    }
    if type_is_same::<T, u8>() {
        let source = unsafe { core::mem::transmute_copy::<T, u8>(&value) };
        scalar_as_target!(source);
    }
    if type_is_same::<T, i16>() {
        let source = unsafe { core::mem::transmute_copy::<T, i16>(&value) };
        scalar_as_target!(source);
    }
    if type_is_same::<T, u16>() {
        let source = unsafe { core::mem::transmute_copy::<T, u16>(&value) };
        scalar_as_target!(source);
    }
    if type_is_same::<T, i32>() {
        let source = unsafe { core::mem::transmute_copy::<T, i32>(&value) };
        scalar_as_target!(source);
    }
    if type_is_same::<T, u32>() {
        let source = unsafe { core::mem::transmute_copy::<T, u32>(&value) };
        scalar_as_target!(source);
    }
    if type_is_same::<T, i64>() {
        let source = unsafe { core::mem::transmute_copy::<T, i64>(&value) };
        scalar_as_target!(source);
    }
    if type_is_same::<T, u64>() {
        let source = unsafe { core::mem::transmute_copy::<T, u64>(&value) };
        scalar_as_target!(source);
    }
    if type_is_same::<T, f32>() {
        let source = unsafe { core::mem::transmute_copy::<T, f32>(&value) };
        scalar_as_target!(source);
    }
    if type_is_same::<T, f64>() {
        let source = unsafe { core::mem::transmute_copy::<T, f64>(&value) };
        scalar_as_target!(source);
    }
    panic!("unsupported scalar-as cast")
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
