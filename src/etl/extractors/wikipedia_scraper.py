"""
Extracteur de films d'horreur depuis Wikipedia.
Scrape les listes de films par année.
"""

import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup, Tag

from src.etl.settings import Settings, WikipediaConfig, settings
from src.etl.utils import setup_logger, CheckpointManager


@dataclass
class FilmCandidate:
    """Candidat film extrait d'une cellule Wikipedia."""

    title: str
    url: str
    director: str = ""


class WikipediaExtractor:
    """
    Extracteur de films d'horreur depuis Wikipedia.

    Scrape les pages "List of horror films of YYYY" pour extraire
    les métadonnées des films (titre, réalisateur, pays, etc.).
    """

    def __init__(self, config_overrides: Optional[dict[str, object]] = None) -> None:
        """
        Initialise l'extracteur Wikipedia.

        Args:
            config_overrides: Dictionnaire de surcharges de configuration
        """
        # Créer une nouvelle instance de Settings avec les surcharges
        if config_overrides:
            # Convertir les clés pour correspondre aux noms de champs de Settings
            override_dict = {f"wikipedia_{k}": v for k, v in config_overrides.items()}
            settings_obj = Settings(**override_dict)
            self.cfg = WikipediaConfig(settings_obj)
        else:
            self.cfg = settings.wikipedia

        # Initialisation des composants
        self.logger = setup_logger("etl.wikipedia")
        self.checkpoint_manager = CheckpointManager()

        # Configuration session HTTP
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.cfg.user_agent,
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate",
            }
        )
        self.session.timeout = self.cfg.request_timeout

        # Statistiques
        self.stats: dict[str, object] = {
            "pages_scraped": 0,
            "requests_made": 0,
            "requests_failed": 0,
            "films_found": 0,
        }

    def extract(
        self,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
        max_films: Optional[int] = None,
        save_checkpoint: Optional[bool] = None,
    ) -> list[dict[str, object]]:
        """
        Extrait les films d'horreur depuis Wikipedia.

        Args:
            start_year: Année de début (incluse). Si None, utilise la valeur de configuration.
            end_year: Année de fin (incluse). Si None, utilise la valeur de configuration.
            max_films: Limite du nombre de films (None = tous). Si None, utilise la valeur de configuration.
            save_checkpoint: Sauvegarder un checkpoint final. Si None, utilise la valeur de configuration.

        Returns:
            Liste de dictionnaires contenant les données des films

        Raises:
            requests.RequestException: Erreur réseau
        """
        # Utiliser les valeurs de la configuration si aucun paramètre n'est fourni
        start_year = start_year or self.cfg.start_year
        end_year = end_year or self.cfg.end_year
        max_films = max_films or self.cfg.max_films
        save_checkpoint = (
            save_checkpoint
            if save_checkpoint is not None
            else self.cfg.save_checkpoints
        )

        self._log_extraction_start(start_year, end_year, max_films)

        # Vérifier checkpoint existant
        checkpoint = self.checkpoint_manager.load("wikipedia_films")
        if checkpoint:
            self.logger.info(
                f"📂 Checkpoint trouvé : {len(checkpoint)} films déjà extraits"
            )
            return checkpoint

        all_films: list[dict[str, object]] = []
        start_time = datetime.now()

        # Scraper chaque année
        for year in range(start_year, end_year + 1):
            if max_films and len(all_films) >= max_films:
                self.logger.info(f"✋ Limite de {max_films} films atteinte")
                break

            films_year = self._scrape_year(year)
            all_films.extend(films_year)

            self.logger.info(
                f"✅ Année {year} : {len(films_year)} films (total: {len(all_films)})"
            )

            # Rate limiting : attendre entre les requêtes
            time.sleep(self.cfg.rate_limit_delay)

        # Limiter au nombre demandé
        if max_films:
            all_films = all_films[:max_films]

        # Statistiques finales
        duration = (datetime.now() - start_time).total_seconds()
        self.stats["films_found"] = len(all_films)

        self._print_stats(duration)

        # Sauvegarder checkpoint
        if save_checkpoint and all_films:
            self.checkpoint_manager.save("wikipedia_final", all_films)
            self.logger.info(f"💾 Checkpoint final sauvegardé : {len(all_films)} films")

        return all_films

    def _log_extraction_start(
        self, start_year: int, end_year: int, max_films: Optional[int]
    ) -> None:
        """Affiche les logs de démarrage de l'extraction."""
        self.logger.info("=" * 80)
        self.logger.info("🌐 DÉMARRAGE EXTRACTION WIKIPEDIA")
        self.logger.info("=" * 80)
        self.logger.info(f"📅 Période : {start_year}-{end_year}")
        self.logger.info(f"🎯 Limite : {max_films or 'Aucune'}")
        self.logger.info("")

    @staticmethod
    def _get_wiki_page_title(year: int) -> str:
        """
        Returns the Wikipedia page title for horror films of a given year (English only).

        Args:
            year: Year to search for

        Returns:
            Wikipedia page title to scrape
        """
        return f"List_of_horror_films_of_{year}"

    def _scrape_year(self, year: int) -> list[dict[str, object]]:
        """
        Scrape les films d'une année donnée.

        Args:
            year: Année à scraper

        Returns:
            Liste des films de cette année
        """
        page_title = self._get_wiki_page_title(year)
        url = f"{self.cfg.base_url}/wiki/{page_title}"

        for attempt in range(1, self.cfg.max_retries + 1):
            try:
                self.stats["requests_made"] = (
                    int(self.stats.get("requests_made", 0)) + 1
                )

                response = self.session.get(url, timeout=self.cfg.request_timeout)
                response.raise_for_status()

                self.stats["pages_scraped"] = (
                    int(self.stats.get("pages_scraped", 0)) + 1
                )

                # Parser le HTML et retourner directement le résultat
                soup = BeautifulSoup(response.content, "html.parser")
                return self._parse_films_table(soup, year)

            except requests.RequestException as e:
                self.stats["requests_failed"] = (
                    int(self.stats.get("requests_failed", 0)) + 1
                )

                if attempt == self.cfg.max_retries:
                    self.logger.error(
                        f"❌ Échec scraping {year} après {self.cfg.max_retries} tentatives : {e}"
                    )
                    return []

                self.logger.warning(
                    f"⚠️ Tentative {attempt}/{self.cfg.max_retries} échouée pour "
                    f"{year}, retry..."
                )
                # Backoff exponentiel
                time.sleep(self.cfg.rate_limit_delay * attempt)

        return []

    def _parse_films_table(
        self, soup: BeautifulSoup, year: int
    ) -> list[dict[str, object]]:
        """
        Parses the horror films list page for a given year (English Wikipedia).

        Args:
            soup: BeautifulSoup HTML object
            year: Year of the films

        Returns:
            List of parsed films
        """
        result = []

        # Find all film tables
        for table in soup.find_all("table", class_="wikitable"):
            films_from_table = self._extract_films_from_table(table, year)
            result.extend(films_from_table)

        if not result:
            self.logger.warning(
                f"⚠️ No films found for {year} in the current page format"
            )

        return result

    def _extract_films_from_table(
        self, table: Tag, year: int
    ) -> list[dict[str, object]]:
        """
        Extrait tous les films d'un tableau Wikipedia.

        Args:
            table: Tag BeautifulSoup du tableau
            year: Année des films

        Returns:
            Liste des films extraits
        """
        extracted_films = []

        # Skip header row (first tr)
        for row in table.find_all("tr")[1:]:
            film_data = self._extract_film_from_row(row, year)
            if film_data:
                extracted_films.append(film_data)

        return extracted_films

    def _extract_film_from_row(
        self, row: Tag, year: int
    ) -> Optional[dict[str, object]]:
        """
        Extrait les données d'un film depuis une ligne de tableau.

        Args:
            row: Tag BeautifulSoup de la ligne
            year: Année du film

        Returns:
            Dictionnaire du film ou None si extraction échoue
        """
        cells = row.find_all(["td", "th"])
        if not cells:
            return None

        # Extraire et valider le candidat film
        candidate = self._extract_film_candidate(cells)
        if not candidate or not self._is_valid_film_title(candidate.title):
            return None

        # Créer les données du film
        return self._create_film_data(candidate, year)

    def _extract_film_candidate(self, cells: list[Tag]) -> Optional[FilmCandidate]:
        """
        Extrait un candidat film depuis les cellules d'une ligne.

        Args:
            cells: Liste des cellules de la ligne

        Returns:
            FilmCandidate ou None si extraction échoue
        """
        if not cells:
            return None

        # Extraire titre et URL depuis la première cellule
        first_cell = cells[0]
        film_link = self._find_film_link(first_cell)

        if not film_link or not film_link.get("title"):
            return None

        title = self._clean_film_title(film_link.get("title", "").strip())
        href = film_link.get("href", "")

        # Extraire le réalisateur depuis la deuxième cellule (si disponible)
        director = ""
        if len(cells) > 1:
            director = self._extract_director(cells[1])

        return FilmCandidate(title=title, url=href, director=director)

    @staticmethod
    def _find_film_link(cell: Tag) -> Optional[Tag]:
        """
        Trouve le lien principal d'un film dans une cellule.

        Args:
            cell: Cellule BeautifulSoup

        Returns:
            Tag du lien ou None
        """
        return cell.find(
            "a",
            href=lambda x: (
                x
                and x.startswith("/wiki/")
                and not x.startswith("/wiki/File:")
                and not x.startswith("/wiki/Category:")
            ),
        )

    @staticmethod
    def _clean_film_title(title: str) -> str:
        """
        Nettoie le titre d'un film.

        Args:
            title: Titre brut

        Returns:
            Titre nettoyé
        """
        # Supprimer " (film)" du titre
        title = title.split(" (film)")[0].strip()
        return title

    @staticmethod
    def _extract_director(cell: Tag) -> str:
        """
        Extrait le nom du réalisateur depuis une cellule.

        Args:
            cell: Cellule BeautifulSoup

        Returns:
            Nom du réalisateur
        """
        text = cell.get_text(strip=True)
        # Supprimer les références [1], [2], etc.
        text = text.split("[")[0].strip()
        return text

    @staticmethod
    def _is_valid_film_title(title: str) -> bool:
        """
        Valide qu'un titre de film est acceptable.

        Args:
            title: Titre à valider

        Returns:
            True si valide, False sinon
        """
        # Titre trop court
        if len(title) < 3:
            return False

        # Titre est juste un nombre (année)
        if title.isdigit():
            return False

        return True

    def _create_film_data(
        self, candidate: FilmCandidate, year: int
    ) -> dict[str, object]:
        """
        Crée le dictionnaire de données d'un film.

        Args:
            candidate: Candidat film
            year: Année du film

        Returns:
            Dictionnaire de données du film
        """
        return {
            "title": candidate.title,
            "year": year,
            "director": candidate.director,
            "source": "wikipedia",
            "scraped_at": datetime.now().isoformat(),
            "url": f"{self.cfg.base_url}{candidate.url}",
        }

    @staticmethod
    def _clean_text(cell: Tag) -> str:
        """
        Nettoie le texte d'une cellule HTML.

        Args:
            cell: Tag BeautifulSoup de la cellule

        Returns:
            Texte nettoyé
        """
        # Récupérer le texte
        text = cell.get_text(strip=True)

        # Supprimer les références [1], [2], etc.
        text = re.sub(r"\[\d+]", "", text)

        # Supprimer les whitespaces multiples
        text = " ".join(text.split())

        return text

    def _print_stats(self, duration: float) -> None:
        """
        Affiche les statistiques d'extraction.

        Args:
            duration: Durée totale en secondes
        """
        self.logger.info("=" * 80)
        self.logger.info("📊 STATISTIQUES EXTRACTION WIKIPEDIA")
        self.logger.info("-" * 80)
        self.logger.info(f"Films extraits       : {self.stats['films_found']}")
        self.logger.info(f"Pages scrapées       : {self.stats['pages_scraped']}")
        self.logger.info(f"Requêtes effectuées  : {self.stats['requests_made']}")
        self.logger.info(f"Requêtes échouées    : {self.stats['requests_failed']}")
        self.logger.info(
            f"Durée totale         : {duration:.2f}s ({duration / 60:.1f} min)"
        )

        if self.stats["films_found"] > 0:
            avg_time = duration / int(self.stats["films_found"])
            self.logger.info(f"Temps moyen par film : {avg_time:.2f}s")

        self.logger.info("=" * 80)


# ============================================================================
# Script de test standalone
# ============================================================================

if __name__ == "__main__":
    """
    Test de l'extracteur Wikipedia.
    Usage: python -m src.etl.extractors.wikipedia_scraper
    """
    print("\n🧪 TEST WIKIPEDIA EXTRACTOR")
    print("=" * 80)

    # Créer l'extracteur avec surcharge de configuration pour les tests
    extractor = WikipediaExtractor(
        config_overrides={
            "start_year": 2022,
            "end_year": 2024,
            "max_films": 50,
            "save_checkpoints": False,
        }
    )

    # Extraire les films avec les paramètres par défaut de l'extracteur
    films = extractor.extract()

    print("=" * 80)
    print(f"\n✅ {len(films)} films extraits")

    if films:
        print("\n🎬 Exemple de films :")
        for film in films[:5]:
            print(
                f"  • {film['title']} ({film['year']}) - Réalisateur: {film.get('director', 'N/A')}"
            )
            print(f"    🔗 {film.get('url', 'URL non disponible')}")

    print("\n" + "=" * 80)
