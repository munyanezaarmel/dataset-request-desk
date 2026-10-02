from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user, require_roles
from ..models import Assignment, DatasetRequest, Episode, StatusHistory, User
from ..schemas import (
    EpisodeOut,
    HistoryOut,
    RequestCreate,
    RequestDetail,
    RequestOut,
    Status,
    TransitionIn,
)
from ..services.request_queries import load_request, request_out, request_query, to_out
from ..services.workflow import apply_transition

router = APIRouter(prefix="/requests", tags=["requests"])


@router.post("", response_model=RequestOut, status_code=201)
def create_request(
    body: RequestCreate,
    user: User = Depends(require_roles("client")),
    db: Session = Depends(get_db),
):
    req = DatasetRequest(client_id=user.id, status="submitted", **body.model_dump())
    db.add(req)
    db.flush()  # assigns req.id without committing yet
    db.add(StatusHistory(request_id=req.id, from_status=None, to_status="submitted", changed_by=user.id))
    db.commit()  # request and its first history row are saved together, or not at all
    return request_out(db, req.id)


@router.get("", response_model=list[RequestOut])
def list_requests(
    status: Status | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = request_query()
    if user.role == "client":
        query = query.where(DatasetRequest.client_id == user.id)  # clients: own requests only
    if status:
        query = query.where(DatasetRequest.status == status)
    query = query.order_by(DatasetRequest.created_at.desc(), DatasetRequest.id.desc())
    return [to_out(r) for r in db.execute(query.limit(limit).offset(offset)).all()]


@router.get("/{request_id}", response_model=RequestDetail)
def get_request(request_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    load_request(db, request_id, user)  # 404 if it does not exist or is not yours
    history = db.execute(
        select(StatusHistory, User.name)
        .join(User, User.id == StatusHistory.changed_by)
        .where(StatusHistory.request_id == request_id)
        .order_by(StatusHistory.id)
    ).all()
    episodes = db.scalars(
        select(Episode)
        .join(Assignment, Assignment.episode_pk == Episode.id)
        .where(Assignment.request_id == request_id)
        .order_by(Episode.episode_id)
    ).all()
    return RequestDetail(
        **request_out(db, request_id).model_dump(),
        history=[
            HistoryOut(
                from_status=h.from_status,
                to_status=h.to_status,
                changed_by=h.changed_by,
                changed_by_name=name,
                changed_at=h.changed_at,
            )
            for h, name in history
        ],
        episodes=[EpisodeOut.model_validate(e, from_attributes=True) for e in episodes],
    )


@router.post("/{request_id}/transition", response_model=RequestOut)
def transition(
    request_id: int,
    body: TransitionIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    req = load_request(db, request_id, user, lock=True)  # lock the row while we decide
    apply_transition(db, req, body.to_status, user)  # raises 409/403 if not allowed
    db.commit()  # status change + history row saved together
    return request_out(db, request_id)
