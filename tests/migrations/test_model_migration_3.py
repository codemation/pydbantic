import time
import pytest
from pydbantic import Database, DataBaseModel

class Data(DataBaseModel):
    __renamed__ = [
        {'old_name': 'b', 'new_name': 'b_new'}
    ]
    a: int
    b_new: float # renamed
    c: str = 'test'
    d: list = [1,2]
    i: str

@pytest.mark.order(3)
@pytest.mark.asyncio
async def test_model_migrations_3_new(db_url):
    """
    test migration when a colunn is renamed
    b -> b_new
    """
    db = await Database.create(
        db_url,
        tables=[Data],
        cache_enabled=False
    )
    data_items = await Data.all()
    assert data_items[0].b_new == 2.0