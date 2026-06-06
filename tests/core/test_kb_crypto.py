# tests/core/test_kb_crypto.py
"""Bateria de testes para src/core/kb_crypto.py.

AES-256-GCM symmetric encryption pra KB at rest. Crítico: regressão silenciosa
aqui = backup do Postgres começa a vazar Compêndio em plaintext, OU rotação
de chave deixa rows ilegíveis.

Cobertura:
- _load_key: env vazia, base64 inválido, tamanho errado, sucesso
- is_enabled: reflete _load_key
- encrypt_content: opt-in (no-op sem chave), no-op idempotente, formato v1:
- decrypt_content: backward-compat plaintext, ciphertext válido,
  chave sumiu mid-config, tampering
- generate_key_base64: tamanho + entropy
"""
from __future__ import annotations

import base64
import os
from unittest.mock import patch

import pytest


# ───────────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────────


def _fresh_key_b64() -> str:
    """Gera chave AES-256 (32 bytes) em base64 — fresh por teste pra evitar
    poluição entre execuções."""
    return base64.b64encode(os.urandom(32)).decode("ascii")


@pytest.fixture
def with_key():
    """Seta KB_ENCRYPTION_KEY válida + limpa lru_cache."""
    from src.core import kb_crypto
    key_b64 = _fresh_key_b64()
    with patch.dict(os.environ, {"KB_ENCRYPTION_KEY": key_b64}):
        kb_crypto._load_key.cache_clear()
        yield key_b64
    kb_crypto._load_key.cache_clear()


@pytest.fixture
def without_key():
    """Garante que a env var NÃO está setada + limpa lru_cache."""
    from src.core import kb_crypto
    env_copy = {k: v for k, v in os.environ.items() if k != "KB_ENCRYPTION_KEY"}
    with patch.dict(os.environ, env_copy, clear=True):
        kb_crypto._load_key.cache_clear()
        yield
    kb_crypto._load_key.cache_clear()


# ───────────────────────────────────────────────────────────────────────
# _load_key + is_enabled
# ───────────────────────────────────────────────────────────────────────


class TestLoadKey:
    """Validação da chave em todos os cenários de input."""

    def test_returns_none_when_env_unset(self, without_key):
        from src.core.kb_crypto import _load_key
        assert _load_key() is None

    def test_returns_none_when_env_empty(self):
        from src.core import kb_crypto
        with patch.dict(os.environ, {"KB_ENCRYPTION_KEY": ""}):
            kb_crypto._load_key.cache_clear()
            assert kb_crypto._load_key() is None
        kb_crypto._load_key.cache_clear()

    def test_returns_none_when_env_whitespace(self):
        from src.core import kb_crypto
        with patch.dict(os.environ, {"KB_ENCRYPTION_KEY": "   "}):
            kb_crypto._load_key.cache_clear()
            assert kb_crypto._load_key() is None
        kb_crypto._load_key.cache_clear()

    def test_returns_none_when_base64_invalid(self):
        """Strings que não são base64 válido viram None (log de erro)."""
        from src.core import kb_crypto
        with patch.dict(os.environ, {"KB_ENCRYPTION_KEY": "not-base64!!!"}):
            kb_crypto._load_key.cache_clear()
            assert kb_crypto._load_key() is None
        kb_crypto._load_key.cache_clear()

    def test_returns_none_when_key_wrong_size(self):
        """AES-256 precisa de 32 bytes. 16 bytes (AES-128) é rejeitado."""
        from src.core import kb_crypto
        wrong_size = base64.b64encode(os.urandom(16)).decode("ascii")
        with patch.dict(os.environ, {"KB_ENCRYPTION_KEY": wrong_size}):
            kb_crypto._load_key.cache_clear()
            assert kb_crypto._load_key() is None
        kb_crypto._load_key.cache_clear()

    def test_returns_bytes_when_valid(self, with_key):
        from src.core.kb_crypto import _load_key
        key = _load_key()
        assert key is not None
        assert len(key) == 32


class TestIsEnabled:

    def test_disabled_without_key(self, without_key):
        from src.core.kb_crypto import is_enabled
        assert is_enabled() is False

    def test_enabled_with_key(self, with_key):
        from src.core.kb_crypto import is_enabled
        assert is_enabled() is True


# ───────────────────────────────────────────────────────────────────────
# encrypt_content
# ───────────────────────────────────────────────────────────────────────


class TestEncryptContent:

    def test_empty_string_passes_through(self, with_key):
        from src.core.kb_crypto import encrypt_content
        assert encrypt_content("") == ""

    def test_already_encrypted_is_idempotent(self, with_key):
        """Re-criptografar uma string já com prefixo v1: NÃO duplica encryption."""
        from src.core.kb_crypto import encrypt_content
        # Primeiro encrypt
        ct = encrypt_content("hello world")
        assert ct.startswith("v1:")
        # Segundo encrypt do MESMO valor → noop (devolve igual)
        ct2 = encrypt_content(ct)
        assert ct2 == ct

    def test_no_op_when_key_unset(self, without_key):
        """Sem chave, encrypt_content devolve plaintext (opt-in disabled)."""
        from src.core.kb_crypto import encrypt_content
        assert encrypt_content("hello") == "hello"

    def test_output_format_starts_with_v1(self, with_key):
        from src.core.kb_crypto import encrypt_content
        ct = encrypt_content("hello")
        assert ct.startswith("v1:")

    def test_payload_is_base64(self, with_key):
        from src.core.kb_crypto import encrypt_content
        ct = encrypt_content("hello world")
        # remove prefixo, deve ser decodificável
        payload = ct[len("v1:"):]
        decoded = base64.b64decode(payload)
        # nonce (12) + ciphertext + tag (16) = >= 28
        assert len(decoded) >= 28

    def test_different_calls_produce_different_ciphertexts(self, with_key):
        """Nonce random → mesma plaintext gera ciphertexts diferentes (segurança)."""
        from src.core.kb_crypto import encrypt_content
        ct1 = encrypt_content("hello")
        ct2 = encrypt_content("hello")
        assert ct1 != ct2

    def test_roundtrip_basic(self, with_key):
        from src.core.kb_crypto import encrypt_content, decrypt_content
        for original in ["hello", "🌙 Moon Compêndio Haira", "x" * 10000]:
            ct = encrypt_content(original)
            assert ct.startswith("v1:")
            assert decrypt_content(ct) == original

    def test_roundtrip_unicode(self, with_key):
        """UTF-8 multibyte chars sobrevivem encrypt+decrypt."""
        from src.core.kb_crypto import encrypt_content, decrypt_content
        text = "Capilar 🧬 cabelo 3a — INCI: água, óleo de açaí"
        assert decrypt_content(encrypt_content(text)) == text


# ───────────────────────────────────────────────────────────────────────
# decrypt_content
# ───────────────────────────────────────────────────────────────────────


class TestDecryptContent:

    def test_empty_passes_through(self, with_key):
        from src.core.kb_crypto import decrypt_content
        assert decrypt_content("") == ""

    def test_plaintext_without_prefix_passes_through(self, with_key):
        """Backward-compat: rows criados antes de habilitar encryption ficam legíveis."""
        from src.core.kb_crypto import decrypt_content
        assert decrypt_content("plain text without prefix") == "plain text without prefix"

    def test_raises_when_key_missing_for_ciphertext(self, with_key):
        """Cenário ops crítico: ciphertext existe, mas chave sumiu do env."""
        from src.core import kb_crypto
        # Gera ciphertext com chave válida
        ct = kb_crypto.encrypt_content("secret content")
        assert ct.startswith("v1:")

        # Remove chave do env
        env_copy = {k: v for k, v in os.environ.items() if k != "KB_ENCRYPTION_KEY"}
        with patch.dict(os.environ, env_copy, clear=True):
            kb_crypto._load_key.cache_clear()
            with pytest.raises(RuntimeError, match="KB_ENCRYPTION_KEY"):
                kb_crypto.decrypt_content(ct)
        kb_crypto._load_key.cache_clear()

    def test_raises_on_tampered_ciphertext(self, with_key):
        """GCM tag detecta modificação — InvalidTag raised."""
        from cryptography.exceptions import InvalidTag
        from src.core.kb_crypto import decrypt_content, encrypt_content
        ct = encrypt_content("hello world")
        # Flipa um caractere no meio do payload
        prefix, payload = ct.split(":", 1)
        decoded = bytearray(base64.b64decode(payload))
        decoded[20] ^= 0xFF  # corrompe um byte
        tampered = f"{prefix}:{base64.b64encode(bytes(decoded)).decode()}"
        with pytest.raises(InvalidTag):
            decrypt_content(tampered)

    def test_raises_when_wrong_key_used(self):
        """Chave diferente da que cifrou → InvalidTag (segurança)."""
        from cryptography.exceptions import InvalidTag
        from src.core import kb_crypto

        key_a = _fresh_key_b64()
        key_b = _fresh_key_b64()

        # Cifra com key_a
        with patch.dict(os.environ, {"KB_ENCRYPTION_KEY": key_a}):
            kb_crypto._load_key.cache_clear()
            ct = kb_crypto.encrypt_content("sensitive content")
        kb_crypto._load_key.cache_clear()

        # Tenta decifrar com key_b — falha
        with patch.dict(os.environ, {"KB_ENCRYPTION_KEY": key_b}):
            kb_crypto._load_key.cache_clear()
            with pytest.raises(InvalidTag):
                kb_crypto.decrypt_content(ct)
        kb_crypto._load_key.cache_clear()


# ───────────────────────────────────────────────────────────────────────
# generate_key_base64
# ───────────────────────────────────────────────────────────────────────


class TestGenerateKey:

    def test_returns_valid_base64(self):
        from src.core.kb_crypto import generate_key_base64
        k = generate_key_base64()
        # decodifica sem erro
        decoded = base64.b64decode(k)
        assert isinstance(decoded, bytes)

    def test_returns_32_bytes(self):
        """AES-256 = chave de 32 bytes."""
        from src.core.kb_crypto import generate_key_base64
        decoded = base64.b64decode(generate_key_base64())
        assert len(decoded) == 32

    def test_each_call_returns_different_key(self):
        """Não pode retornar o mesmo valor — entropy preserved."""
        from src.core.kb_crypto import generate_key_base64
        keys = {generate_key_base64() for _ in range(10)}
        assert len(keys) == 10  # zero colisão em 10 chamadas

    def test_generated_key_is_usable(self):
        """Chave gerada funciona end-to-end com encrypt+decrypt."""
        from src.core import kb_crypto
        new_key = kb_crypto.generate_key_base64()
        with patch.dict(os.environ, {"KB_ENCRYPTION_KEY": new_key}):
            kb_crypto._load_key.cache_clear()
            original = "lorem ipsum dolor sit amet"
            assert kb_crypto.decrypt_content(kb_crypto.encrypt_content(original)) == original
        kb_crypto._load_key.cache_clear()
