import httpx
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import ListView, ListItem, Label, Static
from textual import on
from ..ascii import LOGO

from .configuration import ConfigurationScreen
from .server import ServerInformation
from .run_benchmark import RunBenchmarkScreen
from .benchmark_history import BenchmarkHistoryScreen

POLL_INTERVAL = 10

STATUS_STYLES = {
    "online": ("● Online", "green"),
    "offline": ("● Offline", "red"),
    "unauthorized": ("● Unauthorized", "yellow"),
    "not_configured": ("● Not Configured", "yellow"),
}


class ServerStatus(Static):
    """
    Live server status box shown on the main menu.

    Polls the Jellyfin server while the menu is visible and stops
    when the screen is suspended.
    """

    def __init__(self) -> None:
        super().__init__("", id="server-status")

    def on_mount(self) -> None:
        """
        Create the paused polling timer.
        """
        self._timer = self.set_interval(POLL_INTERVAL, self._poll, pause=True)

    def start(self) -> None:
        """
        Resume polling and check immediately.
        """
        self._timer.resume()
        self._poll()

    def stop(self) -> None:
        """
        Pause polling while the menu is not visible.
        """
        self._timer.pause()

    def _poll(self) -> None:
        """
        Run a status check as an exclusive worker.
        """
        self.run_worker(self._check(), exclusive=True)

    async def _check(self) -> None:
        """
        Query the Jellyfin server and update the status box.
        """
        config = self.app.config.server
        if not config.url or not config.api_key:
            self._set_status("not_configured")
            return
        headers = {"Authorization": f'MediaBrowser Token="{config.api_key}"'}
        try:
            async with httpx.AsyncClient(
                base_url=config.url.rstrip("/"), headers=headers, timeout=5
            ) as client:
                info = await client.get("/System/Info")
        except httpx.HTTPError:
            self._set_status("offline")
            return
        if info.status_code == 401:
            self._set_status("unauthorized")
        elif info.status_code < 400:
            try:
                data = info.json()
            except ValueError:
                self._set_status("offline")
                return
            self._set_status(
                "online",
                data.get("ServerName") or data.get("serverName") or "Unknown",
                data.get("Version") or data.get("version") or "Unknown",
            )
        else:
            self._set_status("offline")

    def _set_status(self, status: str, name: str = "", version: str = "") -> None:
        """
        Render the status box for the given state.

        :param status: Status key from STATUS_STYLES
        :param name: Server name, shown when online
        :param version: Server version, shown when online
        """
        label, color = STATUS_STYLES[status]
        lines = [f"[{color}]{label}[/]"]
        if status == "online":
            lines.append(f"[bold]{name}[/]")
            lines.append(f"[dim]Version {version}[/]")
        if status != "not_configured":
            lines.append(f"[dim]{self.app.config.server.url}[/]")
        self.update("\n".join(lines))


class MainMenu(Screen):
    def compose(self) -> ComposeResult:
        """
        Compose the logo, menu list, and server status box.
        """
        yield Static(LOGO, id="logo")
        yield Container(
            ListView(
                ListItem(Label("Run Benchmark"), id="benchmark"),
                ListItem(Label("Server Information"), id="server"),
                ListItem(Label("Benchmark History"), id="history"),
                ListItem(Label("Compare Results"), id="compare"),
                ListItem(Label("Configuration"), id="configuration"),
                classes="optionslist",
            ),
            ServerStatus(),
            id="menu-container",
        )

    def on_mount(self) -> None:
        """
        Start polling once the menu is mounted.
        """
        self.query_one(ServerStatus).start()

    def on_screen_suspend(self) -> None:
        """
        Stop polling when the menu is left.
        """
        self.query_one(ServerStatus).stop()

    def on_screen_resume(self) -> None:
        """
        Restart polling when the menu is shown again.
        """
        self.query_one(ServerStatus).start()

    @on(ListView.Selected)
    def on_selected(self, event: ListView.Selected) -> None:
        """
        Push the screen matching the selected menu item.
        """
        if event.item.id == "configuration":
            self.app.push_screen(ConfigurationScreen())
        elif event.item.id == "server":
            self.app.push_screen(ServerInformation())
        elif event.item.id == "benchmark":
            self.app.push_screen(RunBenchmarkScreen())
        elif event.item.id == "history":
            self.app.push_screen(BenchmarkHistoryScreen())
