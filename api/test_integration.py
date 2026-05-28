import os
import sys
from unittest.mock import patch, AsyncMock

# Add api/, shared/auth/ and shared/queue/ to python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../shared/auth"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../shared/queue"))

# Mock database calls to run tests in isolation without needing a live MongoDB server
MOCK_USERS_DB = {
    "admin@klegally.com": {
        "user_id": "user_admin_01",
        "email": "admin@klegally.com",
        "hashed_password": "$argon2id$v=19$m=65536,t=3,p=4$DxCgiXyby6vTKaz6zDm3XQ$d3PeAjBCfpttTg9WmRKY27lfeFtkXizOecpYoIfc9DU", # Password: AdminPassword123!
        "role": "admin",
        "org_id": "org_klegally",
    }
}

async def mock_get_user_by_email(email: str):
    return MOCK_USERS_DB.get(email.lower())

async def mock_get_user_by_id(user_id: str):
    for user in MOCK_USERS_DB.values():
        if user["user_id"] == user_id:
            return user
    return None

# Apply global mocks before importing app so it registers them seamlessly
patcher_email = patch("api.services.db.get_user_by_email", side_effect=mock_get_user_by_email)
patcher_id = patch("api.services.db.get_user_by_id", side_effect=mock_get_user_by_id)
patcher_seed = patch("api.services.db.seed_database", new_callable=AsyncMock)
patcher_insert = patch("api.services.db.users_collection.insert_one", new_callable=AsyncMock)

patcher_email.start()
patcher_id.start()
patcher_seed.start()
patcher_insert.start()

from api.app import app
from api.infrastructure.queue import get_queue_service
from fastapi.testclient import TestClient

# Standard FastAPI dependency overrides for fully offline queue assertions
mock_queue_service = AsyncMock()
app.dependency_overrides[get_queue_service] = lambda: mock_queue_service

client = TestClient(app)

def test_root():
    print("Testing base endpoint status...")
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "mongodb" in data["features"]
    print("Base endpoint works!")

def test_register_flow():
    print("Testing user registration flow...")
    
    # Reset mock assertions
    mock_queue_service.reset_mock()
    new_email = "new_user@klegally.com"

    # 1. Register a brand new user
    print(f"Submitting registration for new user: {new_email}")
    response = client.post("/auth/register", json={
        "email": new_email,
        "password": "Password123!",
        "role": "user",
        "org_id": "org_test"
    })
    assert response.status_code == 201
    reg_data = response.json()
    assert reg_data["email"] == new_email
    assert reg_data["role"] == "user"
    assert "user_id" in reg_data
    
    # Validate that registration event was successfully published to Queue
    mock_queue_service.publish.assert_called_once()
    topic, payload = mock_queue_service.publish.call_args[0]
    assert topic == "email_tasks"
    assert payload["email"] == new_email
    assert payload["user_id"] == reg_data["user_id"]
    print("Outbound registration queue event validated successfully!")

    # Add the newly registered user to MOCK_USERS_DB to simulate persistence
    MOCK_USERS_DB[new_email] = {
        "user_id": reg_data["user_id"],
        "email": new_email,
        "hashed_password": "hashed_password_mock",
        "role": "user",
        "org_id": "org_test"
    }

    # 2. Re-register the exact same user, must be rejected with 400
    print("Attempting to re-register duplicate email address...")
    response = client.post("/auth/register", json={
        "email": new_email,
        "password": "Password123!"
    })
    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"
    print("Registration duplication validation verified successfully!")

def test_auth_and_user_profile():
    print("Testing authentication and protected profile fetch...")
    
    # 1. Login with invalid credentials
    print("Submitting invalid login details...")
    response = client.post("/auth/login", json={
        "email": "admin@klegally.com",
        "password": "WrongPassword!"
    })
    assert response.status_code == 401
    
    # 2. Login with valid credentials
    print("Submitting valid login details...")
    response = client.post("/auth/login", json={
        "email": "admin@klegally.com",
        "password": "AdminPassword123!"
    })
    assert response.status_code == 200
    tokens = response.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    print("Login successful! Acquired tokens.")

    # 3. Access profile without token
    print("Testing profile retrieval without authorization header...")
    response = client.get("/users/me")
    assert response.status_code == 401

    # 4. Access profile with token
    print("Testing profile retrieval with acquired bearer token...")
    response = client.get("/users/me", headers={
        "Authorization": f"Bearer {tokens['access_token']}"
    })
    assert response.status_code == 200
    profile = response.json()
    assert profile["email"] == "admin@klegally.com"
    assert profile["role"] == "admin"
    assert profile["org_id"] == "org_klegally"
    print("Acquired profile details match database exactly!")

    # 5. Refresh token exchange
    print("Testing access token renewal via refresh token...")
    response = client.post("/auth/refresh", json={
        "refresh_token": tokens["refresh_token"]
    })
    assert response.status_code == 200
    refreshed = response.json()
    assert "access_token" in refreshed
    print("Token renewal successful!")

if __name__ == "__main__":
    try:
        test_root()
        test_register_flow()
        test_auth_and_user_profile()
        print("All integration tests passed successfully!")
    finally:
        patcher_email.stop()
        patcher_id.stop()
        patcher_seed.stop()
        patcher_insert.stop()
