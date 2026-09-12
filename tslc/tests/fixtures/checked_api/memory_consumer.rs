use tsl::profile::{
    load_checked, load_maskz_checked, mask_false, store_checked, store_mask_checked, Avx2,
};
use tsl::tsl_core::{Simd, SimdVector};
use tsl::PreconditionError;

type Vec = Simd<i32, Avx2>;

#[repr(align(64))]
struct Aligned([i32; 10]);

fn main() {
    let mut input = Aligned([0; 10]);
    for (index, value) in input.0.iter_mut().enumerate() {
        *value = 10 + index as i32;
    }

    assert!(matches!(
        load_checked::<Vec, false>(&[]),
        Err(PreconditionError::InsufficientExtent)
    ));
    assert!(matches!(
        load_checked::<Vec, false>(&input.0[..7]),
        Err(PreconditionError::InsufficientExtent)
    ));
    assert!(matches!(
        load_checked::<Vec, true>(&input.0[1..9]),
        Err(PreconditionError::Misaligned)
    ));
    assert!(matches!(
        load_checked::<Vec, true>(&input.0[1..7]),
        Err(PreconditionError::InsufficientExtent)
    ));

    let value = load_checked::<Vec, false>(&input.0[1..9]).unwrap();
    let mut output = Aligned([-7; 10]);
    assert_eq!(
        store_checked::<Vec, false, _>(&mut output.0[1..8], value),
        Err(PreconditionError::InsufficientExtent)
    );
    assert_eq!(output.0, [-7; 10]);
    store_checked::<Vec, false, _>(&mut output.0[1..9], value).unwrap();
    assert_eq!(&output.0[1..9], &input.0[1..9]);
    assert_eq!(output.0[0], -7);
    assert_eq!(output.0[9], -7);

    output.0.fill(-7);
    assert_eq!(
        store_checked::<Vec, true, _>(&mut output.0[1..9], value),
        Err(PreconditionError::Misaligned)
    );
    assert_eq!(output.0, [-7; 10]);
    assert_eq!(
        store_checked::<Vec, true, _>(&mut output.0[1..7], value),
        Err(PreconditionError::InsufficientExtent)
    );
    assert_eq!(output.0, [-7; 10]);

    assert_eq!(
        store_checked::<Vec, false, _>(&mut [], 99_i32),
        Err(PreconditionError::InsufficientExtent)
    );
    store_checked::<Vec, false, _>(&mut output.0[..1], 99_i32).unwrap();
    assert_eq!(output.0[0], 99);

    let no_lanes = mask_false::<Vec>();
    assert!(matches!(
        load_maskz_checked::<Vec, false>(no_lanes, &input.0[..7]),
        Err(PreconditionError::InsufficientExtent)
    ));
    output.0.fill(-7);
    assert_eq!(
        store_mask_checked::<Vec, false>(no_lanes, &mut output.0[..7], value),
        Err(PreconditionError::InsufficientExtent)
    );
    assert_eq!(output.0, [-7; 10]);
    assert_eq!(
        store_mask_checked::<Vec, true>(no_lanes, &mut output.0[1..9], value),
        Err(PreconditionError::Misaligned)
    );
    assert_eq!(output.0, [-7; 10]);

    assert_eq!(<Vec as SimdVector>::lane_count(), 8);
}
