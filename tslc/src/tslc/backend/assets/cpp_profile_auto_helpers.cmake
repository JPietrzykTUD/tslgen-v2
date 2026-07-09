set(TSL_ONEAPI_FPGA_PROBE_TIMEOUT_SECONDS "30" CACHE STRING "Timeout for generated oneAPI FPGA auto-detection commands")

function(_tsl_output_has_real_fpga output out_var)
  set(_found FALSE)
  string(REPLACE "\r\n" "\n" _normalized "${output}")
  string(REPLACE "\n" ";" _lines "${_normalized}")
  foreach(_line IN LISTS _lines)
    string(TOLOWER "${_line}" _lower)
    if(_lower MATCHES "fpga" AND NOT _lower MATCHES "emulat|simulat")
      set(_found TRUE)
    endif()
  endforeach()
  set(${out_var} "${_found}" PARENT_SCOPE)
endfunction()

function(_tsl_aocl_output_has_device output out_var)
  string(TOLOWER "${output}" _lower)
  string(STRIP "${_lower}" _stripped)
  if(_stripped AND NOT _lower MATCHES "no device|no devices|none detected|not found|error")
    set(${out_var} TRUE PARENT_SCOPE)
  else()
    set(${out_var} FALSE PARENT_SCOPE)
  endif()
endfunction()

function(_tsl_detect_oneapi_fpga out_ready out_reason)
  set(_reasons "")

  find_program(TSL_ONEAPI_FPGA_CXX NAMES icpx dpcpp
    HINTS
      "$ENV{ONEAPI_ROOT}/compiler/latest/bin"
      "$ENV{ONEAPI_ROOT}/compiler/2025.0/bin"
      "/opt/intel/oneapi/compiler/latest/bin"
      "/opt/intel/oneapi/compiler/2025.0/bin"
  )
  if(NOT TSL_ONEAPI_FPGA_CXX AND NOT CMAKE_CXX_COMPILER_ID STREQUAL "IntelLLVM")
    list(APPEND _reasons "icpx/dpcpp was not found")
  endif()
  if(NOT CMAKE_CXX_COMPILER_ID STREQUAL "IntelLLVM")
    list(APPEND _reasons "current CMAKE_CXX_COMPILER_ID is '${CMAKE_CXX_COMPILER_ID}', configure with icpx or dpcpp")
  endif()

  set(_runtime_ready FALSE)
  find_program(TSL_ONEAPI_FPGA_SYCL_LS NAMES sycl-ls
    HINTS
      "$ENV{ONEAPI_ROOT}/compiler/latest/bin"
      "$ENV{ONEAPI_ROOT}/compiler/2025.0/bin"
      "/opt/intel/oneapi/compiler/latest/bin"
      "/opt/intel/oneapi/compiler/2025.0/bin"
  )
  if(TSL_ONEAPI_FPGA_SYCL_LS)
    execute_process(
      COMMAND "${TSL_ONEAPI_FPGA_SYCL_LS}"
      RESULT_VARIABLE _sycl_ls_result
      OUTPUT_VARIABLE _sycl_ls_output
      ERROR_VARIABLE _sycl_ls_error
      TIMEOUT ${TSL_ONEAPI_FPGA_PROBE_TIMEOUT_SECONDS}
    )
    if(_sycl_ls_result STREQUAL "0")
      _tsl_output_has_real_fpga("${_sycl_ls_output}\n${_sycl_ls_error}" _sycl_ls_has_fpga)
      if(_sycl_ls_has_fpga)
        set(_runtime_ready TRUE)
      endif()
    endif()
  endif()
  if(NOT _runtime_ready)
    find_program(TSL_ONEAPI_FPGA_CLINFO NAMES clinfo)
    if(TSL_ONEAPI_FPGA_CLINFO)
      execute_process(
        COMMAND "${TSL_ONEAPI_FPGA_CLINFO}" -l
        RESULT_VARIABLE _clinfo_result
        OUTPUT_VARIABLE _clinfo_output
        ERROR_VARIABLE _clinfo_error
        TIMEOUT ${TSL_ONEAPI_FPGA_PROBE_TIMEOUT_SECONDS}
      )
      if(_clinfo_result STREQUAL "0")
        _tsl_output_has_real_fpga("${_clinfo_output}\n${_clinfo_error}" _clinfo_has_fpga)
        if(_clinfo_has_fpga)
          set(_runtime_ready TRUE)
        endif()
      endif()
    endif()
  endif()
  if(NOT _runtime_ready)
    list(APPEND _reasons "neither sycl-ls nor clinfo -l listed a non-emulation FPGA device")
  endif()

  find_program(TSL_ONEAPI_FPGA_AOCL NAMES aocl
    HINTS
      "$ENV{ONEAPI_ROOT}/compiler/latest/bin"
      "$ENV{ONEAPI_ROOT}/compiler/2025.0/bin"
      "$ENV{ONEAPI_ROOT}/fpga/latest/bin"
      "$ENV{ONEAPI_ROOT}/fpga/2025.0/bin"
      "/opt/intel/oneapi/compiler/latest/bin"
      "/opt/intel/oneapi/compiler/2025.0/bin"
      "/opt/intel/oneapi/fpga/latest/bin"
      "/opt/intel/oneapi/fpga/2025.0/bin"
  )
  if(NOT TSL_ONEAPI_FPGA_AOCL)
    list(APPEND _reasons "aocl was not found")
  else()
    execute_process(
      COMMAND "${TSL_ONEAPI_FPGA_AOCL}" list-devices
      RESULT_VARIABLE _aocl_list_result
      OUTPUT_VARIABLE _aocl_list_output
      ERROR_VARIABLE _aocl_list_error
      TIMEOUT ${TSL_ONEAPI_FPGA_PROBE_TIMEOUT_SECONDS}
    )
    _tsl_aocl_output_has_device("${_aocl_list_output}\n${_aocl_list_error}" _aocl_has_device)
    if(NOT _aocl_list_result STREQUAL "0" OR NOT _aocl_has_device)
      list(APPEND _reasons "aocl list-devices did not report a usable FPGA board")
    endif()

    execute_process(
      COMMAND "${TSL_ONEAPI_FPGA_AOCL}" diagnose
      RESULT_VARIABLE _aocl_diagnose_result
      OUTPUT_VARIABLE _aocl_diagnose_output
      ERROR_VARIABLE _aocl_diagnose_error
      TIMEOUT ${TSL_ONEAPI_FPGA_PROBE_TIMEOUT_SECONDS}
    )
    if(NOT _aocl_diagnose_result STREQUAL "0")
      list(APPEND _reasons "aocl diagnose failed")
    endif()
  endif()

  if(_reasons)
    list(JOIN _reasons "; " _reason_text)
    set(${out_ready} FALSE PARENT_SCOPE)
    set(${out_reason} "${_reason_text}" PARENT_SCOPE)
  else()
    set(${out_ready} TRUE PARENT_SCOPE)
    set(${out_reason} "" PARENT_SCOPE)
  endif()
endfunction()

function(_tsl_detect_profile_gate gate out_ready out_reason)
  if("${gate}" STREQUAL "oneapi_fpga")
    _tsl_detect_oneapi_fpga(_ready _reason)
    set(${out_ready} "${_ready}" PARENT_SCOPE)
    set(${out_reason} "${_reason}" PARENT_SCOPE)
  else()
    set(${out_ready} FALSE PARENT_SCOPE)
    set(${out_reason} "unknown profile auto-detection gate '${gate}'" PARENT_SCOPE)
  endif()
endfunction()
