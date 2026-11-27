"""Ledger entries: creation, confirmation and balance calculation."""

from dataclasses import dataclass

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.db.types import utcnow_naive
from app.models import Account, AccountKind, Entry, EntryKind, EntryStatus


class EntryError(ValueError):
    """Base class for expected entry failures.

    Still a `ValueError` so existing callers keep working; the API layer maps the
    subclasses to 404/403/409/422.
    """


class EntryNotFound(EntryError):
    pass


class EntryForbidden(EntryError):
    pass


class EntryConflict(EntryError):
    pass


class EntryInvalid(EntryError):
    pass


@dataclass(frozen=True)
class Balance:
    """Net position with one other account in one currency.

    Positive `net_minor` means that account owes me; negative means I owe it.
    """

    other_account_id: int
    display_name: str
    kind: AccountKind
    currency: str
    net_minor: int


def _clean_title(title: str) -> str:
    cleaned = title.strip()
    if not cleaned:
        raise EntryInvalid("title must not be empty")
    if len(cleaned) > 120:
        raise EntryInvalid("title must be at most 120 characters")
    return cleaned


def _clean_currency(currency: str) -> str:
    cleaned = currency.strip().upper()
    if len(cleaned) != 3 or not cleaned.isalpha():
        raise EntryInvalid("currency must be a three-letter code")
    return cleaned


def _get_account(db: Session, account_id: int) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise EntryNotFound(f"account {account_id} does not exist")
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
        raise EntryInvalid("payer and payee must differ")
    if actor_account_id not in (payer_account_id, payee_account_id):
        raise EntryNotFound("actor must be one of the entry's parties")
    if not isinstance(amount_minor, int) or isinstance(amount_minor, bool):
        raise EntryInvalid("amount_minor must be an integer")
    if amount_minor <= 0:
        raise EntryInvalid("amount_minor must be positive")

    payer = _get_account(db, payer_account_id)
    payee = _get_account(db, payee_account_id)
    counterparty = payee if actor_account_id == payer_account_id else payer

    if counterparty.kind is AccountKind.local:
        if counterparty.owner_account_id != actor_account_id:
            raise EntryNotFound("a local account can only trade with its owner")
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
        raise EntryNotFound(f"entry {entry_id} does not exist")
    if actor_account_id not in (entry.payer_account_id, entry.payee_account_id):
        raise EntryNotFound("only the counterparty can decide this entry")
    if actor_account_id == entry.created_by_account_id:
        raise EntryForbidden("the creator cannot decide their own entry")
    if entry.status is not EntryStatus.pending:
        raise EntryConflict("only pending entries can be decided")

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
    if entry is None or entry.created_by_account_id != actor_account_id:
        raise EntryNotFound("only the creator can cancel this entry")
    if entry.status is not EntryStatus.pending:
        raise EntryConflict("only pending entries can be cancelled")

    entry.status = EntryStatus.cancelled
    db.flush()
    db.commit()
    return entry


def _pair_net(account_id: int):
    """Signed net per counterparty and currency over accepted entries."""
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

    return (
        select(other_id.label("other_id"), Entry.currency, func.sum(signed).label("net"))
        .where(
            Entry.status == EntryStatus.accepted,
            or_(me_is_payer, me_is_payee),
        )
        .group_by(other_id, Entry.currency)
    )


def balances_for(db: Session, account_id: int, *, include_zero: bool = False) -> list[Balance]:
    """Net balance per other account and currency, accepted entries only.

    Zero rows (fully settled pairs) are hidden unless `include_zero`; they are a
    presentation concern, the entries behind them still exist.
    """
    pair = _pair_net(account_id).subquery()
    query = (
        select(
            pair.c.other_id,
            pair.c.currency,
            pair.c.net,
            Account.display_name,
            Account.kind,
        )
        .join(Account, Account.id == pair.c.other_id)
        .order_by(pair.c.currency, Account.display_name, pair.c.other_id)
    )
    if not include_zero:
        query = query.where(pair.c.net != 0)

    return [
        Balance(
            other_account_id=row.other_id,
            display_name=row.display_name,
            kind=row.kind,
            currency=row.currency,
            net_minor=int(row.net),
        )
        for row in db.execute(query).all()
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


@dataclass(frozen=True)
class EntryPage:
    items: list[Entry]
    total: int


def list_entries(
    db: Session,
    *,
    account_id: int,
    with_account_id: int | None = None,
    status: EntryStatus | None = None,
    currency: str | None = None,
    exclude_created_by_me: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> EntryPage:
    """Entries the account is a party to, newest first, with a total count."""
    me_is_payer = Entry.payer_account_id == account_id
    me_is_payee = Entry.payee_account_id == account_id
    conditions = [or_(me_is_payer, me_is_payee)]

    if with_account_id is not None:
        conditions.append(
            or_(
                (Entry.payer_account_id == account_id)
                & (Entry.payee_account_id == with_account_id),
                (Entry.payee_account_id == account_id)
                & (Entry.payer_account_id == with_account_id),
            )
        )
    if status is not None:
        conditions.append(Entry.status == status)
    if currency:
        conditions.append(Entry.currency == currency.strip().upper())
    if exclude_created_by_me:
        conditions.append(Entry.created_by_account_id != account_id)

    total = db.scalar(select(func.count(Entry.id)).where(*conditions)) or 0
    items = list(
        db.scalars(
            select(Entry)
            .where(*conditions)
            .order_by(Entry.created_at.desc(), Entry.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return EntryPage(items=items, total=int(total))


def visible_entry(db: Session, *, entry_id: int, viewer_account_id: int) -> Entry:
    entry = db.get(Entry, entry_id)
    if entry is None or viewer_account_id not in (
        entry.payer_account_id,
        entry.payee_account_id,
    ):
        raise EntryNotFound(f"entry {entry_id} does not exist")
    return entry


@dataclass(frozen=True)
class BalanceTotals:
    """Sum over all counterparties for one currency.

    `owed_by_others_minor` is what people owe me, `owed_to_others_minor` is what
    I owe them (absolute value), `net_minor` is the difference.
    """

    currency: str
    owed_by_others_minor: int
    owed_to_others_minor: int
    net_minor: int


def balance_totals(db: Session, account_id: int) -> list[BalanceTotals]:
    """Aggregate accepted entries per currency, across every counterparty."""
    pair = _pair_net(account_id).subquery()
    owed_by_others = func.sum(case((pair.c.net > 0, pair.c.net), else_=0))
    owed_to_others = func.sum(case((pair.c.net < 0, -pair.c.net), else_=0))
    net = func.sum(pair.c.net)

    rows = db.execute(
        select(
            pair.c.currency,
            owed_by_others.label("owed_by_others"),
            owed_to_others.label("owed_to_others"),
            net.label("net"),
        )
        .group_by(pair.c.currency)
        .having(or_(owed_by_others != 0, owed_to_others != 0))
        .order_by(pair.c.currency)
    ).all()

    return [
        BalanceTotals(
            currency=row.currency,
            owed_by_others_minor=int(row.owed_by_others),
            owed_to_others_minor=int(row.owed_to_others),
            net_minor=int(row.net),
        )
        for row in rows
    ]
