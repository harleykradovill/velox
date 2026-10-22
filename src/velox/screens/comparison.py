from textual.app import ComposeResult
from textual.containers import Center, Grid, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Label, Static
from textual_plot import HiResMode, NumericAxisFormatter, PlotWidget
from textual_plot.axis_formatter import CategoricalAxisFormatter

from ..ascii import LOGO
from ..storage import Benchmark


def _fmt_ms(ms: float) -> str:
    return f"{ms:.0f}ms"


def _fmt_duration(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes:02d}:{secs:02d}"


def _fmt_throughput(requests: int, duration: float) -> str:
    return f"{requests / max(duration, 1):.1f} req/sec"


def _compare_card(label: str, a_value: str, b_value: str) -> Vertical:
    return Vertical(
        Label(label, classes="stat-label"),
        Label(f"{a_value} vs {b_value}", classes="compare-value"),
        classes="stat-card",
    )


class ComparisonScreen(Screen):
    def __init__(self, benchmark_a: Benchmark, benchmark_b: Benchmark) -> None:
        super().__init__()
        self.benchmark_a = benchmark_a
        self.benchmark_b = benchmark_b

    def compose(self) -> ComposeResult:
        a = self.benchmark_a.results
        b = self.benchmark_b.results
        yield Static(LOGO, id="logo")
        yield Vertical(
            Label(
                f"{self.benchmark_a.scenario}  ·  "
                f"#{self.benchmark_a.id} vs #{self.benchmark_b.id}",
                id="compare-title",
            ),
            Center(
                Horizontal(
                    Label(f"A: #{self.benchmark_a.id}", classes="compare-col"),
                    Label(f"B: #{self.benchmark_b.id}", classes="compare-col"),
                    id="compare-columns",
                )
            ),
            Center(
                Grid(
                    _compare_card("Avg Latency", _fmt_ms(a["avg"]), _fmt_ms(b["avg"])),
                    _compare_card(
                        "Avg Throughput",
                        _fmt_throughput(a["requests"], self.benchmark_a.duration),
                        _fmt_throughput(b["requests"], self.benchmark_b.duration),
                    ),
                    _compare_card(
                        "Requests", f"{a['requests']:,}", f"{b['requests']:,}"
                    ),
                    _compare_card("Errors", f"{a['errors']}", f"{b['errors']}"),
                    _compare_card("P50", _fmt_ms(a["p50"]), _fmt_ms(b["p50"])),
                    _compare_card("P95", _fmt_ms(a["p95"]), _fmt_ms(b["p95"])),
                    _compare_card("P99", _fmt_ms(a["p99"]), _fmt_ms(b["p99"])),
                    _compare_card(
                        "Error Rate",
                        f"{a['errors'] / max(a['requests'], 1):.2%}",
                        f"{b['errors'] / max(b['requests'], 1):.2%}",
                    ),
                    classes="stats-grid",
                )
            ),
            Label("Latency Distribution", classes="plot-title"),
            Center(PlotWidget(id="histogram-plot", allow_pan_and_zoom=False)),
            Label(
                f"A: #{self.benchmark_a.id}  {_fmt_duration(self.benchmark_a.duration)}  {self.benchmark_a.workers} workers   |   B: #{self.benchmark_b.id}  {_fmt_duration(self.benchmark_b.duration)}  {self.benchmark_b.workers} workers",
                id="compare-meta",
            ),
            Center(Button("Go Back", id="return", classes="btn-details")),
            id="compare-container",
        )

    def on_mount(self) -> None:
        """
        Draw the combined latency distribution plot.
        """
        self._setup_histogram()

    def _setup_histogram(self) -> None:
        """
        Render both benchmark histograms as grouped bar plots.
        """
        plot = self.query_one("#histogram-plot", PlotWidget)
        plot.set_y_formatter(NumericAxisFormatter())
        plot.set_xlabel("Latency (ms)")
        plot.set_ylimits(ymin=0)
        plot.show_legend(is_visible=True)
        histograms = [
            (benchmark, style)
            for benchmark, style in (
                (self.benchmark_a, "bold #fcc179"),
                (self.benchmark_b, "bold #7aa2f7"),
            )
            if benchmark.results.get("histogram")
        ]
        if not histograms:
            return
        labels = [bucket["label"] for bucket in histograms[0][0].results["histogram"]]
        plot.set_x_formatter(CategoricalAxisFormatter(labels))
        plot.set_xticks(list(range(1, len(labels) + 1)))
        for i, (benchmark, style) in enumerate(histograms):
            counts = [bucket["count"] for bucket in benchmark.results["histogram"]]
            x = [pos + (i - 0.5) * 0.4 for pos in range(1, len(labels) + 1)]
            plot.bar(
                x,
                counts,
                width=0.4,
                bar_style=style,
                label=f"#{benchmark.id}",
                hires_mode=HiResMode.BRAILLE,
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "return":
            self.app.pop_screen()

    def key_down(self) -> None:
        self.focus_next()

    def key_up(self) -> None:
        self.focus_previous()