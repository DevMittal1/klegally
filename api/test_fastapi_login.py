import os
import sys
from unittest.mock import patch, MagicMock, AsyncMock

# Add directories to system path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "../shared/auth"),
)

# Mock DB import to prevent connection issues during unit tests
patcher_db = patch("api.services.db.db")
mock_db = patcher_db.start()

from api.app import app
from fastapi.testclient import TestClient

client = TestClient(app)


@patch("api.services.auth.get_user_by_email", new_callable=AsyncMock)
@patch("api.services.auth.verify_password", new_callable=AsyncMock)
def test_oauth2_form_login(mock_verify_password, mock_get_user_by_email):
    print("Testing standard Form URL-encoded OAuth2 login (FastAPI Swagger standard)...")

    # Mock database and password verification
    mock_get_user_by_email.return_value = {
        "user_id": "user_fastapi_01",
        "email": "fastapi@klegally.com",
        "hashed_password": "mocked_hashed_password",
        "role": "user",
        "org_id": "org_klegally",
    }
    mock_verify_password.return_value = True

    # Call /auth/login with Form urlencoded data
    response = client.post(
        "/auth/login",
        data={"username": "fastapi@klegally.com", "password": "password123"},
    )

    assert response.status_code == 200
    tokens = response.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    print("OAuth2 Form Login verified successfully!")


@patch("api.services.auth.get_user_by_email", new_callable=AsyncMock)
@patch("api.services.auth.verify_password", new_callable=AsyncMock)
def test_json_login(mock_verify_password, mock_get_user_by_email):
    print("Testing standard JSON payload login...")

    # Mock database and password verification
    mock_get_user_by_email.return_value = {
        "user_id": "user_fastapi_01",
        "email": "fastapi@klegally.com",
        "hashed_password": "mocked_hashed_password",
        "role": "user",
        "org_id": "org_klegally",
    }
    mock_verify_password.return_value = True

    # Call /auth/login with application/json
    response = client.post(
        "/auth/login",
        json={"email": "fastapi@klegally.com", "password": "password123"},
    )

    assert response.status_code == 200
    tokens = response.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    print("JSON Login verified successfully!")


if __name__ == "__main__":
    try:
        test_oauth2_form_login()
        test_json_login()
        print("All FastAPI login compatibility tests passed successfully!")
    finally:
        patcher_db.stop()
