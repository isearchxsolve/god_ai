"""Scratch: provision life_archive role/db on local PostgreSQL, verify login."""

import asyncio
import os
import urllib.parse

import asyncpg
from dotenv import load_dotenv

load_dotenv()

PW = urllib.parse.urlparse(os.environ["DATABASE_URL"]).password
APP_DSN = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")


async def main():
    admin = await asyncpg.connect("postgresql://postgres:postgres@localhost:5432/postgres")
    # token_urlsafe charset is safe to inline; DDL cannot take bound params
    roles = await admin.fetch("SELECT rolname FROM pg_roles")
    if not any(r["rolname"] == "life_archive" for r in roles):
        await admin.execute(f"CREATE ROLE life_archive LOGIN PASSWORD '{PW}'")
        print("created role life_archive")
    else:
        await admin.execute(f"ALTER USER life_archive WITH PASSWORD '{PW}'")
        print("role life_archive already exists; password synced")
    dbs = await admin.fetch("SELECT datname FROM pg_database")
    if not any(d["datname"] == "life_archive" for d in dbs):
        await admin.execute("CREATE DATABASE life_archive OWNER life_archive")
        print("created db life_archive")
    else:
        print("db life_archive already exists")
    await admin.close()

    conn = await asyncpg.connect(APP_DSN)
    version = await conn.fetchval("SELECT version()")
    print("connect as life_archive OK:", version.split(",")[0])
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
