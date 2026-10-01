from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..constants import ASSIGNABLE_QUALITIES
from ..db import get_db
from ..deps import require_roles
from ..models import Assignment, Episode, User
from ..schemas import AssignIn, RequestOut
from ..services.request_queries import load_request, request_out

router = APIRouter(prefix="/requests", tags=["assignments"])
staff = require_roles("operator", "admin")


@router.post("/{request_id}/assignments", response_model=RequestOut)
def assign_episodes(
    request_id: int,
    body: AssignIn,
    user: User = Depends(staff),
    db: Session = Depends(get_db),
):
    # Lock the request so a concurrent "deliver" cannot slip in between our checks.
    req = load_request(db, request_id, user, lock=True)
    if req.status != "in_progress":
        raise HTTPException(409, f"Episodes can only be assigned while a request is in_progress (now '{req.status}')")

    wanted = sorted({e.strip().upper() for e in body.episode_ids})
    episodes = db.scalars(select(Episode).where(Episode.episode_id.in_(wanted))).all()

    unknown = sorted(set(wanted) - {e.episode_id for e in episodes})
    if unknown:
        raise HTTPException(404, f"Unknown episodes: {', '.join(unknown)}")

    bad_quality = [e.episode_id for e in episodes if e.quality not in ASSIGNABLE_QUALITIES]
    if bad_quality:
        raise HTTPException(409, f"Only good/usable episodes can be assigned. Not allowed: {', '.join(sorted(bad_quality))}")

    taken = db.scalars(
        select(Episode.episode_id)
        .join(Assignment, Assignment.episode_pk == Episode.id)
        .where(Episode.id.in_([e.id for e in episodes]))
    ).all()
    if taken:
        raise HTTPException(409, f"Already assigned to a request: {', '.join(sorted(taken))}")

    db.add_all(Assignment(episode_pk=e.id, request_id=req.id, assigned_by=user.id) for e in episodes)
    try:
        db.commit()
    except IntegrityError:
        # Someone assigned one of these episodes to ANOTHER request in the split second
        # after our check above. The primary key on assignments.episode_pk stopped it.
        db.rollback()
        raise HTTPException(409, "One of these episodes was just assigned to another request")
    return request_out(db, request_id)


@router.delete("/{request_id}/assignments/{episode_id}", response_model=RequestOut)
def unassign_episode(
    request_id: int,
    episode_id: str,
    user: User = Depends(staff),
    db: Session = Depends(get_db),
):
    req = load_request(db, request_id, user, lock=True)
    if req.status != "in_progress":
        raise HTTPException(409, f"Episodes can only be removed while a request is in_progress (now '{req.status}')")
    assignment = db.scalar(
        select(Assignment)
        .join(Episode, Episode.id == Assignment.episode_pk)
        .where(Episode.episode_id == episode_id.strip().upper(), Assignment.request_id == request_id)
    )
    if assignment is None:
        raise HTTPException(404, "That episode is not assigned to this request")
    db.delete(assignment)
    db.commit()
    return request_out(db, request_id)