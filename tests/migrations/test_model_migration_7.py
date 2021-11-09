from logging import exception
import time
import uuid
from attr import has
import pytest


from pydbantic import Database, DataBaseModel, PrimaryKey, Default
from pydantic import BaseModel

def get_uuid():
    return str(uuid.uuid4())

class SubData(BaseModel):
    a: int = 1
    b: float = 1.0

class Data(DataBaseModel):
    a: int
    b_new: float
    c: str
    d: list
    e: str = PrimaryKey(default=get_uuid)
    i: str
    sub: SubData = None

@pytest.mark.asyncio
async def test_model_migrations_7_new(db_url):
    db = await Database.create(
        db_url,
        tables=[Data],
        cache_enabled=False
    )
    data_items = await Data.all()
    for data in data_items:
        assert hasattr(data, 'sub')
    
    await Data.refresh_models()
    data_items = await Data.all()

    assert len(data_items) == 10