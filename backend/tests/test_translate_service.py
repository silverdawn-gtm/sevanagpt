"""Tests for translation service: language mapping, caching, batching."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.services.translate_service import (
    GOOGLE_LANG_MAP,
    SUPPORTED_LANGS,
    _cache_key,
    _google_translate_batch_sync,
    _google_translate_sync,
    translate_text,
    translate_texts_batch,
)


# ---------------------------------------------------------------------------
# Language code mapping tests
# ---------------------------------------------------------------------------

class TestGoogleLangMapping:
    """Validate the internal → Google Translate code mapping."""

    def test_manipuri_maps_to_bcp47(self):
        assert GOOGLE_LANG_MAP["mni"] == "mni-Mtei"

    def test_konkani_maps_to_gom(self):
        assert GOOGLE_LANG_MAP["kok"] == "gom"

    def test_hindi_maps_directly(self):
        assert GOOGLE_LANG_MAP["hi"] == "hi"

    def test_bengali_maps_directly(self):
        assert GOOGLE_LANG_MAP["bn"] == "bn"

    def test_bodo_not_in_google(self):
        assert "bodo" not in GOOGLE_LANG_MAP

    def test_santali_not_in_google(self):
        assert "sat" not in GOOGLE_LANG_MAP

    def test_all_google_langs_are_supported(self):
        """Every language in GOOGLE_LANG_MAP should also be in SUPPORTED_LANGS."""
        for lang in GOOGLE_LANG_MAP:
            assert lang in SUPPORTED_LANGS, f"{lang} in GOOGLE_LANG_MAP but not SUPPORTED_LANGS"

    def test_unsupported_lang_returns_none(self):
        """_google_translate_sync returns None for unsupported languages."""
        result = _google_translate_sync("hello", "bodo")
        assert result is None

    def test_unsupported_lang_batch_returns_none(self):
        result = _google_translate_batch_sync(["hello", "world"], "sat")
        assert result is None


# ---------------------------------------------------------------------------
# Cache key tests
# ---------------------------------------------------------------------------

class TestCacheKey:
    def test_deterministic(self):
        assert _cache_key("hello", "hi") == _cache_key("hello", "hi")

    def test_different_text(self):
        assert _cache_key("hello", "hi") != _cache_key("world", "hi")

    def test_different_lang(self):
        assert _cache_key("hello", "hi") != _cache_key("hello", "bn")


# ---------------------------------------------------------------------------
# Translation with mock external services
# ---------------------------------------------------------------------------

class TestTranslateText:
    @pytest.mark.asyncio
    async def test_english_passthrough(self):
        """English text returns as-is regardless of target."""
        result = await translate_text("hello", "en")
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_empty_text_passthrough(self):
        result = await translate_text("", "hi")
        assert result == ""

    @pytest.mark.asyncio
    async def test_unsupported_lang_passthrough(self):
        result = await translate_text("hello", "xx")
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_whitespace_passthrough(self):
        result = await translate_text("   ", "hi")
        assert result == "   "

    @pytest.mark.asyncio
    async def test_indictrans_preferred_over_google(self):
        """When IndicTrans2 succeeds, Google Translate should not be called."""
        with patch("app.services.indictrans_client.translate_single", new_callable=AsyncMock) as it_mock, \
             patch("app.services.translate_service._google_translate_sync") as gt_mock:
            it_mock.return_value = "नमस्ते"
            result = await translate_text("hello", "hi")
            assert result == "नमस्ते"
            it_mock.assert_called_once()
            gt_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_google_fallback_on_indictrans_failure(self):
        """When IndicTrans2 returns None, fall back to Google Translate."""
        with patch("app.services.indictrans_client.translate_single", new_callable=AsyncMock) as it_mock, \
             patch("app.services.translate_service._google_translate_sync") as gt_mock:
            it_mock.return_value = None
            gt_mock.return_value = "translated_text"
            result = await translate_text("hello", "hi")
            assert result == "translated_text"

    @pytest.mark.asyncio
    async def test_no_fallback_for_bodo(self):
        """Bodo isn't in Google Translate — should return original text."""
        with patch("app.services.indictrans_client.translate_single", new_callable=AsyncMock) as it_mock:
            it_mock.return_value = None
            result = await translate_text("hello", "bodo")
            assert result == "hello"


# ---------------------------------------------------------------------------
# Batch translation tests
# ---------------------------------------------------------------------------

class TestBatchTranslation:
    @pytest.mark.asyncio
    async def test_english_batch_passthrough(self):
        result = await translate_texts_batch(["a", "b", "c"], "en")
        assert result == ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_unsupported_batch_passthrough(self):
        result = await translate_texts_batch(["a", "b"], "xx")
        assert result == ["a", "b"]

    @pytest.mark.asyncio
    async def test_empty_texts_in_batch(self):
        """Empty strings in batch should be preserved as empty."""
        with patch("app.services.indictrans_client.translate_batch", new_callable=AsyncMock) as it_mock:
            it_mock.return_value = None  # Force Google fallback
            with patch("app.services.translate_service._google_translate_batch_sync") as gt_mock:
                gt_mock.return_value = ["[hi]a"]
                result = await translate_texts_batch(["a", "", "  "], "hi")
                assert result[1] == ""
                assert result[2] == "  "

    @pytest.mark.asyncio
    async def test_batch_chunking(self):
        """Texts exceeding 4500 chars should be split into multiple chunks."""
        # Create texts that exceed chunk limit
        long_texts = ["x" * 1000 for _ in range(6)]  # 6000 chars total > 4500

        call_count = 0
        original_texts = []

        async def fake_indictrans_batch(texts, lang):
            nonlocal call_count
            call_count += 1
            original_texts.append(len(texts))
            return [f"[{lang}]{t}" for t in texts]

        with patch("app.services.indictrans_client.translate_batch", side_effect=fake_indictrans_batch):
            result = await translate_texts_batch(long_texts, "hi")

        assert len(result) == 6
        # Should have been split into multiple chunks
        assert call_count >= 2

    @pytest.mark.asyncio
    async def test_batch_indictrans_preferred(self):
        """IndicTrans2 batch should be tried before Google batch."""
        with patch("app.services.indictrans_client.translate_batch", new_callable=AsyncMock) as it_mock, \
             patch("app.services.translate_service._google_translate_batch_sync") as gt_mock:
            it_mock.return_value = ["a_hi", "b_hi"]
            result = await translate_texts_batch(["a", "b"], "hi")
            it_mock.assert_called()
            gt_mock.assert_not_called()
            assert result == ["a_hi", "b_hi"]

    @pytest.mark.asyncio
    async def test_batch_google_fallback(self):
        """When IndicTrans2 batch returns None, fall back to Google batch."""
        with patch("app.services.indictrans_client.translate_batch", new_callable=AsyncMock) as it_mock, \
             patch("app.services.translate_service._google_translate_batch_sync") as gt_mock:
            it_mock.return_value = None
            gt_mock.return_value = ["a_hi", "b_hi"]
            result = await translate_texts_batch(["a", "b"], "hi")
            assert result == ["a_hi", "b_hi"]
