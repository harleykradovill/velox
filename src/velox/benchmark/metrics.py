import asyncio
import bisect

_BUCKET_EDGES = [0, 100, 250, 500, 1000, 2000, 4000]


class Metrics:
    def __init__(self) -> None:
        self._latencies: list[float] = []
        self._errors = 0
        self._lock = asyncio.Lock()

    async def record(self, latency_ms: float, ok: bool) -> None:
        async with self._lock:
            self._latencies.append(latency_ms)
            if not ok:
                self._errors += 1

    def snapshot(self) -> dict:
        lat = sorted(self._latencies)
        return {
            "requests": len(lat),
            "errors": self._errors,
            "avg": sum(lat) / len(lat) if lat else 0.0,
            "p50": self._percentile(lat, 50),
            "p95": self._percentile(lat, 95),
            "p99": self._percentile(lat, 99),
            "histogram": self._histogram(lat),
        }

    @staticmethod
    def _percentile(sorted_lat: list[float], p: int) -> float:
        if not sorted_lat:
            return 0.0
        idx = min(len(sorted_lat) - 1, round(p / 100 * (len(sorted_lat) - 1)))
        return sorted_lat[idx]

    @staticmethod
    def _histogram(sorted_lat: list[float]) -> list[dict]:
        """
        Bucket latencies into fixed ranges and count each bucket.

        :param sorted_lat: Latencies in ascending order
        :returns: A list of {"label", "count"} buckets for the distribution
        """
        counts = [0] * (len(_BUCKET_EDGES) - 1)
        for latency in sorted_lat:
            idx = min(bisect.bisect_right(_BUCKET_EDGES, latency) - 1, len(counts) - 1)
            counts[idx] += 1
        return [
            {
                "label": (
                    f"{_BUCKET_EDGES[i]}+"
                    if i == len(counts) - 1
                    else f"{_BUCKET_EDGES[i]}-{_BUCKET_EDGES[i + 1]}"
                ),
                "count": count,
            }
            for i, count in enumerate(counts)
        ]
