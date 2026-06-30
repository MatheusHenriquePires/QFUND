import hashlib
import json
import mimetypes
import os
import secrets
import time
import unicodedata
import uuid
import re
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse, unquote

import pymysql
import requests


BASE_DIR = Path(__file__).resolve().parent
GENERATED_DIR = BASE_DIR / "generated"
DEFAULT_IMAGE_CACHE = GENERATED_DIR / "db_images"


class MySQLConnection:
    """
    Pequeno wrapper para manter o padrão antigo do projeto:
    connection.execute(...), connection.executemany(...) e fetchone/fetchall.
    """

    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql: str, params=None):
        cursor = self.connection.cursor()
        cursor.execute(sql, params or ())
        return cursor

    def executemany(self, sql: str, params_seq):
        cursor = self.connection.cursor()
        if params_seq:
            cursor.executemany(sql, params_seq)
        return cursor

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()


class Database:
    """
    Versão MySQL/MariaDB para o QFUND.

    Configure no .env:

    DB_HOST=127.0.0.1
    DB_PORT=3307
    DB_NAME=qfund
    DB_USER=root
    DB_PASSWORD=

    Ou use DATABASE_URL:

    DATABASE_URL=mysql+pymysql://root:@127.0.0.1:3307/qfund
    """

    def __init__(self, path: str | Path | None = None):
        # O parâmetro path fica apenas para compatibilidade com o código antigo.
        # No MySQL o banco é definido por DB_NAME ou DATABASE_URL.
        self.config = self._load_config()
        GENERATED_DIR.mkdir(parents=True, exist_ok=True)

        image_cache_dir = os.getenv("IMAGE_CACHE_DIR")
        self.image_cache = Path(image_cache_dir).expanduser().resolve() if image_cache_dir else DEFAULT_IMAGE_CACHE
        self.image_cache.mkdir(parents=True, exist_ok=True)

        self._ensure_database_exists()
        self._initialize()

    def _load_config(self):
        database_url = os.getenv("DATABASE_URL", "").strip()

        if database_url:
            parsed = urlparse(database_url)
            db_name = parsed.path.lstrip("/") or "qfund"
            return {
                "host": parsed.hostname or "127.0.0.1",
                "port": int(parsed.port or 3307),
                "user": unquote(parsed.username or "root"),
                "password": unquote(parsed.password or ""),
                "database": db_name,
            }

        return {
            "host": os.getenv("DB_HOST", "127.0.0.1"),
            "port": int(os.getenv("DB_PORT", "3307")),
            "user": os.getenv("DB_USER", "root"),
            "password": os.getenv("DB_PASSWORD", ""),
            "database": os.getenv("DB_NAME", "qfund"),
        }

    def _quote_database_name(self, name: str):
        if not re.fullmatch(r"[A-Za-z0-9_]+", name or ""):
            raise ValueError("DB_NAME inválido. Use apenas letras, números e underscore. Exemplo: qfund")
        return f"`{name}`"

    def _connect_raw(self, database: str | None = None):
        return pymysql.connect(
            host=self.config["host"],
            port=self.config["port"],
            user=self.config["user"],
            password=self.config["password"],
            database=database,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )

    def _ensure_database_exists(self):
        database_name = self.config["database"]
        quoted_database = self._quote_database_name(database_name)

        connection = self._connect_raw(database=None)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS {quoted_database} "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            connection.commit()
        finally:
            connection.close()

    @contextmanager
    def connect(self):
        connection = self._connect_raw(database=self.config["database"])
        wrapped = MySQLConnection(connection)
        try:
            wrapped.execute("SET SESSION group_concat_max_len = 1000000")
            yield wrapped
            wrapped.commit()
        except Exception:
            wrapped.rollback()
            raise
        finally:
            wrapped.close()

    def _initialize(self):
        with self.connect() as connection:
            self._create_tables(connection)
            self._ensure_question_columns(connection)
            self._seed_grade_levels(connection)
            self._create_views(connection)
            self._import_legacy_history(connection)

    def _create_tables(self, connection):
        statements = [
            """
            CREATE TABLE IF NOT EXISTS users (
                id INT NOT NULL AUTO_INCREMENT,
                email VARCHAR(255) NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                name VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL DEFAULT 'professor',
                preferred_subject VARCHAR(255) NULL,
                created_at BIGINT NOT NULL,
                PRIMARY KEY (id),
                UNIQUE KEY uq_users_email (email)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash CHAR(64) NOT NULL,
                user_id INT NOT NULL,
                expires_at BIGINT NOT NULL,
                created_at BIGINT NOT NULL,
                PRIMARY KEY (token_hash),
                KEY idx_sessions_user (user_id),
                CONSTRAINT fk_sessions_user
                    FOREIGN KEY (user_id) REFERENCES users(id)
                    ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS disciplines (
                id VARCHAR(64) NOT NULL,
                name VARCHAR(255) NOT NULL,
                normalized_name VARCHAR(255) NOT NULL,
                active TINYINT NOT NULL DEFAULT 1,
                updated_at BIGINT NOT NULL,
                PRIMARY KEY (id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS contents (
                id VARCHAR(128) NOT NULL,
                discipline_id VARCHAR(64) NOT NULL,
                parent_id VARCHAR(128) NULL,
                name VARCHAR(255) NOT NULL,
                normalized_name VARCHAR(255) NOT NULL,
                path TEXT NOT NULL,
                normalized_path TEXT NOT NULL,
                depth INT NOT NULL,
                updated_at BIGINT NOT NULL,
                PRIMARY KEY (id),
                KEY idx_contents_discipline_path (discipline_id, normalized_name),
                KEY idx_contents_parent (parent_id),
                CONSTRAINT fk_contents_discipline
                    FOREIGN KEY (discipline_id) REFERENCES disciplines(id)
                    ON DELETE CASCADE,
                CONSTRAINT fk_contents_parent
                    FOREIGN KEY (parent_id) REFERENCES contents(id)
                    ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS grade_levels (
                code VARCHAR(10) NOT NULL,
                segment_id VARCHAR(20) NOT NULL,
                name VARCHAR(100) NOT NULL,
                education_level VARCHAR(100) NOT NULL,
                position INT NOT NULL,
                PRIMARY KEY (code),
                UNIQUE KEY uq_grade_segment (segment_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS questions (
                id BIGINT NOT NULL AUTO_INCREMENT,
                storage_key VARCHAR(512) NOT NULL,
                external_id VARCHAR(255) NULL,
                discipline_id VARCHAR(64) NULL,
                series VARCHAR(20) NULL,
                owner_user_id INT NULL,
                kind VARCHAR(120) NULL,
                statement LONGTEXT NOT NULL,
                alternatives_json LONGTEXT NOT NULL,
                answer LONGTEXT NULL,
                resolution LONGTEXT NULL,
                content_json LONGTEXT NULL,
                difficulty VARCHAR(120) NULL,
                year VARCHAR(40) NULL,
                origin VARCHAR(120) NULL,
                credits_json LONGTEXT NOT NULL,
                extra_json LONGTEXT NOT NULL,
                created_at BIGINT NOT NULL,
                updated_at BIGINT NOT NULL,
                question_type_label VARCHAR(255) NULL,
                knowledge_area TEXT NULL,
                skill TEXT NULL,
                keywords TEXT NULL,
                tags_json LONGTEXT NULL,
                expected_answer LONGTEXT NULL,
                raw_json LONGTEXT NULL,
                last_synced_at BIGINT NULL,
                PRIMARY KEY (id),
                UNIQUE KEY uq_questions_storage_key (storage_key),
                KEY idx_questions_filters (discipline_id, series, difficulty, kind),
                KEY idx_questions_external (discipline_id, external_id),
                KEY idx_questions_owner (owner_user_id),
                CONSTRAINT fk_questions_owner
                    FOREIGN KEY (owner_user_id) REFERENCES users(id)
                    ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS question_contents (
                question_id BIGINT NOT NULL,
                content_id VARCHAR(128) NOT NULL,
                is_primary TINYINT NOT NULL DEFAULT 0,
                PRIMARY KEY (question_id, content_id),
                KEY idx_question_contents_content (content_id),
                CONSTRAINT fk_question_contents_question
                    FOREIGN KEY (question_id) REFERENCES questions(id)
                    ON DELETE CASCADE,
                CONSTRAINT fk_question_contents_content
                    FOREIGN KEY (content_id) REFERENCES contents(id)
                    ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS question_grades (
                question_id BIGINT NOT NULL,
                grade_code VARCHAR(10) NOT NULL,
                PRIMARY KEY (question_id, grade_code),
                KEY idx_question_grades_grade (grade_code, question_id),
                CONSTRAINT fk_question_grades_question
                    FOREIGN KEY (question_id) REFERENCES questions(id)
                    ON DELETE CASCADE,
                CONSTRAINT fk_question_grades_grade
                    FOREIGN KEY (grade_code) REFERENCES grade_levels(code)
                    ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS question_images (
                id BIGINT NOT NULL AUTO_INCREMENT,
                question_id BIGINT NOT NULL,
                source_url TEXT NULL,
                mime_type VARCHAR(255) NOT NULL DEFAULT 'application/octet-stream',
                content LONGBLOB NOT NULL,
                sha256 CHAR(64) NOT NULL,
                created_at BIGINT NOT NULL,
                PRIMARY KEY (id),
                UNIQUE KEY uq_question_image_sha (question_id, sha256),
                KEY idx_question_images_question (question_id),
                CONSTRAINT fk_question_images_question
                    FOREIGN KEY (question_id) REFERENCES questions(id)
                    ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS activities (
                id VARCHAR(36) NOT NULL,
                user_id INT NULL,
                kind VARCHAR(80) NOT NULL,
                responsible VARCHAR(255) NULL,
                filename TEXT NOT NULL,
                metadata_json LONGTEXT NOT NULL,
                created_at BIGINT NOT NULL,
                PRIMARY KEY (id),
                KEY idx_activities_user_created (user_id, created_at),
                CONSTRAINT fk_activities_user
                    FOREIGN KEY (user_id) REFERENCES users(id)
                    ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS app_meta (
                `key` VARCHAR(191) NOT NULL,
                value TEXT NULL,
                PRIMARY KEY (`key`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS sync_runs (
                id VARCHAR(36) NOT NULL,
                status VARCHAR(50) NOT NULL,
                phase VARCHAR(80) NOT NULL,
                current_discipline VARCHAR(255) NULL,
                current_grade VARCHAR(50) NULL,
                total_disciplines INT NOT NULL DEFAULT 0,
                completed_disciplines INT NOT NULL DEFAULT 0,
                questions_seen INT NOT NULL DEFAULT 0,
                questions_stored INT NOT NULL DEFAULT 0,
                images_stored INT NOT NULL DEFAULT 0,
                error LONGTEXT NULL,
                started_at BIGINT NOT NULL,
                finished_at BIGINT NULL,
                PRIMARY KEY (id),
                KEY idx_sync_runs_started (started_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
        ]

        for statement in statements:
            connection.execute(statement)

    def _ensure_question_columns(self, connection):
        existing_rows = connection.execute("SHOW COLUMNS FROM questions").fetchall()
        existing = {row["Field"] for row in existing_rows}

        columns = {
            "question_type_label": "VARCHAR(255) NULL",
            "knowledge_area": "TEXT NULL",
            "skill": "TEXT NULL",
            "keywords": "TEXT NULL",
            "tags_json": "LONGTEXT NULL",
            "expected_answer": "LONGTEXT NULL",
            "raw_json": "LONGTEXT NULL",
            "last_synced_at": "BIGINT NULL",
        }

        for name, definition in columns.items():
            if name not in existing:
                connection.execute(f"ALTER TABLE questions ADD COLUMN {name} {definition}")

    def _seed_grade_levels(self, connection):
        levels = [
            ("EF1", "0003", "1º ano", "Ensino Fundamental I", 1),
            ("EF2", "0004", "2º ano", "Ensino Fundamental I", 2),
            ("EF3", "0005", "3º ano", "Ensino Fundamental I", 3),
            ("EF4", "0006", "4º ano", "Ensino Fundamental I", 4),
            ("EF5", "0007", "5º ano", "Ensino Fundamental I", 5),
            ("EF6", "0008", "6º ano", "Ensino Fundamental II", 6),
            ("EF7", "0009", "7º ano", "Ensino Fundamental II", 7),
            ("EF8", "0010", "8º ano", "Ensino Fundamental II", 8),
            ("EF9", "0011", "9º ano", "Ensino Fundamental II", 9),
            ("EM1", "0012", "1º ano EM", "Ensino Médio", 10),
            ("EM2", "0013", "2º ano EM", "Ensino Médio", 11),
            ("EM3", "0014", "3º ano EM", "Ensino Médio", 12),
        ]

        connection.executemany(
            """
            INSERT INTO grade_levels(code, segment_id, name, education_level, position)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                segment_id = VALUES(segment_id),
                name = VALUES(name),
                education_level = VALUES(education_level),
                position = VALUES(position)
            """,
            levels,
        )

    def _create_views(self, connection):
        connection.execute("DROP VIEW IF EXISTS question_bank_view")
        connection.execute(
            """
            CREATE VIEW question_bank_view AS
            SELECT
                q.id,
                q.external_id AS api_id,
                d.name AS disciplina,
                q.kind AS tipo,
                q.difficulty AS dificuldade,
                q.year AS ano,
                q.origin AS origem,
                q.knowledge_area AS area_conhecimento,
                q.skill AS habilidade,
                q.statement AS enunciado,
                q.answer AS gabarito,
                q.expected_answer AS resposta_esperada,
                (
                    SELECT GROUP_CONCAT(qg.grade_code)
                    FROM question_grades qg
                    WHERE qg.question_id = q.id
                ) AS series,
                (
                    SELECT c.path
                    FROM question_contents qc
                    JOIN contents c ON c.id = qc.content_id
                    WHERE qc.question_id = q.id
                    ORDER BY qc.is_primary DESC, c.depth DESC
                    LIMIT 1
                ) AS conteudo,
                (
                    SELECT COUNT(*)
                    FROM question_images qi
                    WHERE qi.question_id = q.id
                ) AS quantidade_imagens,
                q.last_synced_at AS sincronizada_em
            FROM questions q
            LEFT JOIN disciplines d ON d.id = q.discipline_id
            """
        )

        connection.execute("DROP VIEW IF EXISTS question_bank_summary")
        connection.execute(
            """
            CREATE VIEW question_bank_summary AS
            SELECT
                d.name AS disciplina,
                q.kind AS tipo,
                q.difficulty AS dificuldade,
                COUNT(*) AS quantidade
            FROM questions q
            LEFT JOIN disciplines d ON d.id = q.discipline_id
            GROUP BY d.name, q.kind, q.difficulty
            """
        )

    def _import_legacy_history(self, connection):
        imported = connection.execute(
            "SELECT value FROM app_meta WHERE `key` = 'legacy_history_imported'"
        ).fetchone()

        if imported:
            return

        history_path = BASE_DIR / "generated" / "history.json"

        try:
            records = json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() else []
        except (OSError, json.JSONDecodeError):
            records = []

        for record in records if isinstance(records, list) else []:
            connection.execute(
                """
                INSERT IGNORE INTO activities
                    (id, user_id, kind, responsible, filename, metadata_json, created_at)
                VALUES (%s, NULL, %s, %s, %s, %s, %s)
                """,
                (
                    str(record.get("id") or uuid.uuid4()),
                    record.get("tipo") or "usuario",
                    record.get("responsavel"),
                    record.get("arquivo") or "",
                    json.dumps(record.get("meta") or {}, ensure_ascii=False),
                    int(record.get("ts") or time.time()),
                ),
            )

        connection.execute(
            "INSERT INTO app_meta(`key`, value) VALUES ('legacy_history_imported', %s)",
            (str(int(time.time())),),
        )

    def create_user(self, email: str, password_hash: str, name: str, role: str):
        now = int(time.time())

        try:
            with self.connect() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO users(email, password_hash, name, role, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (email.strip().lower(), password_hash, name.strip(), role, now),
                )

                user_id = cursor.lastrowid

                user_count = connection.execute(
                    "SELECT COUNT(*) AS total FROM users"
                ).fetchone()["total"]

                if user_count == 1:
                    connection.execute(
                        "UPDATE activities SET user_id = %s WHERE user_id IS NULL",
                        (user_id,),
                    )

        except pymysql.err.IntegrityError as exc:
            raise ValueError("Este e-mail já está cadastrado") from exc

        return self.get_user(user_id)

    def get_user(self, user_id: int):
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE id = %s",
                (user_id,),
            ).fetchone()

        return dict(row) if row else None

    def get_user_by_email(self, email: str):
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE LOWER(email) = LOWER(%s)",
                (email.strip(),),
            ).fetchone()

        return dict(row) if row else None

    def update_user(self, user_id: int, name: str, role: str, preferred_subject: str | None):
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE users
                SET name = %s, role = %s, preferred_subject = %s
                WHERE id = %s
                """,
                (name.strip(), role, preferred_subject, user_id),
            )

        return self.get_user(user_id)

    def create_session(self, user_id: int, lifetime_seconds: int):
        session_id = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(session_id.encode()).hexdigest()
        now = int(time.time())

        with self.connect() as connection:
            connection.execute("DELETE FROM sessions WHERE expires_at <= %s", (now,))
            connection.execute(
                """
                INSERT INTO sessions(token_hash, user_id, expires_at, created_at)
                VALUES (%s, %s, %s, %s)
                """,
                (token_hash, user_id, now + lifetime_seconds, now),
            )

        return session_id

    def user_from_session(self, session_id: str | None):
        if not session_id:
            return None

        token_hash = hashlib.sha256(session_id.encode()).hexdigest()
        now = int(time.time())

        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT users.*
                FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE sessions.token_hash = %s
                  AND sessions.expires_at > %s
                """,
                (token_hash, now),
            ).fetchone()

        return dict(row) if row else None

    def delete_session(self, session_id: str | None):
        if not session_id:
            return

        token_hash = hashlib.sha256(session_id.encode()).hexdigest()

        with self.connect() as connection:
            connection.execute(
                "DELETE FROM sessions WHERE token_hash = %s",
                (token_hash,),
            )

    def normalize_text(self, value):
        text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
        text = "".join(char for char in text if not unicodedata.combining(char))
        return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()

    def sync_catalog(self, subjects: list[dict]):
        now = int(time.time())

        with self.connect() as connection:
            for subject in subjects or []:
                discipline_id = str(subject.get("id") or "").strip()
                name = str(subject.get("name") or "").strip()

                if not discipline_id or not name:
                    continue

                connection.execute(
                    """
                    INSERT INTO disciplines(id, name, normalized_name, active, updated_at)
                    VALUES (%s, %s, %s, 1, %s)
                    ON DUPLICATE KEY UPDATE
                        name = VALUES(name),
                        normalized_name = VALUES(normalized_name),
                        active = 1,
                        updated_at = VALUES(updated_at)
                    """,
                    (discipline_id, name, self.normalize_text(name), now),
                )

                self._sync_content_nodes(
                    connection,
                    discipline_id,
                    subject.get("subitens") or [],
                    parent_id=None,
                    ancestors=[name],
                    depth=1,
                    now=now,
                )

    def _sync_content_nodes(self, connection, discipline_id, nodes, parent_id, ancestors, depth, now):
        for node in nodes or []:
            content_id = str(node.get("id") or "").strip()
            name = str(node.get("name") or node.get("nome") or "").strip()

            if not content_id or not name:
                continue

            path_parts = [*ancestors, name]
            path = " > ".join(path_parts)

            connection.execute(
                """
                INSERT INTO contents(
                    id, discipline_id, parent_id, name, normalized_name,
                    path, normalized_path, depth, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    discipline_id = VALUES(discipline_id),
                    parent_id = VALUES(parent_id),
                    name = VALUES(name),
                    normalized_name = VALUES(normalized_name),
                    path = VALUES(path),
                    normalized_path = VALUES(normalized_path),
                    depth = VALUES(depth),
                    updated_at = VALUES(updated_at)
                """,
                (
                    content_id,
                    discipline_id,
                    parent_id,
                    name,
                    self.normalize_text(name),
                    path,
                    self.normalize_text(path),
                    depth,
                    now,
                ),
            )

            self._sync_content_nodes(
                connection,
                discipline_id,
                node.get("subitens") or [],
                content_id,
                path_parts,
                depth + 1,
                now,
            )

    def link_question_content(self, question_id: int, discipline_id: str, breadcrumb):
        normalized = self.normalize_text(breadcrumb)

        if not normalized:
            return

        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT id
                FROM contents
                WHERE discipline_id = %s
                  AND normalized_path = %s
                ORDER BY depth DESC
                LIMIT 1
                """,
                (discipline_id, normalized),
            ).fetchone()

            if not row:
                row = connection.execute(
                    """
                    SELECT id
                    FROM contents
                    WHERE discipline_id = %s
                      AND %s LIKE CONCAT('%%', normalized_path)
                    ORDER BY depth DESC
                    LIMIT 1
                    """,
                    (discipline_id, normalized),
                ).fetchone()

            if row:
                connection.execute(
                    """
                    INSERT IGNORE INTO question_contents(question_id, content_id, is_primary)
                    VALUES (%s, %s, 1)
                    """,
                    (question_id, row["id"]),
                )

    def link_question_grade(self, question_id: int, grade_code: str):
        with self.connect() as connection:
            connection.execute(
                """
                INSERT IGNORE INTO question_grades(question_id, grade_code)
                SELECT %s, code
                FROM grade_levels
                WHERE code = %s
                """,
                (question_id, str(grade_code).upper()),
            )

    def link_external_question_grade(self, discipline_id: str, external_id, grade_code: str):
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT id
                FROM questions
                WHERE discipline_id = %s
                  AND external_id = %s
                ORDER BY id
                LIMIT 1
                """,
                (str(discipline_id), str(external_id)),
            ).fetchone()

        if not row:
            return False

        self.link_question_grade(row["id"], grade_code)
        return True

    def link_external_questions_grade(self, discipline_id: str, external_ids, grade_code: str):
        ids = [str(value) for value in external_ids if value is not None]

        if not ids:
            return []

        placeholders = ",".join(["%s"] * len(ids))

        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT id, external_id
                FROM questions
                WHERE discipline_id = %s
                  AND external_id IN ({placeholders})
                """,
                [str(discipline_id), *ids],
            ).fetchall()

            connection.executemany(
                """
                INSERT IGNORE INTO question_grades(question_id, grade_code)
                VALUES (%s, %s)
                """,
                [(row["id"], grade_code) for row in rows],
            )

        found = {row["external_id"] for row in rows}
        return [value for value in ids if value not in found]

    def start_sync_run(self, total_disciplines: int):
        run_id = str(uuid.uuid4())

        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO sync_runs(
                    id, status, phase, total_disciplines, started_at
                ) VALUES (%s, 'running', 'catalog', %s, %s)
                """,
                (run_id, total_disciplines, int(time.time())),
            )

        return run_id

    def update_sync_run(self, run_id: str, **values):
        allowed = {
            "status",
            "phase",
            "current_discipline",
            "current_grade",
            "total_disciplines",
            "completed_disciplines",
            "questions_seen",
            "questions_stored",
            "images_stored",
            "error",
            "finished_at",
        }

        values = {key: value for key, value in values.items() if key in allowed}

        if not values:
            return

        assignments = ", ".join(f"{key} = %s" for key in values)

        with self.connect() as connection:
            connection.execute(
                f"UPDATE sync_runs SET {assignments} WHERE id = %s",
                [*values.values(), run_id],
            )

    def latest_sync_run(self):
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM sync_runs ORDER BY started_at DESC LIMIT 1"
            ).fetchone()

        return dict(row) if row else None

    def bank_statistics(self):
        with self.connect() as connection:
            return {
                "disciplinas": connection.execute(
                    "SELECT COUNT(*) AS total FROM disciplines"
                ).fetchone()["total"],
                "conteudos": connection.execute(
                    "SELECT COUNT(*) AS total FROM contents"
                ).fetchone()["total"],
                "questoes": connection.execute(
                    "SELECT COUNT(*) AS total FROM questions"
                ).fetchone()["total"],
                "imagens": connection.execute(
                    "SELECT COUNT(*) AS total FROM question_images"
                ).fetchone()["total"],
                "questoes_com_serie": connection.execute(
                    "SELECT COUNT(DISTINCT question_id) AS total FROM question_grades"
                ).fetchone()["total"],
                "questoes_com_conteudo": connection.execute(
                    "SELECT COUNT(DISTINCT question_id) AS total FROM question_contents"
                ).fetchone()["total"],
            }

    def upsert_question(
        self,
        question: dict,
        discipline_id: str | None = None,
        series: str | None = None,
        owner_user_id: int | None = None,
        hydrate: bool = True,
        download_images: bool = True,
    ):
        external_id = str(question.get("id") or uuid.uuid4())
        origin = str(question.get("origem") or "bernoulli")
        storage_key = f"{origin}:{discipline_id or ''}:{external_id}"
        now = int(time.time())

        known_fields = {
            "id",
            "tipo",
            "enunciado",
            "alternativas",
            "gabarito",
            "resolucao",
            "conteudo",
            "dificuldade",
            "ano",
            "origem",
            "creditos_imagem",
            "imagens",
            "_imagem_ids",
            "_db_id",
            "linhas_resposta",
            "area",
            "keywords",
            "habilidade",
            "tags",
            "tipo_api",
            "resposta_esperada",
            "raw",
        }

        extra = {key: value for key, value in question.items() if key not in known_fields}

        if question.get("linhas_resposta") is not None:
            extra["linhas_resposta"] = question["linhas_resposta"]

        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO questions(
                    storage_key, external_id, discipline_id, series, owner_user_id, kind,
                    statement, alternatives_json, answer, resolution, content_json,
                    difficulty, year, origin, credits_json, extra_json, created_at, updated_at,
                    question_type_label, knowledge_area, skill, keywords, tags_json,
                    expected_answer, raw_json, last_synced_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s
                )
                ON DUPLICATE KEY UPDATE
                    series = COALESCE(VALUES(series), series),
                    owner_user_id = COALESCE(VALUES(owner_user_id), owner_user_id),
                    kind = VALUES(kind),
                    statement = VALUES(statement),
                    alternatives_json = VALUES(alternatives_json),
                    answer = VALUES(answer),
                    resolution = VALUES(resolution),
                    content_json = VALUES(content_json),
                    difficulty = VALUES(difficulty),
                    year = VALUES(year),
                    credits_json = VALUES(credits_json),
                    extra_json = VALUES(extra_json),
                    question_type_label = VALUES(question_type_label),
                    knowledge_area = VALUES(knowledge_area),
                    skill = VALUES(skill),
                    keywords = VALUES(keywords),
                    tags_json = VALUES(tags_json),
                    expected_answer = VALUES(expected_answer),
                    raw_json = VALUES(raw_json),
                    last_synced_at = VALUES(last_synced_at),
                    updated_at = VALUES(updated_at)
                """,
                (
                    storage_key,
                    external_id,
                    str(discipline_id or ""),
                    series,
                    owner_user_id,
                    question.get("tipo"),
                    question.get("enunciado") or "",
                    json.dumps(question.get("alternativas") or [], ensure_ascii=False),
                    question.get("gabarito"),
                    question.get("resolucao"),
                    json.dumps(question.get("conteudo"), ensure_ascii=False),
                    question.get("dificuldade"),
                    str(question.get("ano") or "") or None,
                    origin,
                    json.dumps(question.get("creditos_imagem") or [], ensure_ascii=False),
                    json.dumps(extra, ensure_ascii=False),
                    now,
                    now,
                    question.get("tipo_api"),
                    question.get("area"),
                    question.get("habilidade"),
                    self._json_text(question.get("keywords")),
                    json.dumps(question.get("tags") or [], ensure_ascii=False),
                    question.get("resposta_esperada"),
                    json.dumps(question.get("raw") or {}, ensure_ascii=False, default=str),
                    now,
                ),
            )

            row = connection.execute(
                "SELECT id FROM questions WHERE storage_key = %s",
                (storage_key,),
            ).fetchone()

            question_id = row["id"]

        if series:
            self.link_question_grade(question_id, series)

        self.link_question_content(question_id, str(discipline_id or ""), question.get("conteudo"))

        if download_images:
            for image_url in question.get("imagens") or []:
                self._store_remote_image(question_id, image_url)

        if not hydrate:
            return {"id": question_id, "external_id": external_id}

        stored = self.get_question(question_id)

        if stored:
            question.clear()
            question.update(stored)

        return stored

    def upsert_questions_batch(
        self,
        questions: list[dict],
        discipline_id: str,
        series: str | None = None,
        download_images: bool = True,
    ):
        if not questions:
            return 0

        now = int(time.time())
        discipline_id = str(discipline_id)
        rows = []
        keys = []

        for question in questions:
            external_id = str(question.get("id") or uuid.uuid4())
            origin = str(question.get("origem") or "bernoulli")
            storage_key = f"{origin}:{discipline_id}:{external_id}"
            keys.append(storage_key)

            known_fields = {
                "id",
                "tipo",
                "enunciado",
                "alternativas",
                "gabarito",
                "resolucao",
                "conteudo",
                "dificuldade",
                "ano",
                "origem",
                "creditos_imagem",
                "imagens",
                "_imagem_ids",
                "_db_id",
                "linhas_resposta",
                "area",
                "keywords",
                "habilidade",
                "tags",
                "tipo_api",
                "resposta_esperada",
                "raw",
            }

            extra = {key: value for key, value in question.items() if key not in known_fields}

            if question.get("linhas_resposta") is not None:
                extra["linhas_resposta"] = question["linhas_resposta"]

            rows.append(
                (
                    storage_key,
                    external_id,
                    discipline_id,
                    None,
                    None,
                    question.get("tipo"),
                    question.get("enunciado") or "",
                    json.dumps(question.get("alternativas") or [], ensure_ascii=False),
                    question.get("gabarito"),
                    question.get("resolucao"),
                    json.dumps(question.get("conteudo"), ensure_ascii=False),
                    question.get("dificuldade"),
                    str(question.get("ano") or "") or None,
                    origin,
                    json.dumps(question.get("creditos_imagem") or [], ensure_ascii=False),
                    json.dumps(extra, ensure_ascii=False),
                    now,
                    now,
                    question.get("tipo_api"),
                    question.get("area"),
                    question.get("habilidade"),
                    self._json_text(question.get("keywords")),
                    json.dumps(question.get("tags") or [], ensure_ascii=False),
                    question.get("resposta_esperada"),
                    json.dumps(question.get("raw") or {}, ensure_ascii=False, default=str),
                    now,
                )
            )

        sql = """
            INSERT INTO questions(
                storage_key, external_id, discipline_id, series, owner_user_id, kind,
                statement, alternatives_json, answer, resolution, content_json,
                difficulty, year, origin, credits_json, extra_json, created_at, updated_at,
                question_type_label, knowledge_area, skill, keywords, tags_json,
                expected_answer, raw_json, last_synced_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s
            )
            ON DUPLICATE KEY UPDATE
                kind = VALUES(kind),
                statement = VALUES(statement),
                alternatives_json = VALUES(alternatives_json),
                answer = VALUES(answer),
                resolution = VALUES(resolution),
                content_json = VALUES(content_json),
                difficulty = VALUES(difficulty),
                year = VALUES(year),
                credits_json = VALUES(credits_json),
                extra_json = VALUES(extra_json),
                question_type_label = VALUES(question_type_label),
                knowledge_area = VALUES(knowledge_area),
                skill = VALUES(skill),
                keywords = VALUES(keywords),
                tags_json = VALUES(tags_json),
                expected_answer = VALUES(expected_answer),
                raw_json = VALUES(raw_json),
                last_synced_at = VALUES(last_synced_at),
                updated_at = VALUES(updated_at)
        """

        with self.connect() as connection:
            connection.executemany(sql, rows)

            placeholders = ",".join(["%s"] * len(keys))
            stored_rows = connection.execute(
                f"SELECT id, storage_key FROM questions WHERE storage_key IN ({placeholders})",
                keys,
            ).fetchall()

            question_ids = {row["storage_key"]: row["id"] for row in stored_rows}

            content_rows = connection.execute(
                "SELECT id, normalized_path FROM contents WHERE discipline_id = %s",
                (discipline_id,),
            ).fetchall()

            content_map = {row["normalized_path"]: row["id"] for row in content_rows}
            content_links = []
            image_jobs = []

            for question, storage_key in zip(questions, keys):
                question_id = question_ids.get(storage_key)

                if not question_id:
                    continue

                content_id = content_map.get(self.normalize_text(question.get("conteudo")))

                if content_id:
                    content_links.append((question_id, content_id, 1))

                image_jobs.extend(
                    (question_id, source)
                    for source in question.get("imagens") or []
                    if source
                )

            if content_links:
                connection.executemany(
                    """
                    INSERT IGNORE INTO question_contents(question_id, content_id, is_primary)
                    VALUES (%s, %s, %s)
                    """,
                    content_links,
                )

            if series:
                connection.executemany(
                    """
                    INSERT IGNORE INTO question_grades(question_id, grade_code)
                    VALUES (%s, %s)
                    """,
                    [(question_id, str(series).upper()) for question_id in question_ids.values()],
                )

        if download_images and image_jobs:
            with ThreadPoolExecutor(max_workers=8) as executor:
                list(executor.map(lambda job: self._store_remote_image(*job), image_jobs))

        return len(stored_rows)

    def _json_text(self, value):
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False)

        return str(value or "") or None

    def _store_remote_image(self, question_id: int, source: str):
        if not source:
            return False

        try:
            with self.connect() as connection:
                existing = connection.execute(
                    """
                    SELECT id
                    FROM question_images
                    WHERE question_id = %s
                      AND source_url = %s
                    LIMIT 1
                    """,
                    (question_id, str(source)),
                ).fetchone()

            if existing:
                return False

            if str(source).startswith(("http://", "https://")):
                response = requests.get(
                    source,
                    headers={"User-Agent": "QFund Image Storage"},
                    timeout=(3, 8),
                )
                response.raise_for_status()
                content = response.content
                mime_type = response.headers.get("Content-Type", "").split(";", 1)[0]
            else:
                content = Path(source).read_bytes()
                mime_type = mimetypes.guess_type(str(source))[0]

            if not content:
                return False

            mime_type = mime_type or "application/octet-stream"
            digest = hashlib.sha256(content).hexdigest()

            with self.connect() as connection:
                cursor = connection.execute(
                    """
                    INSERT IGNORE INTO question_images(
                        question_id, source_url, mime_type, content, sha256, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        question_id,
                        str(source),
                        mime_type,
                        content,
                        digest,
                        int(time.time()),
                    ),
                )

                return cursor.rowcount > 0

        except (OSError, requests.RequestException, pymysql.MySQLError):
            return False

    def get_question(self, question_id: int):
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM questions WHERE id = %s",
                (question_id,),
            ).fetchone()

            images = connection.execute(
                """
                SELECT id, mime_type, sha256, content
                FROM question_images
                WHERE question_id = %s
                ORDER BY id
                """,
                (question_id,),
            ).fetchall()

        if not row:
            return None

        return self._question_dict(row, images)

    def list_questions(self, discipline_id: str, series: str | None = None):
        query = "SELECT * FROM questions WHERE discipline_id = %s"
        params: list = [str(discipline_id)]

        if series:
            query += """
                AND (
                    EXISTS (
                        SELECT 1
                        FROM question_grades qg
                        WHERE qg.question_id = questions.id
                          AND qg.grade_code = %s
                    )
                    OR (
                        NOT EXISTS (
                            SELECT 1
                            FROM question_grades qg2
                            WHERE qg2.question_id = questions.id
                        )
                        AND (series = %s OR series IS NULL OR series = '')
                    )
                )
            """
            params.append(series)
            params.append(series)

        query += " ORDER BY updated_at DESC"

        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
            result = []

            for row in rows:
                images = connection.execute(
                    """
                    SELECT id, mime_type, sha256, content
                    FROM question_images
                    WHERE question_id = %s
                    ORDER BY id
                    """,
                    (row["id"],),
                ).fetchall()

                result.append(self._question_dict(row, images))

        return result

    def search_questions(
        self,
        discipline_id: str,
        series: str | None = None,
        difficulty: str | None = None,
        kind: str | None = None,
        content_terms: list[str] | None = None,
        limit: int = 500,
    ):
        query = "SELECT * FROM questions WHERE discipline_id = %s"
        params: list = [str(discipline_id)]

        if series:
            query += """
                AND EXISTS (
                    SELECT 1
                    FROM question_grades qg
                    WHERE qg.question_id = questions.id
                      AND qg.grade_code = %s
                )
            """
            params.append(series)

        if difficulty:
            query += " AND LOWER(difficulty) = LOWER(%s)"
            params.append(difficulty)

        if kind:
            query += " AND LOWER(kind) = LOWER(%s)"
            params.append(kind)

        terms = [str(term).strip() for term in content_terms or [] if str(term).strip()]

        if terms:
            query += " AND (" + " OR ".join("content_json LIKE %s" for _ in terms) + ")"
            params.extend(f"%{term}%" for term in terms)

        query += " ORDER BY RAND() LIMIT %s"
        params.append(max(1, min(int(limit), 5000)))

        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
            result = []

            for row in rows:
                images = connection.execute(
                    """
                    SELECT id, mime_type, sha256, content
                    FROM question_images
                    WHERE question_id = %s
                    ORDER BY id
                    """,
                    (row["id"],),
                ).fetchall()

                result.append(self._question_dict(row, images))

        return result

    def _question_dict(self, row, images):
        try:
            content = json.loads(row.get("content_json") or "null")
        except json.JSONDecodeError:
            content = row.get("content_json")

        result = {
            "id": row.get("external_id"),
            "tipo": row.get("kind"),
            "enunciado": row.get("statement"),
            "alternativas": json.loads(row.get("alternatives_json") or "[]"),
            "gabarito": row.get("answer"),
            "resolucao": row.get("resolution"),
            "conteudo": content,
            "dificuldade": row.get("difficulty"),
            "ano": row.get("year"),
            "origem": row.get("origin"),
            "creditos_imagem": json.loads(row.get("credits_json") or "[]"),
            "tipo_api": row.get("question_type_label"),
            "area": row.get("knowledge_area"),
            "habilidade": row.get("skill"),
            "keywords": row.get("keywords"),
            "tags": json.loads(row.get("tags_json") or "[]"),
            "resposta_esperada": row.get("expected_answer"),
        }

        try:
            result.update(json.loads(row.get("extra_json") or "{}"))
        except json.JSONDecodeError:
            pass

        result["_db_id"] = row.get("id")
        result["_imagem_ids"] = [image["id"] for image in images]
        result["imagens"] = [self._materialize_image(image) for image in images]

        return result

    def _materialize_image(self, image):
        extension = mimetypes.guess_extension(image["mime_type"] or "") or ".bin"
        path = self.image_cache / f"{image['sha256']}{extension}"

        if not path.exists() or path.stat().st_size == 0:
            path.write_bytes(image["content"])

        return str(path)

    def get_image(self, image_id: int):
        with self.connect() as connection:
            row = connection.execute(
                "SELECT mime_type, content FROM question_images WHERE id = %s",
                (image_id,),
            ).fetchone()

        return (row["content"], row["mime_type"]) if row else None

    def add_activity(self, user_id, kind, filename, metadata, responsible=None):
        record_id = str(uuid.uuid4())
        now = int(time.time())

        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO activities(
                    id, user_id, kind, responsible, filename, metadata_json, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    record_id,
                    user_id,
                    kind or "usuario",
                    responsible,
                    filename,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    now,
                ),
            )

        return {
            "id": record_id,
            "tipo": kind or "usuario",
            "responsavel": responsible,
            "arquivo": filename,
            "meta": metadata or {},
            "ts": now,
        }

    def list_activities(self, user_id, kind=None, responsible=None):
        query = "SELECT * FROM activities WHERE user_id = %s"
        params: list = [user_id]

        if kind:
            query += " AND kind = %s"
            params.append(kind)

        if responsible:
            query += " AND responsible = %s"
            params.append(responsible)

        query += " ORDER BY created_at DESC"

        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()

        return [
            {
                "id": row["id"],
                "tipo": row["kind"],
                "responsavel": row["responsible"],
                "arquivo": row["filename"],
                "meta": json.loads(row["metadata_json"] or "{}"),
                "ts": row["created_at"],
            }
            for row in rows
        ]

    def activity_by_filename(self, user_id, filename):
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT id
                FROM activities
                WHERE user_id = %s
                  AND filename = %s
                """,
                (user_id, filename),
            ).fetchone()

        return bool(row)


db = Database()
