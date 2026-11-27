from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import Account, AccountKind, User


@pytest.fixture
def db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def client(db: Session) -> TestClient:
    def override_get_db() -> Session:
        return db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def make_user(db: Session) -> Callable[[str], Account]:
    def factory(name: str) -> Account:
        account = Account(kind=AccountKind.user, display_name=name)
        db.add(account)
        db.flush()
        db.add(User(account_id=account.id, username=name.lower(), password_hash="x"))
        db.commit()
        return account

    return factory


@pytest.fixture
def make_local(db: Session) -> Callable[[Account, str], Account]:
    def factory(owner: Account, name: str) -> Account:
        account = Account(kind=AccountKind.local, display_name=name, owner_account_id=owner.id)
        db.add(account)
        db.commit()
        return account

    return factory
