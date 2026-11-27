from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import token_digest
from app.db.types import utcnow_naive
from app.models import Account, AccountKind, AuthSession, User


def signup(
    client: TestClient,
    username: str = "alice",
    password: str = "s3cret-pass",
    currency: str = "PLN",
):
    return client.post(
        "/auth/signup",
        json={"username": username, "password": password, "default_currency": currency},
    )


def test_signup_creates_account_and_logs_in(client: TestClient) -> None:
    response = signup(client)

    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "alice"
    assert body["display_name"] == "alice"
    assert body["default_currency"] == "PLN"
    assert isinstance(body["account_id"], int)
    assert "password" not in response.text

    cookie = response.cookies.get("owe2me_session")
    assert cookie
    assert response.headers["set-cookie"].lower().find("httponly") != -1

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json() == body


def test_signup_normalizes_username_and_keeps_display_name(client: TestClient) -> None:
    response = client.post(
        "/auth/signup",
        json={
            "username": "Alice.B",
            "password": "s3cret-pass",
            "default_currency": "eur",
            "display_name": "Alice B.",
        },
    )

    assert response.status_code == 201
    assert response.json()["username"] == "alice.b"
    assert response.json()["display_name"] == "Alice B."
    assert response.json()["default_currency"] == "EUR"


def test_signup_rejects_taken_username_case_insensitively(client: TestClient) -> None:
    assert signup(client, "alice").status_code == 201

    response = signup(client, "ALICE")

    assert response.status_code == 409
    assert response.json()["detail"] == "username already taken"


def test_signup_validation(client: TestClient) -> None:
    assert signup(client, password="short").status_code == 422
    assert signup(client, username="ab").status_code == 422
    assert signup(client, username="bad name").status_code == 422
    assert (
        client.post(
            "/auth/signup",
            json={
                "username": "alice",
                "password": "s3cret-pass",
                "default_currency": "PLN",
                "display_name": "",
            },
        ).status_code
        == 422
    )


def test_signup_stores_hash_not_password(client: TestClient, db: Session) -> None:
    assert signup(client, "alice", "s3cret-pass").status_code == 201

    user = db.scalar(select(User).where(User.username == "alice"))
    assert user is not None
    assert user.password_hash.startswith("$argon2id$")
    assert "s3cret-pass" not in user.password_hash

    account = db.get(Account, user.account_id)
    assert account is not None
    assert account.kind is AccountKind.user
    assert account.owner_account_id is None


def test_session_token_is_stored_hashed(client: TestClient, db: Session) -> None:
    response = signup(client)
    raw = response.cookies.get("owe2me_session")
    assert raw

    session = db.scalar(select(AuthSession))
    assert session is not None
    assert session.token_hash == token_digest(raw)
    assert session.token_hash != raw
    assert len(session.token_hash) == 64
    assert session.expires_at > utcnow_naive()


def test_login_with_valid_password(client: TestClient) -> None:
    assert signup(client, "alice", "s3cret-pass").status_code == 201
    client.post("/auth/logout")

    response = client.post("/auth/login", json={"username": "Alice", "password": "s3cret-pass"})

    assert response.status_code == 200
    assert response.json()["username"] == "alice"
    assert client.get("/auth/me").status_code == 200


def test_login_rejects_bad_password_and_unknown_user_identically(client: TestClient) -> None:
    assert signup(client, "alice", "s3cret-pass").status_code == 201
    client.post("/auth/logout")

    wrong = client.post("/auth/login", json={"username": "alice", "password": "wrong-pass"})
    unknown = client.post("/auth/login", json={"username": "nobody", "password": "wrong-pass"})

    assert wrong.status_code == 401
    assert unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"detail": "invalid username or password"}


def test_me_requires_session(client: TestClient) -> None:
    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "not authenticated"


def test_me_rejects_forged_token(client: TestClient) -> None:
    assert signup(client).status_code == 201
    client.cookies.clear()
    client.cookies.set("owe2me_session", "not-a-real-token")

    assert client.get("/auth/me").status_code == 401


def test_logout_revokes_session(client: TestClient, db: Session) -> None:
    assert signup(client).status_code == 201
    assert client.get("/auth/me").status_code == 200

    response = client.post("/auth/logout")

    assert response.status_code == 204
    assert client.get("/auth/me").status_code == 401
    assert db.scalar(select(AuthSession)) is None
    # Idempotent: logging out again is not an error.
    assert client.post("/auth/logout").status_code == 204


def test_expired_session_is_rejected_and_removed(client: TestClient, db: Session) -> None:
    assert signup(client).status_code == 201

    session = db.scalar(select(AuthSession))
    assert session is not None
    session.expires_at = utcnow_naive() - timedelta(seconds=1)
    db.commit()

    assert client.get("/auth/me").status_code == 401
    assert db.scalar(select(AuthSession)) is None


def test_session_can_be_recreated_after_logout(client: TestClient, db: Session) -> None:
    assert signup(client).status_code == 201
    client.post("/auth/logout")

    response = client.post("/auth/login", json={"username": "alice", "password": "s3cret-pass"})

    assert response.status_code == 200
    assert db.scalar(select(AuthSession)) is not None
    assert client.get("/auth/me").status_code == 200


def test_signup_requires_currency(client: TestClient) -> None:
    response = client.post("/auth/signup", json={"username": "alice", "password": "s3cret-pass"})

    assert response.status_code == 422


def test_signup_rejects_malformed_currency(client: TestClient) -> None:
    for currency in ("PL", "PLNX", "P1N", ""):
        response = signup(client, currency=currency)
        assert response.status_code == 422, currency


def test_update_default_currency(client: TestClient) -> None:
    assert signup(client, currency="PLN").status_code == 201

    response = client.patch("/auth/me", json={"default_currency": "eur"})

    assert response.status_code == 200
    assert response.json()["default_currency"] == "EUR"
    assert client.get("/auth/me").json()["default_currency"] == "EUR"


def test_update_default_currency_requires_login(client: TestClient) -> None:
    assert client.patch("/auth/me", json={"default_currency": "EUR"}).status_code == 401


def test_update_default_currency_validation(client: TestClient) -> None:
    assert signup(client).status_code == 201

    assert client.patch("/auth/me", json={"default_currency": "EURO"}).status_code == 422
    assert client.get("/auth/me").json()["default_currency"] == "PLN"


def test_update_display_name(client: TestClient) -> None:
    assert signup(client).status_code == 201

    response = client.patch("/auth/me", json={"display_name": "Alicja B."})

    assert response.status_code == 200
    assert response.json()["display_name"] == "Alicja B."
    assert response.json()["username"] == "alice"
    assert client.get("/auth/me").json()["display_name"] == "Alicja B."


def test_update_display_name_touches_existing_entries(client: TestClient, db: Session) -> None:
    from app.models import Account
    from app.services.entries import create_entry

    alice = signup(client)
    bob = Account(kind="user", display_name="Bob")
    db.add(bob)
    db.flush()
    db.add(User(account_id=bob.id, username="bob", password_hash="x", default_currency="PLN"))
    db.commit()
    entry = create_entry(
        db,
        actor_account_id=alice.json()["account_id"],
        payer_account_id=alice.json()["account_id"],
        payee_account_id=bob.id,
        kind="debt",
        amount_minor=100,
        currency="PLN",
        title="tea",
    )

    assert client.patch("/auth/me", json={"display_name": "Alicja"}).status_code == 200

    fetched = client.get(f"/entries/{entry.id}").json()
    assert fetched["payer_display_name"] == "Alicja"
    assert fetched["payee_display_name"] == "Bob"


def test_update_profile_rejects_empty_and_blank(client: TestClient) -> None:
    assert signup(client).status_code == 201

    assert client.patch("/auth/me", json={}).status_code == 422
    assert client.patch("/auth/me", json={"display_name": ""}).status_code == 422
    assert client.patch("/auth/me", json={"display_name": "   "}).status_code == 422
    assert client.patch("/auth/me", json={"display_name": "x" * 101}).status_code == 422
    assert client.get("/auth/me").json()["display_name"] == "alice"


def test_update_both_profile_fields(client: TestClient) -> None:
    assert signup(client).status_code == 201

    response = client.patch("/auth/me", json={"display_name": "Alicja", "default_currency": "eur"})

    assert response.status_code == 200
    assert response.json()["display_name"] == "Alicja"
    assert response.json()["default_currency"] == "EUR"
