include(FetchContent)

if(POLICY CMP0135)
  cmake_policy(SET CMP0135 NEW)
endif()

function(irbench_load_tsl)
  set(TSL_BUILD_TESTS OFF CACHE BOOL "Build generated TSL tests" FORCE)
  set(TSL_BUILD_BENCHMARKS OFF CACHE BOOL "Build generated TSL benchmarks" FORCE)
  set(TSL_AUTOTUNE_VARIANTS OFF CACHE BOOL "Autotune generated TSL variants" FORCE)
  set(TSL_PROFILE "${IRBENCH_PROFILE}" CACHE STRING "Generated TSL profile" FORCE)

  if(TSL_LOCAL_SOURCE_DIR)
    get_filename_component(
      _tsl_source
      "${TSL_LOCAL_SOURCE_DIR}"
      ABSOLUTE
      BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}"
    )
    if(EXISTS "${_tsl_source}/cpp/CMakeLists.txt")
      set(_tsl_source "${_tsl_source}/cpp")
    elseif(NOT EXISTS "${_tsl_source}/CMakeLists.txt")
      message(FATAL_ERROR
        "TSL_LOCAL_SOURCE_DIR must name a generated TSL root or its cpp directory")
    endif()
    add_subdirectory(
      "${_tsl_source}"
      "${CMAKE_CURRENT_BINARY_DIR}/_deps/tsl-local-build"
      EXCLUDE_FROM_ALL
    )
    file(GLOB_RECURSE _tsl_public_files LIST_DIRECTORIES FALSE
      "${_tsl_source}/include/*"
    )
    list(APPEND _tsl_public_files "${_tsl_source}/CMakeLists.txt")
    list(SORT _tsl_public_files)
    set(_tsl_manifest "")
    foreach(_tsl_file IN LISTS _tsl_public_files)
      file(RELATIVE_PATH _tsl_relative "${_tsl_source}" "${_tsl_file}")
      file(SHA256 "${_tsl_file}" _tsl_file_hash)
      string(APPEND _tsl_manifest "${_tsl_relative}:${_tsl_file_hash}\n")
    endforeach()
    string(SHA256 _tsl_public_digest "${_tsl_manifest}")
    set(_tsl_source_id "local:${_tsl_public_digest}:${_tsl_source}")
  else()
    string(LENGTH "${TSL_RELEASE_ARCHIVE_SHA256}" _tsl_hash_length)
    if(NOT _tsl_hash_length EQUAL 64 OR
       NOT TSL_RELEASE_ARCHIVE_SHA256 MATCHES "^[0-9a-fA-F]+$")
      message(FATAL_ERROR "TSL_RELEASE_ARCHIVE_SHA256 must be a SHA-256 digest")
    endif()
    FetchContent_Declare(
      tsl
      URL "${TSL_RELEASE_ARCHIVE_URL}"
      URL_HASH "SHA256=${TSL_RELEASE_ARCHIVE_SHA256}"
      SOURCE_SUBDIR cpp
    )
    FetchContent_MakeAvailable(tsl)
    set(_tsl_source_id "release:v0.2.7@0a2cbe068ad5984339b3622f70a74003dfacb966:${TSL_RELEASE_ARCHIVE_SHA256}")
  endif()

  set(_base_target "tsl::${IRBENCH_PROFILE}")
  if(NOT TARGET "${_base_target}")
    message(FATAL_ERROR
      "Generated TSL product does not expose requested target ${_base_target}")
  endif()

  if(IRBENCH_ENABLE_CLANG_OVERLAY)
    if(NOT CMAKE_CXX_COMPILER_ID MATCHES "^(AppleClang|Clang)$")
      message(FATAL_ERROR
        "IRBENCH_ENABLE_CLANG_OVERLAY requires Clang; configure GCC builds with it OFF")
    endif()
    include(CheckCXXSourceCompiles)
    check_cxx_source_compiles(
      "#if !__has_builtin(__builtin_elementwise_clzg)\n#error missing __builtin_elementwise_clzg\n#endif\nint main() { return 0; }"
      IRBENCH_CLANG_HAS_ELEMENTWISE_CLZG
    )
    if(NOT IRBENCH_CLANG_HAS_ELEMENTWISE_CLZG)
      message(FATAL_ERROR
        "The generated TSL v0.2.7 Clang overlay requires "
        "__builtin_elementwise_clzg, which this Clang frontend does not provide. "
        "Use a compatible Clang or configure IRBENCH_ENABLE_CLANG_OVERLAY=OFF.")
    endif()
    set(_consumer_target "tsl::${IRBENCH_PROFILE}_clang")
    if(NOT TARGET "${_consumer_target}")
      message(FATAL_ERROR
        "Generated TSL product does not expose requested target ${_consumer_target}")
    endif()
  else()
    set(_consumer_target "${_base_target}")
  endif()

  set(IRBENCH_TSL_TARGET "${_consumer_target}" PARENT_SCOPE)
  set(IRBENCH_TSL_SOURCE_ID "${_tsl_source_id}" PARENT_SCOPE)
endfunction()

function(irbench_load_google_benchmark)
  if(TARGET benchmark::benchmark)
    return()
  endif()

  string(LENGTH "${GBENCH_RELEASE_ARCHIVE_SHA256}" _gbench_hash_length)
  if(NOT _gbench_hash_length EQUAL 64 OR
     NOT GBENCH_RELEASE_ARCHIVE_SHA256 MATCHES "^[0-9a-fA-F]+$")
    message(FATAL_ERROR "GBENCH_RELEASE_ARCHIVE_SHA256 must be a SHA-256 digest")
  endif()
  set(BENCHMARK_ENABLE_TESTING OFF CACHE BOOL "" FORCE)
  set(BENCHMARK_ENABLE_INSTALL OFF CACHE BOOL "" FORCE)
  set(BENCHMARK_ENABLE_GTEST_TESTS OFF CACHE BOOL "" FORCE)
  set(BENCHMARK_ENABLE_WERROR OFF CACHE BOOL "" FORCE)
  FetchContent_Declare(
    googlebenchmark
    URL "${GBENCH_RELEASE_ARCHIVE_URL}"
    URL_HASH "SHA256=${GBENCH_RELEASE_ARCHIVE_SHA256}"
  )
  FetchContent_MakeAvailable(googlebenchmark)
  set(
    IRBENCH_GBENCH_SOURCE_ID
    "release:v1.9.5:${GBENCH_RELEASE_ARCHIVE_SHA256}"
    PARENT_SCOPE
  )
endfunction()
