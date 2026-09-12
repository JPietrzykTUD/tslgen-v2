use core::arch::x86_64::__m256i;
use tsl::profile::{
    load_convert_up_checked, load_scalar_checked, random_step_checked, Avx2,
};
use tsl::tsl_core::Simd;
use tsl::PreconditionError;

type Vec8 = Simd<i8, Avx2>;
type Vec32 = Simd<i32, Avx2>;
type Scalar = Simd<u32, Avx2>;

fn lanes32(value: __m256i) -> [i32; 8] {
    unsafe { core::mem::transmute(value) }
}

fn check_scalar_load() {
    assert_eq!(load_scalar_checked::<Scalar, false>(&[42]).unwrap(), 42);
    assert_eq!(
        load_scalar_checked::<Scalar, false>(&[]),
        Err(PreconditionError::InsufficientExtent)
    );
}

fn check_converting_load() {
    let input = [1_i8, -2, 3, -4, 5, -6, 7, -8];
    let value = load_convert_up_checked::<Vec8, Vec32>(&input).unwrap();
    assert_eq!(lanes32(value), [1, -2, 3, -4, 5, -6, 7, -8]);
    assert!(matches!(
        load_convert_up_checked::<Vec8, Vec32>(&input[..7]),
        Err(PreconditionError::InsufficientExtent)
    ));
}

fn check_random_output() {
    assert_eq!(
        random_step_checked(&mut []),
        Err(PreconditionError::InsufficientExtent)
    );
    if std::is_x86_feature_detected!("rdrand") {
        let mut output = 0_u64;
        assert!(random_step_checked(core::slice::from_mut(&mut output)).unwrap() <= 1);
    }
}

fn main() {
    check_scalar_load();
    check_converting_load();
    check_random_output();
}
