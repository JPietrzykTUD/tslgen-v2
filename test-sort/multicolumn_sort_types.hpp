#pragma once

#include <cstddef>


enum class TslSortOrder { ASCENDING, DESCENDING };
enum class TslRunDiscoveryKind { POST_SORT, INCREMENTAL };

template <class DataType>
struct TslSortColumn {
  DataType * data;
  TslSortOrder order;
};

struct TslRunSpan {
  std::size_t begin;
  std::size_t end;
};

struct TslColumnSortTask {
  std::size_t column;
  std::size_t begin;
  std::size_t end;
};

struct TslMultiColumnSortMetrics {
  std::size_t rle_values_scanned = 0;
  std::size_t direct_equal_bands = 0;
  std::size_t direct_equal_band_rows = 0;
  std::size_t tasks_submitted = 0;
  std::size_t tasks_executed_inline = 0;
  std::size_t max_outstanding_tasks = 0;
};
