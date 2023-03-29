import pytest

from pydbantic import Database, DataBaseModel


@pytest.mark.asyncio
async def test_multiple_database():
    class DB1Model1(DataBaseModel):
        __tablename__ = "model1"
        data: str
        data2: str

    class DB2Model1(DataBaseModel):
        __tablename__ = "model1"
        data: str
        data2: str

    db1 = await Database.create("sqlite:///db1", tables=[DB1Model1])
    db2 = await Database.create("sqlite:///db2", tables=[DB2Model1])

    assert not await DB1Model1.all()
    assert not await DB2Model1.all()

    await DB1Model1.create(data="1", data2="2")
    assert await DB1Model1.all()
    assert not await DB2Model1.all()
