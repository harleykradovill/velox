import random

import httpx

from .base import BenchmarkScenario

PERSON_TYPES = [
    "Actor",
    "Director",
    "Writer",
    "Producer",
    "Composer",
]

SORT_ORDERS = [
    "SortName",
    "Name",
    "Random",
    "PremiereDate",
    "ProductionYear",
    "CommunityRating",
]

PAGE_SIZE = 50


class PeopleStudiosBenchmarkScenario(BenchmarkScenario):
    name = "People & Studios"
    description = (
        "People and studio browsing: person, studio, genre, and year "
        "listings, detail views, sorting, and person-type filters."
    )
    fast_latency = 300.0
    slow_latency = 700.0

    def __init__(self) -> None:
        """
        Setup the scenarios cached state. Initializes the user id and the name
        lists for people, studios, genres, and years to empty placeholders
        that get filled during setup.
        """
        self._user_id: str | None = None
        self._person_names: list[str] = []
        self._studio_names: list[str] = []
        self._genre_names: list[str] = []
        self._years: list[str] = []

    async def setup(self, client: httpx.AsyncClient) -> None:
        """
        Fetch the server's user and a sample of names for each browsing
        category. Cached so the run loop can pick realistic targets without
        hammering the server with discovery calls on every request.

        :param client: The shared HTTP client used for all requests
        """
        users = await client.get("/Users")
        users.raise_for_status()
        user_list = users.json()
        if user_list:
            self._user_id = user_list[0]["Id"]

        self._person_names = await self._names(client, "/Persons")
        self._studio_names = await self._names(client, "/Studios")
        self._genre_names = await self._names(client, "/Genres")
        self._years = await self._names(client, "/Years")

    async def _names(self, client: httpx.AsyncClient, path: str) -> list[str]:
        """
        Fetch a sample of names from a browsing endpoint.

        :param client: The shared HTTP client used for all requests
        :param path: Endpoint path to fetch names from
        :returns: List of item names
        """
        resp = await client.get(path, params={"limit": 100, "enableImages": False})
        resp.raise_for_status()
        return [
            item["Name"] for item in resp.json().get("Items", []) if item.get("Name")
        ]

    async def run(self, client: httpx.AsyncClient) -> bool:
        """
        Pick a random people and studio action and execute it. Each call
        simulates a different kind of browsing so the load spread across
        the run looks like real traffic.

        :param client: The shared HTTP client used for all requests
        :returns: True if the request succeeded, False otherwise
        """
        action = random.choice(
            [
                self._browse_persons,
                self._browse_studios,
                self._browse_genres,
                self._browse_years,
                self._person_detail,
                self._studio_detail,
                self._genre_detail,
                self._year_detail,
            ]
        )
        return await action(client)

    async def _browse_persons(self, client: httpx.AsyncClient) -> bool:
        """
        List persons filtered by a random person type such as actors or
        directors.

        :param client: The shared HTTP client used for all requests
        :returns: True if the request succeeded, False otherwise
        """
        return await self._list(
            client,
            "/Persons",
            personTypes=random.choice(PERSON_TYPES),
        )

    async def _browse_studios(self, client: httpx.AsyncClient) -> bool:
        """
        List studios sorted by a random field and direction.

        :param client: The shared HTTP client used for all requests
        :returns: True if the request succeeded, False otherwise
        """
        return await self._list(
            client,
            "/Studios",
            sortBy=random.choice(SORT_ORDERS),
            sortOrder=random.choice(["Ascending", "Descending"]),
        )

    async def _browse_genres(self, client: httpx.AsyncClient) -> bool:
        """
        List genres sorted by a random field and direction.

        :param client: The shared HTTP client used for all requests
        :returns: True if the request succeeded, False otherwise
        """
        return await self._list(
            client,
            "/Genres",
            sortBy=random.choice(SORT_ORDERS),
            sortOrder=random.choice(["Ascending", "Descending"]),
        )

    async def _browse_years(self, client: httpx.AsyncClient) -> bool:
        """
        List years sorted by a random field and direction.

        :param client: The shared HTTP client used for all requests
        :returns: True if the request succeeded, False otherwise
        """
        return await self._list(
            client,
            "/Years",
            sortBy=random.choice(SORT_ORDERS),
            sortOrder=random.choice(["Ascending", "Descending"]),
        )

    async def _person_detail(self, client: httpx.AsyncClient) -> bool:
        """
        Fetch the detail page for a random person.

        :param client: The shared HTTP client used for all requests
        :returns: True if the request succeeded, False otherwise
        """
        return await self._detail(client, "/Persons", self._person_names)

    async def _studio_detail(self, client: httpx.AsyncClient) -> bool:
        """
        Fetch the detail page for a random studio.

        :param client: The shared HTTP client used for all requests
        :returns: True if the request succeeded, False otherwise
        """
        return await self._detail(client, "/Studios", self._studio_names)

    async def _genre_detail(self, client: httpx.AsyncClient) -> bool:
        """
        Fetch the detail page for a random genre.

        :param client: The shared HTTP client used for all requests
        :returns: True if the request succeeded, False otherwise
        """
        return await self._detail(client, "/Genres", self._genre_names)

    async def _year_detail(self, client: httpx.AsyncClient) -> bool:
        """
        Fetch the detail page for a random year.


        :param client: The shared HTTP client used for all requests
        :returns: True if the request succeeded, False otherwise
        """
        return await self._detail(client, "/Years", self._years)

    async def _list(
        self, client: httpx.AsyncClient, path: str, **extra: object
    ) -> bool:
        """
        Run a generic listing query with the given extra parameters. Shared
        request behind most of the browse actions, so they all hit the same
        endpoints with different options.


        :param client: The shared HTTP client used for all requests
        :param path: Endpoint path to list items from
        :param extra: Additional query params to pass to the endpoint
        :returns: True if the request succeeded, False otherwise
        """
        resp = await client.get(
            path,
            params={
                "userId": self._user_id,
                "limit": PAGE_SIZE,
                "enableImages": False,
                **extra,
            },
        )
        return resp.status_code < 400

    async def _detail(
        self, client: httpx.AsyncClient, path: str, names: list[str]
    ) -> bool:
        """
        Fetch the detail page for a random cached name. Does nothing if no
        names were found during setup.


        :param client: The shared HTTP client used for all requests
        :param path: Endpoint path prefix for the detail route
        :param names: Cached names to pick from
        :returns: True if the request succeeded, False otherwise
        """
        if not names:
            return True  # Nothing cached to fetch
        name = random.choice(names)
        resp = await client.get(
            f"{path}/{name}",
            params={"userId": self._user_id},
        )
        return resp.status_code < 400
