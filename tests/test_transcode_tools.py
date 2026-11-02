import asyncio
import os
from pathlib import Path

from textual.app import App
from textual.widgets import Static

import velox
from velox.benchmark.transcode import (
    Capabilities,
    Tools,
    hardware_backends,
    parse_encoders,
    parse_filters,
    parse_hwaccels,
    parse_version,
    read_capabilities,
    tone_mappers,
    video_encoders,
)
from velox.benchmark.transcode.tools import _binary, _resolve_ffmpeg, ToolsError
from velox.screens import transcode_capabilities
from velox.screens.transcode_capabilities import TranscodingCapabilitiesScreen

ENCODER_OUTPUT = """
Encoders:
 V..... = Video
 ------
 V....D libx264              libx264 H.264/AVC
 V....D libx265              libx265 H.265/HEVC
 V....D h264_nvenc           NVIDIA NVENC H.264 encoder
 V....D hevc_nvenc           NVIDIA NVENC HEVC encoder
 V....D av1_qsv              AV1 (Intel Quick Sync Video)
 V..... libsvtav1            SVT-AV1 encoder
 A....D aac                  AAC encoder
"""

FILTER_OUTPUT = """
Filters:
 T.. = Timeline support
 ..C = Command support
 ... zscale            V->V       Apply resizing, colorspace and bit depth
 ... tonemap           V->V       Conversion to/from different dynamic ranges
 ... hwupload_cuda     V->V       Upload to CUDA
"""

HWACCEL_OUTPUT = """
Hardware acceleration methods:
cuda
vaapi
d3d11va
"""

VERSION_OUTPUT = "ffmpeg version 7.1-jellyfin Copyright (c) 2000-2024\nbuilt with gcc"


def test_parse_encoders_skips_headers_and_audio() -> None:
    """
    Only real encoder rows are kept, and audio encoders are grouped out.
    """
    names = parse_encoders(ENCODER_OUTPUT)
    assert {"libx264", "h264_nvenc", "hevc_nvenc", "aac"} <= names
    assert "Encoders:" not in names
    assert "=" not in names
    assert video_encoders(Capabilities(encoders=names))["h264"] == [
        "h264_nvenc",
        "libx264",
    ]


def test_parse_encoders_keeps_rows_with_extra_flags() -> None:
    """
    Rows carrying F, X or B flags are still real encoders.
    """
    output = """
 Encoders:
 VF...D h264_amf            AMD AMF H.264 Encoder
 V....X libvpx-vp9          libvpx VP9
 V..X.. experimental_enc    Experimental encoder
"""
    names = parse_encoders(output)
    assert {"h264_amf", "libvpx-vp9", "experimental_enc"} <= names


def test_video_encoders_covers_all_codec_families() -> None:
    """
    Codec-named, prefixed, and library encoders all reach their group.
    """
    groups = video_encoders(
        Capabilities(
            encoders=frozenset(
                {
                    "libx264",
                    "libx265",
                    "libsvtav1",
                    "libvpx-vp9",
                    "mpeg2video",
                    "mpeg4",
                }
            )
        )
    )
    assert set(groups) == {"h264", "hevc", "av1", "vp9", "mpeg2video", "mpeg4"}
    assert groups["vp9"] == ["libvpx-vp9"]
    assert groups["mpeg4"] == ["mpeg4"]


def test_parse_filters_and_hwaccels() -> None:
    """
    Filter arrows and the hardware acceleration header are handled.
    """
    assert parse_filters(FILTER_OUTPUT) == {
        "zscale",
        "tonemap",
        "hwupload_cuda",
    }
    assert parse_hwaccels(HWACCEL_OUTPUT) == {"cuda", "vaapi", "d3d11va"}


def test_parse_version_reads_third_token() -> None:
    """
    The version comes from the first banner line.
    """
    assert parse_version(VERSION_OUTPUT) == "7.1-jellyfin"
    assert parse_version("") == "unknown"


def test_backend_and_tonemap_helpers() -> None:
    """
    Hardware backends and tone mappers are derived from capability sets.
    """
    caps = Capabilities(
        encoders=parse_encoders(ENCODER_OUTPUT),
        filters=parse_filters(FILTER_OUTPUT),
    )
    assert hardware_backends(caps) == ["NVIDIA NVENC", "Intel Quick Sync"]
    assert tone_mappers(caps) == ["zscale", "tonemap"]


def test_read_capabilities_uses_ffmpeg_listings(monkeypatch) -> None:
    """
    Each ffmpeg listing command feeds one capability set.
    """
    outputs = {
        "-encoders": ENCODER_OUTPUT,
        "-filters": FILTER_OUTPUT,
        "-hwaccels": HWACCEL_OUTPUT,
    }

    def fake_run(args):
        return outputs[args[-1]]

    monkeypatch.setattr("velox.benchmark.transcode.tools._run", fake_run)
    caps = read_capabilities("ffmpeg")
    assert "libx265" in caps.encoders
    assert "zscale" in caps.filters
    assert caps.hwaccels == {"cuda", "vaapi", "d3d11va"}


def test_resolve_ffmpeg_rejects_missing_path(tmp_path) -> None:
    """
    An explicit path without a binary fails with an actionable error.
    """
    try:
        _resolve_ffmpeg(str(tmp_path))
    except ToolsError as error:
        assert "ffmpeg" in str(error)
    else:
        raise AssertionError("expected ToolsError")


def test_resolve_ffmpeg_adds_missing_extension(tmp_path) -> None:
    """
    A configured Windows path without ".exe" still resolves.
    """
    binary = _binary("ffmpeg")
    target = tmp_path / binary
    target.write_text("")
    resolved, origin = _resolve_ffmpeg(str(tmp_path / "ffmpeg"))
    assert resolved == target
    assert origin == "configured"


def test_binary_name_matches_platform() -> None:
    """
    Windows binaries keep their .exe suffix.
    """
    suffix = ".exe" if os.name == "nt" else ""
    assert _binary("ffmpeg") == f"ffmpeg{suffix}"


def _fake_tools() -> Tools:
    return Tools(
        ffmpeg="ffmpeg",
        ffprobe="ffprobe",
        version="7.1",
        origin="PATH",
        caps=Capabilities(
            encoders=parse_encoders(ENCODER_OUTPUT),
            filters=parse_filters(FILTER_OUTPUT),
            hwaccels=parse_hwaccels(HWACCEL_OUTPUT),
        ),
    )


class _App(App):
    """Bare app that opens the capability screen directly."""

    CSS_PATH = str(Path(velox.__file__).with_name("styles.tcss"))

    def on_mount(self) -> None:
        self.push_screen(TranscodingCapabilitiesScreen())


def test_screen_reports_detected_capabilities(monkeypatch) -> None:
    """
    A successful check renders the version, encoders, and tone mapping lines.
    """
    monkeypatch.setattr(transcode_capabilities, "find_tools", lambda: _fake_tools())

    async def scenario() -> str:
        app = _App()
        async with app.run_test() as pilot:
            await pilot.pause()
            tools = app.screen.query_one("#cap-tools", Static).render().plain
            encoders = app.screen.query_one("#cap-encoders", Static).render().plain
            tonemap = app.screen.query_one("#cap-tonemap", Static).render().plain
        return f"{tools}\n{encoders}\n{tonemap}"

    text = asyncio.run(scenario())
    assert "ffmpeg 7.1" in text
    assert "hevc_nvenc" in text
    assert "HDR → SDR tone mapping available" in text


def test_screen_reports_missing_ffmpeg(monkeypatch) -> None:
    """
    A failed lookup shows the reason instead of raising.
    """

    def fail():
        raise ToolsError("ffmpeg was not found.")

    monkeypatch.setattr(transcode_capabilities, "find_tools", fail)

    async def scenario() -> tuple[str, str]:
        app = _App()
        async with app.run_test() as pilot:
            await pilot.pause()
            return (
                app.screen.query_one("#cap-tools", Static).render().plain,
                app.screen.query_one("#cap-encoders", Static).render().plain,
            )

    tools, encoders = asyncio.run(scenario())
    assert "ffmpeg unavailable" in tools
    assert "ffmpeg was not found." in tools
    assert encoders == ""


def test_screen_survives_bracketed_paths_and_unexpected_errors(monkeypatch) -> None:
    """
    Brackets in a path are shown as text, and unknown errors are reported.
    """
    bracketed = Tools(
        ffmpeg=r"D:\Tools\ffmpeg [portable]\bin\ffmpeg.exe",
        ffprobe=r"D:\Tools\ffmpeg [portable]\bin\ffprobe.exe",
        version="7.1",
        origin="configured",
        caps=Capabilities(
            encoders=parse_encoders(ENCODER_OUTPUT),
            filters=parse_filters(FILTER_OUTPUT),
        ),
    )

    async def run(find) -> tuple[str, str]:
        monkeypatch.setattr(transcode_capabilities, "find_tools", find)
        app = _App()
        async with app.run_test() as pilot:
            await pilot.pause()
            return (
                app.screen.query_one("#cap-tools", Static).render().plain,
                app.screen.query_one("#cap-hardware", Static).render().plain,
            )

    tools, hardware = asyncio.run(run(lambda: bracketed))
    assert r"D:\Tools\ffmpeg [portable]\bin\ffmpeg.exe" in tools
    assert "NVIDIA NVENC" in hardware

    def explode():
        raise ValueError("bad listing")

    tools, _ = asyncio.run(run(explode))
    assert "Unexpected error: bad listing" in tools
