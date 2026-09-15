from ..ascii import LOGO
from ..benchmark import ApiBenchmarkScenario, LibraryBenchmarkScenario
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Select, Static

from .active_benchmark import ActiveBenchmarkScreen

SCENARIOS = [
    ("API", "api"),
    ("Library", "library"),
]

DURATIONS = [
    ("30 seconds", "30s"),
    ("1 minute", "1m"),
    ("5 minutes", "5m"),
    ("10 minutes", "10m"),
    ("30 minutes", "30m"),
]

WORKERS = [
    ("5", "5"),
    ("20", "20"),
    ("50", "50"),
    ("100", "100"),
]

RAMP_UPS = [
    ("None", "0s"),
    ("10 seconds", "10s"),
    ("30 seconds", "30s"),
    ("1 minute", "1m"),
]


class RunBenchmarkScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Static(LOGO, id="logo")
        yield Container(
            Label("Scenario"),
            Select(SCENARIOS, id="scenario", classes="select"),
            Label("Concurrent Workers"),
            Select(WORKERS, id="users", classes="select"),
            Label("Ramp-Up Time"),
            Select(RAMP_UPS, id="ramp-up", classes="select"),
            Label("Duration"),
            Select(DURATIONS, id="duration", classes="select"),
            Button("Start Benchmark", id="start", classes="btn"),
            Button("Go Back", id="return", classes="btn"),
            id="active-benchmark-container",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "return":
            self.app.pop_screen()
        elif event.button.id == "start":
            users = int(self.query_one("#users", Select).value)
            duration = self.query_one("#duration", Select).value
            scenario = self.query_one("#scenario", Select).value
            ramp_up = self.query_one("#ramp-up", Select).value
            self.app.push_screen(
                ActiveBenchmarkScreen(
                    scenario=self._make_scenario(scenario),
                    users=users,
                    duration=duration,
                    ramp_up=ramp_up,
                    config=self.app.config,
                )
            )

    @staticmethod
    def _make_scenario(value: str):
        if value == "library":
            return LibraryBenchmarkScenario()
        return ApiBenchmarkScenario()

    def key_down(self) -> None:
        self.focus_next()

    def key_up(self) -> None:
        self.focus_previous()
