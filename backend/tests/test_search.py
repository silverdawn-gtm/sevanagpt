"""Tests for hybrid search and RRF scoring."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import Category, Scheme
from app.services.search_service import reciprocal_rank_fusion


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion (pure logic, no DB)
# ---------------------------------------------------------------------------

class TestReciprocalRankFusion:
    """Test the RRF merging algorithm."""

    def _make_scheme(self, name: str) -> Scheme:
        s = Scheme.__new__(Scheme)
        s.id = uuid.uuid4()
        s.name = name
        return s

    def test_single_list(self):
        s1 = self._make_scheme("A")
        s2 = self._make_scheme("B")
        result = reciprocal_rank_fusion([(s1, 0.9), (s2, 0.5)])
        assert len(result) == 2
        assert result[0][0].name == "A"  # Higher rank
        assert result[1][0].name == "B"

    def test_two_lists_same_scheme_boosted(self):
        """A scheme appearing in both lists should rank higher."""
        shared = self._make_scheme("Shared")
        only_kw = self._make_scheme("KeywordOnly")
        only_sem = self._make_scheme("SemanticOnly")

        kw_results = [(shared, 0.9), (only_kw, 0.7)]
        sem_results = [(shared, 0.8), (only_sem, 0.6)]

        merged = reciprocal_rank_fusion(kw_results, sem_results)
        names = [s.name for s, _ in merged]

        # Shared should be first (boosted by appearing in both lists)
        assert names[0] == "Shared"
        assert set(names) == {"Shared", "KeywordOnly", "SemanticOnly"}

    def test_empty_lists(self):
        result = reciprocal_rank_fusion([], [])
        assert result == []

    def test_one_empty_one_full(self):
        s1 = self._make_scheme("A")
        result = reciprocal_rank_fusion([], [(s1, 0.9)])
        assert len(result) == 1
        assert result[0][0].name == "A"

    def test_rrf_scores_are_positive(self):
        s1 = self._make_scheme("A")
        s2 = self._make_scheme("B")
        result = reciprocal_rank_fusion([(s1, 0.9), (s2, 0.5)])
        for _, score in result:
            assert score > 0

    def test_k_parameter_changes_scores(self):
        """Different k values should produce different score magnitudes."""
        s1 = self._make_scheme("A")
        result_k60 = reciprocal_rank_fusion([(s1, 0.9)], k=60)
        result_k10 = reciprocal_rank_fusion([(s1, 0.9)], k=10)
        # k=10 gives higher individual scores than k=60
        assert result_k10[0][1] > result_k60[0][1]

    def test_ordering_preserved_with_many_items(self):
        """With 10 items in one list, RRF should maintain relative order."""
        schemes = [self._make_scheme(f"S{i}") for i in range(10)]
        single_list = [(s, 1.0 - i * 0.1) for i, s in enumerate(schemes)]
        merged = reciprocal_rank_fusion(single_list)
        names = [s.name for s, _ in merged]
        assert names == [f"S{i}" for i in range(10)]

    def test_duplicate_in_same_list_handled(self):
        """Same scheme appearing twice in one list shouldn't crash."""
        s1 = self._make_scheme("A")
        result = reciprocal_rank_fusion([(s1, 0.9), (s1, 0.5)])
        # Should deduplicate by ID
        assert len(result) == 1

    def test_three_lists_merge(self):
        """RRF should handle 3+ result lists."""
        s1 = self._make_scheme("A")
        s2 = self._make_scheme("B")
        s3 = self._make_scheme("C")

        list1 = [(s1, 0.9), (s2, 0.5)]
        list2 = [(s2, 0.8), (s3, 0.4)]
        list3 = [(s1, 0.7), (s3, 0.6)]

        merged = reciprocal_rank_fusion(list1, list2, list3)
        assert len(merged) == 3
        # s1 appears in 2 lists at rank 0, s2 appears in 2 lists
        names = [s.name for s, _ in merged]
        assert "A" in names
        assert "B" in names
        assert "C" in names
