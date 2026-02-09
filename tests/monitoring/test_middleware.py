"""Tests for Prometheus metrics middleware."""

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from prometheus_client import Counter, Histogram

from src.monitoring.middleware import (
    HTTP_REQUEST_DURATION,
    HTTP_REQUESTS_TOTAL,
    PrometheusMiddleware,
    mount_metrics,
)


@pytest.fixture
def app():
    """Create a minimal FastAPI app with Prometheus middleware."""
    test_app = FastAPI()
    test_app.add_middleware(PrometheusMiddleware)
    mount_metrics(test_app)

    @test_app.get("/api/v1/health")
    def health():
        return {"status": "ok"}

    @test_app.get("/api/v1/error")
    def error():
        raise HTTPException(status_code=500, detail="test error")

    return test_app


@pytest.fixture
def client(app):
    """TestClient for the middleware test app."""
    return TestClient(app)


class TestMetricsEndpoint:
    """Tests for the /metrics Prometheus endpoint."""

    @staticmethod
    def test_metrics_returns_200(client) -> None:
        """GET /metrics returns HTTP 200."""
        response = client.get("/metrics")
        assert response.status_code == 200

    @staticmethod
    def test_metrics_content_type(client) -> None:
        """GET /metrics returns Prometheus text format."""
        response = client.get("/metrics")
        assert "text/plain" in response.headers["content-type"]

    @staticmethod
    def test_metrics_contains_http_requests_total(client) -> None:
        """GET /metrics body contains HTTP request counter."""
        client.get("/api/v1/health")
        response = client.get("/metrics")
        assert "horrorbot_http_requests_total" in response.text

    @staticmethod
    def test_metrics_contains_http_duration(client) -> None:
        """GET /metrics body contains HTTP duration histogram."""
        client.get("/api/v1/health")
        response = client.get("/metrics")
        assert "horrorbot_http_request_duration_seconds" in response.text


class TestPrometheusMiddleware:
    """Tests for HTTP request metrics recording."""

    @staticmethod
    def test_successful_request_recorded(client) -> None:
        """A 200 response is recorded with correct labels."""
        client.get("/api/v1/health")
        response = client.get("/metrics")
        body = response.text
        assert 'method="GET"' in body
        assert 'path="/api/v1/health"' in body
        assert 'status="200"' in body

    @staticmethod
    def test_error_request_recorded(client) -> None:
        """A 500 response is recorded with correct status label."""
        client.get("/api/v1/error")
        response = client.get("/metrics")
        assert 'status="500"' in response.text

    @staticmethod
    def test_metrics_endpoint_not_recorded(client) -> None:
        """Requests to /metrics are not recorded in HTTP metrics."""
        client.get("/metrics")
        response = client.get("/metrics")
        # /metrics path should not appear in the request counter labels
        lines = [
            line
            for line in response.text.splitlines()
            if line.startswith("horrorbot_http_requests_total{")
        ]
        for line in lines:
            assert 'path="/metrics"' not in line

    @staticmethod
    def test_duration_histogram_recorded(client) -> None:
        """Request duration is observed in the histogram."""
        client.get("/api/v1/health")
        response = client.get("/metrics")
        assert "horrorbot_http_request_duration_seconds_count" in response.text


class TestMetricDefinitions:
    """Tests for HTTP metric object types and naming."""

    @staticmethod
    def test_http_requests_total_is_counter() -> None:
        """HTTP_REQUESTS_TOTAL is a prometheus Counter."""
        assert isinstance(HTTP_REQUESTS_TOTAL, Counter)

    @staticmethod
    def test_http_request_duration_is_histogram() -> None:
        """HTTP_REQUEST_DURATION is a prometheus Histogram."""
        assert isinstance(HTTP_REQUEST_DURATION, Histogram)

    @staticmethod
    def test_http_requests_total_has_horrorbot_prefix() -> None:
        """HTTP_REQUESTS_TOTAL follows the horrorbot_ naming convention."""
        assert HTTP_REQUESTS_TOTAL._name.startswith("horrorbot_")

    @staticmethod
    def test_http_request_duration_has_horrorbot_prefix() -> None:
        """HTTP_REQUEST_DURATION follows the horrorbot_ naming convention."""
        assert HTTP_REQUEST_DURATION._name.startswith("horrorbot_")
