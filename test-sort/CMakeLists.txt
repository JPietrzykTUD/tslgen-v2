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
set(TSL_RELEASE_VERSION "v0.3.1" CACHE STRING "Generated TSL release tag")
set(
  TSL_RELEASE_ARCHIVE_URL
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
    # The C++ compiler's own sibling first: `clang++-22` -> `clang-22`. A fetched
    # dependency that derives its C flags from the C++ compiler's identity -- Arrow
    # does, and adds clang's `-Qunused-arguments` -- hands them to whatever C
    # compiler CMake picked, and `cc` being gcc turns that into a build failure in
    # somebody else's project. Matching the pair is also simply more correct.
    get_filename_component(_highway_cxx_compiler_name "${CMAKE_CXX_COMPILER}" NAME)
    get_filename_component(_highway_cxx_compiler_dir "${CMAKE_CXX_COMPILER}" DIRECTORY)
    string(REPLACE "clang++" "clang" _highway_sibling "${_highway_cxx_compiler_name}")
    string(REPLACE "g++" "gcc" _highway_sibling "${_highway_sibling}")
    if(NOT _highway_sibling STREQUAL _highway_cxx_compiler_name)
      if(_highway_cxx_compiler_dir)
        list(APPEND _highway_c_compiler_candidates
             "${_highway_cxx_compiler_dir}/${_highway_sibling}")
      endif()
      list(APPEND _highway_c_compiler_candidates "${_highway_sibling}")
    endif()
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
# Q0, the coordinate descent every later number depends on. One object library
# per (style, width) so the nine instantiations of the candidate set compile in
# parallel rather than serialising into one enormous translation unit.
set(_q0_units "")
foreach(_q0_style Intrinsics ClangBuiltin ClangBoolMask)
  foreach(_q0_width 128 256 512)
    set(_q0_name q0_unit_${_q0_style}_${_q0_width})
    add_library(${_q0_name} OBJECT benchmarks/q0_tune_unit.cpp)
    target_compile_features(${_q0_name} PRIVATE cxx_std_17)
    target_compile_definitions(
      ${_q0_name} PRIVATE TSL_Q0_STYLE=${_q0_style} TSL_Q0_WIDTH=${_q0_width}
    )
    target_link_libraries(${_q0_name} PRIVATE tsl::tsl Threads::Threads)
    list(APPEND _q0_units ${_q0_name})
  endforeach()
endforeach()

add_executable(bench_q0_tune benchmarks/bench_q0_tune.cpp)
target_compile_features(bench_q0_tune PRIVATE cxx_std_17)
target_link_libraries(bench_q0_tune PRIVATE tsl::tsl Threads::Threads)
foreach(_q0_unit ${_q0_units})
  target_sources(bench_q0_tune PRIVATE $<TARGET_OBJECTS:${_q0_unit}>)
endforeach()

add_executable(bench_q4_scaling benchmarks/bench_q4_scaling.cpp)
target_compile_features(bench_q4_scaling PRIVATE cxx_std_17)
target_link_libraries(bench_q4_scaling PRIVATE tsl::tsl Threads::Threads)

# --- measurement builds collect nothing ------------------------------------------
# A build made for publishing numbers should be incapable of collecting counters,
# not merely configured not to. This compiles the element and range counters out of
# both sorters: the entry points funnel the caller's metrics pointer through
# `tsl_metrics_or_null`, which returns a statically-known null, so every guarded
# increment folds away. Measured on tpcds_q064 at twenty-four workers, the atomic
# counters on the parallel index-sort path cost 1.17x -- twenty fetch_adds across
# 986,867 task-tree nodes.
#
# Off by default so tests and diagnostic tools keep their counters. The `bench`
# preset turns it on for exactly the targets that publish numbers.
option(TSL_COSORT_NO_INSTRUMENTATION
       "Compile the sorters' counters out: for builds that publish measurements" OFF)

# The (style, register width) cell the reporting drivers are built for. Q0 explores
# all nine; a driver can only be built for one, because both are template
# parameters sitting under a configuration dispatch that is already 36
# instantiations per key width. So the cell is a build parameter, `run_all.sh`
# probes Q0 for the winner before building the rest, and the full Q0 run re-checks
# the choice and says so if the built cell is more than 10% off.
# ClangBoolMask, not Intrinsics. Measured in pairs at a fixed sixteen lanes, the
# packed-boolean-mask overlay is at least as fast as hand-written intrinsics on
# every shape tried and 2-5% faster on three of four; the lane-mask overlay is
# never faster and costs up to 46%. On AVX-512 that is what the encoding predicts:
# a packed boolean mask *is* a `k` register, where a lane-wide compare result has
# to be converted into one for every masked operation. See probe_paired_styles and
# docs/benchmark-plan.md. Override per host if its ordering differs.
set(TSL_COSORT_MEASURE_STYLE "ClangBoolMask" CACHE STRING
    "TslStyle the reporting drivers measure with: Intrinsics|ClangBuiltin|ClangBoolMask")
set(TSL_COSORT_MEASURE_WIDTH "512" CACHE STRING
    "Register width in bits the reporting drivers measure with: 128|256|512")

# Targets whose output is a published number. Kept as a list because the property
# has to follow every one of them, and a driver added without it would silently
# publish instrumented numbers.
set(TSL_COSORT_MEASURING_TARGETS
    bench_q0_tune bench_q1_baselines bench_q2_algorithms bench_q3_detection
    bench_q4_scaling cosort_bench)

# --- Q1 external baselines ----------------------------------------------------
# Off by default, following the QPL/DML pattern: the default build stays
# dependency-free and no test acquires a hidden network requirement. When asked
# for, the build acquires what it can and says precisely what it cannot, per host,
# so a second machine needs this flag and nothing else remembered.
#
#   -DTSL_COSORT_ENABLE_BASELINES=ON
#
# Fetched automatically (headers, pinned commits, no system package):
#   IPS4o            state-of-the-art parallel comparison sort
#   x86-simd-sort    Intel's AVX-512 argsort, single-column rows
#   oneTBB           only if no system TBB is found
#
# From the system, because building them here is not worth the minutes:
#   TBB      libtbb-dev            execution::par, and IPS4o's parallel sort
#   Arrow    libarrow-dev          SortIndices, the semantically equal baseline
#   atomic   libatomic1            IPS4o's 16-byte compare-and-exchange
#
# A missing optional baseline is not an error: its rows are emitted as drops
# naming the reason, so a run from a host without it is visibly incomplete rather
# than quietly shorter. A missing *required* piece is a fatal error, because a
# handicapped competitor is worse than an absent one.
option(TSL_COSORT_ENABLE_BASELINES
       "Fetch IPS4o and x86-simd-sort and build the Q1 baseline comparison" OFF)
option(TSL_COSORT_FETCH_TBB
       "Build oneTBB from source when the system has none" ON)

if(TSL_COSORT_ENABLE_BASELINES)
  set(_q1_present)
  set(_q1_absent)

  FetchContent_Declare(
    ips4o
    GIT_REPOSITORY https://github.com/ips4o/ips4o.git
    GIT_TAG        08a5b926ee65cef19139057c6bde02bb5542c1cb
    GIT_SHALLOW    FALSE
  )
  FetchContent_Declare(
    x86simdsort
    GIT_REPOSITORY https://github.com/intel/x86-simd-sort.git
    GIT_TAG        fa944efbea1a33426b3f8a9a21e23794ab8aa300
    GIT_SHALLOW    FALSE
  )
  # Both are consumed as headers; neither project's own CMake is run, because
  # IPS4o's would go looking for its own TBB and libatomic.
  FetchContent_Populate(ips4o)
  FetchContent_Populate(x86simdsort)
  list(APPEND _q1_present "ips4o (fetched)" "x86-simd-sort (fetched)")

  add_executable(bench_q1_baselines benchmarks/bench_q1_baselines.cpp)
  target_compile_features(bench_q1_baselines PRIVATE cxx_std_17)
  target_include_directories(
    bench_q1_baselines PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/include"
    "${CMAKE_CURRENT_SOURCE_DIR}/benchmarks"
    "${ips4o_SOURCE_DIR}/include"
    "${x86simdsort_SOURCE_DIR}/src"
  )
  target_compile_definitions(
    bench_q1_baselines PRIVATE TSL_COSORT_HAVE_IPS4O=1 TSL_COSORT_HAVE_XSS=1
  )
  # IPS4o exposes `ips4o::parallel` only under _REENTRANT, which -pthread defines.
  # Threads::Threads alone does not guarantee the macro, so it is explicit.
  target_compile_options(bench_q1_baselines PRIVATE -pthread)
  target_link_libraries(bench_q1_baselines PRIVATE tsl::tsl Threads::Threads)

  # --- TBB: required, because without it execution::par is silently serial ------
  find_package(TBB QUIET)
  if(NOT TBB_FOUND AND TSL_COSORT_FETCH_TBB)
    message(STATUS "bench_q1_baselines: no system TBB; building oneTBB from source")
    set(TBB_TEST OFF CACHE BOOL "" FORCE)
    set(TBB_EXAMPLES OFF CACHE BOOL "" FORCE)
    set(TBB_STRICT OFF CACHE BOOL "" FORCE)
    FetchContent_Declare(
      onetbb
      GIT_REPOSITORY https://github.com/uxlfoundation/oneTBB.git
      GIT_TAG        v2022.0.0
      GIT_SHALLOW    TRUE
    )
    FetchContent_MakeAvailable(onetbb)
    if(TARGET TBB::tbb)
      set(TBB_FOUND TRUE)
      list(APPEND _q1_present "oneTBB (built from source)")
    endif()
  elseif(TBB_FOUND)
    list(APPEND _q1_present "TBB (system)")
  endif()
  if(TBB_FOUND)
    target_link_libraries(bench_q1_baselines PRIVATE TBB::tbb)
  else()
    message(FATAL_ERROR
      "bench_q1_baselines needs TBB: without it libstdc++ runs "
      "std::sort(std::execution::par) serially, which would silently turn the "
      "parallel baseline into a second serial one and invert the comparison. "
      "Install it (Debian/Ubuntu: apt-get install libtbb-dev; Fedora/RHEL: dnf "
      "install tbb-devel) or leave TSL_COSORT_FETCH_TBB=ON to build it here.")
  endif()

  # --- libatomic: required, for IPS4o's 16-byte compare-and-exchange ------------
  # The versioned soname is searched too: a runtime-only install has
  # libatomic.so.1 without the libatomic.so development symlink, and IPS4o's
  # parallel path needs __atomic_fetch_add_16 either way. Disabling its 16-byte
  # compare-and-exchange would handicap the baseline, which defeats the purpose.
  find_library(TSL_LIBATOMIC NAMES atomic libatomic.so.1)
  if(TSL_LIBATOMIC)
    target_link_libraries(bench_q1_baselines PRIVATE ${TSL_LIBATOMIC})
  else()
    message(FATAL_ERROR
      "bench_q1_baselines needs libatomic for IPS4o's __atomic_fetch_add_16 "
      "(Debian/Ubuntu: apt-get install libatomic1; Fedora/RHEL: dnf install "
      "libatomic). Its parallel sort is the strongest baseline here and running "
      "it without 16-byte atomics would understate it.")
  endif()

  # --- Arrow: fetched, so both machines measure the same one --------------------
  # SortIndices over a table with one sort key per column is literally this
  # operation, so Arrow is the baseline whose result cannot be dismissed -- which
  # makes "whatever the distribution packaged" the wrong way to get it. One host
  # had Arrow 23 and another an Arrow predating `arrow/compute/initialize.h`, so
  # the same source failed to compile on the second machine, and even had it
  # compiled the two would have been comparing against different Arrows.
  #
  # Fetching it is wired up and *not* the default, because it does not currently
  # work here: apache-arrow-23.0.0 fails to compile with clang 22 inside
  # `arrow/util/dispatch_internal.h`, an upstream incompatibility rather than
  # anything about this wiring. Distribution packages are built with gcc, which is
  # why the system one works. Set TSL_COSORT_ARROW_FETCH=ON on a host with an older
  # clang or with gcc to get a pinned Arrow identical across machines; otherwise
  # the system one is used and its version is probed, so a host with an Arrow
  # predating `arrow/compute/initialize.h` still builds.
  option(TSL_COSORT_ARROW_FETCH
         "Fetch and build a pinned Arrow instead of using the system one" OFF)
  if(TSL_COSORT_ARROW_FETCH)
    set(TSL_COSORT_ARROW_FROM_SYSTEM OFF)
  else()
    set(TSL_COSORT_ARROW_FROM_SYSTEM ON)
  endif()
  set(TSL_COSORT_ARROW_TAG "apache-arrow-23.0.0" CACHE STRING
      "Arrow release tag to fetch for the Q1 baseline")

  set(_arrow_target "")
  if(TSL_COSORT_ARROW_FROM_SYSTEM)
    find_package(Arrow QUIET)
    if(Arrow_FOUND)
      if(TARGET Arrow::arrow_shared)
        set(_arrow_target Arrow::arrow_shared)
      else()
        set(_arrow_target arrow)
      endif()
      find_library(TSL_ARROW_COMPUTE NAMES arrow_compute)
      if(TSL_ARROW_COMPUTE)
        list(APPEND _arrow_target ${TSL_ARROW_COMPUTE})
      endif()
      set(_arrow_label "Arrow ${Arrow_VERSION} (system)")
    else()
      list(APPEND _q1_absent
           "Arrow -- TSL_COSORT_ARROW_FROM_SYSTEM=ON but none found. Its rows will "
           "be drops.")
    endif()
  else()
    # Everything Arrow can build is turned off except the compute kernels the
    # baseline needs. Bundled thirdparty, so the fetch does not depend on what the
    # host happens to have installed.
    set(ARROW_BUILD_SHARED OFF CACHE BOOL "" FORCE)
    set(ARROW_BUILD_STATIC ON CACHE BOOL "" FORCE)
    set(ARROW_COMPUTE ON CACHE BOOL "" FORCE)
    set(ARROW_BUILD_TESTS OFF CACHE BOOL "" FORCE)
    set(ARROW_BUILD_BENCHMARKS OFF CACHE BOOL "" FORCE)
    set(ARROW_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
    set(ARROW_BUILD_UTILITIES OFF CACHE BOOL "" FORCE)
    set(ARROW_BUILD_INTEGRATION OFF CACHE BOOL "" FORCE)
    set(ARROW_CSV OFF CACHE BOOL "" FORCE)
    set(ARROW_JSON OFF CACHE BOOL "" FORCE)
    set(ARROW_PARQUET OFF CACHE BOOL "" FORCE)
    set(ARROW_IPC OFF CACHE BOOL "" FORCE)
    set(ARROW_FILESYSTEM OFF CACHE BOOL "" FORCE)
    set(ARROW_DATASET OFF CACHE BOOL "" FORCE)
    set(ARROW_ACERO OFF CACHE BOOL "" FORCE)
    set(ARROW_FLIGHT OFF CACHE BOOL "" FORCE)
    set(ARROW_JEMALLOC OFF CACHE BOOL "" FORCE)
    set(ARROW_MIMALLOC OFF CACHE BOOL "" FORCE)
    set(ARROW_WITH_RE2 OFF CACHE BOOL "" FORCE)
    set(ARROW_WITH_UTF8PROC OFF CACHE BOOL "" FORCE)
    set(ARROW_DEPENDENCY_SOURCE "BUNDLED" CACHE STRING "" FORCE)
    set(ARROW_SIMD_LEVEL "AVX512" CACHE STRING "" FORCE)
    FetchContent_Declare(
      arrow
      GIT_REPOSITORY https://github.com/apache/arrow.git
      GIT_TAG        ${TSL_COSORT_ARROW_TAG}
      GIT_SHALLOW    TRUE
      SOURCE_SUBDIR  cpp
    )
    FetchContent_MakeAvailable(arrow)
    if(TARGET arrow_static)
      set(_arrow_target arrow_static)
    elseif(TARGET arrow_shared)
      set(_arrow_target arrow_shared)
    endif()
    if(TARGET arrow_compute_static)
      list(APPEND _arrow_target arrow_compute_static)
    elseif(TARGET arrow_compute_shared)
      list(APPEND _arrow_target arrow_compute_shared)
    endif()
    if(_arrow_target)
      set(_arrow_label "Arrow ${TSL_COSORT_ARROW_TAG} (fetched)")
    else()
      list(APPEND _q1_absent
           "Arrow -- the fetch produced no usable target. Its rows will be drops.")
    endif()
  endif()

  if(_arrow_target)
    # Probed by *linking*, not by looking for a header.
    #
    # `arrow/compute/initialize.h` arrived in Arrow 14; before that libarrow
    # registered the kernels itself and there is nothing to call. So the call has to
    # be conditional -- but the previous test asked whether the header exists while
    # the link line added `libarrow_compute` only `if(TSL_ARROW_COMPUTE)` found it.
    # Two different questions, and nothing checked they agreed. On a host whose
    # Arrow has the header but keeps compute in a library CMake did not find, the
    # call was compiled and could not be linked:
    #
    #   undefined reference to `arrow::compute::Initialize()'
    #
    # at 100% of the build, after everything else had compiled. `check_cxx_source_
    # compiles` builds an executable, so it answers the question that matters --
    # can this call be linked with these libraries -- and covers the split-library
    # case, an ABI change, and a wrong-arch library equally.
    # Only on the system path. A fetched Arrow's `arrow_static` is a target *this*
    # build produces, so no library file exists while CMake is configuring and any
    # link probe against it fails for a reason that has nothing to do with Arrow --
    # which would drop the one path that reliably works. There the header probe is
    # both sufficient and all that is possible: the tag is pinned and
    # `ARROW_COMPUTE=ON` is forced above, so compute is there by construction.
    include(CheckIncludeFileCXX)
    include(CheckCXXSourceCompiles)
    set(_arrow_saved_includes "${CMAKE_REQUIRED_INCLUDES}")
    set(_arrow_saved_libraries "${CMAKE_REQUIRED_LIBRARIES}")
    foreach(_t IN LISTS _arrow_target)
      if(TARGET ${_t})
        get_target_property(_inc ${_t} INTERFACE_INCLUDE_DIRECTORIES)
        if(_inc)
          list(APPEND CMAKE_REQUIRED_INCLUDES ${_inc})
        endif()
      endif()
    endforeach()
    if(TSL_COSORT_ARROW_FROM_SYSTEM)
      list(APPEND CMAKE_REQUIRED_LIBRARIES ${_arrow_target})
      check_cxx_source_compiles("
        #include <arrow/compute/initialize.h>
        int main() { return arrow::compute::Initialize().ok() ? 0 : 1; }
      " TSL_ARROW_INITIALIZE_LINKS)
      # And the call the baseline exists for, so a broken Arrow is found here
      # rather than at 100% of the build or, worse, at runtime.
      check_cxx_source_compiles("
        #include <arrow/api.h>
        #include <arrow/compute/api_vector.h>
        int main() {
          arrow::compute::SortOptions options;
          auto result = arrow::compute::SortIndices(arrow::Datum{}, options);
          return result.ok() ? 0 : 1;
        }
      " TSL_ARROW_SORT_INDICES_LINKS)
    else()
      # Read off the pinned tag, not probed. A FetchContent target expresses its
      # include directories as `$<BUILD_INTERFACE:...>` generator expressions, which
      # `CMAKE_REQUIRED_INCLUDES` cannot evaluate while CMake is still configuring --
      # so the probe got no `-I` at all and reported the header missing every time,
      # on every host, for a tree that plainly contains it. The consequence was not
      # a build failure but a quiet one: `Initialize()` went uncalled against a
      # *static* Arrow, which is exactly where it is needed, because nothing else
      # pulls the compute kernels' registration objects out of the archive.
      #
      # The tag is ours and pinned, so its version is known rather than discovered.
      string(REGEX MATCH "([0-9]+)\\.[0-9]+\\.[0-9]+" _arrow_ver
             "${TSL_COSORT_ARROW_TAG}")
      set(_arrow_major "${CMAKE_MATCH_1}")
      if(_arrow_major AND _arrow_major GREATER_EQUAL 14)
        set(TSL_ARROW_INITIALIZE_LINKS TRUE)
      else()
        # Before Arrow 14 libarrow registered the kernels itself and there is
        # nothing to call.
        set(TSL_ARROW_INITIALIZE_LINKS FALSE)
      endif()
      set(TSL_ARROW_SORT_INDICES_LINKS TRUE)
    endif()
    set(CMAKE_REQUIRED_INCLUDES "${_arrow_saved_includes}")
    set(CMAKE_REQUIRED_LIBRARIES "${_arrow_saved_libraries}")

    if(NOT TSL_ARROW_SORT_INDICES_LINKS)
      # Arrow is present but its compute kernels cannot be linked. Dropped rather
      # than allowed to break the build: the other Q1 baselines are independent of
      # it, and a row that says why is worth more than a build that stops.
      list(APPEND _q1_absent
           "${_arrow_label} -- found, but arrow::compute::SortIndices does not "
           "link. Modern Arrow keeps the kernels in a separate libarrow_compute; if "
           "this host has none, build a pinned Arrow instead: run_paper.sh --arrow "
           "fetch, or -DTSL_COSORT_ARROW_FETCH=ON. Note that the pinned release "
           "does not compile with every clang -- see TSL_COSORT_ARROW_TAG. Its rows "
           "will be drops.")
    else()
      # Announced only now: whether Arrow is *usable* is what the reader needs,
      # and until the probe above ran, "found" and "usable" were the same claim.
      list(APPEND _q1_present "${_arrow_label}")
      target_compile_definitions(bench_q1_baselines PRIVATE TSL_COSORT_HAVE_ARROW=1)
      target_link_libraries(bench_q1_baselines PRIVATE ${_arrow_target})
      if(TSL_ARROW_INITIALIZE_LINKS)
        target_compile_definitions(
          bench_q1_baselines PRIVATE TSL_COSORT_ARROW_HAS_INITIALIZE=1
        )
      endif()
    endif()
  endif()

  message(STATUS "bench_q1_baselines will compare against:")
  foreach(_entry IN LISTS _q1_present)
    message(STATUS "    + ${_entry}")
  endforeach()
  foreach(_entry IN LISTS _q1_absent)
    message(STATUS "    - ${_entry}")
  endforeach()
endif()

add_executable(bench_q3_detection benchmarks/bench_q3_detection.cpp)
target_compile_features(bench_q3_detection PRIVATE cxx_std_17)
target_link_libraries(bench_q3_detection PRIVATE tsl::tsl Threads::Threads)

add_executable(bench_q2_algorithms benchmarks/bench_q2_algorithms.cpp)
target_compile_features(bench_q2_algorithms PRIVATE cxx_std_17)
target_link_libraries(bench_q2_algorithms PRIVATE tsl::tsl Threads::Threads)

add_executable(bench_samplesort_multicolumn EXCLUDE_FROM_ALL benchmarks/deprecated/bench_samplesort_multicolumn.cpp)
target_compile_features(bench_samplesort_multicolumn PRIVATE cxx_std_17)
target_link_libraries(bench_samplesort_multicolumn PRIVATE tsl::tsl Threads::Threads)

# The worklist scheduler an asynchronous detector needs: termination that counts
# the device's outstanding work, an idle worker that polls rather than sleeps, and
# a published range that outlives the frame that produced it. It touches neither
# TSL nor an accelerator, so it builds and runs anywhere.
add_executable(test_pending_range_queue tests/test_pending_range_queue.cpp)
target_compile_features(test_pending_range_queue PRIVATE cxx_std_17)
target_include_directories(test_pending_range_queue PRIVATE include)
target_link_libraries(test_pending_range_queue PRIVATE Threads::Threads)
add_test(NAME test_pending_range_queue COMMAND test_pending_range_queue)

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
  # Both measurement paths are compiled while both exist: --paper-csv runs the
  # cases through paper_harness.hpp and writes the shared schema, and without it
  # they go to Google Benchmark as before. Dropping this define drops the old path.
  target_compile_definitions(cosort_bench PRIVATE TSL_COSORT_WITH_GBENCH=1)
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

# Applied last, so every measuring target exists by now.
if(TSL_COSORT_NO_INSTRUMENTATION)
  foreach(_measuring IN LISTS TSL_COSORT_MEASURING_TARGETS)
    if(TARGET ${_measuring})
      target_compile_definitions(${_measuring} PRIVATE TSL_COSORT_NO_INSTRUMENTATION=1)
      message(STATUS "${_measuring}: counters compiled out")
    endif()
  endforeach()
  # Q0's per-cell units are separate object libraries and need it too.
  foreach(_style Intrinsics ClangBuiltin ClangBoolMask)
    foreach(_width 128 256 512)
      set(_unit "q0_unit_${_style}_${_width}")
      if(TARGET ${_unit})
        target_compile_definitions(${_unit} PRIVATE TSL_COSORT_NO_INSTRUMENTATION=1)
      endif()
    endforeach()
  endforeach()
endif()

# The measurement cell, applied to every target that publishes a number.
foreach(_measuring IN LISTS TSL_COSORT_MEASURING_TARGETS)
  if(TARGET ${_measuring})
    target_compile_definitions(
      ${_measuring} PRIVATE
      TSL_COSORT_MEASURE_STYLE=${TSL_COSORT_MEASURE_STYLE}
      TSL_COSORT_MEASURE_WIDTH=${TSL_COSORT_MEASURE_WIDTH}
    )
  endif()
endforeach()
message(STATUS "reporting drivers measure with ${TSL_COSORT_MEASURE_STYLE}/${TSL_COSORT_MEASURE_WIDTH}-bit")

# --- paired-comparison probes ---------------------------------------------------
# Two questions the reporting drivers cannot answer, because they compare costs
# that differ by less than the machine's drift: whether the three implementation
# styles differ at a fixed lane count, and whether a knob's response curve is a
# function of lane count alone. Both need interleaved measurement -- see
# `tsl_paper_compare` -- so they live as small probes rather than as another axis
# bolted onto a driver whose job is reporting.
#
# EXCLUDE_FROM_ALL: they answer a question once and are not part of a paper run.
#   cmake --build <dir> --target probe_paired_styles probe_lane_curves
foreach(_probe probe_paired_styles probe_lane_curves)
  add_executable(${_probe} EXCLUDE_FROM_ALL benchmarks/${_probe}.cpp)
  target_compile_features(${_probe} PRIVATE cxx_std_17)
  target_include_directories(
    ${_probe} PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/include" "${CMAKE_CURRENT_SOURCE_DIR}/benchmarks"
  )
  # A probe measures, so it collects nothing while it does.
  target_compile_definitions(${_probe} PRIVATE TSL_COSORT_NO_INSTRUMENTATION=1)
  target_link_libraries(${_probe} PRIVATE tsl::tsl Threads::Threads)
endforeach()
# The style probe needs the clang families to exist at all.
if(_cosort_clang_style)
  target_compile_definitions(
    probe_paired_styles PRIVATE TSL_ENABLE_CLANG TSL_COSORT_HAVE_CLANG_STYLE=1
  )
  if(TSL_COSORT_HAVE_EXT_VECTOR_TYPE_BOOLEAN)
    target_compile_definitions(
      probe_paired_styles PRIVATE TSL_COSORT_HAVE_CLANG_BOOL_STYLE=1
    )
  endif()
endif()
