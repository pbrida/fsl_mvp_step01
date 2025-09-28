# tests/conftest.py
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Make sure models are imported so Base has all tables
from fantasy_stocks import models  # noqa: F401
from fantasy_stocks.db import Base, get_db
from fantasy_stocks.main import app

# --- Enable test mode so idempotency decorator auto-fills keys ---
os.environ["TESTING"] = "1"

# Single in-memory DB shared across the whole process
TEST_DATABASE_URL = "sqlite+pysqlite://"


@pytest.fixture(scope="session")
def engine():
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # <<< key: share the same memory DB
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(engine):
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    # Override app DB dependency to use our shared in-memory session
    def _get_db_override():
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override

    from starlette.testclient import TestClient

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
