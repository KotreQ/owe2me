"""Integration tests against a real MySQL instance.

Skipped unless `TEST_MYSQL_URL` points at a database migrated with
`alembic upgrade head`; CI runs them in a dedicated job. The schema is
deliberately not created here: it must come from the migrations, which is what
makes these tests catch drift between models and migrations.
"""

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import get_db
from app.main import app

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_MYSQL_URL"), reason="TEST_MYSQL_URL is not set"
)

TABLES = ("sessions", "entries", "users", "accounts")


@pytest.fixture(scope="session")
def mysql_engine() -> Iterator[Engine]:
    engine = create_engine(os.environ["TEST_MYSQL_URL"], pool_pre_ping=True)
    yield engine
    engine.dispose()


def _truncate(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in TABLES:
            connection.execute(text(f"DELETE FROM {table}"))
        connection.execute(text("SET FOREIGN_KEY_CHECKS = 1"))


@pytest.fixture
def db(mysql_engine: Engine) -> Iterator[Session]:
    _truncate(mysql_engine)
    factory = sessionmaker(bind=mysql_engine, expire_on_commit=False)
    with factory() as session:
        yield session
    _truncate(mysql_engine)


@pytest.fixture
def api(db: Session) -> Iterator[TestClient]:
    def override_get_db() -> Session:
        return db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def new_client() -> TestClient:
    return TestClient(app)


def test_full_flow_on_mysql(api: TestClient) -> None:
    alice = api.post(
        "/auth/signup",
        json={"username": "Alice", "password": "s3cret-pass", "default_currency": "pln"},
    )
    assert alice.status_code == 201, alice.text
    assert alice.json()["default_currency"] == "PLN"
    alice_id = alice.json()["account_id"]

    bob_api = new_client()
    bob = bob_api.post(
        "/auth/signup",
        json={"username": "bob", "password": "b0b-password", "default_currency": "EUR"},
    )
    assert bob.status_code == 201, bob.text
    bob_id = bob.json()["account_id"]

    created = api.post(
        "/entries",
        json={
            "payer_account_id": alice_id,
            "payee_account_id": bob_id,
            "kind": "debt",
            "amount_minor": 2_500,
            "currency": "pln",
            "title": "lunch",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["currency"] == "PLN"
    assert created.json()["status"] == "pending"
    entry_id = created.json()["id"]

    accepted = bob_api.post(f"/entries/{entry_id}/accept")
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["decided_at"] is not None

    mine = api.get("/balances").json()
    assert mine == [
        {
            "account_id": bob_id,
            "display_name": "bob",
            "kind": "user",
            "currency": "PLN",
            "net_minor": -2_500,
        }
    ]
    theirs = bob_api.get(f"/balances/{alice_id}").json()
    assert theirs[0]["net_minor"] == 2_500

    assert api.post("/auth/logout").status_code == 204
    assert api.get("/auth/me").status_code == 401


def test_local_nickname_link_on_mysql(api: TestClient) -> None:
    alice = api.post(
        "/auth/signup",
        json={"username": "alice", "password": "s3cret-pass", "default_currency": "PLN"},
    ).json()
    bob_api = new_client()
    bob = bob_api.post(
        "/auth/signup",
        json={"username": "bob", "password": "b0b-password", "default_currency": "PLN"},
    ).json()

    nickname = api.post("/accounts/local", json={"display_name": "Bobby"})
    assert nickname.status_code == 201, nickname.text

    entry = api.post(
        "/entries",
        json={
            "payer_account_id": nickname.json()["id"],
            "payee_account_id": alice["account_id"],
            "kind": "debt",
            "amount_minor": 4_000,
            "currency": "PLN",
            "title": "cinema",
        },
    )
    assert entry.status_code == 201, entry.text
    assert entry.json()["provisional"] is True

    linked = api.post(f"/accounts/{nickname.json()['id']}/link", json={"target_username": "bob"})
    assert linked.status_code == 200, linked.text
    assert linked.json()["rewritten_entries"] == 1
    assert linked.json()["account"]["id"] == bob["account_id"]

    assert api.get(f"/accounts/{nickname.json()['id']}").status_code == 404
    assert api.get("/entries/pending").json()["total"] == 0
    assert bob_api.get("/entries/pending").json()["total"] == 1
    assert bob_api.get("/balances").json() == []
