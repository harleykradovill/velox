import random

import httpx

from .base import BenchmarkScenario

PAGE_SIZE = 20


class DiscoveryBenchmarkScenario(BenchmarkScenario):
    name = "Discovery"
    description = (
        "Home screen discovery: suggestions, movie recommendations, next up "
        "and upcoming episodes, latest items, resume rows, and user data."
    )
    fast_latency = 250.0
    slow_latency = 600.0

    def __init__(self) -> None:
        """
        Setup the scenarios cached state. Initializes the user id and item id
        list to empty placeholders that get filled during setup.
        """
        self._user_id: str | None = None
        self._item_ids: list[str] = []

    async def setup(self, client: httpx.AsyncClient) -> None:
        """
        Fetch the server's user and a sample of item ids. Cached so the run
        loop can pick realistic targets without hammering the server with
        discovery calls on every request.

        :param client: The shared HTTP client used for all requests
        """
        users = await client.get("/Users")
        users.raise_for_status()
        user_list = users.json()
        if user_list:
            self._user_id = user_list[0]["Id"]

        resp = await client.get("/Items", params={"limit": 100, "enableImages": False})
        resp.raise_for_status()
        self._item_ids = [item["Id"] for item in resp.json().get("Items", [])]

    async def run(self, client: httpx.AsyncClient) -> bool:
        """
        Pick a random discovery action and execute it. Each call simulates a
        different part of the home screen so the load spread across the run
        looks like real traffic.

        :param client: The shared HTTP client used for all requests
        :returns: True if the request succeeded, False otherwise
        """
        action = random.choice(
            [
                self._suggestions,
                self._recommendations,
                self._next_up,
                self._upcoming,
                self._latest,
                self._resume,
                self._user_data,
            ]
        )
        return await action(client)

    async def _suggestions(self, client: httpx.AsyncClient) -> bool:
        """
        Fetch suggested items for the user.

        :param client: The shared HTTP client used for all requests
        :returns: True if the request succeeded, False otherwise
        """
        resp = await client.get(
            "/Items/Suggestions",
            params={"userId": self._user_id, "limit": PAGE_SIZE},
        )
        return resp.status_code < 400

    async def _recommendations(self, client: httpx.AsyncClient) -> bool:
        """
        Fetch movie recommendations grouped into categories.

        :param client: The shared HTTP client used for all requests
        :returns: True if the request succeeded, False otherwise
        """
        resp = await client.get(
            "/Movies/Recommendations",
            params={"userId": self._user_id, "categoryLimit": 5, "itemLimit": 8},
        )
        return resp.status_code < 400

    async def _next_up(self, client: httpx.AsyncClient) -> bool:
        """
        Fetch the next up episodes for the user.

        :param client: The shared HTTP client used for all requests
        :returns: True if the request succeeded, False otherwise
        """
        resp = await client.get(
            "/Shows/NextUp",
            params={"userId": self._user_id, "limit": PAGE_SIZE},
        )
        return resp.status_code < 400

    async def _upcoming(self, client: httpx.AsyncClient) -> bool:
        """
        Fetch the upcoming episodes for the user.

        :param client: The shared HTTP client used for all requests
        :returns: True if the request succeeded, False otherwise
        """
        resp = await client.get(
            "/Shows/Upcoming",
            params={"userId": self._user_id, "limit": PAGE_SIZE},
        )
        return resp.status_code < 400

    async def _latest(self, client: httpx.AsyncClient) -> bool:
        """
        Fetch the most recently added items.

        :param client: The shared HTTP client used for all requests
        :returns: True if the request succeeded, False otherwise
        """
        resp = await client.get(
            "/Items/Latest",
            params={"userId": self._user_id, "limit": PAGE_SIZE},
        )
        return resp.status_code < 400

    async def _resume(self, client: httpx.AsyncClient) -> bool:
        """
        Fetch the items the user has started but not finished.

        :param client: The shared HTTP client used for all requests
        :returns: True if the request succeeded, False otherwise
        """
        resp = await client.get(
            "/UserItems/Resume",
            params={"userId": self._user_id, "limit": PAGE_SIZE},
        )
        return resp.status_code < 400

    async def _user_data(self, client: httpx.AsyncClient) -> bool:
        """
        Fetch the user data for a random item, such as play state and rating.

        :param client: The shared HTTP client used for all requests
        :returns: True if the request succeeded, False otherwise
        """
        if not self._item_ids or not self._user_id:
            return True  # Nothing cached to fetch
        resp = await client.get(
            f"/UserItems/{random.choice(self._item_ids)}/UserData",
            params={"userId": self._user_id},
        )
        return resp.status_code < 400
