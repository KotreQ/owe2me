"""Account lifecycle: local nicknames and linking them to real users."""

from sqlalchemy import or_, select, union, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Account, AccountKind, Entry, EntryStatus, User


def link_local_account(
    db: Session,
    *,
    actor_account_id: int,
    alias_account_id: int,
    target_account_id: int,
    relabel_pending: bool = True,
) -> int:
    """Rewrite a local nickname's entries onto a real account and delete it.

    Ownership rule: only the account that owns the nickname may link it.
    Provisional entries (auto-accepted against the nickname) are moved back to
    pending, so the real user has to confirm them; their balances stop counting
    until then. Returns the number of rewritten entries.
    """
    if alias_account_id == target_account_id:
        raise AccountConflict("an account cannot be linked to itself")

    locked = {
        account.id: account
        for account in db.execute(
            select(Account)
            .where(Account.id.in_([alias_account_id, target_account_id]))
            .with_for_update()
        ).scalars()
    }
    alias = locked.get(alias_account_id)
    target = locked.get(target_account_id)

    if alias is None or target is None:
        raise AccountNotFound("alias or target account does not exist")
    if alias.kind is not AccountKind.local:
        raise AccountConflict("only local accounts can be linked")
    if target.kind is not AccountKind.user:
        raise AccountConflict("the target must be a real user account")
    if alias.owner_account_id != actor_account_id:
        raise AccountNotFound("only the owner of the local account can link it")

    if (
        db.scalar(select(Entry.id).where(Entry.created_by_account_id == alias_account_id).limit(1))
        is not None
    ):
        raise AccountConflict("a local account cannot be an entry creator")

    pair = or_(
        Entry.payer_account_id == alias_account_id,
        Entry.payee_account_id == alias_account_id,
    )
    entry_ids = list(db.scalars(select(Entry.id).where(pair)))

    if entry_ids:
        db.execute(
            update(Entry)
            .where(Entry.payer_account_id == alias_account_id)
            .values(payer_account_id=target_account_id)
        )
        db.execute(
            update(Entry)
            .where(Entry.payee_account_id == alias_account_id)
            .values(payee_account_id=target_account_id)
        )
        if relabel_pending:
            db.execute(
                update(Entry)
                .where(Entry.id.in_(entry_ids), Entry.provisional.is_(True))
                .values(
                    status=EntryStatus.pending,
                    provisional=False,
                    decided_by_account_id=None,
                    decided_at=None,
                )
            )

    db.delete(alias)
    db.flush()
    db.commit()
    return len(entry_ids)


class AccountError(Exception):
    """Base class for expected account failures."""


class AccountNotFound(AccountError):
    pass


class AccountConflict(AccountError):
    pass


def create_local_account(db: Session, *, owner_account_id: int, display_name: str) -> Account:
    """Create a nickname owned by one account. Names are unique per owner."""
    name = display_name.strip()
    if not name:
        raise AccountError("display name must not be blank")
    existing = db.scalar(
        select(Account.id).where(
            Account.owner_account_id == owner_account_id,
            Account.display_name == name,
        )
    )
    if existing is not None:
        raise AccountConflict("you already have a contact with that name")

    account = Account(kind=AccountKind.local, display_name=name, owner_account_id=owner_account_id)
    db.add(account)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AccountConflict("you already have a contact with that name") from exc
    return account


def list_contacts(db: Session, *, account_id: int) -> list[Account]:
    """Nicknames I own plus real accounts I already have entries with."""
    owned = select(Account.id).where(
        Account.owner_account_id == account_id,
        Account.kind == AccountKind.local,
    )
    counterparties = union(
        select(Entry.payer_account_id).where(Entry.payee_account_id == account_id),
        select(Entry.payee_account_id).where(Entry.payer_account_id == account_id),
    )
    return list(
        db.scalars(
            select(Account)
            .where(or_(Account.id.in_(owned), Account.id.in_(counterparties)))
            .order_by(Account.display_name, Account.id)
        )
    )


def visible_account(db: Session, *, account_id: int, viewer_account_id: int) -> Account:
    """An account the viewer may see: themselves, their own nickname, or a ledger counterparty."""
    account = db.get(Account, account_id)
    if account is None:
        raise AccountNotFound
    if account.id == viewer_account_id or account.owner_account_id == viewer_account_id:
        return account
    shares_entry = db.scalar(
        select(Entry.id)
        .where(
            or_(
                Entry.payer_account_id == viewer_account_id,
                Entry.payee_account_id == viewer_account_id,
            ),
            or_(Entry.payer_account_id == account.id, Entry.payee_account_id == account.id),
        )
        .limit(1)
    )
    if shares_entry is None:
        raise AccountNotFound
    return account


def find_user_by_username(db: Session, username: str) -> User | None:
    """Exact match on a real user's login name. Local nicknames are never found."""
    normalized = username.strip().lower()
    if not normalized:
        return None
    return db.scalar(select(User).where(User.username == normalized))
