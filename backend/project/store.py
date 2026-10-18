"""Where analysis requests are recorded: Postgres (Tiger Cloud) when DATABASE_URL is set, else memory.

Only job metadata and the Result JSON are stored: never the uploaded file, its name, or any image
(reports/decisions.md). Images stay on this machine under paths.jobs.
"""

import os
import threading
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Optional

RESTARTED = "The server restarted during this analysis. Upload the image again."


class StoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class JobRecord:
    id: str
    created_at: datetime
    status: str                     # running | done | error
    model: str
    prompt_set: str
    cancer_type: Optional[str] = None
    result: Optional[dict] = None
    error: Optional[str] = None
    finished_at: Optional[datetime] = None


def now():
    return datetime.now(timezone.utc)


class MemoryStore:
    """Used by tests and when no database is configured; forgets everything on restart."""

    name = "memory"

    def __init__(self):
        self._rows = {}
        self._lock = threading.Lock()

    def create(self, job_id, model, prompt_set, created_at=None):
        with self._lock:
            self._rows[job_id] = JobRecord(job_id, created_at or now(), "running", model, prompt_set)

    def finish(self, job_id, result, cancer_type):
        with self._lock:
            self._rows[job_id] = replace(self._rows[job_id], status="done", result=result,
                                         cancer_type=cancer_type, finished_at=now())

    def fail(self, job_id, error):
        with self._lock:
            self._rows[job_id] = replace(self._rows[job_id], status="error", error=error, finished_at=now())

    def get(self, job_id):
        return self._rows.get(job_id)

    def delete(self, job_id):
        with self._lock:
            return self._rows.pop(job_id, None) is not None

    def list(self, limit=100):
        with self._lock:
            return sorted(self._rows.values(), key=lambda r: r.created_at, reverse=True)[:limit]

    def recover(self):
        with self._lock:
            stuck = [r for r in self._rows.values() if r.status == "running"]
            for r in stuck:
                self._rows[r.id] = replace(r, status="error", error=RESTARTED, finished_at=now())
            return len(stuck)

    def close(self):
        pass


class PostgresStore:
    """One table, `<schema>.jobs`. One connection, shared by request and worker threads under a lock."""

    name = "postgres"
    COLUMNS = "id, created_at, status, model, prompt_set, cancer_type, result, error, finished_at"

    def __init__(self, dsn, schema="public"):
        import psycopg
        from psycopg import sql

        self._sql = sql
        self._schema = schema
        self._table = sql.Identifier(schema, "jobs")
        self._lock = threading.Lock()
        self._conn = psycopg.connect(dsn, autocommit=True, connect_timeout=10)
        self._run(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))
        self._run(sql.SQL("""
            CREATE TABLE IF NOT EXISTS {} (
                id          text PRIMARY KEY,
                created_at  timestamptz NOT NULL DEFAULT now(),
                status      text NOT NULL CHECK (status IN ('running', 'done', 'error')),
                model       text NOT NULL,
                prompt_set  text NOT NULL,
                cancer_type text,
                result      jsonb,
                error       text,
                finished_at timestamptz
            )""").format(self._table))
        self._run(sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} (created_at DESC)").format(
            sql.Identifier("jobs_created_at_idx"), self._table))

    def _run(self, query, params=None, fetch=False):
        with self._lock, self._conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall() if fetch else cur.rowcount

    def _select(self, where="", params=None, tail=""):
        q = self._sql.SQL("SELECT " + self.COLUMNS + " FROM {} " + where + " " + tail).format(self._table)
        return [JobRecord(*row) for row in self._run(q, params, fetch=True)]

    def create(self, job_id, model, prompt_set, created_at=None):
        self._run(self._sql.SQL(
            "INSERT INTO {} (id, created_at, status, model, prompt_set) VALUES (%s, %s, 'running', %s, %s)"
        ).format(self._table), (job_id, created_at or now(), model, prompt_set))

    def finish(self, job_id, result, cancer_type):
        from psycopg.types.json import Jsonb

        self._run(self._sql.SQL(
            "UPDATE {} SET status = 'done', result = %s, cancer_type = %s, finished_at = now() WHERE id = %s"
        ).format(self._table), (Jsonb(result), cancer_type, job_id))

    def fail(self, job_id, error):
        self._run(self._sql.SQL(
            "UPDATE {} SET status = 'error', error = %s, finished_at = now() WHERE id = %s"
        ).format(self._table), (error, job_id))

    def get(self, job_id):
        rows = self._select("WHERE id = %s", (job_id,))
        return rows[0] if rows else None

    def delete(self, job_id):
        return self._run(self._sql.SQL("DELETE FROM {} WHERE id = %s").format(self._table), (job_id,)) > 0

    def list(self, limit=100):
        return self._select(tail="ORDER BY created_at DESC LIMIT %s", params=(limit,))

    def recover(self):
        return self._run(self._sql.SQL(
            "UPDATE {} SET status = 'error', error = %s, finished_at = now() WHERE status = 'running'"
        ).format(self._table), (RESTARTED,))

    def drop_schema(self):
        """Tests only: remove the throwaway schema."""
        self._run(self._sql.SQL("DROP SCHEMA {} CASCADE").format(self._sql.Identifier(self._schema)))

    def close(self):
        self._conn.close()


def open_store():
    """Postgres when DATABASE_URL is set (refusing to start if it can't connect), memory otherwise."""
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        return MemoryStore()
    try:
        store = PostgresStore(dsn)
    except Exception as e:
        # psycopg messages can echo the host or user; never the URL itself, which may hold a password.
        raise StoreError(
            f"Could not connect to the database in DATABASE_URL ({type(e).__name__}). "
            "Check the service is running and the URL is right, or unset DATABASE_URL to run without history."
        ) from None
    store.recover()
    return store
