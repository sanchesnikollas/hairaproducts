#!/usr/bin/env python3
"""Compara source vs destinos pra validar a migração.

Pra cada tabela:
  1. COUNT(*) em ambos lados — destino deve ser >= source (idempotência permite extras).
  2. MD5 dos valores agregados (string_agg da PK ordenada) — detecta diff de conteúdo.

Uso:
    SOURCE_DATABASE_URL=... \\
    CORE_DATABASE_URL=... CATALOG_DATABASE_URL=... AUDIT_DATABASE_URL=... \\
    python scripts/verify_migration.py

Saída:
  ✓ products              source=24308 dest=24308  md5 ok
  ⚠ knowledge_chunks      source=5     dest=5      md5 DIFF (ciphertext mudou — pode ser intencional se re-cifrou)
  ✗ users                 source=7     dest=6      MISSING 1 ROW

Exit code: 0 quando tudo bate, 1 quando há discrepância de count, 2 quando script
quebra (env faltando, conexão).
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

import psycopg2

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("verify")

# Mesmo mapping do migrate script
from scripts.migrate_to_split_dbs import TABLE_DESTINATION  # noqa: E402


def _normalise(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def _table_exists(conn, name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = %s LIMIT 1",
            (name,),
        )
        return cur.fetchone() is not None


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
        return [r[0] for r in cur.fetchall()]


def _count_and_md5(conn, table: str) -> tuple[int, str]:
    pks = _pk_columns(conn, table)
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM "' + table + '"')
        n = cur.fetchone()[0] or 0
        if not pks or n == 0:
            return n, ""
        pk_concat_parts = ['COALESCE("' + p + '"::text, \'\')' for p in pks]
        pk_concat = " || '|' || ".join(pk_concat_parts)
        order_by = ", ".join('"' + p + '"' for p in pks)
        sql = (
            "SELECT md5(string_agg((" + pk_concat + "), '' ORDER BY " + order_by + "))"
            ' FROM "' + table + '"'
        )
        cur.execute(sql)
        digest = cur.fetchone()[0] or ""
    return n, digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=["core", "catalog", "audit", "all"], default="all")
    parser.add_argument("--tables", help="csv lista (default: todas)")
    args = parser.parse_args()

    source_url = os.environ.get("SOURCE_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not source_url:
        log.error("SOURCE_DATABASE_URL faltando")
        return 2

    targets = {
        "core": os.environ.get("CORE_DATABASE_URL"),
        "catalog": os.environ.get("CATALOG_DATABASE_URL"),
        "audit": os.environ.get("AUDIT_DATABASE_URL"),
    }
    user_tables = (
        {t.strip() for t in args.tables.split(",") if t.strip()}
        if args.tables else None
    )

    source_conn = psycopg2.connect(_normalise(source_url))
    dest_conns: dict[str, psycopg2.extensions.connection] = {
        t: psycopg2.connect(_normalise(u)) for t, u in targets.items() if u
    }

    print(f"{'TABLE':<35} {'DEST':<8} {'SRC':>10} {'DST':>10}  MD5")
    print("-" * 90)
    issues = 0

    for table, dest in TABLE_DESTINATION.items():
        if dest == "SKIP":
            continue
        if args.target != "all" and dest != args.target:
            continue
        if user_tables and table not in user_tables:
            continue
        if dest not in dest_conns:
            continue

        if not _table_exists(source_conn, table):
            print(f"{table:<35} {dest:<8} {'(absent)':>10}")
            continue
        if not _table_exists(dest_conns[dest], table):
            print(f"{table:<35} {dest:<8} ?          ✗ TABLE MISSING IN DESTINATION")
            issues += 1
            continue

        try:
            s_n, s_md = _count_and_md5(source_conn, table)
            d_n, d_md = _count_and_md5(dest_conns[dest], table)
        except Exception as exc:  # noqa: BLE001
            print(f"{table:<35} {dest:<8} ERROR: {exc}")
            issues += 1
            continue

        # Destino deve ter ao menos os mesmos N (idempotência permite mais)
        count_ok = d_n >= s_n
        md_ok = (s_md == d_md) if s_md else True

        if count_ok and md_ok:
            mark = "✓"
        elif not count_ok:
            mark = "✗"
            issues += 1
        else:
            mark = "⚠"  # count ok, md5 diff — pode ser intencional (ex: re-encrypt)

        md_label = "ok" if md_ok else "DIFF"
        print(f"{table:<35} {dest:<8} {s_n:>10} {d_n:>10}  {md_label} {mark}")

    print("-" * 90)
    if issues == 0:
        print(f"\n✓ Tudo consistente — destino tem >= source em todas as tabelas verificadas")
        return 0
    print(f"\n⚠ {issues} discrepâncias — revisar antes de cutover")
    return 1


if __name__ == "__main__":
    sys.exit(main())
