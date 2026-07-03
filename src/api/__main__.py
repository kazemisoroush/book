"""Launch the local API with Uvicorn."""
import uvicorn
from dotenv import load_dotenv

from src.api.app import create_app
from src.config.api_config import ApiConfig


def main() -> None:
    """Load environment and serve the API on the configured host and port."""
    load_dotenv()
    config = ApiConfig.from_env()
    uvicorn.run(create_app(), host=config.host, port=config.port)


if __name__ == "__main__":
    main()
