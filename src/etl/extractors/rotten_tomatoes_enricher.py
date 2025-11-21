"""Module d'enrichissement des films via Rotten Tomatoes."""

import asyncio
import json
import random
import re
from typing import Any

from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig
from tenacity import retry, stop_after_attempt, wait_exponential
from unidecode import unidecode

from src.settings import settings
from src.etl.utils import setup_logger


class RottenTomatoesEnricher:
    """Enrichit les données films avec les scores Rotten Tomatoes."""

    def __init__(self) -> None:
        """Initialise l'enrichisseur RT."""

        self.name = "RottenTomatoesEnricher"
        self.logger = setup_logger("etl.rt")
        self.base_url = "https://www.rottentomatoes.com"
        # ✅ Checkpoint centralisé
        self.checkpoint_path = (
            settings.paths.checkpoints_dir / "rotten_tomatoes_processed.json"
        )
        self.processed_films: set[str] = self._load_checkpoint()

    def _load_checkpoint(self) -> set[str]:
        """Charge les films déjà traités depuis le checkpoint."""
        if self.checkpoint_path.exists():
            try:
                with self.checkpoint_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    processed = set(data.get("processed_films", []))
                    self.logger.info(
                        f"✅ Checkpoint RT chargé : {len(processed)} films traités"
                    )

                    return processed
            except json.JSONDecodeError:
                self.logger.error("checkpoint_rt_corrupted")
        return set()

    def _save_checkpoint(self) -> None:
        """Sauvegarde les films traités dans le checkpoint."""
        try:
            # ✅ Créer le répertoire si nécessaire
            self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

            with self.checkpoint_path.open("w", encoding="utf-8") as f:
                json.dump(
                    {
                        "timestamp": asyncio.get_event_loop().time(),
                        "processed_films": list(self.processed_films),
                    },
                    f,
                    indent=2,
                )

            self.logger.info(
                f"✅ Checkpoint RT sauvegardé : {len(self.processed_films)} films traités"
            )

        except OSError as e:
            self.logger.error(f"checkpoint_rt_save_failed: {str(e)}")

    @staticmethod
    def _build_film_url(title: str) -> str | None:
        """
        Construit l'URL RT à partir du titre avec translittération.

        Args:
            title: Titre du film

        Returns:
            URL relative du film, ou None si slug invalide
        """
        if not title or not title.strip():
            return None

        # ✅ Translittération caractères spéciaux → ASCII
        slug = unidecode(title).lower()

        # Supprimer caractères non-alphanumériques
        slug = re.sub(r"[^\w\s-]", "", slug)

        # Remplacer espaces/tirets multiples par underscore
        slug = re.sub(r"[-\s]+", "_", slug)

        # Nettoyer underscores début/fin
        slug = slug.strip("_")

        # ✅ Vérifier slug non vide
        if not slug or slug == "_":
            return None

        return f"/m/{slug}"

    async def _check_film_url(
        self, crawler: AsyncWebCrawler, film_url: str, title: str
    ) -> bool:
        """Vérifie si une URL de film est valide (pas une 404).

        Args:
            crawler: Instance du crawler
            film_url: URL relative du film
            title: Titre du film (pour logging)

        Returns:
            True si la page existe, False sinon
        """
        full_url = f"{self.base_url}{film_url}"
        run_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            page_timeout=30000,
        )

        try:
            await asyncio.sleep(random.uniform(1.0, 3.0))
            result = await crawler.arun(url=full_url, config=run_config)

            if not result.success or len(result.html) <= 10000:
                return False

            return "404 - Not Found" not in result.html

        except (asyncio.TimeoutError, ConnectionError) as e:
            self.logger.error(f"❌ Erreur vérification URL pour {title} : {e}")
            return False

    async def _search_film(
        self, crawler: AsyncWebCrawler, title: str, original_title: str | None = None
    ) -> str | None:
        """Recherche un film avec plusieurs stratégies de fallback.

        Ordre de priorité :
        1. title (titre US/anglais de TMDB) - PRIORITAIRE
        2. title sans "the"
        3. original_title (dernier recours si title échoue)
        4. original_title sans "the"

        Args:
            crawler: Instance du crawler
            title: Titre localisé US/anglais (TMDB "title")
            original_title: Titre original (TMDB "original_title")

        Returns:
            URL relative si trouvée, None sinon
        """
        # Liste ordonnée des variantes à essayer
        title_variants: list[str] = [title]

        # 2. Variante sans "the" du titre US
        if title.lower().startswith("the "):
            title_variants.append(title[4:].strip())

        # 3. Titre original (dernier recours, souvent inutile pour RT)
        if original_title and original_title.lower() != title.lower():
            title_variants.append(original_title)
            if original_title.lower().startswith("the "):
                title_variants.append(original_title[4:].strip())

        # Tester chaque variante
        for idx, variant in enumerate(title_variants, 1):
            film_url = self._build_film_url(variant)

            # ✅ Vérifier slug valide avant tentative
            if not film_url:
                self.logger.warning(f"⚠️ Slug invalide pour '{variant}' (ignoré)")
                continue

            if await self._check_film_url(crawler, film_url, title):
                self.logger.info(
                    f"✅ Film trouvé : {film_url} "
                    f"(tentative {idx}/{len(title_variants)}: '{variant}')"
                )
                return film_url

        self.logger.warning(
            f"❌ Film introuvable après {len(title_variants)} tentatives : {title}"
        )
        return None

    @staticmethod
    def _extract_critics_scores(
        scorecard_data: dict[str, Any], details: dict[str, Any]
    ) -> None:
        """Extrait les scores critiques."""
        if critics := scorecard_data.get("criticsScore"):
            if score := critics.get("score"):
                details["tomatometer_score"] = int(score)
            if certified := critics.get("certified"):
                details["certified_fresh"] = certified
            details["critics_count"] = critics.get("reviewCount", 0)
            details["critics_average_rating"] = critics.get("averageRating")

    @staticmethod
    def _extract_audience_scores(
        scorecard_data: dict[str, Any], details: dict[str, Any]
    ) -> None:
        """Extrait les scores audience."""
        if audience := scorecard_data.get("audienceScore"):
            if score := audience.get("score"):
                details["audience_score"] = int(score)
            details["audience_count"] = audience.get("reviewCount", 0)
            details["audience_average_rating"] = audience.get("averageRating")

    @staticmethod
    def _extract_consensus(soup: BeautifulSoup, details: dict[str, Any]) -> None:
        """Extrait le consensus critique."""
        consensus_elem = soup.select_one("#critics-consensus p")
        if consensus_elem:
            consensus_text = " ".join(consensus_elem.stripped_strings)
            if consensus_text:
                details["critics_consensus"] = consensus_text

    def _process_scorecard_data(
        self, scorecard_data: dict[str, Any], details: dict[str, Any], full_url: str
    ) -> None:
        """Traite les données du scorecard et les ajoute aux détails du film."""
        details["rotten_tomatoes_url"] = full_url

        if scorecard_data.get("scoreboard", {}).get("tomatometerScore"):
            self._extract_critics_scores(scorecard_data, details)
        if scorecard_data.get("criticsScore") or scorecard_data.get("audienceScore"):
            self._extract_audience_scores(scorecard_data, details)

    async def _fetch_film_page(
        self, crawler: AsyncWebCrawler, full_url: str, run_config: CrawlerRunConfig
    ) -> tuple[bool, BeautifulSoup | None, str | None]:
        """Récupère et parse la page du film."""
        soup = None
        script_content = None
        success = False

        try:
            await asyncio.sleep(random.uniform(1.5, 4.0))
            result = await crawler.arun(url=full_url, config=run_config)

            if result.success and result.html:
                soup = BeautifulSoup(result.html, "html.parser")
                script_tag = soup.select_one("script#media-scorecard-json")

                if script_tag and script_tag.string:
                    script_content = script_tag.string.strip()
                    success = True
                else:
                    self.logger.warning(
                        f"⚠️ Script absent/vide pour {full_url}, retry..."
                    )
            else:
                self.logger.warning(f"⚠️ Échec chargement : {full_url}, retry...")

        except (asyncio.TimeoutError, ConnectionError) as e:
            self.logger.error(f"❌ Erreur réseau pour {full_url} : {e}")
        except json.JSONDecodeError as e:
            self.logger.error(f"❌ JSON invalide pour {full_url} : {e}")

        return success, soup if success else None, script_content

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _extract_film_details(
        self, crawler: AsyncWebCrawler, film_url: str
    ) -> dict[str, Any]:
        """Extrait les détails d'un film depuis son JSON embarqué avec retry."""
        full_url = f"{self.base_url}{film_url}"
        run_config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)
        details: dict[str, Any] = {}

        success, soup, script_content = await self._fetch_film_page(
            crawler, full_url, run_config
        )
        if not success or not script_content:
            return {}

        try:
            scorecard_data = json.loads(script_content)
            self._process_scorecard_data(scorecard_data, details, full_url)
            if soup:
                self._extract_consensus(soup, details)
            self.logger.info(f"✓ Détails extraits pour {film_url}")

        except json.JSONDecodeError as e:
            self.logger.error(f"❌ JSON invalide pour {full_url} : {e}")

        return details

    async def enrich_film(
        self, crawler: AsyncWebCrawler, film: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Enrichit un film avec les données Rotten Tomatoes."""
        title = film.get("title", "").strip()
        if not title:
            return None

        original_title = film.get("original_title", "").strip()
        year = str(film.get("year", "")).strip() if film.get("year") else None
        film_id = f"{title}_{year}" if year else title

        if film_id in self.processed_films:
            return film

        result = None
        try:
            # Passer original_title à la recherche
            film_url = await self._search_film(crawler, title, original_title)
            if film_url:
                details = await self._extract_film_details(crawler, film_url)
                if details:
                    result = {**film, **details}
                    self.processed_films.add(film_id)
                    self._save_checkpoint()

                    if "tomatometer_score" in details:
                        tomatometer = details["tomatometer_score"]
                        audience = details.get("audience_score", "N/A")
                        self.logger.info(
                            f"Enrichi : {title} ({year or 'N/A'}) - "
                            f"Tomatometer: {tomatometer}% | Audience: {audience}%"
                        )
        except (asyncio.TimeoutError, ConnectionError) as e:
            self.logger.error(f"Erreur enrichissement {title} : {e}")

        return result

    async def enrich_films_async(
        self, films: list[dict[str, Any]], max_concurrent: int = 3
    ) -> list[dict[str, Any]]:
        """Enrichit une liste de films de manière asynchrone."""
        if not films:
            return []

        self.logger.info(f"Démarrage enrichissement de {len(films)} films")
        enriched_films: list[dict[str, Any]] = []

        async with AsyncWebCrawler() as crawler:
            for i in range(0, len(films), max_concurrent):
                batch = films[i : i + max_concurrent]
                tasks = [self.enrich_film(crawler, film) for film in batch]
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)

                for film, result in zip(batch, batch_results, strict=False):
                    if isinstance(result, Exception):
                        self.logger.error(f"Erreur batch : {result}")
                        enriched_films.append(film)
                    # ✅ Vérifier que result n'est pas None
                    elif result is not None:
                        enriched_films.append(result)
                    else:
                        # Enrichissement échoué, garder le film original
                        enriched_films.append(film)

                if i + max_concurrent < len(films):
                    delay = random.uniform(2.0, 5.0)
                    self.logger.info(f"Pause de {delay:.1f}s entre batches")
                    await asyncio.sleep(delay)

        # ✅ Filtrer les None avant le comptage
        enriched_count = sum(
            1
            for film in enriched_films
            if film is not None and "tomatometer_score" in film
        )

        self.logger.info(
            f"Enrichissement terminé : {enriched_count}/{len(films)} films enrichis"
        )

        return enriched_films


async def enrich_films_with_rt(
    films: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Fonction utilitaire pour enrichir des films avec RT."""
    enricher = RottenTomatoesEnricher()
    return await enricher.enrich_films_async(films)
