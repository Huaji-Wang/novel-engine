"""Dump the SQLite schema of the configured database.

Usage: python scripts/inspect_db.py [path-to-db]
Without an argument the path is read from database.url in config.yaml.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SQLITE_PREFIX = "sqlite:///"


def _db_path() -> Path:
    if len(sys.argv) > 1:
        return Path(sys.argv[1])
    config = PROJECT_ROOT / "config.yaml"
    if not config.is_file():
        raise SystemExit(f"{config.name} not found; pass a database path instead")
    url = ((yaml.safe_load(config.read_text(encoding="utf-8")) or {}).get("database") or {}).get("url", "")
    if not url.startswith(SQLITE_PREFIX):
        raise SystemExit(f"only sqlite urls are supported, got: {url or '<empty>'}")
    return PROJECT_ROOT / url[len(SQLITE_PREFIX) :]


def main() -> None:
    path = _db_path()
    if not path.is_file():
        raise SystemExit(f"database not found: {path}")
    conn = sqlite3.connect(path)
    for name, sql in conn.execute(
        "select name, sql from sqlite_master where type='table'"
    ):
        print(f"=== {name} ===")
        print(sql)
        print()


if __name__ == "__main__":
    main()
