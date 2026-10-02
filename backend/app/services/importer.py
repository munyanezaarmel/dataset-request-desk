"""CSV import of episodes: clean each row, validate it, insert safely, report everything."""
import csv
import io
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..constants import KNOWN_ROBOTS, MAX_DURATION_SECONDS, QUALITIES
from ..models import Episode

EXPECTED_COLUMNS = [
    "episode_id", "robot_id", "task_name", "recorded_at",
    "duration_seconds", "operator_name", "quality",
]
BATCH_SIZE = 1000
MAX_REPORTED_SKIPS = 1000


class RowError(Exception):
    """Raised when a row must be skipped. `code` groups reasons, `message` explains."""

    def __init__(self, code: str, message: str):
        self.code, self.message = code, message


class FileError(Exception):
    """The file as a whole is unusable (e.g. wrong header)."""


def parse_timestamp(raw: str) -> datetime:
    """Accepts ISO-8601 (T or space separator, optional Z/offset) and DD/MM/YYYY HH:MM.
    Timestamps without a timezone are treated as UTC."""
    raw = raw.strip()
    try:
        value = datetime.fromisoformat(raw)
    except ValueError:
        try:
            value = datetime.strptime(raw, "%d/%m/%Y %H:%M")  # day first, see NOTES.md
        except ValueError:
            raise RowError("invalid_date", f"unparseable date '{raw}'")
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


def clean_row(cells: dict[str, str]) -> dict:
    """Normalise one CSV row into a dict ready for the database, or raise RowError."""
    for column, value in cells.items():
        if not value.strip():
            raise RowError("missing_value", f"missing value for '{column}'")

    episode_id = cells["episode_id"].strip().upper()
    if not (episode_id.startswith("EP-") and episode_id[3:].isdigit()):
        raise RowError("invalid_episode_id", f"invalid episode_id '{cells['episode_id'].strip()}'")

    robot_id = cells["robot_id"].strip().lower()
    if robot_id not in KNOWN_ROBOTS:
        raise RowError("unknown_robot", f"unknown robot '{robot_id}'")

    quality = cells["quality"].strip().lower()
    if quality not in QUALITIES:
        raise RowError("invalid_quality", f"invalid quality '{cells['quality'].strip()}'")

    raw_duration = cells["duration_seconds"].strip()
    if not raw_duration.isdigit():  # rejects "-5", "45.5", "N/A"
        raise RowError("invalid_duration", f"duration must be a whole positive number, got '{raw_duration}'")
    duration = int(raw_duration)
    if not 0 < duration <= MAX_DURATION_SECONDS:
        raise RowError("invalid_duration", f"duration {duration}s outside 1-{MAX_DURATION_SECONDS}")

    return {
        "episode_id": episode_id,
        "robot_id": robot_id,
        "task_name": " ".join(cells["task_name"].split()).lower(),
        "recorded_at": parse_timestamp(cells["recorded_at"]),
        "duration_seconds": duration,
        "operator_name": " ".join(cells["operator_name"].split()),
        "quality": quality,
    }


def import_episodes(db: Session, raw: bytes) -> dict:
    try:
        text = raw.decode("utf-8-sig")  # utf-8-sig also strips an Excel BOM
    except UnicodeDecodeError:
        raise FileError("File is not valid UTF-8 text")

    reader = csv.reader(io.StringIO(text, newline=""))
    header = [h.strip().lower() for h in next(reader, [])]
    if header != EXPECTED_COLUMNS:
        raise FileError(f"Unexpected header. Expected: {','.join(EXPECTED_COLUMNS)}")

    skipped: list[dict] = []
    reasons: Counter = Counter()
    valid: list[tuple[int, dict]] = []  # (line number, cleaned row)
    seen: set[str] = set()
    rows_read = 0

    def skip(line: int, episode_id: str | None, code: str, message: str) -> None:
        reasons[code] += 1
        if len(skipped) < MAX_REPORTED_SKIPS:
            skipped.append({"line": line, "episode_id": episode_id, "reason": code, "detail": message})

    for cells in reader:
        rows_read += 1
        line = reader.line_num  # physical line in the file, handy for humans
        raw_id = cells[0].strip() if cells else None
        if not any(c.strip() for c in cells):
            skip(line, None, "blank_row", "row is empty")
            continue
        if len(cells) != len(EXPECTED_COLUMNS):
            skip(line, raw_id, "wrong_column_count", f"expected {len(EXPECTED_COLUMNS)} columns, got {len(cells)}")
            continue
        try:
            row = clean_row(dict(zip(EXPECTED_COLUMNS, cells)))
        except RowError as err:
            skip(line, raw_id, err.code, err.message)
            continue
        if row["episode_id"] in seen:
            skip(line, row["episode_id"], "duplicate_in_file", "episode_id appears earlier in this file (first one wins)")
            continue
        seen.add(row["episode_id"])
        valid.append((line, row))

    imported = 0
    for start in range(0, len(valid), BATCH_SIZE):
        batch = valid[start : start + BATCH_SIZE]
        statement = (
            insert(Episode)
            .values([row for _, row in batch])
            .on_conflict_do_nothing(index_elements=["episode_id"])  # makes re-imports safe
            .returning(Episode.episode_id)
        )
        inserted = set(db.execute(statement).scalars())
        imported += len(inserted)
        for line, row in batch:
            if row["episode_id"] not in inserted:
                skip(line, row["episode_id"], "already_exists", "episode already in the database (left unchanged)")
    db.commit()

    return {
        "rows_read": rows_read,
        "imported": imported,
        "skipped": sum(reasons.values()),
        "skipped_by_reason": dict(reasons),
        "skipped_rows": sorted(skipped, key=lambda s: s["line"]),
        "skipped_rows_truncated": sum(reasons.values()) > len(skipped),
    }
