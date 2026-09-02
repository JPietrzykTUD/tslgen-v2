"""Generated C++ wrapping arithmetic has defined overflow behavior."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import textwrap

import pytest

from tslc.api import generate_project, write_artifacts
from tslc.diagnostics import has_errors

pytestmark = pytest.mark.generated_build


@pytest.mark.parametrize("compiler_name", ("g++", "clang++"))
def test_scalar_and_generic_wrapping_arithmetic_is_ubsan_clean(
    data_root: Path,
    machine_profiles_path: Path,
    tmp_path: Path,
    compiler_name: str,
) -> None:
    compiler = shutil.which(compiler_name)
    if compiler is None:
        pytest.skip(f"{compiler_name} is required")

    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["add", "sub", "mul", "neg"],
        profiles=["scalar"],
        type_tags=("si16", "si32"),
        backends=("cpp",),
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics

    source = tmp_path / "wrapping-arithmetic.cpp"
    source.write_text(
        textwrap.dedent(
            """
            #include <cstdint>
            #include <limits>
            #include <tsl.hpp>

            volatile std::int32_t runtime_i32_max =
                std::numeric_limits<std::int32_t>::max();
            volatile std::int32_t runtime_i32_min =
                std::numeric_limits<std::int32_t>::min();
            volatile std::int16_t runtime_i16_max =
                std::numeric_limits<std::int16_t>::max();

            int main() {
              const auto maximum = runtime_i32_max;
              const auto minimum = runtime_i32_min;
              using Scalar32 = tsl::simd<std::int32_t, tsl::scalar>;
              if (tsl::add<Scalar32>(maximum, 1) != minimum) return 1;
              if (tsl::sub<Scalar32>(minimum, 1) != maximum) return 2;
              if (tsl::mul<Scalar32>(maximum, 2) != -2) return 3;
              if (tsl::neg<Scalar32>(minimum) != minimum) return 4;

              using Scalar16 = tsl::simd<std::int16_t, tsl::scalar>;
              const auto maximum16 = runtime_i16_max;
              if (tsl::mul<Scalar16>(maximum16, maximum16) != 1) return 5;

              using Generic = tsl::simd<std::int32_t, tsl::generic<4>>;
              const auto equal = [](
                  const Generic::register_type& left,
                  const Generic::register_type& right) {
                for (std::size_t lane = 0; lane < 4; ++lane) {
                  if (left[lane] != right[lane]) return false;
                }
                return true;
              };
              const Generic::register_type add_left{
                  maximum, minimum, maximum, minimum};
              const Generic::register_type add_right{1, -1, 1, -1};
              const auto add_zero =
                  tsl::add_maskz<Generic>(0b1010, add_left, add_right);
              const auto add_pass =
                  tsl::add_mask<Generic>(0b1010, add_left, add_right);
              if (!equal(
                      add_zero,
                      Generic::register_type{0, maximum, 0, maximum})) return 6;
              if (!equal(
                      add_pass,
                      Generic::register_type{
                          maximum, maximum, maximum, maximum})) return 7;

              const Generic::register_type sub_left{
                  minimum, minimum, maximum, maximum};
              const Generic::register_type sub_right{1, 1, -1, -1};
              const auto sub_zero =
                  tsl::sub_maskz<Generic>(0b1010, sub_left, sub_right);
              const auto sub_pass =
                  tsl::sub_mask<Generic>(0b1010, sub_left, sub_right);
              if (!equal(
                      sub_zero,
                      Generic::register_type{0, maximum, 0, minimum})) return 8;
              if (!equal(
                      sub_pass,
                      Generic::register_type{
                          minimum, maximum, maximum, minimum})) return 9;

              const Generic::register_type factors{
                  maximum, maximum, maximum, maximum};
              const Generic::register_type twos{2, 2, 2, 2};
              const auto mul_zero =
                  tsl::mul_maskz<Generic>(0b1010, factors, twos);
              const auto mul_pass =
                  tsl::mul_mask<Generic>(0b1010, factors, twos);
              if (!equal(
                      mul_zero,
                      Generic::register_type{0, -2, 0, -2})) return 10;
              if (!equal(
                      mul_pass,
                      Generic::register_type{
                          maximum, -2, maximum, -2})) return 11;
              return 0;
            }
            """
        ).lstrip(),
        encoding="utf-8",
    )
    binary = tmp_path / "wrapping-arithmetic"
    compiled = subprocess.run(
        (
            compiler,
            "-std=c++17",
            "-O1",
            "-g",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fsanitize=undefined",
            "-fno-sanitize-recover=undefined",
            "-DTSL_PROFILE_SCALAR=1",
            f"-I{tmp_path / 'cpp' / 'include'}",
            str(source),
            "-o",
            str(binary),
        ),
        check=False,
        capture_output=True,
        text=True,
    )
    assert compiled.returncode == 0, compiled.stderr + compiled.stdout
    environment = os.environ.copy()
    environment["UBSAN_OPTIONS"] = "halt_on_error=1:print_stacktrace=1"
    executed = subprocess.run(
        (str(binary),),
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert executed.returncode == 0, executed.stderr + executed.stdout
