import time
import pytest
from pydbantic import Database

@pytest.mark.asyncio
async def test_model_migrations_1_new(new_model_1, db_url):
    Data = new_model_1
    db = await Database.create(
        db_url,
        tables=[Data],
        cache_enabled=False
    )
    data_items = await Data.select('*')
    assert data_items[0].d == (1,2)