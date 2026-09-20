"""Tests for the deployment-oriented generated release bundle boundary."""

from __future__ import annotations

from dataclasses import replace
import importlib.util
from hashlib import sha256
import io
import json
from pathlib import Path
import sys
import tarfile
from types import ModuleType

import pytest


_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / ".github/scripts/build_release_bundles.py"


def _load_release_bundles() -> ModuleType:
    script_root = str(_SCRIPT.parent)
    if script_root not in sys.path:
        sys.path.insert(0, script_root)
    spec = importlib.util.spec_from_file_location("build_release_bundles", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


release_bundles = _load_release_bundles()
release_bundle_package = sys.modules["release_bundle_package"]


def _contract() -> dict[str, object]:
    return {
        "schema_version": 1,
        "product": {"id": "tsl-generated-library", "version": "1.0.0"},
        "backends": [
            {
                "id": "cpp",
                "profiles": [
                    {"name": "scalar"},
                    {"name": "avx2"},
                    {"name": "rvv"},
                ],
            },
            {
                "id": "rust",
                "profiles": [{"name": "sse"}, {"name": "avx2"}],
            },
        ],
    }


def _layout(tmp_path: Path | None = None) -> object:
    return release_bundles.GeneratedBundleConfig(
        layout_id="backend-deployment-bundles-v1",
        release_contract=(tmp_path or _ROOT) / "contract.json",
        backend_grouping=(("cpp", "per_profile"), ("rust", "combined")),
        backend_product_markers=(
            ("cpp", "CMakeLists.txt"),
            ("rust", "Cargo.toml"),
        ),
        generated_scope_additions=(("rust", ("fallback",)),),
        generated_scope_omissions=(),
        shared_artifact_roots=("docs",),
    )


def test_bundle_plan_keeps_cpp_deployments_small_and_rust_selection_whole() -> None:
    bundles = release_bundles.expected_generated_bundles(_contract(), _layout())

    assert [bundle.bundle_id for bundle in bundles] == [
        "cpp-scalar",
        "cpp-avx2",
        "cpp-rvv",
        "rust-release",
    ]
    assert [bundle.profiles for bundle in bundles] == [
        ("scalar",),
        ("avx2",),
        ("rvv",),
        ("sse", "avx2"),
    ]
    assert [bundle.generated_scope for bundle in bundles] == [
        ("scalar",),
        ("avx2",),
        ("rvv",),
        ("avx2", "fallback", "sse"),
    ]


def test_bundle_build_records_exact_generated_manifests(tmp_path: Path) -> None:
    generated: list[tuple[object, Path]] = []

    def generate(spec: object, root: Path) -> None:
        generated.append((spec, root))
        backend_id = spec.backend_id
        (root / backend_id).mkdir(parents=True)
        marker = "CMakeLists.txt" if backend_id == "cpp" else "Cargo.toml"
        product = root / backend_id / marker
        product.write_text(
            f"# {spec.bundle_id}\n", encoding="utf-8"
        )
        (root / backend_id / "public-api.json").write_text(
            json.dumps(
                {"backend": backend_id, "scope": list(spec.generated_scope)}
            )
            + "\n",
            encoding="utf-8",
        )
        public_api = root / backend_id / "public-api.json"
        (root / ".tslc-manifest.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "artifacts": [
                        {
                            "logical_path": f"{backend_id}/{marker}",
                            "digest": sha256(product.read_bytes()).hexdigest(),
                        },
                        {
                            "logical_path": f"{backend_id}/public-api.json",
                            "digest": sha256(public_api.read_bytes()).hexdigest(),
                        }
                    ],
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    output = tmp_path / "release"
    manifest = release_bundles.build_release_bundles(
        _contract(), _layout(tmp_path), output, generate=generate
    )

    assert [item[0].bundle_id for item in generated] == [
        "cpp-scalar",
        "cpp-avx2",
        "cpp-rvv",
        "rust-release",
    ]
    assert manifest == json.loads(
        (output / ".tsl-release-bundles.json").read_text(encoding="utf-8")
    )
    records = manifest["bundles"]
    assert isinstance(records, list)
    assert all(len(record["artifact_manifest_sha256"]) == 64 for record in records)
    assert all(record["extracted_size_bytes"] > 0 for record in records)
    assert records[-1]["generated_scope"] == ["avx2", "fallback", "sse"]
    assert "extracting every bundle" in (output / "README.md").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda contract: contract["backends"].append(
                {"id": "fortran", "profiles": [{"name": "scalar"}]}
            ),
            "no release packaging policy",
        ),
        (
            lambda contract: contract["backends"][0]["profiles"].append(
                {"name": "../escape"}
            ),
            "unsafe name",
        ),
        (
            lambda contract: contract["backends"][0]["profiles"].append(
                {"name": "scalar"}
            ),
            "duplicate profiles",
        ),
    ],
)
def test_bundle_plan_rejects_unsupported_or_unsafe_contracts(
    mutate: object, message: str
) -> None:
    contract = _contract()
    mutate(contract)

    with pytest.raises(release_bundles.ReleaseBundleError, match=message):
        release_bundles.expected_generated_bundles(contract, _layout())


def test_bundle_build_refuses_stale_output(tmp_path: Path) -> None:
    output = tmp_path / "release"
    output.mkdir()
    (output / "stale").write_text("old\n", encoding="utf-8")

    with pytest.raises(release_bundles.ReleaseBundleError, match="not empty"):
        release_bundles.build_release_bundles(
            _contract(), _layout(tmp_path), output, generate=lambda _spec, _root: None
        )


def test_checked_in_layout_covers_the_checked_in_release_contract() -> None:
    production = json.loads(
        (_ROOT / "supplementary/release/tsl-v1-production.json").read_text(
            encoding="utf-8"
        )
    )
    layout = release_bundles.load_generated_bundle_config(production, root=_ROOT)
    contract = json.loads(layout.release_contract.read_text(encoding="utf-8"))

    bundles = release_bundles.expected_generated_bundles(contract, layout)

    cpp_profiles = tuple(
        profile["name"]
        for backend in contract["backends"]
        if backend["id"] == "cpp"
        for profile in backend["profiles"]
    )
    rust_profiles = tuple(
        profile["name"]
        for backend in contract["backends"]
        if backend["id"] == "rust"
        for profile in backend["profiles"]
    )
    assert tuple(bundle.bundle_id for bundle in bundles[:-1]) == tuple(
        f"cpp-{profile}" for profile in cpp_profiles
    )
    assert bundles[-1].bundle_id == "rust-release"
    assert bundles[-1].profiles == rust_profiles


def test_bundle_layout_accepts_an_additive_backend_from_policy() -> None:
    contract = _contract()
    contract["backends"].append(
        {"id": "next", "profiles": [{"name": "portable"}]}
    )
    layout = replace(
        _layout(),
        backend_grouping=(
            ("cpp", "per_profile"),
            ("rust", "combined"),
            ("next", "per_profile"),
        ),
        backend_product_markers=(
            ("cpp", "CMakeLists.txt"),
            ("rust", "Cargo.toml"),
            ("next", "Package.toml"),
        ),
    )

    bundles = release_bundles.expected_generated_bundles(contract, layout)

    assert bundles[-1].bundle_id == "next-portable"
    assert bundles[-1].generated_scope == ("portable",)


def test_bundle_plan_applies_declared_scope_omissions_generically() -> None:
    contract = _contract()
    rust_backend = contract["backends"][1]
    rust_backend["profiles"].insert(0, {"name": "scalar"})
    layout = replace(
        _layout(),
        generated_scope_omissions=(("rust", ("scalar",)),),
    )

    bundles = release_bundles.expected_generated_bundles(contract, layout)

    assert bundles[-1].profiles == ("scalar", "sse", "avx2")
    assert bundles[-1].generated_scope == ("avx2", "fallback", "sse")


@pytest.mark.parametrize(
    ("members", "message"),
    [
        (("tsl-1/file", "other-1/file"), "exactly one versioned root"),
        (("tsl-1/file", "tsl-1/file"), "duplicate file"),
        (("tsl-1/../file",), "unsafe path"),
    ],
)
def test_archive_inventory_rejects_ambiguous_or_unsafe_paths(
    members: tuple[str, ...], message: str, tmp_path: Path
) -> None:
    archive_path = tmp_path / "invalid.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        for name in members:
            contents = b"content\n"
            info = tarfile.TarInfo(name)
            info.size = len(contents)
            archive.addfile(info, io.BytesIO(contents))

    with pytest.raises(release_bundles.ReleaseBundleError, match=message):
        release_bundle_package._generated_archive_inventory(
            archive_path, product_markers=()
        )
