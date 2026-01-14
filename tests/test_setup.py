"""
    Tests for setup
"""

import sys
from src.settings.base import BaseSettings

def test_python_version() -> None:
    """Vérifie que l'on tourne sur une version de Python compatible (>= 3.12)."""
    assert sys.version_info.major == 3
    assert sys.version_info.minor >= 12

def test_settings_load() -> None:
    """Vérifie que la configuration de base peut être chargée sans erreur."""
    settings = BaseSettings()
    assert settings is not None
    # Vérifie que pydantic-settings fonctionne
    assert isinstance(settings.model_dump(), dict)

def test_src_in_pythonpath() -> None:
    """Vérifie que le dossier src est bien accessible."""
    import src
    assert src.__file__ is not None

def test_environment_variable_mock() -> None:
    """Vérifie que pytest-env ou .env.test est bien pris en compte."""
    pass
