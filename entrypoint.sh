#!/bin/sh
set -e

echo "Menunggu database siap..."
python <<'EOF'
import os
import time

from sqlalchemy import create_engine

database_url = os.environ["DATABASE_URL"]

for attempt in range(30):
    try:
        engine = create_engine(database_url)
        with engine.connect():
            break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit("Database tidak siap setelah 30 detik.")
EOF

echo "Menjalankan seed admin..."
python seed_admin.py

echo "Menjalankan API..."
exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
