import pytest
from pydantic import ValidationError

from src.schemas.auth import RegisterRequest


def test_register_request_valid():
    payload = {"username": "user123", "password": "Password123", "email": "user@example.com"}

    req = RegisterRequest(**payload)
    assert req.username == "user123"


def test_register_request_invalid_username():
    payload = {
        "username": "us",  # min length 3
        "password": "Password123",
    }

    with pytest.raises(ValidationError) as exc:
        RegisterRequest(**payload)

    assert "username" in str(exc.value)


def test_register_request_invalid_password():
    payload = {
        "username": "user123",
        "password": "short",  # min length 8
    }

    with pytest.raises(ValidationError) as exc:
        RegisterRequest(**payload)

    assert "password" in str(exc.value)
