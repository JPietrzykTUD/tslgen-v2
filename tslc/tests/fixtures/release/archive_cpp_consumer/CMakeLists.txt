cmake_minimum_required(VERSION 3.20)
project(tsl_release_archive_cpp_consumer LANGUAGES CXX)

if(NOT IS_DIRECTORY "${TSL_GENERATED_ROOT}/cpp")
  message(FATAL_ERROR "TSL_GENERATED_ROOT does not name an extracted TSL package")
endif()

include(FetchContent)
set(TSL_PROFILE scalar CACHE STRING "Generated TSL profile" FORCE)
set(TSL_BUILD_TESTS OFF CACHE BOOL "Generated TSL tests" FORCE)
FetchContent_Declare(tsl SOURCE_DIR "${TSL_GENERATED_ROOT}/cpp")
FetchContent_MakeAvailable(tsl)

add_executable(tsl_release_archive_cpp_consumer main.cpp)
target_link_libraries(tsl_release_archive_cpp_consumer PRIVATE tsl::tsl)
target_compile_features(tsl_release_archive_cpp_consumer PRIVATE cxx_std_17)
if(MSVC)
  target_compile_options(tsl_release_archive_cpp_consumer PRIVATE /W4 /WX)
else()
  target_compile_options(
    tsl_release_archive_cpp_consumer PRIVATE -Wall -Wextra -Werror
  )
endif()

enable_testing()
add_test(
  NAME tsl_release_archive_cpp_consumer
  COMMAND tsl_release_archive_cpp_consumer
)
