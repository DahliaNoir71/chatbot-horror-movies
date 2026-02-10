"""RAG prompt builder for assembling LLM message lists.

Combines system prompts, retrieved context, conversation history,
and the current user query into the message format expected by LLMService.
"""

from src.services.intent.prompts import get_system_prompt
from src.services.rag.retriever import RetrievedDocument


class RAGPromptBuilder:
    """Builds LLM-ready message lists from RAG components.

    Assembles messages in the order:
    1. System prompt (intent-specific)
    2. Context block (from RAG retrieval)
    3. Conversation history (from session)
    4. Current user message
    """

    @staticmethod
    def build(
        intent: str,
        user_message: str,
        documents: list[RetrievedDocument] | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> list[dict[str, str]]:
        """Build complete message list for LLM.

        Args:
            intent: Classified intent label.
            user_message: Current user query.
            documents: Retrieved RAG documents (may be empty).
            history: Previous conversation messages.

        Returns:
            List of message dicts with 'role' and 'content' keys.
        """
        has_context = bool(documents)
        messages: list[dict[str, str]] = []

        system_prompt = get_system_prompt(intent, has_context=has_context)
        messages.append({"role": "system", "content": system_prompt})

        if documents:
            context_text = RAGPromptBuilder._format_context(documents)
            messages.append({"role": "system", "content": context_text})

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": user_message})

        return messages

    @staticmethod
    def _format_context(documents: list[RetrievedDocument]) -> str:
        """Format retrieved documents into a context block.

        Args:
            documents: Retrieved documents with metadata.

        Returns:
            Formatted context string for the LLM.
        """
        parts = ["Voici les informations pertinentes de notre base de films d'horreur :\n"]

        for i, doc in enumerate(documents, 1):
            meta = doc.metadata
            title = meta.get("title", "Inconnu")
            year = meta.get("year", "")
            rating = meta.get("vote_average", "")
            tomatometer = meta.get("tomatometer", "")

            header = f"[{i}] {title}"
            if year:
                header += f" ({year})"
            if rating:
                header += f" - TMDB: {rating}/10"
            if tomatometer:
                header += f" - Tomatometer: {tomatometer}%"

            parts.append(header)
            parts.append(f"   Source: {doc.source_type}")
            parts.append(f"   {doc.content}\n")

        return "\n".join(parts)
