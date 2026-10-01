"""Test assignment rules, delivery rules and the concurrent-assignment race."""
import threading

import pytest
from fastapi.testclient import TestClient

from app.main import app


def start_request(make_request, move, who="client_a", **kw):
    rid = make_request(who, **kw)
    assert move(rid, "in_progress", "ops").status_code == 200
    return rid


def assign(client, H, rid, ids, who="ops"):
    return client.post(f"/requests/{rid}/assignments", json={"episode_ids": ids}, headers=H[who])


@pytest.mark.parametrize("method,path", [("GET", "/episodes"), ("GET", "/episodes/task-names"),
                                          ("POST", "/requests/1/assignments")])
def test_endpoints_require_a_token(client, method, path):
    assert client.request(method, path).status_code == 401


def test_clients_cannot_use_staff_endpoints(client, H, make_request, make_episodes, move):
    rid = start_request(make_request, move)
    assert client.get("/episodes", headers=H["client_a"]).status_code == 403
    assert client.get("/episodes/task-names", headers=H["client_a"]).status_code == 403
    assert assign(client, H, rid, make_episodes(1), who="client_a").status_code == 403


def test_good_and_usable_can_be_assigned(client, H, make_request, make_episodes, move):
    rid = start_request(make_request, move, episodes_requested=2)
    ids = make_episodes(1, quality="good") + make_episodes(1, quality="usable")
    r = assign(client, H, rid, ids)
    assert r.status_code == 200 and r.json()["assigned_count"] == 2


def test_bad_episodes_are_refused_and_nothing_is_saved(client, H, make_request, make_episodes, move):
    rid = start_request(make_request, move, episodes_requested=2)
    good = make_episodes(1, quality="good")
    bad = make_episodes(1, quality="bad")
    r = assign(client, H, rid, good + bad)
    assert r.status_code == 409 and bad[0] in r.json()["detail"]
    assert client.get(f"/requests/{rid}", headers=H["ops"]).json()["assigned_count"] == 0  # all or nothing


def test_episode_cannot_belong_to_two_requests(client, H, make_request, make_episodes, move):
    r1 = start_request(make_request, move)
    r2 = start_request(make_request, move, "client_b")
    ep = make_episodes(1)
    assert assign(client, H, r1, ep).status_code == 200
    second = assign(client, H, r2, ep)
    assert second.status_code == 409 and ep[0] in second.json()["detail"]


def test_assigning_twice_to_same_request_is_also_refused(client, H, make_request, make_episodes, move):
    rid = start_request(make_request, move)
    ep = make_episodes(1)
    assert assign(client, H, rid, ep).status_code == 200
    assert assign(client, H, rid, ep).status_code == 409


def test_unknown_episode_is_404(client, H, make_request, move):
    rid = start_request(make_request, move)
    assert assign(client, H, rid, ["EP-99999"]).status_code == 404


def test_only_while_in_progress(client, H, make_request, make_episodes, move):
    rid = make_request("client_a")  # still 'submitted'
    ep = make_episodes(1)
    assert assign(client, H, rid, ep).status_code == 409
    move(rid, "in_progress", "ops")
    assert assign(client, H, rid, ep).status_code == 200
    move(rid, "delivered", "ops")
    assert assign(client, H, rid, make_episodes(1)).status_code == 409  # frozen once delivered
    assert client.delete(f"/requests/{rid}/assignments/{ep[0]}", headers=H["ops"]).status_code == 409


def test_unassign_frees_the_episode_for_another_request(client, H, make_request, make_episodes, move):
    r1 = start_request(make_request, move)
    r2 = start_request(make_request, move, "client_b")
    ep = make_episodes(1)
    assign(client, H, r1, ep)
    assert client.delete(f"/requests/{r1}/assignments/{ep[0]}", headers=H["ops"]).status_code == 200
    assert assign(client, H, r2, ep).status_code == 200
    assert client.delete(f"/requests/{r1}/assignments/{ep[0]}", headers=H["ops"]).status_code == 404  # wrong request


def test_cannot_deliver_without_enough_episodes(client, H, make_request, make_episodes, move):
    rid = make_request("client_a", episodes_requested=3)
    move(rid, "in_progress", "ops")
    assert move(rid, "delivered", "ops").status_code == 409             # 0 of 3
    assign(client, H, rid, make_episodes(2))
    assert move(rid, "delivered", "ops").status_code == 409             # 2 of 3
    assign(client, H, rid, make_episodes(1))
    assert move(rid, "delivered", "ops").status_code == 200             # 3 of 3
    history = client.get(f"/requests/{rid}", headers=H["ops"]).json()["history"]
    assert [h["to_status"] for h in history] == ["submitted", "in_progress", "delivered"]  # refused moves leave no trace


def test_happy_path_and_history(client, H, make_request, make_episodes, move):
    rid = make_request("client_a", episodes_requested=2)
    move(rid, "in_progress", "ops")
    assign(client, H, rid, make_episodes(2))
    assert move(rid, "delivered", "ops").status_code == 200
    assert move(rid, "accepted", "client_a").json()["status"] == "accepted"
    detail = client.get(f"/requests/{rid}", headers=H["client_a"]).json()
    assert [(h["from_status"], h["to_status"], h["changed_by_name"]) for h in detail["history"]] == [
        (None, "submitted", "client_a"),
        ("submitted", "in_progress", "ops"),
        ("in_progress", "delivered", "ops"),
        ("delivered", "accepted", "client_a"),
    ]
    assert all(h["changed_at"] for h in detail["history"]) and len(detail["episodes"]) == 2


def test_only_the_owning_client_can_accept_or_reject(client, H, make_request, make_episodes, move):
    rid = make_request("client_a", episodes_requested=1)
    move(rid, "in_progress", "ops")
    assign(client, H, rid, make_episodes(1))
    assert move(rid, "delivered", "client_a").status_code == 403
    move(rid, "delivered", "ops")
    assert move(rid, "accepted", "ops").status_code == 403      # operators cannot accept
    assert move(rid, "accepted", "admin").status_code == 403    # neither can admins
    assert move(rid, "rejected", "ops").status_code == 403
    assert move(rid, "accepted", "client_b").status_code == 404  # another client cannot even see it
    assert client.get(f"/requests/{rid}", headers=H["client_a"]).json()["status"] == "delivered"


def test_rejection_leads_to_rework_and_second_delivery(client, H, make_request, make_episodes, move):
    rid = make_request("client_a", episodes_requested=1)
    move(rid, "in_progress", "ops")
    assign(client, H, rid, make_episodes(1))
    move(rid, "delivered", "ops")
    assert move(rid, "rejected", "client_a").status_code == 200
    assert move(rid, "in_progress", "ops2").status_code == 200  # rework
    assert move(rid, "delivered", "ops").status_code == 200     # assignments were kept
    assert move(rid, "accepted", "client_a").status_code == 200


def test_nothing_leaves_accepted(client, H, make_request, make_episodes, move):
    rid = make_request("client_a", episodes_requested=1)
    move(rid, "in_progress", "ops")
    assign(client, H, rid, make_episodes(1))
    move(rid, "delivered", "ops")
    move(rid, "accepted", "client_a")
    for target in ("submitted", "in_progress", "delivered", "rejected", "accepted"):
        assert move(rid, target, "ops").status_code == 409


def test_episode_list_filters_and_availability(client, H, make_request, make_episodes, move):
    rid = start_request(make_request, move)
    make_episodes(2, task_name="pick cup", quality="good")
    taken = make_episodes(1, task_name="fold towel", quality="usable")
    make_episodes(1, task_name="fold towel", quality="bad")
    assign(client, H, rid, taken)

    def ids(**params):
        return {e["episode_id"] for e in client.get("/episodes", params=params, headers=H["ops"]).json()["items"]}

    assert len(ids(task_name="fold towel")) == 2
    assert len(ids(quality="good")) == 2
    assert len(ids(task_name="fold towel", quality="bad")) == 1
    assert taken[0] not in ids(available_only=True)
    listing = client.get("/episodes", headers=H["ops"]).json()
    assert listing["total"] == 4
    assert {i["episode_id"]: i["assigned_request_id"] for i in listing["items"]}[taken[0]] == rid
    assert client.get("/episodes/task-names", headers=H["ops"]).json() == ["fold towel", "pick cup"]


def test_concurrent_assignment_of_same_episode_has_exactly_one_winner(make_request, make_episodes, move, H):
    """Two operators click 'assign' on the same episode for two DIFFERENT requests at the
    same moment. The application-level check can pass for both; the database primary key
    on assignments.episode_pk makes sure only one commit succeeds."""
    r1 = start_request(make_request, move)
    r2 = start_request(make_request, move, "client_b")
    ep = make_episodes(1)
    barrier = threading.Barrier(2)
    results = []

    def worker(rid, who):
        with TestClient(app) as c:
            barrier.wait()
            results.append(assign(c, H, rid, ep, who).status_code)

    threads = [threading.Thread(target=worker, args=(r1, "ops")), threading.Thread(target=worker, args=(r2, "ops2"))]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(results) == [200, 409]