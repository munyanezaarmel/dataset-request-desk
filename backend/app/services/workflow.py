"""The rules for moving a request between statuses live HERE and only here."""
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Assignment, DatasetRequest, StatusHistory, User

# (from_status, to_status) -> roles allowed to make that move
TRANSITIONS: dict[tuple[str, str], set[str]] = {
    ("submitted", "in_progress"): {"operator", "admin"},
    ("in_progress", "delivered"): {"operator", "admin"},
    ("delivered", "accepted"): {"client"},
    ("delivered", "rejected"): {"client"},
    ("rejected", "in_progress"): {"operator", "admin"},  # rework
}


def count_assigned(db: Session, request_id: int) -> int:
    return db.scalar(
        select(func.count()).select_from(Assignment).where(Assignment.request_id == request_id)
    )


def apply_transition(db: Session, req: DatasetRequest, to_status: str, actor: User) -> None:
    """Validate and perform a status change. The caller must hold a row lock
    on `req` (SELECT ... FOR UPDATE) and commit afterwards."""
    allowed_roles = TRANSITIONS.get((req.status, to_status))
    if allowed_roles is None:
        raise HTTPException(409, f"Cannot move a request from '{req.status}' to '{to_status}'")
    if actor.role not in allowed_roles:
        raise HTTPException(
            403, f"Role '{actor.role}' cannot move a request from '{req.status}' to '{to_status}'"
        )
    if to_status == "delivered":
        assigned = count_assigned(db, req.id)
        if assigned < req.episodes_requested:
            raise HTTPException(
                409,
                f"Cannot deliver: {req.episodes_requested} episodes requested "
                f"but only {assigned} assigned",
            )

    db.add(
        StatusHistory(
            request_id=req.id, from_status=req.status, to_status=to_status, changed_by=actor.id
        )
    )
    req.status = to_status
    req.updated_at = datetime.now(timezone.utc)
    