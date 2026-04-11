from src.utils.security import hash_password, verify_password


def test_hash_password_returns_hash_and_verifies() -> None:
    plain = "StrongPassword123!"
    hashed = hash_password(plain)

    assert hashed != plain
    assert verify_password(plain, hashed) is True


def test_verify_password_rejects_invalid_password() -> None:
    hashed = hash_password("StrongPassword123!")

    assert verify_password("WrongPassword456!", hashed) is False
