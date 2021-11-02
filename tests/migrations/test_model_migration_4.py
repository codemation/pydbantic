from logging import exception
import time
import pytest
from pydbantic import Database

@pytest.mark.asyncio
async def test_model_migrations_4_new(new_model_3, db_url):
    Data = new_model_3
    try:
        db = await Database.create(
            db_url,
            tables=[Data],
            cache_enabled=False
        )
        assert False, f"Migration should have failed due to primary key YNIQUE constraint failed: Data.d"
    except Exception:
        assert True