cmake_minimum_required(VERSION 3.20)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON CACHE BOOL "Export compile_commands.json")
project(tsl_release_fetch_content_sort LANGUAGES CXX)

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
set(TSL_RELEASE_VERSION "v0.2.5" CACHE STRING "Generated TSL release tag")
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

add_executable(test_sort test_quicksort_pairwise_swap.cpp)
target_compile_features(test_sort PRIVATE cxx_std_17)
target_link_libraries(test_sort PRIVATE tsl::tsl)

add_executable(test_multicolumn_sort test_multicolumn_sort.cpp)
target_compile_features(test_multicolumn_sort PRIVATE cxx_std_17)
target_link_libraries(test_multicolumn_sort PRIVATE tsl::tsl Threads::Threads)

add_executable(benchmark_quicksort_pairwise_swap benchmark_quicksort_pairwise_swap.cpp)
target_compile_features(benchmark_quicksort_pairwise_swap PRIVATE cxx_std_17)
target_link_libraries(benchmark_quicksort_pairwise_swap PRIVATE tsl::tsl)
if(ENABLE_VQSORT_BENCHMARK)
  target_compile_definitions(benchmark_quicksort_pairwise_swap PRIVATE HAVE_HIGHWAY_VQSORT=1)
  target_link_libraries(benchmark_quicksort_pairwise_swap PRIVATE hwy_contrib)
endif()

add_executable(benchmark_compact_merge benchmark_compact_merge.cpp)
target_compile_features(benchmark_compact_merge PRIVATE cxx_std_17)
target_link_libraries(benchmark_compact_merge PRIVATE tsl::tsl)

add_executable(benchmark_cosort_network benchmark_cosort_network.cpp)
target_compile_features(benchmark_cosort_network PRIVATE cxx_std_17)
target_link_libraries(benchmark_cosort_network PRIVATE tsl::tsl)

add_executable(benchmark_multicolumn_sort benchmark_multicolumn_sort.cpp)
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

  add_executable(benchmark_multicolumn_gbench benchmark_multicolumn_gbench.cpp)
  target_compile_features(benchmark_multicolumn_gbench PRIVATE cxx_std_17)
  target_link_libraries(
    benchmark_multicolumn_gbench
    PRIVATE tsl::tsl benchmark::benchmark Threads::Threads
  )
endif()

# --- Intel DSA (DML) run detector -------------------------------------------
# Off by default: the default build and test run must not require DML or DSA
# hardware. When on, the detector targets are built and the accelerator is
# additionally selectable at runtime (scalar / DML software path / DSA
# hardware), so one binary can compare all three.
option(TSL_COSORT_ENABLE_DSA "Build the Intel DSA (DML) run-length detector targets" OFF)
set(DML_ROOT "" CACHE PATH "Pre-built Intel DML install prefix (empty = fetch from GitHub)")
set(DML_GIT_TAG "v1.2.0" CACHE STRING "Intel DML tag to fetch when DML_ROOT is unset")

if(TSL_COSORT_ENABLE_DSA)
  # DML ships a C core under its C++ facade.
  enable_language(C)

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

  add_executable(test_dsa_run_detector test_dsa_run_detector.cpp)
  target_compile_features(test_dsa_run_detector PRIVATE cxx_std_17)
  target_compile_definitions(test_dsa_run_detector PRIVATE TSL_COSORT_ENABLE_DSA=1)
  target_link_libraries(test_dsa_run_detector PRIVATE tsl::tsl ${_dsa_link_targets})
  add_test(NAME test_dsa_run_detector COMMAND test_dsa_run_detector)

  add_executable(benchmark_dsa_run_detector benchmark_dsa_run_detector.cpp)
  target_compile_features(benchmark_dsa_run_detector PRIVATE cxx_std_17)
  target_compile_definitions(benchmark_dsa_run_detector PRIVATE TSL_COSORT_ENABLE_DSA=1)
  target_link_libraries(benchmark_dsa_run_detector PRIVATE tsl::tsl ${_dsa_link_targets})

  # The full co-sort with the RLE backend as the registered axis. Needs Google
  # Benchmark, so it follows ENABLE_GBENCH.
  if(ENABLE_GBENCH)
    add_executable(benchmark_dsa_cosort benchmark_dsa_cosort.cpp)
    target_compile_features(benchmark_dsa_cosort PRIVATE cxx_std_17)
    target_compile_definitions(benchmark_dsa_cosort PRIVATE TSL_COSORT_ENABLE_DSA=1)
    target_link_libraries(
      benchmark_dsa_cosort
      PRIVATE tsl::tsl benchmark::benchmark Threads::Threads ${_dsa_link_targets}
    )
  endif()
endif()

add_test(NAME test_sort COMMAND test_sort)
add_test(NAME test_multicolumn_sort COMMAND test_multicolumn_sort)
