pub(super) fn chunk_count_for_lanes(count: usize, lanes: usize) -> usize {
    count.div_ceil(lanes)
}

pub(crate) fn selected_row_scale<T, const SCALE: u32>() -> usize {
    let scale = if SCALE == 0 {
        core::mem::size_of::<T>()
    } else {
        SCALE as usize
    };
    assert!(scale > 0, "tsl::algo selected-row scale must be nonzero");
    scale
}

pub(crate) fn selected_row_pointer<T, const SCALE: u32>(input: *const T, index: usize) -> *const T {
    let byte_offset = index.wrapping_mul(selected_row_scale::<T, SCALE>());
    (input as *const u8).wrapping_add(byte_offset) as *const T
}

pub(super) fn selected_address_error<T, const SCALE: u32>(
    input: &[T],
    indices: &[usize],
) -> Option<crate::PreconditionError> {
    let scale = if SCALE == 0 {
        core::mem::size_of::<T>()
    } else {
        SCALE as usize
    };
    let Some(input_bytes) = input.len().checked_mul(core::mem::size_of::<T>()) else {
        return Some(crate::PreconditionError::AddressOverflow);
    };
    for &index in indices {
        let Some(offset) = index.checked_mul(scale) else {
            return Some(crate::PreconditionError::AddressOverflow);
        };
        if !offset.is_multiple_of(core::mem::align_of::<T>()) {
            return Some(crate::PreconditionError::Misaligned);
        }
        if offset > input_bytes
            || core::mem::size_of::<T>() > input_bytes.saturating_sub(offset)
        {
            return Some(crate::PreconditionError::IndexOutOfBounds);
        }
    }
    None
}
