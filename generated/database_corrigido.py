import hashlib
import json
import mimetypes
import os
import shutil
import secrets
import sqlite3
import time
import unicodedata
import uuid
import re
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

import requests


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "generated" / "qfund.db"
IS_VERCEL = os.getenv("VERCEL") == "1"


def _as_project_path(value: str | Path) -> Path:
    """
    Resolve caminhos relativos a partir da raiz do projeto.
    Caminhos absolutos continuam absolutos.

    Local:
      generated/qfund.db -> <projeto>/generated/qfund.db

    Vercel:
      generated/qfund.db -> /var/task/generated/qfund.db
    """
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.resolve()


def _copy_db_to_tmp(source_db: Path, runtime_db: Path) -> None:
    """
    No Vercel, /var/task é somente leitura.
    Então copiamos o SQLite enviado no deploy para /tmp,
    que é o único local gravável em runtime.
    """
    runtime_db.parent.mkdir(parents=True, exist_ok=True)

    if source_db.exists():
        should_copy = (
            not runtime_db.exists()
            or source_db.stat().st_size != runtime_db.stat().st_size
            or int(source_db.stat().st_mtime) > int(runtime_db.stat().st_mtime)
        )
        if should_copy:
            shutil.copy2(source_db, runtime_db)
    elif not runtime_db.exists():
        # Permite iniciar com banco vazio em /tmp caso o qfund.db não tenha sido enviado no deploy.
        runtime_db.touch()


class Database:
    def __init__(self, path: str | Path | None = None):
        configured_path = path or os.getenv("DATABASE_PATH")

        if IS_VERCEL:
            # Importante:
            # A Vercel NÃO consegue ler C:\Users\... do seu computador.
            # Para produção, envie o arquivo generated/qfund.db junto com o projeto
            # ou use um storage/banco externo. Aqui copiamos o banco enviado no deploy
            # para /tmp/qfund.db antes de abrir o SQLite.
            source_db = _as_project_path(configured_path or DEFAULT_DB_PATH)
            self.path = Path("/tmp") / "qfund.db"
            _copy_db_to_tmp(source_db, self.path)
            self.image_cache = Path("/tmp") / "qfund_db_images"
        else:
            # Localmente, este caminho vira:
            # C:\Users\PENSAR\Documents\Matheus\QFUND\generated\qfund.db
            # desde que este arquivo esteja na raiz do projeto QFUND.
            self.path = _as_project_path(configured_path or DEFAULT_DB_PATH)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.image_cache = self.path.parent / "db_images"

        self.image_cache.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=30)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self):
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'professor',
                    preferred_subject TEXT,
                    created_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    expires_at INTEGER NOT NULL,
                    created_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    storage_key TEXT NOT NULL UNIQUE,
                    external_id TEXT,
                    discipline_id TEXT,
                    series TEXT,
                    owner_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    kind TEXT,
                    statement TEXT NOT NULL,
                    alternatives_json TEXT NOT NULL DEFAULT '[]',
                    answer TEXT,
                    resolution TEXT,
                    content_json TEXT,
                    difficulty TEXT,
                    year TEXT,
                    origin TEXT,
                    credits_json TEXT NOT NULL DEFAULT '[]',
                    extra_json TEXT NOT NULL DEFAULT '{}',
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_questions_filters
                ON questions(discipline_id, series, difficulty, kind);

                CREATE TABLE IF NOT EXISTS disciplines (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    normalized_name TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    updated_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS contents (
                    id TEXT PRIMARY KEY,
                    discipline_id TEXT NOT NULL REFERENCES disciplines(id) ON DELETE CASCADE,
                    parent_id TEXT REFERENCES contents(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    normalized_name TEXT NOT NULL,
                    path TEXT NOT NULL,
                    normalized_path TEXT NOT NULL,
                    depth INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_contents_discipline_path
                ON contents(discipline_id, normalized_path);

                CREATE TABLE IF NOT EXISTS grade_levels (
                    code TEXT PRIMARY KEY,
                    segment_id TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    education_level TEXT NOT NULL,
                    position INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS question_contents (
                    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
                    content_id TEXT NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
                    is_primary INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(question_id, content_id)
                );

                CREATE TABLE IF NOT EXISTS question_grades (
                    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
                    grade_code TEXT NOT NULL REFERENCES grade_levels(code) ON DELETE CASCADE,
                    PRIMARY KEY(question_id, grade_code)
                );

                CREATE INDEX IF NOT EXISTS idx_question_grades_grade
                ON question_grades(grade_code, question_id);

                CREATE TABLE IF NOT EXISTS question_images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
                    source_url TEXT,
                    mime_type TEXT NOT NULL DEFAULT 'application/octet-stream',
                    content BLOB NOT NULL,
                    sha256 TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    UNIQUE(question_id, sha256)
                );

                CREATE TABLE IF NOT EXISTS activities (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    kind TEXT NOT NULL,
                    responsible TEXT,
                    filename TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at INTEGER NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_activities_user_created
                ON activities(user_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS app_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );

                CREATE TABLE IF NOT EXISTS sync_runs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    current_discipline TEXT,
                    current_grade TEXT,
                    total_disciplines INTEGER NOT NULL DEFAULT 0,
                    completed_disciplines INTEGER NOT NULL DEFAULT 0,
                    questions_seen INTEGER NOT NULL DEFAULT 0,
                    questions_stored INTEGER NOT NULL DEFAULT 0,
                    images_stored INTEGER NOT NULL DEFAULT 0,
                    error TEXT,
                    started_at INTEGER NOT NULL,
                    finished_at INTEGER
                );
                """
            )
            self._ensure_question_columns(connection)
            self._seed_grade_levels(connection)
            self._create_views(connection)
            self._import_legacy_history(connection)

    def _ensure_question_columns(self, connection):
        existing = {
            row["name"] for row in connection.execute("PRAGMA table_info(questions)")
        }
        columns = {
            "question_type_label": "TEXT",
            "knowledge_area": "TEXT",
            "skill": "TEXT",
            "keywords": "TEXT",
            "tags_json": "TEXT NOT NULL DEFAULT '[]'",
            "expected_answer": "TEXT",
            "raw_json": "TEXT NOT NULL DEFAULT '{}'",
            "last_synced_at": "INTEGER",
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
            """INSERT INTO grade_levels(code, segment_id, name, education_level, position)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(code) DO UPDATE SET segment_id=excluded.segment_id,
               name=excluded.name, education_level=excluded.education_level,
               position=excluded.position""",
            levels,
        )

    def _create_views(self, connection):
        connection.executescript(
            """
            DROP VIEW IF EXISTS question_bank_view;
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
                (SELECT GROUP_CONCAT(qg.grade_code)
                 FROM question_grades qg WHERE qg.question_id = q.id) AS series,
                (SELECT c.path FROM question_contents qc
                 JOIN contents c ON c.id = qc.content_id
                 WHERE qc.question_id = q.id
                 ORDER BY qc.is_primary DESC, c.depth DESC LIMIT 1) AS conteudo,
                (SELECT COUNT(*) FROM question_images qi
                 WHERE qi.question_id = q.id) AS quantidade_imagens,
                q.last_synced_at AS sincronizada_em
            FROM questions q
            LEFT JOIN disciplines d ON d.id = q.discipline_id;

            DROP VIEW IF EXISTS question_bank_summary;
            CREATE VIEW question_bank_summary AS
            SELECT
                d.name AS disciplina,
                q.kind AS tipo,
                q.difficulty AS dificuldade,
                COUNT(*) AS quantidade
            FROM questions q
            LEFT JOIN disciplines d ON d.id = q.discipline_id
            GROUP BY d.name, q.kind, q.difficulty;
            """
        )

    def _import_legacy_history(self, connection):
        imported = connection.execute(
            "SELECT value FROM app_meta WHERE key = 'legacy_history_imported'"
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
                """INSERT OR IGNORE INTO activities
                   (id, user_id, kind, responsible, filename, metadata_json, created_at)
                   VALUES (?, NULL, ?, ?, ?, ?, ?)""",
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
            "INSERT INTO app_meta(key, value) VALUES ('legacy_history_imported', ?)",
            (str(int(time.time())),),
        )

    def create_user(self, email: str, password_hash: str, name: str, role: str):
        now = int(time.time())
        try:
            with self.connect() as connection:
                cursor = connection.execute(
                    """INSERT INTO users(email, password_hash, name, role, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (email.strip().lower(), password_hash, name.strip(), role, now),
                )
                user_id = cursor.lastrowid
                user_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
                if user_count == 1:
                    connection.execute(
                        "UPDATE activities SET user_id = ? WHERE user_id IS NULL", (user_id,)
                    )
        except sqlite3.IntegrityError as exc:
            raise ValueError("Este e-mail já está cadastrado") from exc
        return self.get_user(user_id)

    def get_user(self, user_id: int):
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

    def get_user_by_email(self, email: str):
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email.strip(),)
            ).fetchone()
        return dict(row) if row else None

    def update_user(self, user_id: int, name: str, role: str, preferred_subject: str | None):
        with self.connect() as connection:
            connection.execute(
                """UPDATE users SET name = ?, role = ?, preferred_subject = ? WHERE id = ?""",
                (name.strip(), role, preferred_subject, user_id),
            )
        return self.get_user(user_id)

    def create_session(self, user_id: int, lifetime_seconds: int):
        session_id = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(session_id.encode()).hexdigest()
        now = int(time.time())
        with self.connect() as connection:
            connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
            connection.execute(
                "INSERT INTO sessions(token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
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
                """SELECT users.* FROM sessions
                   JOIN users ON users.id = sessions.user_id
                   WHERE sessions.token_hash = ? AND sessions.expires_at > ?""",
                (token_hash, now),
            ).fetchone()
        return dict(row) if row else None

    def delete_session(self, session_id: str | None):
        if not session_id:
            return
        token_hash = hashlib.sha256(session_id.encode()).hexdigest()
        with self.connect() as connection:
            connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))

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
                    """INSERT INTO disciplines(id, name, normalized_name, active, updated_at)
                       VALUES (?, ?, ?, 1, ?)
                       ON CONFLICT(id) DO UPDATE SET name=excluded.name,
                       normalized_name=excluded.normalized_name, active=1,
                       updated_at=excluded.updated_at""",
                    (discipline_id, name, self.normalize_text(name), now),
                )
                self._sync_content_nodes(
                    connection, discipline_id, subject.get("subitens") or [],
                    parent_id=None, ancestors=[name], depth=1, now=now,
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
                """INSERT INTO contents(
                       id, discipline_id, parent_id, name, normalized_name,
                       path, normalized_path, depth, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET discipline_id=excluded.discipline_id,
                   parent_id=excluded.parent_id, name=excluded.name,
                   normalized_name=excluded.normalized_name, path=excluded.path,
                   normalized_path=excluded.normalized_path, depth=excluded.depth,
                   updated_at=excluded.updated_at""",
                (
                    content_id, discipline_id, parent_id, name, self.normalize_text(name),
                    path, self.normalize_text(path), depth, now,
                ),
            )
            self._sync_content_nodes(
                connection, discipline_id, node.get("subitens") or [],
                content_id, path_parts, depth + 1, now,
            )

    def link_question_content(self, question_id: int, discipline_id: str, breadcrumb):
        normalized = self.normalize_text(breadcrumb)
        if not normalized:
            return
        with self.connect() as connection:
            row = connection.execute(
                """SELECT id FROM contents
                   WHERE discipline_id = ? AND normalized_path = ?
                   ORDER BY depth DESC LIMIT 1""",
                (discipline_id, normalized),
            ).fetchone()
            if not row:
                row = connection.execute(
                    """SELECT id FROM contents
                       WHERE discipline_id = ? AND ? LIKE '%' || normalized_path
                       ORDER BY depth DESC LIMIT 1""",
                    (discipline_id, normalized),
                ).fetchone()
            if row:
                connection.execute(
                    """INSERT OR IGNORE INTO question_contents(question_id, content_id, is_primary)
                       VALUES (?, ?, 1)""",
                    (question_id, row["id"]),
                )

    def link_question_grade(self, question_id: int, grade_code: str):
        with self.connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO question_grades(question_id, grade_code)
                   SELECT ?, code FROM grade_levels WHERE code = ?""",
                (question_id, str(grade_code).upper()),
            )

    def link_external_question_grade(self, discipline_id: str, external_id, grade_code: str):
        with self.connect() as connection:
            row = connection.execute(
                """SELECT id FROM questions WHERE discipline_id = ? AND external_id = ?
                   ORDER BY id LIMIT 1""",
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
        placeholders = ",".join("?" for _ in ids)
        with self.connect() as connection:
            rows = connection.execute(
                f"""SELECT id, external_id FROM questions
                    WHERE discipline_id = ? AND external_id IN ({placeholders})""",
                [str(discipline_id), *ids],
            ).fetchall()
            connection.executemany(
                "INSERT OR IGNORE INTO question_grades(question_id, grade_code) VALUES (?, ?)",
                [(row["id"], grade_code) for row in rows],
            )
        found = {row["external_id"] for row in rows}
        return [value for value in ids if value not in found]

    def start_sync_run(self, total_disciplines: int):
        run_id = str(uuid.uuid4())
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO sync_runs(
                       id, status, phase, total_disciplines, started_at
                   ) VALUES (?, 'running', 'catalog', ?, ?)""",
                (run_id, total_disciplines, int(time.time())),
            )
        return run_id

    def update_sync_run(self, run_id: str, **values):
        allowed = {
            "status", "phase", "current_discipline", "current_grade",
            "total_disciplines", "completed_disciplines", "questions_seen",
            "questions_stored", "images_stored", "error", "finished_at",
        }
        values = {key: value for key, value in values.items() if key in allowed}
        if not values:
            return
        assignments = ", ".join(f"{key} = ?" for key in values)
        with self.connect() as connection:
            connection.execute(
                f"UPDATE sync_runs SET {assignments} WHERE id = ?",
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
                "disciplinas": connection.execute("SELECT COUNT(*) FROM disciplines").fetchone()[0],
                "conteudos": connection.execute("SELECT COUNT(*) FROM contents").fetchone()[0],
                "questoes": connection.execute("SELECT COUNT(*) FROM questions").fetchone()[0],
                "imagens": connection.execute("SELECT COUNT(*) FROM question_images").fetchone()[0],
                "questoes_com_serie": connection.execute(
                    "SELECT COUNT(DISTINCT question_id) FROM question_grades"
                ).fetchone()[0],
                "questoes_com_conteudo": connection.execute(
                    "SELECT COUNT(DISTINCT question_id) FROM question_contents"
                ).fetchone()[0],
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
            "id", "tipo", "enunciado", "alternativas", "gabarito", "resolucao",
            "conteudo", "dificuldade", "ano", "origem", "creditos_imagem",
            "imagens", "_imagem_ids", "_db_id", "linhas_resposta", "area", "keywords",
            "habilidade", "tags", "tipo_api", "resposta_esperada", "raw",
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
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(storage_key) DO UPDATE SET
                    series = COALESCE(excluded.series, questions.series),
                    owner_user_id = COALESCE(excluded.owner_user_id, questions.owner_user_id),
                    kind = excluded.kind, statement = excluded.statement,
                    alternatives_json = excluded.alternatives_json, answer = excluded.answer,
                    resolution = excluded.resolution, content_json = excluded.content_json,
                    difficulty = excluded.difficulty, year = excluded.year,
                    credits_json = excluded.credits_json, extra_json = excluded.extra_json,
                    question_type_label = excluded.question_type_label,
                    knowledge_area = excluded.knowledge_area, skill = excluded.skill,
                    keywords = excluded.keywords, tags_json = excluded.tags_json,
                    expected_answer = excluded.expected_answer, raw_json = excluded.raw_json,
                    last_synced_at = excluded.last_synced_at,
                    updated_at = excluded.updated_at
                """,
                (
                    storage_key, external_id, str(discipline_id or ""), series, owner_user_id,
                    question.get("tipo"), question.get("enunciado") or "",
                    json.dumps(question.get("alternativas") or [], ensure_ascii=False),
                    question.get("gabarito"), question.get("resolucao"),
                    json.dumps(question.get("conteudo"), ensure_ascii=False),
                    question.get("dificuldade"), str(question.get("ano") or "") or None,
                    origin, json.dumps(question.get("creditos_imagem") or [], ensure_ascii=False),
                    json.dumps(extra, ensure_ascii=False), now, now,
                    question.get("tipo_api"), question.get("area"), question.get("habilidade"),
                    self._json_text(question.get("keywords")),
                    json.dumps(question.get("tags") or [], ensure_ascii=False),
                    question.get("resposta_esperada"),
                    json.dumps(question.get("raw") or {}, ensure_ascii=False, default=str), now,
                ),
            )
            row = connection.execute(
                "SELECT id FROM questions WHERE storage_key = ?", (storage_key,)
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
                "id", "tipo", "enunciado", "alternativas", "gabarito", "resolucao",
                "conteudo", "dificuldade", "ano", "origem", "creditos_imagem",
                "imagens", "_imagem_ids", "_db_id", "linhas_resposta", "area", "keywords",
                "habilidade", "tags", "tipo_api", "resposta_esperada", "raw",
            }
            extra = {key: value for key, value in question.items() if key not in known_fields}
            if question.get("linhas_resposta") is not None:
                extra["linhas_resposta"] = question["linhas_resposta"]
            rows.append((
                storage_key, external_id, discipline_id, None, None,
                question.get("tipo"), question.get("enunciado") or "",
                json.dumps(question.get("alternativas") or [], ensure_ascii=False),
                question.get("gabarito"), question.get("resolucao"),
                json.dumps(question.get("conteudo"), ensure_ascii=False),
                question.get("dificuldade"), str(question.get("ano") or "") or None,
                origin, json.dumps(question.get("creditos_imagem") or [], ensure_ascii=False),
                json.dumps(extra, ensure_ascii=False), now, now,
                question.get("tipo_api"), question.get("area"), question.get("habilidade"),
                self._json_text(question.get("keywords")),
                json.dumps(question.get("tags") or [], ensure_ascii=False),
                question.get("resposta_esperada"),
                json.dumps(question.get("raw") or {}, ensure_ascii=False, default=str), now,
            ))

        sql = """
            INSERT INTO questions(
                storage_key, external_id, discipline_id, series, owner_user_id, kind,
                statement, alternatives_json, answer, resolution, content_json,
                difficulty, year, origin, credits_json, extra_json, created_at, updated_at,
                question_type_label, knowledge_area, skill, keywords, tags_json,
                expected_answer, raw_json, last_synced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(storage_key) DO UPDATE SET
                kind=excluded.kind, statement=excluded.statement,
                alternatives_json=excluded.alternatives_json, answer=excluded.answer,
                resolution=excluded.resolution, content_json=excluded.content_json,
                difficulty=excluded.difficulty, year=excluded.year,
                credits_json=excluded.credits_json, extra_json=excluded.extra_json,
                question_type_label=excluded.question_type_label,
                knowledge_area=excluded.knowledge_area, skill=excluded.skill,
                keywords=excluded.keywords, tags_json=excluded.tags_json,
                expected_answer=excluded.expected_answer, raw_json=excluded.raw_json,
                last_synced_at=excluded.last_synced_at, updated_at=excluded.updated_at
        """
        with self.connect() as connection:
            connection.executemany(sql, rows)
            placeholders = ",".join("?" for _ in keys)
            stored_rows = connection.execute(
                f"SELECT id, storage_key FROM questions WHERE storage_key IN ({placeholders})",
                keys,
            ).fetchall()
            question_ids = {row["storage_key"]: row["id"] for row in stored_rows}
            content_rows = connection.execute(
                "SELECT id, normalized_path FROM contents WHERE discipline_id = ?",
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
                    (question_id, source) for source in question.get("imagens") or [] if source
                )
            connection.executemany(
                """INSERT OR IGNORE INTO question_contents(question_id, content_id, is_primary)
                   VALUES (?, ?, ?)""",
                content_links,
            )
            if series:
                connection.executemany(
                    """INSERT OR IGNORE INTO question_grades(question_id, grade_code)
                       VALUES (?, ?)""",
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
                    """SELECT id FROM question_images
                       WHERE question_id = ? AND source_url = ? LIMIT 1""",
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
                    """INSERT OR IGNORE INTO question_images
                       (question_id, source_url, mime_type, content, sha256, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (question_id, str(source), mime_type, content, digest, int(time.time())),
                )
                return cursor.rowcount > 0
        except (OSError, requests.RequestException):
            return False

    def get_question(self, question_id: int):
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
            images = connection.execute(
                "SELECT id, mime_type, sha256, content FROM question_images WHERE question_id = ? ORDER BY id",
                (question_id,),
            ).fetchall()
        if not row:
            return None
        return self._question_dict(row, images)

    def list_questions(self, discipline_id: str, series: str | None = None):
        query = "SELECT * FROM questions WHERE discipline_id = ?"
        params: list = [str(discipline_id)]
        if series:
            query += """ AND (
                EXISTS (
                    SELECT 1 FROM question_grades qg
                    WHERE qg.question_id = questions.id AND qg.grade_code = ?
                ) OR (
                    NOT EXISTS (SELECT 1 FROM question_grades qg2 WHERE qg2.question_id = questions.id)
                    AND (series = ? OR series IS NULL OR series = '')
                )
            )"""
            params.append(series)
            params.append(series)
        query += " ORDER BY updated_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
            result = []
            for row in rows:
                images = connection.execute(
                    "SELECT id, mime_type, sha256, content FROM question_images WHERE question_id = ? ORDER BY id",
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
        query = "SELECT * FROM questions WHERE discipline_id = ?"
        params: list = [str(discipline_id)]
        if series:
            query += """ AND EXISTS (
                SELECT 1 FROM question_grades qg
                WHERE qg.question_id = questions.id AND qg.grade_code = ?
            )"""
            params.append(series)
        if difficulty:
            query += " AND difficulty = ? COLLATE NOCASE"
            params.append(difficulty)
        if kind:
            query += " AND kind = ? COLLATE NOCASE"
            params.append(kind)
        terms = [str(term).strip() for term in content_terms or [] if str(term).strip()]
        if terms:
            query += " AND (" + " OR ".join("content_json LIKE ?" for _ in terms) + ")"
            params.extend(f"%{term}%" for term in terms)
        query += " ORDER BY RANDOM() LIMIT ?"
        params.append(max(1, min(int(limit), 5000)))

        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
            result = []
            for row in rows:
                images = connection.execute(
                    """SELECT id, mime_type, sha256, content FROM question_images
                       WHERE question_id = ? ORDER BY id""",
                    (row["id"],),
                ).fetchall()
                result.append(self._question_dict(row, images))
        return result

    def _question_dict(self, row, images):
        try:
            content = json.loads(row["content_json"] or "null")
        except json.JSONDecodeError:
            content = row["content_json"]
        result = {
            "id": row["external_id"],
            "tipo": row["kind"],
            "enunciado": row["statement"],
            "alternativas": json.loads(row["alternatives_json"] or "[]"),
            "gabarito": row["answer"],
            "resolucao": row["resolution"],
            "conteudo": content,
            "dificuldade": row["difficulty"],
            "ano": row["year"],
            "origem": row["origin"],
            "creditos_imagem": json.loads(row["credits_json"] or "[]"),
            "tipo_api": row["question_type_label"],
            "area": row["knowledge_area"],
            "habilidade": row["skill"],
            "keywords": row["keywords"],
            "tags": json.loads(row["tags_json"] or "[]"),
            "resposta_esperada": row["expected_answer"],
        }
        result.update(json.loads(row["extra_json"] or "{}"))
        result["_db_id"] = row["id"]
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
                "SELECT mime_type, content FROM question_images WHERE id = ?", (image_id,)
            ).fetchone()
        return (row["content"], row["mime_type"]) if row else None

    def add_activity(self, user_id, kind, filename, metadata, responsible=None):
        record_id = str(uuid.uuid4())
        now = int(time.time())
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO activities(id, user_id, kind, responsible, filename, metadata_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (record_id, user_id, kind or "usuario", responsible, filename,
                 json.dumps(metadata or {}, ensure_ascii=False), now),
            )
        return {
            "id": record_id, "tipo": kind or "usuario", "responsavel": responsible,
            "arquivo": filename, "meta": metadata or {}, "ts": now,
        }

    def list_activities(self, user_id, kind=None, responsible=None):
        query = "SELECT * FROM activities WHERE user_id = ?"
        params: list = [user_id]
        if kind:
            query += " AND kind = ?"
            params.append(kind)
        if responsible:
            query += " AND responsible = ?"
            params.append(responsible)
        query += " ORDER BY created_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [
            {
                "id": row["id"], "tipo": row["kind"], "responsavel": row["responsible"],
                "arquivo": row["filename"], "meta": json.loads(row["metadata_json"] or "{}"),
                "ts": row["created_at"],
            }
            for row in rows
        ]

    def activity_by_filename(self, user_id, filename):
        with self.connect() as connection:
            row = connection.execute(
                "SELECT id FROM activities WHERE user_id = ? AND filename = ?",
                (user_id, filename),
            ).fetchone()
        return bool(row)


db = Database()
