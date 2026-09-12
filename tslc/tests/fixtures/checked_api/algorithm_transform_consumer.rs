use tsl::dataparallel;
use tsl::profile;
use tsl::tsl_core::StaticSimdVector;
use tsl::PreconditionError;

struct CountingUnary {
    calls: usize,
}

impl<V> profile::algo::UnaryKernel<V> for CountingUnary
where
    V: StaticSimdVector<BaseType = i32>,
{
    fn apply(&mut self, value: V::RegisterType) -> V::RegisterType {
        self.calls += 1;
        value
    }
}

struct CountingBinary {
    calls: usize,
}

impl<V> profile::algo::BinaryKernel<V> for CountingBinary
where
    V: StaticSimdVector<BaseType = i32>,
{
    fn apply(
        &mut self,
        left: V::RegisterType,
        _right: V::RegisterType,
    ) -> V::RegisterType {
        self.calls += 1;
        left
    }
}

struct CountingPredicate {
    calls: usize,
}

impl<V> profile::algo::BinaryPredicateKernel<V> for CountingPredicate
where
    V: StaticSimdVector<BaseType = i32>,
    V::MaskType: Default,
{
    fn test(&mut self, _left: V::RegisterType, _right: V::RegisterType) -> V::MaskType {
        self.calls += 1;
        V::MaskType::default()
    }
}

fn main() {
    let input = [1_i32, 2, 3];
    let right = [4_i32, 5, 6, 77];
    let short_right = [7_i32, 8];
    let mut output = [91_i32, 92, 93, 94];
    let mut short_output = [81_i32, 82];
    let mut unary = CountingUnary { calls: 0 };

    let error = profile::algo::transform_unary_checked(
        dataparallel::Fixed::<1>,
        &mut unary,
        &input,
        &mut short_output,
    )
    .unwrap_err();
    assert_eq!(error, PreconditionError::InsufficientOutput);
    assert_eq!(unary.calls, 0);
    assert_eq!(short_output, [81, 82]);

    let mut binary = CountingBinary { calls: 0 };
    let error = profile::algo::transform_binary_checked(
        dataparallel::Fixed::<1>,
        &mut binary,
        &input,
        &short_right,
        &mut output,
    )
    .unwrap_err();
    assert_eq!(error, PreconditionError::InsufficientInput);
    assert_eq!(binary.calls, 0);
    assert_eq!(output, [91, 92, 93, 94]);

    let error = profile::algo::transform_binary_checked(
        dataparallel::Fixed::<1>,
        &mut binary,
        &input,
        &right,
        &mut short_output,
    )
    .unwrap_err();
    assert_eq!(error, PreconditionError::InsufficientOutput);
    assert_eq!(binary.calls, 0);
    assert_eq!(short_output, [81, 82]);

    profile::algo::transform_binary_checked(
        dataparallel::Fixed::<1>,
        &mut binary,
        &input,
        &right,
        &mut output,
    )
    .unwrap();
    assert_eq!(binary.calls, 3);
    assert_eq!(output, [1, 2, 3, 94]);

    unary.calls = 0;
    let indices = [2_usize, 0];
    let mut selected_output = [71_i32, 72, 73];
    profile::algo::transform_selected_unary_checked(
        dataparallel::Fixed::<1>,
        &mut unary,
        &input,
        &indices,
        &mut selected_output,
    )
    .unwrap();
    assert_eq!(unary.calls, 2);
    assert_eq!(selected_output, [3, 1, 73]);

    unary.calls = 0;
    selected_output = [71, 72, 73];
    let bad_indices = [0_usize, 3];
    let error = profile::algo::transform_selected_unary_checked(
        dataparallel::Fixed::<1>,
        &mut unary,
        &input,
        &bad_indices,
        &mut selected_output,
    )
    .unwrap_err();
    assert_eq!(error, PreconditionError::IndexOutOfBounds);
    assert_eq!(unary.calls, 0);
    assert_eq!(selected_output, [71, 72, 73]);

    let mut predicate = CountingPredicate { calls: 0 };
    let mut masks: [u64; 0] = [];
    let error = profile::algo::predicate_binary_checked(
        dataparallel::Fixed::<1>,
        &mut predicate,
        &input,
        &right,
        &mut masks,
    )
    .unwrap_err();
    assert_eq!(error, PreconditionError::InsufficientOutput);
    assert_eq!(predicate.calls, 0);

    let scaled_indices = [0_usize, 1];
    let error = profile::algo::transform_selected_unary_scaled_checked::<1, _, _, i32>(
        dataparallel::Fixed::<1>,
        &mut unary,
        &input,
        &scaled_indices,
        &mut selected_output,
    )
    .unwrap_err();
    assert_eq!(error, PreconditionError::Misaligned);
    assert_eq!(unary.calls, 0);

    let overflowing_indices = [usize::MAX];
    let error = profile::algo::transform_selected_unary_scaled_checked::<
        { u32::MAX },
        _,
        _,
        i32,
    >(
        dataparallel::Fixed::<1>,
        &mut unary,
        &input,
        &overflowing_indices,
        &mut selected_output,
    )
    .unwrap_err();
    assert_eq!(error, PreconditionError::AddressOverflow);
    assert_eq!(unary.calls, 0);

    unary.calls = 0;
    unsafe {
        profile::algo::transform_unary(
            dataparallel::Fixed::<1>,
            &mut unary,
            input.as_ptr(),
            output.as_mut_ptr(),
            input.len(),
        );
    }
    assert_eq!(unary.calls, 3);
    assert_eq!(output, [1, 2, 3, 94]);
}
