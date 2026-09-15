from datetime import datetime

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Button, Label, ListItem, ListView, Static

from ..ascii import LOGO
from ..storage import Benchmark, list_benchmarks
from .benchmark_details import BenchmarkDetailsScreen

COLUMNS = {
    "date": 16,
    "scenario": 20,
    "duration": 10,
    "ramp_up": 10,
    "workers": 10,
}


def _fmt_duration(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes:02d}:{secs:02d}"


def _fmt_created(created_at: datetime) -> str:
    return created_at.strftime("%Y-%m-%d %H:%M")


def _row(*cells: str) -> Horizontal:
    return Horizontal(
        *(
            Label(cell, classes=f"cell cell-{name}")
            for name, cell in zip(COLUMNS, cells)
        ),
        classes="row",
    )


class BenchmarkHistoryScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Static(LOGO, id="logo")
        yield Container(
            Container(
                _row("Date/Time", "Scenario", "Duration", "Ramp-Up", "Workers"),
                ListView(id="history-list", classes="history-list"),
                id="history-table",
            ),
            Button("Go Back", id="return", classes="btn"),
            id="history-container",
        )

    def on_mount(self) -> None:
        self.benchmarks = {b.id: b for b in list_benchmarks()}
        self._populate()

    def _populate(self) -> None:
        list_view = self.query_one("#history-list", ListView)
        for benchmark in self.benchmarks.values():
            list_view.append(
                ListItem(
                    _row(
                        _fmt_created(benchmark.created_at),
                        benchmark.scenario,
                        _fmt_duration(benchmark.duration),
                        _fmt_duration(benchmark.ramp_up),
                        f"{benchmark.workers}",
                    ),
                    id=f"benchmark-{benchmark.id}",
                )
            )

    @on(ListView.Selected)
    def on_selected(self, event: ListView.Selected) -> None:
        benchmark_id = int(event.item.id.removeprefix("benchmark-"))
        self.app.push_screen(BenchmarkDetailsScreen(self.benchmarks[benchmark_id]))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "return":
            self.app.pop_screen()
