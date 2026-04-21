"""Ambient audio generation workflow for staged pipeline."""
from pathlib import Path
from typing import Optional
import structlog

from src.workflows.workflow import Workflow
from src.domain.models import Book, Segment
from src.repository.book_repository import BookRepository
from src.repository.url_mapper import get_book_id_from_url
from src.audio.ambient.ambient_provider import AmbientProvider
from src.audio.ambient.stable_audio_ambient_provider import StableAudioAmbientProvider
from src.config import get_config

logger = structlog.get_logger(__name__)


def _compute_scene_time_ranges(
    segments: list[Segment],
    durations: list[float],
) -> dict[str, tuple[float, float]]:
    """Map scene IDs to (start_seconds, end_seconds) from segment durations.

    Segments without a scene_id are skipped. If a scene appears in
    multiple consecutive runs, the range spans from the first segment's
    start to the last segment's end.

    Args:
        segments: Ordered synthesised segments (same order as durations).
        durations: Duration in seconds for each segment, same length as segments.

    Returns:
        Dict mapping each scene_id to its (start, end) time range.
    """
    ranges: dict[str, tuple[float, float]] = {}
    offset = 0.0
    for seg, dur in zip(segments, durations):
        if seg.scene_id is not None:
            existing = ranges.get(seg.scene_id)
            if existing is None:
                ranges[seg.scene_id] = (offset, offset + dur)
            else:
                ranges[seg.scene_id] = (existing[0], offset + dur)
        offset += dur
    return ranges


class AmbientWorkflow(Workflow):
    """Workflow for generating ambient audio from TTS-timed book data.

    Loads a book from the repository (which must have TTS timing data),
    generates ambient audio for scenes, and saves the book back with
    ambient audio paths populated in each chapter.

    This is a staged workflow — it assumes the `ai` and `tts` workflows
    have already run.
    """

    def __init__(
        self,
        repository: BookRepository,
        provider: Optional[AmbientProvider] = None,
        books_dir: Path = Path("books"),
    ) -> None:
        """Initialize with a book repository.

        Args:
            repository: Repository for loading and saving books
            provider: Ambient audio provider for generation
            books_dir: Base directory for book output
        """
        self._repository = repository
        self._provider = provider
        self._books_dir = books_dir

    @classmethod
    def create(cls, books_dir: Path = Path("books")) -> "AmbientWorkflow":
        """Factory that wires production dependencies.

        Requires:
        - STABILITY_API_KEY environment variable for ambient sound

        Args:
            books_dir: Base directory for book output (default: books/)

        Returns:
            A fully-wired AmbientWorkflow
        """
        from src.repository.file_book_repository import FileBookRepository

        config = get_config()

        # Instantiate Stable Audio ambient provider
        provider: Optional[AmbientProvider] = None
        if config.stability_api_key:
            cache_dir = books_dir / "cache" / "ambient"
            provider = StableAudioAmbientProvider(
                api_key=config.stability_api_key,
                cache_dir=cache_dir,
            )

        repository = FileBookRepository(base_dir=str(books_dir))

        return cls(
            repository=repository,
            provider=provider,
            books_dir=books_dir,
        )

    def run(
        self,
        url: str,
        start_chapter: int = 1,
        end_chapter: Optional[int] = None,
        refresh: bool = False,
    ) -> Book:
        """Generate ambient audio for the book identified by URL.

        Args:
            url: Project Gutenberg book URL (used to derive book_id)
            start_chapter: Ignored (staged workflow processes full book)
            end_chapter: Ignored (staged workflow processes full book)
            refresh: Ignored (staged workflow uses existing data)

        Returns:
            The book with ambient audio paths populated

        Raises:
            Exception: If book cannot be loaded or ambient generation fails
        """
        logger.info("ambient_workflow_started", url=url)

        # Derive book_id from URL
        book_id = get_book_id_from_url(url)
        logger.info("ambient_workflow_book_id_derived", book_id=book_id, url=url)

        # Load book from repository
        loaded = self._repository.load(book_id)
        if loaded is None:
            raise ValueError(
                f"No book found in repository for book_id={book_id!r}. "
                "Run the 'ai' and 'tts' workflows first."
            )
        book = loaded
        logger.info("ambient_workflow_book_loaded", book_id=book_id)

        # Generate ambient audio if provider is configured
        if self._provider is not None and book.scene_registry.all():
            for chapter in book.content.chapters:
                # Collect segments with duration_seconds set
                segments_with_duration: list[Segment] = []
                durations: list[float] = []

                for section in chapter.sections:
                    if section.segments is None:
                        continue
                    for segment in section.segments:
                        if segment.duration_seconds is not None:
                            segments_with_duration.append(segment)
                            durations.append(segment.duration_seconds)

                # Skip if no timed segments
                if not segments_with_duration:
                    continue

                # Compute scene time ranges
                time_ranges = _compute_scene_time_ranges(segments_with_duration, durations)

                # Generate ambient for each scene with ambient_prompt
                for scene_id, (start, end) in time_ranges.items():
                    scene = book.scene_registry.get(scene_id)
                    if scene is None or scene.ambient_prompt is None:
                        continue

                    # Generate ambient audio
                    ambient_dir = self._books_dir / book_id / "audio" / "ambient"
                    ambient_dir.mkdir(parents=True, exist_ok=True)
                    output_path = ambient_dir / f"{scene.scene_id}.mp3"

                    duration = max(end - start, 10.0)
                    logger.info(
                        "ambient_workflow_generating",
                        scene_id=scene_id,
                        prompt=scene.ambient_prompt,
                        duration=duration,
                    )

                    ambient_path = self._provider.generate(
                        scene.ambient_prompt,
                        output_path,
                        duration_seconds=duration,
                    )

                    if ambient_path is not None:
                        chapter.ambient_audio_paths.append(str(ambient_path))
                        logger.info(
                            "ambient_workflow_generated",
                            scene_id=scene_id,
                            path=str(ambient_path),
                        )

        # Save book back to repository
        self._repository.save(book, book_id)
        logger.info("ambient_workflow_complete", book_id=book_id)

        return book
