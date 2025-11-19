"""
Extracteur TMDB (The Movie Database) - API REST.
Extrait les films du genre Horror depuis l'API TMDB avec support period batching.
"""

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Union, TypedDict

import requests
from tqdm import tqdm

from src.etl.settings import settings
from src.etl.utils import setup_logger, CheckpointManager


# Type definitions for TMDB API responses
class MovieBase(TypedDict, total=False):
    """Base movie structure from TMDB API."""

    id: int
    title: str
    overview: Optional[str]
    release_date: Optional[str]
    vote_average: float
    poster_path: Optional[str]
    backdrop_path: Optional[str]
    genre_ids: list[int]
    popularity: float
    vote_count: int


class MovieDetails(MovieBase):
    """Extended movie structure with additional details from TMDB API."""

    credits: dict[str, list[dict[str, object]]]
    keywords: dict[str, list[dict[str, object]]]
    genres: list[dict[str, Union[int, str]]]
    runtime: Optional[int]
    tagline: Optional[str]
    imdb_id: Optional[str]
    production_companies: list[dict[str, object]]
    production_countries: list[dict[str, object]]
    spoken_languages: list[dict[str, object]]
    status: str
    original_language: str
    original_title: str
    budget: int
    revenue: int
    adult: bool
    video: bool
    homepage: Optional[str]


@dataclass
class ExtractionState:
    """État de l'extraction en cours."""

    all_movies: list[dict[str, object]]
    current_page: int
    total_pages: Optional[int]
    max_pages: Optional[int]


class TMDBExtractor:
    """
    Extracteur de films d'horreur depuis l'API TMDB.

    API Documentation: https://developers.themoviedb.org/3
    Genre Horror ID: 27
    Rate Limit: 40 requêtes / 10 secondes

    Modes d'extraction:
    - Standard: Limité à max_pages (défaut 500 pages = 10,000 films)
    - Period batching: Division par périodes pour extraction exhaustive
    """

    def __init__(self, config_overrides: Optional[dict[str, object]] = None) -> None:
        """
        Initialise l'extracteur TMDB avec la configuration.

        Args:
            config_overrides: Dictionnaire de surcharges de configuration
        """
        # Configuration
        self.cfg = settings.tmdb

        # Create a session for making requests
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

        # Configuration de l'API avec surcharges
        config_keys = [
            "api_key",
            "base_url",
            "image_base_url",
            "language",
            "include_adult",
            "requests_per_period",
            "period_seconds",
            "default_max_pages",
            "year_min",
            "year_max",
            "years_per_batch",
            "use_period_batching",
        ]

        # Initialize config with values from settings
        config = {
            key: getattr(self.cfg, key) for key in config_keys if hasattr(self.cfg, key)
        }

        # Apply overrides if provided
        if config_overrides:
            for key, value in config_overrides.items():
                if key in config_keys:
                    config[key] = value

        # Set instance attributes
        for key, value in config.items():
            if not hasattr(type(self), key):
                setattr(self, key, value)

        # Initialisation des composants
        self.logger = setup_logger("etl.tmdb")
        self.checkpoint_manager = CheckpointManager()

        # Validation de la clé API
        if not self.api_key:
            raise ValueError(
                "TMDB_API_KEY manquante dans .env. "
                "Obtenir une clé sur https://www.themoviedb.org/settings/api"
            )

        # Statistiques d'extraction
        self.stats: dict[str, object] = {
            "total_movies": 0,
            "total_requests": 0,
            "failed_requests": 0,
            "start_time": None,
            "end_time": None,
        }

    @property
    def min_request_delay(self) -> float:
        """Délai minimum entre les requêtes pour respecter les limites de l'API."""
        return self.cfg.min_request_delay

    def _check_rate_limit(
        self, response_headers: "requests.structures.CaseInsensitiveDict[str, str]"
    ) -> None:
        """Vérifie les en-têtes de taux limite et émet un avertissement si nécessaire."""
        if "X-RateLimit-Remaining" not in response_headers:
            return

        remaining = int(response_headers.get("X-RateLimit-Remaining", 0))
        if remaining < 10:
            self.logger.warning(
                f"Attention: Il ne reste que {remaining} requêtes avant dépassement du quota TMDB"
            )

    def _prepare_request_params(
        self, params: Optional[dict[str, object]]
    ) -> dict[str, object]:
        """Prépare les paramètres de la requête avec les valeurs par défaut."""
        return {
            "api_key": self.api_key,
            "language": self.language,
            "include_adult": str(self.include_adult).lower(),
            **(params or {}),
        }

    def _make_request(
        self, endpoint: str, params: Optional[dict[str, object]] = None
    ) -> dict[str, object]:
        """
        Effectue une requête GET vers l'API TMDB avec retry automatique.

        Args:
            endpoint: Endpoint de l'API (ex: '/discover/movie')
            params: Paramètres de la requête (optionnel)

        Returns:
            Réponse JSON de l'API

        Raises:
            requests.RequestException: Si la requête échoue après tous les retries
        """
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        params = self._prepare_request_params(params)

        time.sleep(self.min_request_delay)

        try:
            self.logger.info(f"Requête TMDB: {endpoint}")
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()

            self.stats["total_requests"] = int(self.stats.get("total_requests", 0)) + 1
            self._check_rate_limit(response.headers)
            return response.json()

        except requests.RequestException as req_err:
            self.stats["failed_requests"] = (
                int(self.stats.get("failed_requests", 0)) + 1
            )
            self.logger.error(f"❌ Erreur requête TMDB {endpoint}: {req_err}")
            raise

    def _initialize_extraction(self, max_pages: Optional[int]) -> Optional[int]:
        """Initialise l'extraction avec logging et stats."""
        self.logger.info("📡 DÉMARRAGE EXTRACTION TMDB - Endpoint /discover/movie")
        self.stats["start_time"] = datetime.now()

        # max_pages ignoré si period batching actif
        if self.cfg.use_period_batching:
            self.logger.info("Mode period batching : max_pages ignoré")
            return None

        if max_pages is None and hasattr(self.cfg, "default_max_pages"):
            max_pages = self.cfg.default_max_pages
            self.logger.info(
                f"Utilisation de la limite de pages par défaut : {max_pages}"
            )

        return max_pages

    def _load_checkpoint_data(self) -> tuple[list[dict[str, object]], int]:
        """Charge les données depuis un checkpoint existant."""
        checkpoint = self.checkpoint_manager.load("tmdb_discover")

        if checkpoint:
            checkpoint_movies = checkpoint.get("movies", [])
            page = checkpoint.get("last_page", 0) + 1
            self.logger.info(
                f"📂 Reprise depuis checkpoint : "
                f"{len(checkpoint_movies)} films déjà extraits, page {page}"
            )
            return checkpoint_movies, page

        return [], 1

    @staticmethod
    def _should_stop_extraction(state: ExtractionState) -> tuple[bool, Optional[str]]:
        """
        Vérifie si l'extraction doit s'arrêter.

        Returns:
            (should_stop, reason) - True si arrêt nécessaire, avec raison
        """
        if state.max_pages and state.current_page > state.max_pages:
            return True, f"✋ Limite de {state.max_pages} pages atteinte"

        if state.total_pages and state.current_page > state.total_pages:
            return True, f"✅ Toutes les pages extraites ({state.total_pages} pages)"

        return False, None

    def _fetch_page(
        self, page: int, year_min: int | None = None, year_max: int | None = None
    ) -> dict[str, object]:
        """
        Récupère une page de films depuis l'API TMDB.

        Args:
            page: Numéro de la page à récupérer
            year_min: Année minimum (optionnel)
            year_max: Année maximum (optionnel)

        Returns:
            Réponse JSON de l'API
        """
        self.logger.info(f"🔍 Requête page {page}")

        params: dict[str, object] = {
            "with_genres": self.cfg.horror_genre_id,
            "sort_by": "popularity.desc",
            "page": page,
            "include_adult": "false",
            "language": self.language,
            # Exclut courts-métrages
            "with_runtime.gte": 40,
        }

        # Ajoute filtres temporels si fournis
        if year_min:
            params["primary_release_date.gte"] = f"{year_min}-01-01"
        if year_max:
            params["primary_release_date.lte"] = f"{year_max}-12-31"

        return self._make_request("/discover/movie", params=params)

    def _extract_pagination_metadata(
        self, response: dict[str, object], state: ExtractionState
    ) -> None:
        """
        Extrait et log les métadonnées de pagination.

        Args:
            response: Réponse de l'API
            state: État d'extraction (modifié in-place)
        """
        if state.total_pages is None:
            state.total_pages = min(response.get("total_pages", 500), 500)
            total_results = response.get("total_results", 0)
            self.logger.info(
                f"📊 {total_results:,} films Horror trouvés "
                f"({state.total_pages} pages disponibles)"
            )

    def _process_page_movies(
        self, response: dict[str, object], state: ExtractionState
    ) -> None:
        """
        Traite les films d'une page et met à jour l'état.

        Args:
            response: Réponse de l'API
            state: État d'extraction (modifié in-place)
        """
        page_movies = response.get("results", [])
        state.all_movies.extend(page_movies)

        self.logger.info(
            f"✅ Page {state.current_page}/{state.total_pages or '?'} : "
            f"{len(page_movies)} films extraits "
            f"(total: {len(state.all_movies):,})"
        )

    def _save_checkpoint_if_needed(self, state: ExtractionState) -> None:
        """Sauvegarde un checkpoint tous les N pages."""
        if state.current_page % self.cfg.checkpoint_save_interval == 0:
            self.checkpoint_manager.save(
                "tmdb_discover",
                {"movies": state.all_movies, "last_page": state.current_page},
            )
            self.logger.info(f"💾 Checkpoint sauvegardé (page {state.current_page})")

    def _handle_extraction_error(
        self, error: requests.RequestException, state: ExtractionState
    ) -> None:
        """Gère les erreurs d'extraction et sauvegarde l'état."""
        self.logger.error(
            f"❌ Erreur page {state.current_page}, abandon après retries: {error}"
        )

        # Sauvegarder l'état avant d'abandonner
        self.checkpoint_manager.save(
            "tmdb_discover",
            {"movies": state.all_movies, "last_page": state.current_page - 1},
        )

    def _finalize_extraction(self, state: ExtractionState) -> list[dict[str, object]]:
        """Finalise l'extraction et met à jour les stats."""
        self.stats["total_movies"] = len(state.all_movies)
        self.stats["end_time"] = datetime.now()
        return state.all_movies

    def discover_horror_movies(
        self, max_pages: Optional[int] = None
    ) -> list[dict[str, object]]:
        """
        Découvre les films d'horreur via l'endpoint /discover/movie.

        Si use_period_batching=true : Extraction par périodes pour contourner limite 500 pages
        Sinon : Extraction standard limitée à max_pages

        Args:
            max_pages: Nombre maximum de pages à récupérer (None = toutes)

        Returns:
            Liste de dictionnaires contenant les films
        """
        # Initialisation
        max_pages = self._initialize_extraction(max_pages)

        self.logger.info(
            f"Critères extraction - Genre: {self.cfg.horror_genre_id}, "
            f"Années: {self.cfg.year_min}-{self.cfg.year_max}, "
            f"Max pages: {max_pages}, Period batching: {self.cfg.use_period_batching}"
        )

        # Choix de la stratégie
        if self.cfg.use_period_batching:
            return self._discover_by_periods()
        else:
            return self._discover_standard(max_pages)

    def _discover_standard(self, max_pages: int | None) -> list[dict[str, object]]:
        """Extraction standard (mode actuel)."""
        all_movies, page = self._load_checkpoint_data()

        # Créer l'état d'extraction
        state = ExtractionState(
            all_movies=all_movies,
            current_page=page,
            total_pages=None,
            max_pages=max_pages,
        )

        # Boucle principale d'extraction
        while True:
            # Vérifier les conditions d'arrêt
            should_stop, reason = self._should_stop_extraction(state)
            if should_stop:
                self.logger.info(reason)
                break

            try:
                # Récupérer une page avec filtres temporels
                response = self._fetch_page(
                    state.current_page, self.cfg.year_min, self.cfg.year_max
                )

                # Extraire les métadonnées (première page uniquement)
                self._extract_pagination_metadata(response, state)

                # Traiter les films de la page
                self._process_page_movies(response, state)

                # Sauvegarder checkpoint si nécessaire
                self._save_checkpoint_if_needed(state)

                # Page suivante
                state.current_page += 1

            except requests.RequestException as req_error:
                self._handle_extraction_error(req_error, state)
                break

        return self._finalize_extraction(state)

    def _discover_by_periods(self) -> list[dict[str, object]]:
        """Extraction exhaustive par périodes."""
        all_movies: list[dict[str, object]] = []

        # Génère les périodes
        for start_year in range(
            self.cfg.year_min, self.cfg.year_max + 1, self.cfg.years_per_batch
        ):
            end_year = min(start_year + self.cfg.years_per_batch - 1, self.cfg.year_max)

            self.logger.info(f"📅 Période {start_year}-{end_year}")

            # Extraction pour cette période
            period_movies = self._extract_period(start_year, end_year)
            all_movies.extend(period_movies)

            self.logger.info(
                f"✅ Période {start_year}-{end_year} : {len(period_movies)} films "
                f"(Total cumulé : {len(all_movies):,})"
            )

        return all_movies

    def _extract_period(self, year_min: int, year_max: int) -> list[dict[str, object]]:
        """Extrait tous les films d'une période donnée."""
        period_movies: list[dict[str, object]] = []
        page = 1

        while True:
            try:
                response = self._fetch_page(page, year_min, year_max)

                # Métadonnées première page
                if page == 1:
                    total_pages = min(response.get("total_pages", 500), 500)
                    total_results = response.get("total_results", 0)
                    self.logger.info(
                        f"   {total_results:,} films trouvés ({total_pages} pages)"
                    )

                # Récupérer films
                page_movies = response.get("results", [])
                if not page_movies:
                    break

                period_movies.extend(page_movies)

                # Arrêt si dernière page
                if page >= response.get("total_pages", 1):
                    break

                page += 1

            except requests.RequestException as e:
                self.logger.warning(f"⚠️ Erreur page {page} : {e}")
                break

        return period_movies

    def enrich_movie_details(
        self, movies_to_enrich: list[MovieBase]
    ) -> list[Union[MovieBase, MovieDetails]]:
        """
        Enrichit chaque film avec des détails supplémentaires.
        Appelle /movie/{id}?append_to_response=credits,keywords

        Args:
            movies_to_enrich: Liste de films basiques (depuis /discover)

        Returns:
            Liste de films enrichis avec cast, réalisateurs, etc.
        """
        self.logger.info(
            f"🔎 Enrichissement de {len(movies_to_enrich):,} films avec détails complets"
        )

        enriched_movies = []

        # Barre de progression
        for enrich_movie in tqdm(
            movies_to_enrich, desc="Enrichissement TMDB", unit="film"
        ):
            movie_id = enrich_movie.get("id")

            if not movie_id:
                self.logger.warning("⚠️ Film sans ID, ignoré")
                continue

            try:
                # Requête vers /movie/{id} avec append_to_response
                details = self._make_request(
                    f"/movie/{movie_id}",
                    params={
                        "append_to_response": "credits,keywords",
                        "language": self.language,
                    },
                )

                # Fusionner les détails avec les données de base
                enriched_movie = {**enrich_movie, **details}
                enriched_movies.append(enriched_movie)

            except requests.RequestException as req_error:
                self.logger.warning(
                    f"⚠️ Échec enrichissement film {movie_id} "
                    f"('{enrich_movie.get('title', 'Unknown')}'): {req_error}"
                )
                # Garder le film sans enrichissement
                enriched_movies.append(enrich_movie)

        self.logger.info(
            f"✅ {len(enriched_movies):,} films enrichis "
            f"({len(movies_to_enrich) - len(enriched_movies)} échecs)"
        )

        return enriched_movies

    def extract(
        self,
        max_pages: Optional[int] = None,
        enrich: Optional[bool] = None,
        save_checkpoint: Optional[bool] = None,
    ) -> list[dict[str, object]]:
        """
        Point d'entrée principal : Extrait les films Horror depuis TMDB.

        Args:
            max_pages: Nombre maximum de pages (None = toutes)
            enrich: Si True, enrichit avec détails complets (plus lent).
                   Si None, utilise la valeur de la configuration.
            save_checkpoint: Si True, sauvegarde le résultat final.
                           Si None, utilise la valeur de la configuration.
        Returns:
            Liste de films extraits
        """
        # Utiliser les valeurs de la configuration si non spécifiées
        if enrich is None:
            enrich = self.cfg.enrich_movies
        if save_checkpoint is None:
            save_checkpoint = self.cfg.save_checkpoints

        self.logger.info("=" * 80)
        self.logger.info("🎬 DÉMARRAGE EXTRACTION TMDB")
        self.logger.info("=" * 80)
        self.logger.info(
            f"Configuration: enrich={enrich}, save_checkpoint={save_checkpoint}"
        )

        try:
            # Étape 1 : Découverte des films Horror
            horror_movies = self.discover_horror_movies(max_pages=max_pages)

            # Étape 2 : Enrichissement (optionnel)
            if enrich and horror_movies:
                self.logger.info("\n🔄 Début de l'enrichissement des films...")
                horror_movies = self.enrich_movie_details(horror_movies)

            # Étape 3 : Sauvegarde du checkpoint final
            if save_checkpoint and horror_movies:
                checkpoint_name = (
                    f"tmdb_movies_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                )
                self.checkpoint_manager.save(checkpoint_name, horror_movies)
                self.logger.info(
                    f"💾 Checkpoint final sauvegardé : "
                    f"{len(horror_movies):,} films dans {checkpoint_name}"
                )

            # Afficher les statistiques
            self._print_stats()

            return horror_movies

        except Exception as enrich_err:
            self.logger.error(
                f"❌ Erreur lors de l'extraction TMDB: {enrich_err}", exc_info=True
            )
            raise

    def _print_stats(self) -> None:
        """Affiche les statistiques d'extraction."""
        if not self.stats["start_time"] or not self.stats["end_time"]:
            return

        duration = (self.stats["end_time"] - self.stats["start_time"]).total_seconds()

        self.logger.info("=" * 80)
        self.logger.info("📊 STATISTIQUES EXTRACTION TMDB")
        self.logger.info("-" * 80)
        self.logger.info(f"Films extraits       : {self.stats['total_movies']:,}")
        self.logger.info(f"Requêtes effectuées  : {self.stats['total_requests']:,}")
        self.logger.info(f"Requêtes échouées    : {self.stats['failed_requests']:,}")
        self.logger.info(
            f"Durée totale         : {duration:.2f}s ({duration / 60:.1f} min)"
        )

        if self.stats["total_movies"] > 0:
            avg_time = duration / int(self.stats["total_movies"])
            self.logger.info(f"Temps moyen par film : {avg_time:.2f}s")

        self.logger.info("=" * 80)


# ============================================================================
# Script d'exécution standalone (pour tests)
# ============================================================================

if __name__ == "__main__":
    """
    Test de l'extracteur TMDB en standalone.
    Usage: python src/etl/extractors/tmdb_extractor.py
    """
    import sys
    from pathlib import Path

    # Configuration du test
    MAX_PAGES_TEST = 5
    ENRICH_TEST = False

    print("\n🧪 TEST EXTRACTEUR TMDB")
    print(
        f"Configuration : {MAX_PAGES_TEST} pages, enrichissement={'ON' if ENRICH_TEST else 'OFF'}"
    )
    print("-" * 80)

    # Afficher les chemins de sauvegarde
    print("\n📂 Répertoires de sauvegarde :")
    print(f"   Working directory : {Path.cwd().absolute()}")
    print(f"   Checkpoints       : {settings.paths.checkpoints_dir.absolute()}")
    print(f"   Logs              : {settings.paths.logs_dir.absolute()}")
    print()

    try:
        # Créer l'extracteur
        extractor = TMDBExtractor()

        # Lancer l'extraction
        movies = extractor.extract(
            max_pages=MAX_PAGES_TEST,
            enrich=ENRICH_TEST,
            save_checkpoint=True,
        )

        # Afficher un échantillon
        print("\n📋 ÉCHANTILLON DES RÉSULTATS")
        print("-" * 80)
        for i, movie in enumerate(movies[:3], 1):
            print(
                f"\n{i}. {movie.get('title', 'Unknown')} ({movie.get('release_date', 'N/A')[:4]})"
            )
            print(f"   Note: {movie.get('vote_average', 0)}/10")
            print(f"   Synopsis: {movie.get('overview', 'N/A')[:100]}...")

        print(f"\n✅ Test réussi : {len(movies)} films extraits")

        # Vérifier que le fichier a été créé
        checkpoint_files = list(
            settings.paths.checkpoints_dir.glob("tmdb_movies_*.json")
        )
        if checkpoint_files:
            latest_checkpoint = max(checkpoint_files, key=lambda p: p.stat().st_mtime)
            file_size = latest_checkpoint.stat().st_size
            print(
                f"📄 Checkpoint créé : {latest_checkpoint.name} "
                f"({file_size:,} octets / {file_size / 1024:.1f} KB)"
            )
        else:
            print("⚠️ ATTENTION : Aucun fichier checkpoint trouvé !")

    except Exception as e:
        print(f"\n❌ Erreur durant le test : {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
