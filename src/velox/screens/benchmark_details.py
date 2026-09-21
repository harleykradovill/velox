from textual.app import ComposeResult
from textual.containers import Container, Grid, Vertical, Center
from textual.screen import Screen
from textual.widgets import Button, Label, Static

from ..ascii import LOGO
from ..benchmark import ApiBenchmarkScenario, LibraryBenchmarkScenario
from ..storage import Benchmark

_FAST_ERROR_RATE = 0.01
_MAX_ERROR_RATE = 0.05
_SCENARIO_BUDGETS = {
    scenario.name: (scenario.fast_latency, scenario.slow_latency)
    for scenario in (ApiBenchmarkScenario, LibraryBenchmarkScenario)
}


def _fmt_ms(ms: float) -> str:
    return f"{ms:.0f}ms"


def _fmt_duration(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes:02d}:{secs:02d}"


def _fmt_throughput(requests: int, duration: float) -> str:
    return f"{requests / max(duration, 1):.1f} req/sec"


def _verdict(results: dict, scenario_name: str) -> tuple[str, str]:
    """
    Judge the run against what a typical Jellyfin server should deliver.

    :param results: Metrics snapshot for the run
    :param scenario_name: Name of the scenario that produced the run
    :returns: A (title, message) pair describing the verdict
    """
    fast, slow = _SCENARIO_BUDGETS[scenario_name]
    avg = results["avg"]
    error_rate = results["errors"] / max(results["requests"], 1)
    if avg <= fast and error_rate < _FAST_ERROR_RATE:
        return "Excellent", "Faster than a typical Jellyfin server."
    if avg <= slow and error_rate < _MAX_ERROR_RATE:
        return "Normal", "Within the expected range for a Jellyfin server."
    return "Slow", "Slower than a typical Jellyfin server."


def _stat_card(label: str, value: str, card_id: str) -> Vertical:
    return Vertical(
        Label(label, classes="stat-label"),
        Label(value, id=card_id, classes="stat-value"),
        classes="stat-card",
    )


class BenchmarkDetailsScreen(Screen):
    def __init__(self, benchmark: Benchmark) -> None:
        super().__init__()
        self.benchmark = benchmark

    def compose(self) -> ComposeResult:
        results = self.benchmark.results
        verdict, verdict_msg = _verdict(results, self.benchmark.scenario)
        yield Static(LOGO, id="logo")
        yield Vertical(
            Label(
                f"{self.benchmark.scenario}  ·  #{self.benchmark.id}",
                id="details-title",
            ),
            Center(
                Container(
                    Label("Verdict", classes="verdict-label"),
                    Label(verdict, id="verdict", classes="verdict-value"),
                    Label(verdict_msg, id="verdict-message"),
                    id="verdict-panel",
                )
            ),
            Center(
                Grid(
                    _stat_card("Avg Latency", _fmt_ms(results["avg"]), "avg"),
                    _stat_card(
                        "Avg Throughput",
                        _fmt_throughput(results["requests"], self.benchmark.duration),
                        "throughput",
                    ),
                    _stat_card("Requests", f"{results['requests']:,}", "requests"),
                    _stat_card("Errors", f"{results['errors']}", "errors"),
                    _stat_card("P50", _fmt_ms(results["p50"]), "p50"),
                    _stat_card("P95", _fmt_ms(results["p95"]), "p95"),
                    _stat_card("P99", _fmt_ms(results["p99"]), "p99"),
                    _stat_card(
                        "Error Rate",
                        f"{results['errors'] / max(results['requests'], 1):.2%}",
                        "error-rate",
                    ),
                    classes="stats-grid",
                )
            ),
            Label(
                f"Users: {self.benchmark.workers}   Duration: {_fmt_duration(self.benchmark.duration)}   Ramp-Up: {_fmt_duration(self.benchmark.ramp_up)}",
                id="details-meta",
            ),
            Center(Button("Go Back", id="return", classes="btn-details")),
            id="details-container",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "return":
            self.app.pop_screen()

    def key_down(self) -> None:
        self.focus_next()

    def key_up(self) -> None:
        self.focus_previous()
