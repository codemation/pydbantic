import time
import pytest
from pydbantic import Database

@pytest.mark.asyncio
async def test_model_migrations_0_init(init_model, db_url):
    Data = init_model
    db = await Database.create(
        db_url,
        tables=[Data],
        cache_enabled=False
    )
    data_items = await Data.select('*')
    if len(data_items) == 0:
        for i in range(1000):
            data = Data(a=i+1, b=i+2, c=i+3)
            await data.insert()