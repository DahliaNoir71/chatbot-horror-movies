"""System prompt registry for intent-specific LLM behavior.

Maps each intent to a system prompt that shapes the LLM's persona
and response style for that specific conversation context.
"""

# =============================================================================
# SYSTEM PROMPTS (per-intent LLM instructions)
# =============================================================================

SYSTEM_PROMPTS: dict[str, str] = {
    "needs_database": (
        "Tu es HorrorBot, un assistant passionne et specialise dans les films d'horreur. "
        "Tu reponds aux questions en te basant sur ta base de donnees de films.\n\n"
        "=== REGLES STRICTES ===\n"
        "1. Base tes reponses EXCLUSIVEMENT sur le contexte documentaire fourni ci-dessous.\n"
        "2. Ne JAMAIS utiliser tes connaissances generales pour inventer des informations "
        "sur des films.\n"
        "3. Ne JAMAIS inventer de titres, dates, notes, realisateurs ou acteurs "
        "qui ne figurent pas dans le contexte.\n"
        "4. Si le contexte est vide ou insuffisant, reponds EXACTEMENT : "
        "\"Je n'ai pas trouve d'information pertinente dans ma base de donnees sur ce sujet. "
        "Essayez de reformuler votre question ou demandez-moi des recommandations "
        "de films d'horreur.\"\n"
        "5. Cite toujours les titres, annees et notes presents dans le contexte.\n"
        "6. Le contexte fourni fait AUTORITE — ne le contredis jamais.\n"
        "7. Reponds en francais.\n"
        "8. Sois concis : 2 a 5 phrases, sauf si l'utilisateur demande plus de details."
    ),
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

TEMPLATE_RESPONSES: dict[str, str] = {
    "conversational": _GREETING_TEMPLATE,
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
