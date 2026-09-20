import random

import httpx

from .base import BenchmarkScenario

SORT_ORDERS = [
    "SortName",
    "DateCreated",
    "PremiereDate",
    "ProductionYear",
    "CommunityRating",
    "Runtime",
    "Random",
    "Name",
]

FILTERS = [
    "IsFolder",
    "IsNotFolder",
    "IsUnplayed",
    "IsPlayed",
    "IsFavorite",
    "IsResumable",
]

ITEM_TYPES = [
    "Movie",
    "Series",
    "Season",
    "Episode",
    "MusicAlbum",
    "MusicArtist",
    "Audio",
    "Video",
    "BoxSet",
]

PAGE_SIZE = 50


class LibraryBenchmarkScenario(BenchmarkScenario):
    name = "Library"
    fast_latency = 300.0
    slow_latency = 700.0

    def __init__(self) -> None:
        """
        Setup the scenarios cached state. Initializes user id, folder list,
        and total item count to empty placeholders that get filled during setup.
        """
        self._user_id: str | None = None
        self._folder_ids: list[str] = []
        self._total_items = 0

    async def setup(self, client: httpx.AsyncClient) -> None:
        """
        Fetch the server's user, media folders, and total item count. Cached so the
        run loop can pick realistic targets without hammering the server with discovery calls
        on every request.

        :param client: The shared HTTP client used for all requests
        """
        users = await client.get("/Users")
        users.raise_for_status()
        user_list = users.json()
        if user_list:
            self._user_id = user_list[0]["Id"]

        folders = await client.get("/Library/MediaFolders")
        folders.raise_for_status()
        self._folder_ids = [item["Id"] for item in folders.json().get("Items", [])]

        counts = await client.get("/Items/Counts", params={"userId": self._user_id})
        counts.raise_for_status()
        self._total_items = counts.json().get("Total", 0)

    async def run(self, client: httpx.AsyncClient) -> bool:
        """
        Pick a random library action and execute it. Each call simulates a different
        kind of browsing behaviour so the load spread across the run looks like real
        traffic.

        :param client: The shared HTTP client used for all requests
        :returns: True if the request succeeded, False otherwise
        """
        action = random.choice(
            [
                self._browse_root,
                self._browse_folder,
                self._paginate,
                self._sort,
                self._filter,
                self._by_type,
                self._latest,
                self._counts,
            ]
        )
        return await action(client)

    async def _browse_root(self, client: httpx.AsyncClient) -> bool:
        """
        List the top level of the library. Acts as a user opening the home
        screen and seeing everything at once.

        :param client: The shared HTTP client used for all requests
        :returns: True if the request suceeded, False otherwise
        """
        return await self._items(client)

    async def _browse_folder(self, client: httpx.AsyncClient) -> bool:
        """
        List the content of a random media folder. Picks from folders
        discovered during setup, or does nothing if none were found.

        :param client: The shared HTTP client used for all requests
        :returns: True if the request succeeded, False otherwise
        """
        if not self._folder_ids:
            return True  # Nothing cached to browse
        return await self._items(client, parentId=random.choice(self._folder_ids))

    async def _paginate(self, client: httpx.AsyncClient) -> bool:
        """
        Jump to a random page of the full library. The offset is chosen
        from the total item count so deep pages get exercised, not just the
        first screen.

        :param client: The shared HTTP client used for all requests
        :returns: True if the requests succeeded, False otherwise
        """
        offset = random.randint(0, max(self._total_items - 1, 0))
        return await self._items(client, startIndex=offset)

    async def _sort(self, client: httpx.AsyncClient) -> bool:
        """
        List items sorted by a random field and direction.

        :param client: The shared HTTP client used for all requests
        :returns: True if the request succeeded, False otherwise
        """
        return await self._items(
            client,
            sortBy=random.choice(SORT_ORDERS),
            sortOrder=random.choice(["Ascending", "Descending"]),
        )

    async def _filter(self, client: httpx.AsyncClient) -> bool:
        """
        List items filtered by a random criterion, such as favorites,
        played stated, and folders.

        :param client: The shared HTTP client used for all requests
        :returns: True if the request succeeded, False otherwise
        """
        return await self._items(client, filters=random.choice(FILTERS))

    async def _by_type(self, client: httpx.AsyncClient) -> bool:
        """
        List items of a random media type such as movies, series, episodes.

        :param client: The shared HTTP client used for all requests
        :returns: True if the request succeeded, False otherwise
        """
        return await self._items(client, includeItemTypes=random.choice(ITEM_TYPES))

    async def _items(self, client: httpx.AsyncClient, **extra: object) -> bool:
        """
        Run a generic items query with the given extra parameters. Shared request
        behind most of the browser actions, so they all hit the same endpoint with
        different options.

        :param client: The shared HTTP client used for all requests
        :param extra: Additional query params to pass to the endpoint
        :returns: True if the request succeeded, False otherwise
        """
        resp = await client.get(
            "/Items",
            params={
                "userId": self._user_id,
                "recursive": True,
                "limit": PAGE_SIZE,
                "enableImages": False,
                **extra,
            },
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
            params={"userId": self._user_id, "limit": 20},
        )
        return resp.status_code < 400

    async def _counts(self, client: httpx.AsyncClient) -> bool:
        """
        Fetch the library item counts.

        :param client: The shared HTTP client used for all requests
        :returns: True if the request succeeded, False otherwise
        """
        resp = await client.get("/Items/Counts", params={"userId": self._user_id})
        return resp.status_code < 400
