from logging import exception
import time
from attr import has
import pytest

from pydbantic import Database

@pytest.mark.asyncio
async def test_model_migrations_6_new(new_model_5, db_url):
    Data, SubData = new_model_5
    db = await Database.create(
        db_url,
        tables=[Data],
        cache_enabled=False,
    )
        
    data_items = await Data.all()

    for data in data_items:
        assert hasattr(data, 'sub')
        data.sub = SubData()
        await data.update()

    assert len(data_items) == 10