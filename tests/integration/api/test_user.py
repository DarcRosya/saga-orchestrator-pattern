import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_user_flow(api_client: AsyncClient, db_session: AsyncSession):
    # Setup username
    username = "testuser"
    password = "SuperSecretPassword123"

    # --- 1. Register ---
    register_payload = {"username": username, "password": password, "email": "test@example.com"}
    register_resp = await api_client.post("/auth/register", json=register_payload)
    assert register_resp.status_code == 201

    tokens = register_resp.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    # --- 2. Login ---
    login_payload = {"username": username, "password": password}
    login_resp = await api_client.post("/auth/login", json=login_payload)
    assert login_resp.status_code == 200

    login_tokens = login_resp.json()
    access_token = login_tokens["access_token"]
    refresh_token = login_tokens["refresh_token"]

    # --- 3. Get Me ---
    me_resp = await api_client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me_resp.status_code == 200

    me_data = me_resp.json()
    assert me_data["username"] == username
