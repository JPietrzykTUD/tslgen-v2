// Text-formatting runtime support for the stable `tsl_core.hpp` facade.
#pragma once

#include "tsl_core_detail_types.hpp"

#include <cstdint>
#include <string>

namespace tsl {

// Format a lane array into a text buffer (the `to_ostream` body). `modifier` selects the base
// (0 = binary, 16 = hex, 8 = octal, else decimal); each lane is cast to a 64-bit pattern and its
// low `sizeof(T)*8` bits are emitted, high lane first, '|'-separated, with a trailing newline.
template <class T, std::size_t N, std::size_t Align>
inline void ostream_write(std::string &out, const array_type<T, N, Align> &arr, int modifier) {
    constexpr std::size_t bits = sizeof(T) * 8;
    const unsigned base =
        (modifier == 16) ? 16u : (modifier == 8) ? 8u : (modifier == 0) ? 2u : 10u;
    for (std::size_t lane = 0; lane < N; ++lane) {
        std::uint64_t value = static_cast<std::uint64_t>(arr[N - 1 - lane]);
        std::uint64_t masked = value;
        if constexpr (bits < 64) {
            masked &= (std::uint64_t{1} << bits) - 1;
        }
        if (base == 2u) {
            for (std::size_t b = bits; b-- > 0;) {
                out += ((masked >> b) & 1u) ? '1' : '0';
            }
        } else {
            char buf[88];
            std::size_t p = 0;
            if (masked == 0) {
                buf[p++] = '0';
            }
            while (masked) {
                unsigned d = static_cast<unsigned>(masked % base);
                buf[p++] = (d < 10) ? char('0' + d) : char('a' + d - 10);
                masked /= base;
            }
            while (p) {
                out += buf[--p];
            }
        }
        out += '|';
    }
    out += '\n';
}

}  // namespace tsl
