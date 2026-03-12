"""Tests for Prometheus metrics middleware."""

from unittest.mock import MagicMock, patch
from uuid import UUID

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

    @test_app.get("/api/v1/items/{item_id}")
    def get_item(item_id: int):
        return {"id": item_id}

    @test_app.get("/api/v1/missing")
    def missing():
        raise HTTPException(status_code=404, detail="not found")

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


class TestPathExclusion:
    """Tests for excluded paths (not recorded in metrics)."""

    @staticmethod
    def test_docs_endpoint_not_recorded(app) -> None:
        """Requests to /api/docs are excluded from HTTP metrics."""
        app.docs_url = "/api/docs"
        client = TestClient(app)
        client.get("/api/docs")
        response = client.get("/metrics")
        lines = [
            line
            for line in response.text.splitlines()
            if line.startswith("horrorbot_http_requests_total{")
        ]
        for line in lines:
            assert 'path="/api/docs"' not in line

    @staticmethod
    def test_openapi_endpoint_not_recorded(app) -> None:
        """Requests to /api/openapi.json are excluded from HTTP metrics."""
        client = TestClient(app)
        client.get("/api/openapi.json")
        response = client.get("/metrics")
        lines = [
            line
            for line in response.text.splitlines()
            if line.startswith("horrorbot_http_requests_total{")
        ]
        for line in lines:
            assert 'path="/api/openapi.json"' not in line


class TestPathNormalization:
    """Tests for parameterised path normalisation."""

    @staticmethod
    def test_parameterized_path_normalized(client) -> None:
        """A parameterised route is recorded with the template, not the value."""
        client.get("/api/v1/items/42")
        response = client.get("/metrics")
        body = response.text
        # The template path should appear, not the literal /42
        assert 'path="/api/v1/items/{item_id}"' in body
        assert 'path="/api/v1/items/42"' not in body


class TestRequestId:
    """Tests for X-Request-ID header injection."""

    @staticmethod
    def test_response_has_request_id_header(client) -> None:
        """Every non-excluded response includes a valid UUID X-Request-ID."""
        response = client.get("/api/v1/health")
        request_id = response.headers.get("X-Request-ID")
        assert request_id is not None
        UUID(request_id)  # raises ValueError if not a valid UUID

    @staticmethod
    def test_each_request_gets_unique_id(client) -> None:
        """Two requests receive distinct request IDs."""
        r1 = client.get("/api/v1/health")
        r2 = client.get("/api/v1/health")
        assert r1.headers["X-Request-ID"] != r2.headers["X-Request-ID"]

    @staticmethod
    def test_excluded_path_has_no_request_id(client) -> None:
        """Excluded paths do not receive an X-Request-ID header."""
        response = client.get("/metrics")
        assert "X-Request-ID" not in response.headers


class TestConditionalLogging:
    """Tests for structured logging by status code."""

    @staticmethod
    def test_2xx_logs_info(client) -> None:
        """A 200 response emits an INFO log with expected fields."""
        with patch("src.monitoring.middleware._log") as mock_log:
            client.get("/api/v1/health")
            mock_log.info.assert_called_once()
            _event, kwargs = mock_log.info.call_args
            assert _event[0] == "request_completed"
            assert kwargs["method"] == "GET"
            assert kwargs["status"] == 200
            assert "duration_ms" in kwargs

    @staticmethod
    def test_4xx_logs_warning(client) -> None:
        """A 404 response emits a WARNING log."""
        with patch("src.monitoring.middleware._log") as mock_log:
            client.get("/api/v1/missing")
            mock_log.warning.assert_called_once()
            _event, kwargs = mock_log.warning.call_args
            assert _event[0] == "client_error"
            assert kwargs["status"] == 404

    @staticmethod
    def test_5xx_logs_error(client) -> None:
        """A 500 response emits an ERROR log."""
        with patch("src.monitoring.middleware._log") as mock_log:
            client.get("/api/v1/error")
            mock_log.error.assert_called_once()
            _event, kwargs = mock_log.error.call_args
            assert _event[0] == "server_error"
            assert kwargs["status"] == 500

    @staticmethod
    def test_excluded_path_not_logged(client) -> None:
        """Excluded paths do not produce any structured log."""
        with patch("src.monitoring.middleware._log") as mock_log:
            client.get("/metrics")
            mock_log.info.assert_not_called()
            mock_log.warning.assert_not_called()
            mock_log.error.assert_not_called()
