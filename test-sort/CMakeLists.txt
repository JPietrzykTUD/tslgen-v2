cmake_minimum_required(VERSION 3.20)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON CACHE BOOL "Export compile_commands.json")
project(tsl_release_fetch_content_sort LANGUAGES CXX)

if(POLICY CMP0135)
  cmake_policy(SET CMP0135 NEW)
endif()

include(CTest)
include(FetchContent)

set(TSL_RELEASE_VERSION "v0.1.3" CACHE STRING "Generated TSL release tag")
set(
  TSL_RELEASE_ARCHIVE_URL
  # "https://github.com/JPietrzykTUD/tslgen-v2/releases/download/${TSL_RELEASE_VERSION}/tsl-generated-1daeecdd39aa2b02a1bb60697d67fe6ae70b23cc.tar.gz"
  "https://github.com/JPietrzykTUD/tslgen-v2/releases/download/${TSL_RELEASE_VERSION}/tsl-generated-${TSL_RELEASE_VERSION}.tar.gz"
  CACHE STRING
  "URL of the generated TSL release archive"
)
# set(
#   TSL_RELEASE_ARCHIVE_SHA256
#   "428af929846e06ecd891eb0e322a6713f10829cfb7412f420c0a548e38a28e95"
#   CACHE STRING
#   "Optional SHA256 digest for the generated TSL release archive"
# )
set(TSL_PROFILE "auto" CACHE STRING "Generated TSL profile consumed by this test")

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
