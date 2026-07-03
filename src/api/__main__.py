"""Launch the local API with Uvicorn."""
import os

import uvicorn
from dotenv import load_dotenv

from src.api.app import create_app


def main() -> None:
    """Load environment and serve the API on the configured host and port."""
    load_dotenv()
    host = os.environ.get("API_HOST", "127.0.0.1")
    port = int(os.environ.get("API_PORT", "8000"))
    uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":
    main()
