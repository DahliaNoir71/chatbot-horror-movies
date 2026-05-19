"""System prompt registry for intent-specific LLM behavior.

Maps each intent to a system prompt that shapes the LLM's persona
and response style for that specific conversation context.
"""

# =============================================================================
# SYSTEM PROMPTS (per-intent LLM instructions)
# =============================================================================

SYSTEM_PROMPT_RAG = """Tu es HorrorBot, un assistant spécialisé dans les films d'horreur.

RÈGLES STRICTES :
- Réponds UNIQUEMENT à partir du CONTEXTE ci-dessous.
- Si le contexte ne contient pas d'information pertinente pour la question, dis clairement : « Je n'ai pas trouvé d'information fiable dans ma base de données sur ce sujet. »
- N'invente JAMAIS de faits, noms d'acteurs, réalisateurs, dates, notes ou synopsis qui ne figurent pas dans le contexte.
- Ne complète JAMAIS avec tes connaissances pré-entraînées, même si tu connais la réponse.
- Si le contexte mentionne un film différent de celui demandé, signale-le explicitement (ex: « Je n'ai pas trouvé <titre demandé>, mais le contexte mentionne <titre trouvé> »).
- Les titres peuvent être donnés en français ou en anglais : les deux sont valides (les sources exposent les deux via title et title_fr).
- Réponds en français, de manière concise et structurée.

CONTEXTE :
{context}
"""

SYSTEM_PROMPTS: dict[str, str] = {
    "needs_database": SYSTEM_PROMPT_RAG,
}

# =============================================================================
# TEMPLATE RESPONSES (non-LLM intents)
# =============================================================================

# Greeting keywords (case-insensitive)
_GREETING_KEYWORDS = {
    "bonjour",
    "salut",
    "hello",
    "hey",
    "coucou",
    "bonsoir",
    "hi",
}

# Farewell keywords (case-insensitive)
_FAREWELL_KEYWORDS = {
    "au revoir",
    "bye",
    "goodbye",
    "adieu",
    "a bientot",
    "bonne nuit",
    "merci",
    "thanks",
}

_GREETING_TEMPLATE = (
    "Bonjour ! Je suis HorrorBot, votre compagnon du cinema d'horreur. "
    "Je peux vous recommander des films effrayants, discuter du cinema d'horreur, "
    "partager des anecdotes ou chercher des details sur des films specifiques. "
    "Que souhaitez-vous explorer ?"
)

_FAREWELL_TEMPLATE = (
    "Au revoir ! Merci d'avoir discute de films d'horreur avec moi. "
    "Revenez quand vous voudrez une bonne frayeur. Restez sur vos gardes !"
)

TEMPLATE_THANKS = "Avec plaisir ! N'hesite pas si tu as d'autres questions sur les films d'horreur."

TEMPLATE_RESPONSES: dict[str, str] = {
    "conversational": _GREETING_TEMPLATE,
    "thanks": TEMPLATE_THANKS,
    "off_topic": (
        "J'apprecie votre question, mais je suis specialise dans les films d'horreur ! "
        "Je peux vous aider avec des recommandations de films d'horreur, des details sur des films, "
        "des anecdotes ou des discussions generales sur l'horreur. "
        "Quel sujet horrifique vous interesse ?"
    ),
}


# =============================================================================
# PUBLIC API
# =============================================================================


def get_system_prompt(intent: str) -> str:
    """Get the system prompt for a given intent.

    Args:
        intent: Classified intent label.

    Returns:
        System prompt string for LLM.
    """
    return SYSTEM_PROMPTS.get(intent, SYSTEM_PROMPTS["needs_database"])


def get_template_response(intent: str, user_message: str = "") -> str | None:
    """Get template response for non-LLM intents.

    For ``conversational`` intent, uses keyword detection to pick
    a greeting or farewell template.

    Args:
        intent: Classified intent label.
        user_message: Original user message (for greeting/farewell detection).

    Returns:
        Template response string, or None if intent requires LLM.
    """
    if intent == "conversational" and user_message:
        lower = user_message.lower()
        if any(kw in lower for kw in _FAREWELL_KEYWORDS):
            return _FAREWELL_TEMPLATE
        return _GREETING_TEMPLATE

    return TEMPLATE_RESPONSES.get(intent)
