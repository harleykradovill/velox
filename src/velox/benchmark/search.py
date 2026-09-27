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

ITEM_TYPES = [
    "Movie",
    "Series",
    "Episode",
    "MusicAlbum",
    "MusicArtist",
    "Audio",
    "Video",
    "BoxSet",
]

MEDIA_TYPES = [
    "Video",
    "Audio",
    "Photo",
    "Book",
]

PAGE_SIZE = 20


class SearchBenchmarkScenario(BenchmarkScenario):
    name = "Search"
    fast_latency = 200.0
    slow_latency = 500.0

    def __init__(self) -> None:
        """
        Setup the scenarios cached state. Initializes the user id to an empty
        placeholder that gets filled during setup.
        """
        self._user_id: str | None = None

    async def setup(self, client: httpx.AsyncClient) -> None:
        """
        Fetch the server's user so searches can be scoped to a real library.

        :param client: The shared HTTP client used for all requests
        """
        users = await client.get("/Users")
        users.raise_for_status()
        user_list = users.json()
        if user_list:
            self._user_id = user_list[0]["Id"]

    async def run(self, client: httpx.AsyncClient) -> bool:
        """
        Pick a random search action and execute it. Each call simulates a
        different kind of search so the load spread across the run looks like
        real traffic.

        :param client: The shared HTTP client used for all requests
        :returns: True if the request succeeded, False otherwise
        """
        action = random.choice(
            [
                self._plain,
                self._by_type,
                self._by_media_type,
                self._paged,
                self._scoped,
            ]
        )
        return await action(client)

    async def _plain(self, client: httpx.AsyncClient) -> bool:
        """
        Run a plain search with no extra filters.

        :param client: The shared HTTP client used for all requests
        :returns: True if the request succeeded, False otherwise
        """
        return await self._search(client)

    async def _by_type(self, client: httpx.AsyncClient) -> bool:
        """
        Search for a random item type such as movies, series, or albums.

        :param client: The shared HTTP client used for all requests
        :returns: True if the request succeeded, False otherwise
        """
        return await self._search(client, includeItemTypes=random.choice(ITEM_TYPES))

    async def _by_media_type(self, client: httpx.AsyncClient) -> bool:
        """
        Search for a random media type such as video or audio.

        :param client: The shared HTTP client used for all requests
        :returns: True if the request succeeded, False otherwise
        """
        return await self._search(client, mediaTypes=random.choice(MEDIA_TYPES))

    async def _paged(self, client: httpx.AsyncClient) -> bool:
        """
        Jump to a random page of search results.

        :param client: The shared HTTP client used for all requests
        :returns: True if the request succeeded, False otherwise
        """
        offset = random.randint(0, 4) * PAGE_SIZE
        return await self._search(client, startIndex=offset)

    async def _scoped(self, client: httpx.AsyncClient) -> bool:
        """
        Search within a specific user's library.

        :param client: The shared HTTP client used for all requests
        :returns: True if the request succeeded, False otherwise
        """
        return await self._search(client, userId=self._user_id)

    async def _search(self, client: httpx.AsyncClient, **extra: object) -> bool:
        """
        Run a search hint query with the given extra parameters. Shared request
        behind most of the search actions, so they all hit the same endpoint
        with different options.

        :param client: The shared HTTP client used for all requests
        :param extra: Additional query params to pass to the endpoint
        :returns: True if the request succeeded, False otherwise
        """
        resp = await client.get(
            "/Search/Hints",
            params={
                "searchTerm": random.choice(SEARCH_TERMS),
                "limit": PAGE_SIZE,
                **extra,
            },
        )
        return resp.status_code < 400
