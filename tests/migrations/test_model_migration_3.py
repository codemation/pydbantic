import time
import pytest
from pydbantic import Database

@pytest.mark.asyncio
async def test_model_migrations_3_new(new_model_2, db_url):
    Data = new_model_2
    db = await Database.create(
        db_url,
        tables=[Data],
        cache_enabled=False
    )
    data_items = await Data.all()
    assert data_items[0].b_new == 2.0

    db.metadata.drop_all()