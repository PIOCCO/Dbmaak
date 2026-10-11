import os
import subprocess
import sys
from pathlib import Path


def _run_alembic(db_url: str, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATABASE_URL": db_url}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_fresh_database_reaches_head(tmp_path: Path) -> None:
    db = tmp_path / "fresh.db"
    url = f"sqlite+pysqlite:///{db}"
    result = _run_alembic(url, "upgrade", "head")
    assert result.returncode == 0, result.stderr
    assert db.exists()


def test_legacy_database_upgrades_from_0001_to_head(tmp_path: Path) -> None:
    db = tmp_path / "legacy.db"
    url = f"sqlite+pysqlite:///{db}"
    first = _run_alembic(url, "upgrade", "20261011_0001")
    assert first.returncode == 0, first.stderr
    second = _run_alembic(url, "upgrade", "head")
    assert second.returncode == 0, second.stderr
