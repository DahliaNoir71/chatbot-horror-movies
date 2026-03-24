"""RAG prompt builder for assembling LLM message lists.

Combines system prompts, retrieved context, conversation history,
and the current user query into the message format expected by LLMService.
"""

from src.services.intent.prompts import get_system_prompt
from src.services.rag.retriever import RetrievedDocument

# Maximum history messages to include (3 turns = 6 messages).
# Budget: system (~300 tok) + context (~1500 tok) + history (~800 tok)
# + user (~50 tok) + generation (1024 tok) ≈ 3674 < 4096 context window.
_MAX_HISTORY_MESSAGES = 6


class RAGPromptBuilder:
    """Builds LLM-ready message lists from RAG components.

    Assembles messages in the order:
    1. System prompt (intent-specific)
    2. Context block (from RAG retrieval, or explicit empty block)
    3. Conversation history (truncated to last 3 turns)
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
        messages: list[dict[str, str]] = []

        system_prompt = get_system_prompt(intent)
        messages.append({"role": "system", "content": system_prompt})

        context_text = RAGPromptBuilder._format_context(documents)
        messages.append({"role": "system", "content": context_text})

        if history:
            truncated = history[-_MAX_HISTORY_MESSAGES:]
            messages.extend(truncated)

        messages.append({"role": "user", "content": user_message})

        return messages

    @staticmethod
    def _format_context(documents: list[RetrievedDocument] | None) -> str:
        """Format retrieved documents into a context block.

        Always returns a context block — when no documents are found,
        returns an explicit empty block so the LLM sees the absence
        and applies the standardized fallback response (rule 4).

        Args:
            documents: Retrieved documents with metadata, or None.

        Returns:
            Formatted context string for the LLM.
        """
        header = "=== CONTEXTE DOCUMENTAIRE (source de verite) ==="

        if not documents:
            return f"{header}\nAucun document pertinent trouve dans la base."

        parts = [header, ""]

        for i, doc in enumerate(documents, 1):
            meta = doc.metadata
            title = meta.get("title", "Inconnu")
            year = meta.get("year", "")
            rating = meta.get("vote_average", "")
            tomatometer = meta.get("tomatometer", "")

            doc_header = f"[{i}] {title}"
            if year:
                doc_header += f" ({year})"
            if rating:
                doc_header += f" - TMDB: {rating}/10"
            if tomatometer:
                doc_header += f" - Tomatometer: {tomatometer}%"

            parts.append(doc_header)
            parts.append(f"   Source: {doc.source_type}")
            parts.append(f"   {doc.content}\n")

        return "\n".join(parts)
