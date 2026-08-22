cmake_minimum_required(VERSION 3.20)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON CACHE BOOL "Export compile_commands.json")
project(tsl_release_fetch_content_sort LANGUAGES CXX)

# Binaries that read the `rle=` backend registry and so gain the accelerator
# backends wherever a build has them.
set(TSL_COSORT_RLE_CONSUMERS cosort_bench bench_samplesort_multicolumn
    bench_q3_detection)


if(NOT CMAKE_CONFIGURATION_TYPES AND NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE "Release" CACHE STRING "Build type" FORCE)
  set_property(CACHE CMAKE_BUILD_TYPE PROPERTY STRINGS "Debug" "Release" "RelWithDebInfo" "MinSizeRel")
endif()

if(POLICY CMP0135)
  cmake_policy(SET CMP0135 NEW)
endif()

include(CTest)
include(FetchContent)
find_package(Threads REQUIRED)

set(
  TSL_LOCAL_SOURCE_DIR
  ""
  CACHE PATH
  "Path to a local generated TSL output root, or to its cpp directory"
)
set(TSL_RELEASE_VERSION "v0.2.9" CACHE STRING "Generated TSL release tag")
set(
  TSL_RELEASE_ARCHIVE_URL
  # "https://github.com/JPietrzykTUD/tslgen-v2/releases/download/${TSL_RELEASE_VERSION}/tsl-generated-1daeecdd39aa2b02a1bb60697d67fe6ae70b23cc.tar.gz"
  "https://github.com/JPietrzykTUD/tslgen-v2/releases/download/${TSL_RELEASE_VERSION}/tsl-generated-${TSL_RELEASE_VERSION}.tar.gz"
  CACHE STRING
  "URL of the generated TSL release archive"
)
set(TSL_PROFILE "auto" CACHE STRING "Generated TSL profile consumed by this test")
set(TSL_BUILD_TESTS OFF CACHE BOOL "Build TSL tests")


option(ENABLE_VQSORT_BENCHMARK "Include Google Highway VQSort in the benchmark" ON)
set(
  HIGHWAY_LOCAL_SOURCE_DIR
  ""
  CACHE PATH
  "Path to a local Google Highway source checkout"
)
set(HIGHWAY_RELEASE_VERSION "1.4.0" CACHE STRING "Google Highway release tag")
set(
  HIGHWAY_RELEASE_ARCHIVE_URL
  "https://github.com/google/highway/archive/refs/tags/${HIGHWAY_RELEASE_VERSION}.tar.gz"
  CACHE STRING
  "URL of the Google Highway release archive"
)
set(
  HIGHWAY_RELEASE_ARCHIVE_SHA256
  ""
  CACHE STRING
  "Optional SHA256 digest for the Google Highway release archive"
)

if(ENABLE_VQSORT_BENCHMARK AND (NOT DEFINED CMAKE_C_COMPILER OR CMAKE_C_COMPILER STREQUAL ""))
  set(_highway_c_compiler_candidates)
  if(CMAKE_CXX_COMPILER)
    get_filename_component(_highway_cxx_compiler_dir "${CMAKE_CXX_COMPILER}" DIRECTORY)
    list(APPEND _highway_c_compiler_candidates "${_highway_cxx_compiler_dir}/cc")
    list(APPEND _highway_c_compiler_candidates "${_highway_cxx_compiler_dir}/gcc")
  endif()
  list(APPEND _highway_c_compiler_candidates cc gcc)

  foreach(_highway_c_compiler_candidate IN LISTS _highway_c_compiler_candidates)
    if(IS_ABSOLUTE "${_highway_c_compiler_candidate}" AND EXISTS "${_highway_c_compiler_candidate}")
      set(_highway_c_compiler "${_highway_c_compiler_candidate}")
      break()
    endif()

    find_program(_highway_found_c_compiler NAMES "${_highway_c_compiler_candidate}")
    if(_highway_found_c_compiler)
      set(_highway_c_compiler "${_highway_found_c_compiler}")
      break()
    endif()
  endforeach()

  if(_highway_c_compiler)
    set(CMAKE_C_COMPILER "${_highway_c_compiler}" CACHE FILEPATH "C compiler used by Google Highway")
  endif()
endif()

if(TSL_LOCAL_SOURCE_DIR)
  get_filename_component(
    _tsl_local_source_dir
    "${TSL_LOCAL_SOURCE_DIR}"
    ABSOLUTE
    BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}"
  )
  if(EXISTS "${_tsl_local_source_dir}/CMakeLists.txt")
    set(_tsl_local_cpp_dir "${_tsl_local_source_dir}")
  elseif(EXISTS "${_tsl_local_source_dir}/cpp/CMakeLists.txt")
    set(_tsl_local_cpp_dir "${_tsl_local_source_dir}/cpp")
  else()
    message(
      FATAL_ERROR
      "TSL_LOCAL_SOURCE_DIR must point to a generated TSL root or cpp directory"
    )
  endif()
  message(STATUS "Using local generated TSL from ${_tsl_local_cpp_dir}")
  add_subdirectory(
    "${_tsl_local_cpp_dir}"
    "${CMAKE_CURRENT_BINARY_DIR}/_deps/tsl-local-build"
    EXCLUDE_FROM_ALL
  )
else()
  set(_tsl_release_hash_args)
  FetchContent_Declare(
      tsl
      URL "${TSL_RELEASE_ARCHIVE_URL}"
      SOURCE_SUBDIR cpp
      ${_tsl_release_hash_args}
  )
  FetchContent_MakeAvailable(tsl)
endif()


if(ENABLE_VQSORT_BENCHMARK)
  set(HWY_ENABLE_CONTRIB ON CACHE BOOL "" FORCE)
  set(HWY_ENABLE_TESTS OFF CACHE BOOL "" FORCE)
  set(HWY_ENABLE_EXAMPLES OFF CACHE BOOL "" FORCE)
  set(HWY_ENABLE_INSTALL OFF CACHE BOOL "" FORCE)
  set(HWY_ENABLE_LIST_TARGETS OFF CACHE BOOL "" FORCE)
  set(HWY_FORCE_STATIC_LIBS ON CACHE BOOL "" FORCE)

  if(HIGHWAY_LOCAL_SOURCE_DIR)
    get_filename_component(
      _highway_local_source_dir
      "${HIGHWAY_LOCAL_SOURCE_DIR}"
      ABSOLUTE
      BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}"
    )
    if(NOT EXISTS "${_highway_local_source_dir}/CMakeLists.txt")
      message(FATAL_ERROR "HIGHWAY_LOCAL_SOURCE_DIR must point to a Google Highway source root")
    endif()

    message(STATUS "Using local Google Highway from ${_highway_local_source_dir}")
    add_subdirectory(
      "${_highway_local_source_dir}"
      "${CMAKE_CURRENT_BINARY_DIR}/_deps/highway-local-build"
      EXCLUDE_FROM_ALL
    )
  else()
    set(_highway_release_hash_args)
    if(HIGHWAY_RELEASE_ARCHIVE_SHA256)
      list(APPEND _highway_release_hash_args URL_HASH "SHA256=${HIGHWAY_RELEASE_ARCHIVE_SHA256}")
    endif()

    FetchContent_Declare(
      highway
      URL "${HIGHWAY_RELEASE_ARCHIVE_URL}"
      ${_highway_release_hash_args}
    )
    FetchContent_MakeAvailable(highway)
  endif()

  if(NOT TARGET hwy_contrib)
    message(FATAL_ERROR "ENABLE_VQSORT_BENCHMARK requires the Google Highway hwy_contrib target")
  endif()
endif()

add_executable(test_sort tests/test_quicksort_pairwise_swap.cpp)
target_compile_features(test_sort PRIVATE cxx_std_17)
target_link_libraries(test_sort PRIVATE tsl::tsl)

add_executable(test_multicolumn_sort tests/test_multicolumn_sort.cpp)
target_compile_features(test_multicolumn_sort PRIVATE cxx_std_17)
target_link_libraries(test_multicolumn_sort PRIVATE tsl::tsl Threads::Threads)

# Hybrid-leaf experiment: is the leaf a per-leaf decision rather than a
# per-configuration one? Standalone driver plus its own sweep; see
# multicolumn_qs_hybrid_leaf.hpp and benchmark-final.md.
add_executable(bench_hybrid_leaf benchmarks/bench_hybrid_leaf.cpp)
target_compile_features(bench_hybrid_leaf PRIVATE cxx_std_17)
target_link_libraries(bench_hybrid_leaf PRIVATE tsl::tsl Threads::Threads)

# Samplesort co-sort: a different algorithm for the same data model as the
# indirect sorter -- sort a key column, carry an index column, materialise the
# rest with one gather pass each. Kernels in samplesort_cosort.hpp, the
# swappable sequential executor in samplesort_executor.hpp, measurements in
# samplesort-notes.md.
# The paper's systematic drivers: one question per binary, one CSV schema, the
# method fixed once in benchmarks/paper_harness.hpp. See docs/benchmark-plan.md.
add_executable(bench_q4_scaling benchmarks/bench_q4_scaling.cpp)
target_compile_features(bench_q4_scaling PRIVATE cxx_std_17)
target_link_libraries(bench_q4_scaling PRIVATE tsl::tsl Threads::Threads)

add_executable(bench_q3_detection benchmarks/bench_q3_detection.cpp)
target_compile_features(bench_q3_detection PRIVATE cxx_std_17)
target_link_libraries(bench_q3_detection PRIVATE tsl::tsl Threads::Threads)

add_executable(bench_q2_algorithms benchmarks/bench_q2_algorithms.cpp)
target_compile_features(bench_q2_algorithms PRIVATE cxx_std_17)
target_link_libraries(bench_q2_algorithms PRIVATE tsl::tsl Threads::Threads)

add_executable(bench_samplesort_multicolumn EXCLUDE_FROM_ALL benchmarks/deprecated/bench_samplesort_multicolumn.cpp)
target_compile_features(bench_samplesort_multicolumn PRIVATE cxx_std_17)
target_link_libraries(bench_samplesort_multicolumn PRIVATE tsl::tsl Threads::Threads)

add_executable(test_samplesort_multicolumn tests/test_samplesort_multicolumn.cpp)
target_compile_features(test_samplesort_multicolumn PRIVATE cxx_std_17)
target_link_libraries(test_samplesort_multicolumn PRIVATE tsl::tsl Threads::Threads)

add_executable(test_samplesort_cosort tests/test_samplesort_cosort.cpp)
target_compile_features(test_samplesort_cosort PRIVATE cxx_std_17)
target_link_libraries(test_samplesort_cosort PRIVATE tsl::tsl Threads::Threads)

# The parallel executor lives in samplesort_parallel_executor.hpp and needs the
# thread library; both binaries exercise it.
# Section 9.2 of the samplesort specification: whether the concurrent
# write-stream cliff that fixed K=16 on one core moves once T threads share the
# LLC and the memory controllers.
add_executable(bench_samplesort_streams benchmarks/bench_samplesort_streams.cpp)
target_compile_features(bench_samplesort_streams PRIVATE cxx_std_17)
target_link_libraries(bench_samplesort_streams PRIVATE tsl::tsl Threads::Threads)

add_executable(bench_samplesort_cosort benchmarks/bench_samplesort_cosort.cpp)
target_compile_features(bench_samplesort_cosort PRIVATE cxx_std_17)
target_link_libraries(bench_samplesort_cosort PRIVATE tsl::tsl Threads::Threads)

# The indirect (index-permutation) sorter. Built without the accelerator options
# it exercises the scalar detector; the IAA block below adds the QPL one, which
# is what proves the detector seam applies to this driver too.
add_executable(test_multicolumn_index_sort tests/test_multicolumn_index_sort.cpp)
target_compile_features(test_multicolumn_index_sort PRIVATE cxx_std_17)
target_link_libraries(test_multicolumn_index_sort PRIVATE tsl::tsl Threads::Threads)

add_executable(benchmark_quicksort_pairwise_swap EXCLUDE_FROM_ALL benchmarks/deprecated/benchmark_quicksort_pairwise_swap.cpp)
target_compile_features(benchmark_quicksort_pairwise_swap PRIVATE cxx_std_17)
target_link_libraries(benchmark_quicksort_pairwise_swap PRIVATE tsl::tsl)
if(ENABLE_VQSORT_BENCHMARK)
  target_compile_definitions(benchmark_quicksort_pairwise_swap PRIVATE HAVE_HIGHWAY_VQSORT=1)
  target_link_libraries(benchmark_quicksort_pairwise_swap PRIVATE hwy_contrib)
endif()

add_executable(benchmark_compact_merge EXCLUDE_FROM_ALL benchmarks/deprecated/benchmark_compact_merge.cpp)
target_compile_features(benchmark_compact_merge PRIVATE cxx_std_17)
target_link_libraries(benchmark_compact_merge PRIVATE tsl::tsl)

add_executable(benchmark_cosort_network EXCLUDE_FROM_ALL benchmarks/deprecated/benchmark_cosort_network.cpp)
target_compile_features(benchmark_cosort_network PRIVATE cxx_std_17)
target_link_libraries(benchmark_cosort_network PRIVATE tsl::tsl)

add_executable(benchmark_multicolumn_sort EXCLUDE_FROM_ALL benchmarks/deprecated/benchmark_multicolumn_sort.cpp)
target_compile_features(benchmark_multicolumn_sort PRIVATE cxx_std_17)
target_link_libraries(benchmark_multicolumn_sort PRIVATE tsl::tsl)

option(ENABLE_GBENCH "Build the Google Benchmark multi-column sweep" ON)
set(GBENCH_RELEASE_VERSION "v1.9.1" CACHE STRING "Google Benchmark release tag")
if(ENABLE_GBENCH)
  set(BENCHMARK_ENABLE_TESTING OFF CACHE BOOL "" FORCE)
  set(BENCHMARK_ENABLE_INSTALL OFF CACHE BOOL "" FORCE)
  set(BENCHMARK_ENABLE_GTEST_TESTS OFF CACHE BOOL "" FORCE)
  set(BENCHMARK_ENABLE_WERROR OFF CACHE BOOL "" FORCE)
  FetchContent_Declare(
    googlebenchmark
    URL "https://github.com/google/benchmark/archive/refs/tags/${GBENCH_RELEASE_VERSION}.tar.gz"
  )
  FetchContent_MakeAvailable(googlebenchmark)

  # Google Benchmark compiles itself with -pedantic-errors, and clang 22 classes
  # its `__COUNTER__` preprocessor test as a C2y extension, which that flag turns
  # into an error. Silence the one diagnostic on the dependency rather than
  # relaxing its warning policy or patching a fetched source tree.
  if(CMAKE_CXX_COMPILER_ID STREQUAL "Clang")
    include(CheckCXXCompilerFlag)
    check_cxx_compiler_flag("-Wno-c2y-extensions" TSL_HAVE_WNO_C2Y_EXTENSIONS)
    if(TSL_HAVE_WNO_C2Y_EXTENSIONS)
      foreach(_gbench_target benchmark benchmark_main)
        if(TARGET ${_gbench_target})
          target_compile_options(${_gbench_target} PRIVATE -Wno-c2y-extensions)
        endif()
      endforeach()
    endif()
  endif()

  add_executable(benchmark_multicolumn_gbench EXCLUDE_FROM_ALL benchmarks/deprecated/benchmark_multicolumn_gbench.cpp)
  target_compile_features(benchmark_multicolumn_gbench PRIVATE cxx_std_17)
  target_link_libraries(
    benchmark_multicolumn_gbench
    PRIVATE tsl::tsl benchmark::benchmark Threads::Threads
  )
endif()

# --- Staged multi-column co-sort benchmark ----------------------------------
# benchmarks/ replaces the flat benchmark matrix with a staged one: data comes
# from the in-memory dataset generator, correctness is a byte comparison against
# the reference image, and COSORT_STAGE selects which variant families are
# registered. See benchmarks/benchmark.md.
option(ENABLE_COSORT_BENCH "Build the staged multi-column co-sort benchmark" ON)

if(ENABLE_COSORT_BENCH AND ENABLE_GBENCH)
  add_executable(cosort_bench benchmarks/cosort_bench.cpp)
  target_compile_features(cosort_bench PRIVATE cxx_std_17)
  target_include_directories(
    cosort_bench PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}"
    "${CMAKE_CURRENT_SOURCE_DIR}/datagen"
    "${CMAKE_CURRENT_SOURCE_DIR}/benchmarks"
  )
  target_link_libraries(
    cosort_bench PRIVATE tsl::tsl benchmark::benchmark Threads::Threads
  )

  # The clang implementation family lives in a profile header guarded by
  # `__clang__` whose bodies call elementwise builtins that older clangs lack, and
  # an unknown builtin is a parse error rather than an instantiation error, so the
  # capability must be probed rather than assumed. The style axis stays in the
  # variant model either way: the binary reports what it could not measure.
  set(_cosort_clang_style OFF)
  if(CMAKE_CXX_COMPILER_ID STREQUAL "Clang")
    include(CheckCXXSourceCompiles)
    check_cxx_source_compiles(
      "int main() { unsigned value = 1u; return (int) __builtin_elementwise_clzg(value); }"
      TSL_COSORT_HAVE_ELEMENTWISE_CLZG
    )
    if(TSL_COSORT_HAVE_ELEMENTWISE_CLZG)
      set(_cosort_clang_style ON)
    endif()
  endif()

  # `clang_v*_bool` differs from `clang_v*` only in mask representation -- packed
  # boolean vectors instead of lane-wide compare results -- and needs the
  # ext_vector_type boolean extension, a capability independent of the elementwise
  # builtins above, so it is probed and reported separately.
  set(_cosort_clang_bool_style OFF)
  if(_cosort_clang_style)
    check_cxx_source_compiles(
      "typedef bool mask16 __attribute__((ext_vector_type(16)));
       int main() { mask16 m = {}; m[3] = true; return m[3] ? 0 : 1; }"
      TSL_COSORT_HAVE_EXT_VECTOR_TYPE_BOOLEAN
    )
    if(TSL_COSORT_HAVE_EXT_VECTOR_TYPE_BOOLEAN)
      set(_cosort_clang_bool_style ON)
    endif()
  endif()

  if(_cosort_clang_style)
    target_compile_definitions(
      cosort_bench PRIVATE TSL_ENABLE_CLANG TSL_COSORT_HAVE_CLANG_STYLE=1
    )
    message(STATUS "cosort_bench: clang implementation family enabled")
    if(_cosort_clang_bool_style)
      target_compile_definitions(
        cosort_bench PRIVATE TSL_COSORT_HAVE_CLANG_BOOL_STYLE=1
      )
      message(STATUS "cosort_bench: clang packed-boolean-mask family enabled")
    else()
      message(
        STATUS
        "cosort_bench: clang packed-boolean-mask family disabled -- this clang "
        "lacks the ext_vector_type boolean extension"
      )
    endif()
  elseif(CMAKE_CXX_COMPILER_ID STREQUAL "Clang")
    message(
      STATUS
      "cosort_bench: clang implementation family disabled -- this clang lacks "
      "__builtin_elementwise_clzg, which the generated clang profile needs "
      "(clang 22 or newer)"
    )
  else()
    message(
      STATUS
      "cosort_bench: clang implementation family disabled -- it requires clang, "
      "compiler is ${CMAKE_CXX_COMPILER_ID}"
    )
  endif()
endif()

# --- Intel DSA (DML) run detector -------------------------------------------
# Off by default: the default build and test run must not require DML or DSA
# hardware. When on, the detector targets are built and the accelerator is
# additionally selectable at runtime (scalar / DML software path / DSA
# hardware), so one binary can compare all three.
option(TSL_COSORT_ENABLE_DSA "Build the Intel DSA (DML) run-length detector targets" OFF)
set(DML_ROOT "" CACHE PATH "Pre-built Intel DML install prefix (empty = fetch from GitHub)")
set(DML_GIT_TAG "v1.2.0" CACHE STRING "Intel DML tag to fetch when DML_ROOT is unset")

# Intel IAA (QPL) run detector. Independent of the DSA option: a host has one
# accelerator or the other, and `rle=` records which produced a result.
option(TSL_COSORT_ENABLE_IAA "Build the Intel IAA (QPL) run-length detector backend" OFF)
set(QPL_ROOT "" CACHE PATH "Pre-built Intel QPL install prefix (empty = fetch from GitHub)")
set(QPL_GIT_TAG "v1.9.0" CACHE STRING "Intel QPL tag to fetch when QPL_ROOT is unset")

if(TSL_COSORT_ENABLE_IAA)
  if(NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/include/cluster_detection/iaa/iaa_run_detector.hpp")
    message(
      FATAL_ERROR
      "TSL_COSORT_ENABLE_IAA needs "
      "test-sort/include/cluster_detection/iaa/iaa_run_detector.hpp, providing "
      "TslIaaRunDetector<T>, TslIaaDetectorFleet<T> and TslIaaAsyncRunDetector<T>. "
      "The contract is documented at the top of benchmarks/cosort_detectors.hpp."
    )
  endif()

  if(QPL_ROOT)
    message(STATUS "QPL: using local installation at ${QPL_ROOT}")
    find_package(QPL REQUIRED CONFIG
                 HINTS "${QPL_ROOT}" "${QPL_ROOT}/lib/cmake/QPL" "${QPL_ROOT}/lib64/cmake/QPL")
    set(_iaa_link_targets QPL::qpl)
  else()
    # QPL bundles ISA-L assembly kernels, so a source build needs NASM. It fails
    # deep inside the fetched tree rather than here if the assembler is absent.
    find_program(TSL_NASM_EXECUTABLE nasm)
    if(NOT TSL_NASM_EXECUTABLE)
      message(
        FATAL_ERROR
        "Building QPL from source needs the nasm assembler for its bundled ISA-L "
        "kernels. Install nasm, or pass -DQPL_ROOT=<prefix> to use a pre-built QPL."
      )
    endif()
    message(STATUS "QPL: fetching ${QPL_GIT_TAG} from github.com/intel/qpl")
    set(QPL_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
    set(QPL_BUILD_TESTS OFF CACHE BOOL "" FORCE)
    # QPL compiles its own sources with -Werror, and a compiler newer than the
    # release diagnoses code the release considered clean -- clang 22, which this
    # project requires, rejects QPL 1.9.0 over -Wunnecessary-virtual-specifier in
    # its hardware dispatcher. Warnings in a fetched dependency are not this
    # project's to fix, so its own switch turns them back into warnings.
    set(QPL_TREAT_WARNINGS_AS_ERRORS OFF CACHE BOOL "" FORCE)
    FetchContent_Declare(
      QPL
      GIT_REPOSITORY https://github.com/intel/qpl.git
      GIT_TAG "${QPL_GIT_TAG}"
      GIT_SHALLOW TRUE
    )
    FetchContent_MakeAvailable(QPL)
    set(_iaa_link_targets qpl)
  endif()

  # Every binary that reads the `rle=` backend registry in
  # benchmarks/cosort_detectors.hpp, not just the staged corpus: the multi-column
  # samplesort takes the same detectors.
  foreach(_rle_consumer ${TSL_COSORT_RLE_CONSUMERS})
    if(TARGET ${_rle_consumer})
      # TSL_COSORT_ENABLE_IAA is what the detector header itself gates on;
      # TSL_COSORT_HAVE_IAA is what the backend registry reads.
      target_compile_definitions(
        ${_rle_consumer} PRIVATE TSL_COSORT_ENABLE_IAA=1 TSL_COSORT_HAVE_IAA=1
      )
      target_link_libraries(${_rle_consumer} PRIVATE ${_iaa_link_targets})
      message(STATUS "${_rle_consumer}: IAA detector backends enabled")
    endif()
  endforeach()

  # Same test binary, now with the QPL detector compiled in: the index sorter's
  # discovery runs on its materialized key buffer, so an accelerator backend
  # applies with no indirection.
  target_compile_definitions(test_multicolumn_index_sort PRIVATE TSL_COSORT_ENABLE_IAA=1)
  target_link_libraries(test_multicolumn_index_sort PRIVATE ${_iaa_link_targets})

  # Frequency-derived run detection: counts resolved on the accelerator while the
  # sort runs, consumed afterwards instead of a comparison scan.
  add_executable(test_iaa_frequency_run_detector tests/test_iaa_frequency_run_detector.cpp)
  target_compile_features(test_iaa_frequency_run_detector PRIVATE cxx_std_17)
  target_compile_definitions(test_iaa_frequency_run_detector PRIVATE TSL_COSORT_ENABLE_IAA=1)
  target_link_libraries(
    test_iaa_frequency_run_detector PRIVATE tsl::tsl Threads::Threads ${_iaa_link_targets}
  )
  add_test(NAME test_iaa_frequency_run_detector COMMAND test_iaa_frequency_run_detector)

  # Tuning tool, not a test: finds the range size at which preparing the counts
  # starts paying for itself. Meaningful only on an IAA host -- see the file's
  # header and benchmark-final.md.
  add_executable(bench_iaa_frequency_min_offload benchmarks/bench_iaa_frequency_min_offload.cpp)
  target_compile_features(bench_iaa_frequency_min_offload PRIVATE cxx_std_17)
  target_compile_definitions(bench_iaa_frequency_min_offload PRIVATE TSL_COSORT_ENABLE_IAA=1)
  target_link_libraries(
    bench_iaa_frequency_min_offload PRIVATE tsl::tsl Threads::Threads ${_iaa_link_targets}
  )

  add_executable(test_iaa_run_detector tests/test_iaa_run_detector.cpp)
  target_compile_features(test_iaa_run_detector PRIVATE cxx_std_17)
  target_compile_definitions(test_iaa_run_detector PRIVATE TSL_COSORT_ENABLE_IAA=1)
  target_link_libraries(
    test_iaa_run_detector PRIVATE tsl::tsl Threads::Threads ${_iaa_link_targets}
  )
  # Runs the QPL software path only, so it needs no accelerator; pass `hw` by
  # hand on an IAA host to cover the hardware path.
  add_test(NAME test_iaa_run_detector COMMAND test_iaa_run_detector)

  # Distinct-value frequencies over an unsorted range. Independent of the
  # detector: iaa_distinct_frequencies.hpp needs only QPL, and its entry point
  # takes a std::span, so this target asks for C++20.
  add_executable(test_iaa_distinct_frequencies tests/test_iaa_distinct_frequencies.cpp)
  target_compile_features(test_iaa_distinct_frequencies PRIVATE cxx_std_20)
  target_compile_definitions(test_iaa_distinct_frequencies PRIVATE TSL_COSORT_ENABLE_IAA=1)
  target_link_libraries(test_iaa_distinct_frequencies PRIVATE ${_iaa_link_targets})
  add_test(NAME test_iaa_distinct_frequencies COMMAND test_iaa_distinct_frequencies)
endif()

if(TSL_COSORT_ENABLE_DSA)
  # DML ships a C core under its C++ facade.
  enable_language(C)

  # DML's hardware dispatcher includes <uuid/uuid.h>, and it fails deep inside the
  # fetched tree rather than here if the header is absent. Say so up front.
  include(CheckIncludeFile)
  check_include_file("uuid/uuid.h" TSL_HAVE_UUID_HEADER)
  if(NOT TSL_HAVE_UUID_HEADER)
    message(
      FATAL_ERROR
      "TSL_COSORT_ENABLE_DSA needs <uuid/uuid.h> for DML's hardware dispatcher. "
      "Install uuid-dev (Debian/Ubuntu) or libuuid-devel (Fedora/RHEL)."
    )
  endif()

  # DML's AVX-512 kernels compile with -march=skylake-avx512. `enable_language(C)`
  # picks the C compiler from the environment, which is not necessarily the one
  # this project was configured with -- a CC of `zig cc`, for instance, parses that
  # flag as arch `skylake` plus an unknown feature `avx512` and fails deep inside
  # the fetched tree. Check the flag here and name the compiler that rejected it.
  if(NOT DML_ROOT)
    include(CheckCCompilerFlag)
    check_c_compiler_flag("-march=skylake-avx512" TSL_C_ACCEPTS_SKYLAKE_AVX512)
    if(NOT TSL_C_ACCEPTS_SKYLAKE_AVX512)
      message(
        FATAL_ERROR
        "Building DML from source needs a C compiler that accepts "
        "-march=skylake-avx512, and ${CMAKE_C_COMPILER} does not. Pass "
        "-DCMAKE_C_COMPILER=<clang|gcc> (the CC environment variable may be "
        "selecting something else), or use a pre-built DML via -DDML_ROOT=<prefix>."
      )
    endif()
  endif()

  if(DML_ROOT)
    message(STATUS "DML: using local installation at ${DML_ROOT}")
    find_package(DML REQUIRED CONFIG
                 HINTS "${DML_ROOT}" "${DML_ROOT}/lib/cmake/DML" "${DML_ROOT}/lib64/cmake/DML")
    set(_dsa_link_targets DML::dml)
  else()
    message(STATUS "DML: fetching ${DML_GIT_TAG} from github.com/intel/DML")
    set(DML_BUILD_TESTS OFF CACHE BOOL "" FORCE)
    set(DML_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
    FetchContent_Declare(
      DML
      GIT_REPOSITORY https://github.com/intel/DML.git
      GIT_TAG "${DML_GIT_TAG}"
      GIT_SHALLOW TRUE
    )
    FetchContent_MakeAvailable(DML)
    set(_dsa_link_targets dml)
  endif()

  # The staged benchmark gains the DSA backends of the `rle=` axis.
  foreach(_rle_consumer ${TSL_COSORT_RLE_CONSUMERS})
    if(TARGET ${_rle_consumer})
      # TSL_COSORT_ENABLE_DSA is what the detector headers themselves gate on;
      # TSL_COSORT_HAVE_DSA is what the backend registry reads.
      target_compile_definitions(
        ${_rle_consumer} PRIVATE TSL_COSORT_ENABLE_DSA=1 TSL_COSORT_HAVE_DSA=1
      )
      target_link_libraries(${_rle_consumer} PRIVATE ${_dsa_link_targets})
      message(STATUS "${_rle_consumer}: DSA detector backends enabled")
    endif()
  endforeach()

  add_executable(test_dsa_run_detector tests/test_dsa_run_detector.cpp)
  target_compile_features(test_dsa_run_detector PRIVATE cxx_std_17)
  target_compile_definitions(test_dsa_run_detector PRIVATE TSL_COSORT_ENABLE_DSA=1)
  target_link_libraries(test_dsa_run_detector PRIVATE tsl::tsl ${_dsa_link_targets})
  add_test(NAME test_dsa_run_detector COMMAND test_dsa_run_detector)

  add_executable(benchmark_dsa_run_detector EXCLUDE_FROM_ALL benchmarks/deprecated/benchmark_dsa_run_detector.cpp)
  target_compile_features(benchmark_dsa_run_detector PRIVATE cxx_std_17)
  target_compile_definitions(benchmark_dsa_run_detector PRIVATE TSL_COSORT_ENABLE_DSA=1)
  target_link_libraries(benchmark_dsa_run_detector PRIVATE tsl::tsl ${_dsa_link_targets})

  # The full co-sort with the RLE backend as the registered axis. Needs Google
  # Benchmark, so it follows ENABLE_GBENCH.
  if(ENABLE_GBENCH)
    add_executable(benchmark_dsa_cosort EXCLUDE_FROM_ALL benchmarks/deprecated/benchmark_dsa_cosort.cpp)
    target_compile_features(benchmark_dsa_cosort PRIVATE cxx_std_17)
    target_compile_definitions(benchmark_dsa_cosort PRIVATE TSL_COSORT_ENABLE_DSA=1)
    target_link_libraries(
      benchmark_dsa_cosort
      PRIVATE tsl::tsl benchmark::benchmark Threads::Threads ${_dsa_link_targets}
    )
  endif()
endif()

# --- Synthetic dataset catalog ----------------------------------------------
# Standalone C++17: the generator and its verifier describe the datasets of
# description_datasets.md and need neither TSL nor a SIMD host. The default
# output directory is the committed source path so that running the binary from
# any build tree writes to the same place; --out overrides it.
# One include root per kind of header, so a source says what it is including:
#   sorting/quicksort/...   sorting/primitives/...   cluster_detection/iaa/...
# `benchmarks` and `benchmarks/datagen` are on the path so the benchmark-local and
# dataset headers keep the bare names they use among themselves.
include_directories(
  "${CMAKE_CURRENT_SOURCE_DIR}/include"
  "${CMAKE_CURRENT_SOURCE_DIR}/benchmarks"
  "${CMAKE_CURRENT_SOURCE_DIR}/benchmarks/datagen"
)

option(TSL_COSORT_BUILD_DATAGEN "Build the synthetic dataset generator and verifier" ON)

if(TSL_COSORT_BUILD_DATAGEN)
  foreach(_datagen_target generate_datasets verify_datasets)
    add_executable(${_datagen_target} benchmarks/datagen/${_datagen_target}.cpp)
    target_compile_features(${_datagen_target} PRIVATE cxx_std_17)
    target_compile_definitions(
      ${_datagen_target}
      PRIVATE TSL_DATASET_DEFAULT_DIR="${CMAKE_CURRENT_SOURCE_DIR}/data"
    )
  endforeach()

  # Reference sorted images: the exact oracle the benchmark memcmps against.
  # Shares only the container and manifest readers with the generator, never the
  # sorting implementation under test.
  add_executable(reference benchmarks/reference.cpp)
  target_compile_features(reference PRIVATE cxx_std_17)
  target_link_libraries(reference PRIVATE Threads::Threads)
  target_compile_definitions(
    reference
    PRIVATE TSL_DATASET_DEFAULT_DIR="${CMAKE_CURRENT_SOURCE_DIR}/data"
  )
endif()

add_test(NAME test_sort COMMAND test_sort)
add_test(NAME test_multicolumn_sort COMMAND test_multicolumn_sort)
add_test(NAME test_multicolumn_index_sort COMMAND test_multicolumn_index_sort)
