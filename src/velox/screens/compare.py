from datetime import datetime

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Button, Label, ListItem, ListView, Select, Static

from ..ascii import LOGO
from ..storage import Benchmark, list_benchmarks
from .comparison import ComparisonScreen

SCENARIOS = [
    ("General", "General"),
    ("Library", "Library"),
    ("Search", "Search"),
    ("Discovery", "Discovery"),
    ("People & Studios", "People & Studios"),
]


def _fmt_duration(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes:02d}:{secs:02d}"


def _fmt_created(created_at: datetime) -> str:
    return created_at.strftime("%Y-%m-%d %H:%M")


class CompareScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Static(LOGO, id="logo")
        yield Container(
            Label("Scenario"),
            Select(
                SCENARIOS,
                id="scenario",
                classes="select",
                allow_blank=True,
                prompt="Select scenario",
            ),
            Horizontal(
                Container(
                    Label("Benchmark A", classes="compare-header"),
                    ListView(id="benchmark-a", classes="compare-list"),
                    id="compare-a",
                ),
                Container(
                    Label("Benchmark B", classes="compare-header"),
                    ListView(id="benchmark-b", classes="compare-list"),
                    id="compare-b",
                ),
                id="compare-lists",
            ),
            Button("Compare", id="compare", classes="btn", disabled=True),
            Button("Go Back", id="return", classes="btn"),
            id="compare-container",
        )

    def on_mount(self) -> None:
        """
        Load all persisted benchmarks and preselect a scenario with data.
        """
        self.benchmarks = {b.id: b for b in list_benchmarks()}
        self._selected: dict[str, Benchmark | None] = {
            "benchmark-a": None,
            "benchmark-b": None,
        }
        scenario = self.query_one("#scenario", Select)
        for name, _ in SCENARIOS:
            if any(b.scenario == name for b in self.benchmarks.values()):
                scenario.value = name
                break

    def on_select_changed(self, event: Select.Changed) -> None:
        """
        Repopulate both lists when the scenario changes.

        :param event: Select change event
        """
        if event.select.id == "scenario":
            self._populate_lists()

    def _populate_lists(self) -> None:
        """
        Fill each list with benchmarks matching the selected scenario.
        """
        scenario = self.query_one("#scenario", Select)
        for list_id in ("benchmark-a", "benchmark-b"):
            list_view = self.query_one(f"#{list_id}", ListView)
            list_view.clear()
            self._selected[list_id] = None
            if scenario.is_blank():
                continue
            for benchmark in self.benchmarks.values():
                if benchmark.scenario != scenario.value:
                    continue
                list_view.append(
                    ListItem(
                        Label(
                            f"{_fmt_created(benchmark.created_at)}  ·  "
                            f"{_fmt_duration(benchmark.duration)}  ·  "
                            f"{benchmark.workers} workers"
                        ),
                        id=f"{list_id}-{benchmark.id}",
                    )
                )
        self._update_compare_button()

    @on(ListView.Selected)
    def on_selected(self, event: ListView.Selected) -> None:
        """
        Remember the chosen benchmark for the list that was selected.

        :param event: List selection event
        """
        list_id = event.list_view.id
        benchmark_id = int(event.item.id.removeprefix(f"{list_id}-"))
        self._selected[list_id] = self.benchmarks[benchmark_id]
        self._update_compare_button()

    def _update_compare_button(self) -> None:
        """
        Enable the compare button once both benchmarks are chosen.
        """
        self.query_one("#compare", Button).disabled = not (
            self._selected["benchmark-a"] and self._selected["benchmark-b"]
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "return":
            self.app.pop_screen()
        elif event.button.id == "compare":
            self.app.push_screen(
                ComparisonScreen(
                    self._selected["benchmark-a"],
                    self._selected["benchmark-b"],
                )
            )

    def key_down(self) -> None:
        self.focus_next()

    def key_up(self) -> None:
        self.focus_previous()
