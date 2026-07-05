cmake_minimum_required(VERSION 3.20)
project(tsl_cpp_examples CXX)

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
  "${CMAKE_CURRENT_LIST_DIR}/../../tslctmp/examples/generated"
  CACHE PATH
  "Path to a generated TSL output root containing cpp/CMakeLists.txt"
)

set(
  TSL_GENERATED_CPP_DIR
  "${CMAKE_CURRENT_LIST_DIR}/../../tslctmp/examples/generated/cpp"
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

add_executable(binary_operator binary_operator.cpp)
target_link_libraries(binary_operator PRIVATE tsl::tsl)

add_executable(chunk_operator chunk_operator.cpp)
target_link_libraries(chunk_operator PRIVATE tsl::tsl)

add_executable(range_operator range_operator.cpp)
target_link_libraries(range_operator PRIVATE tsl::tsl)

add_executable(predicate_operator predicate_operator.cpp)
target_link_libraries(predicate_operator PRIVATE tsl::tsl)

add_executable(where_operator where_operator.cpp)
target_link_libraries(where_operator PRIVATE tsl::tsl)

add_executable(masked_operator masked_operator.cpp)
target_link_libraries(masked_operator PRIVATE tsl::tsl)

add_executable(native_mask_operator native_mask_operator.cpp)
target_link_libraries(native_mask_operator PRIVATE tsl::tsl)

add_executable(byte_mask_operator byte_mask_operator.cpp)
target_link_libraries(byte_mask_operator PRIVATE tsl::tsl)

add_executable(bit_mask_operator bit_mask_operator.cpp)
target_link_libraries(bit_mask_operator PRIVATE tsl::tsl)

add_executable(selection_operator selection_operator.cpp)
target_link_libraries(selection_operator PRIVATE tsl::tsl)

add_executable(masked_selection_operator masked_selection_operator.cpp)
target_link_libraries(masked_selection_operator PRIVATE tsl::tsl)

add_executable(selection_vector_operator selection_vector_operator.cpp)
target_link_libraries(selection_vector_operator PRIVATE tsl::tsl)

add_executable(selected_transform_operator selected_transform_operator.cpp)
target_link_libraries(selected_transform_operator PRIVATE tsl::tsl)

add_executable(selected_refinement_operator selected_refinement_operator.cpp)
target_link_libraries(selected_refinement_operator PRIVATE tsl::tsl)

add_executable(selected_aggregate_consume_operator selected_aggregate_consume_operator.cpp)
target_link_libraries(selected_aggregate_consume_operator PRIVATE tsl::tsl)

add_executable(count_operator count_operator.cpp)
target_link_libraries(count_operator PRIVATE tsl::tsl)

add_executable(aggregation_operator aggregation_operator.cpp)
target_link_libraries(aggregation_operator PRIVATE tsl::tsl)

add_executable(masked_aggregation_operator masked_aggregation_operator.cpp)
target_link_libraries(masked_aggregation_operator PRIVATE tsl::tsl)

add_executable(consume_operator consume_operator.cpp)
target_link_libraries(consume_operator PRIVATE tsl::tsl)

add_executable(masked_consume_operator masked_consume_operator.cpp)
target_link_libraries(masked_consume_operator PRIVATE tsl::tsl)

enable_testing()
add_test(NAME unary_operator COMMAND unary_operator)
add_test(NAME binary_operator COMMAND binary_operator)
add_test(NAME chunk_operator COMMAND chunk_operator)
add_test(NAME range_operator COMMAND range_operator)
add_test(NAME predicate_operator COMMAND predicate_operator)
add_test(NAME where_operator COMMAND where_operator)
add_test(NAME masked_operator COMMAND masked_operator)
add_test(NAME native_mask_operator COMMAND native_mask_operator)
add_test(NAME byte_mask_operator COMMAND byte_mask_operator)
add_test(NAME bit_mask_operator COMMAND bit_mask_operator)
add_test(NAME selection_operator COMMAND selection_operator)
add_test(NAME masked_selection_operator COMMAND masked_selection_operator)
add_test(NAME selection_vector_operator COMMAND selection_vector_operator)
add_test(NAME selected_transform_operator COMMAND selected_transform_operator)
add_test(NAME selected_refinement_operator COMMAND selected_refinement_operator)
add_test(NAME selected_aggregate_consume_operator COMMAND selected_aggregate_consume_operator)
add_test(NAME count_operator COMMAND count_operator)
add_test(NAME aggregation_operator COMMAND aggregation_operator)
add_test(NAME masked_aggregation_operator COMMAND masked_aggregation_operator)
add_test(NAME consume_operator COMMAND consume_operator)
add_test(NAME masked_consume_operator COMMAND masked_consume_operator)
