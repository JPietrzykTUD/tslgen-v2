// Pointer, indexed-address, byte-copy, and allocation runtime for tsl_core.

use super::PreconditionError;

pub fn ptr_add<T>(p: *const T, i: usize) -> *const T {
    p.wrapping_add(i)
}
pub fn ptr_add_mut<T>(p: *mut T, i: usize) -> *mut T {
    p.wrapping_add(i)
}
/// A value usable as a gather/scatter index or scale — an integer lane that converts to a byte
/// offset. Implemented for the integer bases only (floats can't index memory), so a free
/// `IndicesType: IndexVector` guarantees its lanes are valid indices.
pub trait IndexBase: Copy {
    fn as_offset(self) -> usize;
    fn checked_byte_offset(self, scale: usize) -> Result<usize, PreconditionError>;
}

macro_rules! impl_signed_index_base {
    ($($t:ty),*) => { $(impl IndexBase for $t {
        fn as_offset(self) -> usize { self as usize }
        fn checked_byte_offset(self, scale: usize) -> Result<usize, PreconditionError> {
            if self < 0 {
                return Err(PreconditionError::IndexOutOfBounds);
            }
            let index = self as u128;
            if index > usize::MAX as u128 {
                return Err(PreconditionError::AddressOverflow);
            }
            (index as usize)
                .checked_mul(scale)
                .ok_or(PreconditionError::AddressOverflow)
        }
    })* };
}

macro_rules! impl_unsigned_index_base {
    ($($t:ty),*) => { $(impl IndexBase for $t {
        fn as_offset(self) -> usize { self as usize }
        fn checked_byte_offset(self, scale: usize) -> Result<usize, PreconditionError> {
            let index = self as u128;
            if index > usize::MAX as u128 {
                return Err(PreconditionError::AddressOverflow);
            }
            (index as usize)
                .checked_mul(scale)
                .ok_or(PreconditionError::AddressOverflow)
        }
    })* };
}
impl_signed_index_base!(i8, i16, i32, i64, isize);
impl_unsigned_index_base!(u8, u16, u32, u64, usize);

#[inline]
pub(crate) fn indexed_memory_address_error<I: IndexBase, T>(
    index: I,
    scale: u32,
    extent: usize,
) -> Option<PreconditionError> {
    let bytes = match extent.checked_mul(core::mem::size_of::<T>()) {
        Some(bytes) => bytes,
        None => return Some(PreconditionError::AddressOverflow),
    };
    let offset = match index.checked_byte_offset(scale as usize) {
        Ok(offset) => offset,
        Err(error) => return Some(error),
    };
    if offset % core::mem::align_of::<T>() != 0 {
        return Some(PreconditionError::Misaligned);
    }
    if offset > bytes || core::mem::size_of::<T>() > bytes - offset {
        return Some(PreconditionError::IndexOutOfBounds);
    }
    None
}

/// The byte offset of a gather/scatter index: `index * scale` (scale in {1,2,4,8}). Used by the
/// fallback loops over a byte-reinterpreted base pointer.
pub fn idx_offset<I: IndexBase, S: IndexBase>(index: I, scale: S) -> usize {
    index.as_offset() * scale.as_offset()
}

/// A `mem<copy>` byte-count argument. This accepts the corpus' legacy base-typed counts and
/// the explicit `scalar::size`/`usize` form, normalizing either to the byte count consumed by
/// `copy_nonoverlapping`.
pub trait TslByteCount: Copy {
    fn tsl_byte_count(self) -> usize;
}
macro_rules! impl_tsl_byte_count {
    ($($t:ty),*) => { $(impl TslByteCount for $t {
        #[inline]
        fn tsl_byte_count(self) -> usize {
            self as usize
        }
    })* };
}
impl_tsl_byte_count!(i8, i16, i32, i64, u8, u16, u32, u64, f32, f64, usize);

/// `std::memcpy` counterpart: copy `count` bytes from `src` to `dst`. Byte-addressed
/// (`*const u8`/`*mut u8`), so a `void`-cast source/dest plus a base-typed byte count lower
/// identically to the C++ `mem_copy` translate template.
///
/// # Safety
///
/// `src` and `dst` must be valid for `count` bytes and must not overlap.
#[inline]
pub unsafe fn mem_copy<C: TslByteCount>(dst: *mut u8, src: *const u8, count: C) {
    core::ptr::copy_nonoverlapping(src, dst, count.tsl_byte_count());
}

// The C allocator, declared directly (no `libc` crate dependency): every Rust `std` binary
// links the C runtime, so these symbols resolve. Using malloc/aligned_alloc/free here — rather
// than Rust's `Layout`-based global allocator — lets `deallocate(ptr)` free with only the
// pointer (the C contract), and mirrors the C++ `std::malloc`/`std::aligned_alloc`/`std::free`
// lowering exactly. Alloc and free MUST share an allocator, so all three go through libc.
extern "C" {
    fn malloc(size: usize) -> *mut core::ffi::c_void;
    fn aligned_alloc(alignment: usize, size: usize) -> *mut core::ffi::c_void;
    fn free(ptr: *mut core::ffi::c_void);
}

/// `std::malloc` counterpart for the `allocate` free function: a `count_bytes` block as an
/// untyped pointer. Zero-size requests and allocation failures return null.
///
/// # Safety
///
/// The returned pointer must be released exactly once with [`mem_free`] and
/// must not be dereferenced beyond the allocated byte count.
#[inline]
pub unsafe fn mem_alloc(count_bytes: usize) -> *mut core::ffi::c_void {
    if count_bytes == 0 {
        return core::ptr::null_mut();
    }
    malloc(count_bytes)
}

/// `std::aligned_alloc` counterpart for `allocate_aligned`. Argument order mirrors the
/// translate template (`alignment` then `count_bytes`). The requested size is rounded up for
/// C runtimes whose `aligned_alloc` requires a multiple of the effective alignment. Zero-size
/// requests, non-power-of-two alignments, overflow, and allocation failures return null.
///
/// # Safety
///
/// A non-null returned pointer must be released exactly once with [`mem_free`].
#[inline]
pub unsafe fn mem_alloc_aligned(alignment: usize, count_bytes: usize) -> *mut core::ffi::c_void {
    if count_bytes == 0 || !alignment.is_power_of_two() {
        return core::ptr::null_mut();
    }
    let minimum_alignment = core::mem::align_of::<*mut core::ffi::c_void>();
    let effective_alignment = core::cmp::max(alignment, minimum_alignment);
    let allocation_size = match count_bytes
        .checked_add(effective_alignment - 1)
        .map(|size| (size / effective_alignment) * effective_alignment)
    {
        Some(size) => size,
        None => return core::ptr::null_mut(),
    };
    aligned_alloc(effective_alignment, allocation_size)
}

/// `std::free` counterpart for `deallocate`: frees a malloc/aligned_alloc block by pointer
/// alone, so no `Layout` reconstruction is needed. (`free` reclaims `aligned_alloc` memory on
/// conforming platforms.)
///
/// # Safety
///
/// `ptr` must be null or a live pointer returned by [`mem_alloc`] or
/// [`mem_alloc_aligned`], and it must not be used after this call.
#[inline]
pub unsafe fn mem_free(ptr: *mut core::ffi::c_void) {
    free(ptr);
}
