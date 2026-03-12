"""Prometheus metrics middleware for FastAPI.

Exposes HTTP request metrics and a /metrics endpoint
for Prometheus scraping. Part of C8 (Monitoring du service).
"""

import time
import uuid

import structlog
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

_EXCLUDED_PATHS = frozenset({"/metrics", "/api/docs", "/api/redoc", "/api/openapi.json"})

_log = structlog.get_logger("horrorbot.http")


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Records HTTP request metrics and structured logs for each request.

    For every non-excluded request:
    - Measures duration and records Prometheus histogram/counter metrics.
    - Generates a ``request_id`` (UUID4), binds it to structlog context
      variables, and returns it in the ``X-Request-ID`` response header.
    - Emits a structured log at INFO (2xx), WARNING (4xx), or ERROR (5xx).
    - Normalises parameterised paths (e.g. ``/films/42`` → ``/films/{film_id}``)
      to prevent metric cardinality explosion.

    Skips ``/metrics``, ``/api/docs``, ``/api/redoc``, and ``/api/openapi.json``.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process request and record metrics.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware/handler in the chain.

        Returns:
            HTTP response from downstream handler.
        """
        if request.url.path.rstrip("/") in _EXCLUDED_PATHS:
            return await call_next(request)

        method = request.method
        request_id = str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start = time.perf_counter()

        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()

        duration = time.perf_counter() - start
        status_code = response.status_code

        # Normalise parameterised paths via FastAPI route resolution
        route = request.scope.get("route")
        normalized = route.path if route and hasattr(route, "path") else request.url.path

        HTTP_REQUESTS_TOTAL.labels(method=method, path=normalized, status=str(status_code)).inc()
        HTTP_REQUEST_DURATION.labels(method=method, path=normalized).observe(duration)

        response.headers["X-Request-ID"] = request_id

        # Conditional structured logging by status code
        log_data = {
            "method": method,
            "path": normalized,
            "status": status_code,
            "duration_ms": round(duration * 1000, 1),
        }
        if status_code >= 500:
            _log.error("server_error", **log_data)
        elif status_code >= 400:
            _log.warning("client_error", **log_data)
        else:
            _log.info("request_completed", **log_data)

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
