"""Test authentication , users, health and logging."""
import logging

import pytest

PROTECTED = [("GET", "/auth/me"), ("GET", "/users"), ("POST", "/users")]


@pytest.mark.parametrize("method,path", PROTECTED)
def test_endpoints_require_a_token(client, method, path):
    assert client.request(method, path).status_code == 401


def test_garbage_token_is_rejected(client):
    r = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401


def test_login_success_and_failures(client):
    ok = client.post("/auth/login", json={"email": "ops@test.com", "password": "password123"})
    assert ok.status_code == 200 and ok.json()["access_token"]
    assert client.post("/auth/login", json={"email": "ops@test.com", "password": "wrong"}).status_code == 401
    assert client.post("/auth/login", json={"email": "nobody@test.com", "password": "x"}).status_code == 401


def test_deactivated_user_is_locked_out_immediately(client, H):
    created = client.post("/users", headers=H["admin"], json={
        "email": "temp@test.com", "name": "Temp", "password": "password123", "role": "operator"})
    assert created.status_code == 201
    token = client.post("/auth/login", json={"email": "temp@test.com", "password": "password123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/auth/me", headers=headers).status_code == 200

    client.patch(f"/users/{created.json()['id']}", headers=H["admin"], json={"is_active": False})
    assert client.get("/auth/me", headers=headers).status_code == 401  # same token, now refused


def test_users_are_admin_only(client, H):
    body = {"email": "new@test.com", "name": "New", "password": "password123", "role": "client"}
    assert client.get("/users", headers=H["client_a"]).status_code == 403
    assert client.post("/users", json=body, headers=H["ops"]).status_code == 403
    assert client.get("/users", headers=H["ops"]).status_code == 403
    assert client.post("/users", json=body, headers=H["admin"]).status_code == 201


def test_duplicate_email_and_weak_password(client, H):
    body = {"email": "dup@test.com", "name": "Dup", "password": "password123", "role": "client"}
    assert client.post("/users", json=body, headers=H["admin"]).status_code == 201
    assert client.post("/users", json=body, headers=H["admin"]).status_code == 409
    assert client.post("/users", json={**body, "email": "x@test.com", "password": "short"}, headers=H["admin"]).status_code == 422


def test_admin_cannot_demote_or_deactivate_self(client, H):
    me = client.get("/auth/me", headers=H["admin"]).json()
    assert client.patch(f"/users/{me['id']}", json={"role": "operator"}, headers=H["admin"]).status_code == 409
    assert client.patch(f"/users/{me['id']}", json={"is_active": False}, headers=H["admin"]).status_code == 409


def test_log_line_contains_user_id_when_authenticated(client, H, caplog):
    me = client.get("/auth/me", headers=H["ops"]).json()
    caplog.clear()  # forget the log line produced by the /auth/me call above
    with caplog.at_level(logging.INFO, logger="app.request"):
        client.get("/auth/me", headers=H["ops"])
        client.get("/health")
    fields = [r.fields for r in caplog.records if r.name == "app.request"]
    assert fields[0]["user_id"] == me["id"] and fields[0]["path"] == "/auth/me" and fields[0]["status"] == 200
    assert fields[1]["user_id"] is None and fields[1]["path"] == "/health"
    assert "duration_ms" in fields[0] and fields[0]["method"] == "GET"


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}