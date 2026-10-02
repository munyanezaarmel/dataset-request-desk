"""Create the seed users (and load the sample episodes on an empty database).
Safe to run many times: existing users are left alone."""
import json
import logging
import os
from pathlib import Path

from sqlalchemy import func, select

from .config import settings
from .db import SessionLocal
from .logging_conf import setup_logging
from .models import Episode, User
from .security import hash_password
from .services.importer import import_episodes

logger = logging.getLogger("app.seed")


def find_seed_dir() -> Path:
    for candidate in (settings.seed_dir, Path(__file__).resolve().parents[2] / "seed"):
        if (Path(candidate) / "users.json").exists():
            return Path(candidate)
    raise SystemExit("Seed directory with users.json not found (set SEED_DIR)")


def main() -> None:
    setup_logging()
    seed_dir = find_seed_dir()
    with SessionLocal() as db:
        created = 0
        for entry in json.loads((seed_dir / "users.json").read_text()):
            if db.scalar(select(User).where(User.email == entry["email"].lower())):
                continue
            db.add(
                User(
                    email=entry["email"].lower(),
                    name=entry["name"],
                    password_hash=hash_password(entry["password"]),  # plain text never stored
                    role=entry["role"],
                    organisation=entry.get("organisation"),
                    is_active=True,
                )
            )
            created += 1
        db.commit()
        logger.info("seed users", extra={"fields": {"created": created}})

        csv_path = seed_dir / "episodes.csv"
        if csv_path.exists() and db.scalar(select(func.count()).select_from(Episode)) == 0:
            report = import_episodes(db, csv_path.read_bytes())
            logger.info(
                "seed episodes",
                extra={"fields": {"imported": report["imported"], "skipped": report["skipped"]}},
            )


if __name__ == "__main__":
    main()
    