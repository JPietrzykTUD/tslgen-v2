from pathlib import Path

from tslgen.domain.machine_profiles import (
    FeatureFlagName,
    FeatureFlagSpelling,
    MachineFeatureAlternative,
    MachineProfileFamily,
    MachineProfileName,
)
from tslgen.pipeline.machine_profiles import (
    build_machine_feature_profile_catalog,
    load_machine_feature_profile_catalog,
    parse_feature_flag_normalizations,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FLAGS_PATH = _REPO_ROOT / "tsldata" / "detail" / "flags.tsl"
_PROFILE_PATH = _REPO_ROOT / "supplementary" / "buildsystem" / "machine_profiles.json"


def _flag_catalog():
    result = parse_feature_flag_normalizations(
        _FLAGS_PATH.read_text(encoding="utf-8"),
        _FLAGS_PATH,
    )
    assert result.diagnostics == ()
    assert result.catalog is not None
    return result.catalog


def _build_profiles(json_text: str):
    result = build_machine_feature_profile_catalog(
        json_text,
        Path("profiles.json"),
        _flag_catalog(),
    )
    return result


def test_m189_product_profiles_load_as_typed_catalog() -> None:
    result = load_machine_feature_profile_catalog(_PROFILE_PATH, _FLAGS_PATH)

    assert result.diagnostics == ()
    assert result.flag_catalog is not None
    assert result.flag_catalog.normalize("avx3f") == FeatureFlagName("avx512f")
    assert result.flag_catalog.normalize("avx512er") == FeatureFlagName("avx512er")
    assert result.flag_catalog.normalize("sse4_1") == FeatureFlagName("sse4_1")
    assert result.catalog is not None
    assert len(result.catalog.profiles) == 18

    scalar = result.catalog.get(
        MachineProfileFamily("generic"),
        MachineProfileName("scalar"),
    )
    assert scalar is not None
    assert scalar.features == ()
    assert scalar.alternatives == ()

    avx2 = result.catalog.get("x86", "avx2")
    assert avx2 is not None
    assert tuple(str(feature) for feature in avx2.features) == (
        "sse",
        "sse2",
        "ssse3",
        "sse4_1",
        "sse4_2",
        "avx",
        "avx2",
    )

    knl = result.catalog.get("x86", "knl")
    assert knl is not None
    assert "avx512er" in {str(feature) for feature in knl.features}
    assert "avx512pf" in {str(feature) for feature in knl.features}


def test_m189_build_options_preserve_profile_metadata_without_compiler_policy() -> None:
    result = load_machine_feature_profile_catalog(_PROFILE_PATH, _FLAGS_PATH)
    assert result.diagnostics == ()
    assert result.catalog is not None

    selection = result.catalog.select_build_options("x86", "icelake-rockerlake")

    assert selection.diagnostics == ()
    assert selection.build_options is not None
    assert selection.build_options.family == MachineProfileFamily("x86")
    assert selection.build_options.profile_name == MachineProfileName(
        "icelake-rockerlake"
    )
    assert selection.build_options.alternatives == (
        MachineFeatureAlternative(
            FeatureFlagName("avx512_gfni"),
            FeatureFlagSpelling("gfni"),
        ),
        MachineFeatureAlternative(
            FeatureFlagName("avx512_vaes"),
            FeatureFlagSpelling("vaes"),
        ),
        MachineFeatureAlternative(
            FeatureFlagName("avx512_vpclmulqdq"),
            FeatureFlagSpelling("vpclmulqdq"),
        ),
    )

    values = selection.build_options.format_values()
    assert values == {
        "target_profile_family": "x86",
        "target_profile_name": "icelake-rockerlake",
        "target_profile": "x86/icelake-rockerlake",
        "target_features": (
            "sse sse2 ssse3 sse4_1 sse4_2 avx avx2 avx512f "
            "avx512cd avx512vl avx512dq avx512bw avx512_vpopcntdq "
            "avx512ifma avx512vbmi avx512_vnni avx512_vbmi2 "
            "avx512_bitalg avx512_vpclmulqdq avx512_gfni avx512_vaes"
        ),
        "target_feature_alternatives": (
            "avx512_gfni=gfni avx512_vaes=vaes "
            "avx512_vpclmulqdq=vpclmulqdq"
        ),
    }


def test_m189_alternative_values_are_source_provided_spellings() -> None:
    result = _build_profiles(
        """
{
  "aarch64": [
    {
      "name": "neon",
      "flags": "neon",
      "alternatives": {
        "neon": "asimd"
      }
    }
  ]
}
""".strip()
    )

    assert result.diagnostics == ()
    assert result.catalog is not None
    profile = result.catalog.get("aarch64", "neon")
    assert profile is not None
    assert profile.alternatives == (
        MachineFeatureAlternative(
            FeatureFlagName("neon"),
            FeatureFlagSpelling("asimd"),
        ),
    )


def test_m189_unknown_profile_selection_is_diagnostic() -> None:
    result = load_machine_feature_profile_catalog(_PROFILE_PATH, _FLAGS_PATH)
    assert result.diagnostics == ()
    assert result.catalog is not None

    selection = result.catalog.select_build_options("x86", "does-not-exist")

    assert selection.build_options is None
    assert [diagnostic.code for diagnostic in selection.diagnostics] == [
        "TSL-MACHINE-PROFILE-UNKNOWN-PROFILE"
    ]
    assert selection.diagnostics[0].location is None


def test_m189_alias_flags_normalize_before_catalog_storage() -> None:
    result = _build_profiles(
        """
{
  "x86": [
    {
      "name": "alias",
      "flags": "sse4.1"
    }
  ]
}
""".strip()
    )

    assert result.diagnostics == ()
    assert result.catalog is not None
    profile = result.catalog.get("x86", "alias")
    assert profile is not None
    assert profile.features == (FeatureFlagName("sse4_1"),)


def test_m189_unknown_flags_are_diagnostics() -> None:
    result = _build_profiles(
        """
{
  "x86": [
    {
      "name": "bad",
      "flags": "sse mystery"
    }
  ]
}
""".strip()
    )

    assert result.catalog is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-MACHINE-PROFILE-UNKNOWN-FLAG"
    ]
    assert result.diagnostics[0].location is not None
    assert result.diagnostics[0].location.path == Path("profiles.json")


def test_m189_duplicate_normalized_flags_are_diagnostics() -> None:
    result = _build_profiles(
        """
{
  "x86": [
    {
      "name": "duplicate",
      "flags": "sse4.1 sse4_1"
    }
  ]
}
""".strip()
    )

    assert result.catalog is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-MACHINE-PROFILE-DUPLICATE-FLAG"
    ]


def test_m189_duplicate_profile_names_are_diagnostics() -> None:
    result = _build_profiles(
        """
{
  "x86": [
    {
      "name": "avx",
      "flags": "avx"
    },
    {
      "name": "avx",
      "flags": "avx2"
    }
  ]
}
""".strip()
    )

    assert result.catalog is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-MACHINE-PROFILE-DUPLICATE-PROFILE"
    ]


def test_m189_malformed_alternatives_are_diagnostics() -> None:
    result = _build_profiles(
        """
{
  "x86": [
    {
      "name": "bad",
      "flags": "avx",
      "alternatives": []
    }
  ]
}
""".strip()
    )

    assert result.catalog is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-MACHINE-PROFILE-MALFORMED-ALTERNATIVES"
    ]
