"""Package the pinned REDnote launcher icon resources.

The APK keeps the same resource paths and resource table IDs.  This module
only prepares six PNG payloads for replacement inside the existing archive.
"""

from __future__ import annotations

import hashlib
import shutil
import struct
import subprocess
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# These are the exact paths in the pinned REDnote APK. Android's APK compiler
# stores the density directories with the -v4 qualifier in this archive.
PINNED_ICONS: dict[str, tuple[int, int, str]] = {
    "res/mipmap-xhdpi-v4/icon_logo.png": (96, 96, "legacy-square"),
    "res/mipmap-xhdpi-v4/icon_logo_round.png": (96, 96, "legacy-round"),
    "res/mipmap-xxhdpi-v4/icon_logo.png": (144, 144, "legacy-square"),
    "res/mipmap-xxhdpi-v4/icon_logo_round.png": (144, 144, "legacy-round"),
    "res/mipmap-xhdpi-v4/ic_launcher_log.png": (556, 556, "adaptive-foreground"),
    "res/mipmap-xhdpi-v4/ic_launcher_log_single.png": (556, 556, "adaptive-foreground"),
}


def parse_png_header(data: bytes) -> tuple[int, int]:
    """Return (width, height) from a PNG IHDR without a Python image library."""
    if len(data) < 24 or data[:8] != PNG_SIGNATURE or data[12:16] != b"IHDR":
        raise ValueError("Expected a PNG image with a valid IHDR header")
    width, height = struct.unpack(">II", data[16:24])
    if width <= 0 or height <= 0:
        raise ValueError("PNG dimensions must be positive")
    return width, height


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _imagemagick_command() -> list[str]:
    """Find ImageMagick's v7 `magick` command or v6 `convert` command."""
    for executable in ("magick", "convert"):
        located = shutil.which(executable)
        if located:
            return [located]
    raise RuntimeError("ImageMagick is required to resize launcher artwork")


def _resize_png(
    command: list[str],
    source: Path,
    width: int,
    height: int,
    *,
    circular: bool = False,
    rounded: bool = False,
) -> bytes:
    args = [*command, str(source), "-filter", "Lanczos", "-resize", f"{width}x{height}!"]
    if circular:
        # A transparent circular mask preserves the source's alpha within the
        # circle and makes the corners fully transparent.
        cx = width / 2
        cy = height / 2
        radius = min(width, height) / 2
        mask = (
            "(" , "-size", f"{width}x{height}", "xc:none", "-fill", "white",
            "-draw", f"circle {cx},{cy} {cx},{cy - radius}", ")",
        )
        args.extend(mask)
        args.extend(("-compose", "DstIn", "-composite"))
    elif rounded:
        radius = min(width, height) * 0.24
        args.extend((
            "(", "-size", f"{width}x{height}", "xc:none", "-fill", "white",
            "-draw", f"roundrectangle 0,0 {width - 1},{height - 1} {radius},{radius}",
            ")", "-compose", "DstIn", "-composite",
        ))
    args.extend(("-strip", "PNG32:-"))
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"ImageMagick failed to package {source}: {detail or result.returncode}")
    try:
        dimensions = parse_png_header(result.stdout)
    except ValueError as exc:
        raise RuntimeError(f"ImageMagick did not produce a valid PNG for {source}") from exc
    if dimensions != (width, height):
        raise RuntimeError(
            f"ImageMagick produced {dimensions[0]}x{dimensions[1]} for {source}; "
            f"expected {width}x{height}"
        )
    return result.stdout


def _read_square_png(path: Path, label: str) -> tuple[bytes, tuple[int, int]]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"Cannot read {label} PNG at {path}: {exc}") from exc
    try:
        dimensions = parse_png_header(data)
    except ValueError as exc:
        raise ValueError(f"{label} must be a valid PNG: {path}") from exc
    if dimensions[0] != dimensions[1]:
        raise ValueError(f"{label} PNG must be square, got {dimensions[0]}x{dimensions[1]}")
    return data, dimensions


def prepare_launcher_icons(source_apk: Path, artwork: Path) -> tuple[dict[str, bytes], dict[str, Any]]:
    """Build replacements for the six pinned REDnote launcher PNG resources.

    ``artwork`` is the legacy red square master PNG. Its sibling named
    ``<stem>-foreground.png`` supplies the padded adaptive white glyph.
    """
    source_apk = Path(source_apk)
    artwork = Path(artwork)
    foreground = artwork.with_name(f"{artwork.stem}-foreground.png")

    artwork_bytes, artwork_dimensions = _read_square_png(artwork, "Launcher artwork")
    foreground_bytes, foreground_dimensions = _read_square_png(foreground, "Adaptive foreground")
    command = _imagemagick_command()

    try:
        archive = ZipFile(source_apk, "r")
    except (OSError, BadZipFile) as exc:
        raise ValueError(f"Cannot open source APK as a ZIP archive: {source_apk}") from exc

    replacements: dict[str, bytes] = {}
    audit_files: list[dict[str, Any]] = []
    try:
        names = archive.namelist()
        counts = {path: names.count(path) for path in PINNED_ICONS}
        invalid = {path: count for path, count in counts.items() if count != 1}
        if invalid:
            raise ValueError(
                "Pinned APK must contain each of the six launcher resources exactly once; "
                f"found {invalid}"
            )

        for path, (width, height, kind) in PINNED_ICONS.items():
            try:
                source_png = archive.read(path)
            except (KeyError, OSError, BadZipFile) as exc:
                raise ValueError(f"Cannot read pinned launcher resource {path}") from exc
            try:
                source_dimensions = parse_png_header(source_png)
            except ValueError as exc:
                raise ValueError(f"Pinned launcher resource is not a valid PNG: {path}") from exc
            if source_dimensions != (width, height):
                raise ValueError(
                    f"Pinned launcher resource {path} is {source_dimensions[0]}x"
                    f"{source_dimensions[1]}; expected {width}x{height}"
                )

            if kind == "adaptive-foreground":
                master = foreground
                master_bytes = foreground_bytes
                master_dimensions = foreground_dimensions
                circular = False
            else:
                master = artwork
                master_bytes = artwork_bytes
                master_dimensions = artwork_dimensions
                circular = kind == "legacy-round"

            replacement = _resize_png(
                command, master, width, height, circular=circular,
                rounded=kind == "legacy-square",
            )
            replacement_dimensions = parse_png_header(replacement)
            if replacement_dimensions != (width, height):
                raise RuntimeError(f"Unexpected replacement dimensions for {path}")
            replacements[path] = replacement
            audit_files.append(
                {
                    "path": path,
                    "kind": kind,
                    "sourceSha256": _sha256(source_png),
                    "replacementSha256": _sha256(replacement),
                    "sourceDimensions": [source_dimensions[0], source_dimensions[1]],
                    "replacementDimensions": [replacement_dimensions[0], replacement_dimensions[1]],
                    "masterPngSha256": _sha256(master_bytes),
                    "masterPngDimensions": [master_dimensions[0], master_dimensions[1]],
                    "masterPngPath": str(master.resolve()),
                }
            )
    finally:
        archive.close()

    audit: dict[str, Any] = {
        "enabled": True,
        "displayText": "小K书",
        "masterPng": {
            "path": str(artwork.resolve()),
            "sha256": _sha256(artwork_bytes),
            "dimensions": [artwork_dimensions[0], artwork_dimensions[1]],
        },
        "adaptiveForegroundPng": {
            "path": str(foreground.resolve()),
            "sha256": _sha256(foreground_bytes),
            "dimensions": [foreground_dimensions[0], foreground_dimensions[1]],
        },
        "paths": list(PINNED_ICONS),
        "entries": audit_files,
    }
    return replacements, audit


def verify_launcher_icons(archive: ZipFile, audit: dict[str, Any]) -> dict[str, Any]:
    """Verify the six archived launcher PNGs and return a JSON-safe report."""
    expected_paths = list(PINNED_ICONS)
    paths = audit.get("paths")
    entries = audit.get("entries")
    if paths != expected_paths or not isinstance(entries, list) or len(entries) != len(expected_paths):
        raise ValueError("Launcher icon audit must describe exactly the six pinned resource paths")

    entries_by_path: dict[str, dict[str, Any]] = {}
    for row in entries:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise ValueError("Launcher icon audit contains a malformed entry record")
        path = row["path"]
        if path in entries_by_path:
            raise ValueError(f"Launcher icon audit repeats {path}")
        entries_by_path[path] = row
    if set(entries_by_path) != set(expected_paths):
        raise ValueError("Launcher icon audit entries do not match the six pinned paths")

    names = archive.namelist()
    verified_entries: list[dict[str, Any]] = []
    for path, (width, height, kind) in PINNED_ICONS.items():
        if names.count(path) != 1:
            raise ValueError(f"Output APK must contain {path} exactly once")
        row = entries_by_path[path]
        if row.get("kind") != kind:
            raise ValueError(f"Launcher icon audit has the wrong kind for {path}")
        try:
            payload = archive.read(path)
        except (KeyError, OSError, BadZipFile) as exc:
            raise RuntimeError(f"Cannot read output launcher resource {path}") from exc
        dimensions = parse_png_header(payload)
        if dimensions != (width, height):
            raise ValueError(
                f"Output launcher resource {path} is {dimensions[0]}x{dimensions[1]}; "
                f"expected {width}x{height}"
            )
        if row.get("replacementDimensions") != [width, height]:
            raise ValueError(f"Launcher icon audit has wrong replacement dimensions for {path}")
        if row.get("replacementSha256") != _sha256(payload):
            raise ValueError(f"Output launcher resource hash does not match audit for {path}")
        verified_entries.append(
            {
                "path": path,
                "sha256": _sha256(payload),
                "width": width,
                "height": height,
                "kind": kind,
            }
        )
    return {
        "verified": True,
        "entryCount": len(verified_entries),
        "paths": expected_paths,
        "entries": verified_entries,
    }
