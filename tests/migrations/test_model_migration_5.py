from logging import exception
import time
import pytest
from pydbantic import Database

@pytest.mark.asyncio
async def test_model_migrations_5_new(new_model_4, db_url):
    Data = new_model_4
    db = await Database.create(
        db_url,
        tables=[Data],
        cache_enabled=False
    )
        
    data_items = await Data.all()
    for i, data in enumerate(data_items):
        if i == 0:
            assert data.e
            continue
        assert data.e != data_items[i-1].e
    
    assert len(data_items) == 10

    await Data.refresh_models()

    data_items = await Data.all()
    assert len(data_items) == 10