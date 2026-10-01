"""Test setup. Tests run against a REAL Postgres database (dataset_desk_test) that is
rebuilt from the Alembic migrations at the start of every test session - so the
migrations themselves are tested too."""
import os
from datetime import datetime, timezone

# --- must happen BEFORE the app is imported: point the app at the test database ---
from sqlalchemy.engine import make_url

_main_url = make_url(os.environ.get("DATABASE_URL", "postgresql+psycopg://app:app@localhost:5432/dataset_desk"))
TEST_DB = "dataset_desk_test"
os.environ["DATABASE_URL"] = _main_url.set(database=TEST_DB).render_as_string(hide_password=False)
os.environ["BCRYPT_ROUNDS"] = "4"  # fast hashing for tests

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app.db import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Episode, User  # noqa: E402
from app.security import create_access_token, hash_password  # noqa: E402

USERS = {
    "admin": ("admin@test.com", "admin"),
    "ops": ("ops@test.com", "operator"),
    "ops2": ("ops2@test.com", "operator"),
    "client_a": ("a@test.com", "client"),
    "client_b": ("b@test.com", "client"),
}


@pytest.fixture(scope="session", autouse=True)
def database():
    # 1. create the test database if it does not exist yet
    admin_engine = create_engine(_main_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": TEST_DB})
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{TEST_DB}"'))
    admin_engine.dispose()
    # 2. wipe it and build the schema from the migrations
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    command.upgrade(Config("alembic.ini"), "head")
    # 3. create the standard users once (hashing is slow, so not per test)
    with SessionLocal() as db:
        for key, (email, role) in USERS.items():
            db.add(User(email=email, name=key, password_hash=hash_password("password123"),
                        role=role, organisation=f"{key} org" if role == "client" else None, is_active=True))
        db.commit()
    yield


@pytest.fixture(autouse=True)
def clean_tables():
    """Before every test: empty everything except users."""
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE assignments, request_status_history, requests, episodes RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


@pytest.fixture(scope="session")
def H():
    """Authorization headers per user key: H['ops'], H['client_a'], ..."""
    with SessionLocal() as db:
        ids = {u.name: u.id for u in db.query(User).all()}
    return {k: {"Authorization": f"Bearer {create_access_token(ids[k])}"} for k in USERS}


@pytest.fixture
def make_episodes():
    """make_episodes(3, quality='good', task_name='pick cup') -> ['EP-00001', ...]"""
    counter = {"n": 0}

    def _make(count=1, **overrides):
        ids = []
        with SessionLocal() as db:
            for _ in range(count):
                counter["n"] += 1
                values = dict(
                    episode_id=f"EP-{counter['n']:05d}", robot_id="arm-01", task_name="pick cup",
                    recorded_at=datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
                    duration_seconds=30, operator_name="Eric", quality="good",
                )
                values.update(overrides)
                db.add(Episode(**values))
                ids.append(values["episode_id"])
            db.commit()
        return ids

    return _make


@pytest.fixture
def make_request(client, H):
    """make_request('client_a', episodes_requested=2) -> request id"""

    def _make(who="client_a", **overrides):
        body = {"task_name": "pick cup", "episodes_requested": 1, "deadline": "2026-12-01", "notes": "n"}
        body.update(overrides)
        response = client.post("/requests", json=body, headers=H[who])
        assert response.status_code == 201, response.text
        return response.json()["id"]

    return _make


@pytest.fixture
def move(client, H):
    """move(request_id, 'in_progress', 'ops') -> response"""
    return lambda rid, to, who: client.post(f"/requests/{rid}/transition", json={"to_status": to}, headers=H[who])