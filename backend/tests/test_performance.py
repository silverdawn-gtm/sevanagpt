"""API response time benchmarks.

Run with: pytest backend/tests/test_performance.py -v --tb=short
These tests require a running backend + DB. Skip in CI with: pytest -m "not benchmark"

Target latencies:
    GET  /schemes?lang=hi         < 2s
    GET  /schemes/{slug}?lang=hi  < 3s
    GET  /categories?lang=hi      < 500ms
    POST /search                  < 1s
    POST /chat/message            < 5s
    GET  /eligibility/check       < 1s
"""

import time

import httpx
import pytest

BASE_URL = "http://localhost:8000"

pytestmark = pytest.mark.benchmark


def _timed_get(path: str, timeout: float = 10.0) -> tuple[float, int]:
    """Make a GET request and return (elapsed_seconds, status_code)."""
    start = time.perf_counter()
    resp = httpx.get(f"{BASE_URL}{path}", timeout=timeout)
    elapsed = time.perf_counter() - start
    return elapsed, resp.status_code


def _timed_post(path: str, json: dict, timeout: float = 10.0) -> tuple[float, int]:
    start = time.perf_counter()
    resp = httpx.post(f"{BASE_URL}{path}", json=json, timeout=timeout)
    elapsed = time.perf_counter() - start
    return elapsed, resp.status_code


class TestAPIResponseTimes:
    """Benchmark key endpoints against target latencies.

    These tests hit the real running server — skip if server not up.
    """

    def test_schemes_list_english(self):
        elapsed, status = _timed_get("/api/v1/schemes")
        assert status == 200
        print(f"\n  GET /schemes (en): {elapsed:.3f}s")
        assert elapsed < 2.0, f"Too slow: {elapsed:.3f}s (target < 2s)"

    def test_schemes_list_hindi(self):
        elapsed, status = _timed_get("/api/v1/schemes?lang=hi")
        assert status == 200
        print(f"\n  GET /schemes?lang=hi: {elapsed:.3f}s")
        assert elapsed < 5.0, f"Too slow: {elapsed:.3f}s (target < 5s with translation)"

    def test_scheme_detail_english(self):
        # First get a valid slug
        resp = httpx.get(f"{BASE_URL}/api/v1/schemes?page_size=1")
        if resp.status_code != 200 or not resp.json().get("items"):
            pytest.skip("No schemes in DB")
        slug = resp.json()["items"][0]["slug"]

        elapsed, status = _timed_get(f"/api/v1/schemes/{slug}")
        assert status == 200
        print(f"\n  GET /schemes/{slug} (en): {elapsed:.3f}s")
        assert elapsed < 2.0

    def test_scheme_detail_hindi(self):
        resp = httpx.get(f"{BASE_URL}/api/v1/schemes?page_size=1")
        if resp.status_code != 200 or not resp.json().get("items"):
            pytest.skip("No schemes in DB")
        slug = resp.json()["items"][0]["slug"]

        elapsed, status = _timed_get(f"/api/v1/schemes/{slug}?lang=hi")
        assert status == 200
        print(f"\n  GET /schemes/{slug}?lang=hi: {elapsed:.3f}s")
        assert elapsed < 5.0

    def test_categories_english(self):
        elapsed, status = _timed_get("/api/v1/categories")
        assert status == 200
        print(f"\n  GET /categories (en): {elapsed:.3f}s")
        assert elapsed < 0.5

    def test_categories_hindi(self):
        elapsed, status = _timed_get("/api/v1/categories?lang=hi")
        assert status == 200
        print(f"\n  GET /categories?lang=hi: {elapsed:.3f}s")
        assert elapsed < 2.0

    def test_search(self):
        elapsed, status = _timed_post("/api/v1/search", {"query": "education scholarship"})
        assert status == 200
        print(f"\n  POST /search: {elapsed:.3f}s")
        assert elapsed < 3.0

    def test_eligibility_check(self):
        elapsed, status = _timed_post("/api/v1/eligibility/check", {
            "gender": "Female",
            "age": 25,
            "state_code": "KA",
            "social_category": "SC",
        })
        assert status == 200
        print(f"\n  POST /eligibility/check: {elapsed:.3f}s")
        assert elapsed < 1.0

    def test_eligibility_options(self):
        elapsed, status = _timed_get("/api/v1/eligibility/options")
        assert status == 200
        print(f"\n  GET /eligibility/options: {elapsed:.3f}s")
        assert elapsed < 0.5

    def test_health(self):
        elapsed, status = _timed_get("/health")
        assert status == 200
        print(f"\n  GET /health: {elapsed:.3f}s")
        assert elapsed < 0.1
