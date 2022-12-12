import uuid
import pytest
from typing import Optional
from pydantic import BaseModel
from pydbantic import Database, DataBaseModel, PrimaryKey, Default

def get_uuid():
    return str(uuid.uuid4())

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
    sub: Optional[SubData] = None


@pytest.mark.order(6)
@pytest.mark.asyncio
async def test_model_migrations_6_new(db_url):
    db = await Database.create(
        db_url,
        tables=[Data],
        cache_enabled=False,
    )

    data_items = await Data.all()

    for data in data_items:
        assert hasattr(data, 'sub')
        assert data.sub is None

        data.sub = SubData()
        await data.update()
        
    data_items = await Data.all()
    for data in data_items:
        assert data.sub is not None

    assert len(data_items) == 10