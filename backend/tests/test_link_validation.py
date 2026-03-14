"""Tests for the link validation pipeline."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.data.validate_links import validate_link


@pytest.fixture
def semaphore():
    return asyncio.Semaphore(10)


class TestValidateLink:
    """Tests for individual link validation."""

    @pytest.mark.asyncio
    async def test_working_link(self, semaphore):
        """2xx response should classify as working."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = "https://pmjdy.gov.in"

        mock_client = AsyncMock()
        mock_client.head = AsyncMock(return_value=mock_response)

        result = await validate_link(
            mock_client, semaphore, "https://pmjdy.gov.in", "pmjdy"
        )

        assert result["status"] == "working"
        assert result["status_code"] == 200
        assert result["slug"] == "pmjdy"

    @pytest.mark.asyncio
    async def test_redirected_link(self, semaphore):
        """Response with different final URL should classify as redirected."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = "https://www.pmjdy.gov.in/home"

        mock_client = AsyncMock()
        mock_client.head = AsyncMock(return_value=mock_response)

        result = await validate_link(
            mock_client, semaphore, "https://pmjdy.gov.in", "pmjdy"
        )

        assert result["status"] == "redirected"
        assert result["final_url"] == "https://www.pmjdy.gov.in/home"

    @pytest.mark.asyncio
    async def test_broken_link_404(self, semaphore):
        """404 response should classify as broken."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.url = "https://example.gov.in/old-page"

        mock_client = AsyncMock()
        mock_client.head = AsyncMock(return_value=mock_response)

        result = await validate_link(
            mock_client, semaphore, "https://example.gov.in/old-page", "old-scheme"
        )

        assert result["status"] == "broken"
        assert result["status_code"] == 404

    @pytest.mark.asyncio
    async def test_head_405_fallback_to_get(self, semaphore):
        """HEAD returning 405 should fallback to GET."""
        head_response = MagicMock()
        head_response.status_code = 405
        head_response.url = "https://example.gov.in"

        get_response = MagicMock()
        get_response.status_code = 200
        get_response.url = "https://example.gov.in"

        mock_client = AsyncMock()
        mock_client.head = AsyncMock(return_value=head_response)
        mock_client.get = AsyncMock(return_value=get_response)

        result = await validate_link(
            mock_client, semaphore, "https://example.gov.in", "test-scheme"
        )

        assert result["status"] == "working"
        assert result["status_code"] == 200

    @pytest.mark.asyncio
    async def test_timeout(self, semaphore):
        """Timeout should classify as timeout."""
        mock_client = AsyncMock()
        mock_client.head = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        result = await validate_link(
            mock_client, semaphore, "https://slow.gov.in", "slow-scheme"
        )

        assert result["status"] == "timeout"
        assert result["error"] is not None

    @pytest.mark.asyncio
    async def test_dns_error(self, semaphore):
        """DNS resolution failure should classify as dns_error."""
        mock_client = AsyncMock()
        mock_client.head = AsyncMock(
            side_effect=httpx.ConnectError("name resolution failed")
        )

        result = await validate_link(
            mock_client, semaphore, "https://nonexistent.gov.in", "bad-dns"
        )

        assert result["status"] == "dns_error"

    @pytest.mark.asyncio
    async def test_ssl_error(self, semaphore):
        """SSL error should classify as ssl_error."""
        import ssl

        mock_client = AsyncMock()
        mock_client.head = AsyncMock(
            side_effect=ssl.SSLError("certificate verify failed")
        )

        result = await validate_link(
            mock_client, semaphore, "https://bad-ssl.gov.in", "bad-ssl"
        )

        assert result["status"] == "ssl_error"

    @pytest.mark.asyncio
    async def test_result_has_all_fields(self, semaphore):
        """Validation result should always have required fields."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = "https://example.gov.in"

        mock_client = AsyncMock()
        mock_client.head = AsyncMock(return_value=mock_response)

        result = await validate_link(
            mock_client, semaphore, "https://example.gov.in", "test"
        )

        required_fields = [
            "slug", "original_url", "status", "status_code",
            "final_url", "error", "response_time_ms", "checked_at",
        ]
        for field in required_fields:
            assert field in result, f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_server_error_retries(self, semaphore):
        """5xx responses should be retried."""
        error_response = MagicMock()
        error_response.status_code = 500
        error_response.url = "https://example.gov.in"

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.url = "https://example.gov.in"

        mock_client = AsyncMock()
        # First call returns 500, second returns 200
        mock_client.head = AsyncMock(side_effect=[error_response, success_response])

        result = await validate_link(
            mock_client, semaphore, "https://example.gov.in", "retry-test"
        )

        assert result["status"] == "working"
        assert mock_client.head.call_count == 2


class TestValidationClassifications:
    """Tests for correct classification of various HTTP scenarios."""

    @pytest.mark.asyncio
    async def test_status_codes(self, semaphore):
        """Various status codes should be classified correctly."""
        test_cases = [
            (200, "working"),
            (201, "working"),
            (403, "broken"),
            (404, "broken"),
            (410, "broken"),
        ]

        for status_code, expected_status in test_cases:
            mock_response = MagicMock()
            mock_response.status_code = status_code
            mock_response.url = "https://example.gov.in"

            mock_client = AsyncMock()
            mock_client.head = AsyncMock(return_value=mock_response)

            result = await validate_link(
                mock_client, semaphore, "https://example.gov.in", f"test-{status_code}"
            )

            assert result["status"] == expected_status, (
                f"Status code {status_code} should be '{expected_status}', got '{result['status']}'"
            )
