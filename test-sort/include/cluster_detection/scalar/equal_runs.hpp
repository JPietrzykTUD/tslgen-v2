#pragma once

#include <cstddef>
#include <utility>

#include "sorting/common/multicolumn_sort_types.hpp"


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

// The scalar backend in the shape every detector shares:
// `operator()(values, begin, end, emit)`. This is what an accelerator backend is
// compared against, and what a driver defaults to. Named for history rather than
// for the index sort -- it is not specific to it, and both the indirect quicksort
// and the multi-column samplesort take it.
template <class DataType>
struct TslIndexScalarDetector {
  template <class Emit>
  void operator()(DataType const * values, std::size_t begin, std::size_t end,
                  Emit && emit) {
    tsl_for_each_equal_run(values, begin, end, std::forward<Emit>(emit));
  }
};
