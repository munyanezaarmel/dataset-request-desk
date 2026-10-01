"""Query helpers shared by the requests and assignments routers."""
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Assignment, DatasetRequest, User
from ..schemas import RequestOut


def request_query():
    """SELECT for RequestOut: the request + client info + how many episodes are assigned."""
    assigned = (
        select(func.count())
        .select_from(Assignment)
        .where(Assignment.request_id == DatasetRequest.id)
        .correlate(DatasetRequest)
        .scalar_subquery()
    )
    return select(
        DatasetRequest, User.name.label("client_name"), User.organisation, assigned.label("assigned_count")
    ).join(User, User.id == DatasetRequest.client_id)


def to_out(row) -> RequestOut:
    req = row[0]
    return RequestOut(
        id=req.id,
        client_id=req.client_id,
        client_name=row.client_name,
        organisation=row.organisation,
        task_name=req.task_name,
        episodes_requested=req.episodes_requested,
        assigned_count=row.assigned_count,
        deadline=req.deadline,
        notes=req.notes,
        status=req.status,
        created_at=req.created_at,
        updated_at=req.updated_at,
    )


def load_request(db: Session, request_id: int, user: User, lock: bool = False) -> DatasetRequest:
    """Fetch a request the caller is allowed to see. Clients only see their own;
    for anything else we answer 404 (not 403) so ids can't be probed."""
    query = select(DatasetRequest).where(DatasetRequest.id == request_id)
    if user.role == "client":
        query = query.where(DatasetRequest.client_id == user.id)
    if lock:
        query = query.with_for_update()  # row lock: others wait until we commit
    req = db.scalar(query)
    if req is None:
        raise HTTPException(404, "Request not found")
    return req


def request_out(db: Session, request_id: int) -> RequestOut:
    return to_out(db.execute(request_query().where(DatasetRequest.id == request_id)).one())