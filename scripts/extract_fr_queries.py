"""Extract French chatbot queries from the rag_queries log table.

Pulls recent queries from horrorbot_vectors.rag_queries, filters those
detected as French (heuristic on stopwords + diacritics), deduplicates
near-identical entries, and writes a JSONL dataset to feed the A/B
embedding harness.

Usage::

    uv run python scripts/extract_fr_queries.py
    uv run python scripts/extract_fr_queries.py --limit 1000 --max 50
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text

from src.settings import settings

_FR_STOPWORDS = frozenset(
    {
        "le", "la", "les", "un", "une", "des", "du", "de", "et", "ou",
        "mais", "donc", "car", "qui", "que", "quoi", "dont", "où",
        "ce", "cette", "ces", "mon", "ma", "mes", "ton", "ta", "tes",
        "son", "sa", "ses", "notre", "votre", "leur", "leurs",
        "je", "tu", "il", "elle", "nous", "vous", "ils", "elles",
        "est", "sont", "avec", "pour", "sans", "dans", "sur", "sous",
        "plus", "moins", "très", "trop", "aussi", "alors", "comment",
        "pourquoi", "quel", "quelle", "quels", "quelles",
        "as", "avez", "voir", "film", "films", "j'ai", "c'est",
        "n'est", "d'horreur", "d'épouvante",
    }
)
_FR_DIACRITICS = frozenset("àâäçéèêëîïôöùûüÿœæ")
_HORROR_TERMS_FR = frozenset(
    {"horreur", "épouvante", "fantôme", "tueur", "sorcière", "démon",
     "maudit", "hanté", "cauchemar", "sang", "mort", "monstre"}
)


def looks_french(query: str) -> bool:
    """Heuristic French detector — fast, no external dep.

    True when the query contains FR diacritics, FR stopwords, or
    domain-specific FR horror vocabulary. Tuned for chatbot queries
    (short, often noisy) — not a generic langdetect replacement.
    """
    if not query or not query.strip():
        return False
    lower = query.lower()
    if any(c in _FR_DIACRITICS for c in lower):
        return True
    tokens = [t.strip(".,!?;:'\"()") for t in lower.split()]
    if any(t in _HORROR_TERMS_FR for t in tokens):
        return True
    fr_token_hits = sum(1 for t in tokens if t in _FR_STOPWORDS)
    return fr_token_hits >= 2


def _normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.split())


def dedupe(queries: list[dict], threshold: float = 0.9) -> list[dict]:
    """Drop near-duplicates by normalized SequenceMatcher ratio."""
    kept: list[dict] = []
    seen_norm: list[str] = []
    for q in queries:
        norm = _normalize(q["query_text"])
        if any(SequenceMatcher(None, norm, s).ratio() >= threshold for s in seen_norm):
            continue
        kept.append(q)
        seen_norm.append(norm)
    return kept


def fetch_queries(limit: int) -> list[dict]:
    engine = create_engine(settings.database.vectors_sync_url)
    sql = text(
        """
        SELECT query_text, top_similarity_score, documents_retrieved, created_at
        FROM rag_queries
        WHERE query_text IS NOT NULL AND length(query_text) >= 5
        ORDER BY created_at DESC
        LIMIT :limit
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, {"limit": limit}).mappings().all()
    return [
        {
            "query_text": r["query_text"],
            "top_similarity_score": (
                float(r["top_similarity_score"])
                if r["top_similarity_score"] is not None
                else None
            ),
            "documents_retrieved": r["documents_retrieved"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=500,
                        help="Max rows to pull from rag_queries (default: 500).")
    parser.add_argument("--max", type=int, default=50,
                        help="Max FR queries to keep after dedup (default: 50).")
    parser.add_argument(
        "--output", type=Path,
        default=Path(__file__).resolve().parent.parent / "tests" / "data" / "ab_queries_fr.jsonl",
        help="Output JSONL path.",
    )
    args = parser.parse_args()

    print(f"Connecting to vectors DB and pulling last {args.limit} queries...")
    raw = fetch_queries(args.limit)
    print(f"  Pulled {len(raw)} rows.")

    fr = [q for q in raw if looks_french(q["query_text"])]
    print(f"  {len(fr)} detected as French.")

    deduped = dedupe(fr)
    print(f"  {len(deduped)} after dedup.")

    final = deduped[: args.max]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        for q in final:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")

    print(f"Wrote {len(final)} queries to {args.output}")
    if len(final) < 10:
        print(
            "  WARNING: fewer than 10 FR queries — A/B significance will be weak. "
            "Consider seeding the chatbot with more FR traffic, or augment manually."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
