import uuid
from typing import Optional

import pytest

from pydbantic import Database, DataBaseModel, Default, PrimaryKey


def get_uuid():
    return str(uuid.uuid4())


class Data(DataBaseModel):
    a: int = PrimaryKey()
    b_new: float
    c: str
    d: list
    e: Optional[str] = Default(
        default=get_uuid,
    )  #  new column with default
    i: str


@pytest.mark.asyncio
async def test_model_migrations_4_new(db_url):
    db = await Database.create(db_url, tables=[Data], cache_enabled=False, debug=True)
    # assert other things
    data = await Data.all()
    for data_ins in data:
        assert hasattr(data_ins, "e")

    new_ins = Data(**{k: v for k, v in data[0].dict().items() if k != "e"})
    await new_ins.save()
    new_ins = await Data.get(a=new_ins.a)
    assert new_ins.e is not None
