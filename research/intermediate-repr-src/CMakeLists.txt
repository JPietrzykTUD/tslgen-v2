cmake_minimum_required(VERSION 3.20)
project(intermediate_repr_benchmark LANGUAGES CXX)

if(NOT CMAKE_CONFIGURATION_TYPES AND NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()
set(CMAKE_EXPORT_COMPILE_COMMANDS ON CACHE BOOL "Export compile commands" FORCE)

set(IRBENCH_PROFILE "avx2" CACHE STRING "TSL machine profile")
set_property(CACHE IRBENCH_PROFILE PROPERTY STRINGS sse2 avx2 skylake)
option(IRBENCH_ENABLE_CLANG_OVERLAY "Compile Clang fixed-vector policies" OFF)
set(TSL_LOCAL_SOURCE_DIR "" CACHE PATH "Generated TSL root or cpp directory")
set(
  TSL_RELEASE_ARCHIVE_URL
  "https://github.com/JPietrzykTUD/tslgen-v2/releases/download/v0.2.7/tsl-generated-v0.2.7.tar.gz"
  CACHE STRING
  "Pinned generated TSL v0.2.7 archive"
)
set(
  TSL_RELEASE_ARCHIVE_SHA256
  "fcbb851f6b8b05fb5eefffa9d413b19e9a96d0f2a7805451ef7a9ff7c4ba7f03"
  CACHE STRING
  "SHA-256 of the generated TSL archive"
)
set(
  GBENCH_RELEASE_ARCHIVE_URL
  "https://github.com/google/benchmark/archive/refs/tags/v1.9.5.tar.gz"
  CACHE STRING
  "Pinned Google Benchmark v1.9.5 archive"
)
set(
  GBENCH_RELEASE_ARCHIVE_SHA256
  "9631341c82bac4a288bef951f8b26b41f69021794184ece969f8473977eaa340"
  CACHE STRING
  "SHA-256 of the Google Benchmark archive"
)

if(IRBENCH_PROFILE STREQUAL "sse2")
  set(IRBENCH_NATIVE_LANES 4)
elseif(IRBENCH_PROFILE STREQUAL "avx2")
  set(IRBENCH_NATIVE_LANES 8)
elseif(IRBENCH_PROFILE STREQUAL "skylake")
  set(IRBENCH_NATIVE_LANES 16)
else()
  message(FATAL_ERROR "IRBENCH_PROFILE must be sse2, avx2, or skylake")
endif()

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
include(Dependencies)
irbench_load_tsl()
irbench_load_google_benchmark()

add_library(irbench_build_context INTERFACE)
target_compile_features(irbench_build_context INTERFACE cxx_std_17)
target_include_directories(
  irbench_build_context
  INTERFACE "${CMAKE_CURRENT_SOURCE_DIR}/include"
)
target_link_libraries(irbench_build_context INTERFACE "${IRBENCH_TSL_TARGET}")
target_include_directories(
  irbench_build_context
  SYSTEM INTERFACE
    "$<TARGET_PROPERTY:${IRBENCH_TSL_TARGET},INTERFACE_INCLUDE_DIRECTORIES>"
)
target_compile_definitions(
  irbench_build_context
  INTERFACE
    IRBENCH_PROFILE_NAME="${IRBENCH_PROFILE}"
    IRBENCH_NATIVE_LANES=${IRBENCH_NATIVE_LANES}
    IRBENCH_HAS_CLANG_OVERLAY=$<BOOL:${IRBENCH_ENABLE_CLANG_OVERLAY}>
    IRBENCH_TSL_SOURCE_ID="${IRBENCH_TSL_SOURCE_ID}"
    IRBENCH_BUILD_MODE="$<CONFIG>"
    IRBENCH_CXX_COMPILER_ID="${CMAKE_CXX_COMPILER_ID}"
    IRBENCH_CXX_COMPILER_PATH="${CMAKE_CXX_COMPILER}"
)
target_compile_options(
  irbench_build_context
  INTERFACE
    $<$<CXX_COMPILER_ID:GNU,Clang,AppleClang>:-O3;-fno-lto;-Wall;-Wextra;-Wpedantic>
)
target_link_options(
  irbench_build_context
  INTERFACE $<$<CXX_COMPILER_ID:GNU,Clang,AppleClang>:-fno-lto>
)

add_library(irbench_tsl_references OBJECT src/references.cpp)
target_link_libraries(irbench_tsl_references PRIVATE irbench_build_context)
target_compile_definitions(irbench_tsl_references PRIVATE IRBENCH_BUILD_TSL_REFERENCES=1)
set_property(TARGET irbench_tsl_references PROPERTY INTERPROCEDURAL_OPTIMIZATION FALSE)

add_library(irbench_scalar_autovec OBJECT src/references.cpp)
target_link_libraries(irbench_scalar_autovec PRIVATE irbench_build_context)
target_compile_definitions(
  irbench_scalar_autovec
  PRIVATE
    IRBENCH_BUILD_SCALAR_REFERENCE=1
    IRBENCH_SCALAR_FUNCTION=run_scalar_autovec
)
set_property(TARGET irbench_scalar_autovec PROPERTY INTERPROCEDURAL_OPTIMIZATION FALSE)

add_library(irbench_scalar_no_vector OBJECT src/references.cpp)
target_link_libraries(irbench_scalar_no_vector PRIVATE irbench_build_context)
target_compile_definitions(
  irbench_scalar_no_vector
  PRIVATE
    IRBENCH_BUILD_SCALAR_REFERENCE=1
    IRBENCH_SCALAR_FUNCTION=run_scalar_no_vector
)
target_compile_options(
  irbench_scalar_no_vector
  PRIVATE
    $<$<CXX_COMPILER_ID:Clang,AppleClang>:-fno-vectorize;-fno-slp-vectorize>
    $<$<CXX_COMPILER_ID:GNU>:-fno-tree-vectorize>
)
set_property(TARGET irbench_scalar_no_vector PROPERTY INTERPROCEDURAL_OPTIMIZATION FALSE)

add_library(
  irbench_core
  STATIC
    src/datasets.cpp
    src/produce.cpp
    src/consume.cpp
    $<TARGET_OBJECTS:irbench_tsl_references>
    $<TARGET_OBJECTS:irbench_scalar_autovec>
    $<TARGET_OBJECTS:irbench_scalar_no_vector>
)
target_link_libraries(irbench_core PUBLIC irbench_build_context)
set_property(TARGET irbench_core PROPERTY INTERPROCEDURAL_OPTIMIZATION FALSE)

add_executable(irbench_correctness src/correctness_main.cpp)
target_link_libraries(irbench_correctness PRIVATE irbench_core)
set_property(TARGET irbench_correctness PROPERTY INTERPROCEDURAL_OPTIMIZATION FALSE)

add_executable(irbench_benchmark src/benchmark_main.cpp)
target_link_libraries(irbench_benchmark PRIVATE irbench_core benchmark::benchmark)
target_compile_definitions(
  irbench_benchmark
  PRIVATE IRBENCH_GBENCH_SOURCE_ID="${IRBENCH_GBENCH_SOURCE_ID}"
)
set_property(TARGET irbench_benchmark PROPERTY INTERPROCEDURAL_OPTIMIZATION FALSE)

include(CTest)
if(BUILD_TESTING)
  add_test(NAME irbench_correctness COMMAND irbench_correctness)
  add_test(
    NAME irbench_pressure_smoke
    COMMAND
      irbench_benchmark
      --irbench_matrix=pressure
      "--benchmark_filter=realization=hardware/vector_bits=[0-9]+/mask_policy=hardware/representation=native/aggregates=(1|4|8)/scaling=strong/N=65536/B=1024/sA_bp=5000/sBgA_bp=9000"
      --benchmark_dry_run=true
  )
  add_test(
    NAME irbench_threading_smoke
    COMMAND
      irbench_benchmark
      --irbench_matrix=threading
      --irbench_workers=1,2
      --irbench_scaling=both
      "--benchmark_filter=realization=hardware/vector_bits=[0-9]+/mask_policy=hardware/representation=native/aggregates=1/scaling=(strong|weak)/N=65536/B=1024/sA_bp=5000/sBgA_bp=9000"
      --benchmark_dry_run=true
  )
endif()

message(STATUS "IR benchmark profile: ${IRBENCH_PROFILE}")
message(STATUS "IR benchmark TSL target: ${IRBENCH_TSL_TARGET}")
message(STATUS "IR benchmark TSL source: ${IRBENCH_TSL_SOURCE_ID}")
message(STATUS "IR benchmark Google Benchmark source: ${IRBENCH_GBENCH_SOURCE_ID}")
