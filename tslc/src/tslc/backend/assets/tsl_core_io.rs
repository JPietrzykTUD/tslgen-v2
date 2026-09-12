// Text formatting runtime for the tsl_core facade.

use super::ArrayStorage;

/// A lane value reduced to its 64-bit pattern for `to_ostream` formatting (`self as u64`,
/// matching the C++ `static_cast<std::uint64_t>`). Implemented for every base, incl. floats.
pub trait TslBits: Copy {
    fn tsl_as_u64(self) -> u64;
}
macro_rules! impl_tsl_bits {
    ($($t:ty),*) => { $(impl TslBits for $t {
        #[inline]
        fn tsl_as_u64(self) -> u64 {
            self as u64
        }
    })* };
}
impl_tsl_bits!(i8, i16, i32, i64, u8, u16, u32, u64, f32, f64);

/// Format a lane array into a text buffer (the `to_ostream` body). `modifier` selects the base
/// (0 = binary, 16 = hex, 8 = octal, else decimal); the C++ `tsl::ostream_write` counterpart.
pub fn ostream_write<T: TslBits, const N: usize>(
    out: &mut alloc::string::String,
    arr: &ArrayStorage<T, N>,
    modifier: i32,
) {
    let bits = core::mem::size_of::<T>() * 8;
    let base: u64 = match modifier {
        16 => 16,
        8 => 8,
        0 => 2,
        _ => 10,
    };
    for lane in 0..N {
        let value = arr[N - 1 - lane].tsl_as_u64();
        let masked = if bits >= 64 { value } else { value & ((1u64 << bits) - 1) };
        if base == 2 {
            for b in (0..bits).rev() {
                out.push(if (masked >> b) & 1 == 1 { '1' } else { '0' });
            }
        } else {
            let mut digits = [0u8; 64];
            let mut count = 0usize;
            let mut remaining = masked;
            if remaining == 0 {
                digits[count] = b'0';
                count += 1;
            }
            while remaining > 0 {
                let digit = (remaining % base) as u32;
                digits[count] = char::from_digit(digit, base as u32).unwrap() as u8;
                count += 1;
                remaining /= base;
            }
            while count > 0 {
                count -= 1;
                out.push(digits[count] as char);
            }
        }
        out.push('|');
    }
    out.push('\n');
}
