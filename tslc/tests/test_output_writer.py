"""Written artifact identity remains exact after output transformations."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from tslc.output.artifacts import Artifact, ArtifactSet
from tslc.output.writer import ArtifactWriter


def _artifacts() -> ArtifactSet:
    return ArtifactSet.create(
        (
            Artifact(
                logical_path="cpp/include/tsl.hpp",
                content="int answer = 42;\n",
                media_type="text/x-c++hdr",
            ),
            Artifact(
                logical_path="rust/src/lib.rs",
                content="pub const ANSWER: i32 = 42;\n",
                media_type="text/x-rust",
            ),
        )
    )


def test_refresh_manifest_hashes_only_owned_on_disk_bytes(tmp_path: Path) -> None:
    writer = ArtifactWriter()
    write_report = writer.write(_artifacts(), tmp_path, mode="manifest-clean")
    assert write_report.diagnostics == ()

    cpp = tmp_path / "cpp/include/tsl.hpp"
    formatted = b"int answer = 42; // formatted\n"
    cpp.write_bytes(formatted)
    unrelated = tmp_path / "formatter.log"
    unrelated.write_text("not generated\n", encoding="utf-8")

    refresh_report = writer.refresh_manifest(tmp_path)

    assert refresh_report.diagnostics == ()
    assert tuple(record.logical_path for record in refresh_report.artifacts) == (
        "cpp/include/tsl.hpp",
        "rust/src/lib.rs",
    )
    manifest = json.loads(
        (tmp_path / ".tslc-manifest.json").read_text(encoding="utf-8")
    )
    digests = {
        entry["logical_path"]: entry["digest"] for entry in manifest["artifacts"]
    }
    assert digests["cpp/include/tsl.hpp"] == sha256(formatted).hexdigest()
    assert "formatter.log" not in digests


def test_refresh_manifest_rejects_a_missing_owned_artifact(tmp_path: Path) -> None:
    writer = ArtifactWriter()
    write_report = writer.write(_artifacts(), tmp_path, mode="manifest-clean")
    assert write_report.diagnostics == ()
    manifest_path = tmp_path / ".tslc-manifest.json"
    original_manifest = manifest_path.read_bytes()
    (tmp_path / "rust/src/lib.rs").unlink()

    refresh_report = writer.refresh_manifest(tmp_path)

    assert tuple(diagnostic.code for diagnostic in refresh_report.diagnostics) == (
        "TSL-WRITE-MANIFEST-ARTIFACT-NOT-FILE",
    )
    assert manifest_path.read_bytes() == original_manifest


def test_refresh_manifest_requires_an_existing_generator_manifest(
    tmp_path: Path,
) -> None:
    refresh_report = ArtifactWriter().refresh_manifest(tmp_path)

    assert tuple(diagnostic.code for diagnostic in refresh_report.diagnostics) == (
        "TSL-WRITE-MISSING-MANIFEST",
    )


def test_refresh_manifest_rejects_an_owned_symlink_outside_the_output_root(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "generated"
    outside = tmp_path / "outside.hpp"
    outside.write_text("external\n", encoding="utf-8")
    writer = ArtifactWriter()
    write_report = writer.write(_artifacts(), output_root, mode="manifest-clean")
    assert write_report.diagnostics == ()
    owned = output_root / "cpp/include/tsl.hpp"
    owned.unlink()
    owned.symlink_to(outside)

    refresh_report = writer.refresh_manifest(output_root)

    assert tuple(diagnostic.code for diagnostic in refresh_report.diagnostics) == (
        "TSL-WRITE-MANIFEST-PATH-ESCAPES-OUTPUT-ROOT",
    )
