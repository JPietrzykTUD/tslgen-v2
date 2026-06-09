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
pub struct SseVl;
pub struct Avx2;
pub struct Avx2Vl;
pub struct Avx512;

pub struct Simd<T, Ext>(PhantomData<(T, Ext)>);

// Scalar: the register value is just the base value.
impl<T> SimdVector for Simd<T, Scalar> {
    type BaseType = T;
    type RegisterType = T;
}

#[cfg(target_arch = "x86_64")]
mod x86_registrations {
    use super::{Avx2, Avx2Vl, Avx512, Simd, SimdVector, Sse, SseVl};

    macro_rules! tsl_simd_x86 {
        ($t:ty, $ext:ty, $reg:ty) => {
            impl SimdVector for Simd<$t, $ext> {
                type BaseType = $t;
                type RegisterType = $reg;
            }
        };
    }

    // 128-bit register, integral lane base
    macro_rules! tsl_simd_x86_128i {
        ($t:ty) => {
            tsl_simd_x86!($t, Sse, core::arch::x86_64::__m128i);
            tsl_simd_x86!($t, SseVl, core::arch::x86_64::__m128i);
        };
    }
    // 256-bit register, integral lane base
    macro_rules! tsl_simd_x86_256i {
        ($t:ty) => {
            tsl_simd_x86!($t, Avx2, core::arch::x86_64::__m256i);
            tsl_simd_x86!($t, Avx2Vl, core::arch::x86_64::__m256i);
        };
    }
    tsl_simd_x86_128i!(i8);
    tsl_simd_x86_128i!(i16);
    tsl_simd_x86_128i!(i32);
    tsl_simd_x86_128i!(i64);
    tsl_simd_x86_128i!(u8);
    tsl_simd_x86_128i!(u16);
    tsl_simd_x86_128i!(u32);
    tsl_simd_x86_128i!(u64);
    tsl_simd_x86_256i!(i8);
    tsl_simd_x86_256i!(i16);
    tsl_simd_x86_256i!(i32);
    tsl_simd_x86_256i!(i64);
    tsl_simd_x86_256i!(u8);
    tsl_simd_x86_256i!(u16);
    tsl_simd_x86_256i!(u32);
    tsl_simd_x86_256i!(u64);
    // 512-bit integral
    tsl_simd_x86!(i8, Avx512, core::arch::x86_64::__m512i);
    tsl_simd_x86!(i16, Avx512, core::arch::x86_64::__m512i);
    tsl_simd_x86!(i32, Avx512, core::arch::x86_64::__m512i);
    tsl_simd_x86!(i64, Avx512, core::arch::x86_64::__m512i);
    tsl_simd_x86!(u8, Avx512, core::arch::x86_64::__m512i);
    tsl_simd_x86!(u16, Avx512, core::arch::x86_64::__m512i);
    tsl_simd_x86!(u32, Avx512, core::arch::x86_64::__m512i);
    tsl_simd_x86!(u64, Avx512, core::arch::x86_64::__m512i);
    // floats
    tsl_simd_x86!(f32, Sse, core::arch::x86_64::__m128);
    tsl_simd_x86!(f32, SseVl, core::arch::x86_64::__m128);
    tsl_simd_x86!(f64, Sse, core::arch::x86_64::__m128d);
    tsl_simd_x86!(f64, SseVl, core::arch::x86_64::__m128d);
    tsl_simd_x86!(f32, Avx2, core::arch::x86_64::__m256);
    tsl_simd_x86!(f32, Avx2Vl, core::arch::x86_64::__m256);
    tsl_simd_x86!(f64, Avx2, core::arch::x86_64::__m256d);
    tsl_simd_x86!(f64, Avx2Vl, core::arch::x86_64::__m256d);
    tsl_simd_x86!(f32, Avx512, core::arch::x86_64::__m512);
    tsl_simd_x86!(f64, Avx512, core::arch::x86_64::__m512d);
}
