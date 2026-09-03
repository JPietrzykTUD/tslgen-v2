#![allow(improper_ctypes_definitions)]

use tsl::profile::{load, Avx2};
use tsl::tsl_core::{Simd, SimdVector};

type Vec = Simd<i32, Avx2>;
type Register = <Vec as SimdVector>::RegisterType;

#[no_mangle]
#[inline(never)]
pub unsafe extern "C" fn unchecked_load_rust(source: *const i32) -> Register {
    unsafe { load::<Vec, false>(source) }
}

fn main() {}
