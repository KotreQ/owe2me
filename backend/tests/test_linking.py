from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Entry, EntryKind, EntryStatus
from app.services.accounts import link_local_account
from app.services.entries import balances_for, create_entry, decide_entry


def net_with(db: Session, me: int, other: int) -> dict[str, int]:
    return {
        balance.currency: balance.net_minor
        for balance in balances_for(db, me)
        if balance.other_account_id == other
    }


def test_link_rewrites_entries_and_requires_confirmation(
    db: Session,
    make_user: Callable[[str], Account],
    make_local: Callable[[Account, str], Account],
) -> None:
    alice = make_user("alice")
    real_bob = make_user("bob")
    local_bob = make_local(alice, "Bobby")

    entry = create_entry(
        db,
        actor_account_id=alice.id,
        payer_account_id=local_bob.id,
        payee_account_id=alice.id,
        kind=EntryKind.debt,
        amount_minor=9_000,
        currency="PLN",
        title="groceries",
    )
    assert entry.provisional is True

    rewritten = link_local_account(
        db,
        actor_account_id=alice.id,
        alias_account_id=local_bob.id,
        target_account_id=real_bob.id,
    )

    assert rewritten == 1
    assert db.get(Account, local_bob.id) is None

    db.refresh(entry)
    assert entry.payee_account_id == alice.id
    assert entry.payer_account_id == real_bob.id
    assert entry.status is EntryStatus.pending
    assert entry.provisional is False
    assert net_with(db, alice.id, real_bob.id) == {}

    decide_entry(db, actor_account_id=real_bob.id, entry_id=entry.id, accept=True)
    assert net_with(db, alice.id, real_bob.id) == {"PLN": 9_000}


def test_link_moves_entries_in_both_directions(
    db: Session,
    make_user: Callable[[str], Account],
    make_local: Callable[[Account, str], Account],
) -> None:
    alice = make_user("alice")
    real_bob = make_user("bob")
    local_bob = make_local(alice, "Bob")

    create_entry(
        db,
        actor_account_id=alice.id,
        payer_account_id=local_bob.id,
        payee_account_id=alice.id,
        kind=EntryKind.debt,
        amount_minor=3_000,
        currency="PLN",
        title="owed to me",
    )
    create_entry(
        db,
        actor_account_id=alice.id,
        payer_account_id=alice.id,
        payee_account_id=local_bob.id,
        kind=EntryKind.payment,
        amount_minor=1_000,
        currency="PLN",
        title="cash",
    )

    link_local_account(
        db,
        actor_account_id=alice.id,
        alias_account_id=local_bob.id,
        target_account_id=real_bob.id,
    )

    assert net_with(db, alice.id, real_bob.id) == {}

    pending = list(db.scalars(select(Entry).where(Entry.status == EntryStatus.pending)))
    assert len(pending) == 2
    for entry in pending:
        assert real_bob.id in (entry.payer_account_id, entry.payee_account_id)
