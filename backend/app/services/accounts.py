"""Account lifecycle: local nicknames and linking them to real users."""

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.models import Account, AccountKind, Entry, EntryStatus


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
        raise ValueError("an account cannot be linked to itself")

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
        raise ValueError("alias or target account does not exist")
    if alias.kind is not AccountKind.local:
        raise ValueError("only local accounts can be linked")
    if target.kind is not AccountKind.user:
        raise ValueError("the target must be a real user account")
    if alias.owner_account_id != actor_account_id:
        raise ValueError("only the owner of the local account can link it")

    if (
        db.scalar(select(Entry.id).where(Entry.created_by_account_id == alias_account_id).limit(1))
        is not None
    ):
        raise ValueError("a local account cannot be an entry creator")

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
