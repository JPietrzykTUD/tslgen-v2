cmake_minimum_required(VERSION 3.20)
project(pipcost_benchmark CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

set(TSL_GENERATED_CPP_DIR "" CACHE PATH "Generated TSL C++ project")
set(TSL_PROFILE "avx2" CACHE STRING "Generated TSL profile to consume")
set(PIPCOST_SIMD_LANES "8" CACHE STRING "Fixed SIMD lane count for int32")

if(NOT EXISTS "${TSL_GENERATED_CPP_DIR}/CMakeLists.txt")
  message(FATAL_ERROR
    "TSL_GENERATED_CPP_DIR must name a generated cpp directory containing CMakeLists.txt")
endif()

set(TSL_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(TSL_BUILD_BENCHMARKS OFF CACHE BOOL "" FORCE)
add_subdirectory("${TSL_GENERATED_CPP_DIR}" "${CMAKE_BINARY_DIR}/generated-tsl")

add_library(
  pipcost-kernels
  STATIC
  src/data.cpp
  src/measurement.cpp
  src/plan_registry.cpp
  src/reference.cpp
  src/plans/fused_mask.cpp
  src/plans/materialized_mask.cpp
  src/plans/positions.cpp
  src/plans/scalar_autovec.cpp
  src/plans/scalar_no_vector.cpp
)
target_include_directories(pipcost-kernels PUBLIC include)
target_link_libraries(pipcost-kernels PUBLIC tsl::tsl)
target_compile_definitions(
  pipcost-kernels
  PUBLIC PIPCOST_SIMD_LANES=${PIPCOST_SIMD_LANES}
)
target_compile_options(
  pipcost-kernels
  PRIVATE
  $<$<CXX_COMPILER_ID:GNU,Clang,AppleClang>:-O3;-fno-lto>
  $<$<CXX_COMPILER_ID:MSVC>:/O2>
)

if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
  set_property(
    SOURCE src/plans/scalar_no_vector.cpp
    APPEND PROPERTY COMPILE_OPTIONS
    -fno-tree-vectorize
    -fno-tree-slp-vectorize
  )
elseif(CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  set_property(
    SOURCE src/plans/scalar_no_vector.cpp
    APPEND PROPERTY COMPILE_OPTIONS
    -fno-vectorize
    -fno-slp-vectorize
  )
else()
  message(FATAL_ERROR
    "PIPCost requires GNU or Clang to provide a controlled no-vector baseline")
endif()

add_executable(pipcost-bench src/main.cpp)
target_link_libraries(pipcost-bench PRIVATE pipcost-kernels)

add_executable(pipcost-kernel-tests tests/kernel_tests.cpp)
target_link_libraries(pipcost-kernel-tests PRIVATE pipcost-kernels)

enable_testing()
add_test(NAME pipcost-kernel-tests COMMAND pipcost-kernel-tests)
add_test(NAME pipcost-bench-self-test COMMAND pipcost-bench --self-test)
