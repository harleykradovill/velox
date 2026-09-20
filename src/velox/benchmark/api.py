import random

import httpx

from .base import BenchmarkScenario

SEARCH_TERMS = [
    "the",
    "of",
    "and",
    "star",
    "love",
    "night",
    "world",
    "man",
    "time",
    "life",
    "fire",
    "dream",
    "1",
    "first",
    "last",
    "A",
]


class ApiBenchmarkScenario(BenchmarkScenario):
    name = "API"
    fast_latency = 150.0
    slow_latency = 400.0

    def __init__(self) -> None:
        self._item_ids: list[str] = []
        self._user_id: str | None = None

    async def setup(self, client: httpx.AsyncClient) -> None:
        users = await client.get("/Users")
        users.raise_for_status()
        user_list = users.json()
        if user_list:
            self._user_id = user_list[0]["Id"]

        resp = await client.get("/Items", params={"limit": 100, "enableImages": False})
        resp.raise_for_status()
        self._item_ids = [item["Id"] for item in resp.json().get("Items", [])]

    async def run(self, client: httpx.AsyncClient) -> bool:
        action = random.choice(
            [self._user_lookup, self._library, self._search, self._metadata]
        )
        return await action(client)

    async def _user_lookup(self, client: httpx.AsyncClient) -> bool:
        resp = await client.get("/Users")
        return resp.status_code < 400

    async def _library(self, client: httpx.AsyncClient) -> bool:
        resp = await client.get("/Items", params={"limit": 50, "enableImages": False})
        return resp.status_code < 400

    async def _search(self, client: httpx.AsyncClient) -> bool:
        resp = await client.get(
            "/Search/Hints",
            params={"searchTerm": random.choice(SEARCH_TERMS), "limit": 20},
        )
        return resp.status_code < 400

    async def _metadata(self, client: httpx.AsyncClient) -> bool:
        if not self._item_ids or not self._user_id:
            return True  # Nothing cached to fetch
        resp = await client.get(
            f"/Items/{random.choice(self._item_ids)}",
            params={"userId": self._user_id},
        )
        return resp.status_code < 400
