from abc import ABC, abstractmethod

import httpx


class BenchmarkScenario(ABC):
    name: str
    fast_latency = 350.0
    slow_latency = 650.0

    @abstractmethod
    async def setup(self, client: httpx.AsyncClient) -> None:
        """
        Perform one-time preparation before the benchmark loop.

        :param client: The shared HTTP client for the benchmark.
        """

    @abstractmethod
    async def run(self, client: httpx.AsyncClient) -> bool:
        """
        Perform one API operation.

        :param client: The shared HTTP client for the benchmark.
        :returns: True if the operation succeeded, False otherwise.
        """
