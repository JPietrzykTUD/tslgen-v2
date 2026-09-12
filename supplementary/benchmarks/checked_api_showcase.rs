//! Reproducible Rust half of the TSL v1 checked-API mechanism benchmark.
//!
//! Compile this as a binary inside a generated Rust project. With AVX2 target
//! features it uses the AVX2 profile; otherwise it uses the scalar fallback.

#![allow(unsafe_code)]
#![allow(improper_ctypes_definitions)]

use std::arch::x86_64::_mm_lfence;
use std::hint::black_box;

use tsl::tsl_core::{Simd as ProfileSimd, SimdVector};
use tsl::PreconditionError;

#[cfg(target_feature = "avx2")]
use std::arch::x86_64::{__m256i, _mm256_load_si256, _mm256_set1_epi32, _mm256_store_si256};
#[cfg(target_feature = "avx2")]
use tsl::profile::Avx2;
#[cfg(not(target_feature = "avx2"))]
use tsl::tsl_core::Scalar;

#[cfg(target_feature = "avx2")]
type BenchVec = ProfileSimd<i32, Avx2>;
#[cfg(not(target_feature = "avx2"))]
type BenchVec = ProfileSimd<i32, Scalar>;
type Register = <BenchVec as SimdVector>::RegisterType;

const STORAGE_SIZE: usize = 2048;

#[cfg(target_feature = "avx2")]
const PROFILE: &str = "avx2";
#[cfg(not(target_feature = "avx2"))]
const PROFILE: &str = "scalar";

#[repr(align(64))]
struct Storage([i32; STORAGE_SIZE]);

struct Sample {
    ticks: u64,
    checksum: u64,
    errors: u64,
}

#[cfg(target_feature = "avx2")]
#[inline(always)]
fn raw_set1(value: i32) -> Register {
    unsafe { _mm256_set1_epi32(value) }
}

#[cfg(not(target_feature = "avx2"))]
#[inline(always)]
fn raw_set1(value: i32) -> Register {
    value
}

#[cfg(target_feature = "avx2")]
#[inline(always)]
fn raw_lane(value: Register, index: usize) -> i32 {
    let mut lanes = [0_i32; 8];
    unsafe {
        _mm256_store_si256(lanes.as_mut_ptr().cast::<__m256i>(), value);
        *lanes.as_ptr().add(index)
    }
}

#[cfg(not(target_feature = "avx2"))]
#[inline(always)]
fn raw_lane(value: Register, _index: usize) -> i32 {
    value
}

#[cfg(target_feature = "avx2")]
#[inline(always)]
fn raw_div(dividend: Register, divisor: Register) -> Register {
    let left: [i32; 8] = unsafe { std::mem::transmute(dividend) };
    let right: [i32; 8] = unsafe { std::mem::transmute(divisor) };
    let mut result = [0_i32; 8];
    for lane in 0..8 {
        result[lane] = left[lane] / right[lane];
    }
    unsafe { std::mem::transmute(result) }
}

#[cfg(not(target_feature = "avx2"))]
#[inline(always)]
fn raw_div(dividend: Register, divisor: Register) -> Register {
    dividend / divisor
}

#[cfg(target_feature = "avx2")]
#[inline(always)]
fn raw_load(ptr: *const i32) -> Register {
    unsafe { _mm256_load_si256(ptr.cast::<__m256i>()) }
}

#[cfg(not(target_feature = "avx2"))]
#[inline(always)]
fn raw_load(ptr: *const i32) -> Register {
    unsafe { *ptr }
}

#[cfg(target_feature = "avx2")]
#[inline(always)]
fn raw_checksum(value: Register) -> u64 {
    let lanes: [i32; 8] = unsafe { std::mem::transmute(value) };
    lanes.into_iter().map(|lane| lane as u64).sum()
}

#[cfg(not(target_feature = "avx2"))]
#[inline(always)]
fn raw_checksum(value: Register) -> u64 {
    value as u64
}

#[no_mangle]
#[inline(never)]
pub unsafe extern "C" fn showcase_raw_lane(data: Register, index: usize) -> i32 {
    raw_lane(data, index)
}

#[no_mangle]
#[inline(never)]
pub unsafe extern "C" fn showcase_unchecked_lane(data: Register, index: usize) -> i32 {
    unsafe { tsl::profile::extract_value_at::<BenchVec>(data, index) }
}

#[no_mangle]
#[inline(never)]
pub extern "C" fn showcase_checked_lane(data: Register, index: usize) -> i32 {
    match tsl::profile::extract_value_at_checked::<BenchVec>(data, index) {
        Ok(value) => value,
        Err(_) => 0,
    }
}

#[no_mangle]
#[inline(never)]
pub unsafe extern "C" fn showcase_raw_div(dividend: Register, divisor: Register) -> Register {
    raw_div(dividend, divisor)
}

#[no_mangle]
#[inline(never)]
pub unsafe extern "C" fn showcase_unchecked_div(dividend: Register, divisor: Register) -> Register {
    unsafe { tsl::profile::div::<BenchVec>(dividend, divisor) }
}

#[no_mangle]
#[inline(never)]
pub extern "C" fn showcase_checked_div(dividend: Register, divisor: Register) -> Register {
    match tsl::profile::div_checked::<BenchVec>(dividend, divisor) {
        Ok(value) => value,
        Err(_) => raw_set1(0),
    }
}

#[no_mangle]
#[inline(never)]
pub unsafe extern "C" fn showcase_raw_load(source: *const i32) -> Register {
    raw_load(source)
}

#[no_mangle]
#[inline(never)]
pub unsafe extern "C" fn showcase_unchecked_load(source: *const i32) -> Register {
    unsafe { tsl::profile::load::<BenchVec, true>(source) }
}

#[no_mangle]
#[inline(never)]
pub unsafe extern "C" fn showcase_checked_load(source: *const i32, extent: usize) -> Register {
    let source = unsafe { std::slice::from_raw_parts(source, extent) };
    match tsl::profile::load_checked::<BenchVec, true>(source) {
        Ok(value) => value,
        Err(_) => raw_set1(0),
    }
}

fn ticks() -> u64 {
    unsafe {
        _mm_lfence();
        let value = std::arch::x86_64::_rdtsc();
        _mm_lfence();
        value
    }
}

fn measure(iterations: usize, mut function: impl FnMut(usize, u64, &mut u64) -> u64) -> Sample {
    let mut checksum = 0_u64;
    let mut errors = 0_u64;
    let begin = ticks();
    for iteration in 0..iterations {
        checksum = black_box(function(iteration, checksum, &mut errors));
    }
    let end = ticks();
    Sample {
        ticks: end - begin,
        checksum,
        errors,
    }
}

fn print(operation: &str, variant: &str, sample: Sample, iterations: usize) {
    println!(
        "{}\t{}\t{}\t{:.3}\t{}\t{}",
        PROFILE,
        operation,
        variant,
        sample.ticks as f64 / iterations as f64,
        sample.checksum,
        sample.errors
    );
    let expected_errors = if variant == "checked_failure" {
        iterations as u64
    } else {
        0
    };
    if sample.errors != expected_errors {
        std::process::exit(3);
    }
}

fn main() {
    let arguments: Vec<String> = std::env::args().collect();
    let iterations = arguments
        .get(1)
        .and_then(|value| value.parse().ok())
        .unwrap_or(3_000_000);
    let valid_lane = arguments
        .get(2)
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(0)
        % BenchVec::lane_count();
    let valid_extent = arguments
        .get(3)
        .and_then(|value| value.parse().ok())
        .unwrap_or_else(BenchVec::lane_count);
    let divisor_value = arguments
        .get(4)
        .and_then(|value| value.parse().ok())
        .unwrap_or(3_i32);
    if iterations == 0 || valid_extent != BenchVec::lane_count() || divisor_value == 0 {
        std::process::exit(2);
    }

    let mut storage = Storage([0; STORAGE_SIZE]);
    for (index, value) in storage.0.iter_mut().enumerate() {
        *value = (index % 97) as i32 + 1_000_000;
    }
    let failure_value = raw_set1(storage.0[valid_lane] + arguments.len() as i32);

    println!("profile\toperation\tvariant\tcycles_per_call\tchecksum\terrors");

    print(
        "lane",
        "raw",
        measure(iterations, |iteration, sum, _| {
            let offset =
                (iteration * BenchVec::lane_count()) & (STORAGE_SIZE - BenchVec::lane_count());
            let input = raw_load(unsafe { storage.0.as_ptr().add(offset) });
            sum + raw_lane(input, black_box(valid_lane)) as u64
        }),
        iterations,
    );
    print(
        "lane",
        "unchecked",
        measure(iterations, |iteration, sum, _| {
            let offset =
                (iteration * BenchVec::lane_count()) & (STORAGE_SIZE - BenchVec::lane_count());
            let input = raw_load(unsafe { storage.0.as_ptr().add(offset) });
            sum + unsafe {
                tsl::profile::extract_value_at::<BenchVec>(input, black_box(valid_lane))
            } as u64
        }),
        iterations,
    );
    print(
        "lane",
        "checked_valid",
        measure(iterations, |iteration, sum, errors| {
            let offset =
                (iteration * BenchVec::lane_count()) & (STORAGE_SIZE - BenchVec::lane_count());
            let input = raw_load(unsafe { storage.0.as_ptr().add(offset) });
            match tsl::profile::extract_value_at_checked::<BenchVec>(input, black_box(valid_lane)) {
                Ok(candidate) => sum + candidate as u64,
                Err(_) => {
                    *errors += 1;
                    sum
                }
            }
        }),
        iterations,
    );
    print(
        "lane",
        "checked_failure",
        measure(
            iterations,
            |_, sum, errors| match tsl::profile::extract_value_at_checked::<BenchVec>(
                failure_value,
                black_box(BenchVec::lane_count()),
            ) {
                Ok(candidate) => sum + candidate as u64,
                Err(PreconditionError::IndexOutOfBounds) => {
                    *errors += 1;
                    sum
                }
                Err(_) => sum,
            },
        ),
        iterations,
    );

    print(
        "div",
        "raw",
        measure(iterations, |iteration, sum, _| {
            let offset =
                (iteration * BenchVec::lane_count()) & (STORAGE_SIZE - BenchVec::lane_count());
            let dividend = raw_load(unsafe { storage.0.as_ptr().add(offset) });
            sum + raw_checksum(raw_div(dividend, raw_set1(black_box(divisor_value))))
        }),
        iterations,
    );
    print(
        "div",
        "unchecked",
        measure(iterations, |iteration, sum, _| {
            let offset =
                (iteration * BenchVec::lane_count()) & (STORAGE_SIZE - BenchVec::lane_count());
            let dividend = raw_load(unsafe { storage.0.as_ptr().add(offset) });
            let divisor = raw_set1(black_box(divisor_value));
            sum + raw_checksum(unsafe { tsl::profile::div::<BenchVec>(dividend, divisor) })
        }),
        iterations,
    );
    print(
        "div",
        "checked_valid",
        measure(iterations, |iteration, sum, errors| {
            let offset =
                (iteration * BenchVec::lane_count()) & (STORAGE_SIZE - BenchVec::lane_count());
            let dividend = raw_load(unsafe { storage.0.as_ptr().add(offset) });
            let divisor = raw_set1(black_box(divisor_value));
            match tsl::profile::div_checked::<BenchVec>(dividend, divisor) {
                Ok(candidate) => sum + raw_checksum(candidate),
                Err(_) => {
                    *errors += 1;
                    sum
                }
            }
        }),
        iterations,
    );
    print(
        "div",
        "checked_failure",
        measure(iterations, |iteration, sum, errors| {
            let offset =
                (iteration * BenchVec::lane_count()) & (STORAGE_SIZE - BenchVec::lane_count());
            let dividend = raw_load(unsafe { storage.0.as_ptr().add(offset) });
            match tsl::profile::div_checked::<BenchVec>(dividend, raw_set1(black_box(0))) {
                Ok(candidate) => sum + raw_checksum(candidate),
                Err(PreconditionError::ZeroDivisor) => {
                    *errors += 1;
                    sum
                }
                Err(_) => sum,
            }
        }),
        iterations,
    );

    print(
        "load",
        "raw",
        measure(iterations, |iteration, sum, _| {
            let offset =
                (iteration * BenchVec::lane_count()) & (STORAGE_SIZE - BenchVec::lane_count());
            sum + raw_checksum(raw_load(unsafe { storage.0.as_ptr().add(offset) }))
        }),
        iterations,
    );
    print(
        "load",
        "unchecked",
        measure(iterations, |iteration, sum, _| {
            let offset =
                (iteration * BenchVec::lane_count()) & (STORAGE_SIZE - BenchVec::lane_count());
            let pointer = unsafe { storage.0.as_ptr().add(offset) };
            sum + raw_checksum(unsafe { tsl::profile::load::<BenchVec, true>(pointer) })
        }),
        iterations,
    );
    print(
        "load",
        "checked_valid",
        measure(iterations, |iteration, sum, errors| {
            let offset =
                (iteration * BenchVec::lane_count()) & (STORAGE_SIZE - BenchVec::lane_count());
            let extent = black_box(valid_extent);
            match tsl::profile::load_checked::<BenchVec, true>(&storage.0[offset..offset + extent])
            {
                Ok(candidate) => sum + raw_checksum(candidate),
                Err(_) => {
                    *errors += 1;
                    sum
                }
            }
        }),
        iterations,
    );
    print(
        "load",
        "checked_failure",
        measure(
            iterations,
            |_, sum, errors| match tsl::profile::load_checked::<BenchVec, true>(
                &storage.0[..black_box(0)],
            ) {
                Ok(candidate) => sum + raw_checksum(candidate),
                Err(PreconditionError::InsufficientExtent) => {
                    *errors += 1;
                    sum
                }
                Err(_) => sum,
            },
        ),
        iterations,
    );
}
