from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, AccountKind, EntryKind, User
from app.services.entries import create_entry

ALICE = {"username": "alice", "password": "s3cret-pass", "default_currency": "PLN"}
BOB = {"username": "bob", "password": "b0b-password", "default_currency": "EUR"}


def signup(client: TestClient, payload: dict[str, str]) -> dict:
    response = client.post("/auth/signup", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def create_bob(db: Session) -> Account:
    account = Account(kind=AccountKind.user, display_name="Bob")
    db.add(account)
    db.flush()
    db.add(
        User(
            account_id=account.id,
            username="bob",
            password_hash="x",
            default_currency="EUR",
        )
    )
    db.commit()
    return account


def test_accounts_require_login(client: TestClient) -> None:
    assert client.get("/accounts").status_code == 401
    assert client.get("/accounts/1").status_code == 401
    assert client.post("/accounts/local", json={"display_name": "Bob"}).status_code == 401
    assert client.post("/accounts/1/link", json={"target_username": "bob"}).status_code == 401


def test_create_local_contact(client: TestClient) -> None:
    alice = signup(client, ALICE)

    response = client.post("/accounts/local", json={"display_name": "Bob"})

    assert response.status_code == 201
    body = response.json()
    assert body["kind"] == "local"
    assert body["display_name"] == "Bob"
    assert body["owner_account_id"] == alice["account_id"]
    assert body["username"] is None


def test_local_contact_names_are_unique_per_owner(client: TestClient) -> None:
    signup(client, ALICE)
    assert client.post("/accounts/local", json={"display_name": "Bob"}).status_code == 201

    duplicate = client.post("/accounts/local", json={"display_name": "Bob"})

    assert duplicate.status_code == 409
    assert "already" in duplicate.json()["detail"]


def test_local_contact_name_validation(client: TestClient) -> None:
    signup(client, ALICE)

    assert client.post("/accounts/local", json={"display_name": ""}).status_code == 422
    assert client.post("/accounts/local", json={"display_name": "   "}).status_code == 422
    assert client.post("/accounts/local", json={"display_name": "x" * 101}).status_code == 422


def test_list_contacts_includes_nicknames_and_counterparties(
    client: TestClient, db: Session
) -> None:
    alice = signup(client, ALICE)
    bob = create_bob(db)
    assert client.post("/accounts/local", json={"display_name": "Bobby"}).status_code == 201

    before = client.get("/accounts")
    assert before.status_code == 200
    assert sorted(a["display_name"] for a in before.json()) == ["Bobby"]
    assert all(a["kind"] == "local" for a in before.json())

    create_entry(
        db,
        actor_account_id=alice["account_id"],
        payer_account_id=alice["account_id"],
        payee_account_id=bob.id,
        kind=EntryKind.debt,
        amount_minor=1_000,
        currency="PLN",
        title="coffee",
    )

    after = client.get("/accounts").json()
    assert sorted(a["display_name"] for a in after) == ["Bob", "Bobby"]
    bob_row = next(a for a in after if a["display_name"] == "Bob")
    assert bob_row["kind"] == "user"
    assert bob_row["username"] == "bob"
    assert bob_row["owner_account_id"] is None


def test_get_own_local_account(client: TestClient) -> None:
    signup(client, ALICE)
    created = client.post("/accounts/local", json={"display_name": "Bob"}).json()

    response = client.get(f"/accounts/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_get_account_hides_other_peoples_nicknames(client: TestClient, db: Session) -> None:
    signup(client, ALICE)
    bob = create_bob(db)
    bob_local = Account(kind=AccountKind.local, display_name="Alice", owner_account_id=bob.id)
    db.add(bob_local)
    db.commit()

    assert client.get(f"/accounts/{bob_local.id}").status_code == 404
    assert client.get("/accounts/99999").status_code == 404


def test_link_nickname_rewrites_entries_and_deletes_it(client: TestClient, db: Session) -> None:
    alice = signup(client, ALICE)
    bob = create_bob(db)
    nickname = client.post("/accounts/local", json={"display_name": "Bobby"}).json()

    create_entry(
        db,
        actor_account_id=alice["account_id"],
        payer_account_id=nickname["id"],
        payee_account_id=alice["account_id"],
        kind=EntryKind.debt,
        amount_minor=2_000,
        currency="PLN",
        title="pizza",
    )

    response = client.post(f"/accounts/{nickname['id']}/link", json={"target_username": "BOB"})

    assert response.status_code == 200
    body = response.json()
    assert body["rewritten_entries"] == 1
    assert body["account"]["id"] == bob.id
    assert body["account"]["username"] == "bob"

    assert client.get(f"/accounts/{nickname['id']}").status_code == 404
    assert db.get(Account, nickname["id"]) is None

    pending = client.get("/accounts").json()
    assert [a["display_name"] for a in pending] == ["Bob"]


def test_link_unknown_target(client: TestClient) -> None:
    signup(client, ALICE)
    nickname = client.post("/accounts/local", json={"display_name": "Bob"}).json()

    response = client.post(f"/accounts/{nickname['id']}/link", json={"target_username": "ghost"})

    assert response.status_code == 404


def test_cannot_link_to_yourself(client: TestClient) -> None:
    signup(client, ALICE)
    nickname = client.post("/accounts/local", json={"display_name": "Alice"}).json()

    response = client.post(f"/accounts/{nickname['id']}/link", json={"target_username": "alice"})

    assert response.status_code == 404


def test_cannot_link_a_real_account_or_someone_elses_nickname(
    client: TestClient, db: Session
) -> None:
    alice = signup(client, ALICE)
    bob = create_bob(db)
    create_entry(
        db,
        actor_account_id=alice["account_id"],
        payer_account_id=alice["account_id"],
        payee_account_id=bob.id,
        kind=EntryKind.debt,
        amount_minor=500,
        currency="PLN",
        title="tea",
    )
    foreign = Account(kind=AccountKind.local, display_name="Bob", owner_account_id=bob.id)
    db.add(foreign)
    db.commit()

    real = client.post(f"/accounts/{bob.id}/link", json={"target_username": "bob"})
    foreign_response = client.post(f"/accounts/{foreign.id}/link", json={"target_username": "bob"})

    assert real.status_code == 409
    assert foreign_response.status_code == 404
    assert db.get(Account, foreign.id) is not None
    assert db.scalar(select(User).where(User.username == "bob")) is not None
