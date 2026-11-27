from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from tests.test_entries_api import ALICE, debt, make_user, signup


def accepted_entry(
    client: TestClient, bob_client: TestClient, payer: int, payee: int, amount: int, currency: str
) -> None:
    created = client.post("/entries", json=debt(payer, payee, amount, currency=currency))
    assert created.status_code == 201, created.text
    entry_id = created.json()["id"]
    assert bob_client.post(f"/entries/{entry_id}/accept").status_code == 200


def test_balances_require_login(client: TestClient) -> None:
    assert client.get("/balances").status_code == 401


def test_balances_include_name_and_kind(client: TestClient, db: Session) -> None:
    alice_id = signup(client, ALICE)
    bob = make_user(db, "bob", "Bob")
    bob_client = TestClient(app)
    assert (
        bob_client.post(
            "/auth/login", json={"username": "bob", "password": "b0b-password"}
        ).status_code
        == 200
    )

    accepted_entry(client, bob_client, alice_id, bob.id, 2_500, "PLN")

    response = client.get("/balances")

    assert response.status_code == 200
    assert response.json() == [
        {
            "account_id": bob.id,
            "display_name": "Bob",
            "kind": "user",
            "currency": "PLN",
            "net_minor": -2_500,
        }
    ]

    mine = bob_client.get("/balances").json()
    assert mine[0]["net_minor"] == 2_500
    assert mine[0]["account_id"] == alice_id


def test_balances_skip_zero_rows_by_default(client: TestClient, db: Session) -> None:
    alice_id = signup(client, ALICE)
    bob = make_user(db, "bob", "Bob")
    bob_client = TestClient(app)
    bob_client.post("/auth/login", json={"username": "bob", "password": "b0b-password"})
    accepted_entry(client, bob_client, alice_id, bob.id, 1_000, "PLN")

    payment = client.post(
        "/entries",
        json={
            "payer_account_id": alice_id,
            "payee_account_id": bob.id,
            "kind": "payment",
            "amount_minor": 1_000,
            "currency": "PLN",
            "title": "settled",
        },
    ).json()
    assert bob_client.post(f"/entries/{payment['id']}/accept").status_code == 200

    assert client.get("/balances").json() == []
    with_zero = client.get("/balances", params={"include_zero": True}).json()
    assert len(with_zero) == 1
    assert with_zero[0]["net_minor"] == 0


def test_balances_are_per_currency_and_negative_too(client: TestClient, db: Session) -> None:
    alice_id = signup(client, ALICE)
    bob = make_user(db, "bob", "Bob")
    bob_client = TestClient(app)
    bob_client.post("/auth/login", json={"username": "bob", "password": "b0b-password"})

    accepted_entry(client, bob_client, alice_id, bob.id, 1_000, "PLN")
    accepted_entry(client, bob_client, bob.id, alice_id, 2_000, "EUR")

    balances = client.get("/balances").json()

    assert [(b["currency"], b["net_minor"]) for b in balances] == [
        ("EUR", 2_000),
        ("PLN", -1_000),
    ]


def test_balances_report_local_nickname_kind(client: TestClient) -> None:
    signup(client, ALICE)
    me = client.get("/auth/me").json()["account_id"]
    nickname = client.post("/accounts/local", json={"display_name": "Bobby"}).json()

    created = client.post(
        "/entries",
        json={
            "payer_account_id": nickname["account_id"],
            "payee_account_id": me,
            "kind": "debt",
            "amount_minor": 3_000,
            "currency": "PLN",
            "title": "cinema",
        },
    )
    assert created.status_code == 201

    balances = client.get("/balances").json()

    assert balances == [
        {
            "account_id": nickname["account_id"],
            "display_name": "Bobby",
            "kind": "local",
            "currency": "PLN",
            "net_minor": 3_000,
        }
    ]


def test_pending_entries_do_not_count(client: TestClient, db: Session) -> None:
    alice_id = signup(client, ALICE)
    bob = make_user(db, "bob", "Bob")

    assert client.post("/entries", json=debt(alice_id, bob.id, 5_000)).status_code == 201

    assert client.get("/balances").json() == []


def test_balance_with_one_account(client: TestClient, db: Session) -> None:
    alice_id = signup(client, ALICE)
    bob = make_user(db, "bob", "Bob")
    carol = make_user(db, "carol", "Carol")
    bob_client = TestClient(app)
    bob_client.post("/auth/login", json={"username": "bob", "password": "b0b-password"})
    carol_client = TestClient(app)
    carol_client.post("/auth/login", json={"username": "carol", "password": "b0b-password"})

    accepted_entry(client, bob_client, alice_id, bob.id, 1_000, "PLN")
    accepted_entry(client, bob_client, bob.id, alice_id, 2_000, "EUR")
    accepted_entry(client, carol_client, alice_id, carol.id, 500, "PLN")

    response = client.get(f"/balances/{bob.id}")

    assert response.status_code == 200
    assert response.json() == [
        {
            "account_id": bob.id,
            "display_name": "Bob",
            "kind": "user",
            "currency": "EUR",
            "net_minor": 2_000,
        },
        {
            "account_id": bob.id,
            "display_name": "Bob",
            "kind": "user",
            "currency": "PLN",
            "net_minor": -1_000,
        },
    ]


def test_balance_with_account_requires_login_and_visibility(
    client: TestClient, db: Session
) -> None:
    signup(client, ALICE)
    bob = make_user(db, "bob", "Bob")

    assert client.get(f"/balances/{bob.id}").status_code == 404
    assert client.get("/balances/99999").status_code == 404

    anonymous = TestClient(app)
    assert anonymous.get("/balances/1").status_code == 401

    bob_client = TestClient(app)
    bob_client.post("/auth/login", json={"username": "bob", "password": "b0b-password"})
    assert bob_client.get("/balances/99999").status_code == 404


def test_balance_with_settled_account_hides_zero_by_default(
    client: TestClient, db: Session
) -> None:
    alice_id = signup(client, ALICE)
    bob = make_user(db, "bob", "Bob")
    bob_client = TestClient(app)
    bob_client.post("/auth/login", json={"username": "bob", "password": "b0b-password"})

    accepted_entry(client, bob_client, alice_id, bob.id, 1_000, "PLN")
    payment = client.post(
        "/entries",
        json={
            "payer_account_id": alice_id,
            "payee_account_id": bob.id,
            "kind": "payment",
            "amount_minor": 1_000,
            "currency": "PLN",
            "title": "settled",
        },
    ).json()
    bob_client.post(f"/entries/{payment['id']}/accept")

    assert client.get(f"/balances/{bob.id}").json() == []
    zero = client.get(f"/balances/{bob.id}", params={"include_zero": True}).json()
    assert zero[0]["net_minor"] == 0


def test_totals_sum_per_currency_across_people(client: TestClient, db: Session) -> None:
    alice_id = signup(client, ALICE)
    bob = make_user(db, "bob", "Bob")
    carol = make_user(db, "carol", "Carol")
    bob_client = TestClient(app)
    bob_client.post("/auth/login", json={"username": "bob", "password": "b0b-password"})
    carol_client = TestClient(app)
    carol_client.post("/auth/login", json={"username": "carol", "password": "b0b-password"})

    # I owe Bob 30 PLN, Carol owes me 12 PLN, Bob owes me 3 EUR.
    accepted_entry(client, bob_client, alice_id, bob.id, 3_000, "PLN")
    accepted_entry(client, carol_client, carol.id, alice_id, 1_200, "PLN")
    accepted_entry(client, bob_client, bob.id, alice_id, 300, "EUR")

    response = client.get("/balances/totals")

    assert response.status_code == 200
    assert response.json() == [
        {
            "currency": "EUR",
            "owed_by_others_minor": 300,
            "owed_to_others_minor": 0,
            "net_minor": 300,
        },
        {
            "currency": "PLN",
            "owed_by_others_minor": 1_200,
            "owed_to_others_minor": 3_000,
            "net_minor": -1_800,
        },
    ]

    theirs = bob_client.get("/balances/totals").json()
    assert theirs == [
        {
            "currency": "EUR",
            "owed_by_others_minor": 0,
            "owed_to_others_minor": 300,
            "net_minor": -300,
        },
        {
            "currency": "PLN",
            "owed_by_others_minor": 3_000,
            "owed_to_others_minor": 0,
            "net_minor": 3_000,
        },
    ]


def test_totals_ignore_pending_and_settled_pairs(client: TestClient, db: Session) -> None:
    alice_id = signup(client, ALICE)
    bob = make_user(db, "bob", "Bob")
    bob_client = TestClient(app)
    bob_client.post("/auth/login", json={"username": "bob", "password": "b0b-password"})

    assert (
        client.post("/entries", json=debt(alice_id, bob.id, 900, currency="PLN")).status_code == 201
    )
    assert client.get("/balances/totals").json() == []

    accepted_entry(client, bob_client, alice_id, bob.id, 1_000, "PLN")
    payment = client.post(
        "/entries",
        json={
            "payer_account_id": alice_id,
            "payee_account_id": bob.id,
            "kind": "payment",
            "amount_minor": 1_000,
            "currency": "PLN",
            "title": "settle",
        },
    ).json()
    bob_client.post(f"/entries/{payment['id']}/accept")

    # Pair nets are aggregated first, so a settled pair leaves nothing behind.
    assert client.get("/balances/totals").json() == []


def test_totals_require_login_and_do_not_shadow_account_route(client: TestClient) -> None:
    anonymous = TestClient(app)
    assert anonymous.get("/balances/totals").status_code == 401

    signup(client, ALICE)
    assert client.get("/balances/totals").json() == []
    assert client.get("/balances/99999").status_code == 404
