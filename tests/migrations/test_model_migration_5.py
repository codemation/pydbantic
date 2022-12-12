import uuid
import pytest
from typing import Optional
from pydbantic import Database, DataBaseModel, PrimaryKey, Default

def get_uuid():
    return str(uuid.uuid4())

class Data(DataBaseModel):
    a: int
    b_new: float = PrimaryKey()
    c: str
    d: list
    e: Optional[str] = Default(default=get_uuid, ) #  new column with default
    i: str

@pytest.mark.order(5)
@pytest.mark.asyncio
async def test_model_migrations_5_new(db_url):
    try:
        db = await Database.create(
            db_url,
            tables=[Data],
            cache_enabled=False
        )
    except Exception:
        return
    assert False, f"Migration after changing primary key should fail"