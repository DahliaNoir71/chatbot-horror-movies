"""YouTube video extractor.

Orchestrates extraction of videos from YouTube channels
and playlists with transcript support.
"""

from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any, TypedDict

from src.etl.extractors.base import BaseExtractor
from src.etl.extractors.youtube.client import (
    YouTubeAPIError,
    YouTubeClient,
    YouTubeNotFoundError,
    YouTubeQuotaExceededError,
)
from src.etl.extractors.youtube.normalizer import YouTubeNormalizer
from src.etl.extractors.youtube.transcript import TranscriptExtractor, TranscriptResult
from src.etl.types import ETLResult, NormalizedVideoData
from src.settings import settings


class VideoBundle(TypedDict):
    """Bundle of video data with optional transcript."""

    video: NormalizedVideoData
    transcript: TranscriptResult | None
    source_type: str
    source_id: str


class ExtractOptions(TypedDict, total=False):
    """Options for extract method."""

    extract_transcripts: bool
    max_videos: int
    resume: bool


class YouTubeExtractor(BaseExtractor):
    """Extracts videos from YouTube channels and playlists.

    Supports channel handles and playlist IDs extraction,
    with optional transcript fetching.

    Attributes:
        client: YouTube API client.
        normalizer: Data normalizer.
        transcript_extractor: Transcript extraction handler.
    """

    name = "youtube"

    _ERR_CLIENT_NOT_INITIALIZED = "Client not initialized"
    _ERR_NO_SOURCES = "No channels or playlists configured"

    def __init__(self) -> None:
        """Initialize YouTube extractor."""
        super().__init__()
        self._client: YouTubeClient | None = None
        self._normalizer = YouTubeNormalizer()
        self._transcript_extractor = TranscriptExtractor()
        self._checkpoint_dir = Path("data/checkpoints")

    # -------------------------------------------------------------------------
    # Main Extraction
    # -------------------------------------------------------------------------

    def extract(self, **kwargs: bool | int) -> ETLResult:
        """Execute YouTube extraction.

        Args:
            **kwargs: Extraction parameters.
                extract_transcripts: Whether to fetch transcripts.
                max_videos: Maximum videos per source.
                resume: Whether to resume from checkpoint.

        Returns:
            ETLResult with extraction statistics.
        """
        extract_transcripts = bool(
            kwargs.get("extract_transcripts", settings.youtube.extract_transcripts)
        )
        max_videos = int(kwargs.get("max_videos", settings.youtube.max_videos))

        self.logger.info(
            f"Starting YouTube extraction (transcripts={extract_transcripts}, "
            f"max_videos={max_videos})"
        )

        if not settings.youtube.has_sources:
            self._log_error(self._ERR_NO_SOURCES)
            return self._end_extraction()

        self._start_extraction()

        try:
            with YouTubeClient() as client:
                self._client = client
                self._extract_all_sources(extract_transcripts, max_videos)
        except YouTubeQuotaExceededError as e:
            self._log_error(f"Quota exceeded: {e}")

        return self._end_extraction()

    def _extract_all_sources(
        self,
        extract_transcripts: bool,
        max_videos: int,
    ) -> None:
        """Extract from all configured sources.

        Args:
            extract_transcripts: Whether to fetch transcripts.
            max_videos: Maximum videos per source.
        """
        channel_count = len(settings.youtube.channel_handles)
        playlist_count = len(settings.youtube.playlist_ids)

        self.logger.info(f"Processing {channel_count} channels and {playlist_count} playlists")

        self._extract_from_channels(extract_transcripts, max_videos)
        self._extract_from_playlists(extract_transcripts, max_videos)

    # -------------------------------------------------------------------------
    # Channel Extraction
    # -------------------------------------------------------------------------

    def _extract_from_channels(
        self,
        extract_transcripts: bool,
        max_videos: int,
    ) -> None:
        """Extract videos from configured channel handles.

        Args:
            extract_transcripts: Whether to fetch transcripts.
            max_videos: Maximum videos per channel.
        """
        handles = settings.youtube.channel_handles
        if not handles:
            self.logger.debug("No channels configured, skipping")
            return

        self.logger.info(f"Extracting from {len(handles)} channels")

        for idx, handle in enumerate(handles, 1):
            self.logger.debug(f"Channel {idx}/{len(handles)}: {handle}")
            self._extract_channel(handle, extract_transcripts, max_videos)

    def _extract_channel(
        self,
        handle: str,
        extract_transcripts: bool,
        max_videos: int,
    ) -> None:
        """Extract videos from a single channel.

        Args:
            handle: Channel handle (e.g., @ChannelName).
            extract_transcripts: Whether to fetch transcripts.
            max_videos: Maximum videos to extract.
        """
        assert self._client is not None, self._ERR_CLIENT_NOT_INITIALIZED

        self.logger.info(f"Extracting channel: {handle}")

        try:
            channel_data = self._client.get_channel_by_handle(handle)
            playlist_id = self._client.get_uploads_playlist_id(channel_data)

            if not playlist_id:
                self._log_error(f"No uploads playlist for {handle}")
                return

            self.logger.debug(f"Channel {handle} -> playlist {playlist_id}")

            self._extract_playlist_videos(
                playlist_id=playlist_id,
                source_type="channel",
                source_id=handle,
                extract_transcripts=extract_transcripts,
                max_videos=max_videos,
            )

            self.logger.info(f"Channel {handle} extraction complete")

        except YouTubeNotFoundError:
            self._log_error(f"Channel not found: {handle}")
        except YouTubeAPIError as e:
            self._log_error(f"Channel extraction failed {handle}: {e}")

    # -------------------------------------------------------------------------
    # Playlist Extraction
    # -------------------------------------------------------------------------

    def _extract_from_playlists(
        self,
        extract_transcripts: bool,
        max_videos: int,
    ) -> None:
        """Extract videos from configured playlists.

        Args:
            extract_transcripts: Whether to fetch transcripts.
            max_videos: Maximum videos per playlist.
        """
        playlist_ids = settings.youtube.playlist_ids
        if not playlist_ids:
            self.logger.debug("No playlists configured, skipping")
            return

        self.logger.info(f"Extracting from {len(playlist_ids)} playlists")

        for idx, playlist_id in enumerate(playlist_ids, 1):
            self.logger.debug(f"Playlist {idx}/{len(playlist_ids)}: {playlist_id}")
            self._extract_playlist(playlist_id, extract_transcripts, max_videos)

    def _extract_playlist(
        self,
        playlist_id: str,
        extract_transcripts: bool,
        max_videos: int,
    ) -> None:
        """Extract videos from a single playlist.

        Args:
            playlist_id: YouTube playlist ID.
            extract_transcripts: Whether to fetch transcripts.
            max_videos: Maximum videos to extract.
        """
        self.logger.info(f"Extracting playlist: {playlist_id}")

        try:
            self._extract_playlist_videos(
                playlist_id=playlist_id,
                source_type="playlist",
                source_id=playlist_id,
                extract_transcripts=extract_transcripts,
                max_videos=max_videos,
            )

            self.logger.info(f"Playlist {playlist_id} extraction complete")

        except YouTubeAPIError as e:
            self._log_error(f"Playlist extraction failed {playlist_id}: {e}")

    def _extract_playlist_videos(
        self,
        playlist_id: str,
        source_type: str,
        source_id: str,
        extract_transcripts: bool,
        max_videos: int,
    ) -> None:
        """Extract and process videos from a playlist.

        Args:
            playlist_id: YouTube playlist ID.
            source_type: Source type (channel/playlist).
            source_id: Source identifier.
            extract_transcripts: Whether to fetch transcripts.
            max_videos: Maximum videos to extract.
        """
        assert self._client is not None, self._ERR_CLIENT_NOT_INITIALIZED

        items = self._client.iter_playlist_videos(playlist_id, max_videos)
        video_ids = self._extract_video_ids(items)

        self.logger.info(f"Found {len(video_ids)} videos in {source_type} {source_id}")

        batch_count = 0
        for batch in self._batch_ids(video_ids, 50):
            batch_count += 1
            self.logger.debug(f"Processing batch {batch_count} ({len(batch)} videos)")
            self._process_video_batch(batch, extract_transcripts)

        self.logger.debug(f"Processed {len(video_ids)} videos in {batch_count} batches")

    def _extract_video_ids(
        self,
        items: list[dict[str, str | dict[str, str]]],
    ) -> list[str]:
        """Extract video IDs from playlist items.

        Args:
            items: List of playlist items.

        Returns:
            List of video IDs.
        """
        ids: list[str] = []

        for item in items:
            content_details = item.get("contentDetails", {})
            if isinstance(content_details, dict):
                video_id = content_details.get("videoId")
                if video_id and isinstance(video_id, str):
                    ids.append(video_id)

        return ids

    def _batch_ids(
        self,
        ids: list[str],
        batch_size: int,
    ) -> Generator[list[str], None, None]:
        """Split IDs into batches.

        Args:
            ids: List of IDs.
            batch_size: Maximum batch size.

        Yields:
            Batches of IDs.
        """
        for i in range(0, len(ids), batch_size):
            yield ids[i : i + batch_size]

    # -------------------------------------------------------------------------
    # Video Processing
    # -------------------------------------------------------------------------

    def _process_video_batch(
        self,
        video_ids: list[str],
        extract_transcripts: bool,
    ) -> None:
        """Process a batch of videos.

        Args:
            video_ids: List of video IDs.
            extract_transcripts: Whether to fetch transcripts.
        """
        assert self._client is not None, self._ERR_CLIENT_NOT_INITIALIZED

        self.logger.debug(f"Fetching batch of {len(video_ids)} videos")

        videos = self._client.get_videos_batch(video_ids)

        self.logger.debug(f"Processing {len(videos)} videos from batch")

        for video_data in videos:
            self._process_single_video(video_data, extract_transcripts)

    def _process_single_video(
        self,
        video_data: dict[str, Any],
        extract_transcripts: bool,
    ) -> None:
        """Process a single video.

        Args:
            video_data: Raw video data from API.
            extract_transcripts: Whether to fetch transcript.
        """
        try:
            video_id = video_data.get("id", "")
            self._extracted_count += 1

            if extract_transcripts:
                result = self._transcript_extractor.extract(video_id)
                if result.success:
                    self.logger.debug(
                        f"Transcript extracted: {video_id} ({result.word_count} words)"
                    )
                else:
                    self.logger.debug(f"Transcript unavailable: {video_id} - {result.error}")

            self._log_periodic_progress()

        except Exception as e:
            video_id = video_data.get("id", "unknown")
            self._log_error(f"Video processing failed {video_id}: {e}")

    def _log_periodic_progress(self) -> None:
        """Log progress at regular intervals."""
        if self._extracted_count % 50 == 0:
            self.logger.info(f"Progress: {self._extracted_count} videos extracted")

    # -------------------------------------------------------------------------
    # Batch Extraction with Callback
    # -------------------------------------------------------------------------

    def extract_with_callback(
        self,
        callback: Callable[[list[VideoBundle]], None],
        extract_transcripts: bool | None = None,
        max_videos: int | None = None,
        batch_size: int = 20,
    ) -> ETLResult:
        """Extract videos and call callback for each batch.

        Args:
            callback: Function to call with video bundles.
            extract_transcripts: Whether to fetch transcripts (default: from settings).
            max_videos: Maximum videos per source (default: from settings).
            batch_size: Callback batch size.

        Returns:
            ETLResult with statistics.
        """
        transcripts_enabled = (
            extract_transcripts
            if extract_transcripts is not None
            else settings.youtube.extract_transcripts
        )
        max_vids = max_videos if max_videos is not None else settings.youtube.max_videos

        self.logger.info(
            f"Starting callback extraction (transcripts={transcripts_enabled}, "
            f"max_videos={max_vids}, batch_size={batch_size})"
        )

        if not settings.youtube.has_sources:
            self._log_error(self._ERR_NO_SOURCES)
            return self._end_extraction()

        self._start_extraction()

        try:
            with YouTubeClient() as client:
                self._client = client
                self._process_with_callback(
                    callback,
                    transcripts_enabled,
                    max_vids,
                    batch_size,
                )
        except YouTubeQuotaExceededError as e:
            self._log_error(f"Quota exceeded: {e}")

        self.logger.info(f"Callback extraction complete: {self._extracted_count} videos")

        return self._end_extraction()

    def _process_with_callback(
        self,
        callback: Callable[[list[VideoBundle]], None],
        extract_transcripts: bool,
        max_videos: int,
        batch_size: int,
    ) -> None:
        """Process all sources with callback batching.

        Args:
            callback: Batch callback function.
            extract_transcripts: Whether to fetch transcripts.
            max_videos: Maximum videos per source.
            batch_size: Callback batch size.
        """
        batch: list[VideoBundle] = []
        callback_count = 0

        for bundle in self._iter_all_videos(extract_transcripts, max_videos):
            batch.append(bundle)
            self._extracted_count += 1

            if len(batch) >= batch_size:
                callback_count += 1
                self.logger.debug(f"Invoking callback #{callback_count} with {len(batch)} bundles")
                callback(batch)
                batch = []

        if batch:
            callback_count += 1
            self.logger.debug(
                f"Invoking final callback #{callback_count} with {len(batch)} bundles"
            )
            callback(batch)

        self.logger.debug(f"Total callbacks invoked: {callback_count}")

    def _iter_all_videos(
        self,
        extract_transcripts: bool,
        max_videos: int,
    ) -> Generator[VideoBundle, None, None]:
        """Iterate all videos from all sources.

        Args:
            extract_transcripts: Whether to fetch transcripts.
            max_videos: Maximum videos per source.

        Yields:
            Video bundles.
        """
        yield from self._iter_channel_videos(extract_transcripts, max_videos)
        yield from self._iter_playlist_videos_gen(extract_transcripts, max_videos)

    def _iter_channel_videos(
        self,
        extract_transcripts: bool,
        max_videos: int,
    ) -> Generator[VideoBundle, None, None]:
        """Iterate videos from all channels.

        Args:
            extract_transcripts: Whether to fetch transcripts.
            max_videos: Maximum videos per channel.

        Yields:
            Video bundles.
        """
        for handle in settings.youtube.channel_handles:
            self.logger.debug(f"Iterating channel: {handle}")
            yield from self._iter_source_videos(
                source_type="channel",
                source_id=handle,
                extract_transcripts=extract_transcripts,
                max_videos=max_videos,
            )

    def _iter_playlist_videos_gen(
        self,
        extract_transcripts: bool,
        max_videos: int,
    ) -> Generator[VideoBundle, None, None]:
        """Iterate videos from all playlists.

        Args:
            extract_transcripts: Whether to fetch transcripts.
            max_videos: Maximum videos per playlist.

        Yields:
            Video bundles.
        """
        for playlist_id in settings.youtube.playlist_ids:
            self.logger.debug(f"Iterating playlist: {playlist_id}")
            yield from self._iter_source_videos(
                source_type="playlist",
                source_id=playlist_id,
                extract_transcripts=extract_transcripts,
                max_videos=max_videos,
            )

    def _iter_source_videos(
        self,
        source_type: str,
        source_id: str,
        extract_transcripts: bool,
        max_videos: int,
    ) -> Generator[VideoBundle, None, None]:
        """Iterate videos from a single source.

        Args:
            source_type: Type of source (channel/playlist).
            source_id: Source identifier.
            extract_transcripts: Whether to fetch transcripts.
            max_videos: Maximum videos.

        Yields:
            Video bundles.
        """
        assert self._client is not None, self._ERR_CLIENT_NOT_INITIALIZED

        playlist_id = self._resolve_playlist_id(source_type, source_id)
        if not playlist_id:
            return

        self.logger.info(f"Processing {source_type}: {source_id}")

        items = self._client.iter_playlist_videos(playlist_id, max_videos)
        video_ids = self._extract_video_ids(items)

        self.logger.debug(f"Found {len(video_ids)} video IDs to process")

        bundle_count = 0
        for batch in self._batch_ids(video_ids, 50):
            for bundle in self._build_video_bundles(
                batch,
                source_type,
                source_id,
                extract_transcripts,
            ):
                bundle_count += 1
                yield bundle

        self.logger.debug(f"Yielded {bundle_count} bundles from {source_type} {source_id}")

    def _resolve_playlist_id(
        self,
        source_type: str,
        source_id: str,
    ) -> str | None:
        """Resolve source to playlist ID.

        Args:
            source_type: Type of source.
            source_id: Source identifier.

        Returns:
            Playlist ID or None.
        """
        assert self._client is not None, self._ERR_CLIENT_NOT_INITIALIZED

        if source_type == "playlist":
            return source_id

        try:
            channel_data = self._client.get_channel_by_handle(source_id)
            playlist_id = self._client.get_uploads_playlist_id(channel_data)

            if playlist_id:
                self.logger.debug(f"Resolved {source_id} -> {playlist_id}")

            return playlist_id

        except YouTubeNotFoundError:
            self._log_error(f"Channel not found: {source_id}")
            return None

    def _build_video_bundles(
        self,
        video_ids: list[str],
        source_type: str,
        source_id: str,
        extract_transcripts: bool,
    ) -> Generator[VideoBundle, None, None]:
        """Build video bundles from batch of IDs.

        Args:
            video_ids: List of video IDs.
            source_type: Source type.
            source_id: Source identifier.
            extract_transcripts: Whether to fetch transcripts.

        Yields:
            Video bundles.
        """
        assert self._client is not None, self._ERR_CLIENT_NOT_INITIALIZED

        self.logger.debug(f"Building bundles for {len(video_ids)} videos")

        videos = self._client.get_videos_batch(video_ids)

        success_count = 0
        for video_data in videos:
            bundle = self._build_single_bundle(
                video_data,
                source_type,
                source_id,
                extract_transcripts,
            )
            if bundle:
                success_count += 1
                yield bundle

        self.logger.debug(f"Built {success_count}/{len(videos)} bundles successfully")

    def _build_single_bundle(
        self,
        video_data: dict[str, Any],
        source_type: str,
        source_id: str,
        extract_transcripts: bool,
    ) -> VideoBundle | None:
        """Build a single video bundle.

        Args:
            video_data: Raw video data.
            source_type: Source type.
            source_id: Source identifier.
            extract_transcripts: Whether to fetch transcript.

        Returns:
            Video bundle or None on error.
        """
        try:
            normalized = self._normalizer.normalize_video(video_data)
            video_id = normalized["youtube_id"]
            video_title = normalized.get("title", "Unknown")

            transcript = self._get_transcript(video_id, extract_transcripts)

            self.logger.debug(f"Bundle created: {video_id} - {video_title[:50]}")

            return VideoBundle(
                video=normalized,
                transcript=transcript,
                source_type=source_type,
                source_id=source_id,
            )

        except Exception as e:
            video_id = video_data.get("id", "unknown")
            self._log_error(f"Bundle build failed {video_id}: {e}")
            return None

    def _get_transcript(
        self,
        video_id: str,
        extract: bool,
    ) -> TranscriptResult | None:
        """Get transcript if extraction enabled.

        Args:
            video_id: YouTube video ID.
            extract: Whether to extract.

        Returns:
            Transcript result or None.
        """
        if not extract:
            return None

        result = self._transcript_extractor.extract(video_id)

        if result.success:
            self.logger.debug(
                f"Transcript OK: {video_id} ({result.language}, {result.word_count} words)"
            )
        else:
            self.logger.debug(f"Transcript failed: {video_id} - {result.error}")

        return result

    # -------------------------------------------------------------------------
    # Single Video Extraction
    # -------------------------------------------------------------------------

    def extract_video(
        self,
        video_id: str,
        extract_transcript: bool = True,
    ) -> VideoBundle | None:
        """Extract a single video by ID.

        Args:
            video_id: YouTube video ID.
            extract_transcript: Whether to fetch transcript.

        Returns:
            Video bundle or None.
        """
        self.logger.info(f"Extracting single video: {video_id} (transcript={extract_transcript})")

        with YouTubeClient() as client:
            self._client = client

            try:
                video_data = client.get_video_details(video_id)
                bundle = self._build_single_bundle(
                    video_data,
                    source_type="direct",
                    source_id=video_id,
                    extract_transcripts=extract_transcript,
                )

                if bundle:
                    self.logger.info(f"Video extracted successfully: {video_id}")
                else:
                    self.logger.warning(f"Failed to build bundle: {video_id}")

                return bundle

            except YouTubeNotFoundError:
                self.logger.warning(f"Video not found: {video_id}")
                return None
            except YouTubeAPIError as e:
                self.logger.error(f"Failed to extract video {video_id}: {e}")
                return None

    # -------------------------------------------------------------------------
    # Checkpoint Management
    # -------------------------------------------------------------------------

    def _get_checkpoint_path(self) -> Path:
        """Get checkpoint file path."""
        return self._checkpoint_dir / "youtube_checkpoint.json"

    def _load_checkpoint(self) -> dict[str, str | int | list[int]] | None:
        """Load extraction checkpoint."""
        checkpoint = self.load_checkpoint(self._get_checkpoint_path())

        if checkpoint:
            self.logger.info(
                f"Checkpoint loaded: source={checkpoint.get('source_type')}/"
                f"{checkpoint.get('source_id')}"
            )
        else:
            self.logger.debug("No checkpoint found")

        return checkpoint

    def _save_checkpoint(
        self,
        source_type: str,
        source_id: str,
        last_video_id: str,
    ) -> None:
        """Save checkpoint for current progress.

        Args:
            source_type: Current source type.
            source_id: Current source ID.
            last_video_id: Last processed video ID.
        """
        checkpoint = self.create_checkpoint(last_id=last_video_id)
        checkpoint["source_type"] = source_type
        checkpoint["source_id"] = source_id
        self.save_checkpoint(checkpoint, self._get_checkpoint_path())

        self.logger.debug(f"Checkpoint saved: {source_type}/{source_id} -> {last_video_id}")

    def _clear_checkpoint(self) -> None:
        """Clear checkpoint file."""
        self.delete_checkpoint(self._get_checkpoint_path())
        self.logger.info("Checkpoint cleared")

    # -------------------------------------------------------------------------
    # Quota Info
    # -------------------------------------------------------------------------

    def get_quota_status(self) -> dict[str, int]:
        """Get current quota usage status.

        Returns:
            Dict with used and remaining quota.
        """
        if self._client:
            status = {
                "used": self._client.quota_used,
                "remaining": self._client.quota_remaining,
            }
        else:
            status = {"used": 0, "remaining": settings.youtube.daily_quota_limit}

        self.logger.debug(f"Quota status: {status['used']} used, {status['remaining']} remaining")

        return status
