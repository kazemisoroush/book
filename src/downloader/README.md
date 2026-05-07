# Downloader

Downloads books from external sources. Implements disk caching to avoid redundant network requests.

- `BookDownloader` (ABC) - `download(url) -> str`
- `ProjectGutenbergHTMLBookDownloader` - Downloads zip files from Project Gutenberg, extracts HTML; skips download if HTML already exists on disk from a previous run

**Output**: Books are downloaded to `books/{book_id}/` directory.
**Caching**: If the HTML file already exists on disk, the downloader returns the cached content without making a network request.

