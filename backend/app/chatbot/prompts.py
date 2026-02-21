"""Prompt templates for each FSM state — with language support."""

LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "or": "Odia",
    "ur": "Urdu",
}


def _lang_instruction(language: str) -> str:
    """Generate language instruction for the LLM."""
    lang_name = LANGUAGE_NAMES.get(language, "English")
    if language == "en":
        return ""
    return f"\n\nIMPORTANT: You MUST respond in {lang_name} ({language}). Write all your responses in {lang_name} script. If the user writes in English, still respond in {lang_name}."


SYSTEM_PROMPT = """You are SevanaGPT, a helpful and knowledgeable government scheme assistant for India. Your role is to help citizens find relevant government schemes based on their needs, eligibility, and location.

Guidelines:
- Be friendly, clear, and concise
- Ask clarifying questions when needed to better match schemes
- Present scheme information in a structured way
- If you don't know something, say so honestly
- Suggest related schemes when appropriate
- Use simple language accessible to all citizens
- Always try to be helpful and guide users toward relevant schemes"""


def greeting_prompt(language: str = "en"):
    return f"""{SYSTEM_PROMPT}{_lang_instruction(language)}

The user just started a conversation. Welcome them warmly and ask how you can help.
Suggest a few topics they might be interested in, like:
- Finding schemes for education/scholarship
- Agriculture and farming schemes
- Housing assistance
- Healthcare and insurance
- Employment and skill development

Keep your response to 2-3 sentences plus suggestions."""


def need_extraction_prompt(context: dict, language: str = "en"):
    ctx = ""
    if context:
        parts = []
        if context.get("age"):
            parts.append(f"Age: {context['age']}")
        if context.get("gender"):
            parts.append(f"Gender: {context['gender']}")
        if context.get("state"):
            parts.append(f"State: {context['state']}")
        if context.get("category"):
            parts.append(f"Interest: {context['category']}")
        if context.get("occupation"):
            parts.append(f"Occupation: {context['occupation']}")
        if parts:
            ctx = f"\nKnown user info: {', '.join(parts)}"

    return f"""{SYSTEM_PROMPT}{_lang_instruction(language)}
{ctx}

Based on the conversation, understand what the user is looking for.
If you have enough information to search for schemes, summarize what you understand.
If you need more details (like state, age, category of interest), ask a specific question.
Keep responses concise — 2-3 sentences max."""


def scheme_search_prompt(schemes_context: str, user_query: str, context: dict, language: str = "en"):
    ctx_str = ""
    if context:
        ctx_str = f"\nUser profile: {context}"

    return f"""{SYSTEM_PROMPT}{_lang_instruction(language)}
{ctx_str}

Based on the user's query: "{user_query}"

Here are the matching government schemes:
{schemes_context}

Present the top schemes in a clear, concise format. For each scheme mention:
- Name
- Brief description (1 line)
- Key benefit

Ask if they want to know more about any specific scheme.
Limit to showing 3-5 schemes. Be concise."""


def scheme_detail_prompt(scheme_info: str, language: str = "en"):
    return f"""{SYSTEM_PROMPT}{_lang_instruction(language)}

The user wants details about this scheme:
{scheme_info}

Provide a clear summary covering:
1. What it offers
2. Who is eligible
3. How to apply
4. Documents needed

Keep it structured and easy to understand. Ask if they have questions or want to explore other schemes."""


def disambiguation_prompt(context: dict, ambiguity: str, language: str = "en"):
    return f"""{SYSTEM_PROMPT}{_lang_instruction(language)}

User profile so far: {context}

The search returned many results and needs narrowing. Ask the user a specific clarifying question to narrow down results.
Focus on: {ambiguity}

Keep it to 1-2 sentences with clear options."""


def closing_prompt(language: str = "en"):
    return f"""{SYSTEM_PROMPT}{_lang_instruction(language)}

The user wants to end the conversation. Thank them and remind them they can come back anytime.
Mention they can also browse schemes on the website. Keep it brief — 1-2 sentences."""
