from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Button, Label, Static

from ..ascii import LOGO
from ..storage import Benchmark


def _fmt_ms(ms: float) -> str:
    return f"{ms:.0f}ms"


def _fmt_duration(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes:02d}:{secs:02d}"


class BenchmarkDetailsScreen(Screen):
    def __init__(self, benchmark: Benchmark) -> None:
        super().__init__()
        self.benchmark = benchmark

    def compose(self) -> ComposeResult:
        results = self.benchmark.results
        yield Static(LOGO, id="logo")
        yield Container(
            Label("Benchmark ID", classes="info-label"),
            Label(f"#{self.benchmark.id}", id="id", classes="info-value"),
            Label("Scenario", classes="info-label"),
            Label(self.benchmark.scenario, id="scenario", classes="info-value"),
            Label("Users", classes="info-label"),
            Label(f"{self.benchmark.workers}", id="users", classes="info-value"),
            Label("Duration", classes="info-label"),
            Label(
                _fmt_duration(self.benchmark.duration),
                id="duration",
                classes="info-value",
            ),
            Label("Ramp-Up", classes="info-label"),
            Label(
                _fmt_duration(self.benchmark.ramp_up),
                id="ramp-up",
                classes="info-value",
            ),
            Label("Requests", classes="info-label"),
            Label(f"{results['requests']:,}", id="requests", classes="info-value"),
            Label("Latency", classes="info-label"),
            Label(f"P50  {_fmt_ms(results['p50'])}", id="p50", classes="info-value"),
            Label(f"P95  {_fmt_ms(results['p95'])}", id="p95", classes="info-value"),
            Label(f"P99  {_fmt_ms(results['p99'])}", id="p99", classes="info-value"),
            Label("Errors", classes="info-label"),
            Label(f"{results['errors']}", id="errors", classes="info-value"),
            Button("Go Back", id="return", classes="btn"),
            id="details-container",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "return":
            self.app.pop_screen()

    def key_down(self) -> None:
        self.focus_next()

    def key_up(self) -> None:
        self.focus_previous()
