"""Finite State Machine for chatbot conversation flow."""

from enum import Enum


class ChatState(str, Enum):
    GREETING = "GREETING"
    NEED_EXTRACTION = "NEED_EXTRACTION"
    SCHEME_SEARCH = "SCHEME_SEARCH"
    DISAMBIGUATION = "DISAMBIGUATION"
    SCHEME_DETAIL = "SCHEME_DETAIL"
    CLOSING = "CLOSING"


# Intent to state transition map
TRANSITIONS: dict[ChatState, dict[str, ChatState]] = {
    ChatState.GREETING: {
        "greeting": ChatState.GREETING,
        "search_scheme": ChatState.NEED_EXTRACTION,
        "ask_detail": ChatState.NEED_EXTRACTION,
        "check_eligibility": ChatState.NEED_EXTRACTION,
        "other": ChatState.NEED_EXTRACTION,
    },
    ChatState.NEED_EXTRACTION: {
        "search_scheme": ChatState.SCHEME_SEARCH,
        "clarify": ChatState.NEED_EXTRACTION,
        "check_eligibility": ChatState.SCHEME_SEARCH,
        "ask_detail": ChatState.SCHEME_DETAIL,
        "goodbye": ChatState.CLOSING,
        "other": ChatState.SCHEME_SEARCH,
    },
    ChatState.SCHEME_SEARCH: {
        "ask_detail": ChatState.SCHEME_DETAIL,
        "search_scheme": ChatState.NEED_EXTRACTION,
        "clarify": ChatState.DISAMBIGUATION,
        "goodbye": ChatState.CLOSING,
        "other": ChatState.DISAMBIGUATION,
    },
    ChatState.DISAMBIGUATION: {
        "search_scheme": ChatState.SCHEME_SEARCH,
        "ask_detail": ChatState.SCHEME_DETAIL,
        "clarify": ChatState.DISAMBIGUATION,
        "goodbye": ChatState.CLOSING,
        "other": ChatState.SCHEME_SEARCH,
    },
    ChatState.SCHEME_DETAIL: {
        "search_scheme": ChatState.NEED_EXTRACTION,
        "ask_detail": ChatState.SCHEME_DETAIL,
        "goodbye": ChatState.CLOSING,
        "other": ChatState.NEED_EXTRACTION,
    },
    ChatState.CLOSING: {
        "greeting": ChatState.GREETING,
        "search_scheme": ChatState.NEED_EXTRACTION,
        "other": ChatState.GREETING,
    },
}


def get_next_state(current: ChatState, intent: str) -> ChatState:
    """Determine next FSM state based on current state and classified intent."""
    state_transitions = TRANSITIONS.get(current, {})
    return state_transitions.get(intent, state_transitions.get("other", ChatState.NEED_EXTRACTION))
