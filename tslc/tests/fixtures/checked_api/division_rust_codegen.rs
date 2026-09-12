#![allow(improper_ctypes_definitions)]

use tsl::profile::div;
use tsl::tsl_core::{Generic, Simd, SimdVector};

type Vec = Simd<i32, Generic<4>>;
type Register = <Vec as SimdVector>::RegisterType;

#[no_mangle]
#[inline(never)]
pub unsafe extern "C" fn unchecked_divide_rust(
    dividend: Register,
    divisor: Register,
) -> Register {
    unsafe { div::<Vec>(dividend, divisor) }
}

fn main() {}
