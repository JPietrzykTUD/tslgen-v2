// tslc static substrate (profile-independent). The SimdVector trait, the
// Simd<BaseType, Extension> type, and the scalar registration. Per-profile modules
// add the extension tags + SimdVector impls for the (type, ext) pairs they use.
#![allow(dead_code)]
#![allow(non_camel_case_types)]

use core::marker::PhantomData;

pub trait SimdVector {
    type BaseType;
    type RegisterType;
}

// scalar is always available and needs no SIMD substrate.
pub struct Scalar;

pub struct Simd<T, Ext>(PhantomData<(T, Ext)>);

impl<T> SimdVector for Simd<T, Scalar> {
    type BaseType = T;
    type RegisterType = T;
}
