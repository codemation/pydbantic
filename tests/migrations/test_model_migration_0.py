import pytest

from pydbantic import Database, DataBaseModel


class Data(DataBaseModel):
    a: int
    b: float
    c: str = "test"
    i: str


@pytest.mark.asyncio
async def test_model_migrations_0_init(db_url):
    db = await Database.create(db_url, tables=[Data], cache_enabled=False, testing=True)
    data_items = await Data.select("*")
    if len(data_items) == 0:
        for i in range(10):
            data = Data(a=i + 1, b=i + 2, c=i + 3, i=i)
            await data.insert()
