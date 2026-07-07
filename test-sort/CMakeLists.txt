cmake_minimum_required(VERSION 3.20)
project(tsl_release_fetch_content_sort LANGUAGES CXX)

if(POLICY CMP0135)
  cmake_policy(SET CMP0135 NEW)
endif()

include(CTest)
include(FetchContent)

set(
  TSL_RELEASE_ARCHIVE_URL
  ""
  CACHE STRING
  "URL of the generated TSL release archive"
)
set(
  TSL_RELEASE_ARCHIVE_SHA256
  ""
  CACHE STRING
  "Optional SHA256 digest for the generated TSL release archive"
)
set(TSL_PROFILE "scalar" CACHE STRING "Generated TSL profile consumed by this test")

if(NOT TSL_RELEASE_ARCHIVE_URL)
  message(FATAL_ERROR "Pass -DTSL_RELEASE_ARCHIVE_URL=<release-archive-url>")
endif()

set(_tsl_release_hash_args)
if(TSL_RELEASE_ARCHIVE_SHA256)
  list(APPEND _tsl_release_hash_args URL_HASH "SHA256=${TSL_RELEASE_ARCHIVE_SHA256}")
endif()

FetchContent_Declare(
  tsl
  URL "${TSL_RELEASE_ARCHIVE_URL}"
  SOURCE_SUBDIR cpp
  ${_tsl_release_hash_args}
)
FetchContent_MakeAvailable(tsl)

add_executable(test_sort main.cpp)
target_compile_features(test_sort PRIVATE cxx_std_17)
target_link_libraries(test_sort PRIVATE tsl::tsl)

add_test(NAME test_sort COMMAND test_sort)
