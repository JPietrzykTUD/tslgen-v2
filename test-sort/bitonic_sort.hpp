#pragma once
#include <immintrin.h>

#include <algorithm>
#include <array>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <random>
#include <span>
#include <vector>

namespace avx512_sort {

constexpr std::size_t lanes_per_vector = 16;
constexpr std::size_t vector_count     = 16;
constexpr std::size_t network_size     = lanes_per_vector * vector_count;

// -----------------------------------------------------------------------------
// Sortiert bis zu 256 uint32_t.
//
// Voraussetzung:
//   - CPU unterstützt AVX-512F
//   - count <= 256
//
// Unbenutzte Positionen werden mit UINT32_MAX aufgefüllt und wandern dadurch
// beim aufsteigenden Sortieren ans Ende.
// -----------------------------------------------------------------------------
[[gnu::target("avx512f")]]
void sort_u32_up_to_256(std::uint32_t* data, std::size_t count) {
    assert(data != nullptr || count == 0);
    assert(count <= network_size);

    if (count <= 1) {
        return;
    }

    alignas(64) std::array<std::uint32_t, network_size> buffer;
    std::fill(buffer.begin(), buffer.end(),
              std::numeric_limits<std::uint32_t>::max());
    std::copy_n(data, count, buffer.data());

    std::array<__m512i, vector_count> rows{};

    for (std::size_t row = 0; row < vector_count; ++row) {
        rows[row] = _mm512_load_si512(
            buffer.data() + row * lanes_per_vector);
    }

    /*
     * Klassisches Bitonic-Sortiernetz für 256 Elemente.
     *
     * k ist die aktuelle Größe einer bitonisch sortierten Gruppe:
     *
     *   2, 4, 8, 16, 32, ..., 256
     *
     * j ist die Distanz zwischen Comparator-Partnern:
     *
     *   k/2, k/4, ..., 1
     *
     * Der Partner eines globalen Elements i lautet:
     *
     *   partner = i XOR j
     *
     * Für j < 16 liegt der Partner im selben Register.
     * Für j >= 16 liegt der Partner in einem anderen Register, aber
     * in derselben Lane.
     */
    for (std::size_t k = 2; k <= network_size; k <<= 1) {
        for (std::size_t j = k >> 1; j != 0; j >>= 1) {
            if (j < lanes_per_vector) {
                // -------------------------------------------------------------
                // Comparator-Partner liegen im selben SIMD-Register.
                // -------------------------------------------------------------

                alignas(64) std::array<std::uint32_t, lanes_per_vector>
                    permutation_indices{};

                for (std::size_t lane = 0;
                     lane < lanes_per_vector;
                     ++lane) {
                    permutation_indices[lane] =
                        static_cast<std::uint32_t>(lane ^ j);
                }

                const __m512i permutation =
                    _mm512_load_si512(permutation_indices.data());

                for (std::size_t row = 0; row < vector_count; ++row) {
                    const __m512i value = rows[row];

                    const __m512i partner =
                        _mm512_permutexvar_epi32(permutation, value);

                    const __m512i minimum =
                        _mm512_min_epu32(value, partner);

                    const __m512i maximum =
                        _mm512_max_epu32(value, partner);

                    /*
                     * Für jede Lane bestimmen wir, ob diese Position das
                     * Minimum oder Maximum des Comparator-Paars erhält.
                     *
                     * ascending:
                     *   global_index & k == 0
                     *
                     * lower_endpoint:
                     *   global_index & j == 0
                     *
                     * Aufsteigend:
                     *   lower endpoint <- min
                     *   upper endpoint <- max
                     *
                     * Absteigend:
                     *   lower endpoint <- max
                     *   upper endpoint <- min
                     */
                    __mmask16 take_max_mask = 0;

                    for (std::size_t lane = 0;
                         lane < lanes_per_vector;
                         ++lane) {
                        const std::size_t global_index =
                            row * lanes_per_vector + lane;

                        const bool ascending =
                            (global_index & k) == 0;

                        const bool lower_endpoint =
                            (global_index & j) == 0;

                        const bool take_max =
                            ascending
                                ? !lower_endpoint
                                : lower_endpoint;

                        if (take_max) {
                            take_max_mask |=
                                static_cast<__mmask16>(1u << lane);
                        }
                    }

                    rows[row] = _mm512_mask_blend_epi32(
                        take_max_mask,
                        minimum,
                        maximum);
                }
            } else {
                // -------------------------------------------------------------
                // Comparator-Partner liegen in unterschiedlichen Registern.
                //
                // Da j ein Vielfaches von 16 ist, bleiben die Lane-Indizes
                // unverändert. Nur die Registerzeile ändert sich.
                // -------------------------------------------------------------
                const std::size_t row_distance =
                    j / lanes_per_vector;

                for (std::size_t row = 0;
                     row < vector_count;
                     ++row) {
                    const std::size_t partner_row =
                        row ^ row_distance;

                    // Jedes Registerpaar nur einmal bearbeiten.
                    if (row >= partner_row) {
                        continue;
                    }

                    const __m512i a = rows[row];
                    const __m512i b = rows[partner_row];

                    const __m512i minimum =
                        _mm512_min_epu32(a, b);

                    const __m512i maximum =
                        _mm512_max_epu32(a, b);

                    /*
                     * Für j >= 16 ist die Richtung innerhalb eines Registers
                     * für alle Lanes gleich, weil k ebenfalls mindestens 32
                     * beträgt.
                     */
                    const std::size_t first_global_index =
                        row * lanes_per_vector;

                    const bool ascending =
                        (first_global_index & k) == 0;

                    /*
                     * row < partner_row ist der global kleinere Endpunkt des
                     * Comparator-Paars.
                     */
                    if (ascending) {
                        rows[row]         = minimum;
                        rows[partner_row] = maximum;
                    } else {
                        rows[row]         = maximum;
                        rows[partner_row] = minimum;
                    }
                }
            }
        }
    }

    for (std::size_t row = 0; row < vector_count; ++row) {
        _mm512_store_si512(
            buffer.data() + row * lanes_per_vector,
            rows[row]);
    }

    std::copy_n(buffer.data(), count, data);
}

} // namespace avx512_sort