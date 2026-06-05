#!/usr/bin/env python3
"""Migra Postgres-MsGQ (single-DB) → Postgres-Core / Catalog / Audit.

Estratégia "copy from source, dual-write":
  1. Conecta no SOURCE (Postgres-MsGQ atual, env SOURCE_DATABASE_URL).
  2. Conecta nos 3 destinos (CORE_DATABASE_URL, CATALOG_DATABASE_URL, AUDIT_DATABASE_URL).
  3. Pra cada tabela, lê do source e insere no destino correspondente
     (ON CONFLICT DO NOTHING — idempotente, pode rodar várias vezes).
  4. Não toca no source — leitura apenas. Source fica vivo como rollback.

Uso:
    SOURCE_DATABASE_URL=postgresql://... \\
    CORE_DATABASE_URL=postgresql://... \\
    CATALOG_DATABASE_URL=postgresql://... \\
    AUDIT_DATABASE_URL=postgresql://... \\
    python scripts/migrate_to_split_dbs.py [--tables=products,users] [--dry-run]

Pré-requisitos: as DBs destino DEVEM ter sido inicializadas via alembic
upgrade head (cada uma com seu .ini). Esse script só COPIA dados.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from contextlib import contextmanager
from typing import Iterator

import psycopg2
import psycopg2.extras

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s — %(message)s")
log = logging.getLogger("migrate")


# Mapeamento tabela → DB destino. Mantido aqui (não em ORM) porque o script
# roda fora do processo do app e não importa modelos.
TABLE_DESTINATION: dict[str, str] = {
    # haira_core (sensibilidade ALTA)
    "users": "core",
    "hair_profiles": "core",
    "moon_conversations": "core",
    "moon_messages": "core",
    "moon_feedback": "core",
    "moon_config": "core",
    "knowledge_chunks": "core",
    "brand_databases": "core",       # registry central (legado multi-brand)

    # haira_catalog (sensibilidade MÉDIA — dado público)
    "brand_registry": "catalog",
    "brand_coverage": "catalog",
    "products": "catalog",
    "product_evidence": "catalog",
    "product_images": "catalog",
    "product_compositions": "catalog",
    "product_ingredients": "catalog",
    "product_claims": "catalog",
    "quarantine_details": "catalog",
    "ingredients": "catalog",
    "ingredient_aliases": "catalog",
    "ingredient_category_compatibility": "catalog",
    "claims": "catalog",
    "claim_aliases": "catalog",
    "external_inci": "catalog",
    "enrichment_queue": "catalog",
    "validation_comparisons": "catalog",
    "review_queue": "catalog",

    # haira_audit (append-only)
    "revision_history": "audit",
    "kb_retrieval_log": "audit",       # tabela nova; pode vir vazia
    "admin_action_log": "audit",
    "auth_event_log": "audit",

    # Tabelas alembic — pular (cada DB tem o seu próprio)
    "alembic_version": "SKIP",
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _normalise(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


@contextmanager
def _connect(url: str) -> Iterator[psycopg2.extensions.connection]:
    if not url:
        raise SystemExit("Connection URL vazia — confira env vars")
    conn = psycopg2.connect(_normalise(url))
    try:
        yield conn
    finally:
        conn.close()


def _table_exists(conn, name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = %s LIMIT 1",
            (name,),
        )
        return cur.fetchone() is not None


def _row_count(conn, name: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f'SELECT COUNT(*) FROM "{name}"')
        return cur.fetchone()[0] or 0


def _column_names(conn, name: str) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
            """,
            (name,),
        )
        return [row[0] for row in cur.fetchall()]


def _pk_columns(conn, name: str) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = %s::regclass AND i.indisprimary
            """,
            (name,),
        )
        return [row[0] for row in cur.fetchall()]


def _copy_table(source_conn, dest_conn, table: str, dry_run: bool, batch: int = 500) -> tuple[int, int]:
    """Copia source → dest com ON CONFLICT DO NOTHING.

    Retorna (rows_read, rows_inserted). Inserted < read sinaliza linhas
    já existentes no destino (idempotência).
    """
    if not _table_exists(source_conn, table):
        log.info("  [SKIP] %s não existe no source", table)
        return (0, 0)
    if not _table_exists(dest_conn, table):
        log.warning("  [SKIP] %s não existe no DESTINO (rode alembic upgrade head antes)", table)
        return (0, 0)

    cols = _column_names(source_conn, table)
    pks = _pk_columns(source_conn, table)
    if not cols:
        return (0, 0)

    quoted_cols = ", ".join('"' + c + '"' for c in cols)
    placeholders = ", ".join(["%s"] * len(cols))
    conflict = ""
    if pks:
        if len(pks) == 1:
            conflict = ' ON CONFLICT ("' + pks[0] + '") DO NOTHING'
        else:
            quoted_pks = ", ".join('"' + p + '"' for p in pks)
            conflict = ' ON CONFLICT (' + quoted_pks + ') DO NOTHING'

    insert_sql = f'INSERT INTO "{table}" ({quoted_cols}) VALUES ({placeholders}){conflict}'

    rows_read = 0
    rows_inserted = 0

    def _adapt(row: tuple) -> tuple:
        """psycopg2 não sabe adaptar dict/list pra columns JSONB —
        envelopa em psycopg2.extras.Json."""
        out = []
        for val in row:
            if isinstance(val, (dict, list)):
                out.append(psycopg2.extras.Json(val))
            else:
                out.append(val)
        return tuple(out)

    with source_conn.cursor(name=f"copy_{table}") as src_cur:
        src_cur.itersize = batch
        src_cur.execute(f'SELECT {quoted_cols} FROM "{table}"')
        with dest_conn.cursor() as dst_cur:
            buf: list[tuple] = []
            for row in src_cur:
                buf.append(_adapt(row))
                rows_read += 1
                if len(buf) >= batch:
                    if not dry_run:
                        psycopg2.extras.execute_batch(dst_cur, insert_sql, buf, page_size=batch)
                        rows_inserted += dst_cur.rowcount if dst_cur.rowcount > 0 else len(buf)
                    buf.clear()
            if buf:
                if not dry_run:
                    psycopg2.extras.execute_batch(dst_cur, insert_sql, buf, page_size=len(buf))
                    rows_inserted += dst_cur.rowcount if dst_cur.rowcount > 0 else len(buf)
    if not dry_run:
        dest_conn.commit()

    return (rows_read, rows_inserted)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Migra single-DB → split 3-DB.")
    parser.add_argument("--tables", help="csv de tabelas pra processar (default: todas)")
    parser.add_argument("--dry-run", action="store_true", help="só lê + reporta, não escreve")
    parser.add_argument(
        "--target",
        choices=["core", "catalog", "audit", "all"],
        default="all",
        help="só migra tabelas com esse destino (default: all)",
    )
    args = parser.parse_args()

    source_url = os.environ.get("SOURCE_DATABASE_URL") or os.environ.get("DATABASE_URL")
    core_url = os.environ.get("CORE_DATABASE_URL")
    catalog_url = os.environ.get("CATALOG_DATABASE_URL")
    audit_url = os.environ.get("AUDIT_DATABASE_URL")

    if not source_url:
        log.error("SOURCE_DATABASE_URL (ou DATABASE_URL) não setada — preciso saber de onde ler")
        return 2

    targets = {"core": core_url, "catalog": catalog_url, "audit": audit_url}
    missing = [t for t, u in targets.items() if not u and (args.target in (t, "all"))]
    if missing:
        log.error("Faltando env: %s", ", ".join(f"{t.upper()}_DATABASE_URL" for t in missing))
        return 2

    user_tables = (
        {t.strip() for t in args.tables.split(",") if t.strip()}
        if args.tables else None
    )

    log.info("Source: %s", source_url[:40] + "...")
    log.info("Targets: %s", {t: bool(u) for t, u in targets.items()})
    log.info("Mode: %s%s", "DRY-RUN " if args.dry_run else "", "(specific tables)" if user_tables else "(all tables)")

    totals = {"read": 0, "inserted": 0, "skipped": 0}

    with _connect(source_url) as source_conn:
        destinations: dict[str, psycopg2.extensions.connection] = {}
        try:
            for tgt in ("core", "catalog", "audit"):
                if targets[tgt]:
                    destinations[tgt] = psycopg2.connect(_normalise(targets[tgt]))

            for table, dest in TABLE_DESTINATION.items():
                if dest == "SKIP":
                    continue
                if args.target != "all" and dest != args.target:
                    continue
                if user_tables and table not in user_tables:
                    continue
                if dest not in destinations:
                    log.info("[SKIP] %s → %s (destino não configurado)", table, dest)
                    totals["skipped"] += 1
                    continue

                log.info("[%s] %s", dest, table)
                read, inserted = _copy_table(source_conn, destinations[dest], table, args.dry_run)
                totals["read"] += read
                totals["inserted"] += inserted
                log.info("  read=%d, inserted=%d (delta=%d já existiam)", read, inserted, read - inserted)

        finally:
            for c in destinations.values():
                c.close()

    log.info("=" * 60)
    log.info("TOTAIS  read=%d  inserted=%d  skipped_tables=%d",
             totals["read"], totals["inserted"], totals["skipped"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
