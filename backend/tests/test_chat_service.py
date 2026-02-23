"""Tests for chat FSM state transitions and intent classification fallback."""

import pytest

from app.chatbot.fsm import ChatState, TRANSITIONS, get_next_state


# ---------------------------------------------------------------------------
# FSM state transition tests
# ---------------------------------------------------------------------------

class TestFSMTransitions:
    """Validate every defined transition in the FSM."""

    # GREETING state
    def test_greeting_greeting_stays(self):
        assert get_next_state(ChatState.GREETING, "greeting") == ChatState.GREETING

    def test_greeting_search_goes_to_need_extraction(self):
        assert get_next_state(ChatState.GREETING, "search_scheme") == ChatState.NEED_EXTRACTION

    def test_greeting_detail_goes_to_need_extraction(self):
        assert get_next_state(ChatState.GREETING, "ask_detail") == ChatState.NEED_EXTRACTION

    def test_greeting_eligibility_goes_to_need_extraction(self):
        assert get_next_state(ChatState.GREETING, "check_eligibility") == ChatState.NEED_EXTRACTION

    def test_greeting_unknown_goes_to_need_extraction(self):
        assert get_next_state(ChatState.GREETING, "random_unknown") == ChatState.NEED_EXTRACTION

    # NEED_EXTRACTION state
    def test_need_extraction_search_goes_to_scheme_search(self):
        assert get_next_state(ChatState.NEED_EXTRACTION, "search_scheme") == ChatState.SCHEME_SEARCH

    def test_need_extraction_clarify_stays(self):
        assert get_next_state(ChatState.NEED_EXTRACTION, "clarify") == ChatState.NEED_EXTRACTION

    def test_need_extraction_eligibility_goes_to_search(self):
        assert get_next_state(ChatState.NEED_EXTRACTION, "check_eligibility") == ChatState.SCHEME_SEARCH

    def test_need_extraction_detail_goes_to_detail(self):
        assert get_next_state(ChatState.NEED_EXTRACTION, "ask_detail") == ChatState.SCHEME_DETAIL

    def test_need_extraction_goodbye_goes_to_closing(self):
        assert get_next_state(ChatState.NEED_EXTRACTION, "goodbye") == ChatState.CLOSING

    def test_need_extraction_other_goes_to_search(self):
        assert get_next_state(ChatState.NEED_EXTRACTION, "other") == ChatState.SCHEME_SEARCH

    # SCHEME_SEARCH state
    def test_search_detail_goes_to_detail(self):
        assert get_next_state(ChatState.SCHEME_SEARCH, "ask_detail") == ChatState.SCHEME_DETAIL

    def test_search_search_goes_to_need_extraction(self):
        assert get_next_state(ChatState.SCHEME_SEARCH, "search_scheme") == ChatState.NEED_EXTRACTION

    def test_search_clarify_goes_to_disambiguation(self):
        assert get_next_state(ChatState.SCHEME_SEARCH, "clarify") == ChatState.DISAMBIGUATION

    def test_search_goodbye_goes_to_closing(self):
        assert get_next_state(ChatState.SCHEME_SEARCH, "goodbye") == ChatState.CLOSING

    def test_search_other_goes_to_disambiguation(self):
        assert get_next_state(ChatState.SCHEME_SEARCH, "other") == ChatState.DISAMBIGUATION

    # DISAMBIGUATION state
    def test_disambig_search_goes_to_search(self):
        assert get_next_state(ChatState.DISAMBIGUATION, "search_scheme") == ChatState.SCHEME_SEARCH

    def test_disambig_detail_goes_to_detail(self):
        assert get_next_state(ChatState.DISAMBIGUATION, "ask_detail") == ChatState.SCHEME_DETAIL

    def test_disambig_clarify_stays(self):
        assert get_next_state(ChatState.DISAMBIGUATION, "clarify") == ChatState.DISAMBIGUATION

    def test_disambig_goodbye_goes_to_closing(self):
        assert get_next_state(ChatState.DISAMBIGUATION, "goodbye") == ChatState.CLOSING

    def test_disambig_other_goes_to_search(self):
        assert get_next_state(ChatState.DISAMBIGUATION, "other") == ChatState.SCHEME_SEARCH

    # SCHEME_DETAIL state
    def test_detail_search_goes_to_need_extraction(self):
        assert get_next_state(ChatState.SCHEME_DETAIL, "search_scheme") == ChatState.NEED_EXTRACTION

    def test_detail_detail_stays(self):
        assert get_next_state(ChatState.SCHEME_DETAIL, "ask_detail") == ChatState.SCHEME_DETAIL

    def test_detail_goodbye_goes_to_closing(self):
        assert get_next_state(ChatState.SCHEME_DETAIL, "goodbye") == ChatState.CLOSING

    def test_detail_other_goes_to_need_extraction(self):
        assert get_next_state(ChatState.SCHEME_DETAIL, "other") == ChatState.NEED_EXTRACTION

    # CLOSING state
    def test_closing_greeting_goes_to_greeting(self):
        assert get_next_state(ChatState.CLOSING, "greeting") == ChatState.GREETING

    def test_closing_search_goes_to_need_extraction(self):
        assert get_next_state(ChatState.CLOSING, "search_scheme") == ChatState.NEED_EXTRACTION

    def test_closing_other_goes_to_greeting(self):
        assert get_next_state(ChatState.CLOSING, "other") == ChatState.GREETING


# ---------------------------------------------------------------------------
# FSM completeness tests
# ---------------------------------------------------------------------------

class TestFSMCompleteness:
    """Ensure the FSM transition map covers all states."""

    def test_all_states_have_transitions(self):
        for state in ChatState:
            assert state in TRANSITIONS, f"Missing transitions for {state}"

    def test_all_states_have_other_fallback(self):
        """Every state should have an 'other' fallback transition."""
        for state in ChatState:
            assert "other" in TRANSITIONS[state], f"Missing 'other' fallback for {state}"

    def test_greeting_is_reachable_from_closing(self):
        """Users should be able to restart conversations."""
        assert get_next_state(ChatState.CLOSING, "greeting") == ChatState.GREETING

    def test_closing_is_reachable_from_all_middle_states(self):
        """Every middle state should have a path to CLOSING via 'goodbye'."""
        for state in [ChatState.NEED_EXTRACTION, ChatState.SCHEME_SEARCH,
                      ChatState.DISAMBIGUATION, ChatState.SCHEME_DETAIL]:
            assert get_next_state(state, "goodbye") == ChatState.CLOSING


# ---------------------------------------------------------------------------
# Fallback intent classification tests (keyword-based)
# ---------------------------------------------------------------------------

class TestFallbackIntentClassification:
    """Test the keyword-based intent fallback in chat_service."""

    def test_greeting_keywords_coverage(self):
        """All supported languages should have greeting keywords."""
        from app.services.chat_service import GREETING_WORDS
        for lang in ["en", "hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa", "or", "ur"]:
            assert lang in GREETING_WORDS, f"Missing greeting keywords for {lang}"
            assert len(GREETING_WORDS[lang]) > 0

    def test_goodbye_keywords_coverage(self):
        from app.services.chat_service import GOODBYE_WORDS
        for lang in ["en", "hi", "bn", "ta", "te"]:
            assert lang in GOODBYE_WORDS
            assert len(GOODBYE_WORDS[lang]) > 0

    def test_detail_keywords_coverage(self):
        from app.services.chat_service import DETAIL_WORDS
        for lang in ["en", "hi", "bn", "ta", "te"]:
            assert lang in DETAIL_WORDS
            assert len(DETAIL_WORDS[lang]) > 0

    def test_eligibility_keywords_coverage(self):
        from app.services.chat_service import ELIGIBILITY_WORDS
        for lang in ["en", "hi", "bn", "ta", "te"]:
            assert lang in ELIGIBILITY_WORDS
            assert len(ELIGIBILITY_WORDS[lang]) > 0

    def test_fallback_greetings_all_languages(self):
        """Every language should have fallback greeting text."""
        from app.services.chat_service import FALLBACK_GREETINGS
        for lang in ["en", "hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa", "or", "ur"]:
            assert lang in FALLBACK_GREETINGS
            assert len(FALLBACK_GREETINGS[lang]) > 20  # Non-trivial text

    def test_suggestions_all_have_greeting(self):
        """All suggestion languages should have greeting suggestions."""
        from app.services.chat_service import SUGGESTIONS
        for lang, suggs in SUGGESTIONS.items():
            assert "greeting" in suggs, f"Language {lang} missing greeting suggestions"
            assert len(suggs["greeting"]) >= 2
