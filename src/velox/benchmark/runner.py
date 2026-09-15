import asyncio
import time

import httpx

from .base import BenchmarkScenario
from .metrics import Metrics
from ..storage import save_benchmark


class BenchmarkRunner:
    def __init__(
        self,
        scenario: BenchmarkScenario,
        users: int,
        duration: float,
        config,
        ramp_up: float = 0.0,
    ) -> None:
        self.scenario = scenario
        self.users = users
        self.duration = duration
        self.config = config
        self.ramp_up = min(ramp_up, duration)
        self.metrics = Metrics()
        self._stop = asyncio.Event()
        self._started: float | None = None
        self._done = False
        self._cancelled = False
        self.benchmark = None

    @property
    def active_users(self) -> int:
        """
        Number of workers currently performing requests.

        Follows the same ramp curve as the gating logic so the
        dashboard reflects actual load rather than spawned tasks.

        :returns: Active worker count for the current point in the run
        """
        return min(self.target_users, self.users)

    @property
    def target_users(self) -> int:
        """
        Number of workers that should be active at the current elapsed time.

        Scales linearly from a fraction of the full count to the full count
        over the ramp-up window, then stays at the full count.

        :returns: Target worker count for the current point in the run
        """
        if self.ramp_up <= 0:
            return self.users
        progress = min(self.elapsed / self.ramp_up, 1.0)
        return max(1, round(self.users * (0.25 + 0.75 * progress)))

    @property
    def elapsed(self) -> float:
        if self._started is None:
            return 0.0
        return min(time.monotonic() - self._started, self.duration)

    @property
    def done(self) -> bool:
        return self._done

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    async def run(self) -> None:
        headers = {
            "Authorization": f'MediaBrowser Token="{self.config.server.api_key}"'
        }
        async with httpx.AsyncClient(
            base_url=self.config.server.url.rstrip("/"),
            headers=headers,
            timeout=30,
        ) as client:
            await self.scenario.setup(client)
            self._started = time.monotonic()
            tasks = [
                asyncio.create_task(self._user(client, i)) for i in range(self.users)
            ]
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.duration)
            except asyncio.TimeoutError:
                pass
            self._stop.set()
            await asyncio.gather(*tasks, return_exceptions=True)
            self._done = True
            if self._cancelled:
                return
            self.benchmark = save_benchmark(
                scenario=self.scenario.name,
                duration=self.duration,
                workers=self.users,
                ramp_up=self.ramp_up,
                results=self.metrics.snapshot(),
            )

    def stop(self) -> None:
        self._stop.set()
        self._cancelled = True

    async def _user(self, client: httpx.AsyncClient, index: int) -> None:
        while not self._stop.is_set():
            if index >= self.target_users:
                await asyncio.sleep(0.1)
                continue
            start = time.perf_counter()
            ok = await self.scenario.run(client)
            elapsed = (time.perf_counter() - start) * 1000
            await self.metrics.record(elapsed, ok)
