"""
Extracteur TMDB (The Movie Database) - API REST.
Extrait les films du genre Horror depuis l'API TMDB.
"""

import time
from datetime import datetime
from typing import Optional, Union, TypedDict, Any

import requests
from tqdm import tqdm

from src.etl.config import config
from src.etl.utils import setup_logger, retry_on_error, CheckpointManager


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

    credits: dict[str, list[dict[str, Any]]]
    keywords: dict[str, list[dict[str, Any]]]
    genres: list[dict[str, Union[int, str]]]
    runtime: Optional[int]
    tagline: Optional[str]
    imdb_id: Optional[str]
    production_companies: list[dict[str, Any]]
    production_countries: list[dict[str, Any]]
    spoken_languages: list[dict[str, Any]]
    status: str
    original_language: str
    original_title: str
    budget: int
    revenue: int
    adult: bool
    video: bool
    homepage: Optional[str]


class TMDBExtractor:
    """
    Extracteur de films d'horreur depuis l'API TMDB.

    API Documentation: https://developers.themoviedb.org/3
    Genre Horror ID: 27
    Rate Limit: 40 requêtes / 10 secondes
    """

    # ID du genre Horror dans TMDB
    HORROR_GENRE_ID = 27

    # Limite de requêtes pour respecter rate limit
    REQUESTS_PER_PERIOD = 40
    PERIOD_SECONDS = 10

    # Délai minimum entre requêtes (pour être sûr de ne pas dépasser)
    # 0.25 secondes
    MIN_REQUEST_DELAY = PERIOD_SECONDS / REQUESTS_PER_PERIOD

    def __init__(self) -> None:
        """Initialise l'extracteur TMDB."""
        self.api_key = config.TMDB_API_KEY
        self.base_url = config.TMDB_BASE_URL
        self.image_base_url = config.TMDB_IMAGE_BASE_URL
        self.logger = setup_logger(f"{__name__}.TMDBExtractor")
        self.checkpoint_manager = CheckpointManager()

        # Statistiques d'extraction
        self.stats = {
            "total_movies": 0,
            "total_requests": 0,
            "failed_requests": 0,
            "start_time": None,
            "end_time": None,
        }

        # Validation de la clé API
        if not self.api_key:
            raise ValueError(
                "TMDB_API_KEY manquante dans .env. "
                "Obtenir une clé sur https://www.themoviedb.org/settings/api"
            )

    @retry_on_error(
        max_attempts=3,
        exceptions=(requests.RequestException,),
        wait_min=2,
        wait_max=10,
    )
    def _make_request(
        self, endpoint: str, params: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
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
        url = f"{self.base_url}{endpoint}"

        # Ajouter la clé API aux paramètres
        if params is None:
            params = {}
        params["api_key"] = self.api_key

        # Attendre pour respecter le rate limit
        time.sleep(self.MIN_REQUEST_DELAY)

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            self.stats["total_requests"] += 1
            return response.json()

        except requests.RequestException as req_err:
            self.stats["failed_requests"] += 1
            self.logger.error(f"❌ Erreur requête TMDB {endpoint}: {req_err}")
            raise

    def discover_horror_movies(
        self, start_page: int = 1, max_pages: Optional[int] = None
    ) -> list[dict[str, Any]]:
        """
        Découvre les films d'horreur via l'endpoint /discover/movie.

        Args:
            start_page: Page de départ (défaut: 1)
            max_pages: Nombre maximum de pages à récupérer (None = toutes)

        Returns:
            Liste de dictionnaires contenant les films
        """
        self.logger.info("📡 Démarrage extraction TMDB - Endpoint /discover/movie")
        self.stats["start_time"] = datetime.now()

        all_movies = []
        page = start_page
        total_pages = None

        # Tenter de charger un checkpoint existant
        checkpoint = self.checkpoint_manager.load("tmdb_discover")
        if checkpoint:
            all_movies = checkpoint.get("movies", [])
            page = checkpoint.get("last_page", 0) + 1
            self.logger.info(
                f"📂 Reprise depuis checkpoint : "
                f"{len(all_movies)} films déjà extraits, page {page}"
            )

        while True:
            # Vérifier si on a atteint le nombre max de pages
            if max_pages and page > max_pages:
                self.logger.info(f"✋ Limite de {max_pages} pages atteinte")
                break

            # Vérifier si on a atteint la dernière page
            if total_pages and page > total_pages:
                self.logger.info(f"✅ Toutes les pages extraites ({total_pages} pages)")
                break

            try:
                # Requête vers /discover/movie
                self.logger.debug(f"🔍 Requête page {page}/{total_pages or '?'}")

                response = self._make_request(
                    "/discover/movie",
                    params={
                        "with_genres": self.HORROR_GENRE_ID,
                        "sort_by": "popularity.desc",
                        "page": page,
                        "include_adult": "false",
                        "language": "en-US",
                    },
                )

                # Extraire les métadonnées de pagination
                if total_pages is None:
                    total_pages = min(response.get("total_pages", 500), 500)
                    total_results = response.get("total_results", 0)
                    self.logger.info(
                        f"📊 {total_results:,} films Horror trouvés "
                        f"({total_pages} pages disponibles)"
                    )

                # Ajouter les films de cette page
                page_movies = response.get("results", [])
                all_movies.extend(page_movies)

                self.logger.info(
                    f"✅ Page {page}/{total_pages} : "
                    f"{len(page_movies)} films extraits "
                    f"(total: {len(all_movies):,})"
                )

                # Sauvegarder un checkpoint toutes les 10 pages
                if page % 10 == 0:
                    self.checkpoint_manager.save(
                        "tmdb_discover",
                        {"movies": all_movies, "last_page": page},
                    )
                    self.logger.debug(f"💾 Checkpoint sauvegardé (page {page})")

                page += 1

            except requests.RequestException as req_error:
                self.logger.error(
                    f"❌ Erreur page {page}, abandon après retries: {req_error}"
                )
                # Sauvegarder l'état avant d'abandonner
                self.checkpoint_manager.save(
                    "tmdb_discover",
                    {"movies": all_movies, "last_page": page - 1},
                )
                break

        self.stats["total_movies"] = len(all_movies)
        self.stats["end_time"] = datetime.now()

        return all_movies

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
            f"🔍 Enrichissement de {len(movies_to_enrich):,} films avec détails complets"
        )

        enriched_movies = []

        # Barre de progression
        for enriched_movies in tqdm(
            movies_to_enrich, desc="Enrichissement TMDB", unit="film"
        ):
            movie_id = movie.get("id")

            if not movie_id:
                self.logger.warning("⚠️  Film sans ID, ignoré")
                continue

            try:
                # Requête vers /movie/{id} avec append_to_response
                details = self._make_request(
                    f"/movie/{movie_id}",
                    params={
                        "append_to_response": "credits,keywords",
                        "language": "en-US",
                    },
                )

                # Fusionner les détails avec les données de base
                enriched_movie = {**movie, **details}
                enriched_movies.append(enriched_movie)

            except requests.RequestException as req_error:
                self.logger.warning(
                    f"⚠️  Échec enrichissement film {movie_id} "
                    f"('{movie.get('title', 'Unknown')}'): {req_error}"
                )
                # Garder le film sans enrichissement
                enriched_movies.append(movie)

        self.logger.info(
            f"✅ {len(enriched_movies):,} films enrichis "
            f"({len(enriched_movies) - len(movies_to_enrich)} échecs)"
        )

        return enriched_movies

    def extract(
        self,
        max_pages: Optional[int] = None,
        enrich: bool = True,
        save_checkpoint: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Point d'entrée principal : Extrait les films Horror depuis TMDB.

        Args:
            max_pages: Nombre maximum de pages (None = toutes)
            enrich: Si True, enrichit avec détails complets (plus lent)
            save_checkpoint: Si True, sauvegarde le résultat final

        Returns:
            Liste de films extraits
        """
        self.logger.info("=" * 80)
        self.logger.info("🎬 DÉMARRAGE EXTRACTION TMDB")
        self.logger.info("=" * 80)

        # Étape 1 : Découverte des films Horror
        horror_movies = self.discover_horror_movies(start_page=1, max_pages=max_pages)

        # Étape 2 : Enrichissement (optionnel)
        if enrich and horror_movies:
            horror_movies = self.enrich_movie_details(horror_movies)

        # Étape 3 : Sauvegarde du checkpoint final
        if save_checkpoint:
            self.checkpoint_manager.save("tmdb_final", horror_movies)
            self.logger.info(
                f"💾 Checkpoint final sauvegardé : {len(horror_movies):,} films"
            )

        # Afficher les statistiques
        self._print_stats()

        return horror_movies

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
            avg_time = duration / self.stats["total_movies"]
            self.logger.info(f"Temps moyen par film : {avg_time:.2f}s")

        self.logger.info("=" * 80)


# ============================================================================
# Script d'exécution standalone (pour tests)
# ============================================================================

if __name__ == "__main__":
    """
    Test de l'extracteur TMDB en standalone.
    Usage: python etl/extractors/tmdb_extractor.py
    """
    import sys

    # Configuration du test
    # Limiter à 5 pages pour test rapide (100 films)
    MAX_PAGES_TEST = 5
    # Désactiver enrichissement pour test rapide
    ENRICH_TEST = False

    print("\n🧪 TEST EXTRACTEUR TMDB")
    print(
        f"Configuration : {MAX_PAGES_TEST} pages, enrichissement={'ON' if ENRICH_TEST else 'OFF'}"
    )
    print("-" * 80)

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
            print(f"   Genres: {[g.get('name') for g in movie.get('genres', [])]}")
            print(f"   Synopsis: {movie.get('overview', 'N/A')[:100]}...")

        print(f"\n✅ Test réussi : {len(movies)} films extraits")
        print(
            f"💾 Checkpoint sauvegardé dans : {config.CHECKPOINTS_DIR}/tmdb_final.json"
        )

    except Exception as e:
        print(f"\n❌ Erreur durant le test : {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
