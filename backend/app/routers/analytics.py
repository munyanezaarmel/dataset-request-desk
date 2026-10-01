from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Date, case, cast, extract, func, select
from sqlalchemy.orm import Session

from ..constants import STATUSES
from ..db import get_db
from ..deps import require_roles
from ..models import DatasetRequest, Episode, StatusHistory, User

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("")
def analytics(
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    user: User = Depends(require_roles("operator", "admin")),
    db: Session = Depends(get_db),
):
    """All numbers for the inclusive UTC date range [from, to]; default = last 30 days."""
    date_to = date_to or datetime.now(timezone.utc).date()
    date_from = date_from or date_to - timedelta(days=29)
    if date_from > date_to:
        raise HTTPException(422, "'from' must not be after 'to'")
    if (date_to - date_from).days > 366:
        raise HTTPException(422, "Range too large (max 366 days)")

    start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
    end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)  # exclusive

    # 1) episodes per day per robot ------------------------------------------------
    day = cast(func.timezone("UTC", Episode.recorded_at), Date).label("day")
    per_day_robot = db.execute(
        select(day, Episode.robot_id, func.count().label("episodes"))
        .where(Episode.recorded_at >= start, Episode.recorded_at < end)
        .group_by(day, Episode.robot_id)
        .order_by(day, Episode.robot_id)
    ).all()

    # 2) requests by status (requests created in range) ----------------------------
    counts = dict(
        db.execute(
            select(DatasetRequest.status, func.count())
            .where(DatasetRequest.created_at >= start, DatasetRequest.created_at < end)
            .group_by(DatasetRequest.status)
        ).all()
    )

    # 3) median submitted -> delivered ---------------------------------------------
    # Per request: first time it became 'delivered' minus the time it was submitted.
    submitted_at = func.min(case((StatusHistory.to_status == "submitted", StatusHistory.changed_at)))
    delivered_at = func.min(case((StatusHistory.to_status == "delivered", StatusHistory.changed_at)))
    durations = (
        select(extract("epoch", delivered_at - submitted_at).label("seconds"))
        .group_by(StatusHistory.request_id)
        .having(delivered_at.is_not(None), submitted_at >= start, submitted_at < end)
        .subquery()
    )
    median_seconds, delivered_count = db.execute(
        select(func.percentile_cont(0.5).within_group(durations.c.seconds), func.count()).select_from(durations)
    ).one()

    # 4) top 5 tasks by number of GOOD episodes ------------------------------------
    top_tasks = db.execute(
        select(Episode.task_name, func.count().label("good_episodes"))
        .where(Episode.quality == "good", Episode.recorded_at >= start, Episode.recorded_at < end)
        .group_by(Episode.task_name)
        .order_by(func.count().desc(), Episode.task_name)
        .limit(5)
    ).all()

    return {
        "from": date_from,
        "to": date_to,
        "episodes_per_day_per_robot": [
            {"day": r.day, "robot_id": r.robot_id, "episodes": r.episodes} for r in per_day_robot
        ],
        "requests_by_status": {s: counts.get(s, 0) for s in STATUSES},
        "median_submitted_to_delivered": {
            "seconds": float(median_seconds) if median_seconds is not None else None,
            "requests_counted": delivered_count,
        },
        "top_tasks_by_good_episodes": [
            {"task_name": r.task_name, "good_episodes": r.good_episodes} for r in top_tasks
        ],
    }