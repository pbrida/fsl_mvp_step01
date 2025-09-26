# alembic/env.py
from __future__ import annotations

import os
from logging.config import fileConfig
from typing import Any, Dict, cast

from alembic import context
from sqlalchemy import engine_from_config, pool

# Alembic Config object
config = context.config

# Setup Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- Import your app's metadata so autogenerate can see models ---
from fantasy_stocks.db import Base  # noqa: E402

target_metadata = Base.metadata

# Options helpful for SQLite + autogenerate
COMPARE_TYPE = True
RENDER_AS_BATCH = True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")

    # Allow DATABASE_URL env var to override (optional)
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        url = env_url

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=COMPARE_TYPE,
        render_as_batch=RENDER_AS_BATCH,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode'."""
    # get_section may return None; coalesce and cast for type-checkers
    section = cast(Dict[str, Any], config.get_section(config.config_ini_section) or {})

    # Optional: allow DATABASE_URL to override alembic.ini
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        section["sqlalchemy.url"] = env_url

    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=COMPARE_TYPE,
            render_as_batch=RENDER_AS_BATCH,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
