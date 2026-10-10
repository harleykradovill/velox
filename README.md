<p align="center">
<img height="100" alt="Velox" src="https://github.com/harleykradovill/velox/blob/main/assets/velox.png?raw=true" />
</p>

A terminal app that load tests your Jellyfin server to show potential problems.

### Scenarios

- **General:** Mixed traffic across core endpoints: user lookup, library browsing, search, and item metadata.
- **Library:** Library browsing: root and folder listings, pagination, sorting, filtering, item-type views, latest items, and item counts.
- **Search:** Search queries: plain terms, item-type and media-type filters, paged results, and user-scoped searches.
- **Discovery:** Home screen discovery: suggestions, movie recommendations, next up and upcoming episodes, latest items, resume rows, and user data.
- **People & Studios:** Person, studio, genre, and year browsing: listings, detail views, sorting, and person-type filters.

### Running a benchmark

Five configurable options:

- **Scenario:** The scenario that the benchmark exercises.
- **Concurrent Workers:** How many simultaneous virual users hit the server at once. Higher values put more load on the server.
- **Ramp-Up Time:** How long it takes to bring all workers online. A longer ramp-up eases the the server into the load instead of hitting it with everything at once.
- **Request Delay:** The delay each worker waits between requests. Real users don't hammer the API back-to-back, so a small delay makes the load more realistic than a pure saturation test.
- **Duration:** How long the benchmark runs.
