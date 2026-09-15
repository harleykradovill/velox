import httpx
from textual.app import ComposeResult
from textual.containers import Container, Grid, Horizontal
from textual.screen import Screen
from textual.widgets import Button, Label, ProgressBar, Static
from textual_plot import (
    DurationFormatter,
    HiResMode,
    LegendLocation,
    NumericAxisFormatter,
    PlotWidget,
)

from ..ascii import LOGO
from ..benchmark import BenchmarkRunner
from .benchmark_details import BenchmarkDetailsScreen
from .error import ErrorScreen


def _parse_duration(value: str) -> float:
    """
    Parse a duration string like "30s" or "5m" into seconds.

    :param value: Duration string ending in "s" or "m"
    :returns: Duration in seconds
    """
    return int(value[:-1]) * (60 if value.endswith("m") else 1)


def _fmt_ms(ms: float) -> str:
    """
    Format milliseconds as a compact string.

    :param ms: Milliseconds value
    :returns: Formatted string like "123ms"
    """
    return f"{ms:.0f}ms"


def _fmt_clock(seconds: float) -> str:
    """
    Format seconds as a MM:SS clock string.

    :param seconds: Elapsed seconds
    :returns: Formatted clock string like "01:23"
    """
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes:02d}:{secs:02d}"


class ActiveBenchmarkScreen(Screen):
    """
    Live dashboard shown while a benchmark is running.
    """

    def __init__(
        self, scenario, users: int, duration: str, config, ramp_up: str = "0s"
    ) -> None:
        """
        Create the screen and its benchmark runner.

        :param scenario: Benchmark scenario to run
        :param users: Number of concurrent workers
        :param duration: Duration string like "30s" or "5m"
        :param config: Application configuration
        :param ramp_up: Ramp-up duration string like "10s" or "1m"
        """
        super().__init__()
        self.runner = BenchmarkRunner(
            scenario=scenario,
            users=users,
            duration=_parse_duration(duration),
            ramp_up=_parse_duration(ramp_up),
            config=config,
        )
        self._samples: list[float] = []
        self._latency_samples: list[float] = []
        self._last_snapshot: dict | None = None

    def compose(self) -> ComposeResult:
        """
        Build the dashboard widgets.

        :returns: Widgets to display on the screen
        """
        yield Static(LOGO, id="logo")
        yield Container(
            Horizontal(
                Label(f"Scenario: {self.runner.scenario.name}", id="scenario"),
                Label(f"Workers: {self.runner.users}", id="workers"),
                Label("Runtime: 00:00 / 00:00", id="runtime"),
                classes="stats-header",
            ),
            ProgressBar(total=self.runner.duration, show_eta=False, id="progress"),
            Label("Throughput (req/sec)", classes="plot-title"),
            PlotWidget(id="throughput-plot"),
            Label("Latency (ms)", classes="plot-title"),
            PlotWidget(id="latency-plot"),
            Grid(
                Label("Requests", classes="stat-label"),
                Label("0", id="requests", classes="stat-value"),
                Label("Throughput", classes="stat-label"),
                Label("0 req/sec", id="throughput", classes="stat-value"),
                Label("P50", classes="stat-label"),
                Label("0ms", id="p50", classes="stat-value"),
                Label("P95", classes="stat-label"),
                Label("0ms", id="p95", classes="stat-value"),
                Label("P99", classes="stat-label"),
                Label("0ms", id="p99", classes="stat-value"),
                Label("Errors", classes="stat-label"),
                Label("0", id="errors", classes="stat-value"),
                classes="stats-grid",
            ),
            Button("Cancel Benchmark", id="return", classes="btn"),
            id="active-benchmark-container",
        )

    def on_mount(self) -> None:
        """
        Set up plots, start the benchmark worker, and schedule refreshes.
        """
        self._setup_plots()
        self.run_worker(self._run(), exclusive=True)
        self._timer = self.set_interval(1, self._refresh)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """
        Stop the benchmark and return to the previous screen on cancel.

        :param event: Button press event
        """
        if event.button.id == "return":
            self.runner.stop()
            self.app.pop_screen()

    def key_down(self) -> None:
        """
        Move focus to the next widget.
        """
        self.focus_next()

    def key_up(self) -> None:
        """
        Move focus to the previous widget.
        """
        self.focus_previous()

    def _setup_plots(self) -> None:
        """
        Configure both plot widgets with shared axis formatting.
        """
        for plot_id, ylabel in (
            ("#throughput-plot", "req/sec"),
            ("#latency-plot", "ms"),
        ):
            plot = self.query_one(plot_id, PlotWidget)
            plot.set_x_formatter(DurationFormatter())
            plot.set_y_formatter(NumericAxisFormatter())
            plot.set_xlabel("Time")
            plot.set_ylabel(ylabel)
            plot.set_ylimits(ymin=0)
            plot.show_legend(location=LegendLocation.TOPRIGHT)

    async def _run(self) -> None:
        """
        Run the benchmark, showing an error screen on failure.
        """
        try:
            await self.runner.run()
        except httpx.HTTPError as error:
            ErrorScreen.show(
                self.app,
                "Benchmark Failed",
                "Velox could not connect to the Jellyfin server.",
                str(error),
            )
        except Exception as error:
            ErrorScreen.show(
                self.app,
                "Unexpected Error",
                "An unexpected error occurred while running the benchmark.",
                str(error),
            )

    def _refresh(self) -> None:
        """
        Refresh stats and plots, then open details when the run finishes.
        """
        elapsed = self.runner.elapsed
        snap = self.runner.metrics.snapshot()
        self._record_sample(snap)
        self._update_stats(elapsed, snap)
        self._update_plots()
        if self.runner.done and not self.runner.cancelled:
            self._timer.stop()
            self.app.switch_screen(BenchmarkDetailsScreen(self.runner.benchmark))

    def _record_sample(self, snap: dict) -> None:
        """
        Append a per-second throughput/latency sample derived from the snapshot.

        :param snap: Current metrics snapshot
        """
        if self._last_snapshot is None:
            self._last_snapshot = snap
            return
        self._samples.append(snap["requests"] - self._last_snapshot["requests"])
        self._latency_samples.append(snap["p50"])
        self._last_snapshot = snap

    def _update_stats(self, elapsed: float, snap: dict) -> None:
        """
        Update the stat labels with the latest snapshot values.

        :param elapsed: Seconds elapsed in the run
        :param snap: Current metrics snapshot
        """
        self.query_one("#runtime", Label).update(
            f"Runtime: {_fmt_clock(elapsed)} / {_fmt_clock(self.runner.duration)}"
        )
        self.query_one("#workers", Label).update(
            f"Workers: {self.runner.active_users}/{self.runner.users}"
        )
        self.query_one("#progress", ProgressBar).update(progress=elapsed)
        self.query_one("#requests", Label).update(f"{snap['requests']:,}")
        self.query_one("#throughput", Label).update(
            f"{snap['requests'] / max(elapsed, 1):.0f} req/sec"
        )
        self.query_one("#p50", Label).update(_fmt_ms(snap["p50"]))
        self.query_one("#p95", Label).update(_fmt_ms(snap["p95"]))
        self.query_one("#p99", Label).update(_fmt_ms(snap["p99"]))
        self.query_one("#errors", Label).update(f"{snap['errors']}")

    def _update_plots(self) -> None:
        """
        Redraw both plots with the samples collected so far.
        """
        x = range(len(self._samples))
        for plot_id, data, label in (
            ("#throughput-plot", self._samples, "req/sec"),
            ("#latency-plot", self._latency_samples, "P50"),
        ):
            plot = self.query_one(plot_id, PlotWidget)
            plot.clear()
            plot.plot(
                x,
                data,
                line_style="bold #fcc179",
                hires_mode=HiResMode.BRAILLE,
                label=label,
            )
