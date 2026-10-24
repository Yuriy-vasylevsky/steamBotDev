"""Restore trusted administrator PostgreSQL custom-format backups atomically."""
import asyncio
import os
import re
from pathlib import Path

from sqlalchemy.engine import make_url


async def pg_command(*args, database_url=None):
    env = os.environ.copy()
    if database_url:
        url = make_url(database_url)
        env.update(PGHOST=url.host or "localhost", PGPORT=str(url.port or 5432),
                   PGUSER=url.username or "", PGPASSWORD=url.password or "",
                   PGDATABASE=url.database or "", PGOPTIONS="-c lock_timeout=10000 -c statement_timeout=300000")
    process = await asyncio.create_subprocess_exec(*args, env=env,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    try:
        output, _ = await asyncio.wait_for(process.communicate(), timeout=360)
    except BaseException:
        if process.returncode is None:
            process.kill()
        await process.wait()
        raise
    if process.returncode:
        raise ValueError("PostgreSQL command failed")
    return output


async def validate_backup(path):
    with Path(path).open("rb") as stream:
        if stream.read(5) != b"PGDMP":
            raise ValueError("Expected PostgreSQL custom-format backup")
    listing = (await pg_command("pg_restore", "--list", str(path))).decode()
    for table in ("users", "products", "orders", "alembic_version"):
        if not re.search(r" TABLE public " + table + r" ", listing):
            raise ValueError("Missing shop table")
    version = (await pg_command("pg_restore", "--data-only", "--table=alembic_version", "--file=-", str(path))).decode()
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    head = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
    if not re.search(r"(?m)^" + re.escape(head) + r"\r?$", version):
        raise ValueError("Backup schema version differs from application")


async def restore_backup(path, database_url):
    await validate_backup(path)
    await pg_command("pg_restore", "--clean", "--if-exists", "--single-transaction",
                     "--exit-on-error", "--no-owner", "--no-privileges",
                     "--dbname=" + make_url(database_url).database, str(path),
                     database_url=database_url)
