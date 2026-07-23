#pragma once

#include <cstddef>

#include "multicolumn_sort_types.hpp"


template <class DataType, class Emit>
void tsl_for_each_equal_run(
  DataType const * values,
  std::size_t begin,
  std::size_t end,
  Emit && emit
) {
  if (end - begin < 2) {
    return;
  }

  auto run_begin = begin;
  for (auto index = begin + 1; index < end; ++index) {
    if (values[index] == values[index - 1]) {
      continue;
    }
    if (index - run_begin > 1) {
      emit(TslRunSpan{run_begin, index});
    }
    run_begin = index;
  }
  if (end - run_begin > 1) {
    emit(TslRunSpan{run_begin, end});
  }
}
