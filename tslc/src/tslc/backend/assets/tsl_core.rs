// tslc static core. Hand-written library substrate, copied verbatim into
// generated Rust projects. Defines the SimdVector trait + Simd<BaseType, Extension>
// types that generated impls key on.
#![allow(dead_code)]
#![allow(non_camel_case_types)]

use core::marker::PhantomData;

pub trait SimdVector {
    type BaseType;
    type RegisterType;
}

// Extension tag types (the second Simd<> argument).
pub struct Scalar;
pub struct Sse;
pub struct Avx2;

pub struct Simd<T, Ext>(PhantomData<(T, Ext)>);

// Scalar: the register value is just the base value.
impl<T> SimdVector for Simd<T, Scalar> {
    type BaseType = T;
    type RegisterType = T;
}

#[cfg(target_arch = "x86_64")]
mod x86_registrations {
    use super::{Avx2, Simd, SimdVector, Sse};

    macro_rules! tsl_simd_x86 {
        ($t:ty, $ext:ty, $reg:ty) => {
            impl SimdVector for Simd<$t, $ext> {
                type BaseType = $t;
                type RegisterType = $reg;
            }
        };
    }

    tsl_simd_x86!(i8, Sse, core::arch::x86_64::__m128i);
    tsl_simd_x86!(i16, Sse, core::arch::x86_64::__m128i);
    tsl_simd_x86!(i32, Sse, core::arch::x86_64::__m128i);
    tsl_simd_x86!(i64, Sse, core::arch::x86_64::__m128i);
    tsl_simd_x86!(u8, Sse, core::arch::x86_64::__m128i);
    tsl_simd_x86!(u16, Sse, core::arch::x86_64::__m128i);
    tsl_simd_x86!(u32, Sse, core::arch::x86_64::__m128i);
    tsl_simd_x86!(u64, Sse, core::arch::x86_64::__m128i);
    tsl_simd_x86!(f32, Sse, core::arch::x86_64::__m128);
    tsl_simd_x86!(f64, Sse, core::arch::x86_64::__m128d);

    tsl_simd_x86!(i8, Avx2, core::arch::x86_64::__m256i);
    tsl_simd_x86!(i16, Avx2, core::arch::x86_64::__m256i);
    tsl_simd_x86!(i32, Avx2, core::arch::x86_64::__m256i);
    tsl_simd_x86!(i64, Avx2, core::arch::x86_64::__m256i);
    tsl_simd_x86!(u8, Avx2, core::arch::x86_64::__m256i);
    tsl_simd_x86!(u16, Avx2, core::arch::x86_64::__m256i);
    tsl_simd_x86!(u32, Avx2, core::arch::x86_64::__m256i);
    tsl_simd_x86!(u64, Avx2, core::arch::x86_64::__m256i);
    tsl_simd_x86!(f32, Avx2, core::arch::x86_64::__m256);
    tsl_simd_x86!(f64, Avx2, core::arch::x86_64::__m256d);
}
