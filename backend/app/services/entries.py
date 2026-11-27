"""Ledger entries: creation, confirmation and balance calculation."""

from dataclasses import dataclass

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.db.types import utcnow_naive
from app.models import Account, AccountKind, Entry, EntryKind, EntryStatus


@dataclass(frozen=True)
class Balance:
    """Net position with one other account in one currency.

    Positive `net_minor` means that account owes me; negative means I owe it.
    """

    other_account_id: int
    currency: str
    net_minor: int


def _clean_title(title: str) -> str:
    cleaned = title.strip()
    if not cleaned:
        raise ValueError("title must not be empty")
    if len(cleaned) > 120:
        raise ValueError("title must be at most 120 characters")
    return cleaned


def _clean_currency(currency: str) -> str:
    cleaned = currency.strip().upper()
    if len(cleaned) != 3 or not cleaned.isalpha():
        raise ValueError("currency must be a three-letter ISO 4217 code")
    return cleaned


def _get_account(db: Session, account_id: int) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise ValueError(f"account {account_id} does not exist")
    return account


def create_entry(
    db: Session,
    *,
    actor_account_id: int,
    payer_account_id: int,
    payee_account_id: int,
    kind: EntryKind,
    amount_minor: int,
    currency: str,
    title: str,
) -> Entry:
    """Record a debt or payment. The actor must be one of the two parties.

    A local counterparty cannot confirm anything, so the entry is accepted
    immediately and flagged provisional; linking that nickname to a real
    account turns it back into a pending entry for the real user to decide.
    """
    if payer_account_id == payee_account_id:
        raise ValueError("payer and payee must differ")
    if actor_account_id not in (payer_account_id, payee_account_id):
        raise ValueError("actor must be one of the entry's parties")
    if not isinstance(amount_minor, int) or isinstance(amount_minor, bool):
        raise ValueError("amount_minor must be an integer")
    if amount_minor <= 0:
        raise ValueError("amount_minor must be positive")

    payer = _get_account(db, payer_account_id)
    payee = _get_account(db, payee_account_id)
    counterparty = payee if actor_account_id == payer_account_id else payer

    if counterparty.kind is AccountKind.local:
        if counterparty.owner_account_id != actor_account_id:
            raise ValueError("a local account can only trade with its owner")
        status = EntryStatus.accepted
        provisional = True
    else:
        status = EntryStatus.pending
        provisional = False

    entry = Entry(
        payer_account_id=payer.id,
        payee_account_id=payee.id,
        kind=kind,
        amount_minor=amount_minor,
        currency=_clean_currency(currency),
        title=_clean_title(title),
        status=status,
        provisional=provisional,
        created_by_account_id=actor_account_id,
    )
    db.add(entry)
    db.flush()
    db.commit()
    return entry


def decide_entry(db: Session, *, actor_account_id: int, entry_id: int, accept: bool) -> Entry:
    """Accept or reject a pending entry as its non-creator party."""
    entry = db.get(Entry, entry_id)
    if entry is None:
        raise ValueError(f"entry {entry_id} does not exist")
    if entry.status is not EntryStatus.pending:
        raise ValueError("only pending entries can be decided")
    if actor_account_id == entry.created_by_account_id:
        raise ValueError("the creator cannot decide their own entry")
    if actor_account_id not in (entry.payer_account_id, entry.payee_account_id):
        raise ValueError("only the counterparty can decide this entry")

    entry.status = EntryStatus.accepted if accept else EntryStatus.rejected
    entry.provisional = False
    entry.decided_by_account_id = actor_account_id
    entry.decided_at = utcnow_naive()
    db.flush()
    db.commit()
    return entry


def cancel_entry(db: Session, *, actor_account_id: int, entry_id: int) -> Entry:
    """Cancel a pending entry as its creator."""
    entry = db.get(Entry, entry_id)
    if entry is None:
        raise ValueError(f"entry {entry_id} does not exist")
    if entry.created_by_account_id != actor_account_id:
        raise ValueError("only the creator can cancel this entry")
    if entry.status is not EntryStatus.pending:
        raise ValueError("only pending entries can be cancelled")

    entry.status = EntryStatus.cancelled
    db.flush()
    db.commit()
    return entry


def balances_for(db: Session, account_id: int) -> list[Balance]:
    """Net balance per other account and currency, accepted entries only."""
    is_debt = Entry.kind == EntryKind.debt
    is_payment = Entry.kind == EntryKind.payment
    me_is_payee = Entry.payee_account_id == account_id
    me_is_payer = Entry.payer_account_id == account_id

    signed = case(
        (is_debt & me_is_payee, Entry.amount_minor),
        (is_debt & me_is_payer, -Entry.amount_minor),
        (is_payment & me_is_payer, Entry.amount_minor),
        (is_payment & me_is_payee, -Entry.amount_minor),
        else_=0,
    )
    other_id = case((me_is_payer, Entry.payee_account_id), else_=Entry.payer_account_id)

    rows = db.execute(
        select(other_id.label("other_id"), Entry.currency, func.sum(signed).label("net"))
        .where(
            Entry.status == EntryStatus.accepted,
            or_(me_is_payer, me_is_payee),
        )
        .group_by(other_id, Entry.currency)
        .order_by(Entry.currency, other_id)
    ).all()

    return [
        Balance(other_account_id=row.other_id, currency=row.currency, net_minor=int(row.net))
        for row in rows
    ]


def entries_between(db: Session, account_a_id: int, account_b_id: int) -> list[Entry]:
    """All entries between two accounts, newest first, any status."""
    pair = {
        (Entry.payer_account_id == account_a_id) & (Entry.payee_account_id == account_b_id),
        (Entry.payer_account_id == account_b_id) & (Entry.payee_account_id == account_a_id),
    }
    return list(
        db.scalars(
            select(Entry).where(or_(*pair)).order_by(Entry.created_at.desc(), Entry.id.desc())
        )
    )
