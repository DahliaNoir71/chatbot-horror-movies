"""
Tests d'intégration du pipeline ETL complet.
"""

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from src.etl.main import (
    step_1_extract_tmdb,
    step_2_enrich_rt,
    step_3_aggregate,
    run_full_pipeline,
    resume_from_step,
)


@pytest.mark.integration
class TestETLPipelineIntegration:
    """Tests d'intégration du pipeline ETL complet."""

    @pytest.fixture
    def mock_tmdb_movies(self) -> list[dict[str, Any]]:
        """Films TMDB mockés pour intégration."""
        return [
            {
                "id": i,
                "title": f"Horror Film {i}",
                "release_date": f"202{i % 5}-01-01",
                "vote_average": 7.0 + (i % 3),
                "vote_count": 1000 + i * 100,
                "genre_ids": [27],
                "original_language": "en",
            }
            for i in range(10)
        ]

    @pytest.fixture
    def mock_rt_enriched(self, mock_tmdb_movies: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Films enrichis RT mockés."""
        return [
            {**movie, "tomatometer_score": 80 + (i % 20), "critics_consensus": f"Consensus {i}"}
            for i, movie in enumerate(mock_tmdb_movies[:5])
        ] + mock_tmdb_movies[5:]

    @patch("src.etl.main.TMDBExtractor")
    def test_step_1_extract_tmdb(
            self,
            mock_extractor_class: MagicMock,
            mock_tmdb_movies: list[dict[str, Any]]
    ) -> None:
        """Test extraction TMDB."""
        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = mock_tmdb_movies
        mock_extractor_class.return_value = mock_extractor

        result = step_1_extract_tmdb(max_pages=2)

        assert len(result) == 10
        assert result[0]["title"] == "Horror Film 0"
        mock_extractor.extract.assert_called_once_with(
            max_pages=2, enrich=False, save_checkpoint=True
        )

    @pytest.mark.asyncio
    @patch("src.etl.main.RottenTomatoesEnricher")
    async def test_step_2_enrich_rt(
            self,
            mock_enricher_class: MagicMock,
            mock_tmdb_movies: list[dict[str, Any]],
            mock_rt_enriched: list[dict[str, Any]]
    ) -> None:
        """Test enrichissement Rotten Tomatoes."""
        mock_enricher = MagicMock()
        mock_enricher.enrich_films_async = AsyncMock(return_value=mock_rt_enriched)
        mock_enricher_class.return_value = mock_enricher

        result = await step_2_enrich_rt(mock_tmdb_movies)

        assert len(result) == 10
        assert sum(1 for f in result if "tomatometer_score" in f) == 5
        mock_enricher.enrich_films_async.assert_called_once()

    @patch("src.etl.main.DataAggregator")
    def test_step_3_aggregate(
            self,
            mock_aggregator_class: MagicMock,
            mock_tmdb_movies: list[dict[str, Any]],
            mock_rt_enriched: list[dict[str, Any]]
    ) -> None:
        """Test agrégation des données."""
        mock_aggregator = MagicMock()
        aggregated = [
            {**movie, "tmdb_id": movie["id"], "year": 2020 + i}
            for i, movie in enumerate(mock_tmdb_movies[:8])
        ]
        mock_aggregator.extract.return_value = aggregated
        mock_aggregator_class.return_value = mock_aggregator

        result = step_3_aggregate(mock_tmdb_movies, mock_rt_enriched)

        assert len(result) == 8
        assert result[0]["tmdb_id"] == 0

    @pytest.mark.asyncio
    @patch("src.etl.main.step_1_extract_tmdb")
    @patch("src.etl.main.step_2_enrich_rt")
    @patch("src.etl.main.step_3_aggregate")
    @patch("src.etl.main.checkpoint_manager")
    async def test_run_full_pipeline(
            self,
            mock_checkpoint_manager: MagicMock,
            mock_step_3: MagicMock,
            mock_step_2: AsyncMock,
            mock_step_1: MagicMock,
            mock_tmdb_movies: list[dict[str, Any]],
            mock_rt_enriched: list[dict[str, Any]]
    ) -> None:
        """Test exécution complète du pipeline."""
        mock_step_1.return_value = mock_tmdb_movies
        mock_step_2.return_value = mock_rt_enriched
        mock_step_3.return_value = [
            {**movie, "tmdb_id": movie["id"], "year": 2020}
            for movie in mock_tmdb_movies[:8]
        ]
        mock_checkpoint_manager.save.return_value = Path("/tmp/checkpoint.json")

        result = await run_full_pipeline(max_pages=2)

        assert len(result) == 8
        mock_step_1.assert_called_once_with(2)
        mock_step_2.assert_called_once_with(mock_tmdb_movies)
        mock_step_3.assert_called_once()
        assert mock_checkpoint_manager.save.call_count == 3

    @pytest.mark.asyncio
    @patch("src.etl.main.step_2_enrich_rt")
    @patch("src.etl.main.step_3_aggregate")
    @patch("src.etl.main.checkpoint_manager")
    async def test_resume_from_step_2(
            self,
            mock_checkpoint_manager: MagicMock,
            mock_step_3: MagicMock,
            mock_step_2: AsyncMock,
            mock_tmdb_movies: list[dict[str, Any]],
            mock_rt_enriched: list[dict[str, Any]]
    ) -> None:
        """Test reprise à partir de l'étape 2."""
        mock_checkpoint_manager.load.side_effect = [mock_tmdb_movies, None, None]
        mock_step_2.return_value = mock_rt_enriched
        mock_step_3.return_value = [
            {**movie, "tmdb_id": movie["id"], "year": 2020}
            for movie in mock_tmdb_movies[:8]
        ]

        await resume_from_step(2, max_pages=2)

        mock_step_2.assert_called_once_with(mock_tmdb_movies)
        mock_step_3.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.etl.main.step_1_extract_tmdb")
    @patch("src.etl.main.step_2_enrich_rt")
    @patch("src.etl.main.step_3_aggregate")
    @patch("src.etl.main.checkpoint_manager")
    async def test_checkpoint_persistence_between_steps(
            self,
            mock_checkpoint_manager: MagicMock,
            mock_step_3: MagicMock,
            mock_step_2: AsyncMock,
            mock_step_1: MagicMock,
            mock_tmdb_movies: list[dict[str, Any]],
            tmp_path: Path,
    ) -> None:
        """Test persistance checkpoints entre étapes."""
        # Setup mocks
        mock_step_1.return_value = mock_tmdb_movies
        mock_step_2.return_value = mock_tmdb_movies
        mock_step_3.return_value = mock_tmdb_movies[:8]

        # Create a real checkpoint manager for testing
        test_checkpoint_dir = tmp_path / "checkpoints"
        test_checkpoint_dir.mkdir(exist_ok=True)

        # Configure the mock checkpoint manager to use our test directory
        mock_checkpoint_manager.checkpoint_dir = test_checkpoint_dir

        # Create real checkpoints when save is called
        def mock_save(name: str, data: list[dict[str, Any]]) -> Path:
            """
            Mocked save function for CheckpointManager.

            This function takes a name and a list of dictionaries as arguments and saves the list
            to a file with that name in the test checkpoint directory. It returns the path to the
            saved file.

            :param name: Name of the checkpoint to save
            :param data: List of dictionaries to save
            :return: Path to the saved checkpoint
            """
            filename = f"{name}.json"
            path = test_checkpoint_dir / filename
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({"data": data}, f)
            return path

        mock_checkpoint_manager.save.side_effect = mock_save

        # Mock load to return our test data
        def mock_load(name: str) -> list[dict[str, Any]] | None:
            """
            Mocked load function for CheckpointManager.

            This function is used to mock the load behavior of CheckpointManager.
            It takes a name as an argument and returns the data associated with that name
            from the test checkpoint directory. If no file with that name exists, it returns None.

            Parameters:
                name (str): The name of the checkpoint to load.

            Returns:
                list[dict[str, Any]] | None: The data associated with the given name, or None if no file exists.
            """
            filename = f"{name}.json"
            path = test_checkpoint_dir / filename
            if not path.exists():
                return None
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                return json.loads(content)['data']

        mock_checkpoint_manager.load.side_effect = mock_load

        # Mock the _log_pipeline_stats function to avoid the coroutine error
        with patch('src.etl.main._log_pipeline_stats') as mock_log_stats:
            # Run the pipeline
            await run_full_pipeline(max_pages=1)

            # Verify save was called with expected arguments
            assert mock_checkpoint_manager.save.call_count >= 2

            # Get the save calls and extract the filenames (1st argument)
            save_calls = mock_checkpoint_manager.save.call_args_list
            # call.args[0] is the name
            saved_names = [call.args[0] for call in save_calls]

            # Verify the expected checkpoints were saved
            assert any('pipeline_step1_tmdb' in name for name in saved_names), \
                f"Expected 'pipeline_step1_tmdb' in saved names, got {saved_names}"
            assert any('pipeline_step2_rt' in name for name in saved_names), \
                f"Expected 'pipeline_step2_rt' in saved names, got {saved_names}"

            # Verify the final checkpoint was saved
            assert any('pipeline_final' in name for name in saved_names), \
                f"Expected 'pipeline_final' in saved names, got {saved_names}"

            # Verify the log was called with the correct checkpoint path
            assert mock_log_stats.called, "_log_pipeline_stats was not called"
            log_args, _ = mock_log_stats.call_args
            assert len(log_args) >= 3, f"Expected at least 3 arguments, got {len(log_args)}"
            assert 'pipeline_final' in str(log_args[2]), \
                f"Expected 'pipeline_final' in log args, got {log_args[2] if len(log_args) > 2
                else 'not enough arguments'}"

    @patch("src.etl.main.step_1_extract_tmdb")
    @patch("src.etl.main.step_2_enrich_rt")
    @patch("src.etl.main.step_3_aggregate")
    @patch("src.etl.main.checkpoint_manager")
    @patch("src.etl.main.datetime")
    async def test_pipeline_stats_logging(
            self,
            mock_datetime: MagicMock,
            mock_checkpoint_manager: MagicMock,
            mock_step_3: MagicMock,
            mock_step_2: AsyncMock,
            mock_step_1: MagicMock,
            mock_tmdb_movies: list[dict[str, Any]],
            caplog: pytest.LogCaptureFixture,
            tmp_path: Path
    ) -> None:
        """Test logs statistiques pipeline."""
        # Mock datetime to control the test environment
        from datetime import datetime, timedelta
        fixed_time = datetime(2025, 1, 1, 12, 0, 0)

        # Create a list of return values for datetime.now()
        # We need at least 3 calls: start time, final checkpoint name, and duration calculation
        mock_datetime.now.side_effect = [
            fixed_time,
            fixed_time,
            fixed_time + timedelta(seconds=1),
            fixed_time + timedelta(seconds=1)
        ]

        # Setup mocks
        mock_step_1.return_value = mock_tmdb_movies
        mock_step_2.return_value = mock_tmdb_movies
        mock_step_3.return_value = mock_tmdb_movies[:8]

        # Create a real checkpoint file
        checkpoint_file = tmp_path / "checkpoint.json"
        checkpoint_file.write_text('{"data": [], "timestamp": "2025-01-01T12:00:00"}', encoding="utf-8")
        mock_checkpoint_manager.save.return_value = checkpoint_file

        # Run with caplog to capture logs
        with caplog.at_level("INFO"):
            await run_full_pipeline(max_pages=1)

        # Check log messages
        log_messages = caplog.text

        # Verify critical log messages are present
        assert "DÉMARRAGE PIPELINE ETL" in log_messages
        assert "Films finaux         : 8" in log_messages
        assert "Durée totale" in log_messages
        assert "Checkpoint           : checkpoint.json" in log_messages
