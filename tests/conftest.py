from __future__ import annotations

import os

# Ensure tests never require real provider credentials.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("DEFAULT_BUSINESS_ID", "demo_salon")
