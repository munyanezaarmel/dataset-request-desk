from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_roles
from ..models import Assignment, Episode, User
from ..schemas import EpisodeList, EpisodeListItem

router = APIRouter(prefix="/episodes", tags=["episodes"])
staff = require_roles("operator", "admin")


@router.get("", response_model=EpisodeList)
def list_episodes(
    task_name: str | None = None,
    quality: str | None = None,
    robot_id: str | None = None,
    available_only: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(staff),
    db: Session = Depends(get_db),
):
    filters = []
    if task_name:
        filters.append(Episode.task_name == " ".join(task_name.split()).lower())
    if quality:
        filters.append(Episode.quality == quality.lower())
    if robot_id:
        filters.append(Episode.robot_id == robot_id.lower())
    if available_only:
        filters.append(Assignment.episode_pk.is_(None))  # the LEFT JOIN found no assignment

    source = select(Episode).outerjoin(Assignment, Assignment.episode_pk == Episode.id).where(*filters)
    total = db.scalar(select(func.count()).select_from(source.subquery()))
    rows = db.execute(
        select(Episode, Assignment.request_id)
        .outerjoin(Assignment, Assignment.episode_pk == Episode.id)
        .where(*filters)
        .order_by(Episode.episode_id)
        .limit(limit)
        .offset(offset)
    ).all()
    items = [
        EpisodeListItem(
            **{c: getattr(e, c) for c in EpisodeListItem.model_fields if c != "assigned_request_id"},
            assigned_request_id=request_id,
        )
        for e, request_id in rows
    ]
    return EpisodeList(items=items, total=total)


@router.get("/task-names", response_model=list[str])
def task_names(user: User = Depends(staff), db: Session = Depends(get_db)):
    """Distinct task names, for the filter dropdown in the UI."""
    return db.scalars(select(Episode.task_name).distinct().order_by(Episode.task_name)).all()