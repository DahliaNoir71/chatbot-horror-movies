"""Point d'entrée du module src. Permet python -m src."""

import argparse
import asyncio
import sys


def run_etl(max_pages: int | None, resume_from: int | None) -> None:
    """Lance le pipeline ETL."""
    from src.etl.pipeline import resume_from_step, run_full_pipeline

    if resume_from:
        asyncio.run(resume_from_step(resume_from, max_pages))
    else:
        asyncio.run(run_full_pipeline(max_pages))


def run_import_database() -> None:
    """Importe le dernier checkpoint en base."""
    from src.database.importer import DatabaseImporter
    from src.etl.utils import CheckpointManager

    checkpoint_manager = CheckpointManager()

    # Dernier checkpoint final
    checkpoints = sorted(
        [cp for cp in checkpoint_manager.list_checkpoints() if "final" in cp],
        reverse=True,
    )

    if not checkpoints:
        print("❌ Aucun checkpoint final. Lancer: python -m src etl")
        sys.exit(1)

    latest = checkpoints[0]
    print(f"📂 Import checkpoint: {latest}")

    data = checkpoint_manager.load(latest)
    if not data:
        print(f"❌ Erreur chargement {latest}")
        sys.exit(1)

    importer = DatabaseImporter()
    importer.init_database()
    imported = importer.import_films(data)

    print(f"✅ {imported} films importés")


def run_full_pipeline(max_pages: int | None) -> None:
    """Pipeline complet : ETL + Import DB."""
    from src.database.importer import DatabaseImporter
    from src.etl.pipeline import run_full_pipeline as etl_pipeline

    print("🚀 PIPELINE COMPLET : ETL + Import DB")

    # ETL
    dataset = asyncio.run(etl_pipeline(max_pages))

    # Import DB
    print("\n" + "=" * 80)
    print("💾 ÉTAPE 4/4 : IMPORT POSTGRESQL + EMBEDDINGS")
    print("=" * 80)

    importer = DatabaseImporter()
    importer.init_database()
    imported = importer.import_films(dataset)

    print(f"✅ Pipeline complet : {imported} films en base")


def run_api() -> None:
    """Lance l'API FastAPI."""
    import uvicorn

    from src.settings import settings

    print("🌐 Démarrage API FastAPI...")
    uvicorn.run(
        "src.api.main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.api.reload,
    )


def list_checkpoints() -> None:
    """Liste les checkpoints."""
    from src.etl.utils import CheckpointManager

    checkpoint_manager = CheckpointManager()
    checkpoints = checkpoint_manager.list_checkpoints()

    print("\n📂 Checkpoints disponibles :")
    for cp in checkpoints:
        print(f"  - {cp}")
    print(f"\nTotal : {len(checkpoints)}")


def main() -> None:
    """CLI principal."""
    parser = argparse.ArgumentParser(
        description="HorrorBot - Chatbot films d'horreur avec RAG",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python -m src etl --max-pages 5          # Pipeline ETL
  python -m src import-db                  # Import checkpoint
  python -m src full --max-pages 5         # Pipeline complet
  python -m src api                        # API FastAPI
  python -m src list-checkpoints           # Lister checkpoints
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commande")

    # ETL
    etl_parser = subparsers.add_parser("etl", help="Pipeline ETL")
    etl_parser.add_argument("--max-pages", type=int)
    etl_parser.add_argument("--resume-from", type=int, choices=[1, 2, 3])

    # Import DB
    subparsers.add_parser("import-db", help="Import checkpoint en base")

    # Pipeline complet
    full_parser = subparsers.add_parser("full", help="ETL + DB")
    full_parser.add_argument("--max-pages", type=int)

    # API
    subparsers.add_parser("api", help="API FastAPI")

    # Liste
    subparsers.add_parser("list-checkpoints", help="Lister checkpoints")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "etl":
            run_etl(args.max_pages, args.resume_from)
        elif args.command == "import-db":
            run_import_database()
        elif args.command == "full":
            run_full_pipeline(args.max_pages)
        elif args.command == "api":
            run_api()
        elif args.command == "list-checkpoints":
            list_checkpoints()

    except KeyboardInterrupt:
        print("\n⚠️  Interrompu")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ ERREUR : {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
