"""Tests for scheme API endpoints: list, detail, featured."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_check(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Schemes list endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_schemes_list_empty(client):
    """Empty DB returns valid paginated shape with zero items."""
    resp = await client.get("/api/v1/schemes")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "total_pages" in data
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_schemes_list_with_data(client, sample_schemes):
    """With seeded data, list returns active schemes only."""
    resp = await client.get("/api/v1/schemes")
    assert resp.status_code == 200
    data = resp.json()
    # 4 active schemes (s5 is inactive)
    assert data["total"] == 4
    assert len(data["items"]) == 4


@pytest.mark.asyncio
async def test_schemes_list_pagination(client, sample_schemes):
    resp = await client.get("/api/v1/schemes?page=1&page_size=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert data["total_pages"] == 2  # 4 items / 2 per page


@pytest.mark.asyncio
async def test_schemes_list_page_2(client, sample_schemes):
    resp = await client.get("/api/v1/schemes?page=2&page_size=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["page"] == 2


@pytest.mark.asyncio
async def test_schemes_list_search_filter(client, sample_schemes):
    resp = await client.get("/api/v1/schemes?search=Scholarship")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any("Scholarship" in item["name"] for item in data["items"])


@pytest.mark.asyncio
async def test_schemes_list_level_filter(client, sample_schemes):
    resp = await client.get("/api/v1/schemes?level=state")
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        assert item["level"] == "state"


@pytest.mark.asyncio
async def test_schemes_list_category_filter(client, sample_schemes):
    resp = await client.get("/api/v1/schemes?category=education")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


# ---------------------------------------------------------------------------
# Scheme detail endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scheme_detail_found(client, sample_schemes):
    resp = await client.get("/api/v1/schemes/national-scholarship-students")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "National Scholarship for Students"
    assert data["slug"] == "national-scholarship-students"
    assert "description" in data
    assert "benefits" in data
    assert "eligibility_criteria" in data
    assert "category" in data
    assert "tags" in data
    assert "states" in data


@pytest.mark.asyncio
async def test_scheme_detail_not_found(client):
    resp = await client.get("/api/v1/schemes/nonexistent-slug")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_scheme_detail_response_shape(client, sample_schemes):
    """Validate all expected fields exist in the detail response."""
    resp = await client.get("/api/v1/schemes/women-empowerment-programme")
    assert resp.status_code == 200
    data = resp.json()
    expected_fields = [
        "id", "name", "slug", "description", "benefits",
        "eligibility_criteria", "application_process", "documents_required",
        "official_link", "level", "status", "featured",
        "category", "ministry", "states", "tags", "faqs",
    ]
    for field in expected_fields:
        assert field in data, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# Featured schemes endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_featured_schemes(client, sample_schemes):
    resp = await client.get("/api/v1/schemes/featured")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # Only s1 is featured
    assert len(data) >= 1
    for item in data:
        assert item["featured"] is True


@pytest.mark.asyncio
async def test_featured_schemes_empty(client):
    resp = await client.get("/api/v1/schemes/featured")
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# Item shape validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scheme_list_item_shape(client, sample_schemes):
    """Each item in the list should have the SchemeListItem shape."""
    resp = await client.get("/api/v1/schemes")
    data = resp.json()
    for item in data["items"]:
        assert "id" in item
        assert "name" in item
        assert "slug" in item
        assert "level" in item
        assert "featured" in item
        # Optional but should be present
        assert "description" in item
        assert "tags" in item


# ---------------------------------------------------------------------------
# Eligibility API endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_eligibility_options(client, sample_state):
    resp = await client.get("/api/v1/eligibility/options")
    assert resp.status_code == 200
    data = resp.json()
    assert "genders" in data
    assert "social_categories" in data
    assert "states" in data
    assert "Male" in data["genders"]
    assert "Female" in data["genders"]


@pytest.mark.asyncio
async def test_eligibility_check(client, sample_schemes):
    resp = await client.post("/api/v1/eligibility/check", json={
        "gender": "Female",
        "age": 25,
        "social_category": "SC",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert "total" in data
    assert "profile" in data
    assert data["total"] >= 1
    for r in data["results"]:
        assert "scheme" in r
        assert "match_score" in r
        assert "matched_criteria" in r


@pytest.mark.asyncio
async def test_eligibility_check_empty_profile(client, sample_schemes):
    """Empty profile should still return results (universal schemes)."""
    resp = await client.post("/api/v1/eligibility/check", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
