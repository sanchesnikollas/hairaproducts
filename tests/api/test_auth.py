from __future__ import annotations
import pytest
from src.api.auth import create_access_token, verify_token


class TestJWT:
    def test_create_and_verify_token(self):
        token = create_access_token(user_id="abc-123", role="admin")
        payload = verify_token(token)
        assert payload["sub"] == "abc-123"
        assert payload["role"] == "admin"

    def test_invalid_token_returns_none(self):
        payload = verify_token("garbage.token.value")
        assert payload is None

    def test_expired_token_returns_none(self):
        token = create_access_token(user_id="abc", role="admin", expires_minutes=-1)
        payload = verify_token(token)
        assert payload is None
