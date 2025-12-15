#!/usr/bin/env python3
"""Script audit détection données personnelles (RGPD P3)."""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from src.settings import settings
from src.etl.utils import setup_logger

logger = setup_logger("scripts.audit_pii")

# Patterns détection PII
PII_PATTERNS = {
    "email": r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}",
    "phone": r"(\+?\d{1,3}[\s.-]?)?\(?\d{2,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}",
    "name": r"(M\.|Mme|Mr\.|Mrs\.) [A-Z][a-z]+ [A-Z][a-z]+",
    "ssn": r"\d{3}-\d{2}-\d{4}",
    "credit_card": r"\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}",
}


def get_db_engine() -> Engine:
    """Crée connexion SQLAlchemy."""
    return create_engine(settings.database.connection_url)


def check_pattern(text: str | None, pattern: str) -> bool:
    """Vérifie si texte contient pattern PII."""
    if not text:
        return False
    return bool(re.search(pattern, text, re.IGNORECASE))


def audit_table_column(
    engine: Engine, table: str, column: str
) -> list[dict[str, str | int]]:
    """Audit une colonne spécifique pour PII."""
    findings: list[dict[str, str | int]] = []

    query = text(f"SELECT id, {column} FROM {table} WHERE {column} IS NOT NULL")

    with engine.connect() as conn:
        result = conn.execute(query)

        for row in result:
            row_id, text_content = row

            for pattern_name, pattern in PII_PATTERNS.items():
                if check_pattern(text_content, pattern_name):
                    findings.append(
                        {
                            "table": table,
                            "column": column,
                            "row_id": row_id,
                            "pii_type": pattern_name,
                            "match": re.search(pattern, text_content, re.IGNORECASE).group(0),  # type: ignore
                        }
                    )

    return findings


def generate_report(findings: list[dict[str, str | int]], output_path: Path) -> None:
    """Génère rapport audit JSON."""
    report = {
        "audit_date": datetime.now().isoformat(),
        "total_findings": len(findings),
        "findings": findings,
        "status": "ALERT" if findings else "OK",
    }

    output_path.write_text(str(report), encoding="utf-8")
    logger.info(f"report_generated: {output_path}")


def anonymize_pii(
    engine: Engine, table: str, column: str, row_id: int, pii_match: str
) -> None:
    """Anonymise donnée PII détectée."""
    query = text(
        f"UPDATE {table} SET {column} = REPLACE({column}, :pii_match, '[REDACTED]') WHERE id = :row_id"
    )

    with engine.connect() as conn:
        conn.execute(query, {"pii_match": pii_match, "row_id": row_id})
        conn.commit()

    logger.info(f"anonymized: {table}.{column} row_id={row_id}")


def main() -> int:
    """Point d'entrée CLI."""
    parser = argparse.ArgumentParser(description="Audit PII base de données (RGPD P3)")
    parser.add_argument(
        "--table", default="films", help="Table à auditer (défaut: films)"
    )
    parser.add_argument(
        "--columns",
        nargs="+",
        default=["overview", "critics_consensus", "tagline"],
        help="Colonnes à auditer",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("data/rgpd_audit.json"), help="Rapport JSON"
    )
    parser.add_argument(
        "--auto-anonymize", action="store_true", help="Anonymiser PII automatiquement"
    )

    args = parser.parse_args()

    logger.info(f"audit_pii_started: table={args.table}, columns={args.columns}")

    # Connexion DB
    try:
        engine = get_db_engine()
    except Exception as e:
        logger.error(f"db_connection_failed: {e}")
        return 1

    # Audit colonnes
    all_findings: list[dict[str, str | int]] = []

    for column in args.columns:
        logger.info(f"auditing_column: {args.table}.{column}")
        findings = audit_table_column(engine, args.table, column)
        all_findings.extend(findings)

        if findings:
            logger.warning(
                f"pii_detected: {args.table}.{column} - {len(findings)} occurrences"
            )

    # Anonymisation automatique
    if args.auto_anonymize and all_findings:
        logger.info("auto_anonymization_started")

        for finding in all_findings:
            anonymize_pii(
                engine,
                str(finding["table"]),
                str(finding["column"]),
                int(finding["row_id"]),
                str(finding["match"]),
            )

    # Génération rapport
    args.output.parent.mkdir(parents=True, exist_ok=True)
    generate_report(all_findings, args.output)

    # Résumé
    if all_findings:
        logger.warning(f"audit_completed: {len(all_findings)} PII detected - STATUS: ALERT")
        return 1
    else:
        logger.info("audit_completed: 0 PII detected - STATUS: OK")
        return 0


if __name__ == "__main__":
    sys.exit(main())
