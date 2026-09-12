use super::*;

pub fn for_each_chunk<Profile, Policy, Op, T>(policy: Policy, op: &mut Op, data: &[T])
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Op: ChunkKernel<<Policy as VectorFor<Profile, T>>::Vec> + ChunkKernel<Simd<T, Scalar>>,
{
    unsafe {
        for_each_chunk_raw::<Profile, Policy, Op, T>(policy, op, data.as_ptr(), data.len());
    }
}

/// # Safety
///
/// Every raw pointer must be properly aligned and valid for every read or write
/// implied by the length arguments and selected policy. Writable regions must not
/// alias any region read during the call.
pub unsafe fn for_each_chunk_raw<Profile, Policy, Op, T>(
    _policy: Policy,
    op: &mut Op,
    data: *const T,
    count: usize,
) where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec: StaticSimdVector<BaseType = T>,
    Simd<T, Scalar>: StaticSimdVector<BaseType = T>,
    Op: ChunkKernel<<Policy as VectorFor<Profile, T>>::Vec> + ChunkKernel<Simd<T, Scalar>>,
{
    let lanes = <<Policy as VectorFor<Profile, T>>::Vec as StaticSimdVector>::ELEMENT_COUNT;
    assert!(
        lanes > 0,
        "tsl::algo::for_each_chunk requires a vector with at least one lane",
    );

    let mut offset = 0usize;
    while offset + lanes <= count {
        unsafe {
            <Op as ChunkKernel<<Policy as VectorFor<Profile, T>>::Vec>>::apply(
                op,
                data.add(offset),
                offset,
                lanes,
            );
        }
        offset += lanes;
    }

    while offset < count {
        unsafe {
            <Op as ChunkKernel<Simd<T, Scalar>>>::apply(op, data.add(offset), offset, 1);
        }
        offset += 1;
    }
}
