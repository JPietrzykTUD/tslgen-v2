"""Verify manifest, checksums, target metadata, and executable mode in a VSIX."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys
from xml.etree import ElementTree
from zipfile import ZipFile


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 2:
        raise SystemExit("usage: verify_runtime_vsix.py VSIX TARGET")
    vsix, target = Path(arguments[0]), arguments[1]
    with ZipFile(vsix) as archive:
        manifest_name = "extension/server/release-manifest.json"
        manifest = json.loads(archive.read(manifest_name))
        if manifest["target"] != target:
            raise RuntimeError(
                f"VSIX manifest target is {manifest['target']}, expected {target}"
            )
        package = json.loads(archive.read("extension/package.json"))
        if package["version"] != manifest["extension_version"]:
            raise RuntimeError(
                "VSIX extension version does not match the runtime manifest"
            )
        vsix_manifest = ElementTree.fromstring(archive.read("extension.vsixmanifest"))
        identity = next(
            element
            for element in vsix_manifest.iter()
            if element.tag.rsplit("}", 1)[-1] == "Identity"
        )
        if identity.attrib.get("TargetPlatform") != target:
            raise RuntimeError("VSIX target metadata does not match the runtime manifest")
        prefix = f"extension/server/{target}/"
        runtime_files = {
            info.filename: info
            for info in archive.infolist()
            if info.filename.startswith("extension/server/")
            and info.filename != manifest_name
            and not info.is_dir()
        }
        expected_names = {
            prefix + item["path"] for item in manifest["checksums"]
        }
        if set(runtime_files) != expected_names:
            raise RuntimeError("VSIX runtime contents do not match the release manifest")
        for item in manifest["checksums"]:
            name = prefix + item["path"]
            data = archive.read(name)
            if sha256(data).hexdigest() != item["sha256"]:
                raise RuntimeError(f"VSIX checksum mismatch: {name}")
            if len(data) != item["size"]:
                raise RuntimeError(f"VSIX size mismatch: {name}")
        executable_name = "tslc.exe" if target.startswith("win32-") else "tslc"
        executable = runtime_files[prefix + executable_name]
        if not target.startswith("win32-") and not (executable.external_attr >> 16) & 0o111:
            raise RuntimeError("VSIX did not preserve the bundled executable mode")
    print(f"verified platform VSIX: {vsix} ({target})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
