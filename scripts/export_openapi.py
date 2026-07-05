"""Export the FastAPI OpenAPI schema to openapi.yaml, the frontend contract."""
import yaml

from src.api.app import create_app


def main() -> None:
    """Write the app's OpenAPI schema to openapi.yaml at the repo root."""
    app = create_app()
    with open("openapi.yaml", "w", encoding="utf-8") as handle:
        yaml.safe_dump(app.openapi(), handle, sort_keys=False)


if __name__ == "__main__":
    main()
