#pragma once

/**
 * @@file
 * Public unchecked data-parallel algorithms.
 *
 * Pointer/count overloads require every pointer to denote its complete live
 * range. Range overloads take their driving count from the first input and
 * require every secondary input, mask, index, and output to cover the related
 * extent. Explicit `assume_*` alignment policies are caller promises. Output
 * ranges must obey the alias rules documented by the corresponding
 * `*_checked` family. These functions perform no hidden validation; use the
 * checked range overload when the complete runtime contract is representable.
 */

@{algorithm_family_includes}
