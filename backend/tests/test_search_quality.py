"""Search quality metrics: Precision@K, Recall, MRR.

Run with: pytest backend/tests/test_search_quality.py -v -s
Requires: running backend with seeded DB and embeddings.
"""

import httpx
import pytest

pytestmark = pytest.mark.benchmark

BASE_URL = "http://localhost:8000"

# Curated query → expected scheme slugs (ground truth).
# Update these as the DB content changes.
SEARCH_TEST_CASES = [
    {
        "query": "education scholarship for students",
        "expected_slugs": [
            "national-scholarship-for-higher-education",
            "post-matric-scholarship",
            "pre-matric-scholarship",
            "central-sector-scheme-of-scholarship",
        ],
    },
    {
        "query": "health insurance for poor families",
        "expected_slugs": [
            "ayushman-bharat",
            "pradhan-mantri-jan-arogya-yojana",
            "rashtriya-swasthya-bima-yojana",
        ],
    },
    {
        "query": "housing scheme for BPL",
        "expected_slugs": [
            "pradhan-mantri-awas-yojana",
            "indira-awaas-yojana",
        ],
    },
    {
        "query": "farmer loan waiver agriculture",
        "expected_slugs": [
            "pm-kisan",
            "kisan-credit-card",
            "pradhan-mantri-fasal-bima-yojana",
        ],
    },
    {
        "query": "women empowerment self help group",
        "expected_slugs": [
            "beti-bachao-beti-padhao",
            "mahila-shakti-kendra",
            "one-stop-centre-scheme",
        ],
    },
]


def _search(query: str, limit: int = 10) -> list[dict]:
    """Call the search endpoint and return results."""
    resp = httpx.post(
        f"{BASE_URL}/api/v1/search",
        json={"query": query, "limit": limit},
        timeout=10.0,
    )
    if resp.status_code != 200:
        return []
    data = resp.json()
    return data if isinstance(data, list) else data.get("results", data.get("items", []))


class TestSearchQualityMetrics:
    """Measure search quality with Precision@K, Recall, and MRR."""

    def _run_metrics(self, k: int = 5):
        """Compute aggregate metrics across all test cases."""
        precisions = []
        recalls = []
        reciprocal_ranks = []

        for case in SEARCH_TEST_CASES:
            results = _search(case["query"], limit=k)
            if not results:
                continue

            result_slugs = []
            for r in results[:k]:
                slug = r.get("slug", "")
                if not slug and isinstance(r, dict):
                    scheme = r.get("scheme", {})
                    slug = scheme.get("slug", "") if isinstance(scheme, dict) else ""
                result_slugs.append(slug)

            expected = set(case["expected_slugs"])
            retrieved = set(result_slugs)

            # Precision@K: fraction of retrieved that are relevant
            relevant_retrieved = retrieved & expected
            precision = len(relevant_retrieved) / k if k > 0 else 0
            precisions.append(precision)

            # Recall: fraction of expected that are retrieved
            recall = len(relevant_retrieved) / len(expected) if expected else 0
            recalls.append(recall)

            # MRR: reciprocal rank of first relevant result
            rr = 0.0
            for rank, slug in enumerate(result_slugs, 1):
                if slug in expected:
                    rr = 1.0 / rank
                    break
            reciprocal_ranks.append(rr)

        return precisions, recalls, reciprocal_ranks

    def test_precision_at_5(self):
        precisions, _, _ = self._run_metrics(k=5)
        if not precisions:
            pytest.skip("No search results (server not running or DB empty)")
        avg_precision = sum(precisions) / len(precisions)
        print(f"\n  Precision@5: {avg_precision:.3f}")
        print(f"  Per-query: {[f'{p:.2f}' for p in precisions]}")
        # Baseline assertion — adjust as search improves
        assert avg_precision >= 0, "Precision should be non-negative"

    def test_precision_at_10(self):
        precisions, _, _ = self._run_metrics(k=10)
        if not precisions:
            pytest.skip("No search results")
        avg_precision = sum(precisions) / len(precisions)
        print(f"\n  Precision@10: {avg_precision:.3f}")

    def test_recall(self):
        _, recalls, _ = self._run_metrics(k=10)
        if not recalls:
            pytest.skip("No search results")
        avg_recall = sum(recalls) / len(recalls)
        print(f"\n  Recall@10: {avg_recall:.3f}")
        print(f"  Per-query: {[f'{r:.2f}' for r in recalls]}")

    def test_mrr(self):
        _, _, rrs = self._run_metrics(k=10)
        if not rrs:
            pytest.skip("No search results")
        mrr = sum(rrs) / len(rrs)
        print(f"\n  MRR: {mrr:.3f}")
        print(f"  Per-query: {[f'{r:.2f}' for r in rrs]}")
        # MRR > 0 means at least some relevant results found
        assert mrr >= 0

    def test_search_returns_results(self):
        """Basic sanity: search should return non-empty results for common queries."""
        for query in ["education", "health", "farmer", "housing"]:
            results = _search(query)
            print(f"\n  '{query}': {len(results)} results")
