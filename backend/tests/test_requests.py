"""Step 4: creating requests, who can see them, and the status rules that need no episodes."""
import pytest

PROTECTED = [("GET", "/requests"), ("POST", "/requests"), ("GET", "/requests/1"), ("POST", "/requests/1/transition")]


@pytest.mark.parametrize("method,path", PROTECTED)
def test_endpoints_require_a_token(client, method, path):
    assert client.request(method, path).status_code == 401


def test_only_clients_create_requests(client, H):
    body = {"task_name": "pick cup", "episodes_requested": 5, "deadline": "2026-12-01"}
    assert client.post("/requests", json=body, headers=H["ops"]).status_code == 403
    assert client.post("/requests", json=body, headers=H["admin"]).status_code == 403
    assert client.post("/requests", json=body, headers=H["client_a"]).status_code == 201


def test_request_validation(client, H):
    base = {"task_name": "pick cup", "episodes_requested": 5, "deadline": "2026-12-01"}
    for bad in ({"episodes_requested": 0}, {"episodes_requested": -3}, {"deadline": "not-a-date"}, {"task_name": ""}):
        assert client.post("/requests", json={**base, **bad}, headers=H["client_a"]).status_code == 422


def test_task_name_is_normalised(client, H):
    body = {"task_name": "  Pick   CUP ", "episodes_requested": 1, "deadline": "2026-12-01"}
    assert client.post("/requests", json=body, headers=H["client_a"]).json()["task_name"] == "pick cup"


def test_client_sees_only_own_requests(client, H, make_request):
    a = make_request("client_a")
    b = make_request("client_b")
    assert [r["id"] for r in client.get("/requests", headers=H["client_a"]).json()] == [a]
    assert client.get(f"/requests/{a}", headers=H["client_a"]).status_code == 200
    assert client.get(f"/requests/{b}", headers=H["client_a"]).status_code == 404  # not 403: no id probing
    assert {r["id"] for r in client.get("/requests", headers=H["ops"]).json()} == {a, b}


def test_status_filter(client, H, make_request, move):
    a = make_request("client_a")
    b = make_request("client_b")
    move(b, "in_progress", "ops")
    ids = lambda s: [r["id"] for r in client.get("/requests", params={"status": s}, headers=H["ops"]).json()]
    assert ids("submitted") == [a] and ids("in_progress") == [b]


def test_new_request_starts_submitted_with_history(client, H, make_request):
    rid = make_request("client_a")
    detail = client.get(f"/requests/{rid}", headers=H["client_a"]).json()
    assert detail["status"] == "submitted" and detail["assigned_count"] == 0
    assert [(h["from_status"], h["to_status"], h["changed_by_name"]) for h in detail["history"]] == [
        (None, "submitted", "client_a")
    ]


def test_roles_own_their_steps(client, H, make_request, move):
    rid = make_request("client_a")
    assert move(rid, "in_progress", "client_a").status_code == 403  # clients cannot start work
    assert move(rid, "in_progress", "client_b").status_code == 404  # other clients cannot even see it
    assert move(rid, "in_progress", "ops").status_code == 200
    assert client.get(f"/requests/{rid}", headers=H["ops"]).json()["status"] == "in_progress"


@pytest.mark.parametrize("path", [
    ["delivered"],                        # skip in_progress
    ["accepted"],                         # skip everything
    ["in_progress", "accepted"],          # accept before delivery
    ["in_progress", "rejected"],
    ["in_progress", "submitted"],         # going backwards
])
def test_invalid_transitions_are_refused(make_request, move, path):
    rid = make_request("client_a", episodes_requested=1)
    for step in path[:-1]:
        assert move(rid, step, "ops").status_code == 200
    # a move that does not exist is a 409 whoever asks
    assert move(rid, path[-1], "ops").status_code == 409
    assert move(rid, path[-1], "client_a").status_code == 409


def test_unknown_status_value_is_a_validation_error(client, H, make_request):
    rid = make_request("client_a")
    r = client.post(f"/requests/{rid}/transition", json={"to_status": "banana"}, headers=H["ops"])
    assert r.status_code == 422