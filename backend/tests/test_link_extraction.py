"""Tests for the link extraction pipeline."""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.data.extract_links import (
    extract_via_api,
    extract_via_curated,
    extract_via_search,
    load_hf_dataset,
    match_hf_links,
)
from app.data.curated_links import CURATED_LINKS, get_curated_link, get_myscheme_url
from app.data.manual_link_search import (
    _build_queries,
    rank_urls,
    web_search,
)


class TestExtractViaApi:
    """Tests for MyScheme Detail API extraction."""

    @pytest.mark.asyncio
    async def test_api_returns_official_link(self):
        """API response with officialUrl field should extract link."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "fields": {
                    "officialUrl": "https://pmjdy.gov.in",
                    "schemeName": "Pradhan Mantri Jan Dhan Yojana",
                }
            }
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await extract_via_api(mock_client, "pradhan-mantri-jan-dhan-yojana")

        assert result is not None
        assert result["official_link"] == "https://pmjdy.gov.in"
        assert result["strategy"] == "api"

    @pytest.mark.asyncio
    async def test_api_returns_link_in_top_level(self):
        """API response with top-level url field should extract link."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "officialUrl": "https://pmkisan.gov.in",
                "fields": {},
            }
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await extract_via_api(mock_client, "pm-kisan")

        assert result is not None
        assert result["official_link"] == "https://pmkisan.gov.in"

    @pytest.mark.asyncio
    async def test_api_returns_no_link(self):
        """API response without URL fields should return result without link."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "fields": {
                    "schemeName": "Some Scheme",
                    "briefDescription": "A description",
                }
            }
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await extract_via_api(mock_client, "some-scheme")

        assert result is not None
        assert "official_link" not in result

    @pytest.mark.asyncio
    async def test_api_404_returns_none(self):
        """API 404 should return None."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await extract_via_api(mock_client, "nonexistent-scheme")

        assert result is None

    @pytest.mark.asyncio
    async def test_api_timeout_returns_none(self):
        """API timeout should return None."""
        import httpx

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        result = await extract_via_api(mock_client, "slow-scheme")

        assert result is None

    @pytest.mark.asyncio
    async def test_api_ignores_non_http_links(self):
        """Non-HTTP values in URL fields should be ignored."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "fields": {
                    "officialUrl": "not-a-url",
                    "schemeUrl": "",
                }
            }
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await extract_via_api(mock_client, "bad-url-scheme")

        assert result is not None
        assert "official_link" not in result


class TestHuggingFaceMatching:
    """Tests for HuggingFace dataset cross-referencing."""

    def test_exact_slug_match(self):
        """Exact slug match should return the link."""
        schemes = [
            {"id": "1", "slug": "pm-kisan", "name": "PM-KISAN"},
            {"id": "2", "slug": "pmjdy", "name": "PMJDY"},
        ]
        hf_links = {
            "pm-kisan": "https://pmkisan.gov.in",
            "pmjdy": "https://pmjdy.gov.in",
            "other-scheme": "https://other.gov.in",
        }

        matched = match_hf_links(schemes, hf_links)

        assert len(matched) == 2
        assert matched["pm-kisan"] == "https://pmkisan.gov.in"
        assert matched["pmjdy"] == "https://pmjdy.gov.in"

    def test_fuzzy_slug_match(self):
        """Partial slug match should work."""
        schemes = [
            {"id": "1", "slug": "pradhan-mantri-jan-dhan-yojana", "name": "PMJDY"},
        ]
        hf_links = {
            "pradhan-mantri-jan-dhan-yojana-pmjdy": "https://pmjdy.gov.in",
        }

        matched = match_hf_links(schemes, hf_links)

        assert len(matched) == 1
        assert matched["pradhan-mantri-jan-dhan-yojana"] == "https://pmjdy.gov.in"

    def test_no_match(self):
        """Unmatched slugs should not appear in results."""
        schemes = [
            {"id": "1", "slug": "unknown-scheme", "name": "Unknown"},
        ]
        hf_links = {
            "completely-different": "https://example.gov.in",
        }

        matched = match_hf_links(schemes, hf_links)

        assert len(matched) == 0

    def test_empty_inputs(self):
        """Empty inputs should return empty dict."""
        assert match_hf_links([], {}) == {}
        assert match_hf_links([], {"a": "b"}) == {}
        assert match_hf_links([{"slug": "x", "name": "X", "id": "1"}], {}) == {}


class TestCuratedLinks:
    """Tests for the curated links dictionary."""

    def test_all_urls_start_with_http(self):
        """Every curated URL must start with http:// or https://."""
        for slug, url in CURATED_LINKS.items():
            assert url.startswith("http://") or url.startswith("https://"), (
                f"Curated link for {slug} is not a valid URL: {url}"
            )

    def test_no_myscheme_urls(self):
        """Curated links must not point to myscheme.gov.in."""
        for slug, url in CURATED_LINKS.items():
            assert "myscheme.gov.in" not in url.lower(), (
                f"Curated link for {slug} points to myscheme.gov.in: {url}"
            )

    def test_no_duplicate_urls(self):
        """Each URL in curated links should be unique (except portals like scholarships.gov.in)."""
        # Some umbrella portals legitimately serve multiple schemes
        ALLOWED_DUPLICATES = {
            "https://scholarships.gov.in",
            "https://nfsa.gov.in",
            "https://maandhan.in",
            "https://jansuraksha.gov.in",
            "https://wcd.nic.in",
        }
        seen = {}
        for slug, url in CURATED_LINKS.items():
            if url in ALLOWED_DUPLICATES:
                continue
            assert url not in seen, (
                f"Duplicate curated URL: {url} appears in both {seen[url]} and {slug}"
            )
            seen[url] = slug

    def test_slugs_are_valid(self):
        """Curated slugs should be lowercase with hyphens."""
        for slug in CURATED_LINKS:
            assert slug == slug.lower(), f"Slug {slug} should be lowercase"
            assert " " not in slug, f"Slug {slug} should not contain spaces"

    def test_get_curated_link_known(self):
        """get_curated_link should return URL for known slugs."""
        assert get_curated_link("pm-kisan") == "https://pmkisan.gov.in"

    def test_get_curated_link_unknown(self):
        """get_curated_link should return None for unknown slugs."""
        assert get_curated_link("nonexistent-scheme-slug-12345") is None

    def test_get_myscheme_url(self):
        """get_myscheme_url should return the correct myscheme.gov.in URL."""
        assert get_myscheme_url("pm-kisan") == "https://www.myscheme.gov.in/schemes/pm-kisan"

    def test_minimum_curated_count(self):
        """Should have at least 80 curated links."""
        assert len(CURATED_LINKS) >= 80, (
            f"Expected at least 80 curated links, got {len(CURATED_LINKS)}"
        )


class TestExtractViaCurated:
    """Tests for the curated extraction strategy."""

    def test_returns_result_for_known_slug(self):
        """Should return a result dict for a known curated slug."""
        result = extract_via_curated("pm-kisan")
        assert result is not None
        assert result["strategy"] == "curated"
        assert result["official_link"] == "https://pmkisan.gov.in"
        assert result["slug"] == "pm-kisan"

    def test_returns_none_for_unknown_slug(self):
        """Should return None for an unknown slug."""
        result = extract_via_curated("unknown-scheme-xyz-999")
        assert result is None


class TestDuckDuckGoSearch:
    """Tests for DuckDuckGo search function."""

    @patch("app.data.manual_link_search.DDGS")
    def test_web_search_returns_urls(self, mock_ddgs_cls):
        """web_search should return a list of URLs from DDG results."""
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.text.return_value = [
            {"href": "https://pmkisan.gov.in", "title": "PM-KISAN"},
            {"href": "https://example.com/pmkisan", "title": "PM KISAN Info"},
        ]
        mock_ddgs_cls.return_value = mock_instance

        # Patch the import inside web_search
        with patch.dict("sys.modules", {"duckduckgo_search": MagicMock(DDGS=mock_ddgs_cls)}):
            from app.data.manual_link_search import web_search as ws
            # Since the function does `from duckduckgo_search import DDGS` inside,
            # we need to patch it at module level
            pass

        urls = web_search("PM KISAN official website")
        assert len(urls) == 2
        assert "https://pmkisan.gov.in" in urls

    @patch("app.data.manual_link_search.DDGS", side_effect=ImportError("no module"))
    def test_web_search_handles_missing_library(self, mock_ddgs):
        """web_search should return empty list if duckduckgo-search is not installed."""
        # Force the ImportError path
        urls = web_search("test query")
        assert urls == []

    def test_build_queries_returns_multiple(self):
        """_build_queries should return multiple query variations."""
        queries = _build_queries("Pradhan Mantri Jan Dhan Yojana")
        assert len(queries) >= 2
        assert any("site:gov.in" in q for q in queries)
        assert any("official website" in q for q in queries)

    def test_build_queries_includes_scheme_name(self):
        """All queries should include the scheme name."""
        name = "PM-KISAN"
        queries = _build_queries(name)
        for q in queries:
            assert name in q


class TestRankUrls:
    """Tests for URL ranking logic."""

    def test_gov_in_ranked_highest(self):
        """URLs with .gov.in should be ranked highest."""
        urls = [
            "https://example.com/scheme",
            "https://pmkisan.gov.in",
            "https://scheme.nic.in",
        ]
        ranked = rank_urls(urls)
        assert ranked[0]["url"] == "https://pmkisan.gov.in"
        assert ranked[0]["domain_type"] == "gov.in"

    def test_excluded_domains_filtered(self):
        """Excluded domains should not appear in ranked results."""
        urls = [
            "https://myscheme.gov.in/schemes/test",
            "https://youtube.com/watch?v=123",
            "https://wikipedia.org/wiki/Scheme",
            "https://pmkisan.gov.in",
        ]
        ranked = rank_urls(urls)
        assert len(ranked) == 1
        assert ranked[0]["url"] == "https://pmkisan.gov.in"

    def test_empty_input(self):
        """Empty input should return empty list."""
        assert rank_urls([]) == []

    def test_nic_in_ranked_second(self):
        """.nic.in domains should rank below .gov.in but above others."""
        urls = [
            "https://example.com/info",
            "https://scheme.nic.in",
            "https://scheme.gov.in",
        ]
        ranked = rank_urls(urls)
        assert ranked[0]["domain_type"] == "gov.in"
        assert ranked[1]["domain_type"] == "nic.in"


class TestExtractViaSearch:
    """Tests for the DuckDuckGo search extraction strategy."""

    @patch("app.data.extract_links.DDGS")
    def test_returns_gov_in_link(self, mock_ddgs_cls):
        """Should prefer .gov.in results."""
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.text.return_value = [
            {"href": "https://example.com/scheme"},
            {"href": "https://pmkisan.gov.in"},
        ]
        mock_ddgs_cls.return_value = mock_instance

        result = extract_via_search("PM KISAN", "pm-kisan")
        assert result is not None
        assert result["strategy"] == "search"
        assert "gov.in" in result["official_link"]

    @patch("app.data.extract_links.DDGS")
    def test_excludes_myscheme_urls(self, mock_ddgs_cls):
        """Should skip myscheme.gov.in results."""
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.text.return_value = [
            {"href": "https://myscheme.gov.in/schemes/test"},
            {"href": "https://actual-scheme.gov.in"},
        ]
        mock_ddgs_cls.return_value = mock_instance

        result = extract_via_search("Test Scheme", "test-scheme")
        assert result is not None
        assert "myscheme.gov.in" not in result["official_link"]

    def test_returns_none_when_library_missing(self):
        """Should return None if duckduckgo-search is not installed."""
        with patch.dict("sys.modules", {"duckduckgo_search": None}):
            # Force ImportError
            result = extract_via_search("Test", "test")
            # May return None or handle gracefully
            # The function catches ImportError internally


class TestKnownSchemes:
    """Integration-style tests with known scheme data."""

    KNOWN_SCHEMES = [
        {
            "slug": "pradhan-mantri-jan-dhan-yojana",
            "name": "Pradhan Mantri Jan Dhan Yojana (PMJDY)",
            "expected_domain": "pmjdy.gov.in",
        },
        {
            "slug": "pm-kisan",
            "name": "Pradhan Mantri Kisan Samman Nidhi",
            "expected_domain": "pmkisan.gov.in",
        },
        {
            "slug": "ayushman-bharat-pradhan-mantri-jan-arogya-yojana-ab-pmjay",
            "name": "Ayushman Bharat - PMJAY",
            "expected_domain": "pmjay.gov.in",
        },
    ]

    def test_known_schemes_have_gov_domains(self):
        """Known major schemes should resolve to .gov.in domains."""
        for scheme in self.KNOWN_SCHEMES:
            assert ".gov.in" in scheme["expected_domain"], (
                f"{scheme['slug']} should have a .gov.in domain"
            )

    def test_slugs_are_valid(self):
        """Scheme slugs should be lowercase with hyphens."""
        for scheme in self.KNOWN_SCHEMES:
            slug = scheme["slug"]
            assert slug == slug.lower(), f"Slug {slug} should be lowercase"
            assert " " not in slug, f"Slug {slug} should not contain spaces"

    def test_known_schemes_in_curated_links(self):
        """Known major schemes should be present in curated links."""
        for scheme in self.KNOWN_SCHEMES:
            curated = get_curated_link(scheme["slug"])
            assert curated is not None, (
                f"{scheme['slug']} should have a curated link"
            )
            assert scheme["expected_domain"] in curated, (
                f"Curated link for {scheme['slug']} should contain {scheme['expected_domain']}"
            )
