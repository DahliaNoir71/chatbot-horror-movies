"""Prometheus metrics middleware for FastAPI.

Exposes HTTP request metrics and a /metrics endpoint
for Prometheus scraping. Part of C8 (Monitoring du service).
"""

import time

from prometheus_client import Counter, Histogram, make_asgi_app
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# =============================================================================
# HTTP METRICS
# =============================================================================

HTTP_REQUESTS_TOTAL = Counter(
    "horrorbot_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

HTTP_REQUEST_DURATION = Histogram(
    "horrorbot_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)


# =============================================================================
# MIDDLEWARE
# =============================================================================


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Records HTTP request metrics for Prometheus.

    Measures request duration and counts requests by method, path, and status.
    Skips recording for the /metrics endpoint itself.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process request and record metrics.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware/handler in the chain.

        Returns:
            HTTP response from downstream handler.
        """
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        path = request.url.path
        start = time.perf_counter()

        response = await call_next(request)

        duration = time.perf_counter() - start
        status = str(response.status_code)

        HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=status).inc()
        HTTP_REQUEST_DURATION.labels(method=method, path=path).observe(duration)

        return response


# =============================================================================
# MOUNT HELPER
# =============================================================================


def mount_metrics(app) -> None:
    """Mount the /metrics Prometheus endpoint on a FastAPI app.

    Uses prometheus_client.make_asgi_app() which serves all registered
    metrics in Prometheus text exposition format. The mounted ASGI sub-app
    bypasses FastAPI's middleware chain (no JWT authentication required).

    Args:
        app: FastAPI application instance.
    """
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)
