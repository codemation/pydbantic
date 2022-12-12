import uuid
from typing import Optional
import pytest


from pydbantic import Database, DataBaseModel, PrimaryKey, Default
from pydantic import BaseModel

def get_uuid():
    return str(uuid.uuid4())

class Related(DataBaseModel):
    f: str = PrimaryKey(default=get_uuid)
    g: str = 'abcd1234'

class SubData(BaseModel):
    a: int = 1
    b: float = 1.0

class Data(DataBaseModel):
    a: int = PrimaryKey(default=get_uuid)
    b_new: float
    c: str
    d: list
    e: str = None
    i: str
    sub: SubData = None
    related: Optional[Related] = None

@pytest.mark.order(7)
@pytest.mark.asyncio
async def test_model_migrations_7_new(db_url):
    db = await Database.create(
        db_url,
        tables=[
            Data,
            Related
        ],
        cache_enabled=False
    )
    data_items = await Data.all()
    for data in data_items:
        assert hasattr(data, 'related')

    assert len(data_items) == 10