"""CSV import: cleaning, reporting and idempotency."""
from pathlib import Path

HEADER = "episode_id,robot_id,task_name,recorded_at,duration_seconds,operator_name,quality\n"
SAMPLE = Path(__file__).resolve().parents[2] / "seed" / "episodes.csv"


def upload(client, H, content: bytes, who="ops"):
    return client.post("/episodes/import", files={"file": ("e.csv", content, "text/csv")}, headers=H[who])


def row(**kw):
    v = dict(id="EP-1", robot="arm-01", task="pick cup", at="2026-09-01T10:00:00", dur="30", op="Eric", q="good")
    v.update(kw)
    return f"{v['id']},{v['robot']},{v['task']},{v['at']},{v['dur']},{v['op']},{v['q']}\n"


def test_import_is_idempotent(client, H):
    content = (HEADER + row(id="EP-1") + row(id="EP-2")).encode()
    first = upload(client, H, content).json()
    assert (first["imported"], first["skipped"]) == (2, 0)
    second = upload(client, H, content).json()
    assert (second["imported"], second["skipped"]) == (0, 2)
    assert second["skipped_by_reason"] == {"already_exists": 2}
    assert client.get("/episodes", headers=H["ops"]).json()["total"] == 2  # still just 2 rows


def test_sample_file_twice_gives_identical_database(client, H):
    data = SAMPLE.read_bytes()
    first = upload(client, H, data).json()
    total_after_first = client.get("/episodes", headers=H["ops"]).json()["total"]
    second = upload(client, H, data).json()
    assert first["imported"] == total_after_first > 150
    assert second["imported"] == 0
    assert client.get("/episodes", headers=H["ops"]).json()["total"] == total_after_first
    # every row of the file is accounted for, first time and second time
    assert first["rows_read"] == first["imported"] + first["skipped"]


def test_sample_file_report_names_each_problem(client, H):
    report = upload(client, H, SAMPLE.read_bytes()).json()
    reasons = report["skipped_by_reason"]
    assert reasons["duplicate_in_file"] >= 4          # 3 repeated ids + ep-00003 (lower case)
    for code in ("blank_row", "wrong_column_count", "unknown_robot", "invalid_quality",
                 "invalid_date", "invalid_duration", "missing_value"):
        assert code in reasons, code
    by_id = {(s["episode_id"], s["reason"]) for s in report["skipped_rows"]}
    assert ("EP-24", "unknown_robot") not in by_id  # sanity: ids are stored as in the file
    assert ("EP-00024", "unknown_robot") in by_id
    assert ("EP-90001", "wrong_column_count") in by_id
    assert ("EP-90003", "invalid_duration") in by_id and ("EP-90004", "invalid_duration") in by_id


def test_messy_values_are_normalised(client, H):
    content = HEADER + row(id="ep-7", robot=" ARM-02 ", task="  Pick   CUP ", q="Good", at="14/08/2026 09:15") \
        + row(id="EP-8", at="2026-08-01 10:00:00") + row(id="EP-9", at="2026-08-01T10:00:00Z")
    report = upload(client, H, content.encode()).json()
    assert report["imported"] == 3
    items = {e["episode_id"]: e for e in client.get("/episodes", headers=H["ops"]).json()["items"]}
    assert items["EP-7"]["robot_id"] == "arm-02" and items["EP-7"]["task_name"] == "pick cup"
    assert items["EP-7"]["quality"] == "good"
    assert items["EP-7"]["recorded_at"].startswith("2026-08-14T09:15")  # day-first date understood


def test_first_duplicate_wins_and_conflicts_do_not_overwrite(client, H):
    content = HEADER + row(id="EP-1", q="good") + row(id="EP-1", q="bad")
    report = upload(client, H, content.encode()).json()
    assert report["skipped_by_reason"] == {"duplicate_in_file": 1}
    upload(client, H, (HEADER + row(id="EP-1", q="bad")).encode())  # different data, existing id
    ep = client.get("/episodes", headers=H["ops"]).json()["items"][0]
    assert ep["quality"] == "good"  # the existing record was left untouched


def test_bad_rows_do_not_block_good_rows(client, H):
    content = HEADER + row(id="EP-1", robot="arm-99") + row(id="EP-2") + "\n" + "EP-3,arm-01,pick cup\n" + row(id="EP-4", dur="-5")
    report = upload(client, H, content.encode()).json()
    assert report["imported"] == 1 and report["skipped"] == 4
    lines = {s["line"]: s["reason"] for s in report["skipped_rows"]}
    assert lines == {2: "unknown_robot", 4: "blank_row", 5: "wrong_column_count", 6: "invalid_duration"}


def test_wrong_header_or_encoding_is_a_400(client, H):
    assert upload(client, H, b"a,b,c\n1,2,3\n").status_code == 400
    assert upload(client, H, b"\xff\xfe\x00bad").status_code == 400


def test_import_requires_a_token(client):
    assert client.post("/episodes/import").status_code == 401


def test_clients_cannot_import(client, H):
    assert upload(client, H, (HEADER + row()).encode(), who="client_a").status_code == 403