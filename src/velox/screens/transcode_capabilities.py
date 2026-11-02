import asyncio
import socket

from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Label, Static

from ..ascii import LOGO
from ..benchmark.transcode import (
    Tools,
    ToolsError,
    find_tools,
    hardware_backends,
    tone_mappers,
    video_encoders,
)

CODEC_LABELS = {
    "h264": "H.264",
    "hevc": "H.265/HEVC",
    "av1": "AV1",
    "vp9": "VP9",
    "mpeg2video": "MPEG-2",
    "mpeg4": "MPEG-4",
}

OK = "[green]✓[/]"
MISSING = "[red]✗[/]"


def _encoders_text(tools: Tools) -> str:
    """
    Build the per-codec encoder listing.

    :param tools: Resolved ffmpeg tools
    :returns: Markup block listing encoders by codec
    """
    groups = video_encoders(tools.caps)
    if not groups:
        return "[red]No video encoders reported by this build.[/]"
    return "\n".join(
        f"[bold]{escape(CODEC_LABELS.get(codec, codec))}[/]: "
        f"[dim]{escape(', '.join(names))}[/]"
        for codec, names in groups.items()
    )


def _hardware_text(tools: Tools) -> str:
    """
    Build the hardware acceleration summary.

    :param tools: Resolved ffmpeg tools
    :returns: Markup block describing hardware encoders and accelerators
    """
    backends = hardware_backends(tools.caps)
    hwaccels = ", ".join(sorted(tools.caps.hwaccels)) or "none"
    if backends:
        headline = f"{OK} [bold]{escape(', '.join(backends))}[/]"
    else:
        headline = f"{MISSING} [bold]Software encoding only[/]"
    return "\n".join([headline, f"[dim]ffmpeg hwaccels: {escape(hwaccels)}[/]"])


def _tonemap_text(tools: Tools) -> str:
    """
    Build the HDR to SDR tone mapping summary.

    :param tools: Resolved ffmpeg tools
    :returns: Markup block describing tone mapping filters
    """
    filters = tone_mappers(tools.caps)
    if not filters:
        return (
            f"{MISSING} [bold]No HDR → SDR tone mapping[/]\n"
            "[dim]HDR sources need jellyfin-ffmpeg (zscale + tonemap).[/]"
        )
    return "\n".join(
        [
            f"{OK} [bold]HDR → SDR tone mapping available[/]",
            f"[dim]filters: {escape(', '.join(filters))}[/]",
        ]
    )


def _tools_text(tools: Tools) -> str:
    """
    Build the header describing the detected ffmpeg build.

    :param tools: Resolved ffmpeg tools
    :returns: Markup block with version, origin, and binary paths
    """
    return "\n".join(
        [
            f"[green]● ffmpeg {escape(tools.version)}[/] "
            f"[dim]({escape(tools.origin)})[/]",
            f"[dim]{escape(tools.ffmpeg)}[/]",
            f"[dim]{escape(tools.ffprobe)}[/]",
        ]
    )


class TranscodingCapabilitiesScreen(Screen):
    """
    Report the transcoding capabilities of the local ffmpeg build.

    The check never encodes anything; it reads ffmpeg's own listings.
    """

    def __init__(self) -> None:
        super().__init__()
        self._checking = False

    def compose(self) -> ComposeResult:
        """
        Compose the capability report and its buttons.

        :returns: Widgets to display on the screen
        """
        host = socket.gethostname()
        yield Static(LOGO, id="logo")
        yield Container(
            VerticalScroll(
                Label("Local Transcoding Capability", id="cap-title"),
                Static(
                    f"Checks the ffmpeg installed on the current machine ({host}).\n"
                    "Results do not reflect a remote Jellyfin server.",
                    id="cap-warning",
                ),
                Static("Checking ffmpeg…", id="cap-tools"),
                Static("", id="cap-encoders"),
                Static("", id="cap-hardware"),
                Static("", id="cap-tonemap"),
                id="capabilities-container",
            ),
            Horizontal(
                Button("Recheck", id="recheck", classes="btn-cap"),
                Button("Go Back", id="return", classes="btn-cap"),
                id="cap-buttons",
            ),
            id="cap-page",
        )

    def on_mount(self) -> None:
        """
        Run the capability check once the screen is visible.

        The check is deferred one message cycle so the first worker starts after
        the screen is fully active.
        """
        self.call_later(self._check)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "return":
            self.app.pop_screen()
        elif event.button.id == "recheck":
            self._check()

    def key_escape(self) -> None:
        self.app.pop_screen()

    def key_down(self) -> None:
        self.focus_next()

    def key_up(self) -> None:
        self.focus_previous()

    def _check(self) -> None:
        """
        Start a background capability check.

        A worker thread cannot be cancelled, so presses during a check are ignored.
        """
        if self._checking:  # A thread cannot be cancelled, so skip the press
            return
        self._checking = True
        self.query_one("#cap-tools", Static).update("[dim]Checking ffmpeg…[/]")
        self.run_worker(self._detect(), exclusive=True)

    async def _detect(self) -> None:
        """
        Locate ffmpeg and render its capabilities, or the failure reason.
        """
        try:
            try:
                tools = await asyncio.to_thread(find_tools)
            except ToolsError as error:
                self._show_error(str(error))
                return
            except Exception as error:  # Never leave the screen stuck
                self._show_error(f"Unexpected error: {error}")
                return
            self.query_one("#cap-tools", Static).update(_tools_text(tools))
            self.query_one("#cap-encoders", Static).update(_encoders_text(tools))
            self.query_one("#cap-hardware", Static).update(_hardware_text(tools))
            self.query_one("#cap-tonemap", Static).update(_tonemap_text(tools))
        finally:
            self._checking = False

    def _show_error(self, message: str) -> None:
        """
        Render a failed check with its actionable message.

        :param message: Error detail from the tool lookup
        """
        self.query_one("#cap-tools", Static).update(
            f"[red]● ffmpeg unavailable[/]\n[dim]{escape(message)}[/]"
        )
        for section in ("#cap-encoders", "#cap-hardware", "#cap-tonemap"):
            self.query_one(section, Static).update("")
