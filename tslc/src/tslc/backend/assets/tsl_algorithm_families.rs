use super::*;

pub fn integral_mask_chunk_count<Profile, Policy, T>(_policy: Policy, count: usize) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::integral_mask_chunk_count",
    );
    chunk_count_for_lanes(count, lanes)
}

pub fn mask_chunk_count<Profile, Policy, Layout, T>(_policy: Policy, count: usize) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Layout: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_mask_layout_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::mask_chunk_count",
    );
    <Layout as MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>>::storage_count(
        count, lanes,
    )
}

pub fn native_mask_chunk_count<Profile, Policy, T>(policy: Policy, count: usize) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    mask_layout::Native: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
{
    mask_chunk_count::<Profile, Policy, mask_layout::Native, T>(policy, count)
}

pub fn byte_mask_count<Profile, Policy, T>(policy: Policy, count: usize) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    mask_layout::Bytes: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
{
    mask_chunk_count::<Profile, Policy, mask_layout::Bytes, T>(policy, count)
}

pub fn bit_mask_count<Profile, Policy, T>(policy: Policy, count: usize) -> usize
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    mask_layout::Bits: MaskLayout<Profile, <Policy as VectorFor<Profile, T>>::Vec>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
{
    mask_chunk_count::<Profile, Policy, mask_layout::Bits, T>(policy, count)
}

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_consume_selected_unary}
pub fn consume_selected_unary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    indices: &[usize],
) -> Result<(), crate::PreconditionError>
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile:
        SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0> + SelectedLoad<Simd<T, Scalar>, 0>,
    Op: UnaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryConsumeKernel<Simd<T, Scalar>>,
{
@{check_consume_selected_unary}
    unsafe {
        consume_selected_unary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            input.as_ptr(),
            indices.as_ptr(),
            indices.len(),
        );
    }
    Ok(())
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
pub unsafe fn consume_selected_unary_raw<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: *const T,
    indices: *const usize,
    selected_count: usize,
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile:
        SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0> + SelectedLoad<Simd<T, Scalar>, 0>,
    Op: UnaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryConsumeKernel<Simd<T, Scalar>>,
{
    unsafe {
        consume_selected_unary_scaled_raw::<Profile, 0, Policy, Op, T>(
            policy,
            op,
            input,
            indices,
            selected_count,
        );
    }
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
pub unsafe fn consume_selected_unary_scaled_raw<Profile, const SCALE: u32, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    input: *const T,
    indices: *const usize,
    selected_count: usize,
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>
        + SelectedLoad<Simd<T, Scalar>, SCALE>,
    Op: UnaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryConsumeKernel<Simd<T, Scalar>>,
{
    let lanes = <<Policy as VectorFor<Profile, T>>::Vec as StaticSimdVector>::ELEMENT_COUNT;
    assert!(
        lanes > 0,
        "tsl::algo::consume_selected_unary requires a vector with at least one lane",
    );

    let mut offset = 0usize;
    while offset + lanes <= selected_count {
        let value = unsafe {
            <Profile as SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>>::load_selected(
                input,
                indices.add(offset),
            )
        };
        <Op as UnaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>>::consume(op, value);
        offset += lanes;
    }

    while offset < selected_count {
        let value = unsafe {
            <Profile as SelectedLoad<Simd<T, Scalar>, SCALE>>::load_selected(
                input,
                indices.add(offset),
            )
        };
        <Op as UnaryConsumeKernel<Simd<T, Scalar>>>::consume(op, value);
        offset += 1;
    }
}

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_consume_selected_binary}
pub fn consume_selected_binary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    indices: &[usize],
) -> Result<(), crate::PreconditionError>
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile:
        SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0> + SelectedLoad<Simd<T, Scalar>, 0>,
    Op: BinaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryConsumeKernel<Simd<T, Scalar>>,
{
@{check_consume_selected_binary}
    unsafe {
        consume_selected_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            indices.as_ptr(),
            indices.len(),
        );
    }
    Ok(())
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
pub unsafe fn consume_selected_binary_raw<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    indices: *const usize,
    selected_count: usize,
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile:
        SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0> + SelectedLoad<Simd<T, Scalar>, 0>,
    Op: BinaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryConsumeKernel<Simd<T, Scalar>>,
{
    unsafe {
        consume_selected_binary_scaled_raw::<Profile, 0, Policy, Op, T>(
            policy,
            op,
            left,
            right,
            indices,
            selected_count,
        );
    }
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
pub unsafe fn consume_selected_binary_scaled_raw<Profile, const SCALE: u32, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    indices: *const usize,
    selected_count: usize,
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>
        + SelectedLoad<Simd<T, Scalar>, SCALE>,
    Op: BinaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryConsumeKernel<Simd<T, Scalar>>,
{
    let lanes = <<Policy as VectorFor<Profile, T>>::Vec as StaticSimdVector>::ELEMENT_COUNT;
    assert!(
        lanes > 0,
        "tsl::algo::consume_selected_binary requires a vector with at least one lane",
    );

    let mut offset = 0usize;
    while offset + lanes <= selected_count {
        let left_value = unsafe {
            <Profile as SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>>::load_selected(
                left,
                indices.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>>::load_selected(
                right,
                indices.add(offset),
            )
        };
        <Op as BinaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>>::consume(
            op,
            left_value,
            right_value,
        );
        offset += lanes;
    }

    while offset < selected_count {
        let left_value = unsafe {
            <Profile as SelectedLoad<Simd<T, Scalar>, SCALE>>::load_selected(
                left,
                indices.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as SelectedLoad<Simd<T, Scalar>, SCALE>>::load_selected(
                right,
                indices.add(offset),
            )
        };
        <Op as BinaryConsumeKernel<Simd<T, Scalar>>>::consume(op, left_value, right_value);
        offset += 1;
    }
}

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_aggregate_selected_unary}
pub fn aggregate_selected_unary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    indices: &[usize],
) -> Result<<Op as UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output, crate::PreconditionError>
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile:
        SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0> + SelectedLoad<Simd<T, Scalar>, 0>,
    Op: UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryAggregateKernel<Simd<T, Scalar>>,
{
@{check_aggregate_selected_unary}
    Ok(unsafe {
        aggregate_selected_unary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            input.as_ptr(),
            indices.as_ptr(),
            indices.len(),
        )
        })
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
pub unsafe fn aggregate_selected_unary_raw<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: *const T,
    indices: *const usize,
    selected_count: usize,
) -> <Op as UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile:
        SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0> + SelectedLoad<Simd<T, Scalar>, 0>,
    Op: UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryAggregateKernel<Simd<T, Scalar>>,
{
    unsafe {
        aggregate_selected_unary_scaled_raw::<Profile, 0, Policy, Op, T>(
            policy,
            op,
            input,
            indices,
            selected_count,
        )
    }
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
pub unsafe fn aggregate_selected_unary_scaled_raw<Profile, const SCALE: u32, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    input: *const T,
    indices: *const usize,
    selected_count: usize,
) -> <Op as UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>
        + SelectedLoad<Simd<T, Scalar>, SCALE>,
    Op: UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryAggregateKernel<Simd<T, Scalar>>,
{
    let lanes = <<Policy as VectorFor<Profile, T>>::Vec as StaticSimdVector>::ELEMENT_COUNT;
    assert!(
        lanes > 0,
        "tsl::algo::aggregate_selected_unary requires a vector with at least one lane",
    );

    let mut offset = 0usize;
    while offset + lanes <= selected_count {
        let value = unsafe {
            <Profile as SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>>::load_selected(
                input,
                indices.add(offset),
            )
        };
        <Op as UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::accumulate(op, value);
        offset += lanes;
    }

    while offset < selected_count {
        let value = unsafe {
            <Profile as SelectedLoad<Simd<T, Scalar>, SCALE>>::load_selected(
                input,
                indices.add(offset),
            )
        };
        <Op as UnaryAggregateKernel<Simd<T, Scalar>>>::accumulate(op, value);
        offset += 1;
    }

    <Op as UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::finalize(op)
}

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_aggregate_selected_binary}
pub fn aggregate_selected_binary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    indices: &[usize],
) -> Result<<Op as BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output, crate::PreconditionError>
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile:
        SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0> + SelectedLoad<Simd<T, Scalar>, 0>,
    Op: BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryAggregateKernel<Simd<T, Scalar>>,
{
@{check_aggregate_selected_binary}
    Ok(unsafe {
        aggregate_selected_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            indices.as_ptr(),
            indices.len(),
        )
        })
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
pub unsafe fn aggregate_selected_binary_raw<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    indices: *const usize,
    selected_count: usize,
) -> <Op as BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile:
        SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, 0> + SelectedLoad<Simd<T, Scalar>, 0>,
    Op: BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryAggregateKernel<Simd<T, Scalar>>,
{
    unsafe {
        aggregate_selected_binary_scaled_raw::<Profile, 0, Policy, Op, T>(
            policy,
            op,
            left,
            right,
            indices,
            selected_count,
        )
    }
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
pub unsafe fn aggregate_selected_binary_scaled_raw<Profile, const SCALE: u32, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    indices: *const usize,
    selected_count: usize,
) -> <Op as BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>
        + SelectedLoad<Simd<T, Scalar>, SCALE>,
    Op: BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryAggregateKernel<Simd<T, Scalar>>,
{
    let lanes = <<Policy as VectorFor<Profile, T>>::Vec as StaticSimdVector>::ELEMENT_COUNT;
    assert!(
        lanes > 0,
        "tsl::algo::aggregate_selected_binary requires a vector with at least one lane",
    );

    let mut offset = 0usize;
    while offset + lanes <= selected_count {
        let left_value = unsafe {
            <Profile as SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>>::load_selected(
                left,
                indices.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as SelectedLoad<<Policy as VectorFor<Profile, T>>::Vec, SCALE>>::load_selected(
                right,
                indices.add(offset),
            )
        };
        <Op as BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::accumulate(
            op,
            left_value,
            right_value,
        );
        offset += lanes;
    }

    while offset < selected_count {
        let left_value = unsafe {
            <Profile as SelectedLoad<Simd<T, Scalar>, SCALE>>::load_selected(
                left,
                indices.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as SelectedLoad<Simd<T, Scalar>, SCALE>>::load_selected(
                right,
                indices.add(offset),
            )
        };
        <Op as BinaryAggregateKernel<Simd<T, Scalar>>>::accumulate(op, left_value, right_value);
        offset += 1;
    }

    <Op as BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::finalize(op)
}

@{scaled_checked_algorithm_definitions}

@{unchecked_algorithm_aliases}

pub fn consume_unary<Profile, Policy, Op, T>(policy: Policy, op: &mut Op, input: &[T])
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec> + LoadStore<Simd<T, Scalar>>,
    Op: UnaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryConsumeKernel<Simd<T, Scalar>>,
{
    unsafe {
        consume_unary_raw::<Profile, Policy, Op, T>(policy, op, input.as_ptr(), input.len());
    }
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
pub unsafe fn consume_unary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    input: *const T,
    count: usize,
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec> + LoadStore<Simd<T, Scalar>>,
    Op: UnaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryConsumeKernel<Simd<T, Scalar>>,
{
    let lanes = <<Policy as VectorFor<Profile, T>>::Vec as StaticSimdVector>::ELEMENT_COUNT;
    assert!(
        lanes > 0,
        "tsl::algo::consume_unary requires a vector with at least one lane",
    );

    let mut offset = 0usize;
    while offset + lanes <= count {
        let value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                input.add(offset),
            )
        };
        <Op as UnaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>>::consume(op, value);
        offset += lanes;
    }

    while offset < count {
        let value =
            unsafe { <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(input.add(offset)) };
        <Op as UnaryConsumeKernel<Simd<T, Scalar>>>::consume(op, value);
        offset += 1;
    }
}

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_consume_binary}
pub fn consume_binary_checked<Profile, Policy, Op, T>(policy: Policy, op: &mut Op, left: &[T], right: &[T]) -> Result<(), crate::PreconditionError>
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec> + LoadStore<Simd<T, Scalar>>,
    Op: BinaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryConsumeKernel<Simd<T, Scalar>>,
{
@{check_consume_binary}
    unsafe {
        consume_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            left.len(),
        );
    }
    Ok(())
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
pub unsafe fn consume_binary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    count: usize,
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec> + LoadStore<Simd<T, Scalar>>,
    Op: BinaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryConsumeKernel<Simd<T, Scalar>>,
{
    let lanes = <<Policy as VectorFor<Profile, T>>::Vec as StaticSimdVector>::ELEMENT_COUNT;
    assert!(
        lanes > 0,
        "tsl::algo::consume_binary requires a vector with at least one lane",
    );

    let mut offset = 0usize;
    while offset + lanes <= count {
        let left_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                left.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                right.add(offset),
            )
        };
        <Op as BinaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>>::consume(
            op,
            left_value,
            right_value,
        );
        offset += lanes;
    }

    while offset < count {
        let left_value =
            unsafe { <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(left.add(offset)) };
        let right_value =
            unsafe { <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(right.add(offset)) };
        <Op as BinaryConsumeKernel<Simd<T, Scalar>>>::consume(op, left_value, right_value);
        offset += 1;
    }
}

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_consume_masked_unary}
pub fn consume_masked_unary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    masks: &[<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
) -> Result<(), crate::PreconditionError>
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskFromIntegral<Simd<T, Scalar>>,
    Op: MaskedUnaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskedUnaryConsumeKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
@{check_consume_masked_unary}
    unsafe {
        consume_masked_unary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            input.as_ptr(),
            masks.as_ptr(),
            input.len(),
        );
    }
    Ok(())
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
pub unsafe fn consume_masked_unary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    input: *const T,
    masks: *const <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType,
    count: usize,
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskFromIntegral<Simd<T, Scalar>>,
    Op: MaskedUnaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskedUnaryConsumeKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::consume_masked_unary",
    );

    let mut offset = 0usize;
    let mut chunk = 0usize;
    while offset + lanes <= count {
        let imask = unsafe { masks.add(chunk).read() };
        let active =
            <Profile as MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>>::to_mask(imask);
        let value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                input.add(offset),
            )
        };
        <Op as MaskedUnaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>>::consume(
            op, active, value,
        );
        offset += lanes;
        chunk += 1;
    }

    if offset < count {
        let imask = unsafe { masks.add(chunk).read() };
        let mut lane = 0usize;
        while offset < count {
            let active = scalar_mask_from_bool::<Profile, T>(imask.lane_is_set(lane));
            let value = unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(input.add(offset))
            };
            <Op as MaskedUnaryConsumeKernel<Simd<T, Scalar>>>::consume(op, active, value);
            offset += 1;
            lane += 1;
        }
    }
}

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_consume_masked_binary}
pub fn consume_masked_binary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    masks: &[<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
) -> Result<(), crate::PreconditionError>
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskFromIntegral<Simd<T, Scalar>>,
    Op: MaskedBinaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskedBinaryConsumeKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
@{check_consume_masked_binary}
    unsafe {
        consume_masked_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            masks.as_ptr(),
            left.len(),
        );
    }
    Ok(())
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
pub unsafe fn consume_masked_binary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    masks: *const <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType,
    count: usize,
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskFromIntegral<Simd<T, Scalar>>,
    Op: MaskedBinaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskedBinaryConsumeKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::consume_masked_binary",
    );

    let mut offset = 0usize;
    let mut chunk = 0usize;
    while offset + lanes <= count {
        let imask = unsafe { masks.add(chunk).read() };
        let active =
            <Profile as MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>>::to_mask(imask);
        let left_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                left.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                right.add(offset),
            )
        };
        <Op as MaskedBinaryConsumeKernel<<Policy as VectorFor<Profile, T>>::Vec>>::consume(
            op,
            active,
            left_value,
            right_value,
        );
        offset += lanes;
        chunk += 1;
    }

    if offset < count {
        let imask = unsafe { masks.add(chunk).read() };
        let mut lane = 0usize;
        while offset < count {
            let active = scalar_mask_from_bool::<Profile, T>(imask.lane_is_set(lane));
            let left_value = unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(left.add(offset))
            };
            let right_value = unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(right.add(offset))
            };
            <Op as MaskedBinaryConsumeKernel<Simd<T, Scalar>>>::consume(
                op,
                active,
                left_value,
                right_value,
            );
            offset += 1;
            lane += 1;
        }
    }
}

pub fn aggregate_unary<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
) -> <Op as UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec> + LoadStore<Simd<T, Scalar>>,
    Op: UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryAggregateKernel<Simd<T, Scalar>>,
{
    unsafe {
        aggregate_unary_raw::<Profile, Policy, Op, T>(policy, op, input.as_ptr(), input.len())
    }
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
pub unsafe fn aggregate_unary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    input: *const T,
    count: usize,
) -> <Op as UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec> + LoadStore<Simd<T, Scalar>>,
    Op: UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + UnaryAggregateKernel<Simd<T, Scalar>>,
{
    let lanes = <<Policy as VectorFor<Profile, T>>::Vec as StaticSimdVector>::ELEMENT_COUNT;
    assert!(
        lanes > 0,
        "tsl::algo::aggregate_unary requires a vector with at least one lane",
    );

    let mut offset = 0usize;
    while offset + lanes <= count {
        let value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                input.add(offset),
            )
        };
        <Op as UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::accumulate(op, value);
        offset += lanes;
    }

    while offset < count {
        let value =
            unsafe { <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(input.add(offset)) };
        <Op as UnaryAggregateKernel<Simd<T, Scalar>>>::accumulate(op, value);
        offset += 1;
    }

    <Op as UnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::finalize(op)
}

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_aggregate_binary}
pub fn aggregate_binary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
) -> Result<<Op as BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output, crate::PreconditionError>
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec> + LoadStore<Simd<T, Scalar>>,
    Op: BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryAggregateKernel<Simd<T, Scalar>>,
{
@{check_aggregate_binary}
    Ok(unsafe {
        aggregate_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            left.len(),
        )
        })
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
pub unsafe fn aggregate_binary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    count: usize,
) -> <Op as BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec> + LoadStore<Simd<T, Scalar>>,
    Op: BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + BinaryAggregateKernel<Simd<T, Scalar>>,
{
    let lanes = <<Policy as VectorFor<Profile, T>>::Vec as StaticSimdVector>::ELEMENT_COUNT;
    assert!(
        lanes > 0,
        "tsl::algo::aggregate_binary requires a vector with at least one lane",
    );

    let mut offset = 0usize;
    while offset + lanes <= count {
        let left_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                left.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                right.add(offset),
            )
        };
        <Op as BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::accumulate(
            op,
            left_value,
            right_value,
        );
        offset += lanes;
    }

    while offset < count {
        let left_value =
            unsafe { <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(left.add(offset)) };
        let right_value =
            unsafe { <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(right.add(offset)) };
        <Op as BinaryAggregateKernel<Simd<T, Scalar>>>::accumulate(op, left_value, right_value);
        offset += 1;
    }

    <Op as BinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::finalize(op)
}

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_aggregate_masked_unary}
pub fn aggregate_masked_unary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    input: &[T],
    masks: &[<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
) -> Result<<Op as MaskedUnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output, crate::PreconditionError>
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskFromIntegral<Simd<T, Scalar>>,
    Op: MaskedUnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskedUnaryAggregateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
@{check_aggregate_masked_unary}
    Ok(unsafe {
        aggregate_masked_unary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            input.as_ptr(),
            masks.as_ptr(),
            input.len(),
        )
        })
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
pub unsafe fn aggregate_masked_unary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    input: *const T,
    masks: *const <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType,
    count: usize,
) -> <Op as MaskedUnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskFromIntegral<Simd<T, Scalar>>,
    Op: MaskedUnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskedUnaryAggregateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::aggregate_masked_unary",
    );

    let mut offset = 0usize;
    let mut chunk = 0usize;
    while offset + lanes <= count {
        let imask = unsafe { masks.add(chunk).read() };
        let active =
            <Profile as MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>>::to_mask(imask);
        let value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                input.add(offset),
            )
        };
        <Op as MaskedUnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::accumulate(
            op, active, value,
        );
        offset += lanes;
        chunk += 1;
    }

    if offset < count {
        let imask = unsafe { masks.add(chunk).read() };
        let mut lane = 0usize;
        while offset < count {
            let active = scalar_mask_from_bool::<Profile, T>(imask.lane_is_set(lane));
            let value = unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(input.add(offset))
            };
            <Op as MaskedUnaryAggregateKernel<Simd<T, Scalar>>>::accumulate(op, active, value);
            offset += 1;
            lane += 1;
        }
    }

    <Op as MaskedUnaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::finalize(op)
}

/// Checked slice form. Every cross-range precondition is validated before dispatch.
/// Longer related ranges are accepted and their suffixes remain untouched.
@{docs_aggregate_masked_binary}
pub fn aggregate_masked_binary_checked<Profile, Policy, Op, T>(
    policy: Policy,
    op: &mut Op,
    left: &[T],
    right: &[T],
    masks: &[<<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType],
) -> Result<<Op as MaskedBinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output, crate::PreconditionError>
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskFromIntegral<Simd<T, Scalar>>,
    Op: MaskedBinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskedBinaryAggregateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
@{check_aggregate_masked_binary}
    Ok(unsafe {
        aggregate_masked_binary_raw::<Profile, Policy, Op, T>(
            policy,
            op,
            left.as_ptr(),
            right.as_ptr(),
            masks.as_ptr(),
            left.len(),
        )
        })
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
pub unsafe fn aggregate_masked_binary_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    left: *const T,
    right: *const T,
    masks: *const <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType,
    count: usize,
) -> <Op as MaskedBinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::Output
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Profile: LoadStore<<Policy as VectorFor<Profile, T>>::Vec>
        + LoadStore<Simd<T, Scalar>>
        + MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskFromIntegral<Simd<T, Scalar>>,
    Op: MaskedBinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>
        + MaskedBinaryAggregateKernel<Simd<T, Scalar>>,
    <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::ImaskType: IntegralMaskWord,
    <Simd<T, Scalar> as SimdVector>::ImaskType: IntegralMaskWord,
{
    let lanes = validate_integral_mask_vector::<<Policy as VectorFor<Profile, T>>::Vec>(
        "tsl::algo::aggregate_masked_binary",
    );

    let mut offset = 0usize;
    let mut chunk = 0usize;
    while offset + lanes <= count {
        let imask = unsafe { masks.add(chunk).read() };
        let active =
            <Profile as MaskFromIntegral<<Policy as VectorFor<Profile, T>>::Vec>>::to_mask(imask);
        let left_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                left.add(offset),
            )
        };
        let right_value = unsafe {
            <Profile as LoadStore<<Policy as VectorFor<Profile, T>>::Vec>>::load_unaligned(
                right.add(offset),
            )
        };
        <Op as MaskedBinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::accumulate(
            op,
            active,
            left_value,
            right_value,
        );
        offset += lanes;
        chunk += 1;
    }

    if offset < count {
        let imask = unsafe { masks.add(chunk).read() };
        let mut lane = 0usize;
        while offset < count {
            let active = scalar_mask_from_bool::<Profile, T>(imask.lane_is_set(lane));
            let left_value = unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(left.add(offset))
            };
            let right_value = unsafe {
                <Profile as LoadStore<Simd<T, Scalar>>>::load_unaligned(right.add(offset))
            };
            <Op as MaskedBinaryAggregateKernel<Simd<T, Scalar>>>::accumulate(
                op,
                active,
                left_value,
                right_value,
            );
            offset += 1;
            lane += 1;
        }
    }

    <Op as MaskedBinaryAggregateKernel<<Policy as VectorFor<Profile, T>>::Vec>>::finalize(op)
}
