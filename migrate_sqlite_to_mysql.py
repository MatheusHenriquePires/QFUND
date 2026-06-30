"""Migra, de forma retomavel, o banco SQLite legado para MySQL/MariaDB."""

from __future__ import annotations

import argparse
import os
import sqlite3
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

import pymysql
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SOURCE = BASE_DIR / "generated" / "qfund.db"

# A ordem respeita as chaves estrangeiras do esquema MySQL.
TABLES = (
    ("users", "id"),
    ("sessions", "token_hash"),
    ("disciplines", "id"),
    ("contents", "id"),
    ("grade_levels", "code"),
    ("questions", "id"),
    ("question_contents", "question_id, content_id"),
    ("question_grades", "question_id, grade_code"),
    ("question_images", "id"),
    ("activities", "id"),
    ("sync_runs", "id"),
    ("app_meta", "key"),
)


def mysql_config() -> dict:
    load_dotenv(BASE_DIR / ".env")
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        parsed = urlparse(database_url)
        if parsed.scheme not in {"mysql", "mysql+pymysql", "mariadb"}:
            raise RuntimeError("DATABASE_URL precisa apontar para MySQL/MariaDB")
        return {
            "host": parsed.hostname or "127.0.0.1",
            "port": parsed.port or 3306,
            "user": unquote(parsed.username or "root"),
            "password": unquote(parsed.password or ""),
            "database": parsed.path.lstrip("/") or "qfund",
        }

    return {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USERNAME") or os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": os.getenv("DB_DATABASE") or os.getenv("DB_NAME", "qfund"),
    }


def connect_mysql():
    return pymysql.connect(
        **mysql_config(),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
        connect_timeout=15,
        read_timeout=300,
        write_timeout=300,
    )


def source_columns(sqlite_connection, table: str) -> list[str]:
    return [row[1] for row in sqlite_connection.execute(f"PRAGMA table_info(`{table}`)")]


def target_columns(mysql_connection, table: str) -> tuple[list[str], set[str]]:
    with mysql_connection.cursor() as cursor:
        cursor.execute(f"SHOW COLUMNS FROM `{table}`")
        rows = cursor.fetchall()
    return [row["Field"] for row in rows], {
        row["Field"] for row in rows if row["Key"] == "PRI"
    }


def build_upsert(table: str, columns: list[str], primary_keys: set[str]) -> str:
    quoted = ", ".join(f"`{column}`" for column in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    mutable = [column for column in columns if column not in primary_keys]
    if mutable:
        updates = ", ".join(
            f"`{column}` = VALUES(`{column}`)" for column in mutable
        )
    else:
        first = columns[0]
        updates = f"`{first}` = `{first}`"
    return (
        f"INSERT INTO `{table}` ({quoted}) VALUES ({placeholders}) "
        f"ON DUPLICATE KEY UPDATE {updates}"
    )


def migrate_table(
    sqlite_connection,
    mysql_connection,
    table: str,
    order_by: str,
    batch_size: int,
    byte_budget: int,
    user_id_map: dict[int, int],
) -> tuple[int, int]:
    source = source_columns(sqlite_connection, table)
    target, primary_keys = target_columns(mysql_connection, table)
    columns = [column for column in source if column in target]
    if not columns:
        raise RuntimeError(f"Nenhuma coluna compativel encontrada em {table}")

    sql = build_upsert(table, columns, primary_keys)
    select_columns = ", ".join(f"`{column}`" for column in columns)
    order = "depth, id" if table == "contents" else order_by
    source_cursor = sqlite_connection.execute(
        f"SELECT {select_columns} FROM `{table}` ORDER BY {order}"
    )

    with mysql_connection.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) AS total FROM `{table}`")
        before = cursor.fetchone()["total"]

    processed = 0
    batch: list[tuple] = []
    batch_bytes = 0
    started = time.monotonic()

    def flush() -> None:
        nonlocal batch, batch_bytes, processed
        if not batch:
            return
        with mysql_connection.cursor() as cursor:
            cursor.executemany(sql, batch)
        mysql_connection.commit()
        processed += len(batch)
        elapsed = max(time.monotonic() - started, 0.001)
        print(
            f"{table}: {processed} registros processados "
            f"({processed / elapsed:.0f}/s)",
            flush=True,
        )
        batch = []
        batch_bytes = 0

    for row in source_cursor:
        mutable_row = dict(row)
        user_column = "owner_user_id" if table == "questions" else "user_id"
        if user_column in mutable_row and mutable_row[user_column] is not None:
            mutable_row[user_column] = user_id_map.get(
                mutable_row[user_column], mutable_row[user_column]
            )
        values = tuple(mutable_row[column] for column in columns)
        row_bytes = sum(
            len(value) if isinstance(value, bytes) else len(str(value).encode("utf-8"))
            for value in values
            if value is not None
        )
        if batch and (len(batch) >= batch_size or batch_bytes + row_bytes > byte_budget):
            flush()
        batch.append(values)
        batch_bytes += row_bytes
    flush()

    with mysql_connection.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) AS total FROM `{table}`")
        after = cursor.fetchone()["total"]
    return before, after


def build_user_id_map(sqlite_connection, mysql_connection) -> dict[int, int]:
    source_users = sqlite_connection.execute("SELECT id, email FROM users").fetchall()
    with mysql_connection.cursor() as cursor:
        cursor.execute("SELECT id, email FROM users")
        target_by_email = {row["email"].casefold(): row["id"] for row in cursor.fetchall()}
    return {
        row["id"]: target_by_email.get(row["email"].casefold(), row["id"])
        for row in source_users
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument(
        "--byte-budget",
        type=int,
        default=24 * 1024 * 1024,
        help="Tamanho maximo aproximado de um lote (padrao: 24 MiB)",
    )
    args = parser.parse_args()

    source_path = args.source.expanduser().resolve()
    if not source_path.exists():
        raise FileNotFoundError(source_path)

    sqlite_connection = sqlite3.connect(source_path)
    sqlite_connection.row_factory = sqlite3.Row
    mysql_connection = connect_mysql()
    try:
        with mysql_connection.cursor() as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        user_id_map: dict[int, int] = {}
        for table, order_by in TABLES:
            print(f"\nMigrando {table}...", flush=True)
            before, after = migrate_table(
                sqlite_connection,
                mysql_connection,
                table,
                order_by,
                args.batch_size,
                args.byte_budget,
                user_id_map,
            )
            print(f"{table}: destino {before} -> {after}", flush=True)
            if table == "users":
                user_id_map = build_user_id_map(sqlite_connection, mysql_connection)
                print(f"users: mapa de IDs {user_id_map}", flush=True)
    finally:
        mysql_connection.close()
        sqlite_connection.close()


if __name__ == "__main__":
    main()
