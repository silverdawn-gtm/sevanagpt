"""Request timing middleware — logs per-request latency with endpoint breakdown.

Adds an X-Process-Time header to every response and logs p50/p95/p99 stats
to a rotating in-memory buffer for the /metrics endpoint.
"""

import logging
import statistics
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# In-memory storage for latency samples per endpoint (last 1000 per route)
_MAX_SAMPLES = 1000
_latencies: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=_MAX_SAMPLES))


class TimingMiddleware(BaseHTTPMiddleware):
    """Measure and log request processing time for every endpoint."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start

        # Build a route key like "GET /api/v1/schemes"
        route_key = f"{request.method} {request.url.path}"

        # Store the sample
        _latencies[route_key].append(elapsed)

        # Add timing header
        response.headers["X-Process-Time"] = f"{elapsed:.4f}"

        # Log slow requests (> 2s)
        if elapsed > 2.0:
            logger.warning("Slow request: %s %.3fs", route_key, elapsed)
        else:
            logger.debug("Request: %s %.3fs", route_key, elapsed)

        return response


def get_metrics() -> dict:
    """Compute latency percentiles per endpoint.

    Returns a dict like:
    {
        "GET /api/v1/schemes": {
            "count": 150,
            "p50": 0.123,
            "p95": 0.456,
            "p99": 0.789,
            "max": 1.234,
        },
        ...
    }
    """
    result = {}
    for route, samples in _latencies.items():
        if not samples:
            continue
        sorted_samples = sorted(samples)
        n = len(sorted_samples)
        result[route] = {
            "count": n,
            "p50": round(sorted_samples[int(n * 0.50)], 4),
            "p95": round(sorted_samples[min(int(n * 0.95), n - 1)], 4),
            "p99": round(sorted_samples[min(int(n * 0.99), n - 1)], 4),
            "max": round(sorted_samples[-1], 4),
            "mean": round(statistics.mean(sorted_samples), 4),
        }
    return result


async def metrics_endpoint(request: Request) -> JSONResponse:
    """Expose latency metrics as JSON — mount at /metrics."""
    return JSONResponse(get_metrics())
