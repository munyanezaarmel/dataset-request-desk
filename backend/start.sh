#!/bin/sh
set -e
alembic upgrade head        # 1. create/update the tables
python -m app.seed          # 2. seed users (+ sample episodes if empty)
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log "$@"   # 3. run the API
