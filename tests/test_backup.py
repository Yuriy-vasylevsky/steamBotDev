from app.admin import pg_dump_url
from unittest.mock import AsyncMock

import pytest

from app.database_restore import restore_backup, validate_backup


def test_pg_dump_url_uses_standard_postgres_scheme():
    assert (
        pg_dump_url("postgresql+asyncpg://user:password@db:5432/steamsell")
        == "postgresql://user:password@db:5432/steamsell"
    )


async def test_restore_rejects_non_dump_before_running_postgres(tmp_path, monkeypatch):
    source = tmp_path / "invalid.dump"
    source.write_bytes(b"not a database")
    command = AsyncMock()
    monkeypatch.setattr("app.database_restore.pg_command", command)
    with pytest.raises(ValueError):
        await validate_backup(source)
    command.assert_not_called()


async def test_restore_validates_schema_and_uses_atomic_transaction(tmp_path, monkeypatch):
    source = tmp_path / "valid.dump"
    source.write_bytes(b"PGDMP")
    listing = "\n".join(f"1; 1 1 TABLE public {name} owner" for name in
                        ("users", "products", "orders", "alembic_version"))
    command = AsyncMock(side_effect=[listing.encode(), b"COPY public.alembic_version (version_num) FROM stdin;\n0032\n\\.\n", b""])
    monkeypatch.setattr("app.database_restore.pg_command", command)
    await restore_backup(source, "postgresql+asyncpg://user:password@db/shop")
    args = command.call_args.args
    assert "--single-transaction" in args
    assert "--exit-on-error" in args
    assert "--clean" in args
    assert not any("password" in arg for arg in args)


async def test_restore_rejects_different_schema(tmp_path, monkeypatch):
    source = tmp_path / "old.dump"
    source.write_bytes(b"PGDMP")
    listing = "\n".join(f"1; 1 1 TABLE public {name} owner" for name in
                        ("users", "products", "orders", "alembic_version"))
    command = AsyncMock(side_effect=[listing.encode(), b"0030\n"])
    monkeypatch.setattr("app.database_restore.pg_command", command)
    with pytest.raises(ValueError):
        await restore_backup(source, "postgresql://user:password@db/shop")
    assert command.call_count == 2
