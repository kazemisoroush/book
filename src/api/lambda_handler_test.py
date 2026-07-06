"""Tests for the Lambda entrypoint."""
from src.api.lambda_handler import handler


def test_handler_serves_health_from_an_api_gateway_event():
    # Arrange
    event = {
        "version": "2.0",
        "routeKey": "GET /health",
        "rawPath": "/health",
        "rawQueryString": "",
        "headers": {"host": "example.com"},
        "requestContext": {
            "http": {"method": "GET", "path": "/health", "sourceIp": "1.2.3.4"},
        },
        "isBase64Encoded": False,
    }

    # Act
    response = handler(event, None)

    # Assert
    assert response["statusCode"] == 200
    assert "ok" in response["body"]
