from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.main import app
from app.models import Account, AccountKind, User

ALICE = {"username": "alice", "password": "s3cret-pass", "default_currency": "PLN"}


def make_user(db: Session, username: str, display_name: str) -> Account:
    account = Account(kind=AccountKind.user, display_name=display_name)
    db.add(account)
    db.flush()
    db.add(
        User(
            account_id=account.id,
            username=username,
            password_hash=hash_password("b0b-password"),
            default_currency="EUR",
        )
    )
    db.commit()
    return account


def login(db: Session, username: str = "bob") -> TestClient:
    client = TestClient(app)
    response = client.post("/auth/login", json={"username": username, "password": "b0b-password"})
    assert response.status_code == 200, response.text
    return client


def signup(client: TestClient, payload: dict[str, str]) -> int:
    response = client.post("/auth/signup", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["account_id"]


def debt(payer: int, payee: int, amount: int = 1_000, currency: str = "PLN") -> dict:
    return {
        "payer_account_id": payer,
        "payee_account_id": payee,
        "kind": "debt",
        "amount_minor": amount,
        "currency": currency,
        "title": "lunch",
    }


def setup(client: TestClient, db: Session) -> tuple[int, Account, TestClient]:
    alice_id = signup(client, ALICE)
    bob = make_user(db, "bob", "Bob")
    return alice_id, bob, login(db)


def test_entries_require_login(client: TestClient) -> None:
    assert client.get("/entries").status_code == 401
    assert client.get("/entries/pending").status_code == 401
    assert client.post("/entries", json=debt(1, 2)).status_code == 401


def test_create_entry_as_payer(client: TestClient, db: Session) -> None:
    alice_id, bob, _ = setup(client, db)

    response = client.post("/entries", json=debt(alice_id, bob.id, 2_500))

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["provisional"] is False
    assert body["amount_minor"] == 2_500
    assert body["payer_display_name"] == "alice"
    assert body["payee_display_name"] == "Bob"
    assert body["created_by_account_id"] == alice_id
    assert body["decided_by_account_id"] is None


def test_create_entry_as_payee(client: TestClient, db: Session) -> None:
    alice_id, bob, _ = setup(client, db)

    response = client.post("/entries", json=debt(bob.id, alice_id, 700))

    assert response.status_code == 201
    assert response.json()["created_by_account_id"] == alice_id
    assert response.json()["status"] == "pending"


def test_entry_against_local_nickname_is_auto_accepted(client: TestClient) -> None:
    signup(client, ALICE)
    nickname = client.post("/accounts/local", json={"display_name": "Bobby"}).json()
    me = client.get("/auth/me").json()["account_id"]

    response = client.post(
        "/entries",
        json={
            "payer_account_id": nickname["id"],
            "payee_account_id": me,
            "kind": "debt",
            "amount_minor": 1_500,
            "currency": "PLN",
            "title": "cinema",
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "accepted"
    assert response.json()["provisional"] is True


def test_create_entry_validation(client: TestClient, db: Session) -> None:
    alice_id, bob, _ = setup(client, db)

    assert client.post("/entries", json=debt(alice_id, bob.id, 0)).status_code == 422
    assert client.post("/entries", json=debt(alice_id, bob.id, -5)).status_code == 422
    assert (
        client.post("/entries", json=debt(alice_id, bob.id, 100, currency="PL")).status_code == 422
    )
    assert client.post("/entries", json=debt(alice_id, alice_id, 100)).status_code == 422

    blank = debt(alice_id, bob.id)
    blank["title"] = "   "
    assert client.post("/entries", json=blank).status_code == 422


def test_create_entry_where_actor_is_not_a_party(client: TestClient, db: Session) -> None:
    _, bob, _ = setup(client, db)
    carol = make_user(db, "carol", "Carol")

    response = client.post("/entries", json=debt(bob.id, carol.id, 100))

    assert response.status_code == 404


def test_list_entries_is_scoped_and_paginated(client: TestClient, db: Session) -> None:
    alice_id, bob, bob_client = setup(client, db)
    for amount in (100, 200, 300):
        assert client.post("/entries", json=debt(alice_id, bob.id, amount)).status_code == 201

    page = client.get("/entries", params={"limit": 2, "offset": 0})
    assert page.status_code == 200
    body = page.json()
    assert body["total"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert [item["amount_minor"] for item in body["items"]] == [300, 200]

    second = client.get("/entries", params={"limit": 2, "offset": 2}).json()
    assert [item["amount_minor"] for item in second["items"]] == [100]

    assert bob_client.get("/entries").json()["total"] == 3


def test_list_entries_filters(client: TestClient, db: Session) -> None:
    alice_id, bob, _ = setup(client, db)
    carol = make_user(db, "carol", "Carol")
    client.post("/entries", json=debt(alice_id, bob.id, 100))
    client.post("/entries", json=debt(alice_id, bob.id, 200, currency="EUR"))
    client.post("/entries", json=debt(alice_id, carol.id, 300))
    accepted = client.post("/entries", json=debt(alice_id, carol.id, 400)).json()

    assert client.get("/entries", params={"with": bob.id}).json()["total"] == 2
    assert client.get("/entries", params={"currency": "eur"}).json()["total"] == 1
    assert accepted["status"] == "pending"
    assert client.get("/entries", params={"status": "pending"}).json()["total"] == 4


def test_get_entry_visibility(client: TestClient, db: Session) -> None:
    alice_id, bob, bob_client = setup(client, db)
    entry = client.post("/entries", json=debt(alice_id, bob.id)).json()
    make_user(db, "carol", "Carol")

    assert client.get(f"/entries/{entry['id']}").status_code == 200
    assert bob_client.get(f"/entries/{entry['id']}").status_code == 200
    assert client.get("/entries/99999").status_code == 404

    carol_client = login(db, "carol")
    assert carol_client.get(f"/entries/{entry['id']}").status_code == 404


def test_counterparty_accepts(client: TestClient, db: Session) -> None:
    alice_id, bob, bob_client = setup(client, db)
    entry = client.post("/entries", json=debt(alice_id, bob.id)).json()

    response = bob_client.post(f"/entries/{entry['id']}/accept")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "accepted"
    assert body["decided_by_account_id"] == bob.id
    assert body["decided_at"] is not None
    assert client.get(f"/entries/{entry['id']}").json()["status"] == "accepted"


def test_creator_cannot_accept_own_entry(client: TestClient, db: Session) -> None:
    alice_id, bob, _ = setup(client, db)
    entry = client.post("/entries", json=debt(alice_id, bob.id)).json()

    assert client.post(f"/entries/{entry['id']}/accept").status_code == 403


def test_stranger_gets_404_on_accept(client: TestClient, db: Session) -> None:
    alice_id, bob, _ = setup(client, db)
    entry = client.post("/entries", json=debt(alice_id, bob.id)).json()
    make_user(db, "carol", "Carol")

    response = login(db, "carol").post(f"/entries/{entry['id']}/accept")

    assert response.status_code == 404


def test_rejecting_and_re_deciding(client: TestClient, db: Session) -> None:
    alice_id, bob, bob_client = setup(client, db)
    entry = client.post("/entries", json=debt(alice_id, bob.id)).json()

    rejected = bob_client.post(f"/entries/{entry['id']}/reject")
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    again = bob_client.post(f"/entries/{entry['id']}/accept")
    assert again.status_code == 409


def test_creator_cancels_pending_entry(client: TestClient, db: Session) -> None:
    alice_id, bob, bob_client = setup(client, db)
    entry = client.post("/entries", json=debt(alice_id, bob.id)).json()

    assert bob_client.post(f"/entries/{entry['id']}/cancel").status_code == 404
    assert client.post(f"/entries/{entry['id']}/cancel").status_code == 204
    assert client.get(f"/entries/{entry['id']}").json()["status"] == "cancelled"
    assert client.post(f"/entries/{entry['id']}/cancel").status_code == 409


def test_pending_inbox_excludes_own_creations(client: TestClient, db: Session) -> None:
    alice_id, bob, bob_client = setup(client, db)
    client.post("/entries", json=debt(alice_id, bob.id, 100))
    bob_client.post("/entries", json=debt(bob.id, alice_id, 200))

    bob_inbox = bob_client.get("/entries/pending").json()
    alice_inbox = client.get("/entries/pending").json()

    assert bob_inbox["total"] == 1
    assert bob_inbox["items"][0]["amount_minor"] == 100
    assert alice_inbox["total"] == 1
    assert alice_inbox["items"][0]["amount_minor"] == 200
