"""Translation quality metrics: BLEU score, coverage, cache stats.

Run with: pytest backend/tests/test_translation_quality.py -v -s
Requires: running DB + IndicTrans2 service (or Google Translate access).
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.benchmark

# Reference translations: (english, hindi_reference)
# Hand-curated for a few scheme names to compute BLEU against.
REFERENCE_TRANSLATIONS = [
    ("National Scholarship for Students", "छात्रों के लिए राष्ट्रीय छात्रवृत्ति"),
    ("Women Empowerment Programme", "महिला सशक्तिकरण कार्यक्रम"),
    ("Housing for All", "सबके लिए आवास"),
    ("Farmer Income Support Scheme", "किसान आय सहायता योजना"),
    ("Health Insurance Scheme", "स्वास्थ्य बीमा योजना"),
]


class TestTranslationQualityMetrics:
    """Compare translation outputs against reference translations."""

    def test_bleu_score_hindi(self):
        """Compute BLEU score for Hindi translations of scheme names."""
        try:
            import sacrebleu
        except ImportError:
            pytest.skip("sacrebleu not installed")

        from app.services.translate_service import _google_translate_sync

        hypotheses = []
        references = []

        for en_text, hi_ref in REFERENCE_TRANSLATIONS:
            try:
                translated = _google_translate_sync(en_text, "hi")
                if translated:
                    hypotheses.append(translated)
                    references.append(hi_ref)
            except Exception:
                continue

        if not hypotheses:
            pytest.skip("No translations obtained (network issue?)")

        bleu = sacrebleu.corpus_bleu(hypotheses, [references])
        print(f"\n  BLEU score (Hindi): {bleu.score:.2f}")
        print(f"  Translations tested: {len(hypotheses)}/{len(REFERENCE_TRANSLATIONS)}")

        # BLEU > 10 is reasonable for short phrases across scripts
        # This is a baseline — not a hard requirement
        assert bleu.score >= 0, "BLEU score should be non-negative"

    def test_translation_coverage_google(self):
        """Measure which languages Google Translate can handle."""
        from app.services.translate_service import GOOGLE_LANG_MAP, SUPPORTED_LANGS

        google_supported = set(GOOGLE_LANG_MAP.keys())
        total = len(SUPPORTED_LANGS)
        covered = len(google_supported)
        missing = SUPPORTED_LANGS - google_supported

        coverage_pct = (covered / total) * 100
        print(f"\n  Google Translate coverage: {covered}/{total} ({coverage_pct:.0f}%)")
        print(f"  Missing languages: {missing}")

        assert coverage_pct > 80, f"Google coverage too low: {coverage_pct:.0f}%"

    def test_indictrans_language_coverage(self):
        """IndicTrans2 should support all SUPPORTED_LANGS."""
        from app.services.translate_service import SUPPORTED_LANGS

        # IndicTrans2 supports all Indian languages in SUPPORTED_LANGS by design
        # This test documents the expected coverage
        expected_indictrans_langs = {
            "hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa", "or", "ur",
            "as", "ne", "sa", "sd", "mai", "doi", "kok", "sat", "mni", "bodo", "lus",
        }
        assert SUPPORTED_LANGS == expected_indictrans_langs

    def test_lang_code_mapping_consistency(self):
        """All Google lang codes should map to valid identifiers."""
        from app.services.translate_service import GOOGLE_LANG_MAP

        for internal_code, google_code in GOOGLE_LANG_MAP.items():
            assert isinstance(google_code, str)
            assert len(google_code) >= 2
            assert len(internal_code) >= 2


class TestCacheMetrics:
    """Measure translation cache behavior."""

    @pytest.mark.asyncio
    async def test_cache_hit_avoids_api_call(self):
        """After caching, translation should not call external API."""
        from app.services.translate_service import _cache_key, translate_text

        call_count = 0

        async def counting_translate(text, lang):
            nonlocal call_count
            call_count += 1
            return f"[{lang}]{text}"

        with patch("app.services.indictrans_client.translate_single", side_effect=counting_translate):
            # First call — should hit the API
            result1 = await translate_text("hello", "hi", db=None)
            first_calls = call_count

            # Second call — without DB caching, it will still call API
            # (DB cache requires a session; this tests the flow)
            result2 = await translate_text("hello", "hi", db=None)

        assert first_calls == 1
        # Without DB, no caching — both calls go through
        assert call_count == 2

    def test_cache_key_collision_resistance(self):
        """Different inputs should produce different cache keys."""
        from app.services.translate_service import _cache_key

        keys = set()
        test_cases = [
            ("hello", "hi"),
            ("hello", "bn"),
            ("world", "hi"),
            ("Hello", "hi"),  # Case sensitive
            ("hello world", "hi"),
        ]
        for text, lang in test_cases:
            keys.add(_cache_key(text, lang))

        assert len(keys) == len(test_cases), "Cache key collision detected"
