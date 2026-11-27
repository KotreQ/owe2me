from collections.abc import Callable

import pytest
from sqlalchemy.orm import Session

from app.models import Account, EntryKind
from app.services.entries import (
    balances_for,
    cancel_entry,
    create_entry,
    decide_entry,
)


def balance_with(db: Session, me: int, other: int) -> dict[str, int]:
    return {
        balance.currency: balance.net_minor
        for balance in balances_for(db, me)
        if balance.other_account_id == other
    }


def test_real_debt_needs_confirmation(db: Session, make_user: Callable[[str], Account]) -> None:
    alice = make_user("alice")
    bob = make_user("bob")

    entry = create_entry(
        db,
        actor_account_id=alice.id,
        payer_account_id=alice.id,
        payee_account_id=bob.id,
        kind=EntryKind.debt,
        amount_minor=10_000,
        currency="pln",
        title="pizza",
    )

    assert entry.status == "pending"
    assert entry.provisional is False
    assert balance_with(db, alice.id, bob.id) == {}

    decide_entry(db, actor_account_id=bob.id, entry_id=entry.id, accept=True)

    assert balance_with(db, alice.id, bob.id) == {"PLN": -10_000}
    assert balance_with(db, bob.id, alice.id) == {"PLN": 10_000}


def test_creator_can_be_the_payee(db: Session, make_user: Callable[[str], Account]) -> None:
    alice = make_user("alice")
    bob = make_user("bob")

    entry = create_entry(
        db,
        actor_account_id=bob.id,
        payer_account_id=alice.id,
        payee_account_id=bob.id,
        kind=EntryKind.debt,
        amount_minor=2_500,
        currency="EUR",
        title="bob paid for alice",
    )

    assert entry.created_by_account_id == bob.id
    decide_entry(db, actor_account_id=alice.id, entry_id=entry.id, accept=True)
    assert balance_with(db, alice.id, bob.id) == {"EUR": -2_500}


def test_payment_offsets_debt(db: Session, make_user: Callable[[str], Account]) -> None:
    alice = make_user("alice")
    bob = make_user("bob")

    debt = create_entry(
        db,
        actor_account_id=alice.id,
        payer_account_id=alice.id,
        payee_account_id=bob.id,
        kind=EntryKind.debt,
        amount_minor=10_000,
        currency="PLN",
        title="pizza",
    )
    payment = create_entry(
        db,
        actor_account_id=alice.id,
        payer_account_id=alice.id,
        payee_account_id=bob.id,
        kind=EntryKind.payment,
        amount_minor=4_000,
        currency="PLN",
        title="partial transfer",
    )
    decide_entry(db, actor_account_id=bob.id, entry_id=debt.id, accept=True)
    decide_entry(db, actor_account_id=bob.id, entry_id=payment.id, accept=True)

    assert balance_with(db, alice.id, bob.id) == {"PLN": -6_000}


def test_overpayment_flips_balance(db: Session, make_user: Callable[[str], Account]) -> None:
    alice = make_user("alice")
    bob = make_user("bob")

    payment = create_entry(
        db,
        actor_account_id=alice.id,
        payer_account_id=alice.id,
        payee_account_id=bob.id,
        kind=EntryKind.payment,
        amount_minor=5_000,
        currency="PLN",
        title="prepayment",
    )
    decide_entry(db, actor_account_id=bob.id, entry_id=payment.id, accept=True)

    assert balance_with(db, alice.id, bob.id) == {"PLN": 5_000}


def test_rejected_entry_does_not_count(db: Session, make_user: Callable[[str], Account]) -> None:
    alice = make_user("alice")
    bob = make_user("bob")

    entry = create_entry(
        db,
        actor_account_id=alice.id,
        payer_account_id=alice.id,
        payee_account_id=bob.id,
        kind=EntryKind.debt,
        amount_minor=1_000,
        currency="PLN",
        title="disputed",
    )
    decide_entry(db, actor_account_id=bob.id, entry_id=entry.id, accept=False)

    assert balance_with(db, alice.id, bob.id) == {}


def test_creator_can_cancel_pending(db: Session, make_user: Callable[[str], Account]) -> None:
    alice = make_user("alice")
    bob = make_user("bob")

    entry = create_entry(
        db,
        actor_account_id=alice.id,
        payer_account_id=alice.id,
        payee_account_id=bob.id,
        kind=EntryKind.debt,
        amount_minor=1_000,
        currency="PLN",
        title="typo",
    )
    cancel_entry(db, actor_account_id=alice.id, entry_id=entry.id)

    assert entry.status == "cancelled"
    assert balance_with(db, alice.id, bob.id) == {}


def test_currencies_never_mix(db: Session, make_user: Callable[[str], Account]) -> None:
    alice = make_user("alice")
    bob = make_user("bob")

    for currency, amount in (("PLN", 1_000), ("EUR", 2_000)):
        entry = create_entry(
            db,
            actor_account_id=alice.id,
            payer_account_id=alice.id,
            payee_account_id=bob.id,
            kind=EntryKind.debt,
            amount_minor=amount,
            currency=currency,
            title="mixed",
        )
        decide_entry(db, actor_account_id=bob.id, entry_id=entry.id, accept=True)

    assert balance_with(db, alice.id, bob.id) == {"PLN": -1_000, "EUR": -2_000}


def test_local_counterparty_auto_accepts(
    db: Session,
    make_user: Callable[[str], Account],
    make_local: Callable[[Account, str], Account],
) -> None:
    alice = make_user("alice")
    bob_local = make_local(alice, "Bob")

    entry = create_entry(
        db,
        actor_account_id=alice.id,
        payer_account_id=bob_local.id,
        payee_account_id=alice.id,
        kind=EntryKind.debt,
        amount_minor=7_000,
        currency="PLN",
        title="cinema",
    )

    assert entry.status == "accepted"
    assert entry.provisional is True
    assert entry.decided_by_account_id is None
    assert balance_with(db, alice.id, bob_local.id) == {"PLN": 7_000}


def test_validation(
    db: Session,
    make_user: Callable[[str], Account],
    make_local: Callable[[Account, str], Account],
) -> None:
    alice = make_user("alice")
    bob = make_user("bob")
    carol = make_user("carol")
    bob_local = make_local(alice, "Bob")

    with pytest.raises(ValueError):
        create_entry(
            db,
            actor_account_id=carol.id,
            payer_account_id=alice.id,
            payee_account_id=bob.id,
            kind=EntryKind.debt,
            amount_minor=100,
            currency="PLN",
            title="not a party",
        )

    with pytest.raises(ValueError):
        create_entry(
            db,
            actor_account_id=bob.id,
            payer_account_id=alice.id,
            payee_account_id=bob.id,
            kind=EntryKind.debt,
            amount_minor=0,
            currency="PLN",
            title="zero",
        )

    with pytest.raises(ValueError):
        create_entry(
            db,
            actor_account_id=bob.id,
            payer_account_id=alice.id,
            payee_account_id=bob.id,
            kind=EntryKind.debt,
            amount_minor=100,
            currency="PL",
            title="bad currency",
        )

    with pytest.raises(ValueError):
        create_entry(
            db,
            actor_account_id=bob.id,
            payer_account_id=bob_local.id,
            payee_account_id=bob.id,
            kind=EntryKind.debt,
            amount_minor=100,
            currency="PLN",
            title="someone else's local account",
        )
