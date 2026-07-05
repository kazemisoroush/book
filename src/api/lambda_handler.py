"""AWS Lambda entrypoint: the FastAPI app served through Mangum."""
from mangum import Mangum

from src.api.app import create_app

handler = Mangum(create_app())
