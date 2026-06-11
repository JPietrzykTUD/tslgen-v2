// tslc static substrate (profile-independent). The SimdVector trait, the
// Simd<BaseType, Extension> type, and the scalar registration. Per-profile modules
// add the extension tags + SimdVector impls for the (type, ext) pairs they use.
#![allow(dead_code)]
#![allow(non_camel_case_types)]

use core::marker::PhantomData;
use core::ops::Index;

pub trait SimdVector {
    type BaseType;
    type RegisterType;
    type MaskType;
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
    type Array = array_type<T, 1>;
}

// A fixed-size array buffer (the `s[]` kind), counterpart to the C++ `tsl::array_type`.
// Named lowercase to match the corpus body token. The load/store calls it feeds are
// unaligned (Rust has no stable `assume_aligned`), so it needs no special alignment;
// `ALIGN` is carried for spelling parity with C++ but unused.
pub struct array_type<T, const N: usize, const ALIGN: usize = 1> {
    storage: [T; N],
}

impl<T, const N: usize, const ALIGN: usize> array_type<T, N, ALIGN> {
    pub fn data(&mut self) -> *mut T {
        self.storage.as_mut_ptr()
    }
}

impl<T: Copy, const N: usize, const ALIGN: usize> array_type<T, N, ALIGN> {
    pub fn fill(&mut self, value: T) {
        self.storage = [value; N];
    }
}

impl<T, const N: usize, const ALIGN: usize> Index<usize> for array_type<T, N, ALIGN> {
    type Output = T;
    fn index(&self, i: usize) -> &T {
        &self.storage[i]
    }
}

// Scalar-core helpers used by emulated (loop) bodies, counterpart to C++ `tsl::details`.
// In scope via `use crate::tsl_core::*`. Grows one function at a time with the primitives
// that call `details::*`; `arith_add` is the reductions' accumulate step.
pub mod details {
    pub fn arith_add<T: core::ops::Add<Output = T>>(a: T, b: T) -> T {
        a + b
    }
}
