# Downloader

Downloads books from external sources. Implements disk caching to avoid redundant network requests.

## BookDownloader

`download(url) -> str`

### ProjectGutenbergHTMLBookDownloader

Downloads zip files from Project Gutenberg and extracts the HTML. Stages each download under `books/.sources/{pg_id}/`, keyed by the numeric Project Gutenberg id parsed from the URL. Returns the cached HTML if a previous run already populated the staging dir.

After the metadata is parsed and a book_id is known, [ProjectGutenbergBookSource](../parsers/project_gutenberg_book_source.py) calls [materialize_source](source_layout.py) to mirror the staged files into `books/{book_id}/source/`. The staging dir is kept so future downloads continue to cache by URL.

## source_layout

Small helpers shared by the downloader and the book source.

* `pg_id_from_url(url) -> str`. Extracts the numeric Gutenberg id from a URL.
* `staging_dir(books_dir, pg_id) -> Path`. Returns `{books_dir}/.sources/{pg_id}`.
* `book_source_dir(books_dir, book_id) -> Path`. Returns `{books_dir}/{book_id}/source`.
* `materialize_source(books_dir, pg_id, book_id)`. Copies the staged files into the per-book source dir on first materialization.
