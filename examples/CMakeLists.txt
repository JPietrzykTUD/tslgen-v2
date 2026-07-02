cmake_minimum_required(VERSION 3.20)
project(tsl_examples CXX)

include(FetchContent)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(
  TSL_GENERATED_URL
  ""
  CACHE STRING
  "URL of a packaged generated TSL archive; the archive must contain cpp/CMakeLists.txt"
)

set(
  TSL_GENERATED_ROOT_DIR
  "${CMAKE_CURRENT_LIST_DIR}/../tslctmp/examples/generated"
  CACHE PATH
  "Path to a generated TSL output root containing cpp/CMakeLists.txt"
)

set(
  TSL_GENERATED_CPP_DIR
  "${CMAKE_CURRENT_LIST_DIR}/../tslctmp/examples/generated/cpp"
  CACHE PATH
  "Legacy path to the generated TSL C++ project directory containing CMakeLists.txt"
)

if(TSL_GENERATED_URL)
  FetchContent_Declare(
    tsl
    URL "${TSL_GENERATED_URL}"
    SOURCE_SUBDIR cpp
  )
elseif(EXISTS "${TSL_GENERATED_ROOT_DIR}/cpp/CMakeLists.txt")
  FetchContent_Declare(
    tsl
    SOURCE_DIR "${TSL_GENERATED_ROOT_DIR}"
    SOURCE_SUBDIR cpp
  )
elseif(EXISTS "${TSL_GENERATED_CPP_DIR}/CMakeLists.txt")
  FetchContent_Declare(
    tsl
    SOURCE_DIR "${TSL_GENERATED_CPP_DIR}"
  )
else()
  message(
    FATAL_ERROR
    "Generated TSL project not found. Generate it first, pass "
    "-DTSL_GENERATED_ROOT_DIR=/path/to/generated, pass "
    "-DTSL_GENERATED_CPP_DIR=/path/to/generated/cpp, or pass "
    "-DTSL_GENERATED_URL=https://.../tsl-generated-<tag>.tar.gz."
  )
endif()

set(TSL_PROFILE "scalar" CACHE STRING "Generated TSL profile consumed by examples")

FetchContent_MakeAvailable(tsl)

add_executable(unary_operator unary_operator.cpp)
target_link_libraries(unary_operator PRIVATE tsl::tsl)

enable_testing()
add_test(NAME unary_operator COMMAND unary_operator)
