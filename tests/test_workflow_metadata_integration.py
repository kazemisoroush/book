"""Integration tests for the metadata parsing pipeline.

These tests verify that metadata fields (title, author, language, releaseDate)
flow correctly from the HTML source through the parser, workflow, and
Book.to_dict() into the final output structure.

They test the real parsers wired through the real workflow — only the
network/file-system boundary is mocked so no internet access is required.
"""
from unittest.mock import Mock, patch

from src.workflows.project_gutenberg_workflow import ProjectGutenbergWorkflow
from src.parsers.static_project_gutenberg_html_metadata_parser import (
    StaticProjectGutenbergHTMLMetadataParser,
)
from src.parsers.static_project_gutenberg_html_content_parser import (
    StaticProjectGutenbergHTMLContentParser,
)


# ---------------------------------------------------------------------------
# HTML fixtures
# ---------------------------------------------------------------------------

# Older Project Gutenberg format: metadata in plain <div> elements.
# Matches the format used by book 74 (Tom Sawyer).
_DIV_FORMAT_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Test Book | Project Gutenberg</title></head>
<body>
<div style='display:block; margin-top:1em; margin-bottom:1em; margin-left:2em; text-indent:-2em'\
>Title: The Adventures of Tom Sawyer</div>
<div style='display:block; margin-top:1em; margin-bottom:1em; margin-left:2em; text-indent:-2em'\
>Author: Mark Twain</div>
<div style='display:block; margin:1em 0'>Release Date: July, 1993 [eBook #74]<br/>
[Most recently updated: August 9, 2023]</div>
<div style='display:block; margin:1em 0'>Language: English</div>
<div style='display:block; margin-left:2em; text-indent:-2em'>Produced by: David Widger</div>
<div>*** START OF THE PROJECT GUTENBERG EBOOK THE ADVENTURES OF TOM SAWYER ***</div>
<div class="chapter">
<h2>CHAPTER I</h2>
<p>&#8220;Tom!&#8221;</p>
<p>No answer.</p>
</div>
</body>
</html>
"""

# Newer Project Gutenberg format: metadata in Dublin Core <meta> tags.
# Matches the format used by book 11 (Alice in Wonderland).
_META_TAG_FORMAT_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="dc.title" content="Alice's Adventures in Wonderland">
<meta name="dc.creator" content="Carroll, Lewis">
<meta name="dc.language" content="en">
<meta name="dcterms.created" content="2008-06-27">
<title>Alice's Adventures in Wonderland | Project Gutenberg</title>
</head>
<body>
<div id="pg-header">
<p>Title: Alice's Adventures in Wonderland</p>
</div>
<div>*** START OF THE PROJECT GUTENBERG EBOOK ***</div>
<div class="chapter">
<h2>CHAPTER I. Down the Rabbit-Hole</h2>
<p>Alice was beginning to get very tired of sitting by her sister on the bank.</p>
</div>
</body>
</html>
"""


def _make_workflow() -> ProjectGutenbergWorkflow:
    """Create a workflow with real parsers (static only, no AI)."""
    return ProjectGutenbergWorkflow(
        downloader=Mock(),
        metadata_parser=StaticProjectGutenbergHTMLMetadataParser(),
        content_parser=StaticProjectGutenbergHTMLContentParser(),
    )


def _run_workflow_with_html(html: str, book_id: str = "74") -> dict:
    """Run the workflow with the given HTML fixture, return book.to_dict()."""
    workflow = _make_workflow()
    workflow.downloader.parse.return_value = True
    workflow.downloader._extract_book_id.return_value = book_id

    url = f"https://www.gutenberg.org/files/{book_id}/{book_id}-h.zip"
    html_filename = f"{book_id}-h.html"

    with patch("os.walk") as mock_walk, patch(
        "builtins.open", create=True
    ) as mock_open:
        mock_walk.return_value = [(f"books/{book_id}", [], [html_filename])]
        mock_open.return_value.__enter__.return_value.read.return_value = html
        book = workflow.run(url)

    return book.to_dict()


# ---------------------------------------------------------------------------
# Tests: div-based (older) format
# ---------------------------------------------------------------------------

class TestWorkflowMetadataIntegration:
    """End-to-end metadata flow: HTML → parser → workflow → Book.to_dict()."""

    def test_div_format_title_is_non_null_in_output(self):
        """Title extracted from div-based HTML must survive the full pipeline."""
        result = _run_workflow_with_html(_DIV_FORMAT_HTML)
        assert result["metadata"]["title"] is not None
        assert result["metadata"]["title"] != ""

    def test_div_format_author_is_non_null_in_output(self):
        """Author extracted from div-based HTML must survive the full pipeline."""
        result = _run_workflow_with_html(_DIV_FORMAT_HTML)
        assert result["metadata"]["author"] is not None

    def test_div_format_language_is_non_null_in_output(self):
        """Language extracted from div-based HTML must survive the full pipeline."""
        result = _run_workflow_with_html(_DIV_FORMAT_HTML)
        assert result["metadata"]["language"] is not None

    def test_div_format_release_date_is_non_null_in_output(self):
        """Release date extracted from div-based HTML must survive the full pipeline."""
        result = _run_workflow_with_html(_DIV_FORMAT_HTML)
        assert result["metadata"]["releaseDate"] is not None

    def test_div_format_all_metadata_fields_correct_values(self):
        """All metadata fields match expected values for div-based HTML."""
        result = _run_workflow_with_html(_DIV_FORMAT_HTML)
        metadata = result["metadata"]
        assert metadata["title"] == "The Adventures of Tom Sawyer"
        assert metadata["author"] == "Mark Twain"
        assert metadata["language"] == "English"
        assert metadata["releaseDate"] == "July, 1993 [eBook #74]"

    # ------------------------------------------------------------------
    # Tests: newer meta-tag format
    # ------------------------------------------------------------------

    def test_meta_tag_format_title_is_non_null_in_output(self):
        """Title from Dublin Core meta tags must survive the full pipeline."""
        result = _run_workflow_with_html(_META_TAG_FORMAT_HTML, book_id="11")
        assert result["metadata"]["title"] is not None
        assert result["metadata"]["title"] != ""

    def test_meta_tag_format_author_is_non_null_in_output(self):
        """Author from Dublin Core meta tags must survive the full pipeline."""
        result = _run_workflow_with_html(_META_TAG_FORMAT_HTML, book_id="11")
        assert result["metadata"]["author"] is not None

    def test_meta_tag_format_language_is_non_null_in_output(self):
        """Language from Dublin Core meta tags must survive the full pipeline."""
        result = _run_workflow_with_html(_META_TAG_FORMAT_HTML, book_id="11")
        assert result["metadata"]["language"] is not None

    def test_meta_tag_format_release_date_is_non_null_in_output(self):
        """Release date from Dublin Core meta tags must survive the full pipeline."""
        result = _run_workflow_with_html(_META_TAG_FORMAT_HTML, book_id="11")
        assert result["metadata"]["releaseDate"] is not None

    def test_meta_tag_format_all_metadata_fields_correct_values(self):
        """All metadata fields match expected values for meta-tag HTML."""
        result = _run_workflow_with_html(_META_TAG_FORMAT_HTML, book_id="11")
        metadata = result["metadata"]
        assert metadata["title"] == "Alice's Adventures in Wonderland"
        assert metadata["author"] == "Carroll, Lewis"
        assert metadata["language"] == "en"
        assert metadata["releaseDate"] == "2008-06-27"

    # ------------------------------------------------------------------
    # Tests: Book.to_dict() structure
    # ------------------------------------------------------------------

    def test_output_dict_has_metadata_key(self):
        """book.to_dict() must have a top-level 'metadata' key."""
        result = _run_workflow_with_html(_DIV_FORMAT_HTML)
        assert "metadata" in result

    def test_output_dict_metadata_has_all_expected_keys(self):
        """book.to_dict()['metadata'] must contain all expected field names."""
        result = _run_workflow_with_html(_DIV_FORMAT_HTML)
        metadata = result["metadata"]
        for key in ("title", "author", "releaseDate", "language",
                    "originalPublication", "credits"):
            assert key in metadata, f"Missing key: {key}"

    def test_output_dict_has_content_with_chapters(self):
        """book.to_dict() must have content with at least one chapter."""
        result = _run_workflow_with_html(_DIV_FORMAT_HTML)
        assert "content" in result
        assert len(result["content"]["chapters"]) >= 1
