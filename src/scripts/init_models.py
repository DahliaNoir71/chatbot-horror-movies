"""Initialize HorrorBot AI models.

Downloads required models if not already present:
- LLM (GGUF) from HuggingFace
- Intent classifier (DeBERTa) from HuggingFace
- Embedding model (MiniLM) from HuggingFace

Usage:
    python -m src.scripts.init_models
    python -m src.scripts.init_models --check       # Check only
    python -m src.scripts.init_models --llm         # LLM only
    python -m src.scripts.init_models --classifier  # Classifier only
    python -m src.scripts.init_models --embedding   # Embedding only
"""

import argparse
import shutil
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from huggingface_hub import hf_hub_download, snapshot_download, try_to_load_from_cache
from huggingface_hub.utils import GatedRepoError, LocalEntryNotFoundError, RepositoryNotFoundError

from src.settings import settings

# =========================================================================
# Argument parsing
# =========================================================================


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Initialize HorrorBot AI models",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only check model presence, don't download",
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Download LLM model only",
    )
    parser.add_argument(
        "--classifier",
        action="store_true",
        help="Download classifier model only",
    )
    parser.add_argument(
        "--embedding",
        action="store_true",
        help="Download embedding model only",
    )
    return parser.parse_args()


# =========================================================================
# Model checks
# =========================================================================


def is_llm_present() -> bool:
    """Check if the LLM GGUF file exists on disk."""
    return settings.llm.is_configured


def is_hf_model_cached(repo_id: str) -> bool:
    """Check if a HuggingFace model is in the local cache.

    Args:
        repo_id: HuggingFace repository ID.

    Returns:
        True if at least the config file is cached.
    """
    try:
        result = try_to_load_from_cache(repo_id, filename="config.json")
        return result is not None
    except (LocalEntryNotFoundError, RepositoryNotFoundError):
        return False


def check_models() -> dict[str, bool]:
    """Check presence of all models.

    Returns:
        Dict mapping model name to presence status.
    """
    return {
        "llm": is_llm_present(),
        "classifier": is_hf_model_cached(settings.classifier.model_name),
        "embedding": is_hf_model_cached(f"sentence-transformers/{settings.embedding.model_name}"),
    }


# =========================================================================
# Downloads
# =========================================================================


def download_llm() -> bool:
    """Download the LLM GGUF file from HuggingFace.

    Downloads to the HuggingFace cache, then copies to the
    expected local path (settings.llm.absolute_model_path).

    Returns:
        True if download succeeded.
    """
    dest = settings.llm.absolute_model_path
    if dest.exists():
        print(f"   Already present: {dest}")
        return True

    repo_id = settings.llm.hf_repo
    filename = settings.llm.hf_filename

    print(f"   Downloading {filename} from {repo_id}...")
    print(f"   Destination: {dest}")

    try:
        cached_path = hf_hub_download(repo_id=repo_id, filename=filename)
    except (RepositoryNotFoundError, GatedRepoError) as e:
        print(f"   Download failed: {e}")
        return False

    # Copy from HF cache to expected location
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(cached_path, dest)
    print(f"   Copied to {dest}")
    return True


def download_classifier() -> bool:
    """Pre-download the intent classifier model to HuggingFace cache.

    Returns:
        True if download succeeded.
    """
    repo_id = settings.classifier.model_name

    if is_hf_model_cached(repo_id):
        print(f"   Already cached: {repo_id}")
        return True

    print(f"   Downloading {repo_id}...")

    try:
        snapshot_download(repo_id=repo_id)
    except (RepositoryNotFoundError, GatedRepoError) as e:
        print(f"   Download failed: {e}")
        return False

    return True


def download_embedding() -> bool:
    """Pre-download the embedding model to HuggingFace cache.

    Returns:
        True if download succeeded.
    """
    model_name = settings.embedding.model_name
    repo_id = f"sentence-transformers/{model_name}"

    if is_hf_model_cached(repo_id):
        print(f"   Already cached: {repo_id}")
        return True

    print(f"   Downloading {repo_id}...")

    try:
        snapshot_download(repo_id=repo_id)
    except (RepositoryNotFoundError, GatedRepoError) as e:
        print(f"   Download failed: {e}")
        return False

    return True


# =========================================================================
# Display
# =========================================================================


def _print_banner() -> None:
    """Print the application banner with model info."""
    print("=" * 55)
    print("  HorrorBot Model Initialization")
    print("=" * 55)
    print(f"   LLM:        {settings.llm.model_path}")
    print(f"   Classifier:  {settings.classifier.model_name}")
    print(f"   Embedding:   {settings.embedding.model_name}")
    print("=" * 55)


def _print_status(status: dict[str, bool]) -> None:
    """Print model status summary.

    Args:
        status: Dict mapping model name to presence status.
    """
    labels = {
        "llm": f"LLM ({settings.llm.model_path})",
        "classifier": f"Classifier ({settings.classifier.model_name})",
        "embedding": f"Embedding ({settings.embedding.model_name})",
    }

    print("\n  Model Status:")
    print("-" * 55)
    for key, present in status.items():
        icon = "OK" if present else "MISSING"
        print(f"   {icon:>7}  {labels[key]}")
    print("-" * 55)

    missing = sum(1 for v in status.values() if not v)
    if missing == 0:
        print("   All models ready!")
    else:
        print(f"   {missing} model(s) missing")
        print("   Run: python -m src.scripts.init_models")


# =========================================================================
# Main
# =========================================================================


def _download_selected(args: argparse.Namespace) -> int:
    """Download selected models based on CLI arguments.

    Args:
        args: Parsed command line arguments.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    # If no specific flag, download all
    download_all = not (args.llm or args.classifier or args.embedding)

    results = []

    if download_all or args.llm:
        print("\n  LLM (GGUF):")
        results.append(download_llm())

    if download_all or args.classifier:
        print("\n  Intent Classifier:")
        results.append(download_classifier())

    if download_all or args.embedding:
        print("\n  Embedding Model:")
        results.append(download_embedding())

    if all(results):
        print("\n  Model initialization complete!")
        return 0

    failed = sum(1 for r in results if not r)
    print(f"\n  {failed} download(s) failed")
    return 1


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    args = parse_args()
    _print_banner()

    if args.check:
        status = check_models()
        _print_status(status)
        return 0 if all(status.values()) else 1

    return _download_selected(args)


if __name__ == "__main__":
    sys.exit(main())
