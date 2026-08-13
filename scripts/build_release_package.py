#!/usr/bin/env python3
"""Build a deterministic, runtime-only MarkdownReader sublime-package."""

import argparse
import hashlib
import os
import tempfile
import zipfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = (
    ".python-version",
    "CHANGELOG.md",
    "Default.sublime-commands",
    "LICENSE",
    "Main.sublime-menu",
    "MarkdownReader.sublime-settings",
    "README.md",
    "README.zh-CN.md",
    "markdown_reader_plugin.py",
)
RENDERER_FILES = (
    "renderer/browser-preview.js",
    "renderer/server.js",
)
FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
REGULAR_FILE_MODE = 0o100644


def package_files():
    """Return every package path in stable archive-name order."""
    paths = [REPOSITORY_ROOT / name for name in ROOT_FILES + RENDERER_FILES]
    for path in (REPOSITORY_ROOT / "markdown_reader").rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        if path.suffix == ".py" or path.name in ("LICENSE", "README.md"):
            paths.append(path)

    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "release package input is missing: {}".format(
                ", ".join(str(path) for path in missing)
            )
        )
    return sorted(paths, key=lambda path: path.relative_to(REPOSITORY_ROOT).as_posix())


def build_package(destination):
    """Write the package atomically and return its SHA-256 digest."""
    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_path = tempfile.mkstemp(
        dir=str(destination.parent),
        prefix=".markdown-reader-release-",
        suffix=".tmp",
    )
    os.close(descriptor)
    try:
        with zipfile.ZipFile(
            temporary_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for path in package_files():
                archive_name = path.relative_to(REPOSITORY_ROOT).as_posix()
                info = zipfile.ZipInfo(archive_name, date_time=FIXED_TIMESTAMP)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = REGULAR_FILE_MODE << 16
                archive.writestr(
                    info,
                    path.read_bytes(),
                    compress_type=zipfile.ZIP_DEFLATED,
                )
        os.replace(temporary_path, str(destination))
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)
    return hashlib.sha256(destination.read_bytes()).hexdigest()


def write_checksum(destination, digest, checksum_output):
    """Write a sha256sum-compatible checksum file atomically."""
    checksum_output = Path(checksum_output).resolve()
    checksum_output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_path = tempfile.mkstemp(
        dir=str(checksum_output.parent),
        prefix=".markdown-reader-checksum-",
        suffix=".tmp",
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as temporary:
            temporary.write("{}  {}\n".format(digest, Path(destination).name))
        os.replace(temporary_path, str(checksum_output))
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default="dist/MarkdownReader.sublime-package",
        help="destination .sublime-package path",
    )
    parser.add_argument(
        "--checksum-output",
        help="optional sha256sum-compatible checksum path",
    )
    arguments = parser.parse_args()
    destination = Path(arguments.output).resolve()
    digest = build_package(destination)
    if arguments.checksum_output:
        write_checksum(destination, digest, arguments.checksum_output)
    print("Package: {}".format(destination))
    print("Bytes: {}".format(destination.stat().st_size))
    print("SHA256: {}".format(digest))


if __name__ == "__main__":
    main()
