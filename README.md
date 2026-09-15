<p align="center">
<img height="100" alt="Velox" src="https://github.com/harleykradovill/velox/blob/main/assets/velox.png?raw=true" />
</p>

A terminal app that load tests your Jellyfin server and shows you how it holds up.

### Scenarios

- **API Stress Test:** A mix of user lookups, library browsing, searching, and metadata fetches.
- **Library Stress Test:** Heavy browsing and filtering of libraries with different sort orders, filters, and item types.

### Running a benchmark

Four configurable options:

- **Scenario:** The scenario that the benchmark exercises.
- **Concurrent Workers:** How many simultaneous virual users hit the server at once. Higher values put more load on the server.
- **Ramp-Up Time:** How long it takes to bring all workers online. A longer ramp-up eases the server into the load instead of hitting it with everything at once.
- **Duration:** How long the benchmark runs.
