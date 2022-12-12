import time
import sys
import pytest
from pydbantic import Database, DataBaseModel

class Data(DataBaseModel):
    a: int
    b: float
    c: str = 'test'
    d: tuple = (1,2) # added column
    i: str

@pytest.mark.order(1)
@pytest.mark.asyncio
async def test_model_migrations_1_new(db_url):
    db = await Database.create(
        db_url,
        tables=[Data],
        cache_enabled=False
    )
    data_items = await Data.select('*')
    assert data_items[0].d == (1,2)