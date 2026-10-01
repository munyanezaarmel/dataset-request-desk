from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('client','operator','admin')", name="ck_users_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    organisation: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Episode(Base):
    __tablename__ = "episodes"
    __table_args__ = (
        CheckConstraint("quality IN ('good','usable','bad')", name="ck_episodes_quality"),
        CheckConstraint("duration_seconds > 0", name="ck_episodes_duration_positive"),
        Index("ix_episodes_recorded_at", "recorded_at"),
        Index("ix_episodes_task_quality", "task_name", "quality"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    episode_id: Mapped[str] = mapped_column(String(50), unique=True)  # e.g. EP-00042
    robot_id: Mapped[str] = mapped_column(String(50))
    task_name: Mapped[str] = mapped_column(String(255))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int]
    operator_name: Mapped[str] = mapped_column(String(255))
    quality: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DatasetRequest(Base):
    __tablename__ = "requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('submitted','in_progress','delivered','accepted','rejected')",
            name="ck_requests_status",
        ),
        CheckConstraint("episodes_requested > 0", name="ck_requests_count_positive"),
        Index("ix_requests_client_id", "client_id"),
        Index("ix_requests_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    task_name: Mapped[str] = mapped_column(String(255))
    episodes_requested: Mapped[int]
    deadline: Mapped[date] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), server_default="submitted")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class StatusHistory(Base):
    """Audit trail: one row per status change (who, when, from, to)."""

    __tablename__ = "request_status_history"
    __table_args__ = (Index("ix_status_history_request_id", "request_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id", ondelete="CASCADE"))
    from_status: Mapped[str | None] = mapped_column(String(20))  # NULL = creation
    to_status: Mapped[str] = mapped_column(String(20))
    changed_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Assignment(Base):
    """An episode assigned to a request.

    The PRIMARY KEY is the episode itself, so the database physically cannot
    hold two rows for the same episode: "at most one request per episode".
    """

    __tablename__ = "assignments"
    __table_args__ = (Index("ix_assignments_request_id", "request_id"),)

    episode_pk: Mapped[int] = mapped_column(ForeignKey("episodes.id"), primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id", ondelete="CASCADE"))
    assigned_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )