"""
Locate the local ffmpeg build and report what it can do.

The capability check is a read-only query: it runs ffmpeg's own listing
commands and never starts an encode.
"""

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

TIMEOUT = 30

FFMPEG_DIRS = (
    r"C:\Program Files\Jellyfin\Server",
    "/usr/lib/jellyfin-ffmpeg",
    "/usr/share/jellyfin-ffmpeg",
    "/opt/jellyfin-ffmpeg",
    "/Applications/Jellyfin.app/Contents/MacOS",
)

VIDEO_CODECS = ("h264", "hevc", "av1", "vp9", "mpeg2video", "mpeg4")

LIBRARY_ENCODERS = {
    "h264": ("libx264", "libx264rgb"),
    "hevc": ("libx265",),
    "av1": ("libsvtav1", "libaom-av1", "librav1e"),
    "vp9": ("libvpx-vp9",),
}

HARDWARE_BACKENDS = {
    "nvenc": "NVIDIA NVENC",
    "qsv": "Intel Quick Sync",
    "amf": "AMD AMF",
    "vaapi": "VA-API",
    "videotoolbox": "Apple VideoToolbox",
    "vulkan": "Vulkan",
}

TONEMAP_FILTERS = (
    "zscale",
    "tonemap",
    "tonemap_opencl",
    "tonemap_vaapi",
    "libplacebo",
)


class ToolsError(RuntimeError):
    """Raised when ffmpeg cannot be located or queried."""


@dataclass(frozen=True)
class Capabilities:
    """Encoder, filter, and hardware acceleration lists reported by ffmpeg."""

    encoders: frozenset[str] = frozenset()
    filters: frozenset[str] = frozenset()
    hwaccels: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Tools:
    """Resolved ffmpeg/ffprobe binaries with their cached capabilities."""

    ffmpeg: str
    ffprobe: str
    version: str
    origin: str
    caps: Capabilities


def parse_encoders(output: str) -> frozenset[str]:
    """
    Extract encoder names from `ffmpeg -encoders` output.

    :param output: Raw stdout from ffmpeg
    :returns: Encoder names such as "libx264" or "hevc_nvenc"
    """
    names = set()
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 2 or parts[0][0] not in "VASD":
            continue
        if parts[1] == "=" or not parts[1][0].isalnum():  # Legend rows
            continue
        names.add(parts[1])
    return frozenset(names)


def parse_filters(output: str) -> frozenset[str]:
    """
    Extract filter names from `ffmpeg -filters` output.

    :param output: Raw stdout from ffmpeg
    :returns: Filter names such as "zscale"
    """
    names = set()
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 3 and "->" in parts[2]:
            names.add(parts[1])
    return frozenset(names)


def parse_hwaccels(output: str) -> frozenset[str]:
    """
    Extract acceleration names from `ffmpeg -hwaccels` output.

    :param output: Raw stdout from ffmpeg
    :returns: Acceleration names such as "cuda"
    """
    return frozenset(
        line.strip()
        for line in output.splitlines()
        if line.strip() and not line.strip().endswith(":")
    )


def parse_version(output: str) -> str:
    """
    Read the version token from `ffmpeg -version` output.

    :param output: Raw stdout from ffmpeg
    :returns: Version string, or "unknown" when the banner is unrecognised
    """
    lines = output.strip().splitlines()
    parts = lines[0].split() if lines else []
    if len(parts) >= 3 and parts[0].startswith("ffmpeg"):
        return parts[2]
    return "unknown"


def video_encoders(caps: Capabilities) -> dict[str, list[str]]:
    """
    Group available video encoders by codec family.

    :param caps: Capabilities of the ffmpeg build
    :returns: Mapping of codec name to sorted encoder names
    """
    groups = {}
    for codec in VIDEO_CODECS:
        names = [codec] if codec in caps.encoders else []  # Encoder shares codec name
        names += [e for e in caps.encoders if e.startswith(f"{codec}_")]
        names += [n for n in LIBRARY_ENCODERS.get(codec, ()) if n in caps.encoders]
        if names:
            groups[codec] = sorted(names)
    return groups


def hardware_backends(caps: Capabilities) -> list[str]:
    """
    List the hardware encoder families this build provides.

    :param caps: Capabilities of the ffmpeg build
    :returns: Friendly backend names, ordered as declared
    """
    return [
        label
        for suffix, label in HARDWARE_BACKENDS.items()
        if any(e.endswith(f"_{suffix}") for e in caps.encoders)
    ]


def tone_mappers(caps: Capabilities) -> list[str]:
    """
    List the HDR to SDR tone mapping filters this build provides.

    :param caps: Capabilities of the ffmpeg build
    :returns: Filter names present in the build
    """
    return [name for name in TONEMAP_FILTERS if name in caps.filters]


def _run(args: list[str]) -> str:
    """
    Run an ffmpeg listing command and return its stdout.

    :param args: Command and arguments to execute
    :returns: Process stdout
    :raises ToolsError: When the binary cannot run or exits non-zero
    """
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ToolsError(f"Could not run {Path(args[0]).name}: {exc}") from exc
    if result.returncode != 0:
        lines = (result.stderr or result.stdout).strip().splitlines()
        detail = lines[-1] if lines else "no output"
        raise ToolsError(f"{Path(args[0]).name} exited {result.returncode}: {detail}")
    return result.stdout


def read_capabilities(ffmpeg: str) -> Capabilities:
    """
    Query an ffmpeg binary for its encoders, filters, and accelerators.

    :param ffmpeg: Path to the ffmpeg binary
    :returns: Parsed capabilities
    :raises ToolsError: When the binary cannot be queried
    """
    return Capabilities(
        encoders=parse_encoders(_run([ffmpeg, "-hide_banner", "-encoders"])),
        filters=parse_filters(_run([ffmpeg, "-hide_banner", "-filters"])),
        hwaccels=parse_hwaccels(_run([ffmpeg, "-hide_banner", "-hwaccels"])),
    )


def _binary(name: str) -> str:
    """
    Return the executable file name for this platform.

    :param name: Tool name without extension
    :returns: Name including ".exe" on Windows
    """
    return f"{name}.exe" if os.name == "nt" else name


def _resolve_ffmpeg(configured: str) -> tuple[Path, str]:
    """
    Find the ffmpeg binary from the configured path or the usual locations.

    :param configured: Explicit binary or folder path, or "" for auto-detect
    :returns: Resolved binary path and a short description of its origin
    :raises ToolsError: When no usable binary is found
    """
    binary = _binary("ffmpeg")
    if configured:
        path = Path(configured).expanduser()
        candidate = path / binary if path.is_dir() else path
        if not candidate.suffix:  # Windows users often omit .exe
            candidate = candidate.with_name(_binary(candidate.name))
        if candidate.is_file():
            return candidate, "configured"
        raise ToolsError(f"No ffmpeg found at {candidate}")
    for folder in FFMPEG_DIRS:
        candidate = Path(folder) / binary
        if candidate.is_file():
            return candidate, "jellyfin"
    found = shutil.which(binary)
    if found:
        return Path(found), "PATH"
    raise ToolsError(
        "ffmpeg was not found. Install jellyfin-ffmpeg, add ffmpeg to PATH, "
        "or set the ffmpeg path in Configuration."
    )


def _resolve_ffprobe(ffmpeg: Path) -> Path:
    """
    Find ffprobe next to ffmpeg, falling back to PATH.

    :param ffmpeg: Resolved ffmpeg binary
    :returns: Path to ffprobe
    :raises ToolsError: When ffprobe cannot be found
    """
    binary = _binary("ffprobe")
    sibling = ffmpeg.with_name(binary)
    if sibling.is_file():
        return sibling
    found = shutil.which(binary)
    if found:
        return Path(found)
    raise ToolsError(f"ffprobe was not found next to {ffmpeg.name} or on PATH.")


def find_tools(configured: str = "") -> Tools:
    """
    Locate ffmpeg/ffprobe and read the capabilities of that build.

    :param configured: Explicit binary or folder path, or "" for auto-detect
    :returns: Tools with resolved paths, version, and capabilities
    :raises ToolsError: When ffmpeg is missing or cannot be queried
    """
    ffmpeg, origin = _resolve_ffmpeg(configured.strip())
    return Tools(
        ffmpeg=str(ffmpeg),
        ffprobe=str(_resolve_ffprobe(ffmpeg)),
        version=parse_version(_run([str(ffmpeg), "-hide_banner", "-version"])),
        origin=origin,
        caps=read_capabilities(str(ffmpeg)),
    )
