#!/usr/bin/env python3
import argparse
import hashlib
import os
import shutil
import sys
from pathlib import Path

import requests


SDE_VERSION = "10.8"
SDE_FILENAME = "sde-external-10.8.0-2026-03-15-lin.tar.xz"
SDE_SHA256 = "50B320CD226ACEF7A491F5B321FC1BE3C3C7984F9E27A456E64894B5B0979DD3"

# Current known Intel URL for SDE 10.8.
# This may be blocked by Intel anti-bot protection from containers.
DEFAULT_SDE_URL = (
    "https://downloadmirror.intel.com/915934/"
    "sde-external-10.8.0-2026-03-15-lin.tar.xz"
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def looks_like_xz(path: Path) -> bool:
    # XZ magic bytes: FD 37 7A 58 5A 00
    with path.open("rb") as f:
        return f.read(6) == b"\xfd7zXZ\x00"


def verify_sde_tarball(path: Path) -> None:
    if not path.exists():
        raise RuntimeError(f"File does not exist: {path}")

    if not looks_like_xz(path):
        preview = path.read_bytes()[:300]
        raise RuntimeError(
            f"{path} is not an xz archive. Intel probably returned HTML instead.\n"
            f"First bytes:\n{preview!r}"
        )

    actual = sha256_file(path)
    if actual != SDE_SHA256:
        raise RuntimeError(
            "SHA256 mismatch.\n"
            f"Expected: {SDE_SHA256}\n"
            f"Actual:   {actual}\n"
            f"File:     {path}"
        )


def copy_local_tarball(src: Path, out_dir: Path) -> Path:
    dst = out_dir / SDE_FILENAME
    shutil.copyfile(src, dst)
    verify_sde_tarball(dst)
    return dst


def download_url(url: str, out_dir: Path) -> Path:
    dst = out_dir / SDE_FILENAME
    tmp = dst.with_suffix(dst.suffix + ".tmp")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0 Safari/537.36"
        ),
        "Accept": "application/octet-stream,*/*",
    }

    try:
        with requests.get(url, headers=headers, stream=True, timeout=120) as r:
            if r.status_code == 403:
                raise RuntimeError(
                    "Intel returned HTTP 403. This container/IP is blocked from "
                    "fetching the Intel SDE artifact automatically."
                )

            r.raise_for_status()

            with tmp.open("wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)

        tmp.replace(dst)
        verify_sde_tarball(dst)
        return dst

    finally:
        tmp.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    parser.add_argument(
        "--url",
        default=os.environ.get("INTEL_SDE_URL", DEFAULT_SDE_URL),
        help="SDE tarball URL. Can point to Intel or to your own mirror.",
    )
    parser.add_argument(
        "--local-file",
        default=os.environ.get("INTEL_SDE_LOCAL_FILE"),
        help="Path to a manually downloaded SDE tarball.",
    )

    args = parser.parse_args()

    if os.environ.get("ACCEPT_INTEL_SDE_LICENSE") != "yes":
        print(
            "Refusing to install Intel SDE without explicit license acknowledgement.\n"
            "Read Intel's SDE license first, then set:\n"
            "  ACCEPT_INTEL_SDE_LICENSE=yes",
            file=sys.stderr,
        )
        return 2

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        if args.local_file:
            result = copy_local_tarball(Path(args.local_file), out_dir)
        else:
            result = download_url(args.url, out_dir)

        print(result)
        return 0

    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        print(
            "\nAutomatic download failed.\n\n"
            "Reliable options:\n"
            "  1. Download SDE once manually from Intel in a browser.\n"
            "  2. Pass it into the build:\n"
            "       INTEL_SDE_LOCAL_FILE=/path/to/sde-external-10.8.0-2026-03-15-lin.tar.xz\n"
            "  3. Or host the exact tarball on a private/internal mirror and set:\n"
            "       INTEL_SDE_URL=https://your-mirror/sde-external-10.8.0-2026-03-15-lin.tar.xz\n\n"
            "The script will still verify the SHA256 before installing.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())