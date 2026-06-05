"""AES-256-GCM symmetric encryption for KB content at rest.

Padrão hide-but-readable: o conteúdo no DB fica cifrado, mas a chave fica no
env (`KB_ENCRYPTION_KEY`). Backup do Postgres por si só não vaza material
proprietário — atacante precisa também do env do Railway.

Opt-in: se `KB_ENCRYPTION_KEY` não estiver setado, `encrypt_content()` é
no-op e `decrypt_content()` devolve a string como veio. Isso permite ligar
a criptografia gradualmente (deploy do código antes de rotacionar a chave).

Versionamento: ciphertext sempre prefixado com `v1:` pra suportar rotação
futura (ex.: `v2:` com algoritmo diferente, ou mesmo `v1:` com nova chave).
"""

from __future__ import annotations

import base64
import logging
import os
from functools import lru_cache

logger = logging.getLogger("haira.kb_crypto")

_VERSION_PREFIX = "v1:"
_KEY_ENV = "KB_ENCRYPTION_KEY"


@lru_cache(maxsize=1)
def _load_key() -> bytes | None:
    raw = os.environ.get(_KEY_ENV, "").strip()
    if not raw:
        return None
    try:
        key = base64.b64decode(raw)
    except Exception as exc:
        logger.error("%s base64 inválido: %s", _KEY_ENV, exc)
        return None
    if len(key) != 32:
        logger.error("%s deve ter 32 bytes (AES-256). Encontrado: %d", _KEY_ENV, len(key))
        return None
    return key


def is_enabled() -> bool:
    """True se a env var está setada (criptografia ativa)."""
    return _load_key() is not None


def encrypt_content(plaintext: str) -> str:
    """Cifra com AES-GCM. No-op se a chave não estiver configurada.

    Retorna `v1:<base64(nonce || ciphertext_with_tag)>` ou o plaintext.
    """
    if not plaintext:
        return plaintext
    if plaintext.startswith(_VERSION_PREFIX):
        # Já cifrado — idempotente.
        return plaintext

    key = _load_key()
    if key is None:
        return plaintext  # opt-in disabled

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = os.urandom(12)  # AES-GCM nonce padrão 96-bit
    ct = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    blob = base64.b64encode(nonce + ct).decode("ascii")
    return f"{_VERSION_PREFIX}{blob}"


def decrypt_content(stored: str) -> str:
    """Descriptografa. Devolve o texto puro quando não tem prefixo `v1:`
    (backward-compat com rows antigas em plaintext).
    """
    if not stored or not stored.startswith(_VERSION_PREFIX):
        return stored

    key = _load_key()
    if key is None:
        # Configuração quebrada — chave sumiu mas tem ciphertext. Erro
        # explícito é melhor que devolver lixo.
        raise RuntimeError(
            "KB content cifrado mas KB_ENCRYPTION_KEY não está configurada. "
            "Restaure a chave correta no env (ou apague o ciphertext)."
        )

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    blob = base64.b64decode(stored[len(_VERSION_PREFIX):])
    nonce, ct = blob[:12], blob[12:]
    pt = AESGCM(key).decrypt(nonce, ct, None)
    return pt.decode("utf-8")


def generate_key_base64() -> str:
    """Utilitário pra ops: gera uma chave nova AES-256 em base64.

    Uso:
        python -c "from src.core.kb_crypto import generate_key_base64; print(generate_key_base64())"
    """
    return base64.b64encode(os.urandom(32)).decode("ascii")
