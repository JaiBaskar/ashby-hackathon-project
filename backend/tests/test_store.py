"""The job store: the same contract for MemoryStore (always) and PostgresStore (`make test-db`)."""

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from project.store import RESTARTED, MemoryStore, StoreError, open_store

T0 = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
RESULT = {"model": "fake", "regions": [{"rank": 1, "score": 0.5}], "note": None}


@pytest.fixture(params=["memory", pytest.param("postgres", marks=pytest.mark.db)])
def store(request):
    if request.param == "memory":
        yield MemoryStore()
        return
    from project.store import PostgresStore

    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.fail("make test-db needs TEST_DATABASE_URL (a Postgres you can create schemas in).")
    s = PostgresStore(dsn, schema=f"test_{uuid.uuid4().hex[:12]}")
    yield s
    s.drop_schema()
    s.close()


def test_create_then_get(store):
    store.create("a1", model="fake", prompt_set="v2", created_at=T0)
    rec = store.get("a1")
    assert (rec.id, rec.status, rec.model, rec.prompt_set) == ("a1", "running", "fake", "v2")
    assert rec.created_at == T0
    assert rec.cancer_type is None and rec.result is None and rec.error is None and rec.finished_at is None


def test_created_at_defaults_to_now_in_utc(store):
    before = datetime.now(timezone.utc)
    store.create("a1", model="fake", prompt_set="v2")
    created = store.get("a1").created_at
    assert created.tzinfo is not None
    assert before - timedelta(seconds=5) <= created <= datetime.now(timezone.utc) + timedelta(seconds=5)


def test_finish_stores_result_and_cancer_type(store):
    store.create("a1", model="fake", prompt_set="v2", created_at=T0)
    store.finish("a1", RESULT, cancer_type="breast")
    rec = store.get("a1")
    assert rec.status == "done"
    assert rec.result == RESULT
    assert rec.cancer_type == "breast"
    assert rec.finished_at is not None and rec.finished_at >= T0


def test_finish_without_cancer_type_keeps_it_null(store):
    store.create("a1", model="fake", prompt_set="v2", created_at=T0)
    store.finish("a1", RESULT, cancer_type=None)
    assert store.get("a1").cancer_type is None


def test_fail_records_the_error(store):
    store.create("a1", model="fake", prompt_set="v2", created_at=T0)
    store.fail("a1", "No tissue found in this image.")
    rec = store.get("a1")
    assert (rec.status, rec.error, rec.result) == ("error", "No tissue found in this image.", None)


def test_list_is_newest_first_and_limited(store):
    for i in range(5):
        store.create(f"j{i}", model="fake", prompt_set="v2", created_at=T0 + timedelta(minutes=i))
    assert [r.id for r in store.list()] == ["j4", "j3", "j2", "j1", "j0"]
    assert [r.id for r in store.list(limit=2)] == ["j4", "j3"]


def test_unknown_id_is_none(store):
    assert store.get("nope") is None


def test_recover_marks_unfinished_jobs_as_errors(store):
    store.create("done", model="fake", prompt_set="v2", created_at=T0)
    store.finish("done", RESULT, cancer_type=None)
    store.create("stuck", model="fake", prompt_set="v2", created_at=T0)
    assert store.recover() == 1
    assert store.get("stuck").status == "error"
    assert store.get("stuck").error == RESTARTED
    assert store.get("done").status == "done"


def test_open_store_without_database_url_is_memory(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert isinstance(open_store(), MemoryStore)


def test_unreachable_database_refuses_and_hides_the_url(monkeypatch):
    secret_url = "postgresql://user:s3cretpw@127.0.0.1:1/nodb?connect_timeout=1"
    monkeypatch.setenv("DATABASE_URL", secret_url)
    with pytest.raises(StoreError) as err:
        open_store()
    assert "s3cretpw" not in str(err.value)
    assert "DATABASE_URL" in str(err.value)
