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
