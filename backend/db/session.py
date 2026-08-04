"""数据库引擎与会话管理。"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from backend.config import app_config
from backend.db.models import Base

_db_url = app_config().get("database_url", "sqlite:///./novel_engine.db")
_is_sqlite = _db_url.startswith("sqlite:///")
if _is_sqlite:
    Path(_db_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)

_engine = create_engine(_db_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)

if _is_sqlite:
    @event.listens_for(_engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record) -> None:
        # 后台 worker 与 HTTP 请求并发读写同一库：WAL + busy_timeout 避免锁冲突。
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=8000")
        cursor.close()

def _sqlite_ddl(column) -> str:
    """根据模型列类型生成 SQLite ADD COLUMN 的类型与默认值。"""
    type_name = type(column.type).__name__.upper()
    if "INT" in type_name:
        return "INTEGER DEFAULT 0"
    if type_name in ("DATETIME", "TIMESTAMP"):
        return "TIMESTAMP"
    if type_name == "JSON":
        return "TEXT DEFAULT 'null'"
    return "TEXT DEFAULT ''"


def _rename_incompatible_tables() -> None:
    """同名但主键类型不兼容的旧表（如其他工具留下的 VARCHAR 主键表）
    重命名为 legacy_<表名>，保留数据，让本引擎重建自己的表。"""
    inspector = inspect(_engine)
    existing = set(inspector.get_table_names())
    with _engine.begin() as conn:
        for table in Base.metadata.tables.values():
            if table.name not in existing:
                continue
            id_col = next(
                (c for c in inspector.get_columns(table.name) if c["name"] == "id"),
                None,
            )
            if id_col is not None and "INT" not in str(id_col["type"]).upper():
                target = f"legacy_{table.name}"
                suffix = 1
                while target in existing:
                    target = f"legacy_{table.name}_{suffix}"
                    suffix += 1
                conn.execute(text(
                    f"ALTER TABLE {table.name} RENAME TO {target}"))
                existing.add(target)


def init_db() -> None:
    """不兼容旧表重命名保留 → 建表 → 给旧表补齐新增列（不动旧列与数据）。"""
    _rename_incompatible_tables()
    Base.metadata.create_all(_engine)
    inspector = inspect(_engine)
    existing_tables = set(inspector.get_table_names())
    with _engine.begin() as conn:
        for table in Base.metadata.tables.values():
            if table.name not in existing_tables:
                continue
            existing_cols = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name not in existing_cols:
                    conn.execute(text(
                        f"ALTER TABLE {table.name} "
                        f"ADD COLUMN {column.name} {_sqlite_ddl(column)}"
                    ))


@contextmanager
def db_session() -> Session:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
