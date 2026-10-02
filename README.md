# Dataset Request Desk

Internal platform for Neotix: clients request robot-teleoperation datasets, operators fulfil them
by assigning episodes, clients accept or reject the delivery.

**Stack:** FastAPI + SQLAlchemy + Alembic + PostgreSQL (backend), Next.js + TypeScript (frontend), Docker Compose.

## Run it

```bash
docker compose up --build
```

| What | Where |
|---|---|
| Web app | http://localhost:3000 |
| API + interactive docs | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |

On start the backend applies the migrations, creates the seed users and (only if the database is
empty) imports the sample `seed/episodes.csv`. Nothing else to run.

### Log in with

| Email | Password | Role |
|---|---|---|
| admin@example.com | admin123 | admin |
| ops1@example.com / ops2@example.com | ops123 | operator |
| client-a@example.com / client-b@example.com | client123 | client |

(Seed passwords live in `seed/users.json` for development only; the database stores bcrypt hashes.)

## Tests

```bash
docker compose exec backend pytest
```

Tests run against a real Postgres database (`dataset_desk_test`, created automatically and rebuilt
from the Alembic migrations each run).

## Importing episodes

Web: log in as an operator, open **Import episodes**. API:

```bash
TOKEN=$(curl -s localhost:8000/auth/login -H 'content-type: application/json' \
  -d '{"email":"ops1@example.com","password":"ops123"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -s localhost:8000/episodes/import -H "Authorization: Bearer $TOKEN" -F file=@seed/episodes.csv
```

The import is idempotent and returns a report (imported, skipped, reason per skipped row).

## Analytics at 5 million episodes

All four analytics queries run inside PostgreSQL; the API never loads episodes into Python.

- **Episodes per day per robot** and **top tasks** filter on `recorded_at`, which has an index
  (`ix_episodes_recorded_at`), and top tasks also uses `(task_name, quality)`. For a short date range
  Postgres reads only the matching rows. For a very wide range it must still count millions of rows.
- **What I would add first:** a composite index `(recorded_at, robot_id)`, then a daily summary table
  (`day, robot_id, count`) updated on import, then monthly partitioning of `episodes`.
- **Median delivery time** reads the status-history table, which has far fewer rows than episodes
  (one row per status change), so it stays fast.
- **How I would check:** `EXPLAIN ANALYZE`, using `seed/generate_episodes.py` to generate a large file.

**Live demo:** https://dataset-desk-web.onrender.com
> Free hosting: the demo sleeps when idle, so the first load can take 1-2 minutes.
> Demo logins: client-a@example.com / client123, ops1@example.com / ops123.

## Design notes

See [NOTES.md](NOTES.md).
