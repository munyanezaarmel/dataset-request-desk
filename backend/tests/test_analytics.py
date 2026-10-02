"""Analytics numbers checked against a small dataset worked out by hand."""
from datetime import datetime, timezone

from sqlalchemy import text

from app.db import engine


def set_history_time(request_id, to_status, when):
    with engine.begin() as conn:
        conn.execute(text("UPDATE request_status_history SET changed_at = :w WHERE request_id = :r AND to_status = :s"),
                     {"w": when, "r": request_id, "s": to_status})


def test_episodes_per_day_per_robot_and_top_tasks(client, H, make_episodes):
    d = lambda day, hour=10: datetime(2026, 9, day, hour, 0, tzinfo=timezone.utc)
    make_episodes(2, robot_id="arm-01", recorded_at=d(1), task_name="pick cup", quality="good")
    make_episodes(1, robot_id="arm-02", recorded_at=d(1), task_name="pick cup", quality="bad")
    make_episodes(3, robot_id="arm-01", recorded_at=d(2), task_name="fold towel", quality="good")
    make_episodes(1, robot_id="arm-01", recorded_at=d(2), task_name="open drawer", quality="usable")
    make_episodes(5, robot_id="arm-01", recorded_at=d(20), task_name="wipe table", quality="good")  # outside range

    data = client.get("/analytics", params={"from": "2026-09-01", "to": "2026-09-02"}, headers=H["ops"]).json()
    assert data["episodes_per_day_per_robot"] == [
        {"day": "2026-09-01", "robot_id": "arm-01", "episodes": 2},
        {"day": "2026-09-01", "robot_id": "arm-02", "episodes": 1},
        {"day": "2026-09-02", "robot_id": "arm-01", "episodes": 4},
    ]
    # only GOOD episodes count: fold towel 3, pick cup 2 (the 'bad' and 'usable' ones are ignored)
    assert data["top_tasks_by_good_episodes"] == [
        {"task_name": "fold towel", "good_episodes": 3},
        {"task_name": "pick cup", "good_episodes": 2},
    ]


def test_top_tasks_is_limited_to_five(client, H, make_episodes):
    for i in range(7):
        make_episodes(1, task_name=f"task {i}", quality="good")
    data = client.get("/analytics", params={"from": "2026-09-01", "to": "2026-09-01"}, headers=H["ops"]).json()
    assert len(data["top_tasks_by_good_episodes"]) == 5


def test_request_counts_and_median_delivery_time(client, H, make_request, make_episodes, move):
    def deliver(hours):
        rid = make_request("client_a", episodes_requested=1)
        move(rid, "in_progress", "ops")
        client.post(f"/requests/{rid}/assignments", json={"episode_ids": make_episodes(1)}, headers=H["ops"])
        move(rid, "delivered", "ops")
        set_history_time(rid, "submitted", datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc))
        set_history_time(rid, "delivered", datetime(2026, 9, 10, 8 + hours, 0, tzinfo=timezone.utc))
        return rid

    for hours in (1, 3, 8):
        deliver(hours)                      # median of 1h, 3h, 8h is 3h
    make_request("client_b")                # stays 'submitted'
    from app.db import engine as e
    with e.begin() as conn:                 # put all requests inside the queried date range
        conn.execute(text("UPDATE requests SET created_at = '2026-09-10T08:00:00Z'"))

    data = client.get("/analytics", params={"from": "2026-09-01", "to": "2026-09-30"}, headers=H["ops"]).json()
    assert data["requests_by_status"] == {"submitted": 1, "in_progress": 0, "delivered": 3, "accepted": 0, "rejected": 0}
    assert data["median_submitted_to_delivered"] == {"seconds": 3 * 3600.0, "requests_counted": 3}


def test_median_is_null_when_nothing_delivered(client, H):
    data = client.get("/analytics", headers=H["ops"]).json()
    assert data["median_submitted_to_delivered"] == {"seconds": None, "requests_counted": 0}


def test_bad_date_range_is_rejected(client, H):
    assert client.get("/analytics", params={"from": "2026-09-30", "to": "2026-09-01"}, headers=H["ops"]).status_code == 422
    assert client.get("/analytics", params={"from": "2020-01-01", "to": "2026-09-01"}, headers=H["ops"]).status_code == 422


def test_analytics_is_staff_only(client, H):
    assert client.get("/analytics").status_code == 401
    assert client.get("/analytics", headers=H["client_a"]).status_code == 403
    assert client.get("/analytics", headers=H["admin"]).status_code == 200
    